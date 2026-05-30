"""하이브리드 엔진 통합 테스트.

3계층 분기(rule → text_llm → vision_llm) 흐름 + 엣지 케이스 + 내부 헬퍼.
LLM/rule_parser 호출은 monkeypatch로 가짜화 — 실 API/DB 의존성 없음.
"""
import pytest

from app.extractor import hybrid_engine
from app.extractor.llm_response_parser import ExtractionResult
from app.schemas.eligibility import EligibilityField, ParsedCondition


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _field(name, operator="미만", value=3, raw_text="3년 미만", processing_path="text_llm"):
    return EligibilityField(
        field_name=name,
        condition=ParsedCondition(operator=operator, value=value, raw_text=raw_text),
        evidence=f"{name} 근거",
        evidence_source="text",
        processing_path=processing_path,
    )


def _result(fields, exclusions=None, processing_path="text_llm"):
    return ExtractionResult(
        fields=fields,
        exclusions=exclusions or [],
        processing_path=processing_path,
    )


def _ann(target_text="자격요건 본문", pdf_path=None, source_id="TEST"):
    """기본 announcement dict — hybrid_engine 입력 형태."""
    attachments = []
    if pdf_path:
        attachments.append({"file_type": "pdf", "local_path": pdf_path})
    return {
        "source_id": source_id,
        "id": "test-uuid",
        "title": "테스트 공고",
        "target_text": target_text,
        "exclusion_text": "",
        "attachments": attachments,
    }


@pytest.fixture
def patch_rule_parser(monkeypatch):
    """rule_parser 모킹 헬퍼 — 호출 가능한 함수 반환."""
    def _do(rule_fields=None, api_sufficient=False, exclusion_sufficient=False):
        monkeypatch.setattr(
            hybrid_engine.rule_parser, "parse_structured_fields",
            lambda ann: rule_fields or [],
        )
        monkeypatch.setattr(
            hybrid_engine.rule_parser, "is_api_text_sufficient",
            lambda ann: api_sufficient,
        )
        monkeypatch.setattr(
            hybrid_engine.rule_parser, "is_exclusion_sufficient",
            lambda ann: exclusion_sufficient,
        )
    return _do


@pytest.fixture
def call_counter():
    """LLM 호출 횟수 카운터."""
    return {"text": 0, "vision": 0}


@pytest.fixture
def patch_text_llm(monkeypatch, call_counter):
    """text_llm.extract 모킹 — 반환값/예외 지정 가능."""
    def _do(return_value=None, raise_exc=None):
        async def fake(*a, **k):
            call_counter["text"] += 1
            if raise_exc:
                raise raise_exc
            return return_value if return_value is not None else _result([])
        monkeypatch.setattr(hybrid_engine.text_llm, "extract", fake)
    return _do


@pytest.fixture
def patch_vision_llm(monkeypatch, call_counter):
    """vision_llm.extract_from_pdf 모킹."""
    def _do(return_value=None, raise_exc=None):
        async def fake(*a, **k):
            call_counter["vision"] += 1
            if raise_exc:
                raise raise_exc
            return return_value if return_value is not None else _result([])
        monkeypatch.setattr(hybrid_engine.vision_llm, "extract_from_pdf", fake)
    return _do


# ---------------------------------------------------------------------------
# 시나리오 1~7: 3계층 분기 흐름
# ---------------------------------------------------------------------------

class TestBranchScenarios:
    pytestmark = pytest.mark.asyncio

    async def test_rule_only_skips_llm(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm, call_counter,
    ):
        """규칙으로 충분하면 text_llm/vision_llm 호출 X."""
        patch_rule_parser(
            rule_fields=[_field("업력", processing_path="rule_based")],
            api_sufficient=True, exclusion_sufficient=True,
        )
        patch_text_llm()
        patch_vision_llm()

        result = await hybrid_engine.extract_eligibility(_ann())

        assert call_counter == {"text": 0, "vision": 0}
        assert len(result.fields) == 1
        assert result.fields[0].processing_path == "rule_based"

    async def test_text_sufficient_skips_vision(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm, call_counter,
    ):
        """텍스트 LLM 결과 3+개 80%+ 명확하면 vision 호출 X."""
        patch_rule_parser(api_sufficient=False)
        text_result = _result([
            _field("업력"), _field("매출", operator="이하", value=10, raw_text="10억 이하"),
            _field("지역", operator="소재", value="서울", raw_text="서울 소재"),
        ])
        patch_text_llm(return_value=text_result)
        patch_vision_llm()

        result = await hybrid_engine.extract_eligibility(_ann())

        assert call_counter == {"text": 1, "vision": 0}
        assert len(result.fields) == 3

    async def test_text_insufficient_merges_vision(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm, call_counter,
    ):
        """텍스트 LLM 부족(<3) → vision 호출 → merge."""
        patch_rule_parser(api_sufficient=False)
        patch_text_llm(return_value=_result([_field("업력")]))  # 1개 → 부족
        patch_vision_llm(return_value=_result(
            [_field("업종", operator="포함", value="IT", raw_text="IT")],
            processing_path="vision_llm",
        ))

        result = await hybrid_engine.extract_eligibility(
            _ann(pdf_path="/tmp/test.pdf"),
        )

        assert call_counter == {"text": 1, "vision": 1}
        names = {f.field_name for f in result.fields}
        assert "업종" in names  # vision 결과 포함됨

    async def test_text_exception_continues_to_vision(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm, call_counter,
    ):
        """text_llm 예외 발생해도 vision 호출되어야 함."""
        patch_rule_parser(api_sufficient=False)
        patch_text_llm(raise_exc=RuntimeError("OpenAI down"))
        patch_vision_llm(return_value=_result(
            [_field("업종", operator="포함", value="IT", raw_text="IT")],
            processing_path="vision_llm",
        ))

        result = await hybrid_engine.extract_eligibility(
            _ann(pdf_path="/tmp/test.pdf"),
        )

        assert call_counter["vision"] == 1
        assert len(result.fields) >= 1  # vision 결과 반환됨

    async def test_vision_exception_falls_back_to_text(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm,
    ):
        """vision_llm 예외 → text 결과로 fallback."""
        patch_rule_parser(api_sufficient=False)
        text_result = _result([_field("업력"), _field("매출")])
        patch_text_llm(return_value=text_result)
        patch_vision_llm(raise_exc=RuntimeError("Vision down"))

        result = await hybrid_engine.extract_eligibility(
            _ann(pdf_path="/tmp/test.pdf"),
        )

        assert len(result.fields) == 2  # text 결과로 fallback

    async def test_all_llm_fail_uses_rule_fallback(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm,
    ):
        """모든 LLM 실패 → 규칙 결과 반환."""
        rule_fields = [_field("업력", processing_path="rule_based")]
        patch_rule_parser(rule_fields=rule_fields, api_sufficient=False)
        patch_text_llm(raise_exc=RuntimeError())
        patch_vision_llm(raise_exc=RuntimeError())

        result = await hybrid_engine.extract_eligibility(
            _ann(pdf_path="/tmp/test.pdf"),
        )

        assert len(result.fields) == 1
        assert result.fields[0].processing_path == "rule_based"

    async def test_no_pdf_skips_vision_uses_text_result(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm, call_counter,
    ):
        """첨부 PDF 없으면 vision 단계 자체를 건너뛰고 text 결과 반환."""
        patch_rule_parser(api_sufficient=False)
        text_result = _result([_field("업력"), _field("매출")])  # 부족 (<3)
        patch_text_llm(return_value=text_result)
        patch_vision_llm()  # 호출되면 안 됨

        result = await hybrid_engine.extract_eligibility(_ann())  # 첨부 없음

        assert call_counter["vision"] == 0
        assert len(result.fields) == 2  # text 결과 그대로


# ---------------------------------------------------------------------------
# 엣지 케이스
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """extract_eligibility 흐름의 엣지 케이스."""
    pytestmark = pytest.mark.asyncio

    async def test_empty_announcement_returns_empty_result(
        self, patch_rule_parser, patch_text_llm, patch_vision_llm,
    ):
        """본문/첨부 모두 없는 빈 입력."""
        patch_rule_parser(api_sufficient=False)
        patch_text_llm()  # text_llm은 빈 결과
        patch_vision_llm()

        empty = {
            "source_id": "X", "id": "x", "title": "",
            "target_text": "", "exclusion_text": "", "attachments": [],
        }
        result = await hybrid_engine.extract_eligibility(empty)

        assert result.announcement_id == "X"
        assert result.fields == []

    async def test_very_long_text_passes_through_to_llm(
        self, patch_rule_parser, patch_text_llm, monkeypatch,
    ):
        """매우 긴 본문도 잘림 없이 text_llm에 그대로 전달."""
        captured = {}

        async def fake_extract(text, *a, **k):
            captured["text_len"] = len(text)
            return _result([])

        monkeypatch.setattr(hybrid_engine.text_llm, "extract", fake_extract)
        patch_rule_parser(api_sufficient=False)

        long_text = "자격요건: " + ("a" * 20000)
        await hybrid_engine.extract_eligibility(_ann(target_text=long_text))

        assert captured["text_len"] > 20000

    async def test_structured_tables_passed_to_text_llm(
        self, patch_rule_parser, monkeypatch,
    ):
        """structured_tables가 hybrid_engine을 거쳐 text_llm에 combined_text로 전달."""
        captured = {}

        async def fake_extract(text, *a, **k):
            captured["text"] = text
            return _result([])

        monkeypatch.setattr(hybrid_engine.text_llm, "extract", fake_extract)
        patch_rule_parser(api_sufficient=False)

        ann = _ann(target_text="본문")
        ann["structured_tables"] = [{"name": "표_1", "markdown": "| a |"}]
        await hybrid_engine.extract_eligibility(ann)

        assert "본문" in captured["text"]
        assert "# 첨부 표" in captured["text"]
        assert "## 표_1" in captured["text"]


class TestPdfPathResolution:
    """`_get_attachment_pdf_path` 헬퍼 단위 테스트 (sync)."""

    def test_hwp_converted_pdf_path_used(self):
        """HWP→PDF 변환된 경로를 vision 단계에서 인식."""
        ann = {
            "source_id": "X", "id": "x", "title": "",
            "target_text": "", "exclusion_text": "",
            "attachments": [
                {"file_type": "hwp", "converted_pdf_path": "/tmp/converted.pdf"},
            ],
        }
        assert hybrid_engine._get_attachment_pdf_path(ann) == "/tmp/converted.pdf"

    def test_local_pdf_path_used_over_converted(self):
        """동일 첨부에 local_path + converted_pdf_path 있으면 local_path 우선."""
        ann = {
            "attachments": [
                {"file_type": "pdf", "local_path": "/tmp/original.pdf",
                 "converted_pdf_path": "/tmp/converted.pdf"},
            ],
        }
        assert hybrid_engine._get_attachment_pdf_path(ann) == "/tmp/original.pdf"

    def test_no_attachments_returns_none_pdf(self):
        assert hybrid_engine._get_attachment_pdf_path({"attachments": []}) is None
        assert hybrid_engine._get_attachment_pdf_path({}) is None


class TestBuildCombinedText:
    """`_build_combined_text` 헬퍼 단위 테스트 — structured_tables LLM prompt 통합."""

    def test_no_structured_tables_returns_target_text(self):
        ann = {"target_text": "자격요건 본문"}
        assert hybrid_engine._build_combined_text(ann) == "자격요건 본문"

    def test_structured_tables_appended_after_target_text(self):
        ann = {
            "target_text": "본문",
            "structured_tables": [
                {"name": "표_1", "markdown": "| a | b |\n|---|---|\n| 1 | 2 |"},
            ],
        }
        result = hybrid_engine._build_combined_text(ann)
        assert result.startswith("본문")
        assert "# 첨부 표" in result
        assert "## 표_1" in result
        assert "| a | b |" in result

    def test_no_target_text_with_tables(self):
        ann = {
            "structured_tables": [{"name": "표_1", "markdown": "| a |"}],
        }
        result = hybrid_engine._build_combined_text(ann)
        assert result.startswith("# 첨부 표")
        assert "## 표_1" in result

    def test_empty_announcement_returns_empty(self):
        assert hybrid_engine._build_combined_text({}) == ""

    def test_table_without_name_uses_default_index(self):
        ann = {
            "target_text": "본문",
            "structured_tables": [{"markdown": "| x |"}],  # name 누락
        }
        result = hybrid_engine._build_combined_text(ann)
        assert "## 표_0" in result

    def test_multiple_tables_joined(self):
        ann = {
            "target_text": "본문",
            "structured_tables": [
                {"name": "표_1", "markdown": "| a |"},
                {"name": "표_2", "markdown": "| b |"},
            ],
        }
        result = hybrid_engine._build_combined_text(ann)
        assert "## 표_1" in result
        assert "## 표_2" in result

    def test_none_structured_tables_treated_as_empty(self):
        """structured_tables가 None이면 빈 배열처럼 처리."""
        ann = {"target_text": "본문", "structured_tables": None}
        assert hybrid_engine._build_combined_text(ann) == "본문"


# ---------------------------------------------------------------------------
# 내부 헬퍼: _is_text_llm_sufficient
# ---------------------------------------------------------------------------

class TestIsTextLlmSufficient:

    def test_below_3_fields_not_sufficient(self):
        r = _result([_field("업력"), _field("매출")])  # 2개
        assert not hybrid_engine._is_text_llm_sufficient(r)

    def test_all_clear_sufficient(self):
        r = _result([_field("업력"), _field("매출"), _field("지역", operator="소재", value="서울", raw_text="서울")])
        assert hybrid_engine._is_text_llm_sufficient(r)

    def test_exactly_80_percent_sufficient(self):
        """4 clear + 1 unclear (=80%) → 충분."""
        unclear = EligibilityField(
            field_name="나이",
            condition=ParsedCondition(operator=None, value=None, raw_text="청년"),
            evidence="", evidence_source="", processing_path="text_llm",
        )
        r = _result([
            _field("업력"), _field("매출"), _field("지역", operator="소재", value="서울"),
            _field("업종", operator="포함", value="IT"), unclear,
        ])
        assert hybrid_engine._is_text_llm_sufficient(r)  # 4/5 = 0.8

    def test_below_80_percent_not_sufficient(self):
        """3 clear + 2 unclear (=60%) → 부족."""
        unclear = lambda name: EligibilityField(
            field_name=name,
            condition=ParsedCondition(operator=None, value=None, raw_text="청년"),
            evidence="", evidence_source="", processing_path="text_llm",
        )
        r = _result([
            _field("업력"), _field("매출"), _field("지역", operator="소재", value="서울"),
            unclear("나이"), unclear("종업원 수"),
        ])
        assert not hybrid_engine._is_text_llm_sufficient(r)  # 3/5 = 0.6


# ---------------------------------------------------------------------------
# 내부 헬퍼: _merge_results
# ---------------------------------------------------------------------------

class TestMergeResults:

    def test_no_text_returns_vision(self):
        vision = _result([_field("업력")], processing_path="vision_llm")
        merged = hybrid_engine._merge_results(None, vision)
        assert merged is vision

    def test_exclusions_deduplicated_preserving_order(self):
        text_r = _result([], exclusions=["A", "B"])
        vision_r = _result([], exclusions=["B", "C"], processing_path="vision_llm")
        merged = hybrid_engine._merge_results(text_r, vision_r)
        assert merged.exclusions == ["A", "B", "C"]

    def test_fields_unique_field_names_merged(self):
        text_r = _result([_field("업력"), _field("매출")])
        vision_r = _result(
            [_field("업종", operator="포함", value="IT", raw_text="IT",
                   processing_path="vision_llm")],
            processing_path="vision_llm",
        )
        merged = hybrid_engine._merge_results(text_r, vision_r)
        names = {f.field_name for f in merged.fields}
        assert names == {"업력", "매출", "업종"}

    def test_vision_priority_on_duplicate_field(self):
        """text와 vision 동일 field_name → vision 우선."""
        text_r = _result(
            [_field("업력", value=5, raw_text="5년 이하")],
            processing_path="text_llm",
        )
        vision_r = _result(
            [_field("업력", value=3, raw_text="3년 이하", processing_path="vision_llm")],
            processing_path="vision_llm",
        )
        merged = hybrid_engine._merge_results(text_r, vision_r)
        업력_field = next(f for f in merged.fields if f.field_name == "업력")
        assert 업력_field.condition.raw_text == "3년 이하"
