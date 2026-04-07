from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """3소스(기업마당/K-Startup/중기부) 수집기 공통 인터페이스.

    각 소스별 구현체는 이 클래스를 상속하여 collect_all() 을 구현한다.
    반환되는 dict는 announcements 테이블의 컬럼명에 맞춰 정규화된 형태여야 한다.
    """

    source_name: str  # "bizinfo" / "kstartup" / "mss"

    @abstractmethod
    def collect_all(self) -> list[dict[str, Any]]:
        """전체 공고 수집.

        Returns:
            list of dict. 각 dict는 다음 키를 포함해야 함:
                - source: str (소스명, 고정값)
                - source_id: str (소스별 고유 ID)
                - title: str
                - organization: str | None
                - executor: str | None
                - period_start: date | None
                - period_end: date | None
                - target_text: str | None
                - exclusion_text: str | None
                - category: str | None
                - region: str | None
                - detail_url: str | None
                - raw_api_data: dict (원본 응답 전체, 디버깅용)
                - attachments: list[dict] (첨부파일 정보)
                    - file_name: str
                    - file_type: str ("hwp" / "hwpx" / "pdf" / "zip")
                    - download_url: str
        """
        ...

    def normalize(self, raw: dict) -> dict:
        """소스별 원본 응답 → 통합 스키마로 정규화.

        각 구현체에서 필요 시 오버라이드.
        """
        return raw
