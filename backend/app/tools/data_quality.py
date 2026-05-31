"""수집 데이터 품질 검사 도구 모듈."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors.deduplicator import title_similarity

from app.models.announcement import Announcement, Attachment

MIN_TARGET_TEXT = 50  # 자격요건 텍스트 최소 길이 임계치
DUP_SIMILARITY = 0.9  # 유사 중복 임계치
DUP_WINDOW_DAYS = 7   # 게시일 범위 윈도우

def _empty_title(db: Session) -> list[str]:
    """빈 제목 공고 검출."""
    rows = db.scalars(
        select(Announcement.id).where(
            Announcement.title.is_(None) | (Announcement.title == "")
        )
    ).all()
    return [str(r) for r in rows]

def _short_target_text(db: Session) -> list[str]:
    """본문이 없거나 50자 미만인 공고 검출."""
    rows = db.scalars(
        select(Announcement.id).where(
            Announcement.target_text.is_(None)
            | (Announcement.target_text == "")
            | (func.length(Announcement.target_text) < MIN_TARGET_TEXT)
        )
    ).all()
    return [str(r) for r in rows]

def _no_attachments(db: Session) -> list[str]:
    """첨부파일이 0건인 공고 검출 (중복 outerjoin 방지를 위해 distinct 적용)."""
    rows = db.scalars(
        select(Announcement.id)
        .outerjoin(Attachment, Announcement.id == Attachment.announcement_id)
        .where(Attachment.id.is_(None))
        .distinct()
    ).all()
    return [str(r) for r in rows]

def _download_failed(db: Session) -> list[str]:
    """첨부 다운로드 실패 (URL은 있지만 local_path가 없음)."""
    rows = db.scalars(
        select(Attachment.announcement_id)
        .where(Attachment.download_url.isnot(None), Attachment.local_path.is_(None))
        .distinct()
    ).all()
    return [str(r) for r in rows]

def _conversion_failed(db: Session) -> list[str]:
    """HWP/PDF 문서 변환 실패 공고 검출."""
    rows = db.scalars(
        select(Attachment.announcement_id)
        .where(Attachment.conversion_status == "failed")
        .distinct()
    ).all()
    return [str(r) for r in rows]

def _extraction_failed(db: Session) -> list[str]:
    """자격요건 추출(LLM 등) 실패 공고 검출."""
    rows = db.scalars(
        select(Announcement.id).where(Announcement.extraction_status == "failed")
    ).all()
    return [str(r) for r in rows]

def _duplicate_suspected(db: Session) -> list[dict]:
    """제목 유사도 >= 0.9 및 게시일 7일 이내인 의심스러운 중복 공고 검출."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)  # 성능 병목을 예방하기 위해 최근 6개월 한정
    cutoff = cutoff.replace(tzinfo=None)  # naive datetime 비교 충돌 방지
    anns = db.scalars(
        select(Announcement)
        .where(Announcement.created_at >= cutoff)
        .order_by(Announcement.created_at)
    ).all()
    
    suspects = []
    for i, a in enumerate(anns):
        if not a.created_at:
            continue
        a_dt = a.created_at.replace(tzinfo=None) if a.created_at.tzinfo else a.created_at
        for b in anns[i + 1:]:
            if not b.created_at:
                continue
            b_dt = b.created_at.replace(tzinfo=None) if b.created_at.tzinfo else b.created_at
            
            # anns가 created_at 오름차순으로 정렬되어 있어 b는 항상 a보다 늦은 일시임.
            # 격차가 DUP_WINDOW_DAYS를 초과하면 그 이후의 b는 검사할 필요 없이 break
            if (b_dt - a_dt).days > DUP_WINDOW_DAYS:
                break
                
            if not a.title or not b.title:
                continue
            # 공통 모듈의 title_similarity 사용
            ratio = title_similarity(a.title, b.title)
            if ratio >= DUP_SIMILARITY:
                suspects.append({
                    "ann_a": str(a.id),
                    "ann_b": str(b.id),
                    "similarity": round(ratio, 3)
                })
    return suspects

def check_announcements(db: Session) -> dict:
    """7대 데이터 품질 검사 통합 수행."""
    total_count = db.scalar(select(func.count(Announcement.id))) or 0
    return {
        "total": total_count,
        "issues": {
            "empty_title": _empty_title(db),
            "short_target_text": _short_target_text(db),
            "no_attachments": _no_attachments(db),
            "download_failed": _download_failed(db),
            "conversion_failed": _conversion_failed(db),
            "extraction_failed": _extraction_failed(db),
            "duplicate_suspected": _duplicate_suspected(db),
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
