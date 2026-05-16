import uuid
from typing import Literal

from pydantic import BaseModel


class ParsedCondition(BaseModel):
    value: float | str | dict | None = None
    operator: str | None = None
    raw_text: str


class EligibilityField(BaseModel):
    field_name: str
    condition: ParsedCondition
    exception: str | None = None
    evidence: str
    evidence_source: str
    processing_path: Literal["rule_based", "text_llm", "vision_llm"]


class ExclusionItem(BaseModel):
    text: str
    exception: str | None = None
    evidence_source: str
    processing_path: Literal["text_llm", "vision_llm"]


class AnnouncementEligibility(BaseModel):
    announcement_id: str
    title: str
    fields: list[EligibilityField]
    exclusions: list[ExclusionItem]


class EligibilityResultResponse(BaseModel):
    id: uuid.UUID
    announcement_id: uuid.UUID
    field_name: str
    condition_value: str
    condition_parsed: dict | None = None
    evidence: str | None = None
    evidence_source: str | None = None
    processing_path: str

    model_config = {"from_attributes": True}


class EligibilityFieldResponse(BaseModel):
    """API 응답용 — id/announcement_id 제외 (URL path에 포함됨)."""

    field_name: str
    condition_value: str
    condition_parsed: dict | None = None
    evidence: str | None = None
    evidence_source: str | None = None
    processing_path: str

    model_config = {"from_attributes": True}


class ExclusionResponse(BaseModel):
    text: str
    evidence_source: str | None = None
    processing_path: str


class AnnouncementEligibilityResponse(BaseModel):
    """GET /api/eligibility/{announcement_id} 응답."""

    announcement_id: uuid.UUID
    title: str
    fields: list[EligibilityFieldResponse]
    exclusions: list[ExclusionResponse]


class TriggerResponse(BaseModel):
    task_id: str
    message: str
