import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class AnnouncementBase(BaseModel):
    title: str
    source: str
    source_id: str
    organization: str | None = None
    executor: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    target_text: str | None = None
    exclusion_text: str | None = None
    category: str | None = None
    region: str | None = None
    detail_url: str | None = None


class AnnouncementResponse(AnnouncementBase):
    """목록용 — 가벼움. attachments/structured_tables 미포함."""
    id: uuid.UUID
    extraction_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentInfo(BaseModel):
    """announcement detail 응답에 평탄화된 첨부파일 정보."""
    id: uuid.UUID
    file_name: str
    file_type: Literal["pdf", "hwp", "hwpx", "docx", "zip"]
    # has_pdf 계산용 — 응답에선 exclude (내부 경로 노출 방지)
    converted_pdf_path: str | None = Field(default=None, exclude=True)

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def has_pdf(self) -> bool:
        """PDF 스트리밍 가능 여부. HWPX는 False (frontend EvidencePlaceholder 분기)."""
        return bool(self.converted_pdf_path) or self.file_type == "pdf"


class AnnouncementDetailResponse(AnnouncementResponse):
    """단건용 — attachments + structured_tables 포함 (수십~수백 KB)."""
    attachments: list[AttachmentInfo] = []
    structured_tables: list[dict] | None = None  # HWPX 표 markdown 배열


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int


class AnnouncementSummaryResponse(BaseModel):
    """GET /api/announcements/{id}/summary 응답."""
    summary: str
    cached: bool
