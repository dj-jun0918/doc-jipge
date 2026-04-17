"""규칙 기반 자격요건 파서."""

import re

from app.schemas.eligibility import EligibilityField, ParsedCondition

# 지역명 정규화 매핑
_REGION_MAP: dict[str, str] = {
    "서울특별시": "서울", "서울시": "서울", "서울": "서울",
    "경기도": "경기", "경기": "경기",
    "강원특별자치도": "강원", "강원도": "강원", "강원": "강원",
    "부산광역시": "부산", "부산시": "부산", "부산": "부산",
    "대구광역시": "대구", "대구": "대구",
    "인천광역시": "인천", "인천": "인천",
    "광주광역시": "광주", "광주": "광주",
    "대전광역시": "대전", "대전": "대전",
    "울산광역시": "울산", "울산": "울산",
    "세종특별자치시": "세종", "세종시": "세종", "세종": "세종",
    "충청북도": "충북", "충북": "충북",
    "충청남도": "충남", "충남": "충남",
    "전라북도": "전북", "전북특별자치도": "전북", "전북": "전북",
    "전라남도": "전남", "전남": "전남",
    "경상북도": "경북", "경북": "경북",
    "경상남도": "경남", "경남": "경남",
    "제주특별자치도": "제주", "제주도": "제주", "제주": "제주",
    "전국": "전국",
}

# 연산자 패턴
_OPERATORS = r"(미만|이하|이상|초과)"


def parse_biz_enyy(text: str) -> ParsedCondition | None:
    """업력 필드 파싱.

    "3년 미만", "업력 5년 이상", "창업 후 7년 이하" 등에서 수치 + 연산자 추출.
    """
    if not text:
        return None

    match = re.search(rf"(\d+)\s*년\s*{_OPERATORS}", text)
    if match:
        return ParsedCondition(
            value=int(match.group(1)),
            operator=match.group(2),
            raw_text=match.group(0).strip(),
        )

    range_match = re.search(r"(\d+)\s*년\s*[~∼～]\s*(\d+)\s*년", text)
    if range_match:
        return ParsedCondition(
            value={"min": int(range_match.group(1)), "max": int(range_match.group(2))},
            operator="범위",
            raw_text=range_match.group(0).strip(),
        )

    return None


def parse_supt_regin(text: str) -> ParsedCondition | None:
    """지역 필드 파싱.

    "서울특별시 소재", "강원도 내", "전국" 등에서 지역명 추출 + 정규화.
    """
    if not text:
        return None

    if "전국" in text:
        return ParsedCondition(value="전국", operator="무관", raw_text="전국")

    for full_name, short_name in _REGION_MAP.items():
        if full_name in text:
            suffix_match = re.search(
                rf"{re.escape(full_name)}\s*(소재|내|지역)?", text
            )
            raw_text = suffix_match.group(0).strip() if suffix_match else full_name
            return ParsedCondition(
                value=short_name, operator="소재", raw_text=raw_text
            )

    return None


def parse_biz_trgt_age(text: str) -> ParsedCondition | None:
    """나이 필드 파싱.

    "만 39세 이하", "만 60세 이상" 등에서 나이 + 연산자 추출.
    """
    if not text:
        return None

    match = re.search(rf"만\s*(\d+)\s*세\s*{_OPERATORS}", text)
    if match:
        return ParsedCondition(
            value=int(match.group(1)),
            operator=match.group(2),
            raw_text=match.group(0).strip(),
        )

    return None


def is_api_text_sufficient(announcement: dict) -> bool:
    """API 텍스트만으로 자격요건 추출이 충분한지 판단.

    True → 규칙 기반 파서만으로 처리
    False → 첨부파일 LLM 추출 필요
    """
    target_text = announcement.get("target_text") or ""

    if len(target_text) < 10:
        return False

    results = [
        parse_biz_enyy(target_text),
        parse_supt_regin(target_text),
        parse_biz_trgt_age(target_text),
    ]
    parsed_count = sum(1 for r in results if r is not None)

    return parsed_count >= 2


def is_exclusion_sufficient(announcement: dict) -> bool:
    """제외 대상 텍스트가 API 응답에 충분히 있는지 판단."""
    exclusion_text = announcement.get("exclusion_text") or ""
    return len(exclusion_text) >= 10


def parse_structured_fields(announcement: dict) -> list[EligibilityField]:
    """오케스트레이터: API 텍스트에서 모든 필드를 파싱해서 리스트로 반환."""
    target_text = announcement.get("target_text") or ""
    results: list[EligibilityField] = []

    biz_enyy = parse_biz_enyy(target_text)
    if biz_enyy:
        results.append(EligibilityField(
            field_name="업력",
            condition=biz_enyy,
            evidence=biz_enyy.raw_text,
            evidence_source="API target_text",
            processing_path="rule_based",
        ))

    regin = parse_supt_regin(target_text)
    if regin:
        results.append(EligibilityField(
            field_name="지역",
            condition=regin,
            evidence=regin.raw_text,
            evidence_source="API target_text",
            processing_path="rule_based",
        ))

    age = parse_biz_trgt_age(target_text)
    if age:
        results.append(EligibilityField(
            field_name="나이",
            condition=age,
            evidence=age.raw_text,
            evidence_source="API target_text",
            processing_path="rule_based",
        ))

    return results


if __name__ == "__main__":
    print("=== 업력 파싱 ===")
    for t in ["창업 후 3년 미만 기업", "업력 5년 이상", "업력 3년~7년", "중소기업"]:
        print(f"  '{t}' → {parse_biz_enyy(t)}")

    print("\n=== 지역 파싱 ===")
    for t in ["서울특별시 소재 기업", "강원도 내 기업", "전국", "중소기업"]:
        print(f"  '{t}' → {parse_supt_regin(t)}")

    print("\n=== 나이 파싱 ===")
    for t in ["만 39세 이하 청년 대표자", "만 60세 이상", "중소기업"]:
        print(f"  '{t}' → {parse_biz_trgt_age(t)}")

    print("\n=== 분기 판단 ===")
    ann1 = {"target_text": "업력 3년 미만, 서울특별시 소재, 만 39세 이하 청년", "exclusion_text": "휴폐업 기업"}
    ann2 = {"target_text": "중소기업", "exclusion_text": None}
    print(f"  충분한 텍스트: {is_api_text_sufficient(ann1)}")
    print(f"  부족한 텍스트: {is_api_text_sufficient(ann2)}")

    print("\n=== 오케스트레이터 ===")
    fields = parse_structured_fields(ann1)
    print(f"  추출된 필드 수: {len(fields)}개")
    for f in fields:
        print(f"    {f.field_name}: {f.condition}")
