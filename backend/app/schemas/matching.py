"""매칭 API 응답 스키마.

`app/schemas/match_result.py`의 `MatchResultResponse`는 ORM mirror용(UUID 포함).
API 응답에서는 URL path에 ID가 들어가므로 필드 레벨 정보만 노출한다.
"""
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.eligibility import Evidence

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
    evidence: Evidence | None = None
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
    match_score: float | None = None  # 공고 단위 총점 (0~1) — 매칭 목록과 동일 공식
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


class SimulateOverrides(BaseModel):
    """What-if 시뮬레이션 — 회사 프로필 임시 변경값. 허용 필드만, unknown 차단."""

    model_config = {"extra": "forbid"}

    revenue: int | None = None
    employee_count: int | None = None
    founded_date: date | None = None
    region: str | None = None
    industry: str | None = None
    ceo_birth_date: date | None = None
    certifications: dict[str, bool] | None = None


class SimulateRequest(BaseModel):
    """POST /api/matching/{company_id}/simulate 입력."""

    announcement_id: uuid.UUID
    overrides: SimulateOverrides


class SimulateResponse(MatchResultDetailResponse):
    """시뮬레이션 응답 — 매칭 상세와 동일 형식 + simulated 플래그."""

    simulated: bool = True


class CounterfactualItem(BaseModel):
    """미충족 필드를 충족시키는 최소 프로필 변경 제안."""

    field_name: str
    current_value: str | None = None      # 현재 회사 값
    requirement: str | None = None        # 요구 조건 (raw_text)
    suggested_value: str                  # 충족시키는 제안 값(표시용)
    explanation: str                      # "매출 5억원 이상 필요 (현재 3억원)"
    changeable: bool = True               # 업종 제외/인증 미보유 등 현실적으로 바꾸기 어려우면 False


class CounterfactualRequest(BaseModel):
    """POST /api/matching/{company_id}/counterfactual 입력."""

    announcement_id: uuid.UUID


class CounterfactualResponse(BaseModel):
    """반사실 분석 응답 — 미충족 필드별 최소 변경 제안 + 달성 가능 여부."""

    company_id: uuid.UUID
    announcement_id: uuid.UUID
    unmet: list[CounterfactualItem]       # 미충족(hard) 필드별 반사실
    achievable: bool                      # changeable 변경 모두 적용 시 충족 가능?
    note: str | None = None               # 변경 불가 항목 안내 등
