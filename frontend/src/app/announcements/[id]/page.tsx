import Link from "next/link";
import { notFound } from "next/navigation";
import BookmarkButton from "@/components/BookmarkButton";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Attachment {
  id: string;
  file_name?: string;
  file_type?: string;
  has_pdf?: boolean;
}

interface AnnouncementDetail {
  id: string;
  title?: string;
  organization?: string;
  source?: string;
  region?: string;
  category?: string;
  period_start?: string;
  period_end?: string;
  target_text?: string;
  exclusion_text?: string;
  detail_url?: string;
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
            접수기간: {data.period_start ?? "-"} ~ {data.period_end ?? "-"}
          </p>
        </div>

        <div className="mb-8">
          <h2 className="mb-2 text-xl font-semibold text-gray-900">지원 대상</h2>
          {/* 시드·일부 공고는 이 필드에 공고 전문이 들어 있어 장문이면 접어서 표시 */}
          {data.target_text && data.target_text.length > 400 ? (
            <div className="rounded-lg bg-gray-50 p-4 text-gray-700">
              <p className="whitespace-pre-line">{data.target_text.slice(0, 400)}…</p>
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium text-blue-600 hover:underline">
                  전체 내용 펼치기
                </summary>
                <p className="mt-2 whitespace-pre-line">{data.target_text.slice(400)}</p>
              </details>
            </div>
          ) : (
            <div className="whitespace-pre-line rounded-lg bg-gray-50 p-4 text-gray-700">
              {data.target_text ?? "지원 대상 정보가 없습니다."}
            </div>
          )}
        </div>

        {data.exclusion_text && (
          <div className="mb-8">
            <h2 className="mb-2 text-xl font-semibold text-gray-900">제외 대상</h2>
            <div className="whitespace-pre-line rounded-lg bg-gray-50 p-4 text-gray-700">
              {data.exclusion_text}
            </div>
          </div>
        )}

        {data.detail_url && (
          <div className="mb-8">
            <a
              href={data.detail_url}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
            >
              원문 공고 페이지 열기 ↗
            </a>
          </div>
        )}

        <div>
          <h2 className="mb-2 text-xl font-semibold text-gray-900">첨부파일</h2>

          {data.attachments && data.attachments.length > 0 ? (
            <ul className="space-y-2">
              {data.attachments.map((file, index) => (
                <li key={file.id ?? index}>
                  {file.has_pdf ? (
                    <a
                      href={`/backend-api/attachments/${file.id}/file`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {file.file_name ?? `첨부파일 ${index + 1}`}
                    </a>
                  ) : (
                    <span className="text-gray-700">
                      {file.file_name ?? `첨부파일 ${index + 1}`}
                      <span className="ml-2 text-xs text-gray-400">(미리보기 미지원)</span>
                    </span>
                  )}
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