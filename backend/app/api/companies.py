from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.company import CompanyCreate, CompanyUpdate

router = APIRouter()


@router.get("/")
def list_companies(db: Session = Depends(get_db)):
    """기업 목록 조회"""
    # TODO: 구현
    return []


@router.get("/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db)):
    """기업 상세 조회"""
    # TODO: 구현
    return {}


@router.post("/")
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    """기업 등록"""
    # TODO: 구현
    return {}


@router.put("/{company_id}")
def update_company(company_id: str, data: CompanyUpdate, db: Session = Depends(get_db)):
    """기업 수정"""
    # TODO: 구현
    return {}
