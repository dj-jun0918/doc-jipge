"""데이터 품질 리포트 Pydantic 스키마 정의 모듈."""

from datetime import datetime
from pydantic import BaseModel

class DuplicateSuspect(BaseModel):
    """중복 의심 공고 쌍 모델."""
    ann_a: str
    ann_b: str
    similarity: float

class QualityIssues(BaseModel):
    """카테고리별 품질 이슈 목록 모델."""
    empty_title: list[str]
    short_target_text: list[str]
    no_attachments: list[str]
    download_failed: list[str]
    conversion_failed: list[str]
    extraction_failed: list[str]
    duplicate_suspected: list[DuplicateSuspect]

class QualityReport(BaseModel):
    """품질 진단 리포트 응답 모델."""
    total: int
    issues: QualityIssues
    checked_at: datetime
