"""비용 및 성능을 고려한 라우팅 결정 모듈."""

from datetime import datetime, timezone
from typing import Any

from app.extractor.learner.features import extract_features
from app.extractor.learner.predict import predict_path

PATH_COST = {
    "rule_based": 0.0,
    "text_llm": 0.001,   # gpt-4o-mini 평균
    "vision_llm": 0.010, # gpt-4o vision
}

def route(ann: Any) -> dict[str, Any]:
    """공고 데이터 → 최적 라우팅 경로 결정 및 메타데이터 산출."""
    features = extract_features(ann)
    result = predict_path(features)

    if result is None:
        return {
            "chosen_path": None,  # 모델 부재 시 기존 휴리스틱 분기로 결정됨
            "fallback_paths": ["rule_based", "text_llm", "vision_llm"],
            "cost_estimate_usd": 0.0,
            "decision_score": None,
            "features_used": features,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "fallback": "heuristic",
        }

    path, conf = result
    
    # 목표 스키마에 정의된 fallback_paths 구성
    if path == "rule_based":
        fallback_paths = ["text_llm", "vision_llm"]
    elif path == "text_llm":
        fallback_paths = ["vision_llm"]
    else:
        fallback_paths = []

    return {
        "chosen_path": path,
        "fallback_paths": fallback_paths,
        "decision_score": conf,
        "cost_estimate_usd": PATH_COST.get(path, 0.0),
        "features_used": features,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "fallback": None,
    }
