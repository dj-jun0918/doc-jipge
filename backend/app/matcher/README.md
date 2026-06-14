# Matcher — 매칭 엔진 설계

> **브랜치**: `develop` | **최종 업데이트**: 2026-06-15

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
    operator: str | None   # 수치: "미만" | "이하" | "이내" | "이상" | "초과" | "범위"
                           # 업종: "포함" | "제외" / 인증: "보유" | "미보유" / None
    raw_text: str
```

`"이내"`는 `match_numeric`에서 `"이하"`와 동일하게 처리한다 (예: "창업 3년 이내" = 3년 이하).

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
    score: float | None             # 필드별 점수 0~1 (충족 1.0 / 확인필요 0.45 / 미충족 0~0.3 / 해당없음 None)
    distance: float | None          # 미충족 수치 필드의 정규화 거리 (조건값 대비 차이 비율)
    constraint_type: Literal["hard", "soft"] | None  # 현재 전부 "hard" (soft 제약 미구현)
    company_value: str | None       # 회사의 실제 값
    requirement_value: str | None   # 공고의 요구 값 (condition.raw_text)
    evidence: Evidence | None       # 근거 객체 (text + location)
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

### 5-1. 필드별 점수 (`compute_field_score`)

status를 0~1 연속 점수로 환산한다. **값이 아니라 순서가 설계 의도** — 매칭 정답 데이터 부재로 상수는 캘리브레이션되지 않았다.

| status | score |
|--------|-------|
| **충족** | `1.0` |
| **확인필요** | `0.45` — "사실이면 충족일 수 있는 미지"는 "확실한 미충족"보다 항상 위 |
| **미충족** | `(1.0 - distance) * 0.3` (상한 `0.3`). `distance is None` 또는 `>= 1.0`이면 `0.0` |
| **해당없음** | `None` (집계에서 제외) |

상한 `0.3 < 0.45`로, 확실한 탈락이 미지(확인필요)보다 위로 랭크되는 역전을 막는다. `distance`는 미충족 수치 필드에 대해 `|company_value - threshold| / |threshold|`(범위는 가까운 경계 기준)로 계산한다.

### 5-2. 공고 단위 총점 (`compute_aggregate_score`)

필드별 score의 **가중 평균** (0~1). 가중치는 `FIELD_WEIGHTS` — 7종 균등 `1.0` (가중치 학습 후 이 dict만 교체). 해당없음 필드는 분모에서 제외. 단순 충족/전체 비율이 아닌 연속 점수다.

### 5-3. 적합도 버킷 (`derive_eligibility_bucket`)

총점(연속값)과 **별개의 범주 레이어**로, 공고를 3분류한다. 매칭 대시보드는 이 버킷으로 공고를 묶어 표시하고(버킷 우선 정렬), 자격미달 그룹은 접는다. 상세·What-if 화면에도 버킷 배지를 단다.

| 버킷 | 규칙 |
|------|------|
| **자격미달** | 미충족(하드 탈락) ≥ 1건 |
| **조건확인** | 미충족 0건 + 확인필요 ≥ 1건 (또는 판단 대상 0건 = 근거 없음) |
| **신청가능** | 미충족·확인필요 0건 + 충족 ≥ 1건 |

(해당없음 필드는 카운트에서 제외. 버킷이 '미충족' 대신 '자격미달' 단어를 쓰는 이유는 필드 status '해당없음'과의 혼동 방지.)

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
    """
    업종 포함/제외 비교.
    operator "포함" → 허용 업종에 들면 충족 / "제외" → 들면 미충족.
    조건 업종이 회사 업종에 부분포함될 때만 매칭 (예: "제조" ⊂ "식품 제조업").
    회사 업종이 조건보다 더 일반적이면(역방향) 단정 불가 → 확인필요.
    """
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
    operator "보유" / "미보유". condition.value는 표준 키 또는 키 목록.
    복수 요구 키는 '하나라도 보유'로 판정.
    표준 키 boolean(True) 외에 자유입력 텍스트(예: {note: "벤처기업 인증"})도
    cert_mapping 키워드 매칭(match_cert)으로 인정. 텍스트가 있는데 못 찾으면 단정하지 않음(확인필요).
    """
    ...
```

**`cert_mapping.py` — 인증 표준 키 18종**

`CERT_MAPPING`은 표준 키 ↔ 한글 키워드 매핑으로 18종을 정의한다 (라벨링 가이드라인 인증 매핑표와 1:1 동기화).

```
venture_company, inno_biz, main_biz,
iso_9001, iso_14001, iso_27001, iso_22000,
gmp, haccp, ce_marking, kc_certification,
women_owned, social_enterprise, rd_lab,
ip_protection, nep, net, gs
```

짧은 영문 약어(CE/KC/NET/NEP/GMP 등)는 단어경계로 매칭해 부분문자열 오탐(`ACE`/`INTERNET` 등)을 막고, 한글·긴 키워드는 부분문자열로 매칭한다.

---

## 7. 엣지 케이스 처리

| 상황 | 처리 |
|------|------|
| `"3년 미만"` vs `"3년 이하"` | `operator` 엄격 구분 — `<` vs `<=` |
| `ParsedCondition.value is None` | → **확인필요** |
| `ParsedCondition.operator is None` | → **확인필요** |
| `Company.revenue is None` 등 정보 누락 | → **확인필요** |
| `exception` 필드 존재 | 예외 조항 적용(조건 완화)은 매처에서 아직 미반영 |
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

## 9. Counterfactual / What-if

- `compute_field_sensitivities()` — 필드별 sensitivity. 그 필드를 충족(1.0)시킬 때 총점 상승폭(`weight × (1 - eff) / Σweight`). 미충족이 심한 필드일수록 크다. 영향 큰 조건부터 변경 제안하기 위한 정렬 키로 쓰고 raw 값은 노출하지 않는다.
- `counterfactual_for_field()` — 미충족 필드 1개를 충족시키는 최소 변경 제안. 매출/종업원 수/지역/업종/인증은 프로필 수정으로 변경 가능(`changeable=True`, `override_attr`/`override_value`로 What-if 시뮬레이션에 적용), 업력·나이는 시간 기반이라 변경 불가로 표시.

---

## 10. 상태

구현 완료:

- [x] 비교 함수 4종 (`match_numeric`, `match_region`, `match_industry`, `match_certification`)
- [x] 필드별 점수 / 공고 단위 총점 / 적합도 버킷 (`compute_field_score`, `compute_aggregate_score`, `derive_eligibility_bucket`)
- [x] Counterfactual / sensitivity (`counterfactual_for_field`, `compute_field_sensitivities`)
- [x] `processing_path` 전파

미구현:

- [ ] `exception` 필드 처리 로직 (예외 조항 적용 조건 완화)
- [ ] soft 제약 — `constraint_type`은 스키마에만 존재하고 현재 전부 `"hard"`
- [ ] `FIELD_WEIGHTS` 가중치 학습 (현재 7종 균등 `1.0`)