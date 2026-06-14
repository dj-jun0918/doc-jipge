"""vision 표 페이지 키워드 랭킹 (P4) — 후반 별첨 표가 first-N 컷에 잘리지 않게."""
from app.extractor import vision_llm


class _FakePage:
    def __init__(self, text):
        self._text = text

    def get_text(self):
        return self._text


class _FakeDoc:
    def __init__(self, texts):
        self._pages = [_FakePage(t) for t in texts]

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, i):
        return self._pages[i]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_키워드_많은_후반_페이지_우선_선택(monkeypatch):
    # 0~6은 키워드 없음, 7번에 자격요건 키워드 집중 → 7번이 top5에 들어야
    texts = ["내용 없음"] * 7 + ["신청자격 요건 대상 업종 인증 종업원 자격 요건"]
    monkeypatch.setattr(vision_llm.pymupdf, "open", lambda p: _FakeDoc(texts))
    chosen = vision_llm._rank_table_pages("x.pdf", list(range(8)), max_pages=5)
    assert len(chosen) == 5
    assert 7 in chosen  # 후반 키워드 페이지 회수
    assert chosen == sorted(chosen)  # 페이지 순서 유지


def test_max이하면_그대로_반환():
    assert vision_llm._rank_table_pages("x.pdf", [0, 1, 2], max_pages=5) == [0, 1, 2]


def test_pdf_읽기_실패시_앞_N개_fallback(monkeypatch):
    def _boom(p):
        raise RuntimeError("open 실패")
    monkeypatch.setattr(vision_llm.pymupdf, "open", _boom)
    chosen = vision_llm._rank_table_pages("x.pdf", list(range(8)), max_pages=5)
    assert chosen == [0, 1, 2, 3, 4]  # 예외 시 기존 동작(앞 5개)
