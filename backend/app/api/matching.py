import logging
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.announcement import Announcement
from app.models.company import Company
from app.models.match_result import MatchResult
from app.schemas.matching import (
    CompanyMatchListResponse,
    CompanyMatchSummary,
    MatchResultDetailResponse,
    MatchResultItem,
    MatchResultStats,
    TriggerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{what} UUID 형식 오류: {value}")


@router.get("/{company_id}", response_model=CompanyMatchListResponse)
def get_matching_results(
    company_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """회사 전체 매칭 결과 — 충족 비율 기준 정렬 (TOP N)."""
    company_uuid = _parse_uuid(company_id, "company_id")

    if not db.get(Company, company_uuid):
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다")

    rows = db.execute(
        select(
            MatchResult.announcement_id,
            MatchResult.status,
            func.count().label("cnt"),
        )
        .where(MatchResult.company_id == company_uuid)
        .group_by(MatchResult.announcement_id, MatchResult.status)
    ).all()

    agg: dict[uuid.UUID, Counter] = {}
    for ann_id, status, cnt in rows:
        agg.setdefault(ann_id, Counter())[status] = cnt

    summaries: list[tuple[uuid.UUID, float, int, int]] = []
    for ann_id, counter in agg.items():
        fulfilled = counter.get("충족", 0)
        denom = fulfilled + counter.get("미충족", 0) + counter.get("확인필요", 0)
        score = fulfilled / denom if denom > 0 else 0.0
        total = sum(counter.values())
        summaries.append((ann_id, score, fulfilled, total))

    summaries.sort(key=lambda x: (-x[1], -x[3]))
    top = summaries[:limit]

    ann_ids = [s[0] for s in top]
    titles: dict[uuid.UUID, str] = {}
    if ann_ids:
        for ann in db.scalars(select(Announcement).where(Announcement.id.in_(ann_ids))):
            titles[ann.id] = ann.title

    items = [
        CompanyMatchSummary(
            announcement_id=ann_id,
            title=titles.get(ann_id, ""),
            match_score=round(score, 3),
            fulfilled_count=fulfilled,
            total_fields=total,
        )
        for ann_id, score, fulfilled, total in top
    ]

    return CompanyMatchListResponse(
        company_id=company_uuid,
        items=items,
        total=len(summaries),
    )


@router.get(
    "/{company_id}/{announcement_id}",
    response_model=MatchResultDetailResponse,
)
def get_matching_detail(
    company_id: str,
    announcement_id: str,
    db: Session = Depends(get_db),
):
    """특정 공고 vs 회사 필드별 매칭 결과."""
    company_uuid = _parse_uuid(company_id, "company_id")
    ann_uuid = _parse_uuid(announcement_id, "announcement_id")

    rows = db.scalars(
        select(MatchResult)
        .where(
            MatchResult.company_id == company_uuid,
            MatchResult.announcement_id == ann_uuid,
        )
        .order_by(MatchResult.created_at)
    ).all()

    if not rows:
        return MatchResultDetailResponse(
            company_id=company_uuid,
            announcement_id=ann_uuid,
            items=[],
            stats=MatchResultStats(),
            matched_at=None,
        )

    items = [
        MatchResultItem(
            field_name=r.field_name,
            status=r.status,
            company_value=r.company_value,
            requirement_value=r.requirement_value,
            evidence=r.evidence,
            processing_path=r.processing_path,
        )
        for r in rows
    ]
    counter = Counter(r.status for r in rows)
    stats = MatchResultStats(
        충족=counter.get("충족", 0),
        미충족=counter.get("미충족", 0),
        확인필요=counter.get("확인필요", 0),
        해당없음=counter.get("해당없음", 0),
    )

    return MatchResultDetailResponse(
        company_id=company_uuid,
        announcement_id=ann_uuid,
        items=items,
        stats=stats,
        matched_at=rows[-1].created_at,
    )


@router.post("/{company_id}/run", response_model=TriggerResponse)
def trigger_matching(company_id: str, db: Session = Depends(get_db)):
    """회사 vs DB 내 자격요건 추출된 공고 전체 매칭 — Celery 비동기."""
    from app.worker.tasks import match_company_announcements

    company_uuid = _parse_uuid(company_id, "company_id")

    if not db.get(Company, company_uuid):
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다")

    task = match_company_announcements.delay(str(company_uuid))
    return TriggerResponse(task_id=task.id, message="매칭 작업이 시작되었습니다.")
