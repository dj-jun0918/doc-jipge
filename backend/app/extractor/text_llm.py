"""텍스트 LLM 추출기 프로토타입."""

import json

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


SYSTEM_PROMPT = """당신은 정부지원사업 공고문에서 기업 자격요건을 추출하는 전문가입니다.

주어진 공고 텍스트에서 다음 필드별 자격요건을 JSON 형식으로 추출하세요:
- 업력: 기업 설립 후 경과 연수 조건
- 매출: 연매출 기준
- 지역: 소재지 조건
- 나이: 대표자 나이 조건
- 종업원 수: 상시근로자 수
- 업종: 업종 제한
- 인증: 필수 인증

각 필드에 대해 다음 JSON 형식으로 응답:
{
  "fields": [
    {
      "field_name": "업력",
      "condition": "3년 미만",
      "operator": "미만",
      "value": 3,
      "evidence": "원문에서 해당 조건이 명시된 문장"
    }
  ],
  "exclusions": ["지원 제외 대상 1", "지원 제외 대상 2"]
}

규칙:
1. 원문에 명시되지 않은 조건은 포함하지 마세요
2. 조건의 원문 표현을 그대로 유지하세요
3. evidence에는 해당 조건이 있는 원문 문장을 그대로 복사하세요
4. 확실하지 않은 조건은 포함하지 마세요
5. 반드시 유효한 JSON만 응답하세요"""


def extract_from_text(text: str, model: str = "gpt-4o-mini") -> dict:
    """텍스트에서 자격요건을 LLM으로 추출."""
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"다음 공고 텍스트에서 자격요건을 추출하세요:\n\n{text}"},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        if "fields" not in result:
            result["fields"] = []
        if "exclusions" not in result:
            result["exclusions"] = []

        return result

    except json.JSONDecodeError as e:
        return {"fields": [], "exclusions": [], "error": f"JSON 파싱 실패: {e}"}
    except Exception as e:
        return {"fields": [], "exclusions": [], "error": f"LLM 호출 실패: {e}"}


if __name__ == "__main__":
    test_text = """
    [지원자격]
    1. 창업 후 3년 미만 중소기업
    2. 강원도 소재 기업
    3. 대표자 만 39세 이하
    4. 상시근로자 5인 이상
    5. 연매출 10억원 이하

    [지원제외]
    - 휴폐업 기업
    - 국세·지방세 체납 기업
    - 금융기관 채무불이행 기업
    """

    print("=== LLM 추출기 프로토타입 테스트 ===")
    result = extract_from_text(test_text)

    if "error" in result:
        print(f"에러: {result['error']}")
    else:
        print(f"추출된 필드: {len(result['fields'])}개")
        for f in result["fields"]:
            print(f"  - {f.get('field_name')}: {f.get('condition')}")
        print(f"제외 대상: {len(result['exclusions'])}개")
        for ex in result["exclusions"]:
            print(f"  - {ex}")
