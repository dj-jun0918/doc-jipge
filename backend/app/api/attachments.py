"""첨부파일 API — PDF 스트리밍.

frontend PdfViewer가 `/api/attachments/{id}/file` 호출 시 PDF 인라인 응답.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.announcement import Attachment

router = APIRouter()


@router.get("/{attachment_id}/file")
def serve_attachment(attachment_id: str, db: Session = Depends(get_db)):
    """첨부파일 PDF 스트리밍.

    - converted_pdf_path (HWP 구버전 변환 결과) 우선
    - file_type == "pdf"이면 local_path 사용
    - 그 외 (HWPX 등)는 404 — frontend에서 EvidencePlaceholder 분기
    """
    try:
        att_uuid = uuid.UUID(attachment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"attachment_id UUID 형식 오류: {attachment_id}")

    att = db.get(Attachment, att_uuid)
    if not att or not att.local_path:
        raise HTTPException(status_code=404, detail="첨부파일을 찾을 수 없습니다")

    pdf_path = att.converted_pdf_path or (att.local_path if att.file_type == "pdf" else None)
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF 표시 불가 (HWPX는 EvidencePlaceholder)")

    if not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail=f"PDF 파일이 디스크에 존재하지 않습니다: {pdf_path}")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )
