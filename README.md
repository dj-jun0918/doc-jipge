# Doc집게 (doc-jipge)

정부지원사업 공고문과 첨부파일에서 자격요건을 추출하고, 기업 프로필과 자동 매칭해 **판단 근거를 원문에서 함께 보여주는** 시스템.

기존 추천 서비스가 "적합도 점수"만 주는 것과 달리, Doc집게는 ① 공고 첨부파일(HWP/PDF/스캔)까지 추출하고, ② 판단 근거를 공고 원문 문장 그대로 인용·하이라이트하며, ③ 정확도를 측정 방법·신뢰구간과 함께 공개한다.

## 핵심 기능

- **수집**: 기업마당·K-Startup·중소벤처기업부에서 공고 수집, 제목 유사도 기반 중복 제거
- **추출**: 3계층 비용 인식 cascade — 규칙 → 텍스트 LLM → Vision LLM. 표준 7종 자격요건(업력·매출·지역·나이·종업원 수·업종·인증) 구조화. HWP·HWPX·PDF·Office 문서·ZIP 번들 등 변환 지원
- **검증**: 추출 결과를 원문과 verbatim 대조, 근거가 원문에 없으면 필드 제외(환각 방어). 비요건·업종 과추출 차단 필터
- **매칭**: 7종 필드별 충족/미충족/확인필요/해당없음 판정 + 연속 점수(0~1). 공고 단위 **적합도 버킷**(신청가능/조건확인/자격미달)
- **설명**: 판정 근거를 PDF 원문 위치로 점프·하이라이트. What-if 시뮬레이터(프로필 변경 시 결과 재계산)와 반사실 가이드(미충족 요건의 최소 변경 제안)

## 기술 스택

- **백엔드**: FastAPI · SQLAlchemy · PostgreSQL · Celery + Redis · OpenAI(text/Vision) · python-hwpx · PyMuPDF · LibreOffice(변환)
- **프론트엔드**: Next.js(App Router) · React · Tailwind CSS
- **평가**: 자체 measure 파이프라인(micro P/R/F1 + Bootstrap CI), LLM 응답 record/replay 캐시로 결정론적 재측정

## 성능 평가

표준 7종 자격요건을 **값·연산자 완전 일치** 기준으로 엄격 채점하고, 추출 F1·Bootstrap 신뢰구간·필드별/처리경로별 지표·근거 품질(원문 verbatim)을 측정한다. 측정 결과 전체는 자동 생성되는 `evaluation/results/report.md`에서 확인할 수 있다.

## 실행

`.env`에 `OPENAI_API_KEY` 설정 후:

```bash
# 백엔드·워커·DB·Redis 기동
docker compose up -d

# 자동 수집 스케줄러(Celery Beat)까지 켜려면
docker compose --profile scheduler up -d

# 프론트엔드 (별도 실행)
cd frontend && npm install && npm run dev
```

- API: http://localhost:8000 (`/api/...`), 프론트: http://localhost:3000
- 테스트: `docker compose exec backend python -m pytest`
