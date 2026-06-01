"""매칭 API 통합 테스트.

- TestClient + 실 PostgreSQL 테스트 DB
- Celery `.delay`는 monkeypatch로 가짜화 (실제 워커 호출 없음)
"""
import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.models.announcement import Announcement
from app.models.company import Company
from app.models.match_result import MatchResult


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_company(db, **kwargs) -> Company:
    defaults = dict(
        name="테스트 기업",
        founded_date=date(2023, 1, 1),
        revenue=500_000_000,
        region="서울",
        industry="소프트웨어 개발",
        employee_count=10,
        ceo_birth_date=date(1990, 1, 1),
    )
    defaults.update(kwargs)
    company = Company(**defaults)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _make_announcement(db, title="테스트 공고", source="bizinfo", source_id=None) -> Announcement:
    ann = Announcement(
        source=source,
        source_id=source_id or f"TEST-{uuid.uuid4().hex[:8]}",
        title=title,
        extraction_status="done",
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


def _make_match_result(
    db, announcement_id, company_id,
    field_name="업력", status="충족",
    company_value="3년", requirement_value="3년 미만",
    processing_path="text_llm",
):
    mr = MatchResult(
        announcement_id=announcement_id,
        company_id=company_id,
        field_name=field_name,
        status=status,
        company_value=company_value,
        requirement_value=requirement_value,
        evidence="테스트 evidence",
        processing_path=processing_path,
    )
    db.add(mr)
    db.commit()
    return mr


# ---------------------------------------------------------------------------
# GET /api/matching/{company_id}
# ---------------------------------------------------------------------------

class TestGetMatchingResults:

    def test_400_when_invalid_uuid(self, client):
        response = client.get("/api/matching/not-a-uuid")
        assert response.status_code == 400
        assert "company_id" in response.json()["detail"]

    def test_404_when_company_not_found(self, client):
        response = client.get(f"/api/matching/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_empty_when_no_match_results(self, client, db_session):
        company = _make_company(db_session)

        response = client.get(f"/api/matching/{company.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["company_id"] == str(company.id)
        assert body["items"] == []
        assert body["total"] == 0

    def test_sorted_by_fulfillment_ratio_desc(self, client, db_session):
        """충족 비율 높은 순으로 정렬되어야 한다."""
        company = _make_company(db_session)
        ann_high = _make_announcement(db_session, title="HIGH")
        ann_low = _make_announcement(db_session, title="LOW")

        # HIGH: 충족 2, 미충족 0 → score 1.0
        for _ in range(2):
            _make_match_result(db_session, ann_high.id, company.id, status="충족")
        # LOW: 충족 1, 미충족 3 → score 0.25
        _make_match_result(db_session, ann_low.id, company.id, status="충족")
        for _ in range(3):
            _make_match_result(db_session, ann_low.id, company.id, status="미충족")

        response = client.get(f"/api/matching/{company.id}")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2
        assert items[0]["title"] == "HIGH"
        assert items[0]["match_score"] == 1.0
        assert items[0]["fulfilled_count"] == 2
        assert items[1]["title"] == "LOW"
        assert items[1]["match_score"] == 0.25

    def test_continuous_score_reflects_확인필요(self, client, db_session):
        """확인필요는 충족(1.0)과 미충족(0.0) 사이 부분점수(0.3)로 총점에 반영."""
        company = _make_company(db_session)
        ann = _make_announcement(db_session, title="MIXED")
        _make_match_result(db_session, ann.id, company.id, field_name="업력", status="충족")
        _make_match_result(db_session, ann.id, company.id, field_name="매출", status="확인필요")

        response = client.get(f"/api/matching/{company.id}")
        items = response.json()["items"]
        # (1.0 + 0.3) / 2 = 0.65 — 단순 충족비율(0.5)과 구분됨
        assert items[0]["match_score"] == 0.65

    def test_limit_caps_returned_items(self, client, db_session):
        company = _make_company(db_session)
        for i in range(5):
            ann = _make_announcement(db_session, title=f"공고 {i}", source_id=f"S-{i}")
            _make_match_result(db_session, ann.id, company.id, status="충족")

        response = client.get(f"/api/matching/{company.id}?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5  # 전체 개수는 그대로


# ---------------------------------------------------------------------------
# GET /api/matching/{company_id}/export
# ---------------------------------------------------------------------------

class TestExportMatchingResults:

    def test_404_when_company_not_found(self, client):
        response = client.get(f"/api/matching/{uuid.uuid4()}/export")
        assert response.status_code == 404

    def test_export_csv_success(self, client, db_session):
        company = _make_company(db_session, name="가나다")
        ann = _make_announcement(db_session)
        _make_match_result(db_session, ann.id, company.id, status="충족")

        response = client.get(f"/api/matching/{company.id}/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "filename*=UTF-8''matching_%EA%B0%80%EB%82%98%EB%8B%A4" in response.headers["content-disposition"]
        # UTF-8 BOM과 함께 헤더가 포함되는지 확인
        content = response.content.decode("utf-8")
        assert content.startswith("\ufeff")
        assert "점수,거리,제약" in content

    def test_export_xlsx_success(self, client, db_session):
        company = _make_company(db_session)
        ann = _make_announcement(db_session)
        _make_match_result(db_session, ann.id, company.id, status="충족")

        response = client.get(f"/api/matching/{company.id}/export?format=xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        assert response.content.startswith(b"PK")  # Excel 파일 시그니처


# ---------------------------------------------------------------------------
# GET /api/matching/{company_id}/{announcement_id}
# ---------------------------------------------------------------------------

class TestGetMatchingDetail:

    def test_400_when_invalid_uuid(self, client):
        response = client.get(f"/api/matching/bad/{uuid.uuid4()}")
        assert response.status_code == 400

    def test_empty_with_null_matched_at_when_no_results(self, client, db_session):
        """매칭 미실행 케이스 — 빈 items + matched_at=None (방정우 안내 메시지 트리거)."""
        company = _make_company(db_session)
        ann = _make_announcement(db_session)

        response = client.get(f"/api/matching/{company.id}/{ann.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["matched_at"] is None
        assert body["stats"] == {"충족": 0, "미충족": 0, "확인필요": 0, "해당없음": 0}

    def test_items_and_stats_correctness(self, client, db_session):
        company = _make_company(db_session)
        ann = _make_announcement(db_session)
        _make_match_result(db_session, ann.id, company.id, field_name="업력", status="충족")
        _make_match_result(db_session, ann.id, company.id, field_name="지역", status="미충족")
        _make_match_result(db_session, ann.id, company.id, field_name="매출", status="확인필요")

        response = client.get(f"/api/matching/{company.id}/{ann.id}")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 3
        assert body["stats"] == {"충족": 1, "미충족": 1, "확인필요": 1, "해당없음": 0}
        assert body["matched_at"] is not None
        # 필드 데이터 점검
        names = {item["field_name"] for item in body["items"]}
        assert names == {"업력", "지역", "매출"}


# ---------------------------------------------------------------------------
# POST /api/matching/{company_id}/run
# ---------------------------------------------------------------------------

class TestTriggerMatching:

    def test_404_when_company_not_found(self, client, monkeypatch):
        from app.worker import tasks
        fake_task = MagicMock(id="should-not-be-used")
        monkeypatch.setattr(
            tasks.match_company_announcements, "delay", lambda *a, **k: fake_task
        )

        response = client.post(f"/api/matching/{uuid.uuid4()}/run")
        assert response.status_code == 404

    def test_returns_task_id_on_success(self, client, db_session, monkeypatch):
        company = _make_company(db_session)

        from app.worker import tasks
        fake_task = MagicMock(id="fake-celery-task-id")
        monkeypatch.setattr(
            tasks.match_company_announcements, "delay", lambda *a, **k: fake_task
        )

        response = client.post(f"/api/matching/{company.id}/run")
        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == "fake-celery-task-id"
        assert "매칭 작업" in body["message"]
