"""업종 정밀도 패스 — 비업종 과추출 억제 + 진짜 업종요건 보존 가드 (verifier)."""
from app.extractor.verifier import _is_spurious_industry, verify
from app.extractor.llm_response_parser import ExtractionResult
from app.schemas.eligibility import EligibilityField, ParsedCondition


def _field(value, raw="", evidence="", operator=None, name="업종"):
    return EligibilityField(
        field_name=name,
        condition=ParsedCondition(value=value, operator=operator, raw_text=raw or (value if isinstance(value, str) else "")),
        evidence=evidence or (value if isinstance(value, str) else ""),
        evidence_source="LLM 추출",
        processing_path="text_llm",
    )


# --- 억제 대상: 비업종을 업종 요건으로 오추출한 7개 패턴 ---
def test_법인격_억제():  # ann_033
    assert _is_spurious_industry(_field("비영리법인, 정부 부처 허가 재단법인, 사단법인")) is True


def test_수요처_억제():  # ann_010 / ann_039
    assert _is_spurious_industry(_field("녹색기술 수요가 있는 대·중견기업 및 기관")) is True
    assert _is_spurious_industry(_field("방산 분야 수요기업")) is True


def test_중소기업_정의문_억제():  # ann_013
    assert _is_spurious_industry(_field("중소기업기본법 제2조 및 같은 법 시행령 제3조에 따른 중소기업")) is True


def test_과제범위_메타_억제():  # ann_014 / ann_035
    assert _is_spurious_industry(_field("6대 전략산업 12대 신산업 분야에 해당하는 과제")) is True
    assert _is_spurious_industry(_field("건설업 등 전 업종으로 확대")) is True


def test_참여제한_결격_억제():  # ann_011
    assert _is_spurious_industry(_field("스마트제조혁신 지원사업에서 참여제한 중인 기업은 참여 불가")) is True


# --- 보존 대상: 진짜 업종요건은 절대 억제하지 않음 ---
def test_라벨링갭_표준산업분류_보존():  # ann_003 — 긍정 가드
    f = _field("콘텐츠산업", evidence="한국표준산업분류 상 콘텐츠산업 업종에 해당하는 기업")
    assert _is_spurious_industry(f) is False


def test_라벨링갭_업종_열거_보존():  # ann_005 — 비업종 토큰 없음
    f = _field(["제조업", "지식정보 관련업", "건설업", "관광업"])
    assert _is_spurious_industry(f) is False


def test_제외_리스트형_보존():  # ann_024 / ann_042 — operator 가드
    f = _field(["사행산업", "도박"], operator="제외", evidence="지원제외 업종 영위기업 제외")
    assert _is_spurious_industry(f) is False


def test_정상_업종_보존():
    assert _is_spurious_industry(_field("제조업", operator="포함")) is False


def test_번호열거_가드가_비업종토큰보다_우선():
    # 비영리법인(억제 토큰)이 섞여도 번호 열거가 있으면 긍정 리스트로 보존
    f = _field("① 제조업 ② 비영리법인 관련업 ③ 건설업")
    assert _is_spurious_industry(f) is False


def test_타_필드는_무관():
    # 지역 필드에 억제 토큰이 있어도 업종 한정 규칙이라 건드리지 않음
    assert _is_spurious_industry(_field("방산 분야 수요기업", name="지역")) is False


# --- verify() 통합: spurious 업종은 제거, 진짜 업종은 유지 ---
def test_verify_spurious_업종_제거_진짜_유지():
    res = ExtractionResult(
        fields=[
            _field("비영리법인, 재단법인"),                 # 제거
            _field("제조업", operator="포함"),               # 유지
            _field("3년 미만", operator="미만", name="업력"),  # 무관 유지
        ],
        exclusions=[],
        processing_path="text_llm",
    )
    out = verify(res)
    names_values = [(f.field_name, f.condition.value) for f in out.fields]
    assert ("업종", "제조업") in names_values
    assert ("업력", "3년 미만") in names_values
    assert not any(f.field_name == "업종" and "비영리법인" in str(f.condition.value) for f in out.fields)
