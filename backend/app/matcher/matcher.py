"""
backend/app/matcher/matcher.py
매칭 엔진 — 필드별 비교 함수.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Literal

from dateutil.relativedelta import relativedelta

from app.matcher.cert_mapping import match_cert
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
    # 시군구까지 포함된 주소 ("서울특별시 강남구") → 광역시/도 접두사로 매칭
    for key, aliases in REGION_GROUPS.items():
        for alias in (key, *aliases):
            if region.startswith(alias):
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
    if founded_date > today:
        # 미래 창업일은 판단 불가 (음수 업력이 미만/이하 조건을 충족해버리는 것 방지)
        return None
    delta = relativedelta(today, founded_date)
    return delta.years + delta.months / 12 + delta.days / 365.25


def calculate_age(birth_date: date | None) -> int | None:
    """
    만 나이 계산 (KST 기준 date.today() 사용).
    """
    if birth_date is None:
        return None
    today = date.today()
    if birth_date > today:
        return None
    age = today.year - birth_date.year
    # 생일 안 지났으면 1 빼기
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


# ──────────────────────────────────────────────
# match_numeric
# ──────────────────────────────────────────────

def _bound_is_exclusive(raw_text: str, bound, keyword: str) -> bool:
    """범위 경계값 토큰 직후에 배타 키워드('미만'/'초과')가 결합돼 있는지 판별.

    raw 전역 substring 검색은 다른 절의 키워드를 오인한다
    (예: "3년 미만 기업 제외, 5년 이상 10년 이하"에서 상한 10은 '이하'(포함)여야 하나
    전역 검색은 '미만'을 잡아 10을 배타 처리해버림). 따라서 경계 숫자를 앞뒤가 숫자가
    아닌 토큰으로 찾아, 그 직후 8자 이내에 키워드가 붙은 경우만 배타로 인정한다.
    """
    if not raw_text:
        return False
    for m in re.finditer(rf"(?<!\d){re.escape(str(bound))}(?!\d)", raw_text):
        if keyword in raw_text[m.end(): m.end() + 8]:
            return True
    return False


def match_numeric(
    company_value: int | float | None,
    condition: ParsedCondition,
) -> MatchStatus:
    """
    수치 비교 — 업력 / 매출 / 나이 / 종업원 수에 공통 적용.

    operator: "미만" | "이하" | "이내" | "이상" | "초과" | "범위"
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
        elif op in ("이하", "이내"):
            # '이내'는 '이하'와 동일 의미 (예: "창업 3년 이내" = 3년 이하)
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
            # 경계 포함/배타 판별 — "이상~미만"은 상한 배타, "초과~이하"는 하한 배타.
            # 추출은 경계값을 그대로 인코딩하므로("65세 미만"→max:65) raw_text로 배타성을 복원한다.
            # 미복원 시 만 65세가 "65세 미만"에 충족으로 오판정됨. 키워드는 경계값에 결합된 것만 인정.
            raw = condition.raw_text or ""
            lower_ok = (lo < company_value) if _bound_is_exclusive(raw, lo, "초과") else (lo <= company_value)
            upper_ok = (company_value < hi) if _bound_is_exclusive(raw, hi, "미만") else (company_value <= hi)
            return "충족" if (lower_ok and upper_ok) else "미충족"
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
    required_norms = [_normalize_region(str(r)) for r in required_regions]

    if company_norm in required_norms:
        return "충족"
    # 조건이 광역(시/도) 그룹으로 정규화되지 않으면(시군구 단위·해외 등)
    # 도 단위 회사 주소로는 소재 여부를 단정할 수 없다 → 확인필요
    if any(rn not in REGION_GROUPS for rn in required_norms):
        return "확인필요"
    # 회사 주소가 광역 그룹으로 해석 불가한 경우도 판단 불가
    if company_norm not in REGION_GROUPS:
        return "확인필요"
    return "미충족"


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
    # 조건 업종이 회사 업종에 포함될 때만 매칭 (예: "제조" ⊂ "식품 제조업").
    # 반대 방향(회사 업종 ⊂ 조건 업종)은 회사 업종이 더 일반적이라 단정 불가
    # (예: 회사 "제조업" vs 제외 조건 "도박기계 제조업" — 도박기계 여부를 알 수 없음)
    matched = any(a in company_industry for a in allowed)
    company_broader = not matched and any(company_industry in a for a in allowed)

    if op == "포함":
        if matched:
            return "충족"
        return "확인필요" if company_broader else "미충족"
    elif op == "제외":
        if matched:
            return "미충족"
        return "확인필요" if company_broader else "충족"
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
    예: "venture_company" → company_certs["venture_company"] == True 이면 충족.

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
    if not keys:
        # 빈 리스트가 공허하게 '충족' 판정되는 것 방지 — 판정 근거 없음
        return "확인필요"

    # 표준 키 boolean 외에 자유입력 텍스트(예: UI 등록 {note: "벤처기업 인증"})도
    # cert_mapping 키워드 매칭으로 인정 — 텍스트가 있는데 못 찾으면 단정하지 않는다
    cert_texts = [v for v in company_certs.values() if isinstance(v, str) and v.strip()]

    def _holds(k: str) -> bool:
        if company_certs.get(k) is True:
            return True
        return bool(cert_texts) and match_cert(cert_texts, k)

    if op == "보유":
        # 복수 요구 키는 '다음 인증 중 하나 보유' 요건이 일반적 → 하나라도 보유하면 충족
        if any(_holds(k) for k in keys):
            return "충족"
        return "확인필요" if cert_texts else "미충족"
    elif op == "미보유":
        if any(_holds(k) for k in keys):
            return "미충족"
        return "확인필요" if cert_texts else "충족"
    else:
        return "확인필요"


# ──────────────────────────────────────────────
# 매칭 정교화 — continuous score + distance metric + soft constraint 분리
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
    - 확인필요: 0.45 — "사실이면 충족일 수 있는 미지"는 "확실한 미충족"보다 항상 위
    - 미충족: 거리 기반 부분 점수 (0.0 ~ 0.3)
      - distance가 작을수록 (조건에 가까울수록) 높은 점수
      - distance >= 1.0이거나 None이면 0.0
      - 상한 0.3 < 확인필요 0.45: 확실한 탈락이 미지보다 위에 랭크되는 역전 방지
    - 해당없음: None (점수 계산에서 제외)
    ※ 0.45/0.3은 매칭 정답 데이터 부재로 캘리브레이션되지 않은 설계 상수 — 값이 아니라 순서가 설계 의도
    """
    if status == "충족":
        return 1.0
    elif status == "확인필요":
        return 0.45
    elif status == "미충족":
        if distance is None or distance >= 1.0:
            return 0.0
        return max(0.0, 1.0 - distance) * 0.3
    else:  # 해당없음
        return None


# ──────────────────────────────────────────────
# 총점 가중 합산 (공고 단위 aggregate score)
# ──────────────────────────────────────────────

# 표준 7종 필드별 가중치. 1차는 균등(1.0) — 가중치 학습(GT 기반) 후 교체 예정.
FIELD_WEIGHTS: dict[str, float] = {
    "업력": 1.0,
    "매출": 1.0,
    "지역": 1.0,
    "나이": 1.0,
    "종업원 수": 1.0,
    "업종": 1.0,
    "인증": 1.0,
}


def _effective_field_score(status: MatchStatus, score: float | None) -> float | None:
    """집계용 필드 점수. 저장된 score 우선, 없으면 status에서 유도.

    해당없음(또는 유도 불가)은 None → 집계에서 제외.
    """
    if score is not None:
        return score
    if status == "충족":
        return 1.0
    if status == "확인필요":
        return 0.3
    if status == "미충족":
        return 0.0
    return None  # 해당없음


def compute_aggregate_score(
    fields: list[tuple[str, MatchStatus, float | None]],
) -> float:
    """공고 단위 총점 (0~1) — 필드별 score의 가중 평균.

    Args:
        fields: (field_name, status, score) 튜플 리스트. score는 None 가능
                (그 경우 status에서 유도).

    Returns:
        가중 평균 (0~1). 집계 대상 필드(해당없음 제외)가 없으면 0.0.

    Notes:
        - 단순 충족/전체 비율이 아닌 연속 점수 (미충족 거리 부분점수, 확인필요 0.3 반영)
        - 가중치는 FIELD_WEIGHTS (1차 균등). 가중치 학습 후 이 dict만 교체하면 됨.
    """
    num = 0.0
    denom = 0.0
    for field_name, status, score in fields:
        eff = _effective_field_score(status, score)
        if eff is None:
            continue
        weight = FIELD_WEIGHTS.get(field_name, 1.0)
        num += weight * eff
        denom += weight
    return num / denom if denom > 0 else 0.0


def compute_field_sensitivities(
    fields: list[tuple[str, MatchStatus, float | None]],
) -> dict[str, float]:
    """필드별 sensitivity — 그 필드를 충족(1.0)시킬 때 공고 총점(aggregate) 상승폭.

    Δaggregate = weight × (1.0 − eff) / Σweight (선형 aggregate의 단순 미분).
    미충족이 심한(eff 낮은) 필드일수록 크다. Counterfactual에서 영향 큰 조건부터
    변경 제안하기 위한 정렬 키로 쓰고, raw 값은 사용자에게 노출하지 않는다.

    Args:
        fields: (field_name, status, score) 튜플 리스트 — compute_aggregate_score와 동일 입력.

    Returns:
        {field_name: sensitivity(0~1)}. 해당없음 필드는 제외, 집계 대상 없으면 {}.
    """
    active: list[tuple[str, float, float]] = []
    denom = 0.0
    for field_name, status, score in fields:
        eff = _effective_field_score(status, score)
        if eff is None:
            continue
        weight = FIELD_WEIGHTS.get(field_name, 1.0)
        denom += weight
        active.append((field_name, weight, eff))
    if denom == 0:
        return {}
    return {fn: weight * (1.0 - eff) / denom for fn, weight, eff in active}


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

        distance = compute_numeric_distance(company_numeric, cond, status)
        score = compute_field_score(status, distance)
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
            # Evidence 객체(text + location) 전체 전달 — match_results에 location까지 저장
            evidence=field.evidence if field.evidence else None,
            processing_path=field.processing_path,
        ))

    return results


# ──────────────────────────────────────────────
# Counterfactual — 미충족 필드를 충족시키는 최소 변경 역산
# ──────────────────────────────────────────────

def _fmt_revenue(won: int | float) -> str:
    """매출 원 단위 → 억/만원 표시."""
    won = int(won)
    if won % 100_000_000 == 0:
        return f"{won // 100_000_000}억원"
    if won % 10_000 == 0:
        return f"{won // 10_000}만원"
    return f"{won:,}원"


def _numeric_target(operator: str | None, value) -> int | float | None:
    """수치 operator/value → 충족시키는 경계값."""
    if operator == "이상":
        return value
    if operator == "초과":
        return value + 1
    if operator in ("이하", "이내"):
        # match_numeric은 '이내'를 '이하'와 동일 처리 — counterfactual도 일관되게 맞춤
        return value
    if operator == "미만":
        return value - 1
    if operator == "범위":
        if isinstance(value, dict) and "min" in value:
            return value["min"]
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return value[0]
    return None


def counterfactual_for_field(field: EligibilityField, company: Company) -> dict | None:
    """미충족 필드 1개의 최소 변경 제안.

    Returns dict {suggested_value, explanation, changeable, override_attr, override_value}
    또는 None (역산 불가). override_attr/value는 SimulateOverrides 적용용.
    """
    fn = field.field_name
    cond = field.condition
    op, val, raw = cond.operator, cond.value, cond.raw_text

    # 수치(매출/종업원 수) — operator 방향에 따라 현실성 분기
    if fn in ("매출", "종업원 수"):
        if op is None or val is None:
            return None
        attr = "revenue" if fn == "매출" else "employee_count"
        cur = company.revenue if fn == "매출" else company.employee_count
        fmt = _fmt_revenue if fn == "매출" else (lambda x: f"{x}명")
        cur_s = fmt(cur) if cur is not None else "미상"

        # 하한 미달(이상/초과) 또는 범위 아래 → 키우면 충족 (프로필 설정 가능)
        grow_target = _numeric_target(op, val) if op in ("이상", "초과") else None
        if op == "범위":
            lo = _numeric_target(op, val)
            if cur is not None and lo is not None and cur < lo:
                grow_target = lo
        if grow_target is not None:
            return {
                "suggested_value": fmt(grow_target),
                "explanation": f"{fn} {raw or fmt(grow_target)} 필요 (현재 {cur_s})",
                "changeable": True,
                "override_attr": attr,
                "override_value": int(grow_target),
            }

        # 상한 초과(이하/미만) 또는 범위 위 → 규모 축소는 비현실 (지원 대상 아님)
        return {
            "suggested_value": raw or "",
            "explanation": f"{fn} 기준 초과 (현재 {cur_s}, 기준 {raw}) — 규모 축소는 비현실적",
            "changeable": False,
            "override_attr": None,
            "override_value": None,
        }

    # 업력/나이 — 시간 기반이라 프로필 수정으로 못 바꿈
    if fn in ("업력", "나이"):
        return {
            "suggested_value": raw or "",
            "explanation": f"{fn} 조건({raw}) — 시간 기반이라 프로필 변경으로 충족 불가",
            "changeable": False,
            "override_attr": None,
            "override_value": None,
        }

    # 지역 — 요구 지역으로 이전
    if fn == "지역":
        regions = val if isinstance(val, list) else ([val] if val else [])
        if not regions:
            return None
        return {
            "suggested_value": f"{regions[0]} 소재",
            "explanation": f"지역을 {', '.join(regions)} 중 하나로 (현재 {company.region or '미상'})",
            "changeable": True,
            "override_attr": "region",
            "override_value": regions[0],
        }

    # 업종 — 포함이면 허용 업종으로, 제외 등은 구체 제안 어려움
    if fn == "업종":
        allowed = val if isinstance(val, list) else ([val] if val else [])
        if op == "포함" and allowed:
            return {
                "suggested_value": allowed[0],
                "explanation": f"업종을 {', '.join(allowed)} 중 하나로 (현재 {company.industry or '미상'})",
                "changeable": True,
                "override_attr": "industry",
                "override_value": allowed[0],
            }
        return {
            "suggested_value": "업종 변경 필요",
            "explanation": f"업종 조건({raw}) — 구체 변경 제안 어려움",
            "changeable": False,
            "override_attr": None,
            "override_value": None,
        }

    # 인증 — 보유면 취득 제안
    if fn == "인증":
        keys = val if isinstance(val, list) else ([val] if val else [])
        if op == "보유" and keys:
            certs = dict(company.certifications or {})
            for k in keys:
                certs[k] = True
            return {
                "suggested_value": f"{', '.join(keys)} 인증 취득",
                "explanation": f"{', '.join(keys)} 인증 취득 필요",
                "changeable": True,
                "override_attr": "certifications",
                "override_value": certs,
            }
        return {
            "suggested_value": "인증 조건 변경 필요",
            "explanation": f"인증 조건({raw}) — 변경 어려움",
            "changeable": False,
            "override_attr": None,
            "override_value": None,
        }

    return None