"""convert_document 포맷 라우팅 — DOCX/ZIP/미지원 처리 (P5)."""
import zipfile
from pathlib import Path

from app.converters import hwp_converter as hc


def _make_zip(tmp_path, files: dict) -> Path:
    zp = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return zp


def test_zip_재귀_내부_pdf_선택(tmp_path):
    zp = _make_zip(tmp_path, {"공고.pdf": b"%PDF-1.4 dummy", "readme.txt": b"x"})
    r = hc.convert_document(zp, "zip")
    assert r.method == "passthrough"
    assert r.pdf_path and r.pdf_path.endswith(".pdf")


def test_zip_pdf_우선_over_office(tmp_path):
    zp = _make_zip(tmp_path, {"양식.docx": b"PKxx", "공고.pdf": b"%PDF dummy"})
    r = hc.convert_document(zp, "zip")
    assert r.method == "passthrough"
    assert "공고" in r.pdf_path  # office보다 pdf를 먼저 선택


def test_zip_추출가능문서_없으면_unsupported(tmp_path):
    zp = _make_zip(tmp_path, {"readme.txt": b"x", "img.png": b"y"})
    r = hc.convert_document(zp, "zip")
    assert r.method == "unsupported"


def test_손상된_zip은_failed_skip(tmp_path):
    f = tmp_path / "bad.zip"
    f.write_bytes(b"not a zip at all")
    r = hc.convert_document(f, "zip")
    assert r.method == "failed"


def test_미지원_타입은_크래시_대신_skip(tmp_path):
    f = tmp_path / "a.xyz"
    f.write_bytes(b"x")
    r = hc.convert_document(f, "xyz")  # 이전엔 ValueError로 배치 중단
    assert r.method == "unsupported"


def test_office_타입은_soffice_경로(tmp_path, monkeypatch):
    f = tmp_path / "a.docx"
    f.write_bytes(b"PKxx")
    out = tmp_path / "a.pdf"
    out.write_bytes(b"%PDF")
    monkeypatch.setattr(hc, "convert_to_pdf", lambda p, t=60: out)
    r = hc.convert_document(f, "docx")
    assert r.method == "libreoffice-office"
    assert r.pdf_path == str(out)
