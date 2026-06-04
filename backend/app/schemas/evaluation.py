"""평가 프레임워크 API 응답을 위한 Pydantic 스키마 정의 모듈."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ----------------------------------------
# 1. 공통 / 메트릭 스키마
# ----------------------------------------

class MetricItem(BaseModel):
    """정밀도, 재현율, F1-score를 담는 기본 모델."""
    precision: float = Field(..., description="정밀도 (Precision)")
    recall: float = Field(..., description="재현율 (Recall)")
    f1: float = Field(..., description="F1-Score")


class PathMetricItem(BaseModel):
    """라우팅 경로별 메트릭 및 비용 모델."""
    precision: float = Field(..., description="정밀도")
    recall: float = Field(..., description="재현율")
    f1: float = Field(..., description="F1-Score")
    count: int = Field(..., description="해당 경로로 라우팅된 공고 수")
    cost_usd: float = Field(..., description="누적 발생 비용 (USD)")


class EvaluationMetricsResponse(BaseModel):
    """종합 메트릭 응답 모델."""
    overall: MetricItem = Field(..., description="전체 종합 메트릭")
    by_field: Dict[str, MetricItem] = Field(
        ...,
        description="필드별 메트릭 (예: age, location, company_scale, is_small_business, constraint, certification 등)"
    )
    by_path: Dict[str, PathMetricItem] = Field(
        ...,
        description="라우팅 경로별 메트릭 (rule_based, text_llm, vision_llm 등)"
    )
    total_cost_usd: float = Field(..., description="전체 누적 비용 (USD)")


# ----------------------------------------
# 2. Ablation 스키마
# ----------------------------------------

class AblationConditionItem(BaseModel):
    """Ablation 각 조건의 구성 정보 및 결과 모델."""
    condition_id: str = Field(..., description="조건 ID (C1, C2, C3, C4 등)")
    name: str = Field(..., description="조건명")
    components: List[str] = Field(..., description="사용된 컴포넌트 목록")
    description: str = Field(..., description="조건 및 목적 설명")
    metrics: MetricItem = Field(..., description="해당 조건에서의 메트릭 수치")
    cost_estimate_usd: float = Field(..., description="해당 조건에서의 추정 총 비용 (USD)")


class AblationResponse(BaseModel):
    """Ablation 비교 응답 모델."""
    conditions: List[AblationConditionItem] = Field(..., description="Ablation 조건별 결과 목록")


# ----------------------------------------
# 3. IAA 스키마
# ----------------------------------------

class IaaFieldScore(BaseModel):
    """필드별 Cohen's κ 점수 및 평가 모델."""
    field_name: str = Field(..., description="필드명 (한글/영문)")
    kappa: float = Field(..., description="Cohen's kappa 점수")
    agreement_level: str = Field(..., description="합의도 수준 (예: 거의 일치, 상당한 일치, 보통 등)")


class IaaResponse(BaseModel):
    """라벨러 간 합의도(IAA) 응답 모델."""
    overall_kappa: float = Field(..., description="종합 Cohen's kappa 점수")
    by_field: List[IaaFieldScore] = Field(..., description="필드별 합의도 분석 결과")
    evaluated_count: int = Field(..., description="합의도 평가에 사용된 교차 라벨링 공고 수")


# ----------------------------------------
# 4. Bootstrap 스키마
# ----------------------------------------

class BootstrapMetricCi(BaseModel):
    """개별 메트릭의 Bootstrap 점추정치 및 95% 신뢰구간 모델."""
    point_estimate: float = Field(..., description="점추정치 (Point Estimate)")
    ci_low: float = Field(..., description="95% 신뢰구간 하한 (Confidence Interval Low)")
    ci_high: float = Field(..., description="95% 신뢰구간 상한 (Confidence Interval High)")


class BootstrapResponse(BaseModel):
    """Bootstrap 95% CI 응답 모델."""
    precision: BootstrapMetricCi = Field(..., description="정밀도 신뢰구간")
    recall: BootstrapMetricCi = Field(..., description="재현율 신뢰구간")
    f1: BootstrapMetricCi = Field(..., description="F1-score 신뢰구간")
    resampling_iterations: int = Field(..., description="반복 Resampling 횟수 (기본 1000회)")


# ----------------------------------------
# 5. Error 분석 스키마
# ----------------------------------------

class ErrorCaseExample(BaseModel):
    """대표 오답 사례 모델."""
    announcement_id: str = Field(..., description="공고 ID")
    title: str = Field(..., description="공고명")
    field_name: str = Field(..., description="오류 발생 필드명")
    ground_truth: Any = Field(..., description="실제 정답 (GT)")
    prediction: Any = Field(..., description="시스템 예측값 (Pred)")


class ErrorPatternItem(BaseModel):
    """오답 패턴 정보 모델."""
    pattern_name: str = Field(..., description="오류 패턴 유형명 (예: 누락(FN), 과탐지(FP), 값 매칭 오류 등)")
    count: int = Field(..., description="발생 건수")
    ratio: float = Field(..., description="전체 오류 중 비율 (0.0 ~ 1.0)")
    description: str = Field(..., description="패턴 세부 설명")
    examples: List[ErrorCaseExample] = Field(..., description="대표 오답 예시 리스트")


class ErrorAnalysisResponse(BaseModel):
    """오답 패턴 분석 응답 모델."""
    total_errors: int = Field(..., description="분석된 총 오답 필드 건수")
    patterns: List[ErrorPatternItem] = Field(..., description="오답 패턴 분석 목록")
