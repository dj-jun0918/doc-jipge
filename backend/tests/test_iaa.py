"""iaa.py 모듈 단위 테스트."""

import pytest
from evaluation.iaa import calculate_iaa_for_field, calculate_overall_iaa


@pytest.fixture
def sample_labels():
    # 라벨러 A
    labels_a = [
        {
            "announcement_id": "ann_001",
            "title": "공고 1",
            "fields": [
                {"field_name": "업력", "value": 7, "operator": "이하"}
            ]
        },
        {
            "announcement_id": "ann_002",
            "title": "공고 2",
            "fields": [
                {"field_name": "지역", "value": ["서울"], "operator": "소재"}
            ]
        }
    ]
    
    # 라벨러 B (A와 동일)
    labels_b = [
        {
            "announcement_id": "ann_001",
            "title": "공고 1",
            "fields": [
                {"field_name": "업력", "value": 7, "operator": "이하"}
            ]
        },
        {
            "announcement_id": "ann_002",
            "title": "공고 2",
            "fields": [
                {"field_name": "지역", "value": ["서울"], "operator": "소재"}
            ]
        }
    ]
    
    return labels_a, labels_b


class TestIAA:

    def test_calculate_iaa_perfect_agreement(self, sample_labels):
        """두 라벨러가 완벽히 일치하는 경우 Cohen's κ는 1.0 이어야 함."""
        labels_a, labels_b = sample_labels
        
        kappa_age = calculate_iaa_for_field(labels_a, labels_b, "업력")
        assert kappa_age == 1.0

    def test_calculate_iaa_partial_agreement(self, sample_labels):
        """두 라벨러의 의견이 다를 경우 Cohen's κ 수치 계산."""
        labels_a, labels_b = sample_labels
        
        # 라벨러 B의 ann_001 값을 변경 (의견 불일치 유도)
        labels_b[0]["fields"][0]["value"] = 3
        
        kappa_age = calculate_iaa_for_field(labels_a, labels_b, "업력")
        # 불일치 유도로 kappa 점수가 1.0보다 작아졌는지 확인
        assert kappa_age < 1.0

    def test_calculate_overall_iaa(self, sample_labels):
        """종합 카파 합산 기능 검증."""
        labels_a, labels_b = sample_labels
        
        res = calculate_overall_iaa(labels_a, labels_b)
        assert "overall_kappa" in res
        assert "by_field" in res
        assert res["evaluated_count"] == 2
        assert isinstance(res["overall_kappa"], float)
