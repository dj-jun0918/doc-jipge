import uuid
from typing import Literal

from pydantic import BaseModel


LocationType = Literal["pdf_page", "hwpx_table", "hwpx_paragraph", "raw_text"]


class EvidenceLocation(BaseModel):
    """Evidence의 원문 위치 정보.

    location_type 별로 채워지는 필드가 다름:
    - pdf_page: page (+ optional bbox)
    - hwpx_table: table_index (+ optional row)
    - hwpx_paragraph: paragraph_index
    - raw_text: 위치 정보 없음
    """

    location_type: LocationType
    page: int | None = None
    bbox: list[float] | None = None
    table_index: int | None = None
    row: int | None = None
    paragraph_index: int | None = None


class Evidence(BaseModel):
    """text + 위치 정보. EligibilityResult.evidence 컬럼에 JSONB로 저장.

    location=None 이면 위치 정보 없음 (raw_text fallback).
    """

    text: str
    location: EvidenceLocation | None = None


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
