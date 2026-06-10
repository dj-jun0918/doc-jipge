"""Vision LLM 추출기.

PDF의 표를 인식해서 자격요건을 추출. 표가 있는 페이지만 OpenAI Vision API에 전송.
"""

import base64
import json
import logging
from pathlib import Path

import pymupdf
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


VISION_PROMPT = """이 이미지는 정부지원사업 공고문의 일부입니다 (주로 표).
표에 적힌 기업 자격요건을 JSON으로 추출하세요.

다음 7개 필드를 대상으로 합니다:
- 업력, 매출, 지역, 나이, 종업원 수, 업종, 인증

응답 형식:
{
  "fields": [
    {
      "field_name": "업력",
      "condition": "3년 미만",
      "operator": "미만",
      "value": 3,
      "evidence": "표/본문에 적힌 원문 한 문장"
    }
  ],
  "exclusions": ["지원 제외 대상"]
}

규칙:
1. 원문에 명시되지 않은 조건은 포함하지 마세요
2. "3년 미만"과 "3년 이하"는 다릅니다 — 원문 그대로
3. evidence는 원문 그대로 복사 (요약/패러프레이징 금지)
4. operator: 미만 | 이하 | 이상 | 초과 | 범위 | 소재 | 무관 | 포함 | 제외 | 보유 | 미보유
5. **신청 자격요건만** 추출하세요. 지원내용, 지원금액, 지원규모, 보조율, 자부담률, 심사기준, 가점, 우대사항, 추진일정은 자격요건이 아니므로 추출 금지
6. 이미지에 해당 필드의 명시적 제한이 없으면 그 필드를 출력하지 마세요. 제한이 없다는 이유로 operator "무관"을 만들어내지 마세요
7. 반드시 유효한 JSON만 응답하세요"""


def pdf_to_images(pdf_path: str | Path, dpi: int = 150) -> list[bytes]:
    """PDF 각 페이지를 PNG bytes 리스트로 변환."""
    doc = pymupdf.open(str(pdf_path))
    images = []
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()
    return images


def detect_tables(pdf_path: str | Path) -> list[int]:
    """표가 있을 가능성이 높은 페이지 번호 리스트.

    PyMuPDF find_tables() + heuristic (가로/세로 선 개수).
    """
    doc = pymupdf.open(str(pdf_path))
    table_pages: list[int] = []

    try:
        for page_num, page in enumerate(doc):
            try:
                tables = page.find_tables()
                if tables and len(tables.tables) > 0:
                    table_pages.append(page_num)
                    continue
            except Exception:
                pass

            drawings = page.get_drawings()
            h_count = 0
            v_count = 0
            for d in drawings:
                for item in d.get("items", []):
                    if not item or item[0] != "l":
                        continue
                    p1, p2 = item[1], item[2]
                    if abs(p1.y - p2.y) < 1 and abs(p1.x - p2.x) > 50:
                        h_count += 1
                    elif abs(p1.x - p2.x) < 1 and abs(p1.y - p2.y) > 50:
                        v_count += 1
            if h_count >= 5 and v_count >= 3:
                table_pages.append(page_num)
    finally:
        doc.close()

    return table_pages


def _encode_image(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    reraise=True,
)
async def _call_vision(images_b64: list[str], model: str) -> str:
    client = _get_client()

    content_blocks: list[dict] = [{"type": "text", "text": VISION_PROMPT}]
    for b64 in images_b64:
        content_blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content_blocks}],
        temperature=0.0,
        response_format={"type": "json_object"},
        timeout=120,
    )

    usage = response.usage
    if usage:
        logger.info(
            f"vision_llm 호출: model={model}, "
            f"images={len(images_b64)}, "
            f"prompt_tokens={usage.prompt_tokens}, "
            f"completion_tokens={usage.completion_tokens}"
        )
    return response.choices[0].message.content or ""


async def extract_from_pdf(
    pdf_path: str | Path,
    model: str = "gpt-4o",
    max_pages: int = 5,
) -> ExtractionResult:
    """PDF에서 Vision LLM으로 자격요건 추출.

    Args:
        pdf_path: PDF 파일 경로
        model: OpenAI 모델명 (기본 gpt-4o, Vision 지원 필요)
        max_pages: Vision 호출당 최대 페이지 수 (비용 보호)

    Returns:
        ExtractionResult — fields + exclusions
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return ExtractionResult(
            fields=[], exclusions=[], processing_path="vision_llm",
            error=f"PDF 파일 없음: {pdf_path}",
        )

    table_pages = detect_tables(pdf_path)
    if not table_pages:
        logger.info(f"vision_llm: 표 페이지 없음 ({pdf_path})")
        return ExtractionResult(fields=[], exclusions=[], processing_path="vision_llm")

    table_pages = table_pages[:max_pages]

    try:
        images = pdf_to_images(pdf_path)
    except Exception as e:
        return ExtractionResult(
            fields=[], exclusions=[], processing_path="vision_llm",
            error=f"PDF → PNG 변환 실패: {e}",
        )

    target_images = [_encode_image(images[i]) for i in table_pages if i < len(images)]
    if not target_images:
        return ExtractionResult(fields=[], exclusions=[], processing_path="vision_llm")

    try:
        content = await _call_vision(target_images, model)
    except Exception as e:
        logger.warning(f"vision_llm 호출 실패: {e}")
        return ExtractionResult(
            fields=[], exclusions=[], processing_path="vision_llm",
            error=f"Vision 호출 실패: {e}",
        )

    try:
        llm_json = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"vision_llm JSON 파싱 실패: {e}")
        return ExtractionResult(
            fields=[], exclusions=[], processing_path="vision_llm",
            error=f"JSON 파싱 실패: {e}",
        )

    # PDF 텍스트 레이어가 충분하면 evidence 원문 검증에 사용 (스캔본은 검증 기준이 없어 생략)
    source_text = None
    try:
        with pymupdf.open(pdf_path) as doc:
            text_layer = "\n".join(page.get_text() for page in doc)
        if len(text_layer.strip()) >= 200:
            source_text = text_layer
    except Exception as e:
        logger.warning(f"vision_llm 텍스트 레이어 추출 실패 — evidence 검증 생략: {e}")

    return build_extraction_result(llm_json, processing_path="vision_llm", source_text=source_text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python -m app.extractor.vision_llm <PDF경로>")
        print("예시: python -m app.extractor.vision_llm /app/evaluation/ground_truth/ann_001/announcement.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"=== detect_tables ===")
    pages = detect_tables(pdf_path)
    print(f"표 페이지: {pages}")

    print(f"\n=== pdf_to_images ===")
    imgs = pdf_to_images(pdf_path)
    print(f"전체 페이지: {len(imgs)}, 첫 페이지 크기: {len(imgs[0]) if imgs else 0:,} bytes")

    print(f"\n=== extract_from_pdf (Vision API 호출) ===")
    print("⚠️ OPENAI_API_KEY 필요. 비용 발생 (페이지당 약 $0.01~0.02)")

    import asyncio
    result = asyncio.run(extract_from_pdf(pdf_path))

    if result.error:
        print(f"에러: {result.error}")
    else:
        print(f"필드: {len(result.fields)}개")
        for f in result.fields:
            print(f"  - {f.field_name}: {f.condition.raw_text}")
        print(f"제외 대상: {len(result.exclusions)}개")
