import csv
import io
import logging
import uuid
from collections import Counter
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.announcement import Announcement
from app.models.company import Company
from app.models.match_result import MatchResult
from app.schemas.matching import (
    CompanyMatchListResponse,
    CompanyMatchSummary,
    MatchResultDetailResponse,
    MatchResultItem,
    MatchResultStats,
    TriggerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{what} UUID 형식 오류: {value}")


@router.get("/{company_id}", response_model=CompanyMatchListResponse)
def get_matching_results(
    company_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """회사 전체 매칭 결과 — 충족 비율 기준 정렬 (TOP N)."""
    company_uuid = _parse_uuid(company_id, "company_id")

    if not db.get(Company, company_uuid):
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다")

    rows = db.execute(
        select(
            MatchResult.announcement_id,
            MatchResult.status,
            func.count().label("cnt"),
        )
        .where(MatchResult.company_id == company_uuid)
        .group_by(MatchResult.announcement_id, MatchResult.status)
    ).all()

    agg: dict[uuid.UUID, Counter] = {}
    for ann_id, status, cnt in rows:
        agg.setdefault(ann_id, Counter())[status] = cnt

    summaries: list[tuple[uuid.UUID, float, int, int]] = []
    for ann_id, counter in agg.items():
        fulfilled = counter.get("충족", 0)
        denom = fulfilled + counter.get("미충족", 0) + counter.get("확인필요", 0)
        score = fulfilled / denom if denom > 0 else 0.0
        total = sum(counter.values())
        summaries.append((ann_id, score, fulfilled, total))

    summaries.sort(key=lambda x: (-x[1], -x[3]))
    top = summaries[:limit]

    ann_ids = [s[0] for s in top]
    titles: dict[uuid.UUID, str] = {}
    if ann_ids:
        for ann in db.scalars(select(Announcement).where(Announcement.id.in_(ann_ids))):
            titles[ann.id] = ann.title

    items = [
        CompanyMatchSummary(
            announcement_id=ann_id,
            title=titles.get(ann_id, ""),
            match_score=round(score, 3),
            fulfilled_count=fulfilled,
            total_fields=total,
        )
        for ann_id, score, fulfilled, total in top
    ]

    return CompanyMatchListResponse(
        company_id=company_uuid,
        items=items,
        total=len(summaries),
    )


@router.get("/{company_id}/export")
def export_matching_results(
    company_id: str,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
):
    """매칭 결과를 Excel/CSV 파일로 다운로드."""
    company_uuid = _parse_uuid(company_id, "company_id")
    company = db.get(Company, company_uuid)
    if not company:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다")

    stmt = (
        select(MatchResult, Announcement)
        .join(Announcement, MatchResult.announcement_id == Announcement.id)
        .where(MatchResult.company_id == company_uuid)
        .order_by(MatchResult.created_at.desc())
    )
    rows = db.execute(stmt).all()

    if format == "xlsx":
        return _export_xlsx(company, rows)
    return _export_csv(company, rows)


@router.get(
    "/{company_id}/{announcement_id}",
    response_model=MatchResultDetailResponse,
)
def get_matching_detail(
    company_id: str,
    announcement_id: str,
    db: Session = Depends(get_db),
):
    """특정 공고 vs 회사 필드별 매칭 결과."""
    company_uuid = _parse_uuid(company_id, "company_id")
    ann_uuid = _parse_uuid(announcement_id, "announcement_id")

    rows = db.scalars(
        select(MatchResult)
        .where(
            MatchResult.company_id == company_uuid,
            MatchResult.announcement_id == ann_uuid,
        )
        .order_by(MatchResult.created_at)
    ).all()

    if not rows:
        return MatchResultDetailResponse(
            company_id=company_uuid,
            announcement_id=ann_uuid,
            items=[],
            stats=MatchResultStats(),
            matched_at=None,
        )

    items = [
        MatchResultItem(
            field_name=r.field_name,
            status=r.status,
            score=r.score,
            distance=r.distance,
            constraint_type=r.constraint_type,
            company_value=r.company_value,
            requirement_value=r.requirement_value,
            evidence=r.evidence,
            processing_path=r.processing_path,
        )
        for r in rows
    ]
    counter = Counter(r.status for r in rows)
    stats = MatchResultStats(
        충족=counter.get("충족", 0),
        미충족=counter.get("미충족", 0),
        확인필요=counter.get("확인필요", 0),
        해당없음=counter.get("해당없음", 0),
    )

    return MatchResultDetailResponse(
        company_id=company_uuid,
        announcement_id=ann_uuid,
        items=items,
        stats=stats,
        matched_at=rows[-1].created_at,
    )


@router.post("/{company_id}/run", response_model=TriggerResponse)
def trigger_matching(company_id: str, db: Session = Depends(get_db)):
    """회사 vs DB 내 자격요건 추출된 공고 전체 매칭 — Celery 비동기."""
    from app.worker.tasks import match_company_announcements

    company_uuid = _parse_uuid(company_id, "company_id")

    if not db.get(Company, company_uuid):
        raise HTTPException(status_code=404, detail="회사를 찾을 수 없습니다")

    task = match_company_announcements.delay(str(company_uuid))
    return TriggerResponse(task_id=task.id, message="매칭 작업이 시작되었습니다.")


# ── Export helpers ────────────────────────────────────────────────────────────

_EXPORT_HEADERS = [
    "공고명", "필드", "조건", "회사 값", "판정",
    "점수", "거리", "제약", "근거", "처리 경로",
]
_COL_WIDTHS = [50, 20, 30, 30, 10, 10, 10, 10, 50, 15]


def _row_values(match: MatchResult, ann: Announcement) -> list:
    return [
        ann.title,
        match.field_name,
        match.requirement_value or "",
        match.company_value or "",
        match.status,
        round(match.score, 3) if match.score is not None else "",
        round(match.distance, 3) if match.distance is not None else "",
        match.constraint_type or "",
        match.evidence or "",
        match.processing_path,
    ]


def _content_disposition(filename: str) -> str:
    """RFC 5987 방식으로 Content-Disposition 헤더 값 반환 (한글 파일명 안전)."""
    encoded = quote(filename)
    return f"attachment; filename*=UTF-8''{encoded}"


def _export_xlsx(company: Company, rows: list) -> StreamingResponse:
    """openpyxl로 Excel 생성 + StreamingResponse."""
    wb = Workbook()
    ws = wb.active
    ws.title = "매칭 결과"

    # 헤더 스타일 (파란 배경 + 흰 글씨 + 가운데 정렬)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")
    header_align = Alignment(horizontal="center", vertical="center")

    for col_idx, text in enumerate(_EXPORT_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # 데이터 행
    for match, ann in rows:
        ws.append(_row_values(match, ann))

    # 컬럼 너비 지정
    for col_idx, width in enumerate(_COL_WIDTHS, start=1):
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"matching_{company.name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


def _export_csv(company: Company, rows: list) -> StreamingResponse:
    """csv 모듈로 CSV 생성 + StreamingResponse (UTF-8 BOM 포함)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_EXPORT_HEADERS)
    for match, ann in rows:
        writer.writerow(_row_values(match, ann))

    # \ufeff = UTF-8 BOM — Excel에서 CSV 열 때 한글 깨짐 방지
    content = "\ufeff" + buffer.getvalue()
    filename = f"matching_{company.name}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(filename)},
    )
