import Link from "next/link";
import { notFound } from "next/navigation";
import BookmarkButton from "@/components/BookmarkButton";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Attachment {
  name?: string;
  url?: string;
}

interface AnnouncementDetail {
  id: number;
  title?: string;
  organization?: string;
  source?: string;
  region?: string;
  category?: string;
  start_date?: string;
  end_date?: string;
  target?: string;
  content?: string;
  attachments?: Attachment[];
}

interface PageProps {
  params: Promise<{
    id: string;
  }>;
}

async function getAnnouncementDetail(id: string): Promise<AnnouncementDetail> {
  const response = await fetch(`${BACKEND_URL}/api/announcements/${id}`, {
    cache: "no-store",
  });

  if (response.status === 404) {
    notFound();
  }

  if (!response.ok) {
    throw new Error("공고 상세 정보를 불러오지 못했습니다.");
  }

  return response.json();
}

export default async function AnnouncementDetailPage({ params }: PageProps) {
  const { id } = await params;
  const data = await getAnnouncementDetail(id);

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <section className="mx-auto max-w-4xl rounded-2xl border bg-white p-8 shadow-sm">
        <Link
          href="/announcements"
          className="mb-4 inline-block text-sm text-blue-600 hover:underline"
        >
          ← 공고 목록으로
        </Link>

        <div className="flex items-center justify-between mb-4">
          <h1 className="text-3xl font-bold text-gray-900 pr-4">
            {data.title ?? "제목 없음"}
          </h1>
          <BookmarkButton id={id} size={32} />
        </div>

        <div className="mb-8 space-y-2 text-sm text-gray-600">
          <p>기관: {data.organization ?? "-"}</p>
          <p>출처: {data.source ?? "-"}</p>
          <p>지역: {data.region ?? "-"}</p>
          <p>카테고리: {data.category ?? "-"}</p>
          <p>
            접수기간: {data.start_date ?? "-"} ~ {data.end_date ?? "-"}
          </p>
        </div>

        <div className="mb-8">
          <h2 className="mb-2 text-xl font-semibold text-gray-900">지원 대상</h2>
          <div className="rounded-lg bg-gray-50 p-4 text-gray-700">
            {data.target ?? "지원 대상 정보가 없습니다."}
          </div>
        </div>

        <div className="mb-8">
          <h2 className="mb-2 text-xl font-semibold text-gray-900">상세 내용</h2>
          <div className="whitespace-pre-line rounded-lg bg-gray-50 p-4 text-gray-700">
            {data.content ?? "상세 내용이 없습니다."}
          </div>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold text-gray-900">첨부파일</h2>

          {data.attachments && data.attachments.length > 0 ? (
            <ul className="space-y-2">
              {data.attachments.map((file, index) => (
                <li key={index}>
                  <a
                    href={file.url ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {file.name ?? `첨부파일 ${index + 1}`}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-600">첨부파일이 없습니다.</p>
          )}
        </div>
      </section>
    </main>
  );
}