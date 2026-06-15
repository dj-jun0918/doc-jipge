"""지역 정밀도 패스 — 비소재지 과추출 억제 + 진짜 소재요건 보존 가드 (verifier)."""
from app.extractor.verifier import _is_spurious_region, verify
from app.extractor.llm_response_parser import ExtractionResult
from app.schemas.eligibility import EligibilityField, ParsedCondition


def _field(value, raw="", evidence="", operator=None, name="지역"):
    return EligibilityField(
        field_name=name,
        condition=ParsedCondition(value=value, operator=operator, raw_text=raw or (value if isinstance(value, str) else "")),
        evidence=evidence or (value if isinstance(value, str) else ""),
        evidence_source="LLM 추출",
        processing_path="text_llm",
    )


# --- 억제 대상: 비소재지를 지역 요건으로 오추출 ---
def test_수출_대상시장_억제():  # ann_013 — '중동지역 수출 실적'은 판로지 소재지가 아님
    f = _field("중동", raw="중동 지역 수출이력", evidence="단, 추경 우선선정 기업은 중동지역(22개국) 수출 실적 필요")
    assert _is_spurious_region(f) is True


def test_체류_외국인_신분_억제():  # ann_045 — 체류 자격은 위치가 아니라 신분
    f = _field("합법 체류 외국인", evidence="국내에서 기술창업을 하고자 하는 합법 체류 외국인")
    assert _is_spurious_region(f) is True


# --- 보존 대상: 진짜 소재요건은 절대 억제하지 않음 ---
def test_시도_별칭_가드_보존():  # ann_019 / ann_034 / ann_039 — 실제 시도 표기
    assert _is_spurious_region(_field("서울", evidence="서울특별시 소방재난본부")) is False
    assert _is_spurious_region(_field(["서울", "인천", "경기"], evidence="수도권 • 서울, 인천, 경기")) is False
    assert _is_spurious_region(_field("경기")) is False


def test_소재지_framing_가드_보존():  # ann_004 / adv_002 — 시군구 + 소재/관내
    assert _is_spurious_region(_field("횡성", raw="횡성군 관내", evidence="횡성군 관내 만45세 이하 창업기업")) is False
    assert _is_spurious_region(_field("대구 서구", raw="대구 서구 소재", evidence="대구 서구 소재 영업장")) is False


def test_전국_보존():  # ann_007(GT) / ann_027 — 전국은 무제한이지 비소재 신호 아님 (건드리지 않음)
    assert _is_spurious_region(_field("전국", evidence="공고일 기준 전국의 여성 예비창업자")) is False


def test_시도_가드가_수출토큰보다_우선():
    # 실제 소재(서울)가 있으면 '수출'이 섞여도 진짜 소재요건으로 보존
    f = _field("서울", raw="서울 소재 수출기업", evidence="서울 소재 수출 중소기업")
    assert _is_spurious_region(f) is False


def test_정상_소재_보존():
    assert _is_spurious_region(_field("대전", operator="소재", evidence="대전 소재 기업")) is False


def test_수출_들어간_지명_보존():  # 수출산업단지 등 — 지명에 '수출'이 들어가도 위치 가드로 보존
    assert _is_spurious_region(_field("수출산업단지", evidence="수출산업단지 입주기업")) is False
    assert _is_spurious_region(_field("구로수출산업단지", evidence="구로수출산업단지 내 창업기업")) is False


def test_타_필드는_무관():
    # 업종 필드에 비소재 토큰이 있어도 지역 한정 규칙이라 건드리지 않음
    assert _is_spurious_region(_field("중동 수출", name="업종")) is False


# --- verify() 통합: spurious 지역은 제거, 진짜 지역은 유지 ---
def test_verify_spurious_지역_제거_진짜_유지():
    res = ExtractionResult(
        fields=[
            _field("중동", raw="중동 지역 수출 실적 필요", evidence="중동지역(22개국) 수출 실적 필요"),  # 제거
            _field("대전", operator="소재", evidence="대전 소재 기업"),                              # 유지
            _field("3년 미만", operator="미만", name="업력"),                                       # 무관 유지
        ],
        exclusions=[],
        processing_path="text_llm",
    )
    out = verify(res)
    names_values = [(f.field_name, f.condition.value) for f in out.fields]
    assert ("지역", "대전") in names_values
    assert ("업력", "3년 미만") in names_values
    assert not any(f.field_name == "지역" and "중동" in str(f.condition.value) for f in out.fields)
