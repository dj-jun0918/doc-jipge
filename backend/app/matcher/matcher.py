"""
backend/app/matcher/matcher.py
매칭 엔진 — 필드별 비교 함수 (PR#2 착수, PR#3 완성)
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from dateutil.relativedelta import relativedelta

from app.models.company import Company
from app.schemas.eligibility import EligibilityField, ParsedCondition
from app.schemas.match_result import MatchResultResponse


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
    region = region.strip()
    for key, aliases in REGION_GROUPS.items():
        if region in aliases or region == key:
            return key
    return region


def calculate_biz_age(founded_date: date | None) -> float | None:
    """
    창업일 기준 업력(년) 계산. 소수점 포함 반환.
    예: 2년 11개월 → 2.916...
    """
    if founded_date is None:
        return None
    today = date.today()
    delta = relativedelta(today, founded_date)
    return delta.years + delta.months / 12 + delta.days / 365.25


def calculate_age(birth_date: date | None) -> int | None:
    """
    만 나이 계산 (KST 기준 date.today() 사용).
    """
    if birth_date is None:
        return None
    today = date.today()
    age = today.year - birth_date.year
    # 생일 안 지났으면 1 빼기
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


# ──────────────────────────────────────────────
# match_numeric
# ──────────────────────────────────────────────

def match_numeric(
    company_value: int | float | None,
    condition: ParsedCondition,
) -> MatchStatus:
    """
    수치 비교 — 업력 / 매출 / 나이 / 종업원 수에 공통 적용.

    operator: "미만" | "이하" | "이상" | "초과" | "범위"
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
            if isinstance(val, dict) and "min" in val and "max" in val:
                lo, hi = val["min"], val["max"]
            elif isinstance(val, (list, tuple)) and len(val) == 2:
                lo, hi = val
            else:
                return "확인필요"
            return "충족" if lo <= company_value <= hi else "미충족"
        else:
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
    condition.raw_text에 "전국" 포함 → 항상 "충족"
    """
    raw = condition.raw_text or ""
    if "전국" in raw:
        return "충족"

    if company_region is None:
        return "확인필요"

    if condition.value is None:
        return "확인필요"

    company_norm = _normalize_region(company_region)
    required_regions: list[str] = (
        condition.value if isinstance(condition.value, list)
        else [condition.value]
    )
    required_norms = [_normalize_region(r) for r in required_regions]

    return "충족" if company_norm in required_norms else "미충족"


# ──────────────────────────────────────────────
# match_industry
# ──────────────────────────────────────────────

def match_industry(
    company_industry: str | None,
    condition: ParsedCondition,
) -> MatchStatus:
    """
    업종 비교.
    condition.value:
        - str  → 단일 허용 업종
        - list → 허용 업종 목록 (포함 시 충족)
    condition.operator:
        - "포함"  → company_industry가 목록 안에 있으면 충족
        - "제외"  → company_industry가 목록 안에 있으면 미충족
        - None   → 확인필요
    """
    if company_industry is None:
        return "확인필요"

    op = condition.operator
    val = condition.value

    if op is None or val is None:
        return "확인필요"

    allowed: list[str] = val if isinstance(val, list) else [val]
    # 부분 문자열 매칭 (예: "제조" in "식품 제조업")
    matched = any(a in company_industry or company_industry in a for a in allowed)

    if op == "포함":
        return "충족" if matched else "미충족"
    elif op == "제외":
        return "미충족" if matched else "충족"
    else:
        return "확인필요"


# ──────────────────────────────────────────────
# match_certification
# ──────────────────────────────────────────────

def match_certification(
    company_certs: dict | None,
    condition: ParsedCondition,
) -> MatchStatus:
    """
    인증 보유 여부 비교.
    condition.value: 요구 인증 키 문자열 또는 키 목록.
    예: "vc_certified" → company_certs["vc_certified"] == True 이면 충족.

    operator:
        - "보유"  → 해당 인증 True이면 충족
        - "미보유" → 해당 인증 False/없으면 충족
        - None   → 확인필요
    """
    if company_certs is None:
        # certifications 필드 자체가 없으면
        if condition.operator == "미보유":
            return "충족"
        return "확인필요"

    op = condition.operator
    val = condition.value

    if op is None or val is None:
        return "확인필요"

    keys: list[str] = val if isinstance(val, list) else [val]

    if op == "보유":
        # 모든 요구 인증 키가 True이어야 충족
        return "충족" if all(company_certs.get(k) is True for k in keys) else "미충족"
    elif op == "미보유":
        # 어떤 인증 키도 True가 아니어야 충족
        return "충족" if not any(company_certs.get(k) is True for k in keys) else "미충족"
    else:
        return "확인필요"


# ──────────────────────────────────────────────
# 오케스트레이터
# ──────────────────────────────────────────────

def match_announcement(
    company: Company,
    fields: list[EligibilityField],
    announcement_id: uuid.UUID,
) -> list[MatchResultResponse]:
    """
    공고 자격요건 전체 vs 회사 프로필 매칭 결과 산출.

    Args:
        company: Company ORM 객체
        fields: 공고의 EligibilityField 리스트
        announcement_id: 공고 UUID

    Returns:
        list[MatchResultResponse]
    """
    results: list[MatchResultResponse] = []

    for field in fields:
        fn = field.field_name
        cond = field.condition
        company_value_str: str | None = None
        status: MatchStatus = "확인필요"

        if fn == "업력":
            biz_age = calculate_biz_age(company.founded_date)
            company_value_str = f"{biz_age:.2f}년" if biz_age is not None else None
            status = match_numeric(biz_age, cond)

        elif fn == "매출":
            company_value_str = str(company.revenue) if company.revenue is not None else None
            status = match_numeric(company.revenue, cond)

        elif fn == "종업원수":
            company_value_str = str(company.employee_count) if company.employee_count is not None else None
            status = match_numeric(company.employee_count, cond)

        elif fn == "대표자나이":
            age = calculate_age(company.ceo_birth_date)
            company_value_str = f"{age}세" if age is not None else None
            status = match_numeric(age, cond)

        elif fn == "지역":
            company_value_str = company.region
            status = match_region(company.region, cond)

        elif fn == "업종":
            company_value_str = company.industry
            status = match_industry(company.industry, cond)

        elif fn == "인증":
            company_value_str = str(company.certifications) if company.certifications else None
            status = match_certification(company.certifications, cond)

        else:
            # 알 수 없는 필드 → 확인필요
            status = "확인필요"

        results.append(MatchResultResponse(
            id=uuid.uuid4(),
            announcement_id=announcement_id,
            company_id=company.id,
            field_name=fn,
            status=status,
            company_value=company_value_str,
            requirement_value=cond.raw_text,
            evidence=field.evidence,
            processing_path=field.processing_path,
        ))

    return results