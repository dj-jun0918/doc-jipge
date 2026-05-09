"""
엣지 프로필 8개 × match_announcement 실행 데모
증빙용 스크립트 (Progress Report)
"""
import uuid
from datetime import date
from unittest.mock import MagicMock

import sys
sys.path.insert(0, "/Users/limtae-kyu/doc-jipge/backend")

from app.matcher.matcher import match_announcement
from app.schemas.eligibility import EligibilityField, ParsedCondition

def make_company(**kwargs):
    company = MagicMock()
    for k, v in kwargs.items():
        setattr(company, k, v)
    return company

def field(field_name, operator, value, raw_text, evidence="테스트"):
    return EligibilityField(
        field_name=field_name,
        condition=ParsedCondition(operator=operator, value=value, raw_text=raw_text),
        evidence=evidence,
        evidence_source="API target_text",
        processing_path="rule_based",
    )

# ── 공고 조건 (테스트용) ──────────────────────
FIELDS = [
    field("업력",     "미만",  3,           "3년 미만"),
    field("매출",     "이상",  1_000_000_000, "10억 이상"),
    field("종업원수", "이상",  5,           "5인 이상"),
    field("지역",     "소재",  "서울",      "서울특별시 소재"),
    field("업종",     "포함",  "소프트웨어 개발", "소프트웨어 개발"),
]

# ── 엣지 프로필 8개 ───────────────────────────
PROFILES = [
    ("컴퍼니A", dict(id=uuid.uuid4(), founded_date=date(2023,5,11), revenue=500_000_000,  employee_count=8,  region="서울",  industry="소프트웨어 개발", ceo_birth_date=date(1990,3,15), certifications={"vc_certified":True})),
    ("컴퍼니B", dict(id=uuid.uuid4(), founded_date=date(2023,4,11), revenue=500_000_000,  employee_count=8,  region="서울",  industry="소프트웨어 개발", ceo_birth_date=date(1990,3,15), certifications=None)),
    ("컴퍼니C", dict(id=uuid.uuid4(), founded_date=date(2021,1,1),  revenue=999_000_000,  employee_count=15, region="경기",  industry="제조업",           ceo_birth_date=date(1985,6,20), certifications=None)),
    ("컴퍼니D", dict(id=uuid.uuid4(), founded_date=date(2021,1,1),  revenue=1_000_000_000,employee_count=15, region="경기",  industry="제조업",           ceo_birth_date=date(1985,6,20), certifications=None)),
    ("컴퍼니E", dict(id=uuid.uuid4(), founded_date=date(2022,3,1),  revenue=300_000_000,  employee_count=6,  region="부산",  industry="정보통신업",       ceo_birth_date=date(1986,4,12), certifications=None)),
    ("컴퍼니F", dict(id=uuid.uuid4(), founded_date=date(2022,3,1),  revenue=300_000_000,  employee_count=6,  region="부산",  industry="정보통신업",       ceo_birth_date=date(1986,4,11), certifications=None)),
    ("컴퍼니G", dict(id=uuid.uuid4(), founded_date=date(2020,7,1),  revenue=200_000_000,  employee_count=4,  region="대전",  industry="도소매업",         ceo_birth_date=date(1980,11,5), certifications=None)),
    ("컴퍼니H", dict(id=uuid.uuid4(), founded_date=date(2020,7,1),  revenue=200_000_000,  employee_count=5,  region="대전",  industry="도소매업",         ceo_birth_date=date(1980,11,5), certifications=None)),
]

ann_id = uuid.uuid4()

print("=" * 70)
print(f"{'회사':<10} {'업력':<8} {'매출':<8} {'종업원수':<10} {'지역':<8} {'업종':<8}")
print("=" * 70)

for name, kwargs in PROFILES:
    company = make_company(**kwargs)
    results = match_announcement(company, FIELDS, ann_id)
    status_map = {r.field_name: r.status for r in results}
    print(
        f"{name:<10} "
        f"{status_map.get('업력','?'):<8} "
        f"{status_map.get('매출','?'):<8} "
        f"{status_map.get('종업원수','?'):<10} "
        f"{status_map.get('지역','?'):<8} "
        f"{status_map.get('업종','?'):<8}"
    )

print("=" * 70)
print("✅ match_announcement 실행 완료")
