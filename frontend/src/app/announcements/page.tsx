"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import SearchFilter from "@/components/SearchFilter";
import DdayBadge from "@/components/DdayBadge";
import BookmarkButton from "@/components/BookmarkButton";
import { getBookmarks } from "@/lib/bookmark";

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

export default function AnnouncementsPage() {
  const [data, setData] = useState<AnnouncementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [keyword, setKeyword] = useState("");
  const [source, setSource] = useState("");
  const [region, setRegion] = useState("");
  const [showBookmarks, setShowBookmarks] = useState(false);

  const fetchAnnouncements = async () => {
    try {
      setLoading(true);
      setError("");

      const params = new URLSearchParams();

      if (source) params.append("source", source);
      if (region) params.append("region", region);
      if (keyword) params.append("keyword", keyword);
      
      const response = await fetch(
        `/api/announcements${params.toString() ? `?${params.toString()}` : ""}`
      );

      if (!response.ok) {
        throw new Error("공고 목록을 불러오지 못했습니다.");
      }

      const result: AnnouncementResponse = await response.json();

      let filteredItems = result.items;

      if (keyword.trim()) {
        filteredItems = filteredItems.filter((item) =>
          (item.title ?? "").toLowerCase().includes(keyword.toLowerCase())
        );
      }

      setData({
        ...result,
        items: filteredItems,
        total: filteredItems.length,
      });
    } catch (err) {
      console.error("Error fetching announcements:", err);
      setError("문제가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnouncements();
  }, []);

  const handleSearch = () => {
    fetchAnnouncements();
  };

  const handleReset = () => {
    setKeyword("");
    setSource("");
    setRegion("");
    setShowBookmarks(false);

    setTimeout(() => {
      fetchAnnouncements();
    }, 0);
  };

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

        {/* D-day 배지 테스트용 코드 */}
        <div className="mb-6 rounded-xl border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          D-day 배지 테스트
        </h2>
        <div className="flex flex-wrap gap-3">
          <DdayBadge endDate="2026-05-05" />
          <DdayBadge endDate="2026-04-30" />
          <DdayBadge endDate="2026-04-28" />
          <DdayBadge endDate="2026-04-27" />
          <DdayBadge endDate="2026-04-25" />
        </div>
      </div>

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
                      <BookmarkButton id={item.id} size={20} />
                      <DdayBadge endDate={item.end_date} />
                    </div>
                  </div>

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
                </Link>
              ))}
            </div>
          );
        })()}
      </section>
    </main>
  );
}

/* async function getAnnouncements(): Promise<AnnouncementResponse> {
  // loading.tsx 테스트용 딜레이
  await new Promise((resolve) => setTimeout(resolve, 3000)); */