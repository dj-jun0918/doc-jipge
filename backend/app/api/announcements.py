from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.announcement import Announcement

router = APIRouter()

@router.get("/")
def list_announcements(
    source: str | None = Query(None, description="bizinfo/kstartup/mss"),
    region: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Announcement).where(Announcement.duplicate_of.is_(None))
    if source:
        stmt = stmt.where(Announcement.source == source)
    if region:
        stmt = stmt.where(Announcement.region == region)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Announcement.created_at.desc()).offset(offset).limit(limit)).all()

    return {"items": items, "total": total, "limit": limit, "offset": offset}

@router.get("/{announcement_id}")
def get_announcement(announcement_id: str, db: Session = Depends(get_db)):
    ann = db.get(Announcement, announcement_id)
    if not ann:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")
    return ann