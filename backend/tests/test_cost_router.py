"""test_cost_router.py — cost_router 및 특성 추출 단위 테스트."""

import pytest
from unittest.mock import MagicMock, patch

from app.extractor.learner.features import extract_features, features_to_vector
from app.extractor.learner.predict import predict_path
from app.extractor import cost_router

class MockAnnouncement:
    def __init__(self, title, target_text, exclusion_text, attachments, structured_tables):
        self.title = title
        self.target_text = target_text
        self.exclusion_text = exclusion_text
        self.attachments = attachments
        self.structured_tables = structured_tables

def test_extract_features_orm():
    # 1. ORM 객체와 유사한 Mock 객체로 테스트
    mock_att = MagicMock()
    mock_att.file_type = "pdf"
    
    ann = MockAnnouncement(
        title="[공고] 2026 청년 창업 지원사업",
        target_text="창업 3년 이내의 중소기업 대표자 표 참조",
        exclusion_text="세금 체납자 제외",
        attachments=[mock_att],
        structured_tables=[{"col1": "val1"}]
    )
    
    features = extract_features(ann)
    
    assert features["text_length"] == len(ann.target_text)
    assert features["exclusion_length"] == len(ann.exclusion_text)
    assert features["has_attachments"] is True
    assert features["attachment_count"] == 1
    assert features["has_pdf"] is True
    assert features["has_hwpx"] is False
    assert features["structured_tables_count"] == 1
    assert features["has_table_keyword"] == 1
    assert features["title_length"] == len(ann.title)

def test_extract_features_dict():
    # 2. dict 형태로 테스트
    ann_dict = {
        "title": "테스트 공고",
        "target_text": "텍스트 요건",
        "exclusion_text": "",
        "attachments": [{"file_type": "hwpx"}],
        "structured_tables": []
    }
    
    features = extract_features(ann_dict)
    
    assert features["text_length"] == len("텍스트 요건")
    assert features["exclusion_length"] == 0
    assert features["has_attachments"] is True
    assert features["attachment_count"] == 1
    assert features["has_pdf"] is False
    assert features["has_hwpx"] is True
    assert features["structured_tables_count"] == 0
    assert features["has_table_keyword"] == 0

def test_features_to_vector():
    features = {
        "title_length": 10,
        "text_length": 100,
        "exclusion_length": 5,
        "has_attachments": True,
        "attachment_count": 2,
        "has_hwpx": False,
        "has_pdf": True,
        "structured_tables_count": 0,
        "has_table_keyword": 1
    }
    
    vector = features_to_vector(features)
    assert len(vector) == len(features)
    
    # keys가 알파벳 오름차순 정렬인지 확인
    sorted_keys = sorted(features.keys())
    for idx, key in enumerate(sorted_keys):
        assert vector[idx] == float(features[key])

def test_predict_path_no_model():
    # model.pkl이 로드되지 않는(부재) 상황 테스트
    with patch("app.extractor.learner.predict._load_model", return_value=None):
        features = {
            "title_length": 10, "text_length": 100, "exclusion_length": 5,
            "has_attachments": True, "attachment_count": 2, "has_hwpx": False,
            "has_pdf": True, "structured_tables_count": 0, "has_table_keyword": 1
        }
        res = predict_path(features)
        assert res is None

def test_cost_router_route_fallback():
    # 모델 예측 실패시 heuristic fallback 형태 반환 테스트
    ann_dict = {"title": "fallback 테스트", "target_text": "본문"}
    
    with patch("app.extractor.cost_router.predict_path", return_value=None):
        routing_meta = cost_router.route(ann_dict)
        assert routing_meta["chosen_path"] is None
        assert routing_meta["fallback"] == "heuristic"
        assert "fallback_paths" in routing_meta
        assert routing_meta["cost_estimate_usd"] == 0.0

def test_cost_router_route_with_model():
    # 모델 예측 성공시 정보 정합성 테스트
    ann_dict = {"title": "예측 테스트", "target_text": "본문"}
    
    with patch("app.extractor.cost_router.predict_path", return_value=("text_llm", 0.85)):
        routing_meta = cost_router.route(ann_dict)
        assert routing_meta["chosen_path"] == "text_llm"
        assert routing_meta["decision_score"] == 0.85
        assert routing_meta["cost_estimate_usd"] == 0.001
        assert routing_meta["fallback_paths"] == ["vision_llm"]
        assert "decided_at" in routing_meta
        assert routing_meta["fallback"] is None
