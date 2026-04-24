import asyncio
from typing import Any
import json
import re

from playwright.async_api import async_playwright

from app.collectors.base import BaseCollector

class MssCollector(BaseCollector):
    """중소벤처기업부 공고 스크래퍼."""

    source_name = "mss"
    LIST_URL = "https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=310"
    BASE_VIEW_URL = "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=310&bcIdx="

    def collect_all(self) -> list[dict[str, Any]]:
        return asyncio.run(self._scrape())

    async def _scrape(self) -> list[dict[str, Any]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(self.LIST_URL, timeout=30000)
            await page.wait_for_selector("table tbody tr", timeout=10000)


            raw_links = await page.evaluate('''() => {
                const results = [];
                const rows = document.querySelectorAll("table tbody tr");
                rows.forEach(row => {
                    const trOnclick = row.getAttribute("onclick") || "";
                    const trTitle = row.getAttribute("title") || "";
                    const links = Array.from(row.querySelectorAll("a"));
                    const rowData = {
                        trOnclick: trOnclick,
                        trTitle: trTitle,
                        links: links.map(a => ({
                            href: a.getAttribute("href") || "",
                            onclick: a.getAttribute("onclick") || "",
                            innerText: (a.querySelector("strong") ? a.querySelector("strong").innerText : a.innerText).trim()
                        }))
                    };
                    results.push(rowData);
                });
                return results;
            }''')
            
            bc_ids = []
            for row in raw_links:
                bc_id = None
                title = row.get("trTitle", "")
                
                m = re.search(r"doBbsFView\([^,]+,\s*'([0-9]+)'", row['trOnclick'])
                if m:
                    bc_id = m.group(1)
                
                if not bc_id:
                    for link in row['links']:
                        href = link['href']
                        onclick = link['onclick']
                        if not title:
                            title = link['innerText']
                        
                        if "bcIdx=" in href:
                            m = re.search(r"bcIdx=([0-9]+)", href)
                            if m:
                                bc_id = m.group(1)
                        
                        if not bc_id and onclick and "fnSearch" in onclick:
                            m = re.search(r"fnSearch\([^,]+,\s*'([^']+)'\)", onclick)
                            if m:
                                bc_id = m.group(1)

                        if bc_id:
                            break

                if bc_id:
                    if not any(x["bcIdx"] == bc_id for x in bc_ids):
                        bc_ids.append({"bcIdx": bc_id, "title": title.strip()})
            
            items = []
            for i, entry in enumerate(bc_ids):
                detail_url = f"{self.BASE_VIEW_URL}{entry['bcIdx']}"
                await page.goto(detail_url, timeout=30000)
                await asyncio.sleep(3)

                raw = await self._parse_detail(page, entry)
                raw["detail_url"] = detail_url
                items.append(self.normalize(raw))

            await browser.close()
            return items

    async def _parse_detail(self, page, entry: dict) -> dict:
        """상세 페이지에서 공고 내용 + 첨부파일 추출."""
        content_el = await page.query_selector("div.view_contents, div.board_view")
        content = await content_el.inner_text() if content_el else ""

        meta_data = await page.evaluate('''() => {
            const result = {};
            document.querySelectorAll("table tr").forEach(tr => {
                const ths = tr.querySelectorAll("th");
                const tds = tr.querySelectorAll("td");
                for (let i = 0; i < ths.length; i++) {
                    if (ths[i] && tds[i]) {
                        result[ths[i].innerText.trim()] = tds[i].innerText.trim();
                    }
                }
            });
            return result;
        }''')

        attachments = []
        import re
        lis = await page.query_selector_all("li:has(a[href*='Download.do'])")
        for li in lis:
            name_el = await li.query_selector("span.name")
            name_text = await name_el.inner_text() if name_el else ""
            name_text = re.sub(r'\[.*?\]', '', name_text).strip()
            
            link_el = await li.query_selector("a[href*='Download.do']")
            href = await link_el.get_attribute("href") if link_el else ""
            
            if href:
                ext = name_text.split(".")[-1].lower() if "." in name_text else "unknown"
                attachments.append({
                    "file_name": name_text,
                    "file_type": ext,
                    "download_url": href if href.startswith("http") else f"https://www.mss.go.kr{href}",
                })

        return {
            "bcIdx": entry["bcIdx"],
            "title": entry["title"],
            "content": content,
            "attachments": attachments,
            "meta_data": meta_data,
        }

    def normalize(self, raw: dict) -> dict:
        meta = raw.get("meta_data", {})
        
        period_str = meta.get("신청기간", "")
        start, end = None, None
        if "~" in period_str:
            parts = [p.strip() for p in period_str.split("~")]
            if parts[0]: start = parts[0]
            if len(parts) > 1 and parts[1]: end = parts[1]
            
        executor = meta.get("담당부서")
        if executor and not executor.startswith("중소"):
            executor = f"중소벤처기업부 {executor}"

        return {
            "source": "mss",
            "source_id": raw.get("bcIdx", ""),
            "title": raw.get("title", ""),
            "organization": "중소벤처기업부",
            "executor": executor,
            "period_start": start,
            "period_end": end,
            
            # 미제공 필드 (추후 본문/첨부파일에서 추출)
            "target_text": None,
            "exclusion_text": None,
            "category": None,
            
            "region": "전국",  # MSS 기본값
            "detail_url": raw.get("detail_url"),
            "raw_api_data": raw,
            "attachments": raw.get("attachments", []),
        }

if __name__ == "__main__":
    collector = MssCollector()
    items = collector.collect_all()
    print(f"수집된 공고: {len(items)}건")
    if items:
        print(json.dumps(items[0], ensure_ascii=False, indent=2, default=str))
