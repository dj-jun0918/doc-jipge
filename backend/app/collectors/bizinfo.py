"""기업마당 Open API 수집기."""

import re
from typing import Any

import httpx

from app.collectors.base import BaseCollector
from app.config import settings


class BizinfoCollector(BaseCollector):
    """기업마당(bizinfo.go.kr) 지원사업정보 API 수집기."""

    source_name = "bizinfo"
    BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"

    def collect_all(self) -> list[dict[str, Any]]:
        params = {
            "crtfcKey": settings.bizinfo_api_key,
            "dataType": "json",
            "searchCnt": 100,
            "pageUnit": 100,
            "pageIndex": 1,
        }
        resp = httpx.get(self.BASE_URL, params=params, timeout=30.0)
        resp.raise_for_status()
        raw = resp.json()

        items = raw.get("jsonArray", []) if isinstance(raw, dict) else raw
        return [self.normalize(item) for item in items]

    def normalize(self, raw: dict) -> dict:
        """원본 응답 → 통합 스키마 변환."""

        # 첨부파일 파싱 — flpthNm 필드가 @ 구분자로 URL 여러 개 연결
        attachments = []
        flpth = raw.get("flpthNm", "")
        if flpth:
            for url in flpth.split("@"):
                url = url.strip()
                if not url:
                    continue
                file_name = raw.get("fileNm", url.split("/")[-1])
                ext = file_name.split(".")[-1].lower() if "." in file_name else "unknown"
                attachments.append({
                    "file_name": file_name,
                    "file_type": ext,
                    "download_url": url,
                })

        # 지역명: API에 별도 필드 없어서 제목의 [지역] 패턴에서 추출
        title = raw.get("pblancNm", "")
        m = re.search(r"\[(.+?)\]", title)
        region = m.group(1) if m else None

        return {
            "source": "bizinfo",
            "source_id": raw.get("pblancId", ""),
            "title": title,
            "organization": raw.get("jrsdInsttNm"),
            "executor": raw.get("excInsttNm"),
            "period_start": raw.get("reqstBeginEndDe"),
            "period_end": None,
            "target_text": raw.get("trgetNm"),
            "exclusion_text": None,
            "category": raw.get("pldirSportRealmLclasCodeNm"),
            "region": region,
            "detail_url": raw.get("pblancUrl"),
            "raw_api_data": raw,
            "attachments": attachments,
        }


if __name__ == "__main__":
    collector = BizinfoCollector()
    items = collector.collect_all()
    print(f"수집된 공고: {len(items)}건")
    if items:
        import json
        print(json.dumps(items[0], ensure_ascii=False, indent=2, default=str))
