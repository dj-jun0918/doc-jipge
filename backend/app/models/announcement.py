import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(20), index=True)  # "bizinfo" / "kstartup" / "mss"
    source_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(String(200))
    executor: Mapped[str | None] = mapped_column(String(200))
    period_start: Mapped[Date | None] = mapped_column(Date)
    period_end: Mapped[Date | None] = mapped_column(Date)
    target_text: Mapped[str | None] = mapped_column(Text)
    exclusion_text: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    detail_url: Mapped[str | None] = mapped_column(Text)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("announcements.id"))
    raw_api_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.now)

    attachments: Mapped[list["Attachment"]] = relationship(back_populates="announcement")

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_announcements_source_source_id"),
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("announcements.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(20))  # "hwp" / "hwpx" / "pdf" / "zip" / "docx"
    download_url: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    converted_pdf_path: Mapped[str | None] = mapped_column(Text)
    conversion_status: Mapped[str] = mapped_column(String(20), default="pending")
    has_tables: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))

    announcement: Mapped["Announcement"] = relationship(back_populates="attachments")
