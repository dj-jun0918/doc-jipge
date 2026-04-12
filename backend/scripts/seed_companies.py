from datetime import date

from app.database import SessionLocal
from app.models.company import Company

# 기준일: 2026-04-11
COMPANIES = [
    # 1. 업력 2년 11개월 (3년 미만 경계)
    {
        "name": "테스트컴퍼니A",
        "founded_date": date(2023, 5, 11),
        "revenue": 500_000_000,
        "region": "서울",
        "industry": "소프트웨어 개발",
        "employee_count": 8,
        "ceo_birth_date": date(1990, 3, 15),
        "certifications": {"vc_certified": True},
        "is_edge_case": True,
    },
    # 2. 업력 3년 정각
    {
        "name": "테스트컴퍼니B",
        "founded_date": date(2023, 4, 11),
        "revenue": 500_000_000,
        "region": "서울",
        "industry": "소프트웨어 개발",
        "employee_count": 8,
        "ceo_birth_date": date(1990, 3, 15),
        "certifications": None,
        "is_edge_case": True,
    },
    # 3. 매출 9.99억
    {
        "name": "테스트컴퍼니C",
        "founded_date": date(2021, 1, 1),
        "revenue": 999_000_000,
        "region": "경기",
        "industry": "제조업",
        "employee_count": 15,
        "ceo_birth_date": date(1985, 6, 20),
        "certifications": None,
        "is_edge_case": True,
    },
    # 4. 매출 10억 정각
    {
        "name": "테스트컴퍼니D",
        "founded_date": date(2021, 1, 1),
        "revenue": 1_000_000_000,
        "region": "경기",
        "industry": "제조업",
        "employee_count": 15,
        "ceo_birth_date": date(1985, 6, 20),
        "certifications": None,
        "is_edge_case": True,
    },
    # 5. 대표 만 39세 (청년 경계)
    #    생년: 1986-04-12 → 오늘(4/11) 기준 생일 전 → 만 39세
    {
        "name": "테스트컴퍼니E",
        "founded_date": date(2022, 3, 1),
        "revenue": 300_000_000,
        "region": "부산",
        "industry": "정보통신업",
        "employee_count": 6,
        "ceo_birth_date": date(1986, 4, 12),
        "certifications": None,
        "is_edge_case": True,
    },
    # 6. 대표 만 40세
    #    생년: 1986-04-11 → 오늘(4/11) 생일 → 만 40세
    {
        "name": "테스트컴퍼니F",
        "founded_date": date(2022, 3, 1),
        "revenue": 300_000_000,
        "region": "부산",
        "industry": "정보통신업",
        "employee_count": 6,
        "ceo_birth_date": date(1986, 4, 11),
        "certifications": None,
        "is_edge_case": True,
    },
    # 7-1. 종업원 4명 (5인 이상 경계 — 미충족 측)
    {
        "name": "테스트컴퍼니G",
        "founded_date": date(2020, 7, 1),
        "revenue": 200_000_000,
        "region": "대전",
        "industry": "도소매업",
        "employee_count": 4,
        "ceo_birth_date": date(1980, 11, 5),
        "certifications": None,
        "is_edge_case": True,
    },
    # 7-2. 종업원 5명 (5인 이상 경계 — 충족 측)
    {
        "name": "테스트컴퍼니H",
        "founded_date": date(2020, 7, 1),
        "revenue": 200_000_000,
        "region": "대전",
        "industry": "도소매업",
        "employee_count": 5,
        "ceo_birth_date": date(1980, 11, 5),
        "certifications": None,
        "is_edge_case": True,
    },

    
]


def main():
    db = SessionLocal()
    try:
        for data in COMPANIES:
            company = Company(**data)
            db.add(company)
        db.commit()
        print(f"✅ {len(COMPANIES)}개 기업 프로필 INSERT 완료")
    finally:
        db.close()


if __name__ == "__main__":
    main()