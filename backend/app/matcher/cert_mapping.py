"""인증 표준 키 ↔ 한글 키워드 매핑.

가이드라인 인증 매핑표와 1:1 동기화 필요 (한쪽 변경 시 양쪽 같이).
"""

CERT_MAPPING: dict[str, list[str]] = {
    "venture_company": ["벤처기업", "벤처기업 인증", "벤처기업 확인서"],
    "inno_biz": ["이노비즈", "기술혁신형 중소기업"],
    "main_biz": ["메인비즈", "경영혁신형 중소기업"],
    "iso_9001": ["ISO 9001", "ISO9001", "품질경영시스템"],
    "iso_14001": ["ISO 14001", "ISO14001", "환경경영시스템"],
    "iso_27001": ["ISO 27001", "ISO27001", "정보보안경영시스템"],
    "iso_22000": ["ISO 22000", "ISO22000", "식품안전경영시스템"],
    "gmp": ["GMP", "우수의약품제조관리기준"],
    "haccp": ["HACCP", "식품안전관리인증"],
    "ce_marking": ["CE", "CE 마킹"],
    "kc_certification": ["KC", "KC 인증"],
    "women_owned": ["여성기업", "여성기업확인서"],
    "social_enterprise": ["사회적기업", "사회적기업 인증"],
    "rd_lab": ["기업부설연구소", "기업부설 연구소"],
    "ip_protection": ["특허", "지식재산권", "실용신안"],
}


def match_cert(company_certs: list[str], required_cert_key: str) -> bool:
    """회사 인증에 required_cert_key의 한글 키워드가 포함되는지 검사.

    예: company_certs=["벤처기업 인증"], required_cert_key="venture_company" → True
    """
    keywords = CERT_MAPPING.get(required_cert_key, [])
    if not keywords:
        return False
    return any(kw in cert for cert in company_certs for kw in keywords)


def extract_cert_keys(text: str) -> list[str]:
    """텍스트에 등장하는 표준 키 목록 반환.

    예: "벤처기업 인증, ISO 9001" → ["venture_company", "iso_9001"]
    """
    matched = []
    for key, keywords in CERT_MAPPING.items():
        if any(kw in text for kw in keywords):
            matched.append(key)
    return matched
