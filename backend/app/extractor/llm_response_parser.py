"""LLM 응답 파서.

LLM이 반환한 JSON을 내부 Pydantic 모델로 변환 + 조건 문자열 폴백 파싱.
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.schemas.eligibility import EligibilityField, Evidence, ParsedCondition


class ExtractionResult(BaseModel):
    """text_llm / vision_llm 공통 출력 형식."""

    fields: list[EligibilityField]
    exclusions: list[str]
    processing_path: Literal["text_llm", "vision_llm"]
    error: str | None = None


VALID_FIELD_NAMES = {"업력", "매출", "지역", "나이", "종업원 수", "업종", "인증"}


def build_extraction_result(
    llm_json: dict,
    processing_path: Literal["text_llm", "vision_llm"] = "text_llm",
) -> ExtractionResult:
    """LLM JSON 응답을 ExtractionResult로 변환."""
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
            fields.append(EligibilityField(
                field_name=field_name,
                condition=condition,
                evidence=Evidence(text=f.get("evidence") or "", location=None),
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


def parse_condition_string(text: str) -> ParsedCondition:
    """'3년 미만' 같은 조건 문자열을 ParsedCondition으로 폴백 파싱.

    LLM이 condition만 문자열로 반환하고 value/operator를 비웠을 때 사용.
    """
    if not text:
        return ParsedCondition(value=None, operator=None, raw_text="")

    operators = r"(미만|이하|이상|초과)"

    # N년 + operator
    match = re.search(rf"(\d+)\s*년\s*{operators}", text)
    if match:
        return ParsedCondition(
            value=int(match.group(1)),
            operator=match.group(2),
            raw_text=text,
        )

    # 만 N세 + operator
    match = re.search(rf"만\s*(\d+)\s*세\s*{operators}", text)
    if match:
        return ParsedCondition(
            value=int(match.group(1)),
            operator=match.group(2),
            raw_text=text,
        )

    # N억 + operator (매출)
    match = re.search(rf"(\d+(?:\.\d+)?)\s*억\s*{operators}", text)
    if match:
        amount_eok = float(match.group(1))
        return ParsedCondition(
            value=int(amount_eok * 100_000_000),
            operator=match.group(2),
            raw_text=text,
        )

    # N인 + operator (종업원 수)
    match = re.search(rf"(\d+)\s*인\s*{operators}", text)
    if match:
        return ParsedCondition(
            value=int(match.group(1)),
            operator=match.group(2),
            raw_text=text,
        )

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
