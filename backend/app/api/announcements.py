from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.extractor import text_llm
from app.models.announcement import Announcement

router = APIRouter()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {value} (YYYY-MM-DD 형식)")


@router.get("/")
def list_announcements(
    source: str | None = Query(None, description="bizinfo/kstartup/mss"),
    region: str | None = Query(None),
    q: str | None = Query(None, description="키워드 검색 (제목)"),
    from_date: str | None = Query(None, description="접수 시작일 이후 (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="접수 종료일 이전 (YYYY-MM-DD)"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Announcement).where(Announcement.duplicate_of.is_(None))
    if source:
        stmt = stmt.where(Announcement.source == source)
    if region:
        stmt = stmt.where(Announcement.region == region)
    if q:
        stmt = stmt.where(Announcement.title.ilike(f"%{q}%"))
    from_date_obj = _parse_date(from_date)
    if from_date_obj:
        stmt = stmt.where(Announcement.period_start >= from_date_obj)
    to_date_obj = _parse_date(to_date)
    if to_date_obj:
        stmt = stmt.where(Announcement.period_end <= to_date_obj)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Announcement.created_at.desc()).offset(offset).limit(limit)).all()

    return {"items": items, "total": total, "limit": limit, "offset": offset}

@router.get("/{announcement_id}")
def get_announcement(announcement_id: str, db: Session = Depends(get_db)):
    ann = db.get(Announcement, announcement_id)
    if not ann:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")
    return ann


@router.get("/{announcement_id}/summary")
async def summarize(announcement_id: str, db: Session = Depends(get_db)):
    """공고 본문 한 줄 요약 (LLM 호출 + DB 캐싱)."""
    ann = db.get(Announcement, announcement_id)
    if not ann:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    if ann.summary:
        return {"summary": ann.summary, "cached": True}

    text = ann.target_text or ann.title
    summary = await _generate_summary(text)

    ann.summary = summary
    db.commit()

    return {"summary": summary, "cached": False}


async def _generate_summary(text: str, model: str = "gpt-4o-mini") -> str:
    """공고 텍스트 → 50자 이내 한 줄 요약."""
    client = text_llm._get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "다음 정부지원사업 공고를 한 줄(50자 이내)로 요약하세요."},
            {"role": "user", "content": text[:2000]},
        ],
        temperature=0.0,
        max_tokens=100,
    )
    return (response.choices[0].message.content or "").strip()