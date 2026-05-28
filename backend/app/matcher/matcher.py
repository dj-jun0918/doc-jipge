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
# 매칭 정교화 1차 (PR#4, 2026-05-20)
# continuous score + distance metric + soft constraint 분리
# ──────────────────────────────────────────────

def compute_numeric_distance(
    company_value: int | float | None,
    condition: ParsedCondition,
    status: MatchStatus,
) -> float | None:
    """
    미충족 수치 필드에 대해 정규화 거리 계산.

    - 단일 operator (미만/이하/이상/초과): |company_value - threshold| / |threshold|
    - 범위 (dict {min, max}): 범위 밖이면 가까운 경계와의 정규화 거리
    - 충족/확인필요/해당없음: None

    Returns:
        float ≥ 0 (조건에 가까울수록 작음) 또는 None
    """
    if status != "미충족" or company_value is None:
        return None

    val = condition.value

    # 범위 처리
    if isinstance(val, dict) and "min" in val and "max" in val:
        lo, hi = val["min"], val["max"]
        if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
            return None
        if company_value < lo:
            return abs(company_value - lo) / max(abs(lo), 1)
        elif company_value > hi:
            return abs(company_value - hi) / max(abs(hi), 1)
        return None  # 범위 안 = 충족이어야 하는데 미충족이면 condition 모순

    # 단일 수치
    if not isinstance(val, (int, float)) or val == 0:
        return None
    return abs(company_value - val) / abs(val)


def compute_field_score(
    status: MatchStatus,
    distance: float | None = None,
) -> float | None:
    """
    필드별 score (0~1).

    - 충족: 1.0
    - 확인필요: 0.3 (보수적, 불확실성 반영)
    - 미충족: 거리 기반 부분 점수 (0.0 ~ 0.5)
      - distance가 작을수록 (조건에 가까울수록) 높은 점수
      - distance >= 1.0이거나 None이면 0.0
    - 해당없음: None (점수 계산에서 제외)
    """
    if status == "충족":
        return 1.0
    elif status == "확인필요":
        return 0.3
    elif status == "미충족":
        if distance is None or distance >= 1.0:
            return 0.0
        # 거리가 작을수록 점수 ↑ (최대 0.5 — 충족과 명확히 구분)
        return max(0.0, 1.0 - distance) * 0.5
    else:  # 해당없음
        return None


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
        list[MatchResultResponse] — 각 필드별 status + score + distance + constraint_type 포함

    Notes:
        - score/distance/constraint_type은 PR#4 매칭 정교화 1차 (2026-05-20)
        - constraint_type 기본 "hard". PR#5 모호 케이스 합의 후 soft 분리
    """
    results: list[MatchResultResponse] = []

    for field in fields:
        fn = field.field_name
        cond = field.condition
        company_value_str: str | None = None
        company_numeric: int | float | None = None  # distance 계산용 (수치 필드만)
        status: MatchStatus = "확인필요"

        if fn == "업력":
            biz_age = calculate_biz_age(company.founded_date)
            company_numeric = biz_age
            company_value_str = f"{biz_age:.2f}년" if biz_age is not None else None
            status = match_numeric(biz_age, cond)

        elif fn == "매출":
            company_numeric = company.revenue
            company_value_str = str(company.revenue) if company.revenue is not None else None
            status = match_numeric(company.revenue, cond)

        elif fn == "종업원 수":
            company_numeric = company.employee_count
            company_value_str = str(company.employee_count) if company.employee_count is not None else None
            status = match_numeric(company.employee_count, cond)

        elif fn == "나이":
            age = calculate_age(company.ceo_birth_date)
            company_numeric = age
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

        # PR#4 매칭 정교화 1차: distance + score 계산
        distance = compute_numeric_distance(company_numeric, cond, status)
        score = compute_field_score(status, distance)
        # constraint_type — 기본 "hard". PR#5 모호 케이스 합의 후 정밀화
        constraint_type: str = "hard"

        results.append(MatchResultResponse(
            id=uuid.uuid4(),
            announcement_id=announcement_id,
            company_id=company.id,
            field_name=fn,
            status=status,
            score=score,
            distance=distance,
            constraint_type=constraint_type,
            company_value=company_value_str,
            requirement_value=cond.raw_text,
            # EligibilityField.evidence (Evidence 객체)의 text만 추출
            evidence=field.evidence.text if field.evidence else None,
            processing_path=field.processing_path,
        ))

    return results