FROM python:3.13-slim

WORKDIR /app

# 기본 언어셋(Locale)을 UTF-8로 설정 (한글 HWPX 파일명 인식 오류 해결)
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# LibreOffice + Java + libreoffice-java-common (LibreOffice↔Java 브릿지)
# H2Orestart는 Java로 작성된 LibreOffice 확장이라 Java 브릿지가 필수
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-java-common \
    default-jre-headless \
    wget \
    unzip \
    curl \
    && wget -q https://github.com/ebandal/H2Orestart/releases/latest/download/H2Orestart.oxt -O /tmp/H2Orestart.oxt \
    && unopkg add --shared /tmp/H2Orestart.oxt \
    && rm /tmp/H2Orestart.oxt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Playwright Chromium (K-Startup, 중기부 스크래핑)
RUN pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium

# Python 의존성 (의존성 캐시 레이어 분리)
COPY pyproject.toml .
RUN mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir -e ".[dev]" \
    && rm -rf app

# 실제 소스 코드 복사
COPY app/ app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
