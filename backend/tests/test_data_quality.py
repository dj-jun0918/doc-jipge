"""test_data_quality.py — 데이터 품질 검사 도구 및 API 단위/통합 테스트."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.announcement import Announcement, Attachment
from app.tools.data_quality import (
    _empty_title,
    _short_target_text,
    _no_attachments,
    _download_failed,
    _conversion_failed,
    _extraction_failed,
    _duplicate_suspected,
    check_announcements,
)

@pytest.fixture
def mock_db():
    return MagicMock()

def test_empty_title(mock_db):
    # 빈 제목 테스트
    mock_db.scalars.return_value.all.return_value = ["uuid-1", "uuid-2"]
    
    res = _empty_title(mock_db)
    assert res == ["uuid-1", "uuid-2"]
    mock_db.scalars.assert_called_once()

def test_short_target_text(mock_db):
    # 짧은 본문 테스트
    mock_db.scalars.return_value.all.return_value = ["uuid-3"]
    
    res = _short_target_text(mock_db)
    assert res == ["uuid-3"]
    mock_db.scalars.assert_called_once()

def test_no_attachments(mock_db):
    # 첨부파일 없음 테스트
    mock_db.scalars.return_value.all.return_value = ["uuid-4", "uuid-5"]
    
    res = _no_attachments(mock_db)
    assert res == ["uuid-4", "uuid-5"]
    mock_db.scalars.assert_called_once()

def test_download_failed(mock_db):
    # 다운로드 실패 테스트
    mock_db.scalars.return_value.all.return_value = ["uuid-6"]
    
    res = _download_failed(mock_db)
    assert res == ["uuid-6"]
    mock_db.scalars.assert_called_once()

def test_conversion_failed(mock_db):
    # 변환 실패 테스트
    mock_db.scalars.return_value.all.return_value = ["uuid-7"]
    
    res = _conversion_failed(mock_db)
    assert res == ["uuid-7"]
    mock_db.scalars.assert_called_once()

def test_extraction_failed(mock_db):
    # 추출 실패 테스트
    mock_db.scalars.return_value.all.return_value = ["uuid-8"]
    
    res = _extraction_failed(mock_db)
    assert res == ["uuid-8"]
    mock_db.scalars.assert_called_once()

def test_duplicate_suspected(mock_db):
    # 의심 중복 테스트
    ann_a = MagicMock()
    ann_a.id = "uuid-a"
    ann_a.title = "2026년 청년 창업 지원 사업 공고"
    ann_a.created_at = datetime.now()
    
    ann_b = MagicMock()
    ann_b.id = "uuid-b"
    ann_b.title = "2026년 청년 창업 지원 사업 공고(추가)"
    ann_b.created_at = datetime.now() + timedelta(days=2) # 7일 이내
    
    # SequenceMatcher ratio: ~0.93 -> 90% 이상으로 잡혀야 함
    mock_db.scalars.return_value.all.return_value = [ann_a, ann_b]
    
    res = _duplicate_suspected(mock_db)
    assert len(res) == 1
    assert res[0]["ann_a"] == "uuid-a"
    assert res[0]["ann_b"] == "uuid-b"
    assert res[0]["similarity"] >= 0.90

@patch("app.tools.data_quality._empty_title", return_value=["id1"])
@patch("app.tools.data_quality._short_target_text", return_value=["id2"])
@patch("app.tools.data_quality._no_attachments", return_value=[])
@patch("app.tools.data_quality._download_failed", return_value=[])
@patch("app.tools.data_quality._conversion_failed", return_value=[])
@patch("app.tools.data_quality._extraction_failed", return_value=["id3"])
@patch("app.tools.data_quality._duplicate_suspected", return_value=[])
def test_check_announcements(
    mock_dup, mock_ext, mock_conv, mock_down, mock_no_att, mock_short, mock_empty, mock_db
):
    mock_db.scalar.return_value = 100 # 전체 공고 수
    
    report = check_announcements(mock_db)
    assert report["total"] == 100
    assert report["issues"]["empty_title"] == ["id1"]
    assert report["issues"]["short_target_text"] == ["id2"]
    assert report["issues"]["extraction_failed"] == ["id3"]
    assert report["issues"]["no_attachments"] == []
    assert "checked_at" in report

def test_quality_report_api(client: TestClient, db_session: Session):
    # API 엔드포인트 통합 호출 테스트
    ann = Announcement(
        source="kstartup",
        source_id="t-quality-1",
        title="",  # empty title
        target_text="짧음",  # short target text
    )
    db_session.add(ann)
    db_session.flush()
    
    res = client.get("/api/quality/report")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert str(ann.id) in body["issues"]["empty_title"]
    assert str(ann.id) in body["issues"]["short_target_text"]
    assert "checked_at" in body
