import uuid
from datetime import date, datetime

from pydantic import BaseModel


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
    id: uuid.UUID
    extraction_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    items: list[AnnouncementResponse]
    total: int
