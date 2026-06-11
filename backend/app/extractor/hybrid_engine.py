"""하이브리드 추출 엔진 — 규칙/텍스트LLM/VisionLLM 3계층 분기."""

import logging
from typing import Any

from app.extractor import rule_parser, text_llm, verifier, vision_llm
from app.extractor.llm_response_parser import ExtractionResult
from app.schemas.eligibility import (
    AnnouncementEligibility,
    EligibilityField,
    ExclusionItem,
)

logger = logging.getLogger(__name__)


async def extract_eligibility(
    announcement: dict[str, Any],
    routing_meta: dict | None = None
) -> AnnouncementEligibility:
    """공고 자격요건 추출 (3계층 분기 및 비용 인지형 라우팅 통합).

    Args:
        announcement: 14개 키 통합 스키마 dict
        routing_meta: tasks.py에서 ORM 기반으로 결정해서 전달하는 라우팅 메타데이터

    Returns:
        AnnouncementEligibility — fields + exclusions
    """
    if routing_meta and routing_meta.get("chosen_path"):
        chosen = routing_meta["chosen_path"]
        logger.info(f"[hybrid] 비용 인지형 라우팅 적용: chosen_path={chosen}")
        
        result = None
        if chosen == "rule_based":
            result = await _try_rule_based(announcement)
        elif chosen == "text_llm":
            result = await _try_text_llm(announcement)
        elif chosen == "vision_llm":
            result = await _try_vision_llm(announcement)
            
        if result is not None:
            return result
        logger.warning(f"[hybrid] 결정된 경로 {chosen} 실패 또는 결과 부족 → 기존 휴리스틱 분기로 Fallback")

    return await _heuristic_routing(announcement)


async def _try_rule_based(announcement: dict[str, Any]) -> AnnouncementEligibility:
    """1단계: 규칙 기반 파싱 단독 수행."""
    ann_id = str(announcement.get("source_id") or announcement.get("id") or "")
    title = announcement.get("title", "")
    rule_fields = rule_parser.parse_structured_fields(announcement)
    logger.info(f"[hybrid] 규칙 기반 단독 실행 완료: {len(rule_fields)}개 필드")
    return AnnouncementEligibility(
        announcement_id=ann_id,
        title=title,
        fields=rule_fields,
        exclusions=[],
    )


async def _try_text_llm(announcement: dict[str, Any]) -> AnnouncementEligibility | None:
    """2단계: 텍스트 LLM 단독 수행."""
    ann_id = str(announcement.get("source_id") or announcement.get("id") or "")
    title = announcement.get("title", "")
    combined_text = _build_combined_text(announcement)
    exclusion_text = announcement.get("exclusion_text") or ""

    if not combined_text:
        return None

    try:
        raw_text = await text_llm.extract(combined_text, exclusion_text)
        text_result = verifier.verify(raw_text)
        if text_result.error and not text_result.fields:
            # LLM 호출/파싱 실패로 빈 결과 — 휴리스틱 분기(규칙 fallback 포함)로 넘긴다
            logger.warning(f"[hybrid] 텍스트 LLM 단독 실행 오류 → fallback: {text_result.error}")
            return None
        logger.info(f"[hybrid] 텍스트 LLM 단독 실행 성공: {len(text_result.fields)}개 필드")
        return _build_announcement_eligibility(ann_id, title, text_result)
    except Exception as e:
        logger.warning(f"[hybrid] 텍스트 LLM 단독 실행 실패: {e}")
        return None


async def _try_vision_llm(announcement: dict[str, Any]) -> AnnouncementEligibility | None:
    """3단계: Vision LLM 단독 수행 (텍스트 LLM 병합 포함)."""
    ann_id = str(announcement.get("source_id") or announcement.get("id") or "")
    title = announcement.get("title", "")
    
    # 텍스트 LLM 결과 선행 시도
    combined_text = _build_combined_text(announcement)
    exclusion_text = announcement.get("exclusion_text") or ""
    text_result: ExtractionResult | None = None
    if combined_text:
        try:
            raw_text = await text_llm.extract(combined_text, exclusion_text)
            text_result = verifier.verify(raw_text)
        except Exception as e:
            logger.warning(f"[hybrid] vision 경로 text LLM 선행 시도 실패: {e}")

    pdf_path = _get_attachment_pdf_path(announcement)
    if not pdf_path:
        # PDF 파일이 없다면 내용 있는 텍스트 LLM 결과만 채택 (빈 결과면 휴리스틱 fallback)
        if text_result and (text_result.fields or text_result.exclusions):
            return _build_announcement_eligibility(ann_id, title, text_result)
        return None

    try:
        raw_vision = await vision_llm.extract_from_pdf(pdf_path)
        vision_result = verifier.verify(raw_vision)
        logger.info(f"[hybrid] Vision LLM 단독 실행 성공: {len(vision_result.fields)}개 필드")
        merged = _merge_results(text_result, vision_result)
        return _build_announcement_eligibility(ann_id, title, merged)
    except Exception as e:
        logger.warning(f"[hybrid] Vision LLM 단독 실행 실패: {e}")
        if text_result and (text_result.fields or text_result.exclusions):
            return _build_announcement_eligibility(ann_id, title, text_result)
        return None


async def _heuristic_routing(announcement: dict[str, Any]) -> AnnouncementEligibility:
    """기존의 휴리스틱 3계층 분기 라우팅 로직."""
    ann_id = str(announcement.get("source_id") or announcement.get("id") or "")
    title = announcement.get("title", "")
    logger.info(f"[hybrid] 휴리스틱 분기 시작: ann_id={ann_id}")

    # 1단계: 규칙 기반
    rule_fields = rule_parser.parse_structured_fields(announcement)
    logger.info(f"[hybrid] 1단계 규칙: {len(rule_fields)}개 필드")

    api_sufficient = rule_parser.is_api_text_sufficient(announcement)
    exclusion_sufficient = rule_parser.is_exclusion_sufficient(announcement)

    if api_sufficient and exclusion_sufficient:
        logger.info("[hybrid] 규칙만으로 충분 → 종료")
        return AnnouncementEligibility(
            announcement_id=ann_id,
            title=title,
            fields=rule_fields,
            exclusions=[],
        )

    # 2단계: 텍스트 LLM
    combined_text = _build_combined_text(announcement)
    exclusion_text = announcement.get("exclusion_text") or ""

    text_result: ExtractionResult | None = None
    if combined_text:
        try:
            raw_text = await text_llm.extract(combined_text, exclusion_text)
            text_result = verifier.verify(raw_text)
            logger.info(f"[hybrid] 2단계 텍스트 LLM: {len(text_result.fields)}개 필드")
        except Exception as e:
            logger.warning(f"[hybrid] 2단계 실패: {e}")

    if text_result and _is_text_llm_sufficient(text_result):
        logger.info("[hybrid] 텍스트 LLM 충분 → 종료")
        return _build_announcement_eligibility(ann_id, title, text_result)

    # 3단계: Vision LLM
    pdf_path = _get_attachment_pdf_path(announcement)
    vision_result: ExtractionResult | None = None
    if pdf_path:
        try:
            raw_vision = await vision_llm.extract_from_pdf(pdf_path)
            vision_result = verifier.verify(raw_vision)
            logger.info(f"[hybrid] 3단계 Vision LLM: {len(vision_result.fields)}개 필드")
        except Exception as e:
            logger.warning(f"[hybrid] 3단계 실패: {e}")

    if vision_result and (vision_result.fields or vision_result.exclusions):
        merged = _merge_results(text_result, vision_result)
        return _build_announcement_eligibility(ann_id, title, merged)
    if text_result and (text_result.fields or text_result.exclusions):
        # 에러로 빈 결과면 규칙 fallback이 살아야 하므로 내용 있는 경우에만 채택
        return _build_announcement_eligibility(ann_id, title, text_result)

    logger.warning("[hybrid] 모든 LLM 단계 실패 → 규칙 fallback")
    return AnnouncementEligibility(
        announcement_id=ann_id,
        title=title,
        fields=rule_fields,
        exclusions=[],
    )


def _is_text_llm_sufficient(result: ExtractionResult) -> bool:
    """텍스트 LLM 결과가 충분한지 판단.

    필드 3개 이상 + value/operator 명확한 비율 80% 이상.
    """
    if not result.fields or len(result.fields) < 3:
        return False

    clear_count = sum(
        1 for f in result.fields
        if f.condition.operator is not None and f.condition.value is not None
    )
    clear_ratio = clear_count / len(result.fields)
    return clear_ratio >= 0.8


def _build_combined_text(announcement: dict[str, Any]) -> str:
    """target_text + structured_tables markdown 통합. HWPX 첨부 표 LLM 입력에 포함."""
    target_text = announcement.get("target_text") or ""
    structured_tables = announcement.get("structured_tables") or []
    if not structured_tables:
        return target_text
    tables_md = "\n\n".join(
        f"## {t.get('name', f'표_{i}')}\n{t.get('markdown', '')}"
        for i, t in enumerate(structured_tables)
    )
    if not target_text:
        return f"# 첨부 표\n{tables_md}"
    return f"{target_text}\n\n# 첨부 표\n{tables_md}"


def _get_attachment_pdf_path(announcement: dict[str, Any]) -> str | None:
    """공고의 PDF 첨부파일 경로 반환 (없으면 None)."""
    attachments = announcement.get("attachments") or []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        if att.get("file_type") == "pdf" and att.get("local_path"):
            return att["local_path"]
        if att.get("converted_pdf_path"):
            return att["converted_pdf_path"]
    return None


def _merge_results(
    text_result: ExtractionResult | None,
    vision_result: ExtractionResult,
) -> ExtractionResult:
    """텍스트 LLM + Vision LLM 결과 병합. 같은 field_name은 vision 우선."""
    if text_result is None:
        return vision_result

    by_name: dict[str, EligibilityField] = {f.field_name: f for f in text_result.fields}
    for vf in vision_result.fields:
        by_name[vf.field_name] = vf

    merged_exclusions = list(dict.fromkeys(text_result.exclusions + vision_result.exclusions))

    return ExtractionResult(
        fields=list(by_name.values()),
        exclusions=merged_exclusions,
        processing_path="vision_llm",
    )


def _build_announcement_eligibility(
    ann_id: str,
    title: str,
    result: ExtractionResult,
) -> AnnouncementEligibility:
    return AnnouncementEligibility(
        announcement_id=ann_id,
        title=title,
        fields=result.fields,
        exclusions=[
            ExclusionItem(
                text=e,
                evidence_source="LLM 추출",
                processing_path=result.processing_path,
            )
            for e in result.exclusions
        ],
    )


if __name__ == "__main__":
    import asyncio

    print("=== 케이스 1: 규칙만으로 충분 ===")
    ann1 = {
        "source_id": "TEST001",
        "title": "테스트 공고 1",
        "target_text": "창업 후 3년 미만 중소기업, 강원도 소재, 만 39세 이하 청년 대표자",
        "exclusion_text": "휴폐업 기업, 국세 체납 기업, 금융기관 채무불이행",
        "attachments": [],
    }
    result = asyncio.run(extract_eligibility(ann1))
    print(f"필드: {len(result.fields)}개, 제외: {len(result.exclusions)}개")
    for f in result.fields:
        print(f"  - {f.field_name}: {f.condition.raw_text} (path={f.processing_path})")

    print("\n=== 케이스 2: 텍스트 부족 (LLM 호출 시도) ===")
    ann2 = {
        "source_id": "TEST002",
        "title": "테스트 공고 2",
        "target_text": "중소기업",
        "exclusion_text": "",
        "attachments": [],
    }
    result = asyncio.run(extract_eligibility(ann2))
    print(f"필드: {len(result.fields)}개, 제외: {len(result.exclusions)}개")
    if result.fields:
        for f in result.fields:
            print(f"  - {f.field_name}: {f.condition.raw_text} (path={f.processing_path})")
    else:
        print("  (LLM 호출 실패 또는 추출 없음 — OPENAI_API_KEY 미설정 시 정상)")
