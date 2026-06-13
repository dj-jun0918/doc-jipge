import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate

router = APIRouter()


def _parse_uuid(value: str, what: str = "company_id") -> uuid.UUID:
    """잘못된 UUID는 DB까지 보내 500을 내지 말고 400으로 — 엔드포인트 간 일관성."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{what} UUID 형식 오류: {value}")


@router.get("/")
def list_companies(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(select(Company).subquery()))
    items = db.scalars(select(Company).order_by(Company.created_at.desc()).offset(offset).limit(limit)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}



@router.get("/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db)):
    company = db.get(Company, _parse_uuid(company_id))
    if not company:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다")
    return company


@router.post("/", status_code=201)
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    company = Company(**data.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.put("/{company_id}")
def update_company(company_id: str, data: CompanyUpdate, db: Session = Depends(get_db)):
    company = db.get(Company, _parse_uuid(company_id))
    if not company:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company