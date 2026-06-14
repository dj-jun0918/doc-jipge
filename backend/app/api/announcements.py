import logging
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.extractor import text_llm
from app.models.announcement import Announcement
from app.schemas.announcement import (
    AnnouncementDetailResponse,
    AnnouncementListResponse,
    AnnouncementResponse,
    AnnouncementSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_uuid(value: str, what: str = "announcement_id") -> uuid.UUID:
    """잘못된 UUID는 DB까지 보내 500을 내지 말고 400으로 — 엔드포인트 간 일관성."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{what} UUID 형식 오류: {value}")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {value} (YYYY-MM-DD 형식)")


@router.get("/", response_model=AnnouncementListResponse)
def list_announcements(
    source: str | None = Query(None, description="bizinfo/kstartup/mss"),
    region: str | None = Query(None),
    q: str | None = Query(None, description="키워드 검색 (제목)"),
    from_date: str | None = Query(None, description="접수 시작일 이후 (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="접수 종료일 이전 (YYYY-MM-DD)"),
    sort: str = Query("recent", pattern="^(recent|deadline)$", description="recent(최신순)/deadline(마감임박순)"),
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

    if sort == "deadline":
        # 마감 임박순 — 이미 마감된 공고는 제외(미정 NULL은 표시), 마감 가까운 순.
        stmt = stmt.where(
            (Announcement.period_end.is_(None))
            | (Announcement.period_end >= date.today())
        )
        # Postgres ASC는 NULL을 맨 뒤로 정렬 → 마감일 미정 공고가 임박 공고 뒤에 온다
        order_by = Announcement.period_end.asc()
    else:
        order_by = Announcement.created_at.desc()

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(order_by).offset(offset).limit(limit)).all()

    return AnnouncementListResponse(
        items=[AnnouncementResponse.model_validate(a) for a in items],
        total=total or 0,
    )


@router.get("/{announcement_id}", response_model=AnnouncementDetailResponse)
def get_announcement(announcement_id: str, db: Session = Depends(get_db)):
    ann_uuid = _parse_uuid(announcement_id)
    ann = db.scalar(
        select(Announcement)
        .options(selectinload(Announcement.attachments))  # N+1 방지
        .where(Announcement.id == ann_uuid)
    )
    if not ann:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")
    return ann


@router.get("/{announcement_id}/summary", response_model=AnnouncementSummaryResponse)
async def summarize(announcement_id: str, db: Session = Depends(get_db)):
    """공고 본문 한 줄 요약 (LLM 호출 + DB 캐싱)."""
    ann = db.get(Announcement, _parse_uuid(announcement_id))
    if not ann:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    if ann.summary:
        return {"summary": ann.summary, "cached": True}

    text = ann.target_text or ann.title
    try:
        summary = await _generate_summary(text)
    except Exception as e:
        logger.error(f"공고 요약 생성 실패 (id={announcement_id}): {e}")
        raise HTTPException(status_code=500, detail="요약 생성에 실패했습니다")

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
        timeout=30,
    )
    return (response.choices[0].message.content or "").strip()