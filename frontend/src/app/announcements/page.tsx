interface Announcement {
  id: number;
  title?: string;
  source?: string;
  region?: string;
  organization?: string;
  start_date?: string;
  end_date?: string;
}

interface AnnouncementResponse {
  items: Announcement[];
  total: number;
  limit: number;
  offset: number;
}

async function getAnnouncements(): Promise<AnnouncementResponse> {
  const response = await fetch("http://localhost:8000/api/announcements", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("공고 목록을 불러오지 못했습니다.");
  }

  return response.json();
}

export default async function AnnouncementsPage() {
  const data = await getAnnouncements();

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <section className="mx-auto max-w-5xl">
        <h1 className="mb-2 text-3xl font-bold text-gray-900">공고 목록</h1>
        <p className="mb-6 text-sm text-gray-600">
          전체 공고 수: {data.total}
        </p>

        {data.items.length === 0 ? (
          <div className="rounded-xl border bg-white p-6 text-gray-600 shadow-sm">
            현재 등록된 공고가 없습니다.
          </div>
        ) : (
          <div className="grid gap-4">
            {data.items.map((item) => (
              <div
                key={item.id}
                className="rounded-xl border bg-white p-5 shadow-sm"
              >
                <h2 className="mb-2 text-xl font-semibold text-gray-900">
                  {item.title ?? "제목 없음"}
                </h2>

                <div className="space-y-1 text-sm text-gray-600">
                  <p>출처: {item.source ?? "-"}</p>
                  <p>지역: {item.region ?? "-"}</p>
                  {item.organization && <p>기관: {item.organization}</p>}
                  {item.start_date && item.end_date && (
                    <p>
                      접수기간: {item.start_date} ~ {item.end_date}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}