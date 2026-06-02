"""attachment API 테스트."""
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.announcement import Announcement, Attachment


def _create_ann(db_session: Session) -> Announcement:
    ann = Announcement(source="kstartup", source_id="t1", title="테스트")
    db_session.add(ann)
    db_session.flush()
    return ann


def test_invalid_uuid_returns_400(client: TestClient):
    res = client.get("/api/attachments/not-uuid/file")
    assert res.status_code == 400


def test_missing_attachment_returns_404(client: TestClient):
    res = client.get(f"/api/attachments/{uuid.uuid4()}/file")
    assert res.status_code == 404


def test_attachment_without_local_path_returns_404(client: TestClient, db_session: Session):
    ann = _create_ann(db_session)
    att = Attachment(
        announcement_id=ann.id,
        file_name="공고.pdf",
        file_type="pdf",
        local_path=None,
    )
    db_session.add(att)
    db_session.flush()

    res = client.get(f"/api/attachments/{att.id}/file")
    assert res.status_code == 404


def test_hwpx_without_converted_pdf_returns_404(client: TestClient, db_session: Session):
    """HWPX는 converted_pdf_path 없으므로 PDF 서빙 불가 (frontend EvidencePlaceholder)."""
    ann = _create_ann(db_session)
    att = Attachment(
        announcement_id=ann.id,
        file_name="공고.hwpx",
        file_type="hwpx",
        local_path="/app/storage/공고.hwpx",
        converted_pdf_path=None,
    )
    db_session.add(att)
    db_session.flush()

    res = client.get(f"/api/attachments/{att.id}/file")
    assert res.status_code == 404


def test_pdf_serves_file(client: TestClient, db_session: Session, tmp_path: Path):
    """원본 PDF — local_path에서 직접 서빙."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%fake pdf\n")

    ann = _create_ann(db_session)
    att = Attachment(
        announcement_id=ann.id,
        file_name="공고.pdf",
        file_type="pdf",
        local_path=str(pdf_file),
    )
    db_session.add(att)
    db_session.flush()

    res = client.get(f"/api/attachments/{att.id}/file")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"] == "inline"
    assert res.content.startswith(b"%PDF")


def test_hwp_serves_converted_pdf(client: TestClient, db_session: Session, tmp_path: Path):
    """HWP 구버전 — converted_pdf_path에서 서빙."""
    pdf_file = tmp_path / "converted.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%converted from hwp\n")

    ann = _create_ann(db_session)
    att = Attachment(
        announcement_id=ann.id,
        file_name="공고.hwp",
        file_type="hwp",
        local_path="/app/storage/공고.hwp",
        converted_pdf_path=str(pdf_file),
    )
    db_session.add(att)
    db_session.flush()

    res = client.get(f"/api/attachments/{att.id}/file")
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")
