# Matcher — 매칭 엔진 설계 (초안)

## 1. 개요
기업 프로필(`Company`)과 공고 자격요건(`list[EligibilityField]`)을 비교하여
필드별 매칭 결과(`list[MatchResultResponse]`)를 산출한다.

## 2. 매칭 대상 필드
`EligibilityResult.field_name` 컨벤션 기준 (기존 코드 `app/models/eligibility.py` 주석 참고):

| 필드 | 타입 | 비교 연산자 | 비고 |
|------|------|------------|------|
| 업력 | int (년수) | 미만/이하/이상/초과/범위 | `Company.founded_date` 기준 계산 |
| 매출 | int (원) | 미만/이하/이상/초과/범위 | `Company.revenue` |
| 지역 | str | 포함/일치/무관 | `Company.region` |
| 나이 | int (만) | 미만/이하/이상/초과/범위 | `Company.ceo_birth_date` 기준 계산 |
| 종업원 수 | int | 미만/이하/이상/초과/범위 | `Company.employee_count` (PR#2 추가 제안) |
| 업종 | str | 포함/제외 | `Company.industry` (PR#2 추가 제안) |
| 인증 | dict | 보유/미보유 | `Company.certifications` JSONB |

> 기존 `EligibilityResult.field_name` 주석에는 5개(업력/매출/지역/나이/인증)만 예시로 있음.
> 종업원 수/업종은 PR#2에서 함준규와 협의 후 추가 반영.

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
    processing_path: str
```

## 5. 판정 규칙
- **충족**: 회사 값이 공고 조건을 만족
- **미충족**: 회사 값이 공고 조건을 만족하지 않음
- **확인필요**: 조건이 모호 / 회사 정보 누락 / `ParsedCondition.operator is None`
- **해당없음**: 해당 필드가 공고에 명시되지 않음 (매칭 대상 아님)

## 6. 엣지 케이스 처리 방향
- 경계값: "3년 미만" vs "3년 이하" 엄격히 구분 (`operator` 구분으로 판정)
- 모호한 조건: `ParsedCondition.value is None` → **확인필요**
- 정보 부족: `Company.revenue is None` 등 → **확인필요**
- 매칭 엔진은 `exception` 필드도 함께 고려 (예외 조항이 있으면 완화)

## 7. TODO (PR#2~#3)
- [ ] 필드별 비교 함수 스펙 확정 (`match_numeric`, `match_region`, `match_industry`, `match_certification`)
- [ ] 종업원 수/업종 필드를 `EligibilityResult.field_name` 컨벤션에 추가 (함준규 협의) — 인증은 기존 5개에 이미 포함
- [ ] 단위 테스트 케이스 설계 (엣지 프로필 7개 × 조건 6종)
- [ ] `processing_path` 값이 `MatchResultResponse`에 어떻게 전파되는지 설계