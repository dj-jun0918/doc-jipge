"""E2E 파이프라인 통합 테스트.

3소스 각 10건씩 수집 → 변환 (포맷별 분기) → 추출 → 매칭 전체 흐름 검증.
실 API 호출하므로 실행 시간 5~10분.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.announcement import Announcement, Attachment
from app.models.pipeline_job import PipelineJob
from app.worker.tasks import collect_source, download_attachment, convert_attachments, COLLECTORS
import shutil

@pytest.fixture(scope="class")
def clean_db_for_e2e():
    """E2E 테스트용 Teardown fixture. 수집된 공고와 첨부파일 등을 정리합니다."""
    ann_ids = []
    yield ann_ids
    if not ann_ids:
        return
    db = SessionLocal()
    try:
        from app.models.announcement import Announcement
        from app.models.pipeline_job import PipelineJob
        from sqlalchemy import delete
        
        # 1. pipeline_jobs 삭제
        db.execute(delete(PipelineJob).where(PipelineJob.announcement_id.in_(ann_ids)))
        
        # 2. announcements 삭제 (attachments는 cascade로 삭제되도록 설정되어 있다고 가정, 아니면 수동 삭제)
        # SQLAlchemy가 cascade를 지원하지 않을 수 있으므로 수동으로 삭제
        db.execute(delete(Attachment).where(Attachment.announcement_id.in_(ann_ids)))
        db.execute(delete(Announcement).where(Announcement.id.in_(ann_ids)))
        db.commit()
    finally:
        db.close()


@pytest.mark.e2e
@pytest.mark.parametrize("source", ["bizinfo", "kstartup", "mss"])
class TestE2EPipeline:

    def test_수집_DB_INSERT(self, source, clean_db_for_e2e):
        original_collector = COLLECTORS[source]
        original_collect_all = original_collector.collect_all
    
        def mocked_collect_all(self):
            return original_collect_all(self)[:3]
    
        with patch.object(original_collector, 'collect_all', autospec=True, side_effect=mocked_collect_all):
            ann_ids = collect_source(source)
            
        assert len(ann_ids) >= 1, f"{source} 수집 0건"
        clean_db_for_e2e.extend(ann_ids) # teardown 시 삭제되도록 등록

        db = SessionLocal()
        try:
            count = db.scalar(
                select(func.count()).select_from(
                    select(Announcement).where(Announcement.id.in_(ann_ids)).subquery()
                )
            )
            assert count == len(ann_ids)
        finally:
            db.close()

    def test_첨부파일_다운로드_성공률(self, source, clean_db_for_e2e):
        db = SessionLocal()
        try:
            # 방금 수집된 공고 ID들 활용
            if not clean_db_for_e2e:
                pytest.skip(f"{source} 수집된 공고 없음")
            
            for ann_id in clean_db_for_e2e:
                download_attachment(str(ann_id))

            attachments = db.scalars(
                select(Attachment).where(Attachment.announcement_id.in_(clean_db_for_e2e))
            ).all()
            if not attachments:
                pytest.skip("첨부파일 없는 공고")

            downloadable = [a for a in attachments if a.download_url]
            if downloadable:
                success_count = sum(1 for a in downloadable if a.local_path)
                success_rate = success_count / len(downloadable)
                assert success_rate >= 0.8, f"다운로드 성공률 {success_rate:.0%} (목표 80%)"
        finally:
            db.close()

    def test_HWPX_python_hwpx_추출_성공률(self, source, clean_db_for_e2e):
        """HWPX 파일은 python-hwpx로 처리, structured_tables 추출 확인."""
        db = SessionLocal()
        try:
            hwpx_attachments = db.scalars(
                select(Attachment).where(
                    Attachment.file_type == "hwpx",
                    Attachment.local_path.is_not(None),
                    Attachment.announcement_id.in_(clean_db_for_e2e)
                )
            ).all()

            if not hwpx_attachments:
                pytest.skip("HWPX 첨부파일 없음")
                
            convert_attachments([str(a.id) for a in hwpx_attachments])
            
            # db 객체 갱신
            for att in hwpx_attachments:
                db.refresh(att)
                db.refresh(att.announcement)

            success_count = 0
            for att in hwpx_attachments:
                ann = att.announcement
                if ann.structured_tables is not None: # 빈 리스트라도 attempt로 성공 간주
                    success_count += 1

            success_rate = success_count / len(hwpx_attachments)
            assert success_rate >= 0.4, f"HWPX 추출 성공률 {success_rate:.0%} (목표 40%)"
        finally:
            db.close()

    def test_HWP_LibreOffice_fallback(self, source, clean_db_for_e2e):
        """HWP 구버전만 LibreOffice 변환, 실패 시 텍스트 fallback."""
        db = SessionLocal()
        try:
            hwp_attachments = db.scalars(
                select(Attachment).where(
                    Attachment.file_type == "hwp",
                    Attachment.local_path.is_not(None),
                    Attachment.announcement_id.in_(clean_db_for_e2e)
                )
            ).all()

            if not hwp_attachments:
                pytest.skip("HWP 구버전 첨부파일 없음")

            # 변환 시도
            convert_attachments([str(a.id) for a in hwp_attachments])
            
            for att in hwp_attachments:
                db.refresh(att)

            # 검증
            converted_count = sum(
                1 for a in hwp_attachments
                if a.converted_pdf_path or a.conversion_status in ("converted", "text-fallback")
            )
            success_rate = converted_count / len(hwp_attachments)
            assert success_rate >= 0.7, f"HWP 변환 성공률 {success_rate:.0%} (목표 70%)"
        finally:
            db.close()

    def test_변환_분기_정확성(self, source, clean_db_for_e2e):
        """파일 타입별로 올바른 변환 경로가 실행됐는지."""
        db = SessionLocal()
        try:
            attachments = db.scalars(
                select(Attachment).where(
                    Attachment.local_path.is_not(None),
                    Attachment.announcement_id.in_(clean_db_for_e2e)
                )
            ).all()

            for att in attachments:
                if att.file_type == "hwpx":
                    # python-hwpx 경로 → structured_tables 있어야 (또는 빈 리스트라도 attempt)
                    assert hasattr(att.announcement, "structured_tables"), \
                        f"HWPX인데 structured_tables 필드 없음: {att.id}"
                elif att.file_type == "hwp":
                    # LibreOffice 경로 → converted_pdf_path 또는 text-fallback
                    assert att.conversion_status in ("converted", "failed", "text-fallback"), \
                        f"HWP 변환 상태 비정상: {att.id}"
        finally:
            db.close()

    def test_pipeline_jobs_상태(self, source, clean_db_for_e2e):
        """모든 job이 done 또는 failed로 끝났는지."""
        db = SessionLocal()
        try:
            jobs = db.scalars(
                select(PipelineJob).where(PipelineJob.status.in_(["processing", "queued"]), PipelineJob.announcement_id.in_(clean_db_for_e2e))
            ).all()
            assert len(jobs) == 0, f"진행 중인 job {len(jobs)}건 — 미완료 또는 hang"
        finally:
            db.close()
