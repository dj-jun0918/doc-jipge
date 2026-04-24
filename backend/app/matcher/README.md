# Matcher — 매칭 엔진 설계

> **브랜치**: `feat/matcher-spec` | **최종 업데이트**: PR#2

---

## 1. 개요

기업 프로필(`Company`)과 공고 자격요건(`list[EligibilityField]`)을 비교하여
필드별 매칭 결과(`list[MatchResultResponse]`)를 산출한다.

```
Company + list[EligibilityField]
          ↓
     매칭 엔진 (matcher.py)
          ↓
  list[MatchResultResponse]
```

---

## 2. 매칭 대상 필드

`EligibilityResult.field_name` 컨벤션 기준 (기존 코드 `app/models/eligibility.py` 주석 참고):

| 필드 | 타입 | 비교 연산자 | Company 매핑 | 상태 |
|------|------|------------|-------------|------|
| 업력 | int (년수) | 미만/이하/이상/초과/범위 | `Company.founded_date` 기준 계산 | ✅ 확정 |
| 매출 | int (원) | 미만/이하/이상/초과/범위 | `Company.revenue` | ✅ 확정 |
| 지역 | str | 포함/일치/무관 | `Company.region` | ✅ 확정 |
| 나이 | int (만) | 미만/이하/이상/초과/범위 | `Company.ceo_birth_date` 기준 계산 | ✅ 확정 |
| 인증 | dict | 보유/미보유 | `Company.certifications` JSONB | ✅ 확정 |
| 종업원 수 | int | 미만/이하/이상/초과/범위 | `Company.employee_count` | ✅ 확정 |
| 업종 | str | 포함/제외 | `Company.industry` | ✅ 확정 |

---

## 3. 입력 타입

```python
# app/schemas/eligibility.py (이미 존재)
class EligibilityField(BaseModel):
    field_name: str
    condition: ParsedCondition  # {value, operator, raw_text}
    exception: str | None
    evidence: str
    evidence_source: str
    processing_path: Literal["rule_based", "text_llm", "vision_llm"]
```

```python
# app/schemas/parsed_condition.py
class ParsedCondition(BaseModel):
    value: int | float | str | None
    operator: str | None   # "미만" | "이하" | "이상" | "초과" | "범위" | None
    raw_text: str
```

---

## 4. 출력 타입

```python
# app/schemas/match_result.py (이미 존재)
class MatchResultResponse(BaseModel):
    id: uuid.UUID
    announcement_id: uuid.UUID
    company_id: uuid.UUID
    field_name: str
    status: Literal["충족", "미충족", "확인필요", "해당없음"]
    company_value: str | None       # 회사의 실제 값
    requirement_value: str | None   # 공고의 요구 값
    evidence: str | None
    processing_path: str            # EligibilityField.processing_path 전파
```

---

## 5. 판정 규칙

| status | 조건 |
|--------|------|
| **충족** | 회사 값이 공고 조건을 만족 |
| **미충족** | 회사 값이 공고 조건을 만족하지 않음 |
| **확인필요** | 조건 모호 / 회사 정보 누락 / `ParsedCondition.operator is None` |
| **해당없음** | 해당 필드가 공고에 명시되지 않음 (매칭 대상 아님) |

---

## 6. 비교 함수 시그니처

### 6-1. `match_numeric()` — 수치 비교 (업력/매출/나이/종업원 수)

```python
def match_numeric(
    company_value: int | float | None,
    condition: ParsedCondition
) -> Literal["충족", "미충족", "확인필요"]:
    """
    업력 / 매출 / 나이 / 종업원 수에 공통 적용.

    Returns:
        "충족"    — company_value가 조건을 만족
        "미충족"  — company_value가 조건을 불만족
        "확인필요" — company_value is None, 또는 condition.operator is None
    """
    ...
```

**분기 로직 (operator별)**:

| operator | 판정식 |
|----------|--------|
| `"미만"` | `company_value < condition.value` |
| `"이하"` | `company_value <= condition.value` |
| `"이상"` | `company_value >= condition.value` |
| `"초과"` | `company_value > condition.value` |
| `"범위"` | `condition.value[0] <= company_value <= condition.value[1]` |
| `None` | → **확인필요** |

### 6-2. `match_region()` — 지역 비교

```python
def match_region(
    company_region: str | None,
    condition: ParsedCondition
) -> Literal["충족", "미충족", "확인필요"]:
    """
    지역 포함/일치/무관 비교.
    "전국" 조건 → 항상 "충족".
    REGION_GROUPS 상수로 정규화 후 비교.
    """
    ...
```

**REGION_GROUPS 상수 예시**:

```python
REGION_GROUPS: dict[str, list[str]] = {
    "서울": ["서울특별시", "서울"],
    "강원": ["강원특별자치도", "강원도", "강원"],
    "경기": ["경기도", "경기"],
    # ... 전체 광역시/도 포함
}
```

### 6-3. `match_industry()` — 업종 비교

```python
def match_industry(
    company_industry: str | None,
    condition: ParsedCondition
) -> Literal["충족", "미충족", "확인필요"]:
    """업종 포함/제외 비교."""
    ...
```

### 6-4. `match_certification()` — 인증 보유 비교

```python
def match_certification(
    company_certs: dict | None,
    condition: ParsedCondition
) -> Literal["충족", "미충족", "확인필요"]:
    """
    Company.certifications JSONB에서 해당 인증 보유 여부 확인.
    """
    ...
```

---

## 7. 엣지 케이스 처리

| 상황 | 처리 |
|------|------|
| `"3년 미만"` vs `"3년 이하"` | `operator` 엄격 구분 — `<` vs `<=` |
| `ParsedCondition.value is None` | → **확인필요** |
| `ParsedCondition.operator is None` | → **확인필요** |
| `Company.revenue is None` 등 정보 누락 | → **확인필요** |
| `exception` 필드 존재 | 예외 조항 적용 → 조건 완화 가능 (구현 PR#3) |
| `"전국"` 지역 조건 | → 항상 **충족** |
| 지역 표기 불일치 (`"서울"` vs `"서울특별시"`) | `REGION_GROUPS`로 정규화 후 비교 |

---

## 8. `processing_path` 전파 방식

`EligibilityField.processing_path` 값을 `MatchResultResponse.processing_path`에 그대로 전파한다.

```
EligibilityField.processing_path  →  MatchResultResponse.processing_path
    "rule_based"                  →       "rule_based"
    "text_llm"                    →       "text_llm"
    "vision_llm"                  →       "vision_llm"
```

**설계 원칙**: 매칭 엔진은 `processing_path`를 수정하지 않는다. 추출 단계에서 결정된 경로를 그대로 보존하여 추적 가능성(traceability)을 확보한다.

---

## 9. TODO (PR#2 ~ PR#3)

- [x] 종업원 수/업종 필드 `EligibilityResult.field_name` 컨벤션 추가 확정 (함준규 협의 완료)
- [x] 비교 함수 시그니처 확정 (`match_numeric`, `match_region`, `match_industry`, `match_certification`)
- [x] `processing_path` 전파 방식 설계
- [x] `match_numeric()` 구현 착수 (PR#2)
- [x] `match_region()` 구현 착수 (PR#2)
- [ ] 단위 테스트 케이스 설계 — 엣지 프로필 8개 × 조건 6종 (PR#3)
- [ ] `exception` 필드 처리 로직 구현 (PR#3)
- [ ] `match_industry()` 구현 (PR#3)