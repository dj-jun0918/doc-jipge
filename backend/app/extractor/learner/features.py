"""입력 특성 추출 함수 모듈."""

from typing import Any

def extract_features(ann: Any) -> dict[str, Any]:
    """공고 1건 (ORM 객체 또는 dict) → decision tree 입력 dict."""
    if isinstance(ann, dict):
        target_text = ann.get("target_text") or ""
        exclusion_text = ann.get("exclusion_text") or ""
        attachments = ann.get("attachments") or []
        structured_tables = ann.get("structured_tables") or []
        title = ann.get("title") or ""
        
        # 첨부파일 타입 추출 (dict 리스트 또는 ORM Attachment 객체 리스트 지원)
        has_hwpx = any(
            (a.get("file_type") if isinstance(a, dict) else getattr(a, "file_type", None)) == "hwpx"
            for a in attachments
        )
        has_pdf = any(
            (a.get("file_type") if isinstance(a, dict) else getattr(a, "file_type", None)) == "pdf"
            for a in attachments
        )
    else:
        target_text = getattr(ann, "target_text", "") or ""
        exclusion_text = getattr(ann, "exclusion_text", "") or ""
        attachments = getattr(ann, "attachments", []) or []
        structured_tables = getattr(ann, "structured_tables", []) or []
        title = getattr(ann, "title", "") or ""
        
        has_hwpx = any(getattr(a, "file_type", None) == "hwpx" for a in attachments)
        has_pdf = any(getattr(a, "file_type", None) == "pdf" for a in attachments)

    has_table_keyword = "표" in target_text or "참조" in target_text or "별표" in target_text
    
    return {
        "text_length": len(target_text),
        "exclusion_length": len(exclusion_text),
        "has_attachments": bool(attachments),
        "attachment_count": len(attachments),
        "has_hwpx": has_hwpx,
        "has_pdf": has_pdf,
        "structured_tables_count": len(structured_tables),
        "has_table_keyword": int(has_table_keyword),
        "title_length": len(title),
    }

def features_to_vector(features: dict[str, Any]) -> list[float]:
    """dict → 고정 순서 vector (학습/예측 일관성)."""
    keys = sorted(features.keys())
    return [float(features[k]) for k in keys]
