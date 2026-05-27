"""cert_mapping 모듈 단위 테스트."""

from app.matcher.cert_mapping import CERT_MAPPING, extract_cert_keys, match_cert


def test_cert_mapping_has_15_keys():
    """인증 매핑표 15종 일치."""
    assert len(CERT_MAPPING) == 15


def test_match_cert_exact_match():
    """회사 인증 텍스트에 정확히 일치하는 키워드 있으면 True."""
    company_certs = ["벤처기업 인증", "ISO 9001"]
    assert match_cert(company_certs, "venture_company") is True
    assert match_cert(company_certs, "iso_9001") is True


def test_match_cert_partial_match():
    """키워드가 회사 인증 텍스트의 일부면 True (substring)."""
    company_certs = ["우리 회사는 벤처기업 확인서 보유"]
    assert match_cert(company_certs, "venture_company") is True


def test_match_cert_no_match():
    """매칭 안 되면 False."""
    company_certs = ["ISO 14001"]
    assert match_cert(company_certs, "venture_company") is False
    assert match_cert(company_certs, "haccp") is False


def test_match_cert_unknown_key_returns_false():
    """CERT_MAPPING에 없는 키는 False (빈 키워드 리스트)."""
    company_certs = ["벤처기업"]
    assert match_cert(company_certs, "unknown_cert") is False


def test_match_cert_empty_company_certs():
    """회사 인증 비어있으면 False."""
    assert match_cert([], "venture_company") is False


def test_extract_cert_keys_single_match():
    """텍스트에서 1개 인증 키워드 매칭."""
    text = "벤처기업 인증을 보유한 기업"
    assert extract_cert_keys(text) == ["venture_company"]


def test_extract_cert_keys_multiple_match():
    """텍스트에서 여러 인증 키워드 매칭."""
    text = "벤처기업 인증 보유, ISO 9001 획득, 사회적기업 인증"
    result = extract_cert_keys(text)
    assert "venture_company" in result
    assert "iso_9001" in result
    assert "social_enterprise" in result


def test_extract_cert_keys_no_match():
    """텍스트에 인증 없으면 빈 리스트."""
    text = "매출 10억 이상 중소기업"
    assert extract_cert_keys(text) == []


def test_extract_cert_keys_iso_variants():
    """ISO 9001 vs ISO9001 띄어쓰기 변형 모두 매칭."""
    assert "iso_9001" in extract_cert_keys("ISO9001 인증")
    assert "iso_9001" in extract_cert_keys("ISO 9001 인증")
    assert "iso_14001" in extract_cert_keys("ISO 14001 환경경영시스템")


def test_cert_mapping_keys_match_specification():
    """표준 키 15종 정확 일치 (가이드라인과 sync 필수)."""
    expected = {
        "venture_company", "inno_biz", "main_biz",
        "iso_9001", "iso_14001", "iso_27001", "iso_22000",
        "gmp", "haccp", "ce_marking", "kc_certification",
        "women_owned", "social_enterprise", "rd_lab", "ip_protection",
    }
    assert set(CERT_MAPPING.keys()) == expected
