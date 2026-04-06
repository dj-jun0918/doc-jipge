import uuid

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(20))  # "collect" / "convert" / "extract" / "match"
    status: Mapped[str] = mapped_column(String(20), default="running")  # "running" / "completed" / "failed"
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[DateTime] = mapped_column(DateTime, server_default=text("now()"))
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime)
