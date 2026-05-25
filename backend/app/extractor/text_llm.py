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

다음 7개 필드를 JSON으로 추출하세요:
- 업력, 매출, 지역, 나이, 종업원 수, 업종, 인증

각 필드에 대해 다음 형식으로 응답:
{
  "fields": [
    {
      "field_name": "업력",
      "condition": "3년 미만",
      "operator": "미만",
      "value": 3,
      "evidence": "원문 한 문장 그대로"
    }
  ],
  "exclusions": ["지원 제외 대상 1", "지원 제외 대상 2"]
}

규칙:
1. 원문에 명시되지 않은 조건은 포함하지 마세요
2. "3년 미만"과 "3년 이하"는 다릅니다 — 원문 그대로
3. evidence는 원문 한 문장 그대로 복사
4. operator: 미만 | 이하 | 이상 | 초과 | 범위 | 소재 | 무관 | 포함 | 제외 | 보유 | 미보유

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

    user_input = f"공고 내용:\n{text}"
    if exclusion_text:
        user_input += f"\n\n지원 제외 대상:\n{exclusion_text}"

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

    return build_extraction_result(llm_json, processing_path="text_llm")


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
