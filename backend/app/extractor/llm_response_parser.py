"""LLM 응답 파서.

LLM이 반환한 JSON을 내부 Pydantic 모델로 변환 + 조건 문자열 폴백 파싱.
"""

import logging
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

from app.schemas.eligibility import EligibilityField, Evidence, ParsedCondition

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


def build_extraction_result(
    llm_json: dict,
    processing_path: Literal["text_llm", "vision_llm"] = "text_llm",
    source_text: str | None = None,
) -> ExtractionResult:
    """LLM JSON 응답을 ExtractionResult로 변환.

    source_text가 주어지면 각 evidence가 원문에 그대로 있는지 검증 (text_llm 경로).
    근거를 원문에서 검증하지 못한 필드(환각)는 제외한다 — 검증 가능한 추출만 신뢰.
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
            # 근거를 원문에서 검증 못 하면 단언하지 않고 제외 (환각 방어 — 검증 가능한 추출만 신뢰).
            if source_text is not None and not is_evidence_verbatim(evidence_text, source_text):
                logger.warning(
                    f"evidence가 원문에 없음 (환각으로 판단해 필드 제외): field={field_name}, evidence={evidence_text[:80]!r}"
                )
                continue
            fields.append(EligibilityField(
                field_name=field_name,
                condition=condition,
                evidence=Evidence(text=evidence_text, location=None),
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

    operators = r"(미만|이하|이내|이상|초과)"

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
