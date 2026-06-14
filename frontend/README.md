Doc집게 프론트엔드 — 정부지원사업 공고문과 첨부파일에서 추출한 자격요건을 기업 프로필과 비교해 조건별 충족 여부와 원문 근거를 보여주는 웹 UI입니다. [Next.js](https://nextjs.org)(App Router) 기반이며 [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app)으로 부트스트랩되었습니다.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

매칭·평가 데이터는 백엔드(FastAPI, 기본 `http://localhost:8000`)에서 가져옵니다. `/backend-api/*` 요청은 `next.config.ts`의 rewrite로 `NEXT_PUBLIC_API_URL`(미설정 시 `http://localhost:8000`) 백엔드의 `/api/*`로 프록시됩니다. 백엔드가 떠 있지 않으면 매칭/평가 대시보드에 데이터 로드 실패 안내가 표시됩니다.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## 주요 화면 및 기능

상단 네비게이션은 5개 메뉴로 구성됩니다: **홈 · 공고 목록 · 기업 관리 · 매칭 대시보드 · 평가 대시보드**.

- **기업 관리 (`/companies`)** — 표준화된 기업 프로필 입력 폼과 등록 기업 목록을 함께 제공합니다. 인증 18종 multi-select 체크박스(+기타 자유 입력), 지역 17개 시도 select, 업종 KSIC 대분류 datalist 제안, 매출 억/만/원 단위 토글과 입력 검증을 갖춰 매칭 어휘를 표준 항목으로 유도합니다. 등록한 기업은 목록에서 조회·수정할 수 있습니다(삭제 없음).
- **매칭 대시보드 (`/matching`)** — 선택한 기업에 대한 공고 매칭 결과를 적합도 버킷(**신청가능 / 조건확인 / 자격미달**) 3그룹으로 묶어 표시합니다. 버킷 우선 정렬 후 그 안에서 점수 순으로 나열하며, 자격미달 그룹은 기본 접힘 상태로 펼쳐서 확인합니다. 전체 매칭 공고 수, 평균/최고 매칭 점수, 신청가능 공고 수 요약 카드를 함께 보여줍니다.
- **매칭 상세 (`/matching/[id]`)** — 공고별 자격요건 판정을 3개 탭(전체 요건 분석 / 수동 확인 필요 / 자격 충족 대안 가이드)으로 제공합니다. 판정 카드의 근거 버튼을 누르면 증거 유형에 맞는 전용 뷰어(PDF 영역 하이라이트·점프, HWPX 테이블, 텍스트)로 원문을 정밀 표시합니다. What-if 시뮬레이터에서 매출·업력·임직원 수·지역을 가상으로 조정하면 매칭 점수·충족 여부·버킷 배지가 실시간으로 갱신됩니다.
- **공고 목록 (`/announcements`)** — 키워드·출처·지역 필터, 정렬, 북마크, 마감 D-day 배지를 제공하며 상세(`/announcements/[id]`)로 이동합니다.
- **평가 대시보드 (`/evaluation`)** — 추출 정확도(P/R/F1), Bootstrap 95% 신뢰구간, 소거법(Ablation) 연구, 라벨러 합의도(IAA, Cohen's κ), 오답 패턴 분석을 탭으로 시각화합니다. 모든 수치는 백엔드 평가 API에서 실시간으로 받아 표시합니다.

매칭 점수는 충족 1.0 / 확인필요 0.45 / 미충족 (1-거리)\*0.3(상한 0.3) / 해당없음 제외 규칙으로 7개 표준 필드를 균등 가중 평균하며, 적합도 버킷은 점수와 별개의 범주 레이어로 결정적 미충족 유무에 따라 산출됩니다.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
