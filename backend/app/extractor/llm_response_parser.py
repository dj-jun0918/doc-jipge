"""LLM 응답 파서.

LLM이 반환한 JSON을 내부 Pydantic 모델로 변환 + 조건 문자열 폴백 파싱.
"""

import logging
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

from app.schemas.eligibility import EligibilityField, Evidence, EvidenceLocation, ParsedCondition

logger = logging.getLogger(__name__)


class ExtractionResult(BaseModel):
    """text_llm / vision_llm 공통 출력 형식."""

    fields: list[EligibilityField]
    exclusions: list[str]
    processing_path: Literal["text_llm", "vision_llm"]
    error: str | None = None


VALID_FIELD_NAMES = {"업력", "매출", "지역", "나이", "종업원 수", "업종", "인증"}


# PDF 텍스트 추출/LLM 응답 간 문장부호 변형 통일 (curly quote, 가운뎃점, 대시)
_PUNCT_VARIANTS = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "·": ",", "ㆍ": ",", "∙": ",", "•": ",",
    "–": "-", "—": "-", "―": "-",
})


def _normalize_for_match(s: str) -> str:
    """NFKC 정규화 + 문장부호 변형 통일 + 표 파이프(|) 제거 + 모든 공백 제거.

    표 셀 파이프 주변 공백, markdown 표 형태 evidence(셀 구분자 |), PDF 추출 시
    문자 변형(전각/curly quote/가운뎃점) 차이까지 흡수.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_PUNCT_VARIANTS)
    s = s.replace("|", "")
    return re.sub(r"\s+", "", s)


def is_evidence_verbatim(evidence: str, source_text: str) -> bool:
    """evidence가 source_text에 (공백 정규화 후) 그대로 존재하는지 검사.

    표 markdown 라인은 셀 간 공백이 LLM 응답에서 달라질 수 있어 정규화 후 비교.
    빈 evidence는 검증 대상 아님 (True 반환).
    """
    if not evidence:
        return True
    return _normalize_for_match(evidence) in _normalize_for_match(source_text)


def _locate_page(evidence_text: str, page_text_map: list[tuple[int, str]]) -> int | None:
    """evidence_text가 처음 등장하는 PDF 페이지 번호(1-based)를 반환. 못 찾으면 None.

    추출 시점에 근거의 페이지를 확정해 두면 뷰어가 매번 전체 PDF를 재검색하지 않고 바로 점프한다.
    is_evidence_verbatim과 동일한 정규화를 쓰므로, 원문 검증을 통과한 근거는 대개 위치도 잡힌다.
    """
    if not evidence_text.strip():
        return None
    target = _normalize_for_match(evidence_text)
    if not target:
        return None
    for page, text in page_text_map:
        if target in _normalize_for_match(text):
            return page
    return None


def build_extraction_result(
    llm_json: dict,
    processing_path: Literal["text_llm", "vision_llm"] = "text_llm",
    source_text: str | None = None,
    page_text_map: list[tuple[int, str]] | None = None,
) -> ExtractionResult:
    """LLM JSON 응답을 ExtractionResult로 변환.

    source_text가 주어지면 각 evidence가 원문에 그대로 있는지 검증 (text_llm 경로).
    근거를 원문에서 검증하지 못한 필드(환각)는 제외한다 — 검증 가능한 추출만 신뢰.
    page_text_map((page, text) 리스트)이 주어지면 evidence가 나온 PDF 페이지를 location에 저장한다.
    """
    fields: list[EligibilityField] = []

    for f in llm_json.get("fields", []):
        if not isinstance(f, dict):
            continue

        field_name = f.get("field_name")
        if field_name not in VALID_FIELD_NAMES:
            continue

        try:
            condition = ParsedCondition(
                value=f.get("value"),
                operator=f.get("operator"),
                raw_text=f.get("condition") or "",
            )
            evidence_text = f.get("evidence") or ""
            # 근거 없는 단언은 검증이 불가능하므로 신뢰하지 않는다 (빈 evidence가 검증을 우회하던 구멍 봉쇄).
            if source_text is not None and not evidence_text.strip():
                logger.warning(
                    f"evidence가 비어 있음 (검증 불가로 필드 제외): field={field_name}"
                )
                continue
            # 근거를 원문에서 검증 못 하면 단언하지 않고 제외 (환각 방어 — 검증 가능한 추출만 신뢰).
            if source_text is not None and not is_evidence_verbatim(evidence_text, source_text):
                logger.warning(
                    f"evidence가 원문에 없음 (환각으로 판단해 필드 제외): field={field_name}, evidence={evidence_text[:80]!r}"
                )
                continue
            location = None
            if page_text_map:
                located = _locate_page(evidence_text, page_text_map)
                if located is not None:
                    location = EvidenceLocation(location_type="pdf_page", page=located)
            fields.append(EligibilityField(
                field_name=field_name,
                condition=condition,
                evidence=Evidence(text=evidence_text, location=location),
                evidence_source="LLM 추출",
                processing_path=processing_path,
            ))
        except (KeyError, ValueError, TypeError):
            continue

    exclusions = [
        str(e) for e in llm_json.get("exclusions", [])
        if isinstance(e, str) and e.strip()
    ]

    return ExtractionResult(
        fields=fields,
        exclusions=exclusions,
        processing_path=processing_path,
    )


def _num(s: str) -> int | float:
    """'7'→7, '1.5'→1.5 (정수면 int)."""
    v = float(s)
    return int(v) if v.is_integer() else v


def _amount_to_won(text: str) -> int | None:
    """'10억원', '5천만원', '7억 5천만', '3000만원' → 원 단위 int. 억/천만/만 합산."""
    # 천단위 콤마 제거 ('1,200만원'의 '1,'이 잘려 '200만'으로 오인식되는 것 방지)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    total, found = 0, False
    m = re.search(r"(\d+(?:\.\d+)?)\s*억", text)
    if m:
        total += int(float(m.group(1)) * 100_000_000)
        found = True
    m = re.search(r"(\d+(?:\.\d+)?)\s*천\s*만", text)
    if m:
        total += int(float(m.group(1)) * 10_000_000)
        found = True
    else:
        m = re.search(r"(?<![천억\d.])(\d+(?:\.\d+)?)\s*만\s*원?", text)
        if m:
            total += int(float(m.group(1)) * 10_000)
            found = True
    return total if found else None


def parse_condition_string(text: str) -> ParsedCondition:
    """'3년 미만' 같은 조건 문자열을 ParsedCondition으로 폴백 파싱.

    LLM이 condition만 문자열로 반환하고 value/operator를 비웠을 때 사용.
    매출(억/만원), 종업원(인/명), 나이·업력 범위(이상~미만)까지 처리.
    """
    if not text:
        return ParsedCondition(value=None, operator=None, raw_text="")

    operators = r"(미만|이하|이내|이상|초과)"
    lower_op = r"(?:이상|초과)"
    upper_op = r"(?:미만|이하|이내)"

    # 범위: 하한(이상/초과)+상한(미만/이하/이내) 둘 다 (세/년/명/인 단위) → {min,max}
    lo = re.search(rf"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:세|년|명|인)\s*{lower_op}", text)
    up = re.search(rf"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:세|년|명|인)\s*{upper_op}", text)
    if lo and up and lo.start() < up.start():
        return ParsedCondition(
            value={"min": _num(lo.group(1)), "max": _num(up.group(1))},
            operator="범위", raw_text=text,
        )

    # 매출 (억/만원) — '10억원 이하', '5천만원 이하' 등
    if "억" in text or re.search(r"만\s*원", text):
        won = _amount_to_won(text)
        op_m = re.search(operators, text)
        if won is not None and op_m:
            return ParsedCondition(value=won, operator=op_m.group(1), raw_text=text)

    # N년 + operator (업력, 소수 지원)
    match = re.search(rf"(?<![\d.])(\d+(?:\.\d+)?)\s*년\s*{operators}", text)
    if match:
        return ParsedCondition(value=_num(match.group(1)), operator=match.group(2), raw_text=text)

    # 만 N세 + operator (나이)
    match = re.search(rf"만\s*(\d+)\s*세\s*{operators}", text)
    if match:
        return ParsedCondition(value=int(match.group(1)), operator=match.group(2), raw_text=text)

    # N인/명 + operator (종업원 수)
    match = re.search(rf"(?<![\d.])(\d+)\s*(?:인|명)\s*{operators}", text)
    if match:
        return ParsedCondition(value=int(match.group(1)), operator=match.group(2), raw_text=text)

    return ParsedCondition(value=None, operator=None, raw_text=text)


if __name__ == "__main__":
    print("=== build_extraction_result ===")
    sample_json = {
        "fields": [
            {
                "field_name": "업력",
                "condition": "3년 미만",
                "operator": "미만",
                "value": 3,
                "evidence": "창업 후 3년 미만 기업",
            },
            {
                "field_name": "지역",
                "condition": "강원도 소재",
                "operator": "소재",
                "value": "강원",
                "evidence": "강원도 소재 기업",
            },
            {
                "field_name": "알수없는필드",
                "condition": "...",
            },
        ],
        "exclusions": ["휴폐업 기업", "국세 체납 기업"],
    }
    result = build_extraction_result(sample_json)
    print(f"fields: {len(result.fields)}개 (알수없는필드는 제외)")
    for f in result.fields:
        print(f"  - {f.field_name}: {f.condition.raw_text}")
    print(f"exclusions: {result.exclusions}")

    print("\n=== parse_condition_string ===")
    for t in ["3년 미만", "만 39세 이하", "10억 이하", "5인 이상", "청년"]:
        r = parse_condition_string(t)
        print(f"  '{t}' → value={r.value} operator={r.operator}")
