"""데모 환경 셋업 — 회사 초기화/seed + (선택)실데이터 수집 + 매칭 실행.

기본은 기존 추출 공고에 대해 매칭하므로 LLM 비용 0.
--collect 시에만 외부 정부 API 수집 + 신규 공고 LLM 추출(비용 발생).

실행 예:
  # 회사만 깔끔히 교체 + 기존 공고로 매칭 (비용 0)
  docker compose exec -e PYTHONPATH=/app backend python /app/scripts/seed_demo.py

  # 기존 회사 유지 + 실데이터 소량 수집·추출·매칭 (비용 발생)
  docker compose exec -e PYTHONPATH=/app backend python /app/scripts/seed_demo.py \
      --keep-companies --collect --sources mss --limit 5
"""
import argparse
from datetime import date

from app.database import SessionLocal
from app.models.announcement import Announcement
from app.models.company import Company
from app.models.match_result import MatchResult
from app.worker.tasks import (
    collect_source,
    convert_attachments,
    download_attachment,
    extract_announcement_eligibility,
    match_company_announcements,
)

# 발표 데모용 6개 — 지역·업종·규모·연령·인증을 다르게 해서 매칭 스펙트럼이 잘 드러나게 구성.
DEMO_COMPANIES = [
    {"name": "테크노바", "founded_date": date(2023, 3, 1), "revenue": 300_000_000,
     "region": "서울", "industry": "소프트웨어 개발", "employee_count": 5,
     "ceo_birth_date": date(1995, 6, 15), "certifications": {"venture_company": True}},
    {"name": "대성정밀", "founded_date": date(2017, 4, 10), "revenue": 5_000_000_000,
     "region": "경기", "industry": "제조업", "employee_count": 45,
     "ceo_birth_date": date(1972, 9, 20), "certifications": {"iso_9001": True}},
    {"name": "부산테크", "founded_date": date(2021, 5, 1), "revenue": 800_000_000,
     "region": "부산", "industry": "정보통신업", "employee_count": 12,
     "ceo_birth_date": date(1985, 3, 10), "certifications": None},
    {"name": "그린에코", "founded_date": date(2024, 2, 1), "revenue": 150_000_000,
     "region": "대전", "industry": "도소매업", "employee_count": 3,
     "ceo_birth_date": date(1990, 11, 5), "certifications": {"women_owned": True}},
    {"name": "한빛바이오", "founded_date": date(2020, 6, 1), "revenue": 1_500_000_000,
     "region": "강원", "industry": "제조업", "employee_count": 22,
     "ceo_birth_date": date(1980, 1, 20), "certifications": {"inno_biz": True}},
    {"name": "미래로지스", "founded_date": date(2019, 8, 1), "revenue": 3_000_000_000,
     "region": "인천", "industry": "정보통신업", "employee_count": 30,
     "ceo_birth_date": date(1978, 7, 12), "certifications": {"main_biz": True}},
]


def setup_companies(keep: bool) -> list[tuple[str, str]]:
    """회사 seed(또는 기존 유지) 후 (id, name) 목록 반환."""
    db = SessionLocal()
    try:
        if keep:
            rows = db.query(Company).order_by(Company.created_at).all()
            print(f"회사 유지: 기존 {len(rows)}개 사용")
            return [(str(c.id), c.name) for c in rows]

        n_mr = db.query(MatchResult).delete()
        n_c = db.query(Company).delete()
        db.commit()
        print(f"초기화: 회사 {n_c}개, 매칭결과 {n_mr}행 삭제")

        ids = []
        for spec in DEMO_COMPANIES:
            c = Company(**spec)
            db.add(c)
            db.flush()
            ids.append((str(c.id), c.name))
        db.commit()
        print(f"seed: 데모 회사 {len(ids)}개 등록")
        return ids
    finally:
        db.close()


def collect_real(sources: list[str], limit: int) -> None:
    """실데이터 소량 수집 → 다운로드/변환 → 추출 (동기, LLM 비용 발생)."""
    print(f"실데이터 수집 (sources={sources}, 소스당 {limit}건) — 외부 API + LLM 추출 비용 발생")
    new_ids: list[str] = []
    for src in sources:
        ids = collect_source.apply(args=(src, limit)).get()
        print(f"   [{src}] 신규 {len(ids)}건")
        new_ids += ids

    for aid in new_ids:
        try:
            att_ids = download_attachment.apply(args=(aid,)).get()
            if att_ids:
                convert_attachments.apply(args=(att_ids,)).get()
            res = extract_announcement_eligibility.apply(args=(aid,)).get()
            print(f"   추출: {aid} → {res.get('status') if isinstance(res, dict) else res}")
        except Exception as e:  # noqa: BLE001 — 데모 스크립트라 1건 실패가 전체를 막지 않게
            print(f"   추출 실패(스킵): {aid} — {e}")


def reextract_existing() -> None:
    """기존 전체 공고를 새 코드로 재추출 (지역 필터·근거 페이지 적용). LLM 비용 발생."""
    db = SessionLocal()
    ann_ids = [str(a.id) for a in db.query(Announcement).all()]
    db.close()
    print(f"기존 {len(ann_ids)}건 재추출 (새 코드 적용) — LLM 비용 발생")
    ok = 0
    for aid in ann_ids:
        try:
            res = extract_announcement_eligibility.apply(args=(aid,)).get()
            if isinstance(res, dict) and res.get("status") == "ok":
                ok += 1
        except Exception as e:  # noqa: BLE001 — 데모 스크립트라 1건 실패가 전체를 막지 않게
            print(f"   재추출 실패(스킵): {aid[:8]} — {e}")
    print(f"   재추출 완료: {ok}/{len(ann_ids)}건")


def reverify_existing() -> None:
    """기존 추출 결과에 현재 verifier의 spurious 필터를 재적용 (LLM 없이 — 비용 0).

    재추출 없이 새 정밀도 필터(나이·지역·업종 등)를 기존 DB 데이터에 적용한다.
    각 EligibilityResult를 EligibilityField로 재구성 → spurious 판정 시 삭제.
    """
    from app.extractor.verifier import (
        _is_non_requirement_context,
        _is_preferential,
        _is_spurious_age,
        _is_spurious_industry,
        _is_spurious_region,
    )
    from app.models.eligibility import EligibilityResult
    from app.schemas.eligibility import EligibilityField, Evidence, ParsedCondition

    db = SessionLocal()
    try:
        rows = db.query(EligibilityResult).all()
        removed = 0
        for r in rows:
            cp = r.condition_parsed or {}
            ev = r.evidence or {}
            field = EligibilityField(
                field_name=r.field_name,
                condition=ParsedCondition(value=cp.get("value"), operator=cp.get("operator"), raw_text=cp.get("raw_text", "")),
                evidence=Evidence(**ev) if isinstance(ev, dict) else ev,
                evidence_source=r.evidence_source,
                processing_path=r.processing_path,
            )
            if (
                _is_spurious_age(field)
                or _is_spurious_region(field)
                or _is_spurious_industry(field)
                or _is_preferential(field)
                or _is_non_requirement_context(field)
            ):
                db.delete(r)
                removed += 1
        db.commit()
        print(f"재검증: spurious {removed}행 제거 (LLM 비용 0)")
    finally:
        db.close()


def run_match(company_ids: list[tuple[str, str]]) -> None:
    print("매칭 실행 (전체 공고 대상)...")
    for cid, name in company_ids:
        res = match_company_announcements.apply(args=(cid,)).get()
        n = res.get("matched_announcements") if isinstance(res, dict) else res
        print(f"   - {name}: {n}건")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-companies", action="store_true", help="기존 회사 유지(seed 안 함)")
    parser.add_argument("--no-match", action="store_true", help="매칭 생략")
    parser.add_argument("--collect", action="store_true", help="실데이터 수집(외부 API + LLM 비용)")
    parser.add_argument("--reextract", action="store_true", help="기존 전체 공고 재추출(새 코드 적용, LLM 비용)")
    parser.add_argument("--reverify", action="store_true", help="기존 추출에 spurious 필터 재적용(LLM 없이, 비용 0)")
    parser.add_argument("--sources", nargs="+", default=["mss"], help="수집 소스 (mss/bizinfo/kstartup)")
    parser.add_argument("--limit", type=int, default=5, help="소스당 수집 상한")
    args = parser.parse_args()

    ids = setup_companies(keep=args.keep_companies)
    for cid, name in ids:
        print(f"   - {name} ({cid})")

    if args.reextract:
        reextract_existing()
    if args.reverify:
        reverify_existing()
    if args.collect:
        collect_real(args.sources, args.limit)

    if not args.no_match:
        run_match(ids)


if __name__ == "__main__":
    main()
