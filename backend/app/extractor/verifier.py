"""LLM 응답 검증 레이어.

LLM 출력의 필드 완전성/일관성 검사 + 중복 필드 병합 + 인증 표준 키 정규화.
"""

import logging
import re

from app.extractor.llm_response_parser import (
    VALID_FIELD_NAMES,
    ExtractionResult,
    parse_condition_string,
)
# 인증 매핑표의 단일 소스 — matcher와 동일 표 사용 (가이드라인 매핑표와 동기화)
from app.matcher.cert_mapping import CERT_MAPPING, extract_cert_keys
from app.schemas.eligibility import EligibilityField

logger = logging.getLogger(__name__)

# 우대·가점·감면·면제는 가산 요소 — 자격요건이 아니므로 추출됐어도 자격 판정에서 제외.
# 원칙적 카테고리만 (특정 공고 고유명사는 과적합이라 미포함).
_NON_REQUIREMENT_MARKERS = ("가점", "우대", "감면", "면제")
_HARD_OPS = ("미만", "이하", "이내", "이상", "초과")


def _is_preferential(field: EligibilityField) -> bool:
    """요건 '자체'가 우대/가점일 때만 True.

    근거 문장(evidence)에 우대/가점이 병기됐다고 하드 요건까지 삭제하면 recall이 떨어진다
    (예: '만 39세 이하 (여성 가점)'의 나이 요건). 따라서 condition.raw_text만 보고,
    비교 연산자(이상/이하/미만 등)가 함께 있으면 하드 요건으로 간주해 보존한다.
    """
    cond = field.condition
    raw = (cond.raw_text if cond else "") or ""
    if not any(m in raw for m in _NON_REQUIREMENT_MARKERS):
        return False
    if (cond and cond.operator in _HARD_OPS) or any(op in raw for op in _HARD_OPS):
        return False
    return True


# 비요건 문맥 마커 — 신청기업 자격이 아니라 다른 주체·혜택을 설명하는 문장에서 오추출된 경우.
# 주관기관=사업 운영주체, 수요기업=수요처(공급 대상), 계상=비용 계상 혜택 부여 규칙.
_NON_REQUIREMENT_CONTEXT = ("주관기관", "수요기업", "계상")
# 원화 금액 단위 (달러 등 외화는 제외 — '만 원'은 매칭, '만달러'는 비매칭)
_AMOUNT_UNIT_RE = re.compile(r"억|만\s*원")


def _is_non_requirement_context(field: EligibilityField) -> bool:
    """근거가 신청 자격이 아니라 다른 주체·혜택을 설명할 때 True.

    예: '(주관기관) 대기업'(운영주체), '방산 분야 수요기업'(수요처),
        '7년 이내…인건비 현금 계상 가능'(혜택 부여 규칙) — 모두 신청 자격요건이 아니다.
    """
    cond = field.condition
    raw = (cond.raw_text if cond else "") or ""
    ev = field.evidence
    ev_text = ev if isinstance(ev, str) else (getattr(ev, "text", "") or "")
    text = f"{raw} {ev_text}"
    return any(m in text for m in _NON_REQUIREMENT_CONTEXT)


def _recompute_amount(field: EligibilityField) -> None:
    """금액 필드(매출)는 raw_text에서 결정적으로 재계산해 LLM 산술 오류를 교정 (in-place).

    LLM이 '20억원'을 2억으로 잘못 계산해 value를 직접 출력하면 value가 None이 아니라
    폴백 파싱도 안 타고 오류값이 그대로 쓰인다. 금액 산술은 파서가 결정적·정확하므로
    원화 단위가 있을 때 raw에서 재계산해 덮어쓴다 (파서 산출 실패 시 LLM 값 유지).
    """
    if field.field_name != "매출":
        return
    cond = field.condition
    raw = cond.raw_text or ""
    if not _AMOUNT_UNIT_RE.search(raw):
        return
    parsed = parse_condition_string(raw)
    if isinstance(parsed.value, (int, float)) and not isinstance(parsed.value, bool):
        cond.value = parsed.value
        if parsed.operator and not cond.operator:
            cond.operator = parsed.operator


def normalize_cert_value(field: EligibilityField) -> None:
    """인증 field의 value를 표준 키로 정규화 (in-place).

    LLM이 value에 원문 표현('벤처기업 보유')을 그대로 내면 회사 certifications의
    표준 키(venture_company 등)와 영원히 불일치한다 → 원문 키워드에서 표준 키 추출.
    이미 표준 키(또는 키 목록)면 그대로 둔다. 매핑에 없는 인증은 원문 유지.
    """
    cond = field.condition
    val = cond.value

    if isinstance(val, str) and val in CERT_MAPPING:
        return
    if isinstance(val, list) and val and all(
        isinstance(v, str) and v in CERT_MAPPING for v in val
    ):
        return

    parts: list[str] = []
    if isinstance(val, str):
        parts.append(val)
    elif isinstance(val, list):
        parts.extend(str(v) for v in val)
    parts.append(cond.raw_text or "")

    keys = extract_cert_keys(" ".join(parts))
    if not keys:
        # value·조건문에서 못 찾았을 때만 evidence를 최후 수단으로 사용
        # (근거 문장에는 우대·병기 인증이 섞여 있어 직접 쓰면 요구 키가 오염될 수 있음)
        evidence = field.evidence
        evidence_text = evidence if isinstance(evidence, str) else getattr(evidence, "text", "") or ""
        keys = extract_cert_keys(evidence_text)
    if keys:
        cond.value = keys[0] if len(keys) == 1 else keys


def verify(result: ExtractionResult) -> ExtractionResult:
    """ExtractionResult 검증 + 정규화.

    - operator/value 누락 시 raw_text로 폴백 파싱 시도
    - VALID_FIELD_NAMES에 없는 필드 제거
    - 인증 field value를 표준 키로 정규화
    - 중복 필드 병합
    """
    verified_fields: list[EligibilityField] = []

    for field in result.fields:
        if field.field_name not in VALID_FIELD_NAMES:
            continue

        # 우대·가점·감면은 가산 요소이지 자격요건이 아니므로 자격 판정에서 제외
        if _is_preferential(field):
            continue

        # 운영주체·수요처·혜택 부여 문맥에서 오추출된 필드 제외 (신청 자격 아님)
        if _is_non_requirement_context(field):
            continue

        # LLM 산술 오류 방어: 금액 필드는 raw_text에서 결정적으로 재계산해 교정
        _recompute_amount(field)

        cond = field.condition
        if (cond.operator is None or cond.value is None) and cond.raw_text:
            parsed = parse_condition_string(cond.raw_text)
            if parsed.operator is not None and parsed.value is not None:
                field.condition = parsed

        if field.field_name == "인증":
            normalize_cert_value(field)

        verified_fields.append(field)

    deduplicated = deduplicate_fields(verified_fields)

    return ExtractionResult(
        fields=deduplicated,
        exclusions=result.exclusions,
        processing_path=result.processing_path,
        error=result.error,
    )


def deduplicate_fields(fields: list[EligibilityField]) -> list[EligibilityField]:
    """같은 field_name 여러 개일 때 한 개만 유지.

    operator가 명확한 쪽 우선. 둘 다 명확하면 더 엄격한 쪽 우선.
    """
    by_name: dict[str, EligibilityField] = {}
    for field in fields:
        existing = by_name.get(field.field_name)
        if existing is None:
            by_name[field.field_name] = field
        else:
            by_name[field.field_name] = _pick_better(existing, field)
    return list(by_name.values())


_OP_PRIORITY = {
    "미만": 0,
    "이하": 1,
    "이내": 1,  # '이하'와 동일 의미
    "이상": 2,
    "초과": 3,
    "범위": 4,
    "소재": 5,
    "무관": 6,
    "포함": 7,
    "제외": 8,
    "보유": 9,
    "미보유": 10,
}


def _pick_better(a: EligibilityField, b: EligibilityField) -> EligibilityField:
    """두 필드 중 더 신뢰할 만한 쪽 선택.

    1. operator/value 모두 명확한 쪽 우선
    2. 둘 다 명확하면 operator 우선순위 낮은 쪽 (= 미만/이하 같은 엄격한 조건)
    """
    a_clear = a.condition.operator is not None and a.condition.value is not None
    b_clear = b.condition.operator is not None and b.condition.value is not None

    if a_clear and not b_clear:
        return a
    if b_clear and not a_clear:
        return b
    if not a_clear and not b_clear:
        return a

    a_pri = _OP_PRIORITY.get(a.condition.operator or "", 99)
    b_pri = _OP_PRIORITY.get(b.condition.operator or "", 99)
    return a if a_pri <= b_pri else b


if __name__ == "__main__":
    from app.schemas.eligibility import ParsedCondition

    print("=== verify (operator 누락 → 폴백 파싱) ===")
    sample = ExtractionResult(
        fields=[
            EligibilityField(
                field_name="업력",
                condition=ParsedCondition(value=None, operator=None, raw_text="3년 미만"),
                evidence="창업 후 3년 미만",
                evidence_source="LLM 추출",
                processing_path="text_llm",
            ),
            EligibilityField(
                field_name="알수없는필드",
                condition=ParsedCondition(value=None, operator=None, raw_text=""),
                evidence="",
                evidence_source="LLM 추출",
                processing_path="text_llm",
            ),
        ],
        exclusions=["휴폐업 기업"],
        processing_path="text_llm",
    )

    verified = verify(sample)
    print(f"필드: {len(verified.fields)}개 (알수없는필드 제외)")
    for f in verified.fields:
        print(f"  - {f.field_name}: value={f.condition.value} operator={f.condition.operator}")

    print("\n=== deduplicate_fields ===")
    dup = [
        EligibilityField(
            field_name="업력",
            condition=ParsedCondition(value=3, operator="미만", raw_text="3년 미만"),
            evidence="3년 미만", evidence_source="LLM", processing_path="text_llm",
        ),
        EligibilityField(
            field_name="업력",
            condition=ParsedCondition(value=5, operator="이하", raw_text="5년 이하"),
            evidence="5년 이하", evidence_source="LLM", processing_path="text_llm",
        ),
        EligibilityField(
            field_name="지역",
            condition=ParsedCondition(value="서울", operator="소재", raw_text="서울 소재"),
            evidence="서울", evidence_source="LLM", processing_path="text_llm",
        ),
    ]
    result = deduplicate_fields(dup)
    print(f"중복 제거 후: {len(result)}개 (업력 2개 → 1개)")
    for f in result:
        print(f"  - {f.field_name}: {f.condition.raw_text} (operator={f.condition.operator})")
