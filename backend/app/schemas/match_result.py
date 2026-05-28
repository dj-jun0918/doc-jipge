import uuid
from typing import Literal

from pydantic import BaseModel


class MatchResultResponse(BaseModel):
    id: uuid.UUID
    announcement_id: uuid.UUID
    company_id: uuid.UUID
    field_name: str
    status: Literal["충족", "미충족", "확인필요", "해당없음"]
    score: float | None = None              # 필드별 score 0~1 (1=충족, 0~0.5=미충족 거리 기반, 0.3=확인필요, None=해당없음)
    distance: float | None = None           # 미충족 수치 필드의 정규화 거리 (조건값 대비 차이 비율)
    constraint_type: Literal["hard", "soft"] | None = None
    company_value: str | None = None
    requirement_value: str | None = None
    evidence: str | None = None
    processing_path: str

    model_config = {"from_attributes": True}


class MatchSummaryResponse(BaseModel):
    announcement_id: uuid.UUID
    announcement_title: str
    results: list[MatchResultResponse]
