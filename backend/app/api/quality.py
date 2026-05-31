"""데이터 품질 리포트 API 컨트롤러 모듈."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.quality import QualityReport
from app.tools.data_quality import check_announcements

router = APIRouter()

@router.get("/report", response_model=QualityReport)
def get_quality_report(db: Session = Depends(get_db)) -> dict:
    """수집 데이터 품질 검사 리포트 API.

    7대 품질 항목(빈 title, 짧은 target_text, 첨부 유실, 다운로드/변환/추출 실패, 유사 중복 의심 건)에
    대해 데이터 정합성을 진단하여 일괄 리포트합니다.
    """
    return check_announcements(db)
