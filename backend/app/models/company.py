import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    founded_date: Mapped[Date] = mapped_column(Date)
    revenue: Mapped[int] = mapped_column(BigInteger)  # 매출액 (원)
    region: Mapped[str] = mapped_column(String(100))
    industry: Mapped[str] = mapped_column(String(200))
    employee_count: Mapped[int] = mapped_column(Integer)
    ceo_birth_date: Mapped[Date] = mapped_column(Date)  # 만 나이는 매칭 시점에 계산
    certifications: Mapped[dict | None] = mapped_column(JSONB)
    is_edge_case: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
