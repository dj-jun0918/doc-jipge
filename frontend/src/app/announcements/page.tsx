"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import SearchFilter from "@/components/SearchFilter";
import DdayBadge from "@/components/DdayBadge";
import BookmarkButton from "@/components/BookmarkButton";
import { getBookmarks } from "@/lib/bookmark";

interface Announcement {
  id: string;
  title?: string;
  source?: string;
  region?: string;
  organization?: string;
  period_start?: string;
  period_end?: string;
}

// source 코드 → 화면 표시명 (SearchFilter 드롭다운과 동일 표기)
const SOURCE_LABELS: Record<string, string> = {
  bizinfo: "기업마당",
  kstartup: "K-Startup",
  mss: "중소벤처기업부",
};

interface AnnouncementResponse {
  items: Announcement[];
  total: number;
}

const PAGE_SIZE = 20;

export default function AnnouncementsPage() {
  const [data, setData] = useState<AnnouncementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [keyword, setKeyword] = useState("");
  const [source, setSource] = useState("");
  const [region, setRegion] = useState("");
  const [showBookmarks, setShowBookmarks] = useState(false);
  const [page, setPage] = useState(1);
  // 북마크는 localStorage에 있어 토글 시 재렌더 트리거가 필요
  const [, setBookmarkVersion] = useState(0);
  // 검색·페이지 이동을 연타하면 늦게 도착한 옛 응답이 최신 화면을 덮어쓸 수 있음
  const requestSeq = useRef(0);

  // 인자로 받은 필터·페이지가 우선 — 초기화처럼 state 반영 전에 호출해도 정확한 조건으로 조회
  const fetchAnnouncements = async (
    filters?: { keyword: string; source: string; region: string },
    pageArg?: number
  ) => {
    const f = filters ?? { keyword, source, region };
    const p = pageArg ?? page;
    const seq = ++requestSeq.current;
    try {
      setLoading(true);
      setError("");

      const params = new URLSearchParams();

      if (f.source) params.append("source", f.source);
      if (f.region) params.append("region", f.region);
      if (f.keyword.trim()) params.append("q", f.keyword.trim());
      params.append("limit", String(PAGE_SIZE));
      params.append("offset", String((p - 1) * PAGE_SIZE));

      const response = await fetch(`/api/announcements?${params.toString()}`);

      if (!response.ok) {
        throw new Error("공고 목록을 불러오지 못했습니다.");
      }

      const result: AnnouncementResponse = await response.json();
      if (seq !== requestSeq.current) return;
      setData(result);
    } catch (err) {
      if (seq !== requestSeq.current) return;
      console.error("Error fetching announcements:", err);
      setError("문제가 발생했습니다. 다시 시도해주세요.");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnouncements();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = () => {
    setPage(1);
    fetchAnnouncements(undefined, 1);
  };

  const handleReset = () => {
    setKeyword("");
    setSource("");
    setRegion("");
    setShowBookmarks(false);
    setPage(1);
    fetchAnnouncements({ keyword: "", source: "", region: "" }, 1);
  };

  const goToPage = (p: number) => {
    setPage(p);
    fetchAnnouncements(undefined, p);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 px-6 py-10">
        <section className="mx-auto max-w-5xl">
          <h1 className="mb-2 text-3xl font-bold text-gray-900">공고 목록</h1>
          <p className="text-gray-600">불러오는 중...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gray-50 px-6 py-10">
        <section className="mx-auto max-w-5xl">
          <h1 className="mb-2 text-3xl font-bold text-gray-900">공고 목록</h1>
          <p className="text-red-500">{error}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
    
      <section className="mx-auto max-w-5xl">
        <h1 className="mb-2 text-3xl font-bold text-gray-900">공고 목록</h1>
        <p className="mb-6 text-sm text-gray-600">
          전체 공고 수: {data?.total ?? 0}
        </p>

        <SearchFilter
          keyword={keyword}
          source={source}
          region={region}
          showBookmarks={showBookmarks}
          onKeywordChange={setKeyword}
          onSourceChange={setSource}
          onRegionChange={setRegion}
          onShowBookmarksChange={setShowBookmarks}
          onSearch={handleSearch}
          onReset={handleReset}
        />

        {(!data || data.items.length === 0) ? (
          <div className="rounded-xl border bg-white p-6 text-gray-600 shadow-sm">
            현재 등록된 공고가 없습니다.
          </div>
        ) : (() => {
          const displayedItems = data.items.filter(item => {
            if (!showBookmarks) return true;
            return getBookmarks().includes(String(item.id));
          });
          
          if (displayedItems.length === 0) {
            return (
              <div className="rounded-xl border bg-white p-6 text-gray-600 shadow-sm">
                조건에 맞는 공고가 없습니다.
              </div>
            );
          }

          return (
            <div className="grid gap-4">
              {displayedItems.map((item) => (
                <Link
                  key={item.id}
                  href={`/announcements/${item.id}`}
                  className="block rounded-xl border bg-white p-5 shadow-sm transition hover:shadow-md"
                >
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <h2 className="text-xl font-semibold text-gray-900">
                      {item.title ?? "제목 없음"}
                    </h2>
                    <div className="flex items-center gap-2">
                      <BookmarkButton
                        id={item.id}
                        size={20}
                        onToggle={() => setBookmarkVersion((v) => v + 1)}
                      />
                      <DdayBadge endDate={item.period_end} />
                    </div>
                  </div>

                  <div className="space-y-1 text-sm text-gray-600">
                    <p>출처: {item.source ? (SOURCE_LABELS[item.source] ?? item.source) : "-"}</p>
                    <p>지역: {item.region ?? "-"}</p>
                    {item.organization && <p>기관: {item.organization}</p>}
                    {item.period_start && item.period_end && (
                      <p>
                        접수기간: {item.period_start} ~ {item.period_end}
                      </p>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          );
        })()}

        {data && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-4">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => goToPage(page - 1)}
              className="rounded-lg border bg-white px-4 py-2 text-sm text-gray-700 shadow-sm transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← 이전
            </button>
            <span className="text-sm text-gray-600">
              {page} / {totalPages} 페이지
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => goToPage(page + 1)}
              className="rounded-lg border bg-white px-4 py-2 text-sm text-gray-700 shadow-sm transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              다음 →
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

/* async function getAnnouncements(): Promise<AnnouncementResponse> {
  // loading.tsx 테스트용 딜레이
  await new Promise((resolve) => setTimeout(resolve, 3000)); */