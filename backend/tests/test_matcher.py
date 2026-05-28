"""
backend/tests/test_matcher.py
매칭 엔진 단위 테스트
seed_companies.py의 엣지 프로필 8개 기준.
기준일: 2026-05-09
"""

import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest
from dateutil.relativedelta import relativedelta

from app.matcher.matcher import (
    calculate_age,
    calculate_biz_age,
    compute_field_score,
    compute_numeric_distance,
    match_announcement,
    match_certification,
    match_industry,
    match_numeric,
    match_region,
)
from app.schemas.eligibility import EligibilityField, ParsedCondition


# ──────────────────────────────────────────────
# 헬퍼 — ParsedCondition 생성 단축 함수
# ──────────────────────────────────────────────

def cond(operator=None, value=None, raw_text=""):
    return ParsedCondition(operator=operator, value=value, raw_text=raw_text)


def field(field_name, operator=None, value=None, raw_text="", evidence="테스트"):
    return EligibilityField(
        field_name=field_name,
        condition=cond(operator=operator, value=value, raw_text=raw_text),
        evidence=evidence,
        evidence_source="API target_text",
        processing_path="rule_based",
    )


def make_company(**kwargs):
    """Company ORM 목 객체 생성."""
    defaults = dict(
        id=uuid.uuid4(),
        name="테스트",
        founded_date=date(2023, 1, 1),
        revenue=500_000_000,
        region="서울",
        industry="소프트웨어 개발",
        employee_count=10,
        ceo_birth_date=date(1990, 1, 1),
        certifications=None,
        is_edge_case=True,
    )
    defaults.update(kwargs)
    company = MagicMock()
    for k, v in defaults.items():
        setattr(company, k, v)
    return company


# ──────────────────────────────────────────────
# calculate_biz_age
# ──────────────────────────────────────────────

class TestCalculateBizAge:

    def test_None_반환_None(self):
        assert calculate_biz_age(None) is None

    def test_업력_양수(self):
        # 3년 이상임을 확인
        result = calculate_biz_age(date(2022, 1, 1))
        assert result > 3

    def test_업력_소수점_포함(self):
        # 약 2.92년 전 — 3년 미만 (date.today() 기반으로 시간 변화에 robust)
        founded = date.today() - relativedelta(years=2, months=11)
        result = calculate_biz_age(founded)
        assert result < 3

    def test_오늘_창업_0(self):
        result = calculate_biz_age(date.today())
        assert result == pytest.approx(0, abs=0.01)


# ──────────────────────────────────────────────
# calculate_age
# ──────────────────────────────────────────────

class TestCalculateAge:

    def test_None_반환_None(self):
        assert calculate_age(None) is None

    def test_만나이_생일_전(self):
        # 1986-04-12 → 2026-05-09 기준 생일 지남 → 만 40세
        assert calculate_age(date(1986, 4, 12)) == 40

    def test_만나이_생일_당일(self):
        # 오늘 생일 → 만 나이 증가
        today = date.today()
        age = calculate_age(date(today.year - 30, today.month, today.day))
        assert age == 30

    def test_만나이_생일_후(self):
        # 1990-01-01 → 2026-05-09 기준 생일 지남 → 만 36세
        assert calculate_age(date(1990, 1, 1)) == 36


# ──────────────────────────────────────────────
# match_numeric
# ──────────────────────────────────────────────

class TestMatchNumeric:

    # 미만
    def test_업력_2년11개월_3년_미만_충족(self):
        # 약 2.92년 전 → 3년 미만 충족 (시간 변화에 robust)
        founded = date.today() - relativedelta(years=2, months=11)
        biz_age = calculate_biz_age(founded)
        assert match_numeric(biz_age, cond("미만", 3, "3년 미만")) == "충족"

    def test_업력_3년정각_3년_미만_미충족(self):
        # 3.0년 정확히
        assert match_numeric(3.0, cond("미만", 3, "3년 미만")) == "미충족"

    # 이하
    def test_업력_3년정각_3년_이하_충족(self):
        assert match_numeric(3.0, cond("이하", 3, "3년 이하")) == "충족"

    def test_업력_3년초과_3년_이하_미충족(self):
        assert match_numeric(3.1, cond("이하", 3, "3년 이하")) == "미충족"

    # 이상
    def test_매출_10억_10억_이상_충족(self):
        # 컴퍼니D: revenue 1_000_000_000
        assert match_numeric(1_000_000_000, cond("이상", 1_000_000_000, "10억 이상")) == "충족"

    def test_매출_9억99_10억_이상_미충족(self):
        # 컴퍼니C: revenue 999_000_000
        assert match_numeric(999_000_000, cond("이상", 1_000_000_000, "10억 이상")) == "미충족"

    # 초과
    def test_종업원_5명_5명_초과_미충족(self):
        assert match_numeric(5, cond("초과", 5, "5명 초과")) == "미충족"

    def test_종업원_6명_5명_초과_충족(self):
        assert match_numeric(6, cond("초과", 5, "5명 초과")) == "충족"

    # 범위 — dict
    def test_범위_dict_충족(self):
        assert match_numeric(5, cond("범위", {"min": 3, "max": 7}, "3~7년")) == "충족"

    def test_범위_dict_경계_하한_충족(self):
        assert match_numeric(3, cond("범위", {"min": 3, "max": 7}, "3~7년")) == "충족"

    def test_범위_dict_경계_상한_충족(self):
        assert match_numeric(7, cond("범위", {"min": 3, "max": 7}, "3~7년")) == "충족"

    def test_범위_dict_하한_미만_미충족(self):
        assert match_numeric(2, cond("범위", {"min": 3, "max": 7}, "3~7년")) == "미충족"

    def test_범위_dict_상한_초과_미충족(self):
        assert match_numeric(8, cond("범위", {"min": 3, "max": 7}, "3~7년")) == "미충족"

    # 범위 — list
    def test_범위_list_충족(self):
        # list는 ParsedCondition.value 타입 미지원 → 함수 직접 호출
        from app.schemas.eligibility import ParsedCondition
        c = ParsedCondition.model_construct(operator="범위", value=[3, 7], raw_text="3~7년")
        assert match_numeric(5, c) == "충족"

    # 확인필요 케이스
    def test_company_value_None_확인필요(self):
        assert match_numeric(None, cond("미만", 3)) == "확인필요"

    def test_operator_None_확인필요(self):
        assert match_numeric(2, cond(None, 3)) == "확인필요"

    def test_value_None_확인필요(self):
        assert match_numeric(2, cond("미만", None)) == "확인필요"

    def test_범위_잘못된_형식_확인필요(self):
        assert match_numeric(5, cond("범위", "잘못된값")) == "확인필요"

    def test_알수없는_operator_확인필요(self):
        assert match_numeric(5, cond("같음", 5)) == "확인필요"


# ──────────────────────────────────────────────
# match_region
# ──────────────────────────────────────────────

class TestMatchRegion:

    def test_서울_서울특별시_충족(self):
        assert match_region("서울특별시", cond("소재", "서울", "서울특별시 소재")) == "충족"

    def test_서울_경기_미충족(self):
        assert match_region("경기도", cond("소재", "서울", "서울특별시 소재")) == "미충족"

    def test_전국_항상_충족(self):
        assert match_region("부산", cond("무관", "전국", "전국")) == "충족"

    def test_전국_raw_text_포함_충족(self):
        assert match_region("제주", cond(None, None, "전국 소재 기업")) == "충족"

    def test_region_None_확인필요(self):
        assert match_region(None, cond("소재", "서울", "서울")) == "확인필요"

    def test_condition_value_None_확인필요(self):
        assert match_region("서울", cond("소재", None, "서울")) == "확인필요"

    def test_강원도_정규화_충족(self):
        assert match_region("강원도", cond("소재", "강원", "강원 소재")) == "충족"

    def test_다중_지역_충족(self):
        from app.schemas.eligibility import ParsedCondition
        c = ParsedCondition.model_construct(operator="소재", value=["서울", "부산", "대구"], raw_text="서울/부산/대구")
        assert match_region("부산", c) == "충족"

    def test_다중_지역_미충족(self):
        from app.schemas.eligibility import ParsedCondition
        c = ParsedCondition.model_construct(operator="소재", value=["서울", "부산", "대구"], raw_text="서울/부산/대구")
        assert match_region("제주", c) == "미충족"

# ──────────────────────────────────────────────
# match_industry
# ──────────────────────────────────────────────

class TestMatchIndustry:

    def test_제조업_포함_충족(self):
        assert match_industry("제조업", cond("포함", "제조업", "제조업 한정")) == "충족"

    def test_IT서비스_제조업_포함_미충족(self):
        assert match_industry("IT 서비스", cond("포함", "제조업", "제조업 한정")) == "미충족"

    def test_다중_허용_업종_충족(self):
        from app.schemas.eligibility import ParsedCondition
        c = ParsedCondition.model_construct(operator="포함", value=["IT 서비스", "소프트웨어 개발"], raw_text="IT/SW")
        assert match_industry("소프트웨어 개발", c) == "충족"

    def test_제외_업종_미충족(self):
        assert match_industry("도소매업", cond("제외", "도소매업", "도소매업 제외")) == "미충족"

    def test_제외_업종_해당없음_충족(self):
        assert match_industry("소프트웨어 개발", cond("제외", "도소매업", "도소매업 제외")) == "충족"

    def test_industry_None_확인필요(self):
        assert match_industry(None, cond("포함", "제조업", "제조업")) == "확인필요"

    def test_operator_None_확인필요(self):
        assert match_industry("제조업", cond(None, "제조업", "제조업")) == "확인필요"

    def test_value_None_확인필요(self):
        assert match_industry("제조업", cond("포함", None, "제조업")) == "확인필요"

    def test_부분_문자열_매칭_충족(self):
        # "식품 제조업" in "제조업" 포함 조건
        assert match_industry("식품 제조업", cond("포함", "제조업", "제조업")) == "충족"

    def test_알수없는_operator_확인필요(self):
        assert match_industry("제조업", cond("동일", "제조업", "제조업")) == "확인필요"


# ──────────────────────────────────────────────
# match_certification
# ──────────────────────────────────────────────

class TestMatchCertification:

    def test_벤처인증_보유_충족(self):
        certs = {"vc_certified": True}
        assert match_certification(certs, cond("보유", "vc_certified", "벤처인증 보유")) == "충족"

    def test_벤처인증_없음_보유_미충족(self):
        certs = {"vc_certified": False}
        assert match_certification(certs, cond("보유", "vc_certified", "벤처인증 보유")) == "미충족"

    def test_인증_키_없음_보유_미충족(self):
        certs = {"iso9001": True}
        assert match_certification(certs, cond("보유", "vc_certified", "벤처인증 보유")) == "미충족"

    def test_미보유_조건_인증없음_충족(self):
        certs = {"vc_certified": False}
        assert match_certification(certs, cond("미보유", "vc_certified", "벤처인증 미보유")) == "충족"

    def test_미보유_조건_인증있음_미충족(self):
        certs = {"vc_certified": True}
        assert match_certification(certs, cond("미보유", "vc_certified", "벤처인증 미보유")) == "미충족"

    def test_certifications_None_보유_확인필요(self):
        assert match_certification(None, cond("보유", "vc_certified", "벤처인증")) == "확인필요"

    def test_certifications_None_미보유_충족(self):
        # 인증 자체가 없으면 미보유 조건 충족
        assert match_certification(None, cond("미보유", "vc_certified", "벤처인증 미보유")) == "충족"

    def test_다중_인증_모두_보유_충족(self):
        from app.schemas.eligibility import ParsedCondition
        certs = {"vc_certified": True, "iso9001": True}
        c = ParsedCondition.model_construct(operator="보유", value=["vc_certified", "iso9001"], raw_text="벤처+ISO")
        assert match_certification(certs, c) == "충족"

    def test_다중_인증_하나_없음_미충족(self):
        from app.schemas.eligibility import ParsedCondition
        certs = {"vc_certified": True, "iso9001": False}
        c = ParsedCondition.model_construct(operator="보유", value=["vc_certified", "iso9001"], raw_text="벤처+ISO")
        assert match_certification(certs, c) == "미충족"

    def test_operator_None_확인필요(self):
        assert match_certification({"vc_certified": True}, cond(None, "vc_certified")) == "확인필요"


# ──────────────────────────────────────────────
# match_announcement (오케스트레이터)
# ──────────────────────────────────────────────

class TestMatchAnnouncement:

    def test_전체_충족_케이스(self):
        company = make_company(
            founded_date=date.today() - relativedelta(years=2, months=11),  # 약 2.92년 — 3년 미만 충족
            region="서울",
            industry="소프트웨어 개발",
        )
        fields = [
            field("업력", "미만", 3, "3년 미만"),
            field("지역", "소재", "서울", "서울특별시 소재"),
            field("업종", "포함", "소프트웨어 개발", "소프트웨어 개발"),
        ]
        results = match_announcement(company, fields, uuid.uuid4())
        statuses = {r.field_name: r.status for r in results}
        assert statuses["업력"] == "충족"
        assert statuses["지역"] == "충족"
        assert statuses["업종"] == "충족"

    def test_일부_미충족_케이스(self):
        company = make_company(
            founded_date=date(2023, 4, 11),  # 3년 정각 — 3년 미만 미충족
            region="경기",
        )
        fields = [
            field("업력", "미만", 3, "3년 미만"),
            field("지역", "소재", "서울", "서울특별시 소재"),
        ]
        results = match_announcement(company, fields, uuid.uuid4())
        statuses = {r.field_name: r.status for r in results}
        assert statuses["업력"] == "미충족"
        assert statuses["지역"] == "미충족"

    def test_확인필요_케이스(self):
        company = make_company(founded_date=None, region=None)
        fields = [
            field("업력", "미만", 3, "3년 미만"),
            field("지역", "소재", "서울", "서울특별시 소재"),
        ]
        results = match_announcement(company, fields, uuid.uuid4())
        for r in results:
            assert r.status == "확인필요"

    def test_결과_개수_필드_수와_일치(self):
        company = make_company()
        fields = [
            field("업력", "미만", 3),
            field("지역", "소재", "서울"),
            field("업종", "포함", "소프트웨어 개발"),
        ]
        results = match_announcement(company, fields, uuid.uuid4())
        assert len(results) == 3

    def test_결과_field_name_일치(self):
        company = make_company()
        fields = [field("업력", "미만", 3), field("지역", "소재", "서울")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert {r.field_name for r in results} == {"업력", "지역"}

    def test_알수없는_필드_확인필요(self):
        company = make_company()
        fields = [field("알수없는필드", "미만", 3, "모름")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "확인필요"

    def test_빈_필드_리스트_빈_결과(self):
        company = make_company()
        results = match_announcement(company, [], uuid.uuid4())
        assert results == []

    def test_종업원_수_경계_이상_충족(self):
        # 컴퍼니H: employee_count=5, 조건 "5명 이상"
        company = make_company(employee_count=5)
        fields = [field("종업원 수", "이상", 5, "5인 이상")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "충족"

    def test_종업원_수_경계_미충족(self):
        # 컴퍼니G: employee_count=4, 조건 "5명 이상"
        company = make_company(employee_count=4)
        fields = [field("종업원 수", "이상", 5, "5인 이상")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "미충족"

    def test_나이_만39세_이하_충족(self):
        # 컴퍼니E: ceo_birth_date=1986-04-12 → 2026-05-09 기준 만 40세
        # 만 40세 이하 조건 충족
        company = make_company(ceo_birth_date=date(1986, 4, 12))
        fields = [field("나이", "이하", 40, "만 40세 이하")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "충족"

    def test_인증_필드_처리(self):
        company = make_company(certifications={"vc_certified": True})
        fields = [field("인증", "보유", "vc_certified", "벤처인증 보유")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "충족"


# ──────────────────────────────────────────────
# compute_numeric_distance
# ──────────────────────────────────────────────

class TestComputeNumericDistance:

    def test_충족이면_None(self):
        assert compute_numeric_distance(5, cond("미만", 7), "충족") is None

    def test_확인필요면_None(self):
        assert compute_numeric_distance(5, cond("미만", 7), "확인필요") is None

    def test_해당없음이면_None(self):
        assert compute_numeric_distance(5, cond("미만", 7), "해당없음") is None

    def test_company_value_None이면_None(self):
        assert compute_numeric_distance(None, cond("미만", 7), "미충족") is None

    def test_미만_초과_거리(self):
        # 매출 12억 vs 10억 이하 조건 → 거리 0.2 (20% 초과)
        d = compute_numeric_distance(12, cond("이하", 10), "미충족")
        assert d == pytest.approx(0.2, abs=0.01)

    def test_미만_큰_초과_거리(self):
        # 매출 50억 vs 10억 이하 → 거리 4.0
        d = compute_numeric_distance(50, cond("이하", 10), "미충족")
        assert d == pytest.approx(4.0, abs=0.01)

    def test_이상_미달_거리(self):
        # 5명 vs 10명 이상 → 거리 0.5 (50% 부족)
        d = compute_numeric_distance(5, cond("이상", 10), "미충족")
        assert d == pytest.approx(0.5, abs=0.01)

    def test_범위_하한_미달(self):
        # 2 vs {min: 3, max: 7} → 하한 3과 거리 0.333...
        d = compute_numeric_distance(2, cond("범위", {"min": 3, "max": 7}), "미충족")
        assert d == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_범위_상한_초과(self):
        # 10 vs {min: 3, max: 7} → 상한 7과 거리 0.428...
        d = compute_numeric_distance(10, cond("범위", {"min": 3, "max": 7}), "미충족")
        assert d == pytest.approx(3.0 / 7.0, abs=0.01)

    def test_value_0이면_None(self):
        # 0으로 나누기 방지
        assert compute_numeric_distance(5, cond("이하", 0), "미충족") is None

    def test_value_dict_불완전이면_None(self):
        # min만 있고 max 없으면 None
        assert compute_numeric_distance(5, cond("범위", {"min": 3}), "미충족") is None


# ──────────────────────────────────────────────
# compute_field_score
# ──────────────────────────────────────────────

class TestComputeFieldScore:

    def test_충족이면_1(self):
        assert compute_field_score("충족") == 1.0

    def test_확인필요면_0_3(self):
        assert compute_field_score("확인필요") == 0.3

    def test_해당없음이면_None(self):
        assert compute_field_score("해당없음") is None

    def test_미충족_distance_None이면_0(self):
        assert compute_field_score("미충족", None) == 0.0

    def test_미충족_distance_1이상이면_0(self):
        assert compute_field_score("미충족", 1.0) == 0.0
        assert compute_field_score("미충족", 2.5) == 0.0

    def test_미충족_거리_작으면_점수_높음(self):
        # distance 0.2 → score 0.5 * (1 - 0.2) = 0.4
        assert compute_field_score("미충족", 0.2) == pytest.approx(0.4, abs=0.01)

    def test_미충족_거리_경계_0이면_최대(self):
        # distance 0 → score 0.5 (충족과 명확히 구분)
        assert compute_field_score("미충족", 0.0) == 0.5

    def test_미충족_최대_0_5_보장(self):
        # 어떤 distance여도 미충족은 최대 0.5
        score = compute_field_score("미충족", 0.0)
        assert score <= 0.5


# ──────────────────────────────────────────────
# match_announcement 정교화 통합
# ──────────────────────────────────────────────

class TestMatchAnnouncementWithScoreDistance:

    def test_충족_필드_score_1(self):
        company = make_company(founded_date=date.today() - relativedelta(years=2, months=11))  # 약 2.92년
        fields = [field("업력", "미만", 3, "3년 미만")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "충족"
        assert results[0].score == 1.0
        assert results[0].distance is None
        assert results[0].constraint_type == "hard"

    def test_미충족_수치_필드_distance_채워짐(self):
        # 종업원 4명 vs 5명 이상 조건 → 미충족, distance = 0.2
        company = make_company(employee_count=4)
        fields = [field("종업원 수", "이상", 5, "5인 이상")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "미충족"
        assert results[0].distance == pytest.approx(0.2, abs=0.01)
        # score: 0.5 * (1 - 0.2) = 0.4
        assert results[0].score == pytest.approx(0.4, abs=0.01)
        assert results[0].constraint_type == "hard"

    def test_미충족_지역_필드_distance_None(self):
        # 지역은 수치 필드 아님 → distance None
        company = make_company(region="경기")
        fields = [field("지역", "소재", "서울", "서울특별시 소재")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "미충족"
        assert results[0].distance is None
        assert results[0].score == 0.0
        assert results[0].constraint_type == "hard"

    def test_확인필요_score_0_3(self):
        company = make_company(founded_date=None)
        fields = [field("업력", "미만", 3, "3년 미만")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "확인필요"
        assert results[0].score == 0.3
        assert results[0].distance is None

    def test_constraint_type_기본_hard(self):
        # 모든 필드 constraint_type 기본 "hard"
        company = make_company()
        fields = [
            field("업력", "미만", 3, "3년 미만"),
            field("지역", "소재", "서울", "서울"),
            field("인증", "보유", "vc_certified", "벤처인증 보유"),
        ]
        results = match_announcement(company, fields, uuid.uuid4())
        for r in results:
            assert r.constraint_type == "hard"

    def test_거리_큰_미충족은_0_점수(self):
        # 매출 50억 vs 10억 이하 → 거리 4.0 → score 0.0
        company = make_company(revenue=5_000_000_000)
        fields = [field("매출", "이하", 1_000_000_000, "10억 이하")]
        results = match_announcement(company, fields, uuid.uuid4())
        assert results[0].status == "미충족"
        assert results[0].distance == pytest.approx(4.0, abs=0.01)
        assert results[0].score == 0.0