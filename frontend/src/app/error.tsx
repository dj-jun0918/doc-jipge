"use client";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  console.error(error);

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <section className="mx-auto max-w-5xl">
        <div className="rounded-2xl border bg-white p-8 shadow-sm">
          <h1 className="mb-3 text-2xl font-bold text-gray-900">
            문제가 발생했습니다
          </h1>
          <p className="mb-6 text-gray-600">
            데이터를 불러오는 중 오류가 발생했습니다. 다시 시도해주세요.
          </p>

          <button
            onClick={reset}
            className="rounded-lg bg-blue-600 px-5 py-3 text-white hover:bg-blue-700"
          >
            다시 시도
          </button>
        </div>
      </section>
    </main>
  );
}