"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Company {
  id: string;
  name: string;
  industry: string;
  region: string;
}

interface CompanyMatchSummary {
  announcement_id: string;
  title: string;
  match_score: number;
  fulfilled_count: number;
  total_fields: number;
}

interface CompanyMatchListResponse {
  company_id: string;
  items: CompanyMatchSummary[];
  total: number;
}

interface MatchStats {
  totalMatches: number;
  averageScore: number;
  highestScore: number;
  perfectMatches: number;
}

export default function MatchingDashboardPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [matchResults, setMatchResults] = useState<CompanyMatchSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [companiesError, setCompaniesError] = useState<string | null>(null);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState<number>(0);
  const [stats, setStats] = useState<MatchStats>({
    totalMatches: 0,
    averageScore: 0,
    highestScore: 0,
    perfectMatches: 0,
  });

  // 1. 기업 목록 가져오기
  useEffect(() => {
    async function fetchCompanies() {
      try {
        const res = await fetch("/api/companies");
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        setCompanies(data.items || []);
        if (data.items && data.items.length > 0) {
          setSelectedCompanyId(data.items[0].id);
        }
        setCompaniesError(null);
      } catch (err) {
        console.error("기업 목록 로드 실패:", err);
        setCompaniesError("기업 목록을 불러오지 못했습니다. 백엔드 서버 상태를 확인해 주세요.");
      }
    }
    fetchCompanies();
  }, []);

  // 2. 선택된 기업의 매칭 결과 및 상세 통계 가져오기
  useEffect(() => {
    if (!selectedCompanyId) return;

    async function fetchMatchingResults() {
      setLoading(true);
      setMatchError(null);
      try {
        const res = await fetch(`/api/matching/${selectedCompanyId}?limit=50`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data: CompanyMatchListResponse = await res.json();
        const items = data.items || [];
        setMatchResults(items);

        // 임의 점수 분류 제거 -> 객관적인 종합 지표 집계
        let totalScore = 0;
        let highest = 0;
        let perfect = 0;

        items.forEach((item) => {
          const scorePct = item.match_score * 100;
          totalScore += scorePct;
          if (scorePct > highest) {
            highest = scorePct;
          }
          if (scorePct === 100) {
            perfect++;
          }
        });

        const avg = items.length > 0 ? Math.round(totalScore / items.length) : 0;

        setStats({
          totalMatches: items.length,
          averageScore: avg,
          highestScore: Math.round(highest),
          perfectMatches: perfect,
        });
      } catch (err) {
        console.error("매칭 결과 로드 실패:", err);
        setMatchError("매칭 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
        setMatchResults([]);
        setStats({ totalMatches: 0, averageScore: 0, highestScore: 0, perfectMatches: 0 });
      } finally {
        setLoading(false);
      }
    }

    fetchMatchingResults();
  }, [selectedCompanyId, retryNonce]);

  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 px-6 py-10">
      <section className="mx-auto max-w-6xl">
        {/* 헤더 세션 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900">
              매칭 결과 대시보드
            </h1>
            <p className="text-gray-600 mt-2 text-sm">
              기업의 프로필과 정부지원사업 공고 자격요건을 정밀 매칭한 실시간 시각화 보드입니다.
            </p>
          </div>

          {/* 기업 선택 셀렉터 */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <label className="text-sm font-medium text-gray-700">분석 기업 선택</label>
            <div className="relative">
              <select
                value={selectedCompanyId}
                onChange={(e) => setSelectedCompanyId(e.target.value)}
                className="appearance-none bg-white border border-gray-300 rounded-xl px-5 py-3 pr-10 text-sm font-semibold text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all hover:bg-gray-50 cursor-pointer shadow-sm"
              >
                {companies.map((company) => (
                  <option key={company.id} value={company.id} className="text-gray-900">
                    {company.name} ({company.industry})
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-gray-500">
                <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                  <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* 기업 목록 로드 실패 알림 */}
        {companiesError && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 flex items-start gap-3">
            <svg className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-red-800">{companiesError}</p>
              <p className="text-xs text-red-600 mt-1">새로고침으로 재시도하거나 백엔드 로그를 확인하세요.</p>
            </div>
          </div>
        )}

        {/* 로딩 인디케이터 */}
        {loading ? (
          <div className="min-h-[400px] flex flex-col items-center justify-center gap-4 bg-white rounded-2xl border shadow-sm">
            <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-blue-600 animate-spin" />
            <p className="text-gray-500 text-sm">매칭 결과 데이터를 집계하는 중...</p>
          </div>
        ) : matchError ? (
          <div className="min-h-[400px] flex flex-col items-center justify-center gap-3 bg-white rounded-2xl border border-red-200 shadow-sm px-6 text-center">
            <svg className="h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-base font-semibold text-gray-900">{matchError}</p>
            <button
              onClick={() => setRetryNonce((n) => n + 1)}
              className="mt-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition cursor-pointer"
            >
              다시 시도
            </button>
          </div>
        ) : (
          <>
            {/* 요약 통계 카드 섹션 (객관적 지표 카드들로 리뉴얼) */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="relative overflow-hidden group rounded-2xl border border-blue-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">📋 전체 매칭 공고</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.totalMatches}</h3>
                <p className="text-xs text-gray-500 mt-2">전체 매칭 시도된 총 지원 사업</p>
              </div>

              <div className="relative overflow-hidden group rounded-2xl border border-indigo-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">📊 평균 매칭률</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.averageScore}%</h3>
                <p className="text-xs text-gray-500 mt-2">비교 분석된 공고들의 평균 충족 비율</p>
              </div>

              <div className="relative overflow-hidden group rounded-2xl border border-purple-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-purple-700">✨ 최고 매칭률</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.highestScore}%</h3>
                <p className="text-xs text-gray-500 mt-2">가장 높은 충족 결과를 보인 비율</p>
              </div>

              <div className="relative overflow-hidden group rounded-2xl border border-green-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-green-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-green-700">✅ 100% 매칭 공고</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.perfectMatches}</h3>
                <p className="text-xs text-gray-500 mt-2">자격요건을 완벽히 충족하는 사업</p>
              </div>
            </div>

            {/* 추천 공고 TOP 10 섹션 */}
            <div className="rounded-2xl border bg-white p-8 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4 border-b pb-5">
                <div>
                  <h2 className="text-2xl font-bold tracking-tight text-gray-900 flex items-center gap-2">
                    🔥 추천 공고 TOP 10
                  </h2>
                  <p className="text-gray-500 text-xs sm:text-sm mt-1">
                    충족률(매칭 점수) 기준 상위 10개 추천 정부지원사업입니다.
                  </p>
                </div>
                
                {selectedCompany && (
                  <Link
                    href={`/matching/${selectedCompany.id}`}
                    className="inline-flex items-center gap-2 self-start rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs sm:text-sm px-5 py-3 transition shadow-sm hover:shadow-md hover:-translate-y-0.5 active:translate-y-0"
                  >
                    공고별 세부 매칭 분석 보기 →
                  </Link>
                )}
              </div>

              {matchResults.length === 0 ? (
                <div className="py-20 text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-gray-500 font-medium">현재 이 기업에 대한 매칭 결과가 존재하지 않습니다.</p>
                  <p className="text-gray-400 text-xs mt-2">"기업 관리" 메뉴에서 프로필을 입력하거나 백엔드 파이프라인을 실행해 주세요.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {matchResults.slice(0, 10).map((item, index) => {
                    const scorePercentage = Math.round(item.match_score * 100);
                    
                    // 💡 임의 점수 분류 제거 및 표준 블루 테마 적용
                    const borderClass = "border-gray-200 hover:border-blue-200";
                    const bgClass = "bg-white hover:bg-blue-50/5";
                    const textClass = "text-blue-600";
                    const fillClass = "bg-blue-600";

                    return (
                      <div
                        key={item.announcement_id}
                        className={`flex flex-col md:flex-row md:items-center justify-between p-5 rounded-xl border ${borderClass} ${bgClass} transition-all duration-300 hover:-translate-x-1 group relative`}
                      >
                        {/* 랭킹 뱃지 */}
                        <div className="flex items-center gap-4 mb-3 md:mb-0">
                          <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-black shadow-sm ${
                            index === 0 ? "bg-amber-400 text-amber-950" : 
                            index === 1 ? "bg-gray-300 text-gray-900" : 
                            index === 2 ? "bg-amber-700 text-amber-50" : "bg-gray-100 text-gray-500"
                          }`}>
                            {index + 1}
                          </span>
                          <div>
                            <h4 className="font-bold text-gray-900 text-base tracking-tight group-hover:text-blue-600 transition-colors pr-4">
                              {item.title}
                            </h4>
                            <p className="text-gray-500 text-xs mt-1">
                              총 자격 요건 필드: {item.total_fields}개 중 {item.fulfilled_count}개 충족
                            </p>
                          </div>
                        </div>

                        {/* 매칭 충족률 게이지 바 */}
                        <div className="flex items-center gap-6 min-w-[200px] justify-between md:justify-end">
                          <div className="flex flex-col items-end gap-0.5">
                            <span className={`text-lg font-black tracking-tight ${textClass}`}>
                              {scorePercentage}%
                            </span>
                            <span className="text-[10px] text-gray-400 font-semibold">
                              매칭 점수
                            </span>
                          </div>

                          <div className="w-24 h-2 rounded-full bg-gray-200 overflow-hidden shadow-inner">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${fillClass}`}
                              style={{ width: `${scorePercentage}%` }}
                            />
                          </div>

                          {selectedCompany && (
                            <Link
                              href={`/matching/${selectedCompany.id}?announcement_id=${item.announcement_id}`}
                              className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-gray-50 hover:border-gray-300 transition shadow-sm"
                            >
                              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                              </svg>
                            </Link>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </section>
    </main>
  );
}

