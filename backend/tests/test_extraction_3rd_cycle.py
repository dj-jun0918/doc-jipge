"""3차 개선 사이클 — 파서·검증 정확도 수정 단위 테스트 (재추출과 무관하게 결정적 증명).

폴백 파서(매출 억/만원, 종업원 명, 범위), rule_parser(소수·이내), cert 약어 단어경계,
우대 가드 하드요건 보존.
"""
from app.extractor.llm_response_parser import parse_condition_string
from app.extractor.rule_parser import parse_biz_enyy
from app.extractor.verifier import (
    _is_non_requirement_context,
    _is_preferential,
    _recompute_amount,
)
from app.matcher.cert_mapping import extract_cert_keys, match_cert
from app.schemas.eligibility import EligibilityField, Evidence, ParsedCondition


# ── 폴백 파서 (parse_condition_string) ──

def test_매출_억원_파싱():
    # '10억원 이하' — 억 뒤 '원'을 허용 (이전엔 None)
    c = parse_condition_string("10억원 이하")
    assert c.value == 1_000_000_000 and c.operator == "이하"


def test_매출_만원_천만원_파싱():
    assert parse_condition_string("5천만원 이하").value == 50_000_000
    assert parse_condition_string("3000만원 이하").value == 30_000_000
    assert parse_condition_string("7억 5천만원 이하").value == 750_000_000


def test_종업원_명_파싱():
    assert parse_condition_string("30명 이하").value == 30
    assert parse_condition_string("5인 이상").value == 5  # 인도 여전히


def test_나이_범위_파싱():
    c = parse_condition_string("만 40세 이상 65세 미만")
    assert c.operator == "범위" and c.value == {"min": 40, "max": 65}


def test_업력_소수_폴백():
    c = parse_condition_string("1.5년 이하")
    assert c.value == 1.5 and c.operator == "이하"


# ── rule_parser ──

def test_rule_업력_이내():
    c = parse_biz_enyy("창업 후 7년 이내")
    assert c is not None and c.value == 7 and c.operator == "이내"


def test_rule_업력_소수_좌측앵커():
    # '1.5년'에서 '5년'만 잘못 캡처하지 않음
    c = parse_biz_enyy("업력 1.5년 이하")
    assert c is not None and c.value == 1.5 and c.operator == "이하"


# ── cert 약어 단어경계 ──

def test_cert_약어_단어경계_오탐_없음():
    assert match_cert(["CE 마킹 인증"], "ce_marking") is True
    assert match_cert(["ACE 솔루션 보유"], "ce_marking") is False
    assert match_cert(["INTERNET 서비스 기업"], "net") is False
    assert match_cert(["신기술 NET 보유"], "net") is True
    assert match_cert(["벤처기업 인증"], "venture_company") is True  # 한글 키워드 그대로
    assert "ce_marking" not in extract_cert_keys("ACE 가속기 프로그램")
    assert "net" not in extract_cert_keys("INTERNET 분야 지원사업")


# ── 우대 가드 하드요건 보존 (B1) ──

def _field(field_name, value, operator, raw, ev):
    return EligibilityField(
        field_name=field_name,
        condition=ParsedCondition(value=value, operator=operator, raw_text=raw),
        evidence=Evidence(text=ev, location=None),
        evidence_source="t",
        processing_path="text_llm",
    )


def test_우대가드_하드요건은_근거_가점_병기여도_보존():
    # '만 39세 이하 (여성 가점)' — 나이 하드 요건은 삭제하면 안 됨
    hard = _field("나이", 39, "이하", "만 39세 이하 (여성 가점)", "만 39세 이하인 자 (여성 가점 5점)")
    assert _is_preferential(hard) is False


def test_우대가드_순수우대는_삭제():
    pref = _field("업종", "제조업", None, "제조업 가점", "제조업 가점 5점")
    assert _is_preferential(pref) is True


def test_우대가드_근거에만_우대_있으면_보존():
    # raw_text엔 우대 없고 evidence 문장에만 병기된 경우 — 오삭제 방지
    ev_only = _field("지역", "서울", "소재", "서울 소재", "서울 소재 기업 (수도권 우대)")
    assert _is_preferential(ev_only) is False


# ── 천단위 콤마 금액 파싱 ──

def test_금액_천단위_콤마():
    # '1,200만원'의 '1,'이 잘려 '200만'(2백만)으로 오인식되던 버그
    assert parse_condition_string("1,200만원 이상").value == 12_000_000
    assert parse_condition_string("1,500만원 이하").value == 15_000_000


# ── LLM 산술 오류 방어 (_recompute_amount) ──

def test_금액_산술방어_LLM오류_교정():
    # LLM이 '20억원'을 2억으로 잘못 계산 → raw에서 재계산해 20억으로 교정
    f = _field("매출", 200_000_000, "미만", "20억원 미만", "매출액 20억원 미만")
    _recompute_amount(f)
    assert f.condition.value == 2_000_000_000


def test_금액_산술방어_매출만_대상():
    # 업력 등 비금액 필드는 건드리지 않음
    f = _field("업력", 7, "이내", "7년 이내", "업력 7년 이내")
    _recompute_amount(f)
    assert f.condition.value == 7


def test_금액_산술방어_외화는_미적용():
    # '1만달러'는 원화 단위(만 원) 아님 → 재계산 안 함 (LLM 값 유지)
    f = _field("매출", 10_000, "이상", "1만달러 이상", "수출실적 1만달러 이상")
    _recompute_amount(f)
    assert f.condition.value == 10_000


# ── 비요건 문맥 필터 (_is_non_requirement_context) ──

def test_비요건_주관기관_제외():
    f = _field("업종", "대기업", "포함", "대기업(계열사 포함), 중견기업 등", "(주관기관) 대기업(계열사 포함), 중견기업 등")
    assert _is_non_requirement_context(f) is True


def test_비요건_수요기업_제외():
    f = _field("업종", "방산", "포함", "방산 분야 수요기업", "방산 분야 수요기업 (대·중견기업·공공기관 등)")
    assert _is_non_requirement_context(f) is True


def test_비요건_혜택계상_제외():
    f = _field("업력", 7, "이내", "7년 이내", "창업일로부터 7년 이내의 중소기업은 기존인력 인건비 현금 계상 가능")
    assert _is_non_requirement_context(f) is True


def test_비요건_정상요건은_보존():
    # 일반 자격요건은 비요건 마커가 없어 보존
    f = _field("업력", 3, "미만", "3년 미만", "창업 후 3년 미만 중소기업")
    assert _is_non_requirement_context(f) is False
