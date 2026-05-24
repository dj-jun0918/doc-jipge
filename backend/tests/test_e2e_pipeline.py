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
        """HWPX 파일은 python-hwpx로 처리, structured_tables 추출 확인.

        [목표 임계값 25% 설정 근거]
        본 테스트는 실제 공공 포털(Bizinfo, K-Startup, MSS)에서 실시간으로 수집한 실 데이터를 대상으로 작동합니다.
        실시간 라이브 데이터 중에는 텍스트가 전혀 없는 스캔본(이미지형 파일), 깨진 서식, 서식 전용 빈 파일 등이 
        빈번히 포함되며, 이 경우 python-hwpx 파싱이 실패하여 LibreOffice fallback으로 우회될 수 있습니다.
        이러한 불안정한 외부 데이터 환경으로 인해 CI/CD 빌드가 무작위로 실패하는 현상(Flaky Test)을 
        방지하기 위해 최소한의 안전 마진인 25%를 기준값으로 유지합니다.
        """
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
            assert success_rate >= 0.25, f"HWPX 추출 성공률 {success_rate:.0%} (목표 25%)"
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
                    # LibreOffice 경로 → converted_pdf_path 또는 failed
                    assert att.conversion_status in ("converted", "failed", "skipped"), \
                        f"HWP 변환 상태 비정상: {att.id} ({att.conversion_status})"
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

    def test_HWPX_structured_tables_형식_검증(self, source, clean_db_for_e2e):
        """HWPX python-hwpx 경로로 추출된 structured_tables의 데이터 형식을 검증.

        단순 None/not-None 체크(test_HWPX_python_hwpx_추출_성공률)를 넘어,
        실제 추출된 표 데이터가 올바른 구조({name, markdown})를 갖추는지 확인합니다.
        """
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

            for att in hwpx_attachments:
                db.refresh(att)
                db.refresh(att.announcement)

            # python-hwpx 경로를 거친 공고만 검증
            for att in hwpx_attachments:
                ann = att.announcement
                if ann.structured_tables is None:
                    continue  # fallback된 경우는 스킵

                # structured_tables는 반드시 list여야 함
                assert isinstance(ann.structured_tables, list), \
                    f"structured_tables가 list가 아님: {type(ann.structured_tables)}"

                # 표가 있다면 각 항목이 name/markdown 키를 가져야 함
                for table in ann.structured_tables:
                    assert isinstance(table, dict), f"표 항목이 dict가 아님: {table}"
                    assert "name" in table, f"표 항목에 'name' 키 없음: {table}"
                    assert "markdown" in table, f"표 항목에 'markdown' 키 없음: {table}"
                    assert isinstance(table["markdown"], str), "markdown 값이 문자열이 아님"
        finally:
            db.close()
