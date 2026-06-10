"""
backend/tests/test_verifier.py
함준규 verifier 단위 테스트
"""

import pytest

from app.extractor.llm_response_parser import ExtractionResult, VALID_FIELD_NAMES
from app.extractor.verifier import verify, deduplicate_fields, _pick_better
from app.schemas.eligibility import EligibilityField, ParsedCondition


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def make_field(field_name, operator=None, value=None, raw_text="", path="text_llm"):
    return EligibilityField(
        field_name=field_name,
        condition=ParsedCondition(operator=operator, value=value, raw_text=raw_text),
        evidence="테스트",
        evidence_source="LLM 추출",
        processing_path=path,
    )

def make_result(fields, exclusions=None, path="text_llm"):
    return ExtractionResult(
        fields=fields,
        exclusions=exclusions or [],
        processing_path=path,
    )


# ──────────────────────────────────────────────
# verify
# ──────────────────────────────────────────────

class TestVerify:

    def test_정상_추출_결과_통과(self):
        result = make_result([
            make_field("업력", "미만", 3, "3년 미만"),
            make_field("지역", "소재", "서울", "서울 소재"),
        ])
        verified = verify(result)
        assert len(verified.fields) == 2

    def test_알수없는_필드_제거(self):
        result = make_result([
            make_field("업력", "미만", 3, "3년 미만"),
            make_field("알수없는필드", None, None, ""),
        ])
        verified = verify(result)
        field_names = [f.field_name for f in verified.fields]
        assert "알수없는필드" not in field_names
        assert "업력" in field_names

    def test_operator_누락_폴백_파싱(self):
        # raw_text로 폴백 파싱 → operator/value 복원
        result = make_result([
            make_field("업력", None, None, "3년 미만"),
        ])
        verified = verify(result)
        assert verified.fields[0].condition.operator == "미만"
        assert verified.fields[0].condition.value == 3

    def test_operator_누락_폴백_실패_그대로_유지(self):
        # 폴백 파싱도 실패하면 그대로 유지
        result = make_result([
            make_field("업력", None, None, "파싱불가"),
        ])
        verified = verify(result)
        assert len(verified.fields) == 1
        assert verified.fields[0].condition.operator is None

    def test_exclusions_유지(self):
        result = make_result([], exclusions=["휴폐업 기업", "국세 체납"])
        verified = verify(result)
        assert verified.exclusions == ["휴폐업 기업", "국세 체납"]

    def test_processing_path_유지(self):
        result = make_result([], path="vision_llm")
        verified = verify(result)
        assert verified.processing_path == "vision_llm"


# ──────────────────────────────────────────────
# 인증 표준 키 정규화
# ──────────────────────────────────────────────

class TestCertNormalization:

    def test_원문_표현_value를_표준_키로_정규화(self):
        result = make_result([
            make_field("인증", "보유", "벤처기업 보유", "벤처기업 보유"),
        ])
        verified = verify(result)
        assert verified.fields[0].condition.value == "venture_company"

    def test_value_없으면_raw_text에서_표준_키_추출(self):
        result = make_result([
            make_field("인증", "보유", None, "이노비즈 인증 보유"),
        ])
        verified = verify(result)
        assert verified.fields[0].condition.value == "inno_biz"

    def test_이미_표준_키면_유지(self):
        result = make_result([
            make_field("인증", "보유", "venture_company", "벤처기업 보유"),
        ])
        verified = verify(result)
        assert verified.fields[0].condition.value == "venture_company"

    def test_복수_인증은_키_리스트(self):
        result = make_result([
            make_field("인증", "보유", "이노비즈 또는 메인비즈", "이노비즈 또는 메인비즈 보유"),
        ])
        verified = verify(result)
        assert set(verified.fields[0].condition.value) == {"inno_biz", "main_biz"}

    def test_매핑에_없는_인증은_원문_유지(self):
        result = make_result([
            make_field("인증", "보유", "성능인증(EPC)", "성능인증(EPC) 보유"),
        ])
        verified = verify(result)
        assert verified.fields[0].condition.value == "성능인증(EPC)"

    def test_인증_외_필드는_정규화_안_함(self):
        result = make_result([
            make_field("지역", "소재", "벤처밸리", "벤처밸리 소재"),
        ])
        verified = verify(result)
        assert verified.fields[0].condition.value == "벤처밸리"

    def test_중복_필드_병합(self):
        result = make_result([
            make_field("업력", "미만", 3, "3년 미만"),
            make_field("업력", "이하", 5, "5년 이하"),
        ])
        verified = verify(result)
        field_names = [f.field_name for f in verified.fields]
        assert field_names.count("업력") == 1

    def test_빈_필드_리스트(self):
        result = make_result([])
        verified = verify(result)
        assert verified.fields == []

    def test_VALID_FIELD_NAMES_전체_통과(self):
        fields = [make_field(name, "미만", 3, "3년 미만") for name in VALID_FIELD_NAMES]
        result = make_result(fields)
        verified = verify(result)
        assert len(verified.fields) == len(VALID_FIELD_NAMES)


# ──────────────────────────────────────────────
# deduplicate_fields
# ──────────────────────────────────────────────

class TestDeduplicateFields:

    def test_중복_없음_그대로(self):
        fields = [
            make_field("업력", "미만", 3, "3년 미만"),
            make_field("지역", "소재", "서울", "서울 소재"),
        ]
        result = deduplicate_fields(fields)
        assert len(result) == 2

    def test_중복_업력_하나로_병합(self):
        fields = [
            make_field("업력", "미만", 3, "3년 미만"),
            make_field("업력", "이하", 5, "5년 이하"),
        ]
        result = deduplicate_fields(fields)
        assert len(result) == 1
        assert result[0].field_name == "업력"

    def test_중복시_operator_명확한_쪽_우선(self):
        fields = [
            make_field("업력", None, None, "파싱불가"),   # 불명확
            make_field("업력", "미만", 3, "3년 미만"),    # 명확
        ]
        result = deduplicate_fields(fields)
        assert result[0].condition.operator == "미만"

    def test_중복시_엄격한_operator_우선(self):
        # 미만(0) vs 이하(1) → 미만 우선
        fields = [
            make_field("업력", "이하", 5, "5년 이하"),
            make_field("업력", "미만", 3, "3년 미만"),
        ]
        result = deduplicate_fields(fields)
        assert result[0].condition.operator == "미만"

    def test_빈_리스트(self):
        assert deduplicate_fields([]) == []

    def test_3개_중복_하나로(self):
        fields = [
            make_field("업력", "미만", 3, "3년 미만"),
            make_field("업력", "이하", 5, "5년 이하"),
            make_field("업력", "이상", 1, "1년 이상"),
        ]
        result = deduplicate_fields(fields)
        assert len(result) == 1


# ──────────────────────────────────────────────
# _pick_better
# ──────────────────────────────────────────────

class TestPickBetter:

    def test_명확한쪽_우선(self):
        a = make_field("업력", None, None, "")
        b = make_field("업력", "미만", 3, "3년 미만")
        assert _pick_better(a, b) == b

    def test_둘다_불명확_a_반환(self):
        a = make_field("업력", None, None, "")
        b = make_field("업력", None, None, "")
        assert _pick_better(a, b) == a

    def test_둘다_명확_엄격한쪽_우선(self):
        a = make_field("업력", "미만", 3, "3년 미만")   # priority 0
        b = make_field("업력", "이하", 5, "5년 이하")   # priority 1
        assert _pick_better(a, b) == a
