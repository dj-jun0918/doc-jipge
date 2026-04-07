from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/{announcement_id}")
def get_eligibility(announcement_id: str, db: Session = Depends(get_db)):
    """해당 공고의 추출된 자격요건"""
    # TODO: 구현
    return {}


@router.post("/{announcement_id}/extract")
def trigger_extract(announcement_id: str, db: Session = Depends(get_db)):
    """개별 공고 추출 트리거"""
    # TODO: Celery 태스크 호출
    return {"message": "추출 작업이 시작되었습니다."}


@router.post("/extract-all")
def trigger_extract_all(db: Session = Depends(get_db)):
    """전체 미추출 공고 일괄 추출 트리거"""
    # TODO: Celery 태스크 호출
    return {"message": "전체 추출 작업이 시작되었습니다."}
