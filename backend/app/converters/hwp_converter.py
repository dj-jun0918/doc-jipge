"""HWP/HWPX → PDF 변환기.

LibreOffice + H2Orestart 확장 사용 (Dockerfile에 이미 설치됨).
"""

import subprocess
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field

# HWP 파일 시그니처 (매직 바이트)
HWP_BINARY_MAGIC = b"\xd0\xcf\x11\xe0"  # OLE Compound Document (구 바이너리 HWP)
HWP_ZIP_MAGIC    = b"PK\x03\x04"         # ZIP 기반 HWPX


@dataclass
class ConversionResult:
    method: str
    text: str | None = None
    pdf_path: str | None = None
    structured_tables: list[dict] = field(default_factory=list)


def python_hwpx_extract(file_path: str | Path) -> dict:
    """HWPX 파일에서 본문 텍스트 + markdown 표 추출."""
    from hwpx import HwpxDocument
    
    doc = HwpxDocument.open(str(file_path))
    text = doc.export_text()
    markdown = doc.export_markdown()
    
    # Markdown 텍스트에서 표(|로 시작하는 연속된 라인) 추출
    table_pattern = re.compile(r'(?:^\|.*\|[\r\n]+)+', re.MULTILINE)
    tables = []
    for idx, match in enumerate(table_pattern.finditer(markdown)):
        tables.append({
            "name": f"표_{idx+1}",
            "markdown": match.group(0).strip(),
        })
        
    return {"text": text, "markdown_tables": tables}


def convert_to_pdf(input_path: str | Path, timeout: int = 60) -> Path:
    """HWP/HWPX 파일을 PDF로 변환.

    Args:
        input_path: 변환할 HWP/HWPX 파일 경로
        timeout: 변환 타임아웃 (초). 기본 60초.

    Returns:
        변환된 PDF 파일 경로

    Raises:
        FileNotFoundError: 입력 파일이 없을 때
        RuntimeError: LibreOffice 변환 실패 시
        TimeoutError: 변환 시간 초과 시
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"파일 없음: {input_path}")

    output_dir = input_path.parent
    ext = input_path.suffix.lower()

    # 파일 시그니처 확인 (PK로 시작하면 ZIP 기반의 HWPX)
    is_zip = False
    try:
        with open(input_path, "rb") as f:
            is_zip = f.read(4) == b"PK\x03\x04"
    except Exception:
        pass

    # HWP → infilter 필요, HWPX(ZIP) → 자동 인식
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(input_path),
    ]
    if ext == ".hwp" and not is_zip:
        cmd.insert(2, '--infilter=Hwp2002_File')

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"변환 타임아웃 ({timeout}초 초과): {input_path}")

    if result.returncode != 0:
        raise RuntimeError(
            f"HWP 변환 실패 (returncode={result.returncode}): {result.stderr}"
        )

    output_path = output_dir / f"{input_path.stem}.pdf"
    if not output_path.exists():
        raise FileNotFoundError(
            f"변환된 PDF를 찾을 수 없음: {output_path}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return output_path


def is_hwp_file(file_path: str | Path) -> bool:
    """HWP 또는 HWPX 파일인지 확인.

    1차: 확장자 (.hwp / .hwpx) 로 빠르게 판별.
    2차: 확장자가 다를 경우 파일 시그니처(매직 바이트)로 판별.
         - D0 CF 11 E0 → OLE 기반 HWP (바이너리 HWP)
         - PK 03 04    → ZIP 기반 HWPX
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    # 1차: 확장자로 빠르게 판별
    if ext in (".hwp", ".hwpx"):
        return True

    # 2차: 확장자가 다른 파일 → 시그니처(매직 바이트)로 판별
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        return header in (HWP_BINARY_MAGIC, HWP_ZIP_MAGIC)
    except OSError:
        return False


def convert_document(file_path: str | Path, file_type: str, timeout: int = 60) -> ConversionResult:
    """파일 타입에 따라 최적의 추출/변환 경로를 라우팅합니다."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")

    if file_type == "hwpx":
        try:
            result = python_hwpx_extract(path)
            return ConversionResult(
                text=result["text"],
                structured_tables=result["markdown_tables"],
                method="python-hwpx"
            )
        except Exception as e:
            # hwpx 추출 실패 시 LibreOffice fallback 시도
            import traceback
            print(f"[ERROR python-hwpx] Failed to extract {path}: {e}")
            traceback.print_exc()
            try:
                pdf_path = convert_to_pdf(path, timeout)
                return ConversionResult(pdf_path=str(pdf_path), method="libreoffice-fallback")
            except Exception as fallback_e:
                raise RuntimeError(f"HWPX 변환 실패: {e}, fallback 실패: {fallback_e}")

    elif file_type == "hwp":
        try:
            pdf_path = convert_to_pdf(path, timeout)
            return ConversionResult(pdf_path=str(pdf_path), method="libreoffice")
        except Exception as e:
            # LibreOffice 변환 실패 — 텍스트 추출도 불가하므로 failed 처리
            return ConversionResult(method="failed")

    elif file_type == "pdf":
        return ConversionResult(pdf_path=str(path), method="passthrough")
        
    else:
        raise ValueError(f"지원하지 않는 파일 타입: {file_type}")


# 테스트용 main block
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python -m app.converters.hwp_converter <파일경로>")
        print("예시: python -m app.converters.hwp_converter /app/attachments/sample.hwp")
        sys.exit(1)

    input_file = sys.argv[1]
    print(f"변환 시작: {input_file}")

    try:
        pdf_path = convert_to_pdf(input_file)
        print(f"✅ 변환 완료: {pdf_path}")
        print(f"   파일 크기: {pdf_path.stat().st_size:,} bytes")
    except FileNotFoundError as e:
        print(f"❌ 파일 없음: {e}")
    except RuntimeError as e:
        print(f"❌ 변환 실패: {e}")
    except TimeoutError as e:
        print(f"❌ 타임아웃: {e}")
