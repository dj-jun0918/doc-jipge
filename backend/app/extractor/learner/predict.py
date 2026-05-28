"""학습된 모델 예측 및 경로 결정 모듈."""

from pathlib import Path
from typing import Any
import joblib

from app.extractor.learner.features import features_to_vector

_model = None
_MODEL_PATH = Path(__file__).parent / "model.pkl"

def _load_model() -> Any | None:
    """모델 로드 (캐싱 적용). 파일이 없거나 예외 발생 시 None 반환."""
    global _model
    if _model is None:
        try:
            if _MODEL_PATH.exists():
                _model = joblib.load(_MODEL_PATH)
        except Exception:
            _model = None
    return _model

def predict_path(features: dict[str, Any]) -> tuple[str, float] | None:
    """model.pkl 예측 실행. 실패 시 None을 반환하여 호출부에서 휴리스틱 fallback이 되도록 함."""
    model = _load_model()
    if model is None:
        return None
    
    try:
        X = [features_to_vector(features)]
        path = model.predict(X)[0]
        conf = max(model.predict_proba(X)[0])
        return str(path), float(conf)
    except Exception:
        return None
