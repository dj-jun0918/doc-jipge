"""기업마당 Open API 수집기."""

import re
from typing import Any
from urllib.parse import urlparse, unquote, parse_qs

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

        # 첨부파일 파싱 — flpthNm(URL), fileNm(파일명) 모두 @ 구분자로 연결
        attachments = []
        flpth = raw.get("flpthNm", "")
        file_names_raw = raw.get("fileNm", "")
        urls = [u.strip() for u in flpth.split("@") if u.strip()] if flpth else []
        names = [n.strip() for n in file_names_raw.split("@") if n.strip()] if file_names_raw else []

        for idx, url in enumerate(urls):
            # fileNm에서 같은 인덱스의 이름이 있으면 사용, 없으면 URL 파싱 fallback
            if idx < len(names) and names[idx]:
                file_name = names[idx]
                ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "unknown"
            else:
                parsed = urlparse(url)
                path_name = unquote(parsed.path.split("/")[-1])
                if path_name.endswith(".do") or not path_name or "." not in path_name:
                    qs = parse_qs(parsed.query)
                    atch_id = qs.get("atchFileId", [""])[0]
                    file_sn = qs.get("fileSn", [str(idx)])[0]
                    file_name = f"{atch_id}_{file_sn}" if atch_id else f"attachment_{idx}"
                    ext = "unknown"
                else:
                    file_name = path_name
                    ext = file_name.rsplit(".", 1)[-1].lower()

            attachments.append({
                "file_name": file_name,
                "file_type": ext,
                "download_url": url,
            })

        # 지역명: API에 별도 필드 없어서 제목의 [지역] 패턴에서 추출
        title = raw.get("pblancNm", "")
        m = re.search(r"\[(.+?)\]", title)
        region = m.group(1) if m else None

        # 접수기간 파싱: "시작~종료" 형식 분리
        period_start = None
        period_end = None
        period_raw = raw.get("reqstBeginEndDe", "")
        if period_raw and "~" in period_raw:
            parts = period_raw.split("~", maxsplit=1)
            period_start = parts[0].strip() or None
            period_end = parts[1].strip() or None
        else:
            period_start = period_raw.strip() or None

        return {
            "source": "bizinfo",
            "source_id": raw.get("pblancId", ""),
            "title": title,
            "organization": raw.get("jrsdInsttNm"),
            "executor": raw.get("excInsttNm"),
            "period_start": period_start,
            "period_end": period_end,
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
        print(json.dumps(items[5], ensure_ascii=False, indent=2, default=str))
