"""텍스트 LLM 추출기."""

import json
import logging

from openai import APIConnectionError, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.extractor.llm_response_parser import ExtractionResult, build_extraction_result

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


SYSTEM_PROMPT = """당신은 정부지원사업 공고문에서 기업 자격요건을 추출하는 전문가입니다.
공고 본문은 <공고> 태그 안에, 제외 대상은 <제외대상> 태그 안에 주어집니다.

다음 7종 필드만 추출하세요 (field_name은 아래 표기와 정확히 일치):
업력, 매출, 지역, 나이, 종업원 수, 업종, 인증

출력 형식:
{
  "fields": [
    {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3, "evidence": "원문 한 문장 그대로"}
  ],
  "exclusions": ["지원 제외 대상 1", "지원 제외 대상 2"]
}

규칙:
1. 원문에 글자 그대로 근거가 있는 조건만 추출하라. 근거 없는 필드는 출력에서 제외하라.
2. 경계 표현을 그대로 보존하라: "미만"→operator "미만", "이하"→operator "이하" (서로 다름).
3. evidence는 <공고> 안에 글자 그대로 존재하는 문장(또는 표 셀의 markdown 라인)을 복사하라.
4. operator: 미만 | 이하 | 이상 | 초과 | 범위 | 소재 | 무관 | 포함 | 제외 | 보유 | 미보유
5. 입력에 `# 첨부 표` 섹션이 있으면 표 형식 자격요건도 본문과 동일 기준으로 추출하라.
6. **신청 자격요건만** 추출하라. 다음은 자격요건이 아니므로 추출 금지: 지원내용, 지원금액, 지원규모, 보조율, 자부담률, 심사기준, 가점, 우대사항, 추진일정, 선정 후 의무사항.
7. 공고에 해당 필드의 명시적 제한이 없으면 그 필드를 출력하지 마라. 제한이 없다는 이유로 operator "무관"을 만들어내지 마라 (원문에 "전국", "제한 없음" 등이 명시된 경우만 예외).
8. 아래 예시의 값을 출력에 복사하지 마라. 예시는 형식 참고용일 뿐이며, 모든 값은 <공고> 원문에서만 가져와라.

# value 형식
- 금액: "10억"→1000000000, "5000만원"→50000000 (원 단위 정수)
- 종업원: "5인"/"5명"→5, 나이: "만 39세"→39
- 범위: "3년 이상 5년 이하"→operator "범위", value={"min": 3, "max": 5}
- 업종: 허용 업종은 operator "포함", 배제 업종은 operator "제외", value는 업종명 문자열 또는 리스트 (예: "제조업", ["IT", "바이오"])

# 지역 정규화 (value)
- "강원도"/"강원특별자치도"→"강원", "서울특별시"→"서울", "경기도"→"경기"
- "전국"→operator "무관", value "전국"
- 여러 지역→value=["강원", "서울"]

# 인증 표준 키 (value)
- venture_company: 벤처기업 / inno_biz: 이노비즈, 기술혁신형 중소기업 / main_biz: 메인비즈, 경영혁신형 중소기업
- iso_9001: ISO 9001, 품질경영시스템 / iso_14001: ISO 14001, 환경경영시스템
- iso_27001: ISO 27001, 정보보안경영시스템 / iso_22000: ISO 22000, 식품안전경영시스템
- gmp: GMP / haccp: HACCP / ce_marking: CE / kc_certification: KC
- women_owned: 여성기업 / social_enterprise: 사회적기업 / rd_lab: 기업부설연구소 / ip_protection: 특허, 지식재산권
- 매핑에 없는 인증은 원문 그대로

# 예시 1
입력: "창업 후 3년 미만 중소기업, 강원도 소재, 만 39세 이하"
출력: {
  "fields": [
    {"field_name": "업력", "condition": "3년 미만", "operator": "미만", "value": 3, "evidence": "창업 후 3년 미만 중소기업"},
    {"field_name": "지역", "condition": "강원도 소재", "operator": "소재", "value": "강원", "evidence": "강원도 소재"},
    {"field_name": "나이", "condition": "만 39세 이하", "operator": "이하", "value": 39, "evidence": "만 39세 이하"}
  ],
  "exclusions": []
}

# 예시 2 (모호한 조건)
입력: "청년 대표자 우대"
출력: {
  "fields": [
    {"field_name": "나이", "condition": "청년", "operator": null, "value": null, "evidence": "청년 대표자 우대"}
  ],
  "exclusions": []
}

# 예시 3 (표 형식 자격요건 + 제외 대상)
입력: "신청자격: 아래 표 참조. 단, 휴폐업 기업, 국세 체납 기업은 지원 제외.

# 첨부 표
## 표_1
| 구분 | 자격 |
|------|------|
| 업력 | 창업 12년 이하 |
| 매출 | 연 7억 5천만원 이하 |
| 지역 | 제주도 소재 |
| 인증 | HACCP 보유 |"
출력: {
  "fields": [
    {"field_name": "업력", "condition": "창업 12년 이하", "operator": "이하", "value": 12, "evidence": "| 업력 | 창업 12년 이하 |"},
    {"field_name": "매출", "condition": "연 7억 5천만원 이하", "operator": "이하", "value": 750000000, "evidence": "| 매출 | 연 7억 5천만원 이하 |"},
    {"field_name": "지역", "condition": "제주도 소재", "operator": "소재", "value": "제주", "evidence": "| 지역 | 제주도 소재 |"},
    {"field_name": "인증", "condition": "HACCP 보유", "operator": "보유", "value": "haccp", "evidence": "| 인증 | HACCP 보유 |"}
  ],
  "exclusions": ["휴폐업 기업", "국세 체납 기업"]
}

# 예시 4 (자격요건이 아닌 정보 — 추출 금지)
입력: "지원내용: 기업당 최대 3,000만원 지원 (자부담 20% 이상). 심사 시 벤처기업 인증 보유 기업 가점 5점."
출력: {"fields": [], "exclusions": []}
(이유: 지원금액·자부담률은 지원내용, 가점은 우대사항 — 신청 자격요건이 아님)

# 예시 5 (자격요건 없음)
입력: "본 사업은 사업자등록을 마친 누구나 신청 가능합니다."
출력: {"fields": [], "exclusions": []}

반드시 유효한 JSON만 응답하세요."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    reraise=True,
)
async def _call_llm(user_input: str, model: str) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
        timeout=60,
    )
    usage = response.usage
    if usage:
        logger.info(
            f"text_llm 호출: model={model}, "
            f"prompt_tokens={usage.prompt_tokens}, "
            f"completion_tokens={usage.completion_tokens}"
        )
    return response.choices[0].message.content or ""


async def extract(
    text: str,
    exclusion_text: str = "",
    model: str = "gpt-4o-mini",
) -> ExtractionResult:
    """공고 텍스트에서 자격요건 추출.

    Args:
        text: 지원 대상 텍스트 (target_text)
        exclusion_text: 제외 대상 텍스트 (exclusion_text, 선택)
        model: OpenAI 모델명 (기본 gpt-4o-mini)

    Returns:
        ExtractionResult — fields + exclusions, 실패 시 error 필드
    """
    if not text:
        return ExtractionResult(fields=[], exclusions=[], processing_path="text_llm")

    user_input = f"<공고>\n{text}\n</공고>"
    if exclusion_text:
        user_input += f"\n\n<제외대상>\n{exclusion_text}\n</제외대상>"

    try:
        content = await _call_llm(user_input, model)
    except Exception as e:
        logger.warning(f"text_llm 호출 실패: {e}")
        return ExtractionResult(
            fields=[], exclusions=[], processing_path="text_llm",
            error=f"LLM 호출 실패: {e}",
        )

    try:
        llm_json = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"text_llm JSON 파싱 실패: {e}")
        return ExtractionResult(
            fields=[], exclusions=[], processing_path="text_llm",
            error=f"JSON 파싱 실패: {e}",
        )

    return build_extraction_result(llm_json, processing_path="text_llm", source_text=text)


if __name__ == "__main__":
    import asyncio

    test_text = """
    [지원자격]
    1. 창업 후 3년 미만 중소기업
    2. 강원도 소재 기업
    3. 대표자 만 39세 이하
    4. 상시근로자 5인 이상
    5. 연매출 10억원 이하
    """

    test_exclusion = """
    - 휴폐업 기업
    - 국세·지방세 체납 기업
    """

    print("=== text_llm.extract 테스트 ===")
    result = asyncio.run(extract(test_text, test_exclusion))

    if result.error:
        print(f"에러: {result.error}")
    else:
        print(f"필드: {len(result.fields)}개")
        for f in result.fields:
            print(f"  - {f.field_name}: {f.condition.raw_text} (operator={f.condition.operator}, value={f.condition.value})")
        print(f"제외 대상: {len(result.exclusions)}개")
        for ex in result.exclusions:
            print(f"  - {ex}")
