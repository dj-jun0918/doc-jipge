"""bootstrap.py 모듈 단위 테스트."""

import pytest
from evaluation.bootstrap import calc_precision, calc_recall, calc_f1, bootstrap_ci, calculate_metrics_ci


@pytest.fixture
def sample_metrics_data():
    # 5개의 공고 평가 결과 (tp, fp, fn 개수)
    return [
        {"tp": 4, "fp": 1, "fn": 1},
        {"tp": 3, "fp": 0, "fn": 2},
        {"tp": 5, "fp": 2, "fn": 0},
        {"tp": 2, "fp": 1, "fn": 1},
        {"tp": 4, "fp": 0, "fn": 1}
    ]


class TestBootstrap:

    def test_basic_calculations(self, sample_metrics_data):
        """Precision, Recall, F1 기본 연산의 수학적 검증."""
        p = calc_precision(sample_metrics_data)
        r = calc_recall(sample_metrics_data)
        f = calc_f1(sample_metrics_data)
        
        # tp_sum = 18, fp_sum = 4, fn_sum = 5
        # Precision = 18 / 22 = 0.8181...
        # Recall = 18 / 23 = 0.7826...
        assert abs(p - 0.818) < 0.01
        assert abs(r - 0.782) < 0.01
        assert f > 0.0
        assert f == (2 * p * r) / (p + r)

    def test_bootstrap_ci_bounds(self, sample_metrics_data):
        """Bootstrap CI 하한/상한의 수학적 정합성 검증."""
        point, low, high = bootstrap_ci(sample_metrics_data, calc_precision, n_iter=200)
        
        assert 0.0 <= low <= point <= high <= 1.0

    def test_calculate_metrics_ci(self, sample_metrics_data):
        """일괄 신뢰구간 산출 구조 검증."""
        res = calculate_metrics_ci(sample_metrics_data, n_iter=100)
        
        for metric in ["precision", "recall", "f1"]:
            assert metric in res
            m_res = res[metric]
            assert "point_estimate" in m_res
            assert "ci_low" in m_res
            assert "ci_high" in m_res
            assert m_res["ci_low"] <= m_res["point_estimate"] <= m_res["ci_high"]
