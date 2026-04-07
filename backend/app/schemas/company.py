import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    founded_date: date
    revenue: int
    region: str
    industry: str
    employee_count: int
    ceo_birth_date: date
    certifications: dict | None = None
    is_edge_case: bool = False


class CompanyUpdate(BaseModel):
    name: str | None = None
    founded_date: date | None = None
    revenue: int | None = None
    region: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    ceo_birth_date: date | None = None
    certifications: dict | None = None
    is_edge_case: bool | None = None


class CompanyResponse(CompanyCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
