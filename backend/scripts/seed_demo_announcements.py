"""데모용 공고 적재 스크립트.

evaluation/ground_truth의 실제 공고 PDF(텍스트 레이어 보유분)를 announcements에 적재한다.
- title/source_url은 GT json에서, target_text는 PDF 텍스트 레이어에서 가져온다.
- 첨부파일 row를 만들어 PDF 뷰어/Vision 경로가 동작하도록 local_path를 연결한다.
- (source, source_id) 기준 idempotent — 이미 있으면 스킵.

실행 (백엔드 컨테이너):
    python scripts/seed_demo_announcements.py [--limit 20]

이후 추출/매칭:
    추출  → app.worker.tasks.extract_all_pending_eligibility
    매칭  → app.worker.tasks.match_company_announcements (회사별)
"""

import argparse
import json
import unicodedata
from datetime import date
from pathlib import Path

import pymupdf

from app.database import SessionLocal
from app.models.announcement import Announcement, Attachment

GT_ROOT = Path("/evaluation/ground_truth")
MIN_TEXT_LEN = 1000  # 텍스트 레이어가 이만큼 없으면 스캔본으로 보고 제외

# 데모 공고는 마감 전 상태로 보이도록 임의 기간을 부여한다 (PDF에서 기간 파싱은 범위 외)
DEMO_PERIOD_START = date(2026, 6, 1)
DEMO_PERIOD_END = date(2026, 7, 31)


def _source_from_url(url: str) -> str:
    if "k-startup" in url:
        return "kstartup"
    if "bizinfo" in url:
        return "bizinfo"
    if "mss.go.kr" in url:
        return "mss"
    return "demo"


def _pdf_text(pdf_path: Path) -> str:
    try:
        with pymupdf.open(pdf_path) as doc:
            text = "\n".join(page.get_text() for page in doc)
        return unicodedata.normalize("NFC", text)
    except Exception:
        return ""


def main(limit: int) -> None:
    db = SessionLocal()
    added = skipped = no_text = 0
    try:
        for gt_dir in sorted(GT_ROOT.glob("ann_*")):
            if added >= limit:
                break
            gt_file = gt_dir / "ground_truth.json"
            pdfs = list(gt_dir.glob("*.pdf"))
            if not gt_file.exists() or not pdfs:
                continue

            gt = json.loads(gt_file.read_text(encoding="utf-8"))
            ann_id = gt.get("announcement_id") or gt_dir.name
            title = unicodedata.normalize("NFC", gt.get("title") or pdfs[0].stem)
            source_url = gt.get("source_url") or ""
            source = _source_from_url(source_url)

            existing = db.query(Announcement).filter_by(source=source, source_id=ann_id).first()
            if existing:
                skipped += 1
                continue

            text = _pdf_text(pdfs[0])
            if len(text.strip()) < MIN_TEXT_LEN:
                no_text += 1
                continue

            ann = Announcement(
                source=source,
                source_id=ann_id,
                title=title,
                target_text=text,
                detail_url=source_url or None,
                period_start=DEMO_PERIOD_START,
                period_end=DEMO_PERIOD_END,
                extraction_status="pending",
            )
            db.add(ann)
            db.flush()
            db.add(Attachment(
                announcement_id=ann.id,
                file_name=pdfs[0].name,
                file_type="pdf",
                local_path=str(pdfs[0]),
                converted_pdf_path=str(pdfs[0]),
                conversion_status="skipped",
            ))
            added += 1
            print(f"  + {ann_id}: {title[:60]}")

        db.commit()
        print(f"\n적재 {added}건, 기존 스킵 {skipped}건, 텍스트 부족 제외 {no_text}건")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    main(args.limit)
