import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EligibilityResult(Base):
    __tablename__ = "eligibility_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("announcements.id"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(50))  # "업력" / "매출" / "지역" / "나이" / "인증"
    condition_value: Mapped[str] = mapped_column(Text)  # "7년 미만"
    condition_parsed: Mapped[dict | None] = mapped_column(JSONB)  # {"value": 7, "operator": "미만"}
    evidence: Mapped[str | None] = mapped_column(Text)
    evidence_source: Mapped[str | None] = mapped_column(Text)  # "aply_trgt_ctnt" / "첨부파일 2p 표 1행"
    processing_path: Mapped[str] = mapped_column(String(20))  # "rule_based" / "text_llm" / "vision_llm"
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))


class ExclusionResult(Base):
    __tablename__ = "exclusion_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("announcements.id"), index=True
    )
    exclusion_text: Mapped[str] = mapped_column(Text)
    evidence_source: Mapped[str | None] = mapped_column(Text)
    processing_path: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
