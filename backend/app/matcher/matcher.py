"""
backend/app/matcher/matcher.py
매칭 엔진 — 필드별 비교 함수 (PR#2 착수)
PR#3에서 전체 엔진 통합 예정.
"""

from __future__ import annotations
from typing import Literal

from app.schemas.eligibility import ParsedCondition


# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────

REGION_GROUPS: dict[str, list[str]] = {
    "서울": ["서울특별시", "서울"],
    "부산": ["부산광역시", "부산"],
    "대구": ["대구광역시", "대구"],
    "인천": ["인천광역시", "인천"],
    "광주": ["광주광역시", "광주"],
    "대전": ["대전광역시", "대전"],
    "울산": ["울산광역시", "울산"],
    "세종": ["세종특별자치시", "세종"],
    "경기": ["경기도", "경기"],
    "강원": ["강원특별자치도", "강원도", "강원"],
    "충북": ["충청북도", "충북"],
    "충남": ["충청남도", "충남"],
    "전북": ["전북특별자치도", "전라북도", "전북"],
    "전남": ["전라남도", "전남"],
    "경북": ["경상북도", "경북"],
    "경남": ["경상남도", "경남"],
    "제주": ["제주특별자치도", "제주도", "제주"],
}

MatchStatus = Literal["충족", "미충족", "확인필요"]


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _normalize_region(region: str) -> str:
    """
    지역 문자열을 표준 단축 키로 정규화.
    예: "서울특별시" → "서울", "강원도" → "강원"
    매핑되지 않으면 원문 그대로 반환.
    """
    region = region.strip()
    for key, aliases in REGION_GROUPS.items():
        if region in aliases or region == key:
            return key
    return region


# ──────────────────────────────────────────────
# match_numeric
# ──────────────────────────────────────────────

def match_numeric(
    company_value: int | float | None,
    condition: ParsedCondition,
) -> MatchStatus:
    """
    수치 비교 — 업력 / 매출 / 나이 / 종업원 수에 공통 적용.

    Args:
        company_value: 회사의 실제 수치. None이면 "확인필요" 반환.
        condition: ParsedCondition — value, operator, raw_text 포함.

    Returns:
        "충족" | "미충족" | "확인필요"

    Notes:
        - operator가 None이면 → "확인필요"
        - company_value가 None이면 → "확인필요"
        - operator == "범위"일 때 condition.value는 {"min": N, "max": N} dict (rule_parser 반환 형식).
          list/tuple [min, max]도 호환 처리. 형식이 맞지 않으면 → "확인필요"
    """
    if company_value is None:
        return "확인필요"

    op = condition.operator
    val = condition.value

    if op is None or val is None:
        return "확인필요"

    try:
        if op == "미만":
            return "충족" if company_value < val else "미충족"
        elif op == "이하":
            return "충족" if company_value <= val else "미충족"
        elif op == "이상":
            return "충족" if company_value >= val else "미충족"
        elif op == "초과":
            return "충족" if company_value > val else "미충족"
        elif op == "범위":
            # rule_parser는 {"min": N, "max": N} dict로 반환
            if isinstance(val, dict) and "min" in val and "max" in val:
                lo, hi = val["min"], val["max"]
            elif isinstance(val, (list, tuple)) and len(val) == 2:
                lo, hi = val
            else:
                return "확인필요"
            return "충족" if lo <= company_value <= hi else "미충족"
        else:
            # 알 수 없는 operator
            return "확인필요"
    except TypeError:
        return "확인필요"


# ──────────────────────────────────────────────
# match_region
# ──────────────────────────────────────────────

def match_region(
    company_region: str | None,
    condition: ParsedCondition,
) -> MatchStatus:
    """
    지역 비교 — 포함 / 일치 / 무관.

    Args:
        company_region: 회사 소재 지역 문자열. None이면 "확인필요".
        condition: ParsedCondition — raw_text / value 기준 비교.

    Returns:
        "충족" | "미충족" | "확인필요"

    Notes:
        - condition.raw_text에 "전국" 포함 → 항상 "충족"
        - condition.value가 None → "확인필요"
        - REGION_GROUPS 기반 정규화 후 비교
    """
    # "전국" 조건 → 항상 충족
    raw = condition.raw_text or ""
    if "전국" in raw:
        return "충족"

    if company_region is None:
        return "확인필요"

    if condition.value is None:
        return "확인필요"

    # 정규화
    company_norm = _normalize_region(company_region)

    # condition.value가 단일 str 또는 str 리스트 모두 처리
    required_regions: list[str] = (
        condition.value if isinstance(condition.value, list)
        else [condition.value]
    )
    required_norms = [_normalize_region(r) for r in required_regions]

    return "충족" if company_norm in required_norms else "미충족"