from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/{company_id}")
def get_matching_results(company_id: str, db: Session = Depends(get_db)):
    """해당 기업의 전체 매칭 결과"""
    # TODO: 구현
    return []


@router.get("/{company_id}/{announcement_id}")
def get_matching_detail(company_id: str, announcement_id: str, db: Session = Depends(get_db)):
    """특정 공고 상세 매칭 결과"""
    # TODO: 구현
    return {}


@router.post("/{company_id}/run")
def trigger_matching(company_id: str, db: Session = Depends(get_db)):
    """매칭 실행 트리거"""
    # TODO: Celery 태스크 호출
    return {"message": "매칭 작업이 시작되었습니다."}
