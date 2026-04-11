import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 px-6 py-16">
      <section className="mx-auto max-w-4xl text-center">
        <h1 className="mb-4 text-5xl font-bold text-gray-900">Doc집게</h1>

        <p className="mb-6 text-xl text-gray-700">
          정부지원사업 공고문과 첨부파일을 분석하여
          <br />
          기업이 지원 자격을 충족하는지 투명하게 검증해주는 시스템
        </p>

        <p className="mx-auto mb-10 max-w-2xl text-base leading-7 text-gray-600">
          기존 정부지원사업 추천 서비스는 단순히 적합도를 제시하는 경우가 많아
          왜 지원 가능한지, 왜 불가능한지 명확히 알기 어렵습니다. Doc집게는
          공고문과 첨부파일 속 자격요건을 구조화하고, 조건별 충족 여부와 원문
          근거를 함께 제시하여 보다 신뢰도 높은 의사결정을 돕습니다.
        </p>

        <div className="mb-12 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white p-6 shadow-sm border">
            <h2 className="mb-2 text-lg font-semibold text-gray-900">
              공고문 분석
            </h2>
            <p className="text-sm leading-6 text-gray-600">
              정부지원사업 공고문과 첨부파일에서 자격요건 정보를 자동으로
              추출합니다.
            </p>
          </div>

          <div className="rounded-2xl bg-white p-6 shadow-sm border">
            <h2 className="mb-2 text-lg font-semibold text-gray-900">
              조건별 검증
            </h2>
            <p className="text-sm leading-6 text-gray-600">
              업력, 지역, 매출 등 주요 조건을 기준으로 기업 프로필과 공고를
              비교해 충족 여부를 판정합니다.
            </p>
          </div>

          <div className="rounded-2xl bg-white p-6 shadow-sm border">
            <h2 className="mb-2 text-lg font-semibold text-gray-900">
              원문 근거 제시
            </h2>
            <p className="text-sm leading-6 text-gray-600">
              판정 결과와 함께 공고문 내 근거 문장과 출처 위치를 제공하여
              결과를 쉽게 확인할 수 있습니다.
            </p>
          </div>
        </div>

        <Link
          href="/announcements"
          className="inline-block rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700"
        >
          공고 목록 보기
        </Link>
      </section>
    </main>
  );
}