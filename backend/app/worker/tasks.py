"""Celery 태스크 정의.

수집 → 첨부파일 다운로드 → HWP 변환 → 자격요건 추출 파이프라인 + 회사·공고 매칭.
각 단계마다 pipeline_jobs 테이블에 진행 상태를 기록한다.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from celery import chain, group
from sqlalchemy import delete, select
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from app.collectors.bizinfo import BizinfoCollector
from app.collectors.deduplicator import find_duplicate
from app.collectors.kstartup import KstartupCollector
from app.collectors.mss import MssCollector
from app.converters.hwp_converter import convert_to_pdf, is_hwp_file
from app.database import SessionLocal
from app.models.announcement import Announcement, Attachment
from app.models.eligibility import EligibilityResult, ExclusionResult
from app.models.match_result import MatchResult
from app.models.pipeline_job import PipelineJob
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

COLLECTORS = {
    "bizinfo": BizinfoCollector,
    "kstartup": KstartupCollector,
    "mss": MssCollector,
}

# 첨부파일 저장 루트 경로 (컨테이너 내부 경로)
STORAGE_ROOT = Path("/app/storage")


# ---------------------------------------------------------------------------
# 헬퍼: pipeline_jobs 상태 관리
# ---------------------------------------------------------------------------

def _create_job(db, job_type: str, announcement_id: str | None = None) -> PipelineJob:
    """pipeline_jobs에 새 row 생성 (status=processing)."""
    job = PipelineJob(
        job_type=job_type,
        announcement_id=uuid.UUID(announcement_id) if announcement_id else None,
        status="processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _finish_job(db, job: PipelineJob, status: str = "done", error: str | None = None):
    """pipeline_jobs row 완료 처리."""
    job.status = status
    job.finished_at = datetime.now()
    if error:
        job.error_summary = {"error": error}
    db.commit()


# ---------------------------------------------------------------------------
# 태스크 1: 소스별 수집
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.worker.tasks.collect_source")
def collect_source(self, source: str) -> list[str]:
    """소스별 수집기 실행 + DB INSERT.

    Args:
        source: "bizinfo" / "kstartup" / "mss"

    Returns:
        새로 생성된 announcement ID 리스트
    """
    if source not in COLLECTORS:
        raise ValueError(f"지원하지 않는 소스: {source}. 가능한 값: {list(COLLECTORS.keys())}")

    db = SessionLocal()
    job = _create_job(db, "collect")

    try:
        collector = COLLECTORS[source]()
        items = collector.collect_all()
        logger.info(f"[{source}] 수집 완료: {len(items)}건")

        new_ann_ids: list[str] = []
        skip_count = 0

        from sqlalchemy import select
        for item in items:
            attachments_data = item.pop("attachments", [])

            # 1. 완전 동일 공고(이미 수집됨) 확인 -> 스킵
            existing = db.scalar(
                select(Announcement).where(
                    Announcement.source == item["source"],
                    Announcement.source_id == item["source_id"],
                )
            )
            if existing:
                skip_count += 1
                continue

            # 2. 타 소스 중복 탐지 (제목 유사도 등)
            dup_id = find_duplicate(item, db)
            if dup_id:
                item["duplicate_of"] = uuid.UUID(dup_id)
                # 타 소스 중복은 DB에 넣되 duplicate_of만 표시
                # (프론트에서 필터링용)

            ann = Announcement(**item)
            db.add(ann)
            db.flush()  # ID 확보 (Attachment FK 필요)

            # 첨부파일 INSERT
            for att in attachments_data:
                db.add(Attachment(announcement_id=ann.id, **att))

            new_ann_ids.append(str(ann.id))

        db.commit()

        job.total_count = len(items)
        job.success_count = len(items) - skip_count
        job.skip_count = skip_count
        _finish_job(db, job, status="done")

        logger.info(f"[{source}] DB 저장 완료: {len(new_ann_ids)}건 (중복 {skip_count}건)")
        return new_ann_ids

    except Exception as e:
        db.rollback()
        _finish_job(db, job, status="failed", error=str(e))
        logger.error(f"[{source}] 수집 실패: {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 태스크 2: 첨부파일 다운로드
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def download_with_retry(url: str) -> bytes:
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content

@celery_app.task(bind=True, name="app.worker.tasks.download_attachment")
def download_attachment(self, announcement_id: str) -> list[str]:
    """공고의 첨부파일을 로컬에 다운로드.

    Args:
        announcement_id: 공고 UUID 문자열

    Returns:
        다운로드 완료된 attachment ID 리스트
    """
    db = SessionLocal()
    job = _create_job(db, "download", announcement_id)

    try:
        ann = db.get(Announcement, announcement_id)
        if not ann:
            _finish_job(db, job, status="failed", error=f"공고 없음: {announcement_id}")
            return []

        attachments = ann.attachments
        if not attachments:
            _finish_job(db, job, status="done")
            return []

        downloaded_ids: list[str] = []
        save_dir = STORAGE_ROOT / announcement_id
        save_dir.mkdir(parents=True, exist_ok=True)

        errors = {}
        for att in attachments:
            if not att.download_url:
                job.skip_count += 1
                continue

            try:
                content = download_with_retry(att.download_url)
                file_path = save_dir / att.file_name
                file_path.write_bytes(content)

                att.local_path = str(file_path)
                downloaded_ids.append(str(att.id))
                job.success_count += 1
                logger.info(f"  다운로드 완료: {att.file_name} ({len(content):,} bytes)")

            except Exception as e:
                att.conversion_status = "failed"
                job.fail_count += 1
                error_msg = f"{type(e).__name__}: {str(e)}"
                errors[att.file_name] = error_msg
                logger.warning(f"  다운로드 실패: {att.file_name} — {e}")

        job.total_count = len(attachments)
        db.commit()
        
        if errors:
            _finish_job(db, job, status="failed", error=str(errors))
        else:
            _finish_job(db, job, status="done")

        return downloaded_ids

    except Exception as e:
        db.rollback()
        _finish_job(db, job, status="failed", error=str(e))
        logger.error(f"다운로드 태스크 실패: {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 태스크 3: HWP → PDF 변환
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.worker.tasks.convert_hwp_to_pdf")
def convert_hwp_to_pdf(self, attachment_ids: list[str]) -> list[str]:
    """HWP/HWPX → PDF 변환. PDF는 스킵.

    Args:
        attachment_ids: download_attachment가 반환한 ID 리스트

    Returns:
        변환 완료된 PDF 경로 리스트
    """
    if not attachment_ids:
        return []

    db = SessionLocal()

    # announcement_id는 첫 번째 attachment에서 추출
    first_att = db.get(Attachment, attachment_ids[0])
    ann_id = str(first_att.announcement_id) if first_att else None
    job = _create_job(db, "convert", ann_id)

    try:
        converted_paths: list[str] = []

        for att_id in attachment_ids:
            att = db.get(Attachment, att_id)
            if not att or not att.local_path:
                job.skip_count += 1
                continue

            if not is_hwp_file(att.local_path):
                # PDF 등 변환 불필요 파일은 스킵
                att.conversion_status = "skipped"
                job.skip_count += 1
                continue

            try:
                pdf_path = convert_to_pdf(att.local_path)
                att.converted_pdf_path = str(pdf_path)
                att.conversion_status = "converted"
                converted_paths.append(str(pdf_path))
                job.success_count += 1
                logger.info(f"  변환 완료: {att.file_name} → {pdf_path}")

            except Exception as e:
                att.conversion_status = "failed"
                job.fail_count += 1
                logger.warning(f"  변환 실패: {att.file_name} — {e}")

        job.total_count = len(attachment_ids)
        db.commit()
        _finish_job(db, job, status="done")

        return converted_paths

    except Exception as e:
        db.rollback()
        _finish_job(db, job, status="failed", error=str(e))
        logger.error(f"변환 태스크 실패: {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 파이프라인: chain 연결
# ---------------------------------------------------------------------------

def trigger_full_pipeline(source: str):
    """소스 수집 후 각 공고에 대해 다운로드 + 변환 체인 실행.

    collect_source → (각 공고별) download_attachment → convert_hwp_to_pdf
    """
    # 1. 수집 먼저 실행하고 결과 대기
    result = collect_source.delay(source)
    ann_ids = result.get(timeout=300)  # 최대 5분 대기

    if not ann_ids:
        logger.info(f"[{source}] 수집 결과 없음. 파이프라인 종료.")
        return

    # 2. 각 announcement에 대해 병렬로 다운로드 → 변환 체인 실행
    pipelines = group(
        chain(
            download_attachment.s(ann_id),
            convert_hwp_to_pdf.s(),
        )
        for ann_id in ann_ids
    )
    pipelines.apply_async()
    logger.info(f"[{source}] 파이프라인 시작: {len(ann_ids)}건 공고에 대해 다운로드+변환 체인 실행")


# ---------------------------------------------------------------------------
# 태스크 4: 자격요건 추출 (개별)
# ---------------------------------------------------------------------------

def _announcement_to_dict(ann: Announcement) -> dict:
    """ORM Announcement → hybrid_engine 입력용 dict."""
    return {
        "id": str(ann.id),
        "source_id": ann.source_id,
        "title": ann.title,
        "target_text": ann.target_text or "",
        "exclusion_text": ann.exclusion_text or "",
        "raw_api_data": ann.raw_api_data or {},
        "attachments": [
            {
                "file_type": att.file_type,
                "local_path": att.local_path,
                "converted_pdf_path": att.converted_pdf_path,
            }
            for att in (ann.attachments or [])
        ],
    }


@celery_app.task(bind=True, name="app.worker.tasks.extract_announcement_eligibility")
def extract_announcement_eligibility(self, announcement_id: str) -> dict:
    """공고 1건 자격요건 추출. 기존 EligibilityResult/ExclusionResult는 삭제 후 재적재."""
    from app.extractor.hybrid_engine import extract_eligibility

    db = SessionLocal()
    job = _create_job(db, "extract", announcement_id)
    try:
        ann = db.get(Announcement, announcement_id)
        if not ann:
            _finish_job(db, job, status="failed", error=f"공고 없음: {announcement_id}")
            return {"status": "error", "reason": "announcement_not_found"}

        ann_dict = _announcement_to_dict(ann)
        result = asyncio.run(extract_eligibility(ann_dict))

        # 기존 결과 제거 (idempotent 재실행)
        db.execute(delete(EligibilityResult).where(EligibilityResult.announcement_id == ann.id))
        db.execute(delete(ExclusionResult).where(ExclusionResult.announcement_id == ann.id))

        for f in result.fields:
            db.add(EligibilityResult(
                announcement_id=ann.id,
                field_name=f.field_name,
                condition_value=f.condition.raw_text,
                condition_parsed={
                    "value": f.condition.value,
                    "operator": f.condition.operator,
                },
                evidence=f.evidence,
                evidence_source=f.evidence_source,
                processing_path=f.processing_path,
            ))

        for ex in result.exclusions:
            db.add(ExclusionResult(
                announcement_id=ann.id,
                exclusion_text=ex.text,
                evidence_source=ex.evidence_source,
                processing_path=ex.processing_path,
            ))

        ann.extraction_status = "done"
        job.total_count = len(result.fields) + len(result.exclusions)
        job.success_count = job.total_count
        db.commit()
        _finish_job(db, job, status="done")

        return {
            "status": "ok",
            "announcement_id": str(ann.id),
            "fields_count": len(result.fields),
            "exclusions_count": len(result.exclusions),
        }

    except Exception as e:
        db.rollback()
        _finish_job(db, job, status="failed", error=str(e))
        logger.error(f"자격요건 추출 실패 (ann={announcement_id}): {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 태스크 5: 자격요건 추출 (전체 미추출 일괄)
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.worker.tasks.extract_all_pending_eligibility")
def extract_all_pending_eligibility(self) -> dict:
    """extraction_status != 'done' 공고에 대해 개별 추출 태스크 fan-out."""
    db = SessionLocal()
    try:
        pending_ids = [
            str(a.id) for a in db.scalars(
                select(Announcement)
                .where(Announcement.extraction_status != "done")
                .where(Announcement.duplicate_of.is_(None))
            )
        ]
    finally:
        db.close()

    if not pending_ids:
        return {"status": "ok", "scheduled": 0}

    group(extract_announcement_eligibility.s(aid) for aid in pending_ids).apply_async()
    logger.info(f"자격요건 추출 fan-out: {len(pending_ids)}건")
    return {"status": "ok", "scheduled": len(pending_ids)}


# ---------------------------------------------------------------------------
# 태스크 6: 회사 vs 전체 공고 매칭
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.worker.tasks.match_company_announcements")
def match_company_announcements(self, company_id: str) -> dict:
    """회사 vs DB 내 자격요건 추출된 공고 전체 매칭. 기존 결과는 삭제 후 재적재."""
    from app.matcher.matcher import match_announcement
    from app.models.company import Company
    from app.schemas.eligibility import EligibilityField, ParsedCondition

    db = SessionLocal()
    job = _create_job(db, "match")
    try:
        company = db.get(Company, company_id)
        if not company:
            _finish_job(db, job, status="failed", error=f"회사 없음: {company_id}")
            return {"status": "error", "reason": "company_not_found"}

        rows = db.scalars(
            select(EligibilityResult).order_by(EligibilityResult.announcement_id)
        ).all()
        by_ann: dict[uuid.UUID, list[EligibilityResult]] = {}
        for r in rows:
            by_ann.setdefault(r.announcement_id, []).append(r)

        if not by_ann:
            _finish_job(db, job, status="done")
            return {"status": "ok", "matched_announcements": 0}

        # 기존 매칭 결과 제거 (해당 회사 한정, idempotent)
        db.execute(delete(MatchResult).where(MatchResult.company_id == company.id))

        matched_count = 0
        for ann_id, eligibility_rows in by_ann.items():
            fields: list[EligibilityField] = []
            for er in eligibility_rows:
                parsed = er.condition_parsed or {}
                fields.append(EligibilityField(
                    field_name=er.field_name,
                    condition=ParsedCondition(
                        value=parsed.get("value"),
                        operator=parsed.get("operator"),
                        raw_text=er.condition_value,
                    ),
                    evidence=er.evidence or "",
                    evidence_source=er.evidence_source or "",
                    processing_path=er.processing_path,
                ))

            results = match_announcement(company, fields, ann_id)
            for r in results:
                db.add(MatchResult(
                    announcement_id=r.announcement_id,
                    company_id=r.company_id,
                    field_name=r.field_name,
                    status=r.status,
                    company_value=r.company_value,
                    requirement_value=r.requirement_value,
                    evidence=r.evidence,
                    processing_path=r.processing_path,
                ))
            matched_count += 1

        job.total_count = matched_count
        job.success_count = matched_count
        db.commit()
        _finish_job(db, job, status="done")

        return {
            "status": "ok",
            "company_id": str(company.id),
            "matched_announcements": matched_count,
        }

    except Exception as e:
        db.rollback()
        _finish_job(db, job, status="failed", error=str(e))
        logger.error(f"매칭 실패 (company={company_id}): {e}")
        raise
    finally:
        db.close()
