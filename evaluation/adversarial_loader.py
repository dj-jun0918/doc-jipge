"""적대적 케이스(Adversarial Case) 로더 모듈."""

import os
import json
from typing import List, Dict, Any

ADVERSARIAL_ROOT = "/Users/limtae-kyu/doc-jipge/evaluation/ground_truth/adversarial"


def load_adversarial_labels() -> List[Dict[str, Any]]:
    """adversarial/adv_NNN/ground_truth.json의 적대적 케이스 라벨 데이터를 일괄 로드합니다."""
    labels = []
    if not os.path.exists(ADVERSARIAL_ROOT):
        return labels
        
    for item in sorted(os.listdir(ADVERSARIAL_ROOT)):
        item_path = os.path.join(ADVERSARIAL_ROOT, item)
        if os.path.isdir(item_path) and item.startswith("adv_"):
            json_file = os.path.join(item_path, "ground_truth.json")
            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8") as f:
                    labels.append(json.load(f))
    return labels
