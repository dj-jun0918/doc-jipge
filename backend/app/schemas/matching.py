"""매칭 API 응답 스키마.

`app/schemas/match_result.py`의 `MatchResultResponse`는 ORM mirror용(UUID 포함).
API 응답에서는 URL path에 ID가 들어가므로 필드 레벨 정보만 노출한다.
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MatchStatus = Literal["충족", "미충족", "확인필요", "해당없음"]


class MatchResultItem(BaseModel):
    """필드 단위 매칭 결과 (회사별 매칭 결과 페이지의 카드 1장)."""

    field_name: str
    status: MatchStatus
    score: float | None = None              # 필드별 score 0~1
    distance: float | None = None           # 미충족 수치 필드의 정규화 거리
    constraint_type: Literal["hard", "soft"] | None = None
    company_value: str | None = None
    requirement_value: str | None = None
    evidence: str | None = None
    processing_path: str


class MatchResultStats(BaseModel):
    """매칭 결과 상태별 집계."""

    충족: int = 0
    미충족: int = 0
    확인필요: int = 0
    해당없음: int = 0


class MatchResultDetailResponse(BaseModel):
    """GET /api/matching/{company_id}/{announcement_id} 응답."""

    company_id: uuid.UUID
    announcement_id: uuid.UUID
    items: list[MatchResultItem]
    stats: MatchResultStats
    matched_at: datetime | None = None


class CompanyMatchSummary(BaseModel):
    """GET /api/matching/{company_id} 리스트 아이템 (TOP 정렬용)."""

    announcement_id: uuid.UUID
    title: str
    match_score: float
    fulfilled_count: int
    total_fields: int


class CompanyMatchListResponse(BaseModel):
    """GET /api/matching/{company_id} 응답."""

    company_id: uuid.UUID
    items: list[CompanyMatchSummary]
    total: int


class TriggerResponse(BaseModel):
    """비동기 태스크 트리거 응답."""

    task_id: str
    message: str
