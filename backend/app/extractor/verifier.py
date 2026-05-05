"""LLM 응답 검증 레이어.

LLM 출력의 필드 완전성/일관성 검사 + 중복 필드 병합.
"""

import logging

from app.extractor.llm_response_parser import (
    VALID_FIELD_NAMES,
    ExtractionResult,
    parse_condition_string,
)
from app.schemas.eligibility import EligibilityField

logger = logging.getLogger(__name__)


def verify(result: ExtractionResult) -> ExtractionResult:
    """ExtractionResult 검증 + 정규화.

    - operator/value 누락 시 raw_text로 폴백 파싱 시도
    - VALID_FIELD_NAMES에 없는 필드 제거
    - 중복 필드 병합
    """
    verified_fields: list[EligibilityField] = []

    for field in result.fields:
        if field.field_name not in VALID_FIELD_NAMES:
            continue

        cond = field.condition
        if (cond.operator is None or cond.value is None) and cond.raw_text:
            parsed = parse_condition_string(cond.raw_text)
            if parsed.operator is not None and parsed.value is not None:
                field.condition = parsed

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
