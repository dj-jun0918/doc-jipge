"""파이프라인 작업 상태 조회 API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pipeline_job import PipelineJob

router = APIRouter()


def _parse_uuid(value: str, what: str = "job_id") -> uuid.UUID:
    """잘못된 UUID는 DB까지 보내 500을 내지 말고 400으로 — 엔드포인트 간 일관성."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{what} UUID 형식 오류: {value}")


@router.get("/jobs")
def list_jobs(
    status: str | None = Query(None, description="running/completed/failed"),
    job_type: str | None = Query(None, description="collect/convert/extract/match"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """파이프라인 작업 목록 (최신순)."""
    stmt = select(PipelineJob).order_by(PipelineJob.started_at.desc())
    if status:
        stmt = stmt.where(PipelineJob.status == status)
    if job_type:
        stmt = stmt.where(PipelineJob.job_type == job_type)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.offset(offset).limit(limit)).all()

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    """파이프라인 작업 단건 조회."""
    job = db.get(PipelineJob, _parse_uuid(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    return job


@router.get("/jobs/{job_id}/errors")
def get_job_errors(job_id: str, db: Session = Depends(get_db)):
    """파이프라인 작업 에러 요약."""
    job = db.get(PipelineJob, _parse_uuid(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    return {
        "job_id": str(job.id),
        "status": job.status,
        "fail_count": job.fail_count,
        "error_summary": job.error_summary,
        "finished_at": job.finished_at,
    }
