import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.announcement import Announcement
from app.models.eligibility import EligibilityResult, ExclusionResult
from app.schemas.eligibility import (
    AnnouncementEligibilityResponse,
    EligibilityFieldResponse,
    ExclusionResponse,
    TriggerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{what} UUID 형식 오류: {value}")


@router.get("/{announcement_id}", response_model=AnnouncementEligibilityResponse)
def get_eligibility(announcement_id: str, db: Session = Depends(get_db)):
    """공고 자격요건 + 제외 대상 조회 (LLM 추출 결과)."""
    ann_uuid = _parse_uuid(announcement_id, "announcement_id")

    ann = db.get(Announcement, ann_uuid)
    if not ann:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    eligibility_rows = db.scalars(
        select(EligibilityResult)
        .where(EligibilityResult.announcement_id == ann_uuid)
        .order_by(EligibilityResult.created_at)
    ).all()

    exclusion_rows = db.scalars(
        select(ExclusionResult)
        .where(ExclusionResult.announcement_id == ann_uuid)
        .order_by(ExclusionResult.created_at)
    ).all()

    return AnnouncementEligibilityResponse(
        announcement_id=ann.id,
        title=ann.title,
        fields=[EligibilityFieldResponse.model_validate(r) for r in eligibility_rows],
        exclusions=[
            ExclusionResponse(
                text=r.exclusion_text,
                evidence_source=r.evidence_source,
                processing_path=r.processing_path,
            )
            for r in exclusion_rows
        ],
    )


@router.post("/{announcement_id}/extract", response_model=TriggerResponse)
def trigger_extract(announcement_id: str, db: Session = Depends(get_db)):
    """개별 공고 자격요건 추출 — Celery 비동기."""
    from app.worker.tasks import extract_announcement_eligibility

    ann_uuid = _parse_uuid(announcement_id, "announcement_id")

    if not db.get(Announcement, ann_uuid):
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")

    task = extract_announcement_eligibility.delay(str(ann_uuid))
    return TriggerResponse(task_id=task.id, message="추출 작업이 시작되었습니다.")


@router.post("/extract-all", response_model=TriggerResponse)
def trigger_extract_all(db: Session = Depends(get_db)):
    """미추출 공고 일괄 추출 — Celery 비동기."""
    from app.worker.tasks import extract_all_pending_eligibility

    task = extract_all_pending_eligibility.delay()
    return TriggerResponse(task_id=task.id, message="전체 추출 작업이 시작되었습니다.")
