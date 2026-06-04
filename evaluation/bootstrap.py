"""Bootstrap 95% 신뢰구간(CI) 측정 모듈."""

from typing import List, Dict, Callable, Tuple
import numpy as np


def calc_precision(items: List[Dict[str, int]]) -> float:
    """공고 단위 결과 목록에서 Precision을 산출합니다."""
    tp_sum = sum(item.get("tp", 0) for item in items)
    fp_sum = sum(item.get("fp", 0) for item in items)
    denominator = tp_sum + fp_sum
    return tp_sum / denominator if denominator > 0 else 0.0


def calc_recall(items: List[Dict[str, int]]) -> float:
    """공고 단위 결과 목록에서 Recall을 산출합니다."""
    tp_sum = sum(item.get("tp", 0) for item in items)
    fn_sum = sum(item.get("fn", 0) for item in items)
    denominator = tp_sum + fn_sum
    return tp_sum / denominator if denominator > 0 else 0.0


def calc_f1(items: List[Dict[str, int]]) -> float:
    """공고 단위 결과 목록에서 F1-score를 산출합니다."""
    p = calc_precision(items)
    r = calc_recall(items)
    denominator = p + r
    return (2 * p * r) / denominator if denominator > 0 else 0.0


def bootstrap_ci(
    items: List[Dict[str, int]],
    metric_fn: Callable[[List[Dict[str, int]]], float],
    n_iter: int = 1000,
    ci: float = 0.95
) -> Tuple[float, float, float]:
    """공고 단위 평가 결과 목록에 대해 리샘플링을 수행하여 신뢰구간을 계산합니다.

    items: 각 공고별 {"tp": int, "fp": int, "fn": int} 결과 dict 리스트.
    metric_fn: items 리스트를 받아 특정 메트릭 수치(float)를 반환하는 함수 (예: calc_precision)
    n_iter: Resampling 반복 횟수 (기본 1000회)
    ci: 신뢰수준 (Confidence Interval, 기본 0.95)

    Returns:
        (point_estimate, ci_low, ci_high) 튜플
    """
    if not items:
        return 0.0, 0.0, 0.0
        
    point_estimate = metric_fn(items)
    samples = []
    n = len(items)
    indices = np.arange(n)
    
    # 빠른 통계 처리를 위한 난수 리샘플링 인덱스 루프 (재현성을 위해 시드 고정)
    rng = np.random.default_rng(seed=42)
    for _ in range(n_iter):
        resampled_indices = rng.choice(indices, size=n, replace=True)
        resampled_items = [items[idx] for idx in resampled_indices]
        samples.append(metric_fn(resampled_items))
        
    alpha = (1 - ci) / 2
    ci_low = float(np.percentile(samples, alpha * 100))
    ci_high = float(np.percentile(samples, (1 - alpha) * 100))
    
    return point_estimate, ci_low, ci_high


def calculate_metrics_ci(items: List[Dict[str, int]], n_iter: int = 1000) -> Dict[str, Dict[str, float]]:
    """Precision, Recall, F1에 대해 점추정치 및 95% 신뢰구간 하한/상한을 일괄 산출합니다."""
    p_point, p_low, p_high = bootstrap_ci(items, calc_precision, n_iter)
    r_point, r_low, r_high = bootstrap_ci(items, calc_recall, n_iter)
    f_point, f_low, f_high = bootstrap_ci(items, calc_f1, n_iter)
    
    return {
        "precision": {"point_estimate": p_point, "ci_low": p_low, "ci_high": p_high},
        "recall": {"point_estimate": r_point, "ci_low": r_low, "ci_high": r_high},
        "f1": {"point_estimate": f_point, "ci_low": f_low, "ci_high": f_high}
    }
