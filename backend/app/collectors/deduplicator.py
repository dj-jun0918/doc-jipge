"""중복 공고 탐지.

3소스(기업마당/K-Startup/중기부)에서 동일 공고가 중복 수집되는 것을 탐지.
"""

from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.announcement import Announcement

def title_similarity(a: str, b: str) -> float:
    """두 제목의 유사도 계산 (0.0 ~ 1.0).

    difflib.SequenceMatcher 사용. 외부 패키지 불필요.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def find_duplicate(
    ann: dict,
    db: Session,
    similarity_threshold: float = 0.85,) -> str | None:
    """중복 공고 탐지.

    Args:
        ann: normalize()가 반환한 14개 키 dict
        db: SQLAlchemy DB 세션
        similarity_threshold: 제목 유사도 임계값 (기본 0.85)

    Returns:
        중복인 경우 원본 announcement ID (str), 아니면 None
    """
    # 1단계: source + source_id 완전 일치
    existing = db.scalar(
        select(Announcement).where(
            Announcement.source == ann["source"],
            Announcement.source_id == ann["source_id"],
        )
    )
    if existing:
        return str(existing.id)

    # 2단계: 제목 유사도 + 기관명 일치
    # 기관명이 같은 공고 중에서 제목 유사도 검사 (전체 스캔 방지)
    organization = ann.get("organization")
    if not organization:
        return None

    candidates = db.scalars(
        select(Announcement).where(
            Announcement.organization == organization,
            Announcement.duplicate_of.is_(None),  # 원본만 대상
        )
    ).all()

    title = ann.get("title", "")
    for candidate in candidates:
        sim = title_similarity(title, candidate.title)
        if sim >= similarity_threshold:
            return str(candidate.id)

    return None

# 테스트용 main block
if __name__ == "__main__":
    # DB 없이 유사도 함수만 테스트
    test_cases = [
        ("2026 강원 청년창업 지원사업", "2026 강원 청년창업 지원사업", "동일"),
        ("2026 강원 청년창업 지원사업", "2026년 강원 청년창업 지원사업", "유사"),
        ("2026 강원 청년창업 지원사업", "2026 제조기업 디지털 전환 지원", "다름"),
    ]

    print("=== 제목 유사도 테스트 ===")
    for a, b, label in test_cases:
        sim = title_similarity(a, b)
        is_dup = "중복" if sim >= 0.85 else "다른 공고"
        print(f"[{label}] {sim:.2f} → {is_dup}")
        print(f"  A: {a}")
        print(f"  B: {b}")
        print()
