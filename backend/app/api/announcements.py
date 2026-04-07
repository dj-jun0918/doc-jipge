from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/")
def list_announcements(source: str | None = None, region: str | None = None, db: Session = Depends(get_db)):
    """공고 목록 조회 (필터: source, region)"""
    # TODO: 구현
    return {"items": [], "total": 0}


@router.get("/{announcement_id}")
def get_announcement(announcement_id: str, db: Session = Depends(get_db)):
    """공고 상세 조회"""
    # TODO: 구현
    return {}


@router.post("/collect")
def trigger_collect(db: Session = Depends(get_db)):
    """3소스 수집 트리거 (Celery 태스크)"""
    # TODO: Celery 태스크 호출
    return {"message": "수집 작업이 시작되었습니다."}
