"""
backend/tests/test_deduplicator.py
김동준 deduplicator 단위 테스트
"""

from unittest.mock import MagicMock
import pytest
from app.collectors.deduplicator import title_similarity, find_duplicate
from app.models.announcement import Announcement


# ──────────────────────────────────────────────
# title_similarity — 제목 유사도
# ──────────────────────────────────────────────

class TestTitleSimilarity:

    # 기본 케이스
    def test_동일_제목_1점(self):
        assert title_similarity("2026 강원 청년창업 지원사업", "2026 강원 청년창업 지원사업") == 1.0

    def test_유사_제목_임계값_이상(self):
        sim = title_similarity("2026 강원 청년창업 지원사업", "2026년 강원 청년창업 지원사업")
        assert sim >= 0.85

    def test_다른_제목_임계값_미만(self):
        sim = title_similarity("2026 강원 청년창업 지원사업", "2026 제조기업 디지털 전환 지원")
        assert sim < 0.85

    def test_연도_표기_차이_유사(self):
        # "2026" vs "2026년" — 유사로 처리
        sim = title_similarity("2026 서울 스타트업 지원", "2026년 서울 스타트업 지원")
        assert sim >= 0.85

    def test_완전히_다른_제목(self):
        sim = title_similarity("청년창업 지원사업", "중소기업 수출바우처 지원")
        assert sim < 0.85

    # 엣지 케이스
    def test_빈_문자열_a_0점(self):
        assert title_similarity("", "2026 강원 청년창업 지원사업") == 0.0

    def test_빈_문자열_b_0점(self):
        assert title_similarity("2026 강원 청년창업 지원사업", "") == 0.0

    def test_둘_다_빈_문자열_0점(self):
        assert title_similarity("", "") == 0.0

    def test_반환값_범위_0_to_1(self):
        sim = title_similarity("2026 강원 청년창업 지원사업", "2026 부산 청년창업 지원사업")
        assert 0.0 <= sim <= 1.0


# ──────────────────────────────────────────────
# find_duplicate — 중복 탐지 (DB mock)
# ──────────────────────────────────────────────

class TestFindDuplicate:

    def _make_ann(self, title="2026 강원 청년창업 지원사업", source="bizinfo",
                  source_id="ANN001", organization="강원도"):
        return {
            "title": title,
            "source": source,
            "source_id": source_id,
            "organization": organization,
        }

    def _make_db_announcement(self, id="uuid-001", title="2026 강원 청년창업 지원사업",
                               source="bizinfo", source_id="ANN001",
                               organization="강원도"):
        ann = MagicMock(spec=Announcement)
        ann.id = id
        ann.title = title
        ann.source = source
        ann.source_id = source_id
        ann.organization = organization
        ann.duplicate_of = None
        return ann

    # 1단계: source + source_id 완전 일치
    def test_source_id_완전일치_중복_반환(self):
        db = MagicMock()
        existing = self._make_db_announcement()
        db.scalar.return_value = existing

        result = find_duplicate(self._make_ann(), db)
        assert result == "uuid-001"

    def test_source_id_불일치_None(self):
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value.all.return_value = []

        result = find_duplicate(self._make_ann(), db)
        assert result is None

    # 2단계: 제목 유사도 + 기관명 일치
    def test_제목_유사_기관_일치_중복_반환(self):
        db = MagicMock()
        db.scalar.return_value = None  # 1단계 불일치

        candidate = self._make_db_announcement(
            id="uuid-002",
            source_id="ANN002",  # source_id 다름
            title="2026년 강원 청년창업 지원사업"  # 유사 제목
        )
        db.scalars.return_value.all.return_value = [candidate]

        ann = self._make_ann(source_id="ANN999")  # source_id 다른 공고
        result = find_duplicate(ann, db)
        assert result == "uuid-002"

    def test_제목_다름_기관_일치_None(self):
        db = MagicMock()
        db.scalar.return_value = None

        candidate = self._make_db_announcement(
            id="uuid-003",
            title="2026 제조기업 디지털 전환 지원"  # 다른 제목
        )
        db.scalars.return_value.all.return_value = [candidate]

        ann = self._make_ann(source_id="ANN999")
        result = find_duplicate(ann, db)
        assert result is None

    def test_organization_없으면_None(self):
        db = MagicMock()
        db.scalar.return_value = None

        ann = self._make_ann(organization=None)
        result = find_duplicate(ann, db)
        assert result is None

    def test_candidates_없으면_None(self):
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value.all.return_value = []

        result = find_duplicate(self._make_ann(source_id="ANN999"), db)
        assert result is None

    # 임계값 커스텀
    def test_임계값_높이면_유사_제목_미탐지(self):
        db = MagicMock()
        db.scalar.return_value = None

        candidate = self._make_db_announcement(
            id="uuid-004",
            title="2026년 강원 청년창업 지원사업"
        )
        db.scalars.return_value.all.return_value = [candidate]

        ann = self._make_ann(source_id="ANN999")
        # 임계값 0.99로 높이면 유사 제목도 미탐지
        result = find_duplicate(ann, db, similarity_threshold=0.99)
        assert result is None

    def test_반환값_str_타입(self):
        db = MagicMock()
        existing = self._make_db_announcement()
        db.scalar.return_value = existing

        result = find_duplicate(self._make_ann(), db)
        assert isinstance(result, str)

    def test_지역_다르면_유사도_높아도_중복_제외(self):
        db = MagicMock()
        db.scalar.return_value = None  # 1단계 불일치

        candidate = self._make_db_announcement(
            id="uuid-005",
            source_id="ANN005",
            title="[강원] 2026 청년창업 지원사업"
        )
        db.scalars.return_value.all.return_value = [candidate]

        ann = self._make_ann(
            source_id="ANN999",
            title="[경북] 2026 청년창업 지원사업"  # 지역만 [경북]으로 다름
        )
        result = find_duplicate(ann, db)
        assert result is None

    def test_차수_다르면_유사도_높아도_중복_제외(self):
        db = MagicMock()
        db.scalar.return_value = None

        candidate = self._make_db_announcement(
            id="uuid-006",
            source_id="ANN006",
            title="2026 청년창업 지원사업 1차"
        )
        db.scalars.return_value.all.return_value = [candidate]

        ann = self._make_ann(
            source_id="ANN999",
            title="2026 청년창업 지원사업 2차"  # 차수만 2차로 다름
        )
        result = find_duplicate(ann, db)
        assert result is None