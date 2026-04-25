export default function Loading() {
  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <section className="mx-auto max-w-5xl">
        <div className="rounded-2xl border bg-white p-8 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
            <p className="text-gray-700">불러오는 중입니다...</p>
          </div>
        </div>
      </section>
    </main>
  );
}