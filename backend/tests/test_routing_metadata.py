"""test_routing_metadata.py — tasks.py 내 routing_metadata 저장 및 통합 테스트."""

import pytest
import uuid
from unittest.mock import MagicMock, patch

from app.worker import tasks
from app.config import settings

@pytest.fixture
def mock_announcement():
    ann = MagicMock()
    ann.id = uuid.uuid4()
    ann.source_id = "ann_001"
    ann.title = "테스트 지원사업"
    ann.target_text = "대상 요건"
    ann.exclusion_text = "제외 요건"
    ann.attachments = []
    ann.structured_tables = []
    ann.extraction_status = "pending"
    # MagicMock의 기본 속성 자동 생성을 방지하여 hasattr 가드가 정상 동작하도록 제거
    if hasattr(ann, "routing_metadata"):
        del ann.routing_metadata
    return ann

@pytest.fixture
def mock_eligibility_result():
    res = MagicMock()
    res.fields = []
    res.exclusions = []
    return res

@patch("app.worker.tasks.SessionLocal")
@patch("app.worker.tasks._create_job")
@patch("app.worker.tasks._finish_job")
@patch("app.worker.tasks.asyncio.run")
def test_extract_eligibility_task_routing_disabled(
    mock_async_run, mock_finish, mock_create, mock_session, mock_announcement, mock_eligibility_result
):
    # settings.cost_routing_enabled = False 인 경우 기존 흐름 동작 검증
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    mock_db.get.return_value = mock_announcement
    
    mock_async_run.return_value = mock_eligibility_result
    
    with patch.object(settings, "cost_routing_enabled", False), \
         patch("app.extractor.hybrid_engine.extract_eligibility") as mock_extract:
         
        tasks.extract_announcement_eligibility("test_id")
        
        # 1. hybrid_engine이 routing_meta=None으로 호출되었는지 검증
        mock_extract.assert_called_once()
        args, kwargs = mock_extract.call_args
        assert kwargs.get("routing_meta") is None
        
        # 2. routing_metadata 속성이 기록되지 않았는지 검증
        assert not hasattr(mock_announcement, "routing_metadata")

@patch("app.worker.tasks.SessionLocal")
@patch("app.worker.tasks._create_job")
@patch("app.worker.tasks._finish_job")
@patch("app.worker.tasks.asyncio.run")
def test_extract_eligibility_task_routing_enabled_with_hasattr(
    mock_async_run, mock_finish, mock_create, mock_session, mock_announcement, mock_eligibility_result
):
    # settings.cost_routing_enabled = True 이고, Announcement에 routing_metadata 컬럼이 정의된 상황
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    mock_db.get.return_value = mock_announcement
    mock_async_run.return_value = mock_eligibility_result
    
    # 가상의 routing_metadata 컬럼 선언
    setattr(mock_announcement, "routing_metadata", None)
    
    # cost_router.route 결과를 모킹
    fake_meta = {"chosen_path": "text_llm", "cost_estimate_usd": 0.001}
    
    with patch.object(settings, "cost_routing_enabled", True), \
         patch("app.extractor.cost_router.route", return_value=fake_meta) as mock_route, \
         patch("app.extractor.hybrid_engine.extract_eligibility") as mock_extract:
         
        tasks.extract_announcement_eligibility("test_id")
        
        # 1. cost_router.route가 호출되었는지
        mock_route.assert_called_once_with(mock_announcement)
        
        # 2. hybrid_engine 호출 시 routing_meta가 인자로 들어갔는지 검증
        mock_extract.assert_called_once()
        args, kwargs = mock_extract.call_args
        assert kwargs.get("routing_meta") == fake_meta
        
        # 3. ann.routing_metadata에 저장되었는지 검증
        assert mock_announcement.routing_metadata == fake_meta

@patch("app.worker.tasks.SessionLocal")
@patch("app.worker.tasks._create_job")
@patch("app.worker.tasks._finish_job")
@patch("app.worker.tasks.asyncio.run")
def test_extract_eligibility_task_routing_enabled_without_hasattr(
    mock_async_run, mock_finish, mock_create, mock_session, mock_announcement, mock_eligibility_result
):
    # settings.cost_routing_enabled = True 이지만, Announcement에 아직 routing_metadata 컬럼이 없는 상황
    # hasattr 가드 작동으로 인해 AttributeError가 나지 않고 정상 저장 스킵 후 성공해야 함
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    mock_db.get.return_value = mock_announcement
    mock_async_run.return_value = mock_eligibility_result
    
    # Announcement 모델에 routing_metadata 컬럼 미존재 상태 보장
    if hasattr(mock_announcement, "routing_metadata"):
        delattr(mock_announcement, "routing_metadata")
        
    fake_meta = {"chosen_path": "text_llm", "cost_estimate_usd": 0.001}
    
    with patch.object(settings, "cost_routing_enabled", True), \
         patch("app.extractor.cost_router.route", return_value=fake_meta) as mock_route, \
         patch("app.extractor.hybrid_engine.extract_eligibility") as mock_extract:
         
        # AttributeError 없이 정상 종료되어야 함
        res = tasks.extract_announcement_eligibility("test_id")
        assert res["status"] == "ok"
        
        # 속성 추가되지 않은 상태 유지 검증
        assert not hasattr(mock_announcement, "routing_metadata")
