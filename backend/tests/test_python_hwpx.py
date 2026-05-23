"""python-hwpx 파서 유닛 테스트.

실제 HWPX 파일 없이 HwpxDocument를 Mock하여 파서 로직과 변환 분기를 검증합니다.
엄격한 성공률 기준(90% 이상)은 E2E가 아닌 이 유닛 테스트에서 보장합니다.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.converters.hwp_converter import python_hwpx_extract, convert_document, ConversionResult


# ---------------------------------------------------------------------------
# python_hwpx_extract 단위 테스트
# ---------------------------------------------------------------------------

class TestPythonHwpxExtract:

    def test_텍스트_및_표_정상_추출(self, tmp_path):
        """HwpxDocument가 정상 반환할 때 text와 markdown_tables가 파싱되는지 확인."""
        fake_markdown = (
            "# 제목\n\n"
            "| 항목 | 내용 |\n"
            "| --- | --- |\n"
            "| 대상 | 중소기업 |\n\n"
            "본문 텍스트입니다.\n\n"
            "| 지원금 | 한도 |\n"
            "| --- | --- |\n"
            "| 최대 5억 | 매칭 50% |\n"
        )
        fake_hwpx = tmp_path / "sample.hwpx"
        fake_hwpx.write_bytes(b"PK\x03\x04dummy")  # ZIP 매직 바이트

        mock_doc = MagicMock()
        mock_doc.export_text.return_value = "본문 텍스트입니다."
        mock_doc.export_markdown.return_value = fake_markdown

        with patch("hwpx.HwpxDocument") as MockHwpx:
            MockHwpx.open.return_value = mock_doc
            result = python_hwpx_extract(fake_hwpx)

        assert result["text"] == "본문 텍스트입니다."
        assert len(result["markdown_tables"]) == 2, "표 2개가 추출되어야 함"
        assert result["markdown_tables"][0]["name"] == "표_1"
        assert "항목" in result["markdown_tables"][0]["markdown"]

    def test_표_없는_문서(self, tmp_path):
        """표가 없는 HWPX 문서 → markdown_tables 빈 리스트 반환."""
        fake_hwpx = tmp_path / "no_table.hwpx"
        fake_hwpx.write_bytes(b"PK\x03\x04dummy")

        mock_doc = MagicMock()
        mock_doc.export_text.return_value = "텍스트만 있는 문서"
        mock_doc.export_markdown.return_value = "# 제목\n\n텍스트만 있는 문서\n"

        with patch("hwpx.HwpxDocument") as MockHwpx:
            MockHwpx.open.return_value = mock_doc
            result = python_hwpx_extract(fake_hwpx)

        assert result["text"] == "텍스트만 있는 문서"
        assert result["markdown_tables"] == []

    def test_HwpxDocument_오류_시_예외_전파(self, tmp_path):
        """HwpxDocument.open()이 예외를 던질 때 그대로 전파되는지 확인."""
        fake_hwpx = tmp_path / "broken.hwpx"
        fake_hwpx.write_bytes(b"PK\x03\x04dummy")

        with patch("hwpx.HwpxDocument") as MockHwpx:
            MockHwpx.open.side_effect = Exception("파일 손상")
            with pytest.raises(Exception, match="파일 손상"):
                python_hwpx_extract(fake_hwpx)


# ---------------------------------------------------------------------------
# convert_document 라우팅 단위 테스트
# ---------------------------------------------------------------------------

class TestConvertDocument:

    def test_HWPX_python_hwpx_경로_정상(self, tmp_path):
        """file_type='hwpx'이면 python-hwpx 경로를 타고 method가 'python-hwpx'여야 함."""
        fake_hwpx = tmp_path / "test.hwpx"
        fake_hwpx.write_bytes(b"PK\x03\x04dummy")

        mock_doc = MagicMock()
        mock_doc.export_text.return_value = "지원 대상: 중소기업"
        mock_doc.export_markdown.return_value = (
            "| 구분 | 내용 |\n| --- | --- |\n| 대상 | 중소기업 |\n"
        )

        with patch("hwpx.HwpxDocument") as MockHwpx:
            MockHwpx.open.return_value = mock_doc
            result = convert_document(fake_hwpx, "hwpx")

        assert result.method == "python-hwpx"
        assert result.text == "지원 대상: 중소기업"
        assert len(result.structured_tables) == 1

    def test_HWPX_파싱_실패_시_libreoffice_fallback(self, tmp_path):
        """python-hwpx 파싱 실패 시 libreoffice-fallback으로 우회되는지 확인."""
        fake_hwpx = tmp_path / "test.hwpx"
        fake_hwpx.write_bytes(b"PK\x03\x04dummy")

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        with patch("hwpx.HwpxDocument") as MockHwpx, \
             patch("app.converters.hwp_converter.convert_to_pdf") as mock_pdf:
            MockHwpx.open.side_effect = RuntimeError("파싱 실패")
            mock_pdf.return_value = fake_pdf
            result = convert_document(fake_hwpx, "hwpx")

        assert result.method == "libreoffice-fallback"
        assert result.pdf_path == str(fake_pdf)

    def test_HWP_LibreOffice_변환_성공(self, tmp_path):
        """file_type='hwp' 정상 변환 → method='libreoffice'."""
        fake_hwp = tmp_path / "test.hwp"
        fake_hwp.write_bytes(b"\xd0\xcf\x11\xe0dummy")

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        with patch("app.converters.hwp_converter.convert_to_pdf") as mock_pdf:
            mock_pdf.return_value = fake_pdf
            result = convert_document(fake_hwp, "hwp")

        assert result.method == "libreoffice"
        assert result.pdf_path == str(fake_pdf)

    def test_HWP_LibreOffice_변환_실패_시_failed(self, tmp_path):
        """LibreOffice 변환 실패 시 method='failed'로 처리되는지 확인."""
        fake_hwp = tmp_path / "test.hwp"
        fake_hwp.write_bytes(b"\xd0\xcf\x11\xe0dummy")

        with patch("app.converters.hwp_converter.convert_to_pdf") as mock_pdf:
            mock_pdf.side_effect = RuntimeError("변환 실패")
            result = convert_document(fake_hwp, "hwp")

        assert result.method == "failed"

    def test_PDF_passthrough(self, tmp_path):
        """file_type='pdf'는 변환 없이 그대로 passthrough."""
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        result = convert_document(fake_pdf, "pdf")

        assert result.method == "passthrough"
        assert result.pdf_path == str(fake_pdf)

    def test_파일_없음_예외(self, tmp_path):
        """파일이 존재하지 않으면 FileNotFoundError 발생."""
        with pytest.raises(FileNotFoundError):
            convert_document(tmp_path / "nonexistent.hwpx", "hwpx")
