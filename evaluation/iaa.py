"""라벨러 간 합의도(IAA - Cohen's κ) 계산 모듈."""

import os
import json
from typing import List, Dict, Any, Tuple
from sklearn.metrics import cohen_kappa_score


def serialize_value(val: Any) -> Any:
    """비교 가능한 형태로 값을 직렬화합니다 (list -> tuple, dict -> 정렬 튜플)."""
    if val is None:
        return None
    if isinstance(val, list):
        return tuple(sorted(str(x) for x in val))
    if isinstance(val, dict):
        # {"min": 1, "max": 7} 같은 범위를 (min, max) 튜플로 치환
        return (val.get("min"), val.get("max"))
    return val


def get_field_state(gt_data: Dict[str, Any], field_name: str) -> Tuple[Any, Any]:
    """공고 데이터에서 특정 필드의 (value, operator) 튜플을 추출합니다."""
    fields = gt_data.get("fields", [])
    for f in fields:
        if f.get("field_name") == field_name:
            val = serialize_value(f.get("value"))
            op = f.get("operator")
            return (val, op)
    # 해당 필드가 없으면 (None, None) 반환
    return (None, None)


def calculate_iaa_for_field(labels_a: List[Dict[str, Any]], labels_b: List[Dict[str, Any]], field_name: str) -> float:
    """특정 필드에 대해 두 라벨러의 Cohen's κ 점수를 계산합니다.

    labels_a, labels_b는 각각 라벨러 A와 B가 매긴 공고 목록(ground_truth dict 리스트).
    동일한 공고 ID별로 정렬하여 1:1 대조 비교를 수행합니다.
    """
    # 공고 ID 기준으로 정렬
    sorted_a = sorted(labels_a, key=lambda x: x["announcement_id"])
    sorted_b = sorted(labels_b, key=lambda x: x["announcement_id"])
    
    y_a = []
    y_b = []
    
    for ga, gb in zip(sorted_a, sorted_b):
        assert ga["announcement_id"] == gb["announcement_id"], "비교 대상 공고 ID가 일치하지 않습니다."
        
        state_a = get_field_state(ga, field_name)
        state_b = get_field_state(gb, field_name)
        
        # sklearn의 cohen_kappa_score에 넣기 위해 비교 항목을 문자열로 변환하여 저장
        y_a.append(str(state_a))
        y_b.append(str(state_b))
        
    # 두 라벨러의 답변 종류가 완전히 1가지(모두 None 등)뿐인 경우 kappa 연산 시 NaN이 발생할 수 있음
    if len(set(y_a)) <= 1 and len(set(y_b)) <= 1 and y_a[0] == y_b[0]:
        return 1.0  # 완벽히 일치하는 경우 단일 클래스라도 1.0 반환
        
    return float(cohen_kappa_score(y_a, y_b))


def calculate_overall_iaa(labels_a: List[Dict[str, Any]], labels_b: List[Dict[str, Any]]) -> Dict[str, Any]:
    """표준 7종 필드에 대한 개별 κ 점수 및 종합 평균 κ 점수를 산출합니다."""
    standard_fields = ["업력", "매출", "지역", "나이", "종업원 수", "업종", "인증"]
    
    by_field_kappas = {}
    valid_kappas = []
    
    for field in standard_fields:
        kappa = calculate_iaa_for_field(labels_a, labels_b, field)
        by_field_kappas[field] = kappa
        valid_kappas.append(kappa)
        
    overall_kappa = sum(valid_kappas) / len(valid_kappas) if valid_kappas else 0.0
    
    return {
        "overall_kappa": overall_kappa,
        "by_field": by_field_kappas,
        "evaluated_count": len(labels_a)
    }


def load_labels_from_dir(directory: str) -> List[Dict[str, Any]]:
    """지정된 디렉토리의 모든 ann_NNN/ground_truth.json 라벨 파일들을 불러옵니다."""
    labels = []
    if not os.path.exists(directory):
        return labels
        
    for item in sorted(os.listdir(directory)):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path) and item.startswith("ann_"):
            json_file = os.path.join(item_path, "ground_truth.json")
            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    labels.append(json.load(f))
    return labels
