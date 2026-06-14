"""Component-wise Ablation 실행 및 관리 모듈."""

import os
import json
from pathlib import Path
from typing import List, Dict, Any


def get_ablation_config(condition: str) -> Dict[str, Any]:
    """Ablation C1 ~ C4 조건별 추출 파이프라인 설정을 반환합니다.

    - C1: 규칙 기반 baseline (rule_parser)
    - C2: 텍스트 추출 LLM 결합 (rule + text_llm)
    - C3: 멀티모달 비전 LLM 결합 (rule + text_llm + vision_llm)
    - C4: 최종 상호 검증 Verifier 시스템 (rule + text + vision + verifier)
    """
    if condition == "C1":
        return {
            "use_rule_parser": True,
            "use_text_llm": False,
            "use_vision_llm": False,
            "use_verifier": False
        }
    elif condition == "C2":
        return {
            "use_rule_parser": True,
            "use_text_llm": True,
            "use_vision_llm": False,
            "use_verifier": False
        }
    elif condition == "C3":
        return {
            "use_rule_parser": True,
            "use_text_llm": True,
            "use_vision_llm": True,
            "use_verifier": False
        }
    elif condition == "C4":
        return {
            "use_rule_parser": True,
            "use_text_llm": True,
            "use_vision_llm": True,
            "use_verifier": True
        }
    else:
        raise ValueError(f"정의되지 않은 Ablation 조건입니다: {condition}")


def run_ablation(condition: str, gt_list: List[Dict[str, Any]], adv_list: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """조건별 hybrid_engine 파이프라인 구동 및 measure 평가 연산을 자동 수행합니다.

    실제 R&D 파이프라인 구동 및 대규모 LLM 비용 발생 처리는 PR#6에서 수행하며,
    PR#5에서는 조건 분기 및 인터페이스 구조를 정의하여 json 스토리지 구조를 생성합니다.
    """
    # 실측 ablation 미구현 — 가짜(mock) 메트릭 생성 차단.
    # 이전 버전은 하드코딩된 수치(C4 f1=0.893 등)를 ablation_{condition}.json에 그대로 기록해,
    # 실측(~0.59)과 모순되는 가짜 결과를 산출 경로에 양산하는 위험이 있었다. 실측 ablation은
    # 각 조건(C1~C4)의 추출 파이프라인을 GT에 구동 + measure 채점이 필요하며(대규모 LLM 비용)
    # 아직 구현되지 않았다. 가짜 수치가 결과 폴더에 남지 않도록 명시적으로 미구현을 알린다.
    raise NotImplementedError(
        f"ablation 실측 미구현 (condition={condition}): 조건별 파이프라인 실구동 + measure "
        "채점이 필요합니다. mock 메트릭을 기록하지 않습니다."
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    from evaluation.measure import load_ground_truth
    from evaluation.adversarial_loader import load_adversarial_labels
    
    print("=== Ablation Runner 구동 시작 ===")
    gt_list = load_ground_truth()
    adv_list = load_adversarial_labels()
    
    print(f"일반 GT 로드 완료: {len(gt_list)}건")
    print(f"적대적 케이스 로드 완료: {len(adv_list)}건")
    
    for condition in ["C1", "C2", "C3", "C4"]:
        res = run_ablation(condition, gt_list, adv_list)
        print(f"[{condition}] F1-Score: {res['metrics']['f1']}, 비용: ${res['cost_usd']:.2f}")
        
    print("=== Ablation Runner 구동 완료 ===")
