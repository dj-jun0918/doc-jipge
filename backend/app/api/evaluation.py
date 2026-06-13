"""평가 프레임워크 API 컨트롤러 모듈."""

import os
import json
import sys
from pathlib import Path

# Add repository root to sys.path to allow importing from the evaluation module
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from fastapi import APIRouter, HTTPException
from app.schemas.evaluation import (
    EvaluationMetricsResponse,
    AblationResponse,
    IaaResponse,
    BootstrapResponse,
    ErrorAnalysisResponse
)
from evaluation.iaa import calculate_overall_iaa, load_labels_from_dir
from evaluation.bootstrap import calculate_metrics_ci

router = APIRouter()

RESULTS_DIR = REPO_ROOT / "evaluation" / "results"
GT_DIR = REPO_ROOT / "evaluation" / "ground_truth"


def _load_json_data(filename: str) -> dict:
    """evaluation/results 디렉토리에서 JSON 결과를 로드합니다."""
    path = RESULTS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.get("/metrics", response_model=EvaluationMetricsResponse)
def get_evaluation_metrics() -> dict:
    """종합 평가 메트릭 조회 API."""
    data = _load_json_data("pr6_measurement_general.json")
    if not data:
        # 실측 결과 파일이 없으면 가짜 숫자 대신 명시적 404 — 측정 공개 원칙
        raise HTTPException(status_code=404, detail="측정 결과 파일이 없습니다. evaluation/measure.py를 먼저 실행하세요.")


    # 데이터 매핑 조립
    overall = data.get("overall", {})
    by_field = {}
    
    # 기본 영문 키들 빈 값으로 미리 구성
    default_keys = ["age", "location", "company_scale", "is_small_business", "certification"]
    for k in default_keys:
        by_field[k] = {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    field_map = {
        "나이": "age",
        "지역": "location",
        "업력": "company_scale",
        "업종": "is_small_business",
        "인증": "certification",
        "종업원 수": "employee_count",
        "매출": "revenue"
    }

    for f, metrics in data.get("fields", {}).items():
        en_key = field_map.get(f, f)
        by_field[en_key] = {
            "precision": metrics.get("precision", 0.0),
            "recall": metrics.get("recall", 0.0),
            "f1": metrics.get("f1", 0.0)
        }
        
    by_path = {}
    for p, metrics in data.get("processing_paths", {}).items():
        by_path[p] = {
            "precision": metrics.get("precision", 0.0),
            "recall": metrics.get("recall", 0.0),
            "f1": metrics.get("f1", 0.0),
            "count": metrics.get("count", 0),
            "cost_usd": metrics.get("cost_usd", 0.0)
        }
        
    return {
        "overall": {
            "precision": overall.get("precision", 0.0),
            "recall": overall.get("recall", 0.0),
            "f1": overall.get("f1", 0.0)
        },
        "by_field": by_field,
        "by_path": by_path,
        "total_cost_usd": data.get("total_cost_usd", 0.0)
    }


@router.get("/ablation", response_model=AblationResponse)
def get_ablation_results() -> dict:
    """Component-wise Ablation 실험 결과 조회 API."""
    conditions = []
    
    ablation_names = {
        "C1": "Rule Parser Baseline",
        "C2": "Rule + Text LLM",
        "C3": "Rule + Text + Vision LLM",
        "C4": "Hybrid Engine with Verifier"
    }
    ablation_components = {
        "C1": ["rule_parser"],
        "C2": ["rule_parser", "text_llm_extractor"],
        "C3": ["rule_parser", "text_llm_extractor", "vision_llm_extractor"],
        "C4": ["rule_parser", "text_llm_extractor", "vision_llm_extractor", "fact_verifier"]
    }
    
    for c in ["C1", "C2", "C3", "C4"]:
        data = _load_json_data(f"ablation_{c}.json")
        if data:
            conditions.append({
                "condition_id": c,
                "name": ablation_names.get(c, f"Condition {c}"),
                "components": ablation_components.get(c, list(data.get("config", {}).keys())),
                "description": f"Ablation 실험 조건 {c}",
                "metrics": data.get("metrics", {"precision": 0.0, "recall": 0.0, "f1": 0.0}),
                "cost_estimate_usd": data.get("cost_usd", 0.0)
            })
            
    # ablation 실측 파일이 없으면 빈 목록 — 창작 숫자를 서빙하지 않는다 (측정 공개 원칙)
    return {"conditions": conditions}



@router.get("/iaa", response_model=IaaResponse)
def get_iaa_results() -> dict:
    """라벨러 합의도 (IAA - Cohen's κ) 조회 API."""
    # 방정우 님과 임태규 님의 라벨 디렉토리 설정
    dir_a = REPO_ROOT / "evaluation" / "cross_labels" / "eisenberg"
    dir_b = REPO_ROOT / "evaluation" / "cross_labels" / "bangjeongwoo"
    
    if dir_a.exists() and dir_b.exists():
        labels_a = load_labels_from_dir(str(dir_a))
        labels_b = load_labels_from_dir(str(dir_b))
        if labels_a and labels_b:
            res = calculate_overall_iaa(labels_a, labels_b)
            by_field_scores = []
            for f, k in res["by_field"].items():
                lvl = "상당한 합의 (Substantial)"
                if k >= 0.8:
                    lvl = "거의 완전한 합의 (Almost Perfect)"
                elif k < 0.6:
                    lvl = "보통 수준의 합의 (Moderate)"
                by_field_scores.append({
                    "field_name": f,
                    "kappa": k,
                    "agreement_level": lvl
                })
            return {
                "overall_kappa": res["overall_kappa"],
                "by_field": by_field_scores,
                "evaluated_count": res["evaluated_count"]
            }
    # cross_labels 데이터가 존재하지 않을 경우 빈 값 반환
    return {
        "overall_kappa": 0.0,
        "by_field": [],
        "evaluated_count": 0
    }


@router.get("/bootstrap", response_model=BootstrapResponse)
def get_bootstrap_ci() -> dict:
    """Bootstrap 95% 신뢰구간 조회 API."""
    data = _load_json_data("pr6_measurement_general.json")
    if data and "announcements" in data:
        items = []
        for ann_id, res in data["announcements"].items():
            counts = res.get("counts", {})
            items.append({
                "tp": counts.get("tp", 0),
                "fp": counts.get("fp", 0),
                "fn": counts.get("fn", 0)
            })
            
        if items:
            ci_res = calculate_metrics_ci(items, n_iter=1000)
            return {
                "precision": ci_res["precision"],
                "recall": ci_res["recall"],
                "f1": ci_res["f1"],
                "resampling_iterations": 1000
            }
            
    # 실측 결과 파일이 없으면 가짜 CI 대신 명시적 404 — 측정 공개 원칙
    raise HTTPException(status_code=404, detail="측정 결과 파일이 없습니다. evaluation/measure.py를 먼저 실행하세요.")


@router.get("/errors", response_model=ErrorAnalysisResponse)
def get_error_patterns() -> dict:
    """주요 오답 패턴(Error Taxonomy) 분석 데이터 조회 API."""
    data = _load_json_data("pr6_measurement_general.json")
    
    # 기본 3개 오답 패턴 초기 정의
    patterns_map = {
        "누락 (False Negative)": {
            "pattern_name": "누락 (False Negative)",
            "count": 0,
            "ratio": 0.0,
            "description": "공고문 본문 내의 우대사항 또는 예외 조건 텍스트를 파이프라인이 누락하여 추출하지 못한 오류",
            "examples": []
        },
        "과탐지 (False Positive)": {
            "pattern_name": "과탐지 (False Positive)",
            "count": 0,
            "ratio": 0.0,
            "description": "단순 설명 텍스트나 예시를 실제 필수 자격요건으로 과장 해석하여 불필요하게 추출한 오류",
            "examples": []
        },
        "값 매칭 오류 (Value Mismatch)": {
            "pattern_name": "값 매칭 오류 (Value Mismatch)",
            "count": 0,
            "ratio": 0.0,
            "description": "자격요건 항목은 올바르게 식별하였으나 수치/연산자 파싱에서 발생한 값 불일치 오류",
            "examples": []
        }
    }
    
    total_errors = 0
    if data and "mismatches" in data:
        mismatches = data["mismatches"]
        total_errors = len(mismatches)
        
        for m in mismatches:
            raw_type = m.get("type", "")
            key = "누락 (False Negative)"
            if "FP" in raw_type or "과추출" in raw_type:
                key = "과탐지 (False Positive)"
            elif "값" in raw_type or "오인식" in raw_type or "mismatch" in raw_type.lower():
                key = "값 매칭 오류 (Value Mismatch)"
                
            patterns_map[key]["count"] += 1
            if len(patterns_map[key]["examples"]) < 3:
                patterns_map[key]["examples"].append({
                    "announcement_id": m.get("announcement_id", "N/A"),
                    "title": "공고문 자격 검증 사례",
                    "field_name": "age" if m.get("field_name") == "나이" else m.get("field_name", "N/A"),
                    "ground_truth": m.get("target", "N/A"),
                    "prediction": m.get("condition", "N/A")
                })
                
        for key in patterns_map:
            if total_errors > 0:
                patterns_map[key]["ratio"] = patterns_map[key]["count"] / total_errors

    # 실측 데이터만 반환한다 — 결과 파일이 없거나 해당 패턴 사례가 없으면 빈 값이 정상.
    return {
        "total_errors": total_errors,
        "patterns": list(patterns_map.values())
    }

