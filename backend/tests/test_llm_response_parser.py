"""
backend/tests/test_llm_response_parser.py
함준규 llm_response_parser 단위 테스트
"""

import pytest

from app.extractor.llm_response_parser import (
    build_extraction_result,
    is_evidence_verbatim,
    parse_condition_string,
    VALID_FIELD_NAMES,
)


# ──────────────────────────────────────────────
# build_extraction_result
# ──────────────────────────────────────────────

class TestBuildExtractionResult:

    def test_정상_JSON_변환(self):
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3, "evidence": "창업 후 3년 미만"},
                {"field_name": "지역", "condition": "서울 소재", "operator": "소재", "value": "서울", "evidence": "서울 소재"},
            ],
            "exclusions": ["휴폐업 기업"],
        }
        result = build_extraction_result(llm_json)
        assert len(result.fields) == 2
        assert result.exclusions == ["휴폐업 기업"]

    def test_알수없는_필드_제거(self):
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3, "evidence": ""},
                {"field_name": "알수없는필드", "condition": "...", "operator": None, "value": None, "evidence": ""},
            ],
            "exclusions": [],
        }
        result = build_extraction_result(llm_json)
        field_names = [f.field_name for f in result.fields]
        assert "알수없는필드" not in field_names
        assert "업력" in field_names

    def test_processing_path_기본값_text_llm(self):
        result = build_extraction_result({"fields": [], "exclusions": []})
        assert result.processing_path == "text_llm"

    def test_processing_path_vision_llm(self):
        result = build_extraction_result({"fields": [], "exclusions": []}, processing_path="vision_llm")
        assert result.processing_path == "vision_llm"

    def test_빈_JSON_빈_결과(self):
        result = build_extraction_result({})
        assert result.fields == []
        assert result.exclusions == []

    def test_잘못된_필드_형식_스킵(self):
        llm_json = {
            "fields": [
                "잘못된 문자열",
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3, "evidence": ""},
            ],
            "exclusions": [],
        }
        result = build_extraction_result(llm_json)
        assert len(result.fields) == 1

    def test_빈_exclusion_문자열_제거(self):
        llm_json = {
            "fields": [],
            "exclusions": ["휴폐업 기업", "", "  ", "국세 체납"],
        }
        result = build_extraction_result(llm_json)
        assert "" not in result.exclusions
        assert "  " not in result.exclusions
        assert len(result.exclusions) == 2

    def test_VALID_FIELD_NAMES_전체_통과(self):
        fields = [
            {"field_name": name, "condition": "테스트", "operator": None, "value": None, "evidence": ""}
            for name in VALID_FIELD_NAMES
        ]
        result = build_extraction_result({"fields": fields, "exclusions": []})
        assert len(result.fields) == len(VALID_FIELD_NAMES)

    def test_condition_raw_text_매핑(self):
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3, "evidence": ""},
            ],
            "exclusions": [],
        }
        result = build_extraction_result(llm_json)
        assert result.fields[0].condition.raw_text == "3년 미만"

    def test_source_text_검증_환각_evidence는_필드_제외(self):
        """evidence가 원문에 없으면(환각) 해당 필드를 제외 — 검증 가능한 추출만 신뢰."""
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3,
                 "evidence": "원문에 없는 가짜 근거"},
            ],
            "exclusions": [],
        }
        result = build_extraction_result(llm_json, source_text="창업 후 3년 미만 중소기업")
        assert len(result.fields) == 0

    def test_source_text_없으면_검증_스킵(self):
        """source_text=None이면 evidence 검증 안 함 (기존 동작)."""
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3,
                 "evidence": "아무 evidence"},
            ],
            "exclusions": [],
        }
        result = build_extraction_result(llm_json)  # source_text 미전달
        assert len(result.fields) == 1

    def test_환각_evidence_경고_로그_발생(self, caplog):
        """evidence가 원문에 없으면 warning 로그 발생."""
        import logging
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3,
                 "evidence": "원문에 없는 가짜 근거"},
            ],
            "exclusions": [],
        }
        with caplog.at_level(logging.WARNING):
            build_extraction_result(llm_json, source_text="창업 후 3년 미만 중소기업")
        assert any("환각" in r.message for r in caplog.records)

    def test_정상_evidence_경고_로그_없음(self, caplog):
        """evidence가 원문에 있으면 warning 로그 없음."""
        import logging
        llm_json = {
            "fields": [
                {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3,
                 "evidence": "3년 미만"},
            ],
            "exclusions": [],
        }
        with caplog.at_level(logging.WARNING):
            build_extraction_result(llm_json, source_text="창업 후 3년 미만 중소기업")
        assert not any("환각 가능" in r.message for r in caplog.records)


# ──────────────────────────────────────────────
# is_evidence_verbatim
# ──────────────────────────────────────────────

class TestIsEvidenceVerbatim:

    def test_원문에_그대로_있으면_True(self):
        assert is_evidence_verbatim("3년 미만", "창업 후 3년 미만 중소기업")

    def test_원문에_없으면_False(self):
        assert not is_evidence_verbatim("5년 이상", "창업 후 3년 미만 중소기업")

    def test_빈_evidence는_True(self):
        assert is_evidence_verbatim("", "아무 원문")

    def test_표_라인_공백_차이_정규화_매칭(self):
        """LLM이 표 셀 공백을 다르게 반환해도 정규화 후 매칭."""
        evidence = "| 업력 | 창업 7년 이하 |"
        source = "# 첨부 표\n## 표_1\n|업력|  창업 7년 이하|\n| 매출 | 50억 |"
        assert is_evidence_verbatim(evidence, source)

    def test_줄바꿈_탭_정규화(self):
        evidence = "창업 후 3년 미만"
        source = "창업 후\t3년\n미만 중소기업"
        assert is_evidence_verbatim(evidence, source)


# ──────────────────────────────────────────────
# parse_condition_string
# ──────────────────────────────────────────────

class TestParseConditionString:

    def test_3년_미만(self):
        r = parse_condition_string("3년 미만")
        assert r.value == 3
        assert r.operator == "미만"

    def test_7년_이하(self):
        r = parse_condition_string("7년 이하")
        assert r.value == 7
        assert r.operator == "이하"

    def test_5년_이상(self):
        r = parse_condition_string("5년 이상")
        assert r.value == 5
        assert r.operator == "이상"

    def test_만_39세_이하(self):
        r = parse_condition_string("만 39세 이하")
        assert r.value == 39
        assert r.operator == "이하"

    def test_만_60세_이상(self):
        r = parse_condition_string("만 60세 이상")
        assert r.value == 60
        assert r.operator == "이상"

    def test_10억_이하(self):
        r = parse_condition_string("10억 이하")
        assert r.value == 1_000_000_000
        assert r.operator == "이하"

    def test_2억_이상(self):
        r = parse_condition_string("2억 이상")
        assert r.value == 200_000_000
        assert r.operator == "이상"

    def test_5인_이상(self):
        r = parse_condition_string("5인 이상")
        assert r.value == 5
        assert r.operator == "이상"

    def test_10인_미만(self):
        r = parse_condition_string("10인 미만")
        assert r.value == 10
        assert r.operator == "미만"

    def test_파싱_불가_None(self):
        r = parse_condition_string("파싱불가")
        assert r.value is None
        assert r.operator is None

    def test_빈_문자열_None(self):
        r = parse_condition_string("")
        assert r.value is None
        assert r.operator is None

    def test_raw_text_유지(self):
        r = parse_condition_string("3년 미만")
        assert r.raw_text == "3년 미만"

    def test_공백_있는_표현(self):
        r = parse_condition_string("창업 후  3 년  미만 기업")
        assert r.value == 3
        assert r.operator == "미만"


# ──────────────────────────────────────────────
# Evidence 스키마 coercion (JSONB null 백필 방어)
# ──────────────────────────────────────────────

class TestEvidenceCoerce:

    def test_문자열_입력_자동변환(self):
        from app.schemas.eligibility import Evidence
        ev = Evidence.model_validate("창업 후 3년 미만")
        assert ev.text == "창업 후 3년 미만"
        assert ev.location is None

    def test_dict_정상_변환(self):
        from app.schemas.eligibility import Evidence
        ev = Evidence.model_validate({"text": "근거", "location": None})
        assert ev.text == "근거"

    def test_text_null_dict_빈문자열_방어(self):
        # 마이그레이션 백필된 {"text": null} 이 ValidationError 없이 빈 문자열로
        from app.schemas.eligibility import Evidence
        ev = Evidence.model_validate({"text": None, "location": None})
        assert ev.text == ""
        assert ev.location is None
