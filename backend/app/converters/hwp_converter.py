"""HWP/HWPX → PDF 변환기.

LibreOffice + H2Orestart 확장 사용 (Dockerfile에 이미 설치됨).
"""

import subprocess
import sys
from pathlib import Path


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

    # HWP → infilter 필요, HWPX → 자동 인식
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(input_path),
    ]
    if ext == ".hwp":
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
    """HWP 또는 HWPX 파일인지 확인."""
    ext = Path(file_path).suffix.lower()
    return ext in (".hwp", ".hwpx")


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
