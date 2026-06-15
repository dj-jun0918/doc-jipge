"""나이 정밀도 패스 — 비연령(등록 마감·자녀 나이) 과추출 억제 + 진짜 연령요건 보존 (verifier)."""
from app.extractor.verifier import _is_spurious_age, verify
from app.extractor.llm_response_parser import ExtractionResult
from app.schemas.eligibility import EligibilityField, ParsedCondition


def _field(value=None, operator=None, raw="", evidence="", name="나이"):
    return EligibilityField(
        field_name=name,
        condition=ParsedCondition(value=value, operator=operator, raw_text=raw),
        evidence=evidence or raw,
        evidence_source="LLM 추출",
        processing_path="text_llm",
    )


# --- 억제 대상: 신청자 연령이 아닌 값을 나이로 오추출 ---
def test_등록_마감일_억제():  # '26년 12월까지 사업자등록 필수' → 12월을 나이로 오인
    f = _field(value=None, raw="2026년 12월까지 사업자등록 필수",
               evidence="광명시 창업 계획이 있는 예비창업자(‘26년 12월까지 사업자등록 필수)")
    assert _is_spurious_age(f) is True


def test_자녀_나이_억제():  # '만12세 이하 자녀를 둔 육아기 연구자' → 자녀 나이는 신청자 나이 아님
    f = _field(value=12.0, operator="이하",
               evidence="※ 육아기 연구자란? 만12세 이하 또는 초등학교 6학년 이하 자녀를 둔 남녀 연구자")
    assert _is_spurious_age(f) is True


def test_날짜값_억제():  # 연도(2026)가 나이 값으로 오인식 — 신청자 나이로 비현실적
    assert _is_spurious_age(_field(value=2026, operator="이하", raw="2026년까지")) is True


# --- 보존 대상: 진짜 연령요건은 절대 억제하지 않음 ---
def test_정상_나이_상한_보존():
    assert _is_spurious_age(_field(value=39, operator="이하", raw="만 39세 이하", evidence="대표자 만 39세 이하")) is False


def test_청년_범위_보존():  # 범위(dict) value는 값검사 skip, 토큰 없음 → 보존
    assert _is_spurious_age(_field(value={"min": 18, "max": 34}, operator="범위", raw="청년 만 18~34세")) is False


def test_시니어_연령_보존():  # 만 65세 이상 (정상 범위 내)
    assert _is_spurious_age(_field(value=65, operator="이상", raw="만 65세 이상")) is False


def test_타_필드는_무관():  # 나이 한정 규칙 — 다른 필드의 자녀/등록 내용은 안 건드림
    assert _is_spurious_age(_field(value=12.0, raw="자녀 12세", name="종업원 수")) is False


# --- verify() 통합: spurious 나이는 제거, 진짜 나이는 유지 ---
def test_verify_spurious_나이_제거_진짜_유지():
    res = ExtractionResult(
        fields=[
            _field(value=12.0, operator="이하", evidence="만12세 이하 자녀를 둔 육아기 연구자"),  # 제거
            _field(value=39, operator="이하", raw="만 39세 이하", evidence="대표자 만 39세 이하"),  # 유지
            _field(value=3, operator="미만", raw="3년 미만", name="업력"),                          # 무관 유지
        ],
        exclusions=[],
        processing_path="text_llm",
    )
    out = verify(res)
    names_values = [(f.field_name, f.condition.value) for f in out.fields]
    assert ("나이", 39) in names_values
    assert ("업력", 3) in names_values
    assert not any(f.field_name == "나이" and f.condition.value == 12.0 for f in out.fields)
