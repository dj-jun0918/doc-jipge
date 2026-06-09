"""평가 API 통합 테스트.

- TestClient를 사용한 5종 엔드포인트 호출 및 응답 스키마 정합성 검증
"""

import pytest


class TestEvaluationAPI:

    def test_get_metrics(self, client):
        """GET /api/evaluation/metrics API 호출 및 스키마 검증."""
        response = client.get("/api/evaluation/metrics")
        assert response.status_code == 200
        
        body = response.json()
        
        # 1. overall 필드 검증
        assert "overall" in body
        assert "precision" in body["overall"]
        assert "recall" in body["overall"]
        assert "f1" in body["overall"]
        assert isinstance(body["overall"]["precision"], float)
        
        # 2. by_field 필드 검증
        assert "by_field" in body
        assert "age" in body["by_field"]
        assert "location" in body["by_field"]
        assert "f1" in body["by_field"]["age"]
        
        # 3. by_path 필드 검증
        assert "by_path" in body
        assert "rule_based" in body["by_path"]
        assert "text_llm" in body["by_path"]
        assert "vision_llm" in body["by_path"]
        assert body["by_path"]["text_llm"]["count"] >= 0
        assert isinstance(body["by_path"]["text_llm"]["cost_usd"], float)
        
        # 4. total_cost_usd 검증
        assert "total_cost_usd" in body
        assert isinstance(body["total_cost_usd"], float)

    def test_get_ablation(self, client):
        """GET /api/evaluation/ablation API 호출 및 스키마 검증."""
        response = client.get("/api/evaluation/ablation")
        assert response.status_code == 200
        
        body = response.json()
        
        assert "conditions" in body
        assert isinstance(body["conditions"], list)
        assert len(body["conditions"]) == 4
        
        # C1 조건 세부 검증
        c1 = body["conditions"][0]
        assert c1["condition_id"] == "C1"
        assert c1["name"] == "Rule Parser Baseline"
        assert "rule_parser" in c1["components"]
        assert "metrics" in c1
        assert c1["metrics"]["precision"] == 0.985
        assert c1["cost_estimate_usd"] == 0.0

    def test_get_iaa(self, client):
        """GET /api/evaluation/iaa API 호출 및 스키마 검증."""
        response = client.get("/api/evaluation/iaa")
        assert response.status_code == 200
        
        body = response.json()
        
        assert "overall_kappa" in body
        assert isinstance(body["overall_kappa"], float)
        
        assert "by_field" in body
        assert isinstance(body["by_field"], list)
        assert "evaluated_count" in body
        assert isinstance(body["evaluated_count"], int)

        # cross_labels 데이터가 있을 때만 필드 상세 검증 (없으면 빈 값 반환이 정상)
        if body["by_field"]:
            field = body["by_field"][0]
            assert "field_name" in field
            assert isinstance(field["kappa"], float)
            assert "agreement_level" in field

    def test_get_bootstrap(self, client):
        """GET /api/evaluation/bootstrap API 호출 및 스키마 검증."""
        response = client.get("/api/evaluation/bootstrap")
        assert response.status_code == 200
        
        body = response.json()
        
        for metric in ["precision", "recall", "f1"]:
            assert metric in body
            assert "point_estimate" in body[metric]
            assert "ci_low" in body[metric]
            assert "ci_high" in body[metric]
            assert body[metric]["ci_low"] <= body[metric]["point_estimate"] <= body[metric]["ci_high"]
            
        assert body["resampling_iterations"] == 1000

    def test_get_errors(self, client):
        """GET /api/evaluation/errors API 호출 및 스키마 검증."""
        response = client.get("/api/evaluation/errors")
        assert response.status_code == 200
        
        body = response.json()
        
        assert "total_errors" in body
        assert isinstance(body["total_errors"], int)
        
        assert "patterns" in body
        assert isinstance(body["patterns"], list)
        assert len(body["patterns"]) == 3
        
        # 패턴 1 검증
        pattern1 = body["patterns"][0]
        assert pattern1["pattern_name"] == "누락 (False Negative)"
        assert pattern1["count"] >= 0
        assert isinstance(pattern1["ratio"], float)
        assert "description" in pattern1
        
        # 예시 검증
        assert "examples" in pattern1
        assert isinstance(pattern1["examples"], list)
        assert len(pattern1["examples"]) > 0
        
        example = pattern1["examples"][0]
        assert "announcement_id" in example
        assert "title" in example
        assert "field_name" in example
        assert "ground_truth" in example
        assert "prediction" in example
