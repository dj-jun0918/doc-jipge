"""평가 프레임워크 API 컨트롤러 모듈."""

from fastapi import APIRouter
from app.schemas.evaluation import (
    EvaluationMetricsResponse,
    AblationResponse,
    IaaResponse,
    BootstrapResponse,
    ErrorAnalysisResponse,
    MetricItem,
    PathMetricItem,
    AblationConditionItem,
    IaaFieldScore,
    BootstrapMetricCi,
    ErrorPatternItem,
    ErrorCaseExample
)

router = APIRouter()


@router.get("/metrics", response_model=EvaluationMetricsResponse)
def get_evaluation_metrics() -> dict:
    """종합 평가 메트릭 조회 API.

    전체 정밀도/재현율/F1, 개별 필드별 성능 지표, 그리고 하이브리드 라우팅 경로별 성능과 
    비용 통계를 일괄 제공하여 대시보드 화면 구성을 돕습니다.
    """
    # 임시 Mock 데이터 정의
    return {
        "overall": {
            "precision": 0.885,
            "recall": 0.852,
            "f1": 0.868
        },
        "by_field": {
            "age": {"precision": 0.921, "recall": 0.895, "f1": 0.908},
            "location": {"precision": 0.943, "recall": 0.912, "f1": 0.927},
            "company_scale": {"precision": 0.875, "recall": 0.844, "f1": 0.859},
            "is_small_business": {"precision": 0.950, "recall": 0.931, "f1": 0.940},
            "constraint": {"precision": 0.812, "recall": 0.785, "f1": 0.798},
            "certification": {"precision": 0.856, "recall": 0.810, "f1": 0.832}
        },
        "by_path": {
            "rule_based": {
                "precision": 0.985,
                "recall": 0.712,
                "f1": 0.827,
                "count": 15,
                "cost_usd": 0.0
            },
            "text_llm": {
                "precision": 0.892,
                "recall": 0.861,
                "f1": 0.876,
                "count": 25,
                "cost_usd": 12.45
            },
            "vision_llm": {
                "precision": 0.824,
                "recall": 0.805,
                "f1": 0.814,
                "count": 10,
                "cost_usd": 28.60
            }
        },
        "total_cost_usd": 41.05
    }


@router.get("/ablation", response_model=AblationResponse)
def get_ablation_results() -> dict:
    """Component-wise Ablation 실험 결과 조회 API.

    C1(규칙 baseline)부터 C4(최종 하이브리드+검증기 시스템)까지의 4가지 파이프라인
    구성 조건에 따른 성능 격차와 추정 소요 비용의 오프셋을 비교합니다.
    """
    return {
        "conditions": [
            {
                "condition_id": "C1",
                "name": "Rule Parser Baseline",
                "components": ["rule_parser"],
                "description": "정규표현식 및 하드코딩 룰 기반 파싱. 정밀도는 높으나 재현율이 극히 낮음.",
                "metrics": {"precision": 0.985, "recall": 0.354, "f1": 0.521},
                "cost_estimate_usd": 0.0
            },
            {
                "condition_id": "C2",
                "name": "Rule + Text LLM",
                "components": ["rule_parser", "text_llm_extractor"],
                "description": "본문 텍스트 추출에 LLM을 결합하여 정형 규칙이 놓친 자격 요건 식별.",
                "metrics": {"precision": 0.902, "recall": 0.815, "f1": 0.856},
                "cost_estimate_usd": 15.50
            },
            {
                "condition_id": "C3",
                "name": "Rule + Text + Vision LLM",
                "components": ["rule_parser", "text_llm_extractor", "vision_llm_extractor"],
                "description": "공고문 내 표 이미지나 외부 이미지 박스 내 자격요건까지 Vision LLM으로 다각화 파싱.",
                "metrics": {"precision": 0.885, "recall": 0.852, "f1": 0.868},
                "cost_estimate_usd": 41.05
            },
            {
                "condition_id": "C4",
                "name": "Hybrid Engine with Verifier",
                "components": ["rule_parser", "text_llm_extractor", "vision_llm_extractor", "fact_verifier"],
                "description": "모든 오추출 및 불일치 항목을 교차 검증하는 Verifier 모듈이 포함된 완성형 파이프라인.",
                "metrics": {"precision": 0.923, "recall": 0.864, "f1": 0.893},
                "cost_estimate_usd": 48.20
            }
        ]
    }


@router.get("/iaa", response_model=IaaResponse)
def get_iaa_results() -> dict:
    """라벨러 합의도 (IAA - Cohen's κ) 조회 API.

    독립된 두 작업자(임태규, 방정우)가 교차 라벨링한 10건의 공고 결과를 바탕으로
    필드별 일치 강도를 도출하여 전체 GT셋 구축 과정의 객관적 신뢰도를 판단합니다.
    """
    return {
        "overall_kappa": 0.765,
        "by_field": [
            {"field_name": "age", "kappa": 0.842, "agreement_level": "거의 완전한 합의 (Almost Perfect)"},
            {"field_name": "location", "kappa": 0.889, "agreement_level": "거의 완전한 합의 (Almost Perfect)"},
            {"field_name": "company_scale", "kappa": 0.723, "agreement_level": "상당한 합의 (Substantial)"},
            {"field_name": "is_small_business", "kappa": 0.910, "agreement_level": "거의 완전한 합의 (Almost Perfect)"},
            {"field_name": "constraint", "kappa": 0.584, "agreement_level": "보통 수준의 합의 (Moderate)"},
            {"field_name": "certification", "kappa": 0.645, "agreement_level": "상당한 합의 (Substantial)"}
        ],
        "evaluated_count": 10
    }


@router.get("/bootstrap", response_model=BootstrapResponse)
def get_bootstrap_ci() -> dict:
    """Bootstrap 95% 신뢰구간 조회 API.

    1,000회 리샘플링을 거쳐 Precision, Recall, F1 지표의 통계적 95% 신뢰 하한/상한을
    도출함으로써 한정된 GT 풀 환경 내에서 성능 보고의 통계적 유의성을 보장합니다.
    """
    return {
        "precision": {
            "point_estimate": 0.885,
            "ci_low": 0.832,
            "ci_high": 0.927
        },
        "recall": {
            "point_estimate": 0.852,
            "ci_low": 0.798,
            "ci_high": 0.899
        },
        "f1": {
            "point_estimate": 0.868,
            "ci_low": 0.817,
            "ci_high": 0.911
        },
        "resampling_iterations": 1000
    }


@router.get("/errors", response_model=ErrorAnalysisResponse)
def get_error_patterns() -> dict:
    """주요 오답 패턴(Error Taxonomy) 분석 데이터 조회 API.

    시스템이 정답(GT)과 다르게 예측한 케이스들을 오답 유형별로 군집화하고, 
    각 유형별 통계량과 대표적인 불일치 예시 데이터를 반환합니다.
    """
    return {
        "total_errors": 28,
        "patterns": [
            {
                "pattern_name": "누락 (False Negative)",
                "count": 15,
                "ratio": 0.536,
                "description": "공고문 본문 내의 우대사항 또는 예외 조건 텍스트를 파이프라인이 누락하여 추출하지 못한 오류",
                "examples": [
                    {
                        "announcement_id": "ann_005",
                        "title": "2026년 청년창업지원사업 공고",
                        "field_name": "age",
                        "ground_truth": {"value": 39, "operator": "이하"},
                        "prediction": None
                    },
                    {
                        "announcement_id": "ann_012",
                        "title": "글로벌 강소기업 육성사업 모집",
                        "field_name": "certification",
                        "ground_truth": {"cert_keys": ["GLOBAL_CHAMPION"]},
                        "prediction": None
                    }
                ]
            },
            {
                "pattern_name": "과탐지 (False Positive)",
                "count": 8,
                "ratio": 0.286,
                "description": "단순 설명 텍스트나 예시를 실제 필수 자격요건으로 과장 해석하여 불필요하게 추출한 오류",
                "examples": [
                    {
                        "announcement_id": "ann_008",
                        "title": "소상공인 스마트 설비 보급사업",
                        "field_name": "constraint",
                        "ground_truth": None,
                        "prediction": {"value": "폐업 이력이 없는 자", "operator": "equal"}
                    }
                ]
            },
            {
                "pattern_name": "값/범위 오인식 (Value Mismatch)",
                "count": 5,
                "ratio": 0.178,
                "description": "자격조건은 식별하였으나 연산자(이상/초과/이하) 또는 수치를 잘못 파싱한 오류",
                "examples": [
                    {
                        "announcement_id": "ann_019",
                        "title": "스타트업 특허 디딤돌 지원사업",
                        "field_name": "company_scale",
                        "ground_truth": {"value": 7, "operator": "이하", "unit": "년"},
                        "prediction": {"value": 7, "operator": "미만", "unit": "년"}
                    }
                ]
            }
        ]
    }
