import uuid
from typing import Literal

from pydantic import BaseModel, model_validator


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
    문자열 입력은 자동으로 {"text": <str>, "location": None} 로 변환 (구 형식 호환).
    """

    text: str
    location: EvidenceLocation | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_from_string(cls, v):
        if isinstance(v, str):
            return {"text": v, "location": None}
        # JSONB null 백필 데이터 ({"text": null}) 방어 — text는 빈 문자열로
        if isinstance(v, dict) and v.get("text") is None:
            return {**v, "text": ""}
        return v


class ParsedCondition(BaseModel):
    value: float | str | dict | None = None
    operator: str | None = None
    raw_text: str


class EligibilityField(BaseModel):
    field_name: str
    condition: ParsedCondition
    exception: str | None = None
    evidence: Evidence
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
    evidence: Evidence | None = None
    evidence_source: str | None = None
    processing_path: str

    model_config = {"from_attributes": True}


class EligibilityFieldResponse(BaseModel):
    """API 응답용 — id/announcement_id 제외 (URL path에 포함됨)."""

    field_name: str
    condition_value: str
    condition_parsed: dict | None = None
    evidence: Evidence | None = None
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
