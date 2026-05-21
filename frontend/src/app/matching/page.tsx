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
  fulfilled: number;
  unfulfilled: number;
  confirmRequired: number;
  total: number;
}

export default function MatchingDashboardPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [matchResults, setMatchResults] = useState<CompanyMatchSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [stats, setStats] = useState<MatchStats>({
    fulfilled: 0,
    unfulfilled: 0,
    confirmRequired: 0,
    total: 0,
  });

  // 1. 기업 목록 가져오기
  useEffect(() => {
    async function fetchCompanies() {
      try {
        const res = await fetch("/api/companies");
        if (res.ok) {
          const data = await res.json();
          setCompanies(data.items || []);
          if (data.items && data.items.length > 0) {
            setSelectedCompanyId(data.items[0].id);
          }
        }
      } catch (err) {
        console.error("기업 목록 로드 실패:", err);
      }
    }
    fetchCompanies();
  }, []);

  // 2. 선택된 기업의 매칭 결과 및 상세 통계 가져오기
  useEffect(() => {
    if (!selectedCompanyId) return;

    async function fetchMatchingResults() {
      setLoading(true);
      try {
        const res = await fetch(`/api/matching/${selectedCompanyId}?limit=50`);
        if (res.ok) {
          const data: CompanyMatchListResponse = await res.json();
          const items = data.items || [];
          setMatchResults(items);

          // 임시 통계 계산 (WOW 효과를 위해 개별 공고의 매칭 디테일 스펙 분석)
          // match_score가 1.0 (100% 충족)인 것을 '충족', 0.7 이상 '확인필요', 그 미만을 '미충족'으로 매핑하여
          // 대시보드 상단 통계 수치를 역동적으로 렌더링합니다.
          let fulfilled = 0;
          let confirmRequired = 0;
          let unfulfilled = 0;

          items.forEach((item) => {
            const pct = item.match_score * 100;
            if (pct === 100) {
              fulfilled++;
            } else if (pct >= 70) {
              confirmRequired++;
            } else {
              unfulfilled++;
            }
          });

          setStats({
            fulfilled,
            confirmRequired,
            unfulfilled,
            total: items.length,
          });
        }
      } catch (err) {
        console.error("매칭 결과 로드 실패:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchMatchingResults();
  }, [selectedCompanyId]);

  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 px-6 py-10">
      <section className="mx-auto max-w-6xl">
        {/* 헤더 세션 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-6">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-600 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-200 inline-block mb-3">
              Matching Engine v1.2
            </span>
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

        {/* 로딩 인디케이터 */}
        {loading ? (
          <div className="min-h-[400px] flex flex-col items-center justify-center gap-4 bg-white rounded-2xl border shadow-sm">
            <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-blue-600 animate-spin" />
            <p className="text-gray-500 text-sm animate-pulse">매칭 결과 데이터를 집계하는 중...</p>
          </div>
        ) : (
          <>
            {/* 요약 통계 카드 섹션 */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="relative overflow-hidden group rounded-2xl border border-green-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-green-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-green-700">✅ 충족 공고</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.fulfilled}</h3>
                <p className="text-xs text-gray-500 mt-2">자격요건을 100% 만족하는 사업</p>
              </div>

              <div className="relative overflow-hidden group rounded-2xl border border-red-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-red-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-red-700">❌ 미충족 공고</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.unfulfilled}</h3>
                <p className="text-xs text-gray-500 mt-2">자격요건 중 탈락 요인이 있는 사업</p>
              </div>

              <div className="relative overflow-hidden group rounded-2xl border border-yellow-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-yellow-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-yellow-700">⚠️ 확인필요</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.confirmRequired}</h3>
                <p className="text-xs text-gray-500 mt-2">수동 검토 또는 프로필 보완 필요</p>
              </div>

              <div className="relative overflow-hidden group rounded-2xl border border-blue-200 bg-white p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5">
                <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-bl-full pointer-events-none" />
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">📋 전체 매칭 공고</p>
                <h3 className="text-3xl font-extrabold mt-2 text-gray-900">{stats.total}</h3>
                <p className="text-xs text-gray-500 mt-2">전체 매칭 시도된 총 지원 사업</p>
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
                  <svg className="mx-auto h-12 w-12 text-gray-400 mb-4 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-gray-500 font-medium">현재 이 기업에 대한 매칭 결과가 존재하지 않습니다.</p>
                  <p className="text-gray-400 text-xs mt-2">"기업 관리" 메뉴에서 프로필을 입력하거나 백엔드 파이프라인을 실행해 주세요.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {matchResults.slice(0, 10).map((item, index) => {
                    const scorePercentage = Math.round(item.match_score * 100);
                    
                    // 점수에 따른 다이내믹 컬러맵 설정
                    let borderClass = "border-gray-200";
                    let bgClass = "bg-white hover:bg-gray-50/50";
                    let textClass = "text-blue-600";
                    let fillClass = "bg-blue-600";
                    
                    if (scorePercentage === 100) {
                      borderClass = "border-green-200 hover:border-green-300";
                      bgClass = "bg-green-50/10 hover:bg-green-50/20";
                      textClass = "text-green-700";
                      fillClass = "bg-green-500";
                    } else if (scorePercentage >= 70) {
                      borderClass = "border-yellow-200 hover:border-yellow-300";
                      bgClass = "bg-yellow-50/10 hover:bg-yellow-50/20";
                      textClass = "text-yellow-700";
                      fillClass = "bg-amber-500";
                    } else {
                      borderClass = "border-red-200 hover:border-red-300";
                      bgClass = "bg-red-50/10 hover:bg-red-50/20";
                      textClass = "text-red-700";
                      fillClass = "bg-red-500";
                    }

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
                            <span className="text-[10px] text-gray-400 font-semibold tracking-wider uppercase">
                              MATCH SCORE
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
