"""자격요건 API 통합 테스트.

- TestClient + 실 PostgreSQL 테스트 DB
- Celery `.delay`는 monkeypatch로 가짜화
"""
import uuid
from unittest.mock import MagicMock

import pytest

from app.models.announcement import Announcement
from app.models.eligibility import EligibilityResult, ExclusionResult


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_announcement(db, title="테스트 공고") -> Announcement:
    ann = Announcement(
        source="bizinfo",
        source_id=f"TEST-{uuid.uuid4().hex[:8]}",
        title=title,
        extraction_status="done",
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


# ---------------------------------------------------------------------------
# GET /api/eligibility/{announcement_id}
# ---------------------------------------------------------------------------

class TestGetEligibility:

    def test_400_when_invalid_uuid(self, client):
        response = client.get("/api/eligibility/not-a-uuid")
        assert response.status_code == 400

    def test_404_when_announcement_not_found(self, client):
        response = client.get(f"/api/eligibility/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_fields_and_exclusions_returned(self, client, db_session):
        ann = _make_announcement(db_session, title="자격요건 풍부한 공고")

        db_session.add(EligibilityResult(
            announcement_id=ann.id,
            field_name="업력",
            condition_value="3년 미만",
            condition_parsed={"value": 3, "operator": "미만"},
            evidence="창업 후 3년 미만",
            evidence_source="첨부파일 1p",
            processing_path="text_llm",
        ))
        db_session.add(EligibilityResult(
            announcement_id=ann.id,
            field_name="지역",
            condition_value="강원도 소재",
            condition_parsed={"value": "강원", "operator": "소재"},
            evidence="강원도 소재 기업",
            evidence_source="본문 1p",
            processing_path="rule_based",
        ))
        db_session.add(ExclusionResult(
            announcement_id=ann.id,
            exclusion_text="휴폐업 기업",
            evidence_source="첨부파일 2p",
            processing_path="text_llm",
        ))
        db_session.commit()

        response = client.get(f"/api/eligibility/{ann.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["announcement_id"] == str(ann.id)
        assert body["title"] == "자격요건 풍부한 공고"
        assert len(body["fields"]) == 2
        names = {f["field_name"] for f in body["fields"]}
        assert names == {"업력", "지역"}
        assert len(body["exclusions"]) == 1
        assert body["exclusions"][0]["text"] == "휴폐업 기업"


# ---------------------------------------------------------------------------
# POST /api/eligibility/{announcement_id}/extract
# ---------------------------------------------------------------------------

class TestTriggerExtract:

    def test_404_when_announcement_not_found(self, client, monkeypatch):
        from app.worker import tasks
        fake_task = MagicMock(id="should-not-be-used")
        monkeypatch.setattr(
            tasks.extract_announcement_eligibility, "delay", lambda *a, **k: fake_task
        )

        response = client.post(f"/api/eligibility/{uuid.uuid4()}/extract")
        assert response.status_code == 404

    def test_returns_task_id(self, client, db_session, monkeypatch):
        ann = _make_announcement(db_session)

        from app.worker import tasks
        fake_task = MagicMock(id="fake-extract-task-id")
        monkeypatch.setattr(
            tasks.extract_announcement_eligibility, "delay", lambda *a, **k: fake_task
        )

        response = client.post(f"/api/eligibility/{ann.id}/extract")
        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == "fake-extract-task-id"
        assert "추출 작업" in body["message"]


# ---------------------------------------------------------------------------
# POST /api/eligibility/extract-all
# ---------------------------------------------------------------------------

class TestTriggerExtractAll:

    def test_returns_task_id(self, client, monkeypatch):
        from app.worker import tasks
        fake_task = MagicMock(id="fake-extract-all-task-id")
        monkeypatch.setattr(
            tasks.extract_all_pending_eligibility, "delay", lambda *a, **k: fake_task
        )

        response = client.post("/api/eligibility/extract-all")
        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == "fake-extract-all-task-id"
        assert "전체 추출 작업" in body["message"]
