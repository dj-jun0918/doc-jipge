"""
backend/tests/test_rule_parser.py
함준규 rule_parser 단위 테스트 (PR#2)
"""

import pytest
from app.extractor.rule_parser import (
    parse_biz_enyy,
    parse_supt_regin,
    parse_biz_trgt_age,
    is_api_text_sufficient,
    parse_structured_fields,
)


# ──────────────────────────────────────────────
# parse_biz_enyy — 업력
# ──────────────────────────────────────────────

class TestParseBizEnyy:

    # 기본 케이스
    def test_3년_미만(self):
        result = parse_biz_enyy("창업 후 3년 미만 기업")
        assert result.value == 3
        assert result.operator == "미만"

    def test_5년_이상(self):
        result = parse_biz_enyy("업력 5년 이상")
        assert result.value == 5
        assert result.operator == "이상"

    def test_7년_이하(self):
        result = parse_biz_enyy("공고일 기준 창업 후 7년 이하 기업")
        assert result.value == 7
        assert result.operator == "이하"

    def test_10년_초과(self):
        result = parse_biz_enyy("업력 10년 초과 기업")
        assert result.value == 10
        assert result.operator == "초과"

    # 범위 케이스
    def test_범위_3년_7년(self):
        result = parse_biz_enyy("업력 3년~7년")
        assert result.operator == "범위"
        assert result.value["min"] == 3
        assert result.value["max"] == 7

    # 엣지 케이스
    def test_숫자_앞뒤_공백(self):
        result = parse_biz_enyy("창업 후  3 년  미만")
        assert result.value == 3
        assert result.operator == "미만"

    def test_매칭_없음_반환_None(self):
        result = parse_biz_enyy("중소기업")
        assert result is None

    def test_빈_문자열_반환_None(self):
        result = parse_biz_enyy("")
        assert result is None

    def test_raw_text_포함(self):
        result = parse_biz_enyy("창업 후 3년 미만 기업")
        assert result.raw_text is not None
        assert len(result.raw_text) > 0

    # 경계값: "미만" vs "이하" 엄격 구분
    def test_3년_미만_이하_구분(self):
        r_미만 = parse_biz_enyy("3년 미만")
        r_이하 = parse_biz_enyy("3년 이하")
        assert r_미만.operator == "미만"
        assert r_이하.operator == "이하"
        assert r_미만.operator != r_이하.operator


# ──────────────────────────────────────────────
# parse_supt_regin — 지역
# ──────────────────────────────────────────────

class TestParseSuptRegin:

    # 기본 케이스
    def test_서울특별시_정규화(self):
        result = parse_supt_regin("서울특별시 소재 기업")
        assert result.value == "서울"

    def test_서울시_정규화(self):
        result = parse_supt_regin("서울시 내 기업")
        assert result.value == "서울"

    def test_강원도_정규화(self):
        result = parse_supt_regin("강원도 내 기업")
        assert result.value == "강원"

    def test_강원특별자치도_정규화(self):
        result = parse_supt_regin("강원특별자치도 소재")
        assert result.value == "강원"

    def test_세종특별자치시_정규화(self):
        result = parse_supt_regin("세종특별자치시 소재")
        assert result.value == "세종"

    def test_대구광역시_정규화(self):
        result = parse_supt_regin("대구광역시 소재 기업")
        assert result.value == "대구"

    # 전국 케이스
    def test_전국_무관(self):
        result = parse_supt_regin("전국 소재 기업")
        assert result.value == "전국"
        assert result.operator == "무관"

    def test_전국_단독(self):
        result = parse_supt_regin("전국")
        assert result.value == "전국"

    # operator
    def test_operator_소재(self):
        result = parse_supt_regin("서울특별시 소재 기업")
        assert result.operator == "소재"

    # raw_text
    def test_raw_text_포함(self):
        result = parse_supt_regin("서울특별시 소재 기업")
        assert "서울" in result.raw_text

    # 엣지 케이스
    def test_매칭_없음_반환_None(self):
        result = parse_supt_regin("중소기업")
        assert result is None

    def test_빈_문자열_반환_None(self):
        result = parse_supt_regin("")
        assert result is None


# ──────────────────────────────────────────────
# parse_biz_trgt_age — 나이
# ──────────────────────────────────────────────

class TestParseBizTrgtAge:

    # 기본 케이스
    def test_만_39세_이하(self):
        result = parse_biz_trgt_age("만 39세 이하 청년 대표자")
        assert result.value == 39
        assert result.operator == "이하"

    def test_만_60세_이상(self):
        result = parse_biz_trgt_age("만 60세 이상")
        assert result.value == 60
        assert result.operator == "이상"

    def test_만_45세_미만(self):
        result = parse_biz_trgt_age("만 45세 미만인 자")
        assert result.value == 45
        assert result.operator == "미만"

    # 경계값: "이하" vs "미만" 엄격 구분
    def test_39세_이하_미만_구분(self):
        r_이하 = parse_biz_trgt_age("만 39세 이하")
        r_미만 = parse_biz_trgt_age("만 39세 미만")
        assert r_이하.operator == "이하"
        assert r_미만.operator == "미만"
        assert r_이하.operator != r_미만.operator

    # 엣지 케이스
    def test_만_없으면_None(self):
        result = parse_biz_trgt_age("39세 이하")
        assert result is None

    def test_매칭_없음_반환_None(self):
        result = parse_biz_trgt_age("중소기업")
        assert result is None

    def test_빈_문자열_반환_None(self):
        result = parse_biz_trgt_age("")
        assert result is None

    def test_raw_text_포함(self):
        result = parse_biz_trgt_age("만 39세 이하 청년 대표자")
        assert result.raw_text is not None
        assert len(result.raw_text) > 0


# ──────────────────────────────────────────────
# is_api_text_sufficient — 분기 판단
# ──────────────────────────────────────────────

class TestIsApiTextSufficient:

    def test_충분한_텍스트_True(self):
        ann = {
            "target_text": "업력 3년 미만, 서울특별시 소재, 만 39세 이하 청년",
            "exclusion_text": "휴폐업 기업"
        }
        assert is_api_text_sufficient(ann) is True

    def test_부족한_텍스트_False(self):
        ann = {"target_text": "중소기업", "exclusion_text": None}
        assert is_api_text_sufficient(ann) is False

    def test_텍스트_너무_짧음_False(self):
        ann = {"target_text": "짧음", "exclusion_text": ""}
        assert is_api_text_sufficient(ann) is False

    def test_target_text_없음_False(self):
        ann = {"exclusion_text": "휴폐업"}
        assert is_api_text_sufficient(ann) is False

    def test_2개_파싱_성공_True(self):
        # 업력 + 지역 → parsed_count == 2 → True
        ann = {"target_text": "업력 5년 이상, 서울특별시 소재 기업", "exclusion_text": ""}
        assert is_api_text_sufficient(ann) is True

    def test_1개_파싱_성공_False(self):
        # 업력만 → parsed_count == 1 → False
        ann = {"target_text": "업력 5년 이상 기업입니다", "exclusion_text": ""}
        assert is_api_text_sufficient(ann) is False


# ──────────────────────────────────────────────
# parse_structured_fields — 오케스트레이터
# ──────────────────────────────────────────────

class TestParseStructuredFields:

    def test_3개_필드_모두_추출(self):
        ann = {"target_text": "업력 3년 미만, 서울특별시 소재, 만 39세 이하 청년"}
        fields = parse_structured_fields(ann)
        field_names = [f.field_name for f in fields]
        assert "업력" in field_names
        assert "지역" in field_names
        assert "나이" in field_names

    def test_processing_path_rule_based(self):
        ann = {"target_text": "업력 3년 미만, 서울특별시 소재"}
        fields = parse_structured_fields(ann)
        for f in fields:
            assert f.processing_path == "rule_based"

    def test_매칭_없으면_빈_리스트(self):
        ann = {"target_text": "중소기업"}
        fields = parse_structured_fields(ann)
        assert fields == []

    def test_업력_지역만_추출(self):
        ann = {"target_text": "업력 5년 이상, 경기도 소재 기업"}
        fields = parse_structured_fields(ann)
        field_names = [f.field_name for f in fields]
        assert "업력" in field_names
        assert "지역" in field_names
        assert "나이" not in field_names

    def test_evidence_source_api(self):
        ann = {"target_text": "업력 3년 미만, 서울특별시 소재"}
        fields = parse_structured_fields(ann)
        for f in fields:
            assert f.evidence_source == "API target_text"
