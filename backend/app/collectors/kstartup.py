"""K-Startup 지원사업 공고 수집기.

공공데이터포털(data.go.kr)의 '창업진흥원_K-Startup 조회서비스' API 사용.
"""

import asyncio
import time
from typing import Any

import httpx
from playwright.async_api import async_playwright

from app.collectors.base import BaseCollector
from app.config import settings


class KstartupCollector(BaseCollector):
    """K-Startup(k-startup.go.kr) 지원사업 공고 수집기."""

    source_name = "kstartup"

    def collect_all(self) -> list[dict[str, Any]]:
        """전체 공고 수집."""
        params = {
            "serviceKey": settings.kstartup_api_key,
            "numOfRows": 100,
            "pageNo": 1,
            "type": "json",
        }
        resp = httpx.get(settings.kstartup_api_url, params=params, timeout=30.0)

        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "xml" in content_type:
            items = self._parse_xml(resp.text)
        else:
            raw = resp.json()
            body = raw.get("response", {}).get("body", {})
            items_wrapper = body.get("items", {})
            items = items_wrapper.get("item", []) if isinstance(items_wrapper, dict) else items_wrapper
            
            if isinstance(items, dict):
                items = [items]

        results = []
        for item in items:
            normalized = self.normalize(item)
            if normalized["detail_url"]:
                try:
                    attachments = asyncio.run(
                        self._extract_attachments(normalized["detail_url"])
                    )
                    normalized["attachments"] = attachments
                except Exception as e:
                    print(f"[WARN] 첨부파일 추출 실패: {e}")
                finally:
                    time.sleep(2)  # 공고별 크롤링 간 2초 대기 (Rate Limiting)
            results.append(normalized)

        return results

    def _parse_xml(self, text: str) -> list[dict]:
        """XML 응답을 dict 리스트로 변환.

        이 API는 <col name="key">value</col> 형태의 비표준 XML을 반환.
        """
        import xml.etree.ElementTree as ET

        root = ET.fromstring(text)
        items = []
        for item_el in root.iter("item"):
            d = {}
            for col in item_el.findall("col"):
                key = col.get("name", "")
                val = col.text or ""
                if key:
                    d[key] = val
            items.append(d)
        return items

    def normalize(self, raw: dict) -> dict:
        """원본 응답 → 통합 스키마 변환."""
        def fmt_date(val: str | None) -> str | None:
            if not val:
                return None
            import re
            m = re.search(r"(\d{4})[-\./]?(\d{2})[-\./]?(\d{2})", val)
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            return None

        return {
            "source": "kstartup",
            "source_id": raw.get("pbanc_sn", ""),
            "title": raw.get("intg_pbanc_biz_nm", ""),
            "organization": raw.get("pbanc_ntrp_nm"),
            "executor": raw.get("biz_prch_dprt_nm"),
            "period_start": fmt_date(raw.get("pbanc_rcpt_bgng_dt")),
            "period_end": fmt_date(raw.get("pbanc_rcpt_end_dt")),
            "target_text": raw.get("aply_trgt_ctnt"),
            "exclusion_text": raw.get("aply_excl_trgt_ctnt") or None,
            "category": raw.get("supt_biz_clsfc"),
            "region": raw.get("supt_regin"),                 
            "detail_url": raw.get("detl_pg_url"),
            "raw_api_data": raw,
            "attachments": [],
        }

    async def _extract_attachments(self, detail_url: str) -> list[dict]:
        """Playwright로 상세 페이지에서 첨부파일 다운로드 링크 추출."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            attachments = []
            file_items = await page.query_selector_all("a.file_bg")
            
            for file_item in file_items:
                text = (await file_item.inner_text()).strip()
                ext = text.rsplit(".", 1)[-1].lower() if "." in text else "unknown"

                parent = await file_item.evaluate_handle("el => el.parentElement")
                btn_down = await parent.query_selector("a.btn_down")
                if not btn_down:
                    btn_down = await parent.query_selector("a[href*='fileDownload']")

                href = ""
                onclick = ""
                if btn_down:
                    href = await btn_down.get_attribute("href") or ""
                    onclick = await btn_down.get_attribute("onclick") or ""

                if not href or href == "#" or "javascript" in href:
                    href = onclick

                if href and not href.startswith("http") and not href.startswith("fn_"):
                    from urllib.parse import urljoin
                    href = urljoin("https://www.k-startup.go.kr", href)

                attachments.append({
                    "file_name": text,
                    "file_type": ext,
                    "download_url": href,
                })

            await browser.close()
            return attachments


if __name__ == "__main__":
    collector = KstartupCollector()
    items = collector.collect_all()
    print(f"수집된 공고: {len(items)}건")
    if items:
        import json
        print(json.dumps(items[0], ensure_ascii=False, indent=2, default=str))
