# -*- coding: utf-8 -*-
"""매칭 정확도 평가 — matcher 로직을 추출과 분리해 측정.

match_cases.json의 (자격조건 × 회사 프로필) → 기대 판정을 matcher에 흘려
출력 status가 기대와 일치하는지 집계한다. matcher는 순수 함수라 LLM·재추출 불필요.
추출 F1(0.567)과 독립적인, 매칭 레이어 자체의 정확도 지표.

실행: docker compose exec -T backend python /evaluation/match_eval.py
"""
import io
import json
import sys
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "/app")

from app.matcher.matcher import match_announcement
from app.schemas.eligibility import EligibilityField, ParsedCondition, Evidence

CASES_PATH = Path(__file__).parent / "match_cases.json"


def _to_date(v):
    return date.fromisoformat(v) if v else None


def build_company(c: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="평가용 가상기업",
        founded_date=_to_date(c.get("founded_date")),
        revenue=c.get("revenue"),
        region=c.get("region"),
        industry=c.get("industry"),
        employee_count=c.get("employee_count"),
        ceo_birth_date=_to_date(c.get("ceo_birth_date")),
        certifications=c.get("certifications"),
    )


def build_field(f: dict) -> EligibilityField:
    return EligibilityField(
        field_name=f["field_name"],
        condition=ParsedCondition(value=f.get("value"), operator=f.get("operator"), raw_text=f.get("raw_text", "")),
        evidence=Evidence(text=f.get("raw_text", ""), location=None),
        evidence_source="매칭 평가 케이스",
        processing_path="rule_based",
    )


def main():
    data = json.load(open(CASES_PATH, encoding="utf-8"))
    cases = data["cases"]
    correct = 0
    mismatches = []

    for c in cases:
        company = build_company(c["company"])
        field = build_field(c["field"])
        results = match_announcement(company, [field], uuid.uuid4())
        got = results[0].status if results else "(없음)"
        ok = got == c["expected"]
        if ok:
            correct += 1
        else:
            mismatches.append((c["desc"], c["expected"], got))

    n = len(cases)
    acc = correct / n if n else 0.0
    print(f"=== 매칭 정확도 ===")
    print(f"  {correct}/{n} 정답 ({acc:.1%})")
    if mismatches:
        print(f"\n  불일치 {len(mismatches)}건:")
        for desc, exp, got in mismatches:
            print(f"    ❌ {desc}\n       기대={exp}, 실제={got}")
    else:
        print("  전 케이스 일치 — matcher가 명백한 자격 판정을 정확히 수행 ✅")
    return acc, correct, n


if __name__ == "__main__":
    main()
