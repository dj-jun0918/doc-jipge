"""announcement detail API 통합 테스트."""
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.announcement import Announcement, Attachment


def test_detail_response_flattens_attachments_and_structured_tables(
    client: TestClient, db_session: Session
):
    """GET /api/announcements/{id} 응답 검증.

    - attachments[]에 평탄화: id/file_name/file_type/has_pdf 포함
    - converted_pdf_path는 응답에서 exclude (내부 경로 노출 방지)
    - has_pdf 계산: pdf→True, hwp+converted_pdf_path→True, hwpx→False
    - structured_tables 응답 포함
    """
    ann = Announcement(
        source="kstartup",
        source_id="t-detail-1",
        title="테스트 공고",
        structured_tables=[{"name": "표_1", "markdown": "| a | b |"}],
    )
    db_session.add(ann)
    db_session.flush()

    db_session.add_all([
        Attachment(
            announcement_id=ann.id,
            file_name="공고.pdf",
            file_type="pdf",
            local_path="/app/storage/공고.pdf",
        ),
        Attachment(
            announcement_id=ann.id,
            file_name="공고.hwp",
            file_type="hwp",
            local_path="/app/storage/공고.hwp",
            converted_pdf_path="/app/storage/공고.pdf",
        ),
        Attachment(
            announcement_id=ann.id,
            file_name="첨부.hwpx",
            file_type="hwpx",
            local_path="/app/storage/첨부.hwpx",
        ),
    ])
    db_session.flush()

    res = client.get(f"/api/announcements/{ann.id}")
    assert res.status_code == 200
    body = res.json()

    # 평탄화 검증
    assert len(body["attachments"]) == 3
    by_type = {a["file_type"]: a for a in body["attachments"]}

    # has_pdf 계산 검증
    assert by_type["pdf"]["has_pdf"] is True
    assert by_type["hwp"]["has_pdf"] is True
    assert by_type["hwpx"]["has_pdf"] is False

    # converted_pdf_path 응답에서 exclude (내부 경로 노출 방지)
    for att in body["attachments"]:
        assert "converted_pdf_path" not in att
        assert "local_path" not in att

    # structured_tables 응답 포함
    assert body["structured_tables"] == [{"name": "표_1", "markdown": "| a | b |"}]


def test_list_response_excludes_attachments_and_structured_tables(
    client: TestClient, db_session: Session
):
    """GET /api/announcements/ 목록 응답은 attachments/structured_tables 미포함 (응답 가벼움)."""
    ann = Announcement(
        source="kstartup",
        source_id="t-list-1",
        title="목록 테스트",
        structured_tables=[{"name": "표_1", "markdown": "..."}],
    )
    db_session.add(ann)
    db_session.flush()  # ann.id 확보

    db_session.add(Attachment(
        announcement_id=ann.id,
        file_name="공고.pdf",
        file_type="pdf",
        local_path="/app/storage/공고.pdf",
    ))
    db_session.flush()

    res = client.get("/api/announcements/")
    assert res.status_code == 200
    body = res.json()
    item = next(a for a in body["items"] if a["source_id"] == "t-list-1")
    assert "attachments" not in item
    assert "structured_tables" not in item


def test_detail_404_for_missing_id(client: TestClient):
    res = client.get("/api/announcements/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_sort_deadline_orders_by_period_end_excludes_closed(
    client: TestClient, db_session: Session
):
    """sort=deadline — 마감 임박순(가까운 순), 이미 마감된 공고 제외, 미정(NULL)은 맨 뒤."""
    today = date.today()
    db_session.add_all([
        Announcement(source="kstartup", source_id="sd-past", title="마감지남",
                     period_end=today - timedelta(days=5)),
        Announcement(source="kstartup", source_id="sd-soon", title="임박",
                     period_end=today + timedelta(days=3)),
        Announcement(source="kstartup", source_id="sd-later", title="여유",
                     period_end=today + timedelta(days=30)),
        Announcement(source="kstartup", source_id="sd-none", title="미정",
                     period_end=None),
    ])
    db_session.flush()

    res = client.get("/api/announcements/?sort=deadline&limit=100")
    assert res.status_code == 200
    ours = [a["source_id"] for a in res.json()["items"] if a["source_id"].startswith("sd-")]

    assert "sd-past" not in ours  # 이미 마감 → 제외
    assert ours.index("sd-soon") < ours.index("sd-later")  # 임박이 먼저
    assert ours.index("sd-later") < ours.index("sd-none")  # 미정(NULL)은 맨 뒤

