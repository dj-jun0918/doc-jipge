"""`evaluation/measure.py` 내 핵심 매칭 및 계산 모듈에 대한 단위 테스트."""

import pytest
from typing import Any
from evaluation.measure import _normalize, match_fields, calculate_metrics, aggregate_metrics
from app.schemas.eligibility import EligibilityField, ParsedCondition, AnnouncementEligibility


# Mock 객체들을 생성하기 위한 헬퍼 클래스
class DummyEligibilityField:
    def __init__(self, field_name: str, raw_text: str, processing_path: str = "text_llm"):
        self.field_name = field_name
        self.condition = type("ParsedCondition", (object,), {"raw_text": raw_text})()
        self.evidence = "임시 증빙 문장"
        self.processing_path = processing_path


def test_normalize_text_behavior():
    """`_normalize` 헬퍼가 한글 NFD 대응, 공백 및 대소문자 제거, 파이프 이스케이프를 올바르게 처리하는지 테스트."""
    # 1. 공백 및 대소문자 제거
    assert _normalize("  Test   CONDITION  ") == "test condition"
    
    # 2. 마크다운 파이프 기호 이스케이프
    assert _normalize("제조업 | IT서비스업") == "제조업 \\| it서비스업"
    
    # 3. None 또는 빈 값 처리
    assert _normalize(None) == ""


def test_match_fields_classification():
    """TP, FP, FN 분류 매칭 기능 검증."""
    gt_fields = [
        {"field_name": "업력", "condition": "3년 미만", "evidence": "근거 1", "evidence_source": "본문"},
        {"field_name": "매출", "condition": "10억원 이상", "evidence": "근거 2", "evidence_source": "본문"},
        {"field_name": "비표준필드", "condition": "조건", "evidence": "근거 3"}  # 표준 7종 제외 대상
    ]
    
    pred_fields = [
        DummyEligibilityField(field_name="업력", raw_text="3년 미만"),  # TP
        DummyEligibilityField(field_name="매출", raw_text="5억원 이하"),  # condition 불일치 -> FP & FN 발생
        DummyEligibilityField(field_name="지역", raw_text="서울 소재"),  # GT엔 없음 -> 과추출 FP
        DummyEligibilityField(field_name="비표준필드", raw_text="조건")  # 비표준 필드로 예측에서도 제외됨
    ]

    tps, fps, fns = match_fields("ann_001", gt_fields, pred_fields)

    # 1. TP 검증 (업력: 3년 미만 일치)
    assert len(tps) == 1
    assert tps[0]["field_name"] == "업력"
    assert tps[0]["condition"] == "3년 미만"

    # 2. FP 검증 (매출: 5억원 이하 과추출, 지역: 서울 소재 과추출)
    # 매출은 mismatch 처리되므로 fps와 fns에 각각 존재
    assert len(fps) == 2
    fp_fields = {item["field_name"] for item in fps}
    assert "매출" in fp_fields
    assert "지역" in fp_fields

    # 3. FN 검증 (매출: 10억원 이상 누락)
    assert len(fns) == 1
    assert fns[0]["field_name"] == "매출"
    assert fns[0]["condition"] == "10억원 이상"


def test_calculate_metrics():
    """Precision, Recall, F1 수학적 계산 동작 검증."""
    # 1. 기본 계산
    p, r, f1 = calculate_metrics(tp=4, fp=1, fn=2)
    assert p == 4 / 5
    assert r == 4 / 6
    assert f1 == 2 * (p * r) / (p + r)

    # 2. 분모가 0인 엣지케이스 처리
    p, r, f1 = calculate_metrics(tp=0, fp=0, fn=0)
    assert p == 0.0
    assert r == 0.0
    assert f1 == 0.0


def test_aggregate_metrics_sparse_announcements():
    """빈약 라벨에 대한 None 허용 및 오답 케이스 취합 검증."""
    gt_list = [
        {
            "announcement_id": "ann_011",
            "title": "빈약 라벨 공고 11",
            "fields": [
                {"field_name": "업력", "condition": "3년 미만"}  # 필드 1개 -> 빈약 라벨
            ],
            "exclusions": []
        }
    ]

    # 예측에서 아무것도 추출되지 않아 분모가 0인 경우
    predictions = {
        "ann_011": AnnouncementEligibility(
            announcement_id="ann_011",
            title="빈약 라벨 공고 11",
            fields=[],
            exclusions=[]
        )
    }

    results = aggregate_metrics(gt_list, predictions)

    # 빈약 라벨은 sparse_announcements 리스트에 추가되어 메트릭이 None으로 계산되어야 함
    sparse_info = results["sparse_announcements"]
    assert len(sparse_info) == 1
    assert sparse_info[0]["announcement_id"] == "ann_011"
    assert sparse_info[0]["precision"] is None
    assert sparse_info[0]["recall"] == 0.0
    assert sparse_info[0]["f1"] is None
