import uuid
from typing import Literal

from pydantic import BaseModel


class MatchResultResponse(BaseModel):
    id: uuid.UUID
    announcement_id: uuid.UUID
    company_id: uuid.UUID
    field_name: str
    status: Literal["충족", "미충족", "확인필요", "해당없음"]
    company_value: str | None = None
    requirement_value: str | None = None
    evidence: str | None = None
    processing_path: str

    model_config = {"from_attributes": True}


class MatchSummaryResponse(BaseModel):
    announcement_id: uuid.UUID
    announcement_title: str
    results: list[MatchResultResponse]
