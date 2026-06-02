"use client";

import { useEffect, useState, use, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import MatchResultCard, { MatchField } from "@/components/MatchResultCard";
import ConfirmRequiredTab from "@/components/ConfirmRequiredTab";
import HwpxTableViewer from "@/components/HwpxTableViewer";
import RawTextDisplay from "@/components/RawTextDisplay";

// SSR 렌더링 시 브라우저 전용 객체(window, canvas 등) 사용으로 인한 ReferenceError를 원천 차단합니다.
const PdfViewer = dynamic(() => import("@/components/PdfViewer"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col h-[600px] bg-gray-100 rounded-2xl overflow-hidden border shadow-sm items-center justify-center gap-3">
      <div className="w-10 h-10 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
      <p className="text-gray-500 text-sm">PDF 뷰어 구성 요소를 초기화하는 중...</p>
    </div>
  ),
});

// 간단한 커스텀 디바운스 훅 구현
function useDebouncedCallback<T extends (...args: any[]) => any>(callback: T, delay: number) {
  const [timer, setTimer] = useState<NodeJS.Timeout | null>(null);

  const debouncedFn = useCallback((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    const newTimer = setTimeout(() => {
      callback(...args);
    }, delay);
    setTimer(newTimer);
  }, [callback, delay, timer]);

  return debouncedFn;
}

interface PageProps {
  params: Promise<{ id: string }> | { id: string };
  searchParams: Promise<{ announcement_id?: string }> | { announcement_id?: string };
}

interface Company {
  id: string;
  name: string;
  industry: string;
  region: string;
  revenue: number;
  employee_count: number;
  founded_date?: string;
}

interface CompanyMatchSummary {
  announcement_id: string;
  title: string;
  match_score: number;
  fulfilled_count: number;
  total_fields: number;
}

type MatchValue = string | number | boolean | null;

interface MatchResultDetailItem {
  field_name: string;
  status: "충족" | "미충족" | "확인필요" | "해당없음";
  score?: number | null;
  distance?: number | null;
  constraint_type?: "hard" | "soft" | null;
  company_value: MatchValue;
  requirement_value: MatchValue;
  evidence: string | null;
  processing_path: string;
}

interface MatchResultDetailResponse {
  company_id: string;
  announcement_id: string;
  items: MatchResultDetailItem[];
  stats: {
    충족: number;
    미충족: number;
    확인필요: number;
    해당없음: number;
  };
  matched_at: string | null;
}

interface AttachmentInfo {
  id: string;
  file_name: string;
  file_type: "pdf" | "hwp" | "hwpx" | "docx" | "zip";
  has_pdf: boolean;
}

interface AnnouncementDetail {
  id: string;
  title: string;
  source: string;
  attachments: AttachmentInfo[];
  structured_tables?: Array<{name: string; markdown: string}> | null;
}

function pickMainAttachment(attachments: AttachmentInfo[]): AttachmentInfo | null {
  if (!attachments) return null;
  return attachments.find(a => a.has_pdf)
      ?? attachments.find(a => a.file_type === "hwpx")
      ?? null;
}

function EvidencePlaceholder({ text }: { text: string }) {
  return (
    <div className="py-20 border border-dashed border-amber-300 rounded-xl flex flex-col items-center justify-center gap-3 bg-amber-50/20 text-amber-700">
      <svg className="h-10 w-10 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <p className="text-sm font-semibold">{text}</p>
    </div>
  );
}

function isPromise<T>(value: unknown): value is Promise<T> {
  return !!value && typeof (value as { then?: unknown }).then === "function";
}

export default function CompanyMatchingDetailPage(props: PageProps) {
  const params = isPromise<{ id: string }>(props.params)
    ? use(props.params)
    : props.params;

  const searchParams = isPromise<{ announcement_id?: string }>(props.searchParams)
    ? use(props.searchParams)
    : props.searchParams;

  const companyId = params?.id || "";
  const initialAnnId = searchParams?.announcement_id || "";

  // ==========================================
  // 1. All States Initialization
  // ==========================================
  const [company, setCompany] = useState<Company | null>(null);
  const [announcements, setAnnouncements] = useState<CompanyMatchSummary[]>([]);
  const [selectedAnnId, setSelectedAnnId] = useState<string>(initialAnnId);
  const [selectedAnnDetail, setSelectedAnnDetail] = useState<AnnouncementDetail | null>(null);
  const [matchDetails, setMatchDetails] = useState<MatchField[]>([]);
  const [stats, setStats] = useState<MatchResultDetailResponse["stats"] | null>(null);
  
  const [activeTab, setActiveTab] = useState<"all" | "confirm">("all");
  const [loadingCompany, setLoadingCompany] = useState<boolean>(true);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState<boolean>(true);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);

  const [companyError, setCompanyError] = useState<string | null>(null);
  const [companyNotFound, setCompanyNotFound] = useState<boolean>(false);
  const [annError, setAnnError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailRetryNonce, setDetailRetryNonce] = useState<number>(0);
  
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [evidenceText, setEvidenceText] = useState<string | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<any>(null);

  const [overrides, setOverrides] = useState<Partial<Company>>({});
  const [simResult, setSimResult] = useState<MatchResultDetailResponse | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [isWhatIfExpanded, setIsWhatIfExpanded] = useState<boolean>(false);

  // ==========================================
  // 2. Pure Helper Functions (Must be declared before hooks to prevent TDZ)
  // ==========================================
  const parseMatchResultItems = useCallback((items: MatchResultDetailItem[]) => {
    return (items || [])
      .filter((item) => item.status !== "해당없음")
      .map((item) => {
        let page: number | undefined;
        let text: string | undefined;
        let location: any = null;

        if (item.evidence) {
          try {
            const parsed = JSON.parse(item.evidence);
            page = parsed.page || parsed.page_num || parsed.location?.page;
            text = parsed.text || parsed.context;
            location = parsed.location || null;

            if (!location && page) {
              location = {
                location_type: "pdf_page",
                page: page,
              };
            }
          } catch {
            text = item.evidence;
            location = {
              location_type: "raw_text",
            };
          }
        }

        return {
          field_name: item.field_name,
          status: item.status as "충족" | "미충족" | "확인필요",
          criterion: String(item.requirement_value || ""),
          current_value: String(item.company_value || ""),
          reason: item.processing_path || "조건 평가 완료",
          evidence_source: text ? { page, text, location } : null,
          score: item.score !== undefined ? item.score : null,
          distance: item.distance !== undefined ? item.distance : null,
          constraint_type: item.constraint_type || null,
        };
      });
  }, []);

  const getBizAge = useCallback((foundedDateStr?: string) => {
    if (!foundedDateStr) return 0;
    const founded = new Date(foundedDateStr);
    const today = new Date();
    const diffTime = Math.abs(today.getTime() - founded.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return parseFloat((diffDays / 365.25).toFixed(2));
  }, []);

  const getSimulatedFoundedDate = useCallback((targetAgeYears: number) => {
    const today = new Date();
    const targetDays = targetAgeYears * 365.25;
    const simulatedMs = today.getTime() - targetDays * 24 * 60 * 60 * 1000;
    const simulatedDate = new Date(simulatedMs);
    return simulatedDate.toISOString().split("T")[0];
  }, []);

  // ==========================================
  // 3. API & Async Event Handlers / Hooks
  // ==========================================
  useEffect(() => {
    async function fetchCompany() {
      try {
        const res = await fetch(`/api/companies`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        let found = (data.items || []).find((c: Company) => c.id === companyId);
        
        if (found) {
          setCompany(found);
          setCompanyNotFound(false);
        } else {
          setCompanyNotFound(true);
        }
        setCompanyError(null);
      } catch (err) {
        console.error("기업 정보 로드 실패:", err);
        setCompanyError("기업 정보를 불러오지 못했습니다. 백엔드 서버 상태를 확인해 주세요.");
      } finally {
        setLoadingCompany(false);
      }
    }
    fetchCompany();
  }, [companyId]);

  useEffect(() => {
    async function fetchAnnouncements() {
      try {
        const res = await fetch(`/api/matching/${companyId}`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        let items = data.items || [];

        setAnnouncements(items);

        if (!selectedAnnId && items.length > 0) {
          setSelectedAnnId(items[0].announcement_id);
        }
        setAnnError(null);
      } catch (err) {
        console.error("매칭 공고 목록 로드 실패:", err);
        setAnnError("매칭 공고 목록을 불러오지 못했습니다.");
      } finally {
        setLoadingAnnouncements(false);
      }
    }
    fetchAnnouncements();
  }, [companyId, selectedAnnId]);

  useEffect(() => {
    if (!selectedAnnId) return;

    async function fetchDetailsAndMetadata() {
      setLoadingDetails(true);
      setHighlightPage(null);
      setEvidenceText(null);
      setSelectedLocation(null);
      setDetailError(null);
      setOverrides({});
      setSimResult(null);

      try {
        const matchRes = await fetch(`/api/matching/${companyId}?announcement_id=${selectedAnnId}`);
        if (!matchRes.ok) {
          throw new Error(`매칭 결과 HTTP ${matchRes.status}`);
        }
        const matchData: MatchResultDetailResponse = await matchRes.json();
        setStats(matchData.stats);

        const detailsList = parseMatchResultItems(matchData.items);
        setMatchDetails(detailsList);

        const annRes = await fetch(`/api/announcements?id=${selectedAnnId}`);
        if (!annRes.ok) {
          throw new Error(`공고 메타데이터 HTTP ${annRes.status}`);
        }
        const annData: AnnouncementDetail = await annRes.json();
        setSelectedAnnDetail(annData);
      } catch (err) {
        console.error("상세 매칭 결과 로드 실패:", err);
        setDetailError("매칭 상세 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
        setMatchDetails([]);
        setStats(null);
        setSelectedAnnDetail(null);
      } finally {
        setLoadingDetails(false);
      }
    }

    fetchDetailsAndMetadata();
  }, [companyId, selectedAnnId, detailRetryNonce, parseMatchResultItems]);

  const handleEvidenceClick = (page: number, text: string, location?: any) => {
    setHighlightPage(page);
    setEvidenceText(text);
    setSelectedLocation(location || null);
  };

  const handleSimulate = useDebouncedCallback(async (newOverrides: Partial<Company>) => {
    if (!companyId || !selectedAnnId) return;
    setIsSimulating(true);

    try {
      let calculatedFoundedDate = company?.founded_date;
      if (newOverrides.founded_date) {
        calculatedFoundedDate = newOverrides.founded_date;
      }

      const payload = {
        announcement_id: selectedAnnId,
        overrides: {
          revenue: newOverrides.revenue !== undefined ? newOverrides.revenue : null,
          employee_count: newOverrides.employee_count !== undefined ? newOverrides.employee_count : null,
          founded_date: calculatedFoundedDate || null,
          region: newOverrides.region || null,
          industry: newOverrides.industry || null,
        },
      };

      const res = await fetch(`/api/matching/${companyId}/simulate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`시뮬레이션 HTTP ${res.status}`);
      }

      const data: MatchResultDetailResponse = await res.json();
      setSimResult(data);
    } catch (err) {
      console.error("시뮬레이션 연동 실패:", err);
    } finally {
      setIsSimulating(false);
    }
  }, 300);

  // ==========================================
  // 4. Derived Variables & Fallbacks
  // ==========================================
  const selectedAnnSummary = announcements.find((a) => a.announcement_id === selectedAnnId);

  const originalBizAge = company?.founded_date ? getBizAge(company.founded_date) : 0;
  const originalRevenue = company?.revenue ?? 0;
  const originalEmployeeCount = company?.employee_count ?? 0;
  const originalRegion = company?.region ?? "";

  const isSimulatedActive = Object.keys(overrides).length > 0 && simResult !== null;
  const currentDetails = isSimulatedActive
    ? parseMatchResultItems(simResult.items)
    : matchDetails;

  const currentStats = isSimulatedActive
    ? simResult.stats
    : stats;

  const fulfilledCount = currentStats?.충족 ?? 0;
  const unfulfilledCount = currentStats?.미충족 ?? 0;
  const confirmRequiredCount = currentStats?.확인필요 ?? 0;
  const totalFields = currentDetails.length;

  const getMatchScorePct = () => {
    if (isSimulatedActive) {
      const scoredItems = simResult.items.filter(item => item.score !== null && item.status !== "해당없음");
      if (scoredItems.length === 0) return 0;
      const sum = scoredItems.reduce((acc, cur) => acc + (cur.score || 0), 0);
      return Math.round((sum / scoredItems.length) * 100);
    }
    return selectedAnnSummary ? Math.round(selectedAnnSummary.match_score * 100) : 0;
  };
  const matchScorePercentage = getMatchScorePct();

  const mainAttachment = selectedAnnDetail ? pickMainAttachment(selectedAnnDetail.attachments) : null;

  // 404 - 잘못된 company_id 직접 접근 처리
  if (!loadingCompany && companyNotFound) {
    return (
      <main className="min-h-screen bg-gray-50 text-gray-900 px-6 py-10 flex items-center justify-center">
        <div className="max-w-md text-center bg-white border rounded-2xl shadow-sm p-10">
          <svg className="mx-auto h-14 w-14 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h1 className="text-xl font-bold text-gray-900 mb-2">기업을 찾을 수 없습니다</h1>
          <p className="text-sm text-gray-500 leading-relaxed mb-6">
            ID <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">{companyId}</code> 에 해당하는 기업이 존재하지 않습니다.<br />
            URL을 다시 확인하거나 대시보드에서 기업을 선택해 주세요.
          </p>
          <Link
            href="/matching"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition"
          >
            ← 대시보드로 돌아가기
          </Link>
        </div>
      </main>
    );
  }

  // ==========================================
  // 5. What-if Slider Control Panel Component
  // ==========================================
  function WhatIfPanel() {
    if (!company) return null;

    const currentRevenue = overrides.revenue !== undefined ? overrides.revenue : originalRevenue;
    const currentBizAge = overrides.founded_date ? getBizAge(overrides.founded_date) : originalBizAge;
    const currentEmployeeCount = overrides.employee_count !== undefined ? overrides.employee_count : originalEmployeeCount;
    const currentRegion = overrides.region !== undefined ? overrides.region : originalRegion;

    return (
      <div className="rounded-2xl border border-blue-200 bg-white shadow-md mb-8 overflow-hidden transition-all duration-300">
        {/* Header Accordion Bar */}
        <button
          onClick={() => setIsWhatIfExpanded(!isWhatIfExpanded)}
          className="w-full text-left bg-gradient-to-r from-blue-50/50 via-indigo-50/10 to-white hover:from-blue-50 hover:via-indigo-50/20 px-6 py-4 flex items-center justify-between gap-4 border-b border-blue-100 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🔮</span>
            <div>
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                What-if 시뮬레이터 (실시간 기업 정보 가상 변경)
                {isSimulatedActive && (
                  <span className="text-[10px] bg-blue-100 text-blue-700 border border-blue-300 px-2 py-0.5 rounded-full font-bold animate-pulse">
                    가상 모드 활성화됨
                  </span>
                )}
                {isSimulating && (
                  <span className="text-xs text-gray-400 font-normal animate-pulse">
                    (시뮬레이션 분석 중...)
                  </span>
                )}
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                기업의 매출액, 업력, 지역, 임직원 수를 가상으로 조정하여 실시간 매칭률과 충족 여부의 변화를 시뮬레이션합니다. (FastAPI 실시간 계산 연동)
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {isSimulatedActive && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setOverrides({});
                  setSimResult(null);
                }}
                className="text-xs text-red-500 hover:text-red-700 bg-red-50 border border-red-200 px-2.5 py-1 rounded-lg transition font-semibold cursor-pointer"
              >
                초기화
              </button>
            )}
            <svg
              className={`w-5 h-5 text-gray-400 transform transition-transform duration-300 ${
                isWhatIfExpanded ? "rotate-180" : ""
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {/* Simulated Sliders Grid */}
        {isWhatIfExpanded && (
          <div className="p-6 bg-gradient-to-b from-blue-50/5 to-white grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 border-b border-gray-100">
            {/* 1. 매출액 슬라이더 */}
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-gray-600">💰 가상 매출액</span>
                <span className="font-black text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                  {(currentRevenue / 100000000).toFixed(1)}억원
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="10000000000" // 100억원
                step="100000000" // 1억원
                value={currentRevenue}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  const next = { ...overrides, revenue: val };
                  setOverrides(next);
                  handleSimulate(next);
                }}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-[10px] text-gray-400">
                <span>0원</span>
                <span>원본: {(originalRevenue / 100000000).toFixed(1)}억</span>
                <span>100억원</span>
              </div>
            </div>

            {/* 2. 업력 슬라이더 */}
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-gray-600">⏳ 가상 업력</span>
                <span className="font-black text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                  {currentBizAge.toFixed(1)}년
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="15"
                step="0.5"
                value={currentBizAge}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  const simulatedDate = getSimulatedFoundedDate(val);
                  const next = { ...overrides, founded_date: simulatedDate };
                  setOverrides(next);
                  handleSimulate(next);
                }}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-[10px] text-gray-400">
                <span>0년</span>
                <span>원본: {originalBizAge.toFixed(1)}년</span>
                <span>15년</span>
              </div>
            </div>

            {/* 3. 종업원 수 슬라이더 */}
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-gray-600">👥 가상 임직원 수</span>
                <span className="font-black text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                  {currentEmployeeCount}명
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="300"
                step="5"
                value={currentEmployeeCount}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  const next = { ...overrides, employee_count: val };
                  setOverrides(next);
                  handleSimulate(next);
                }}
                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-[10px] text-gray-400">
                <span>0명</span>
                <span>원본: {originalEmployeeCount}명</span>
                <span>300명</span>
              </div>
            </div>

            {/* 4. 지역 선택 */}
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-gray-600">📍 가상 소재지</span>
                <span className="font-black text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                  {currentRegion}
                </span>
              </div>
              <select
                value={currentRegion}
                onChange={(e) => {
                  const val = e.target.value;
                  const next = { ...overrides, region: val };
                  setOverrides(next);
                  handleSimulate(next);
                }}
                className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs text-gray-700 bg-white focus:border-blue-500 focus:outline-none cursor-pointer"
              >
                <option value="서울특별시">서울</option>
                <option value="경기도">경기</option>
                <option value="인천광역시">인천</option>
                <option value="부산광역시">부산</option>
                <option value="대구광역시">대구</option>
                <option value="광주광역시">광주</option>
                <option value="대전광역시">대전</option>
                <option value="울산광역시">울산</option>
                <option value="세종특별자치시">세종</option>
                <option value="강원특별자치도">강원</option>
                <option value="충청북도">충북</option>
                <option value="충청남도">충남</option>
                <option value="전라북도">전북</option>
                <option value="전라남도">전남</option>
                <option value="경상북도">경북</option>
                <option value="경상남도">경남</option>
                <option value="제주특별자치도">제주</option>
              </select>
              <div className="flex justify-between text-[10px] text-gray-400">
                <span>전국 17개 지자체 중 선택</span>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ==========================================
  // 6. JSX Render
  // ==========================================
  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 px-6 py-10">
      <section className="mx-auto max-w-7xl">
        {/* 상단 브레드크럼 및 뒤로가기 */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            href="/matching"
            className="inline-flex items-center gap-2 text-sm font-semibold text-gray-500 hover:text-blue-600 transition"
          >
            ← 대시보드로 돌아가기
          </Link>
          {company && (
            <span className="text-xs bg-gray-100 border text-gray-600 px-3 py-1 rounded-full font-medium">
              🏢 {company.name} ({company.industry})
            </span>
          )}
        </div>

        {/* 기업 정보 로드 실패 알림 */}
        {companyError && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 flex items-start gap-3">
            <svg className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-sm font-semibold text-red-800">{companyError}</p>
          </div>
        )}

        {/* 상단 기업 분석 요약 헤더 */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm mb-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              📂 기업 맞춤형 매칭 상세 분석
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              선택한 정부지원사업의 세부 자격요건 항목들과 매칭 엔진 분석 결과를 원문 근거와 함께 비교 검토합니다.
            </p>
          </div>

          {/* 종합 매칭률 게이지 보드 (백엔드 점수 반영) */}
          <div className="bg-gray-50 border p-4 rounded-xl flex items-center gap-4 min-w-[240px]">
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-gray-400">종합 매칭률</span>
              <span className="text-2xl font-black text-blue-600 mt-1">{matchScorePercentage}%</span>
            </div>
            <div className="flex-1">
              <div className="w-full h-2 rounded-full bg-gray-200 overflow-hidden shadow-inner mb-1">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-500"
                  style={{ width: `${matchScorePercentage}%` }}
                />
              </div>
              <span className="text-[10px] text-gray-400 font-medium">
                {fulfilledCount} / {totalFields}개 요건 충족
              </span>
            </div>
          </div>
        </div>

        {/* 회사별 공고 매칭 결과 요약 카드 */}
        {company && selectedAnnDetail && (
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm mb-8 overflow-hidden">
            <div className="bg-gray-50/50 border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h2 className="text-base font-bold text-gray-800 flex items-center gap-2">
                🤝 [{company.industry || "기업"}] vs {selectedAnnDetail.title}
              </h2>
              <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1 rounded-full font-bold">
                매칭률: {matchScorePercentage}%
              </span>
            </div>
            
            <div className="p-6 grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* 요약 카운트 뱃지들 */}
              <div className="md:col-span-4 flex flex-wrap gap-4 items-center">
                <div className="flex-1 min-w-[120px] bg-green-50/30 border border-green-100 p-4 rounded-xl flex flex-col items-center justify-center">
                  <span className="text-sm font-semibold text-green-700 mb-1">✅ 충족</span>
                  <span className="text-2xl font-bold text-green-800">{fulfilledCount}개</span>
                </div>
                <div className="flex-1 min-w-[120px] bg-red-50/30 border border-red-100 p-4 rounded-xl flex flex-col items-center justify-center">
                  <span className="text-sm font-semibold text-red-700 mb-1">❌ 미충족</span>
                  <span className="text-2xl font-bold text-red-800">{unfulfilledCount}개</span>
                </div>
                <div className="flex-1 min-w-[120px] bg-amber-50/30 border border-amber-100 p-4 rounded-xl flex flex-col items-center justify-center">
                  <span className="text-sm font-semibold text-amber-700 mb-1">⚠️ 확인필요</span>
                  <span className="text-2xl font-bold text-amber-800">{confirmRequiredCount}개</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 🔮 What-if 시뮬레이터 패널 랜더링 */}
        <WhatIfPanel />

        {/* 메인 2분할 레이아웃 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* 1. 좌측 공고 목록 컬럼 (lg: 4/12) */}
          <div className="lg:col-span-4 space-y-4">
            <div className="rounded-2xl border bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900 mb-4 pb-2 border-b flex items-center gap-2">
                📋 매칭 시도된 공고 목록
              </h3>
              
              {loadingAnnouncements ? (
                <div className="py-10 text-center flex flex-col items-center gap-2">
                  <div className="w-8 h-8 border-[3px] border-gray-200 border-t-blue-600 rounded-full animate-spin" />
                  <p className="text-xs text-gray-400">공고 목록 불러오는 중...</p>
                </div>
              ) : annError ? (
                <div className="py-8 px-3 text-center bg-red-50/40 border border-red-100 rounded-lg">
                  <p className="text-xs text-red-700 font-semibold">{annError}</p>
                </div>
              ) : announcements.length === 0 ? (
                <p className="text-gray-400 text-xs py-8 text-center">매칭 공고가 존재하지 않습니다.</p>
              ) : (
                <div className="space-y-2.5 max-h-[600px] overflow-auto pr-1">
                  {announcements.map((ann) => {
                    const isSelected = ann.announcement_id === selectedAnnId;
                    const scorePct = Math.round(ann.match_score * 100);

                    return (
                      <button
                        key={ann.announcement_id}
                        onClick={() => setSelectedAnnId(ann.announcement_id)}
                        className={`w-full text-left p-4 rounded-xl border transition-all duration-200 flex flex-col gap-2 cursor-pointer ${
                          isSelected
                            ? "border-blue-600 bg-blue-50/20 shadow-sm"
                            : "border-gray-200 bg-white hover:bg-gray-50"
                        }`}
                      >
                        <h4 className={`text-sm font-bold truncate leading-snug ${
                          isSelected ? "text-blue-600" : "text-gray-800"
                        }`}>
                          {ann.title}
                        </h4>
                        
                        <div className="flex items-center justify-between mt-1 text-[11px]">
                          <span className="text-gray-400">
                            요건 필드: {ann.total_fields}개
                          </span>
                          <span className="font-black px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                            {scorePct}% 충족
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* 2. 우측 상세 판정 및 PDF 뷰어 레이아웃 (lg: 8/12) */}
          <div className="lg:col-span-8 space-y-8">
            {/* 상단 탭 뷰 전환 컨트롤 */}
            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between border-b pb-4 mb-6">
                <div className="flex gap-2">
                  <button
                    onClick={() => setActiveTab("all")}
                    className={`px-4 py-2 text-sm font-bold rounded-lg transition cursor-pointer ${
                      activeTab === "all"
                        ? "bg-blue-600 text-white shadow-sm"
                        : "text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                    }`}
                  >
                    🔍 전체 요건 분석 ({totalFields}개)
                  </button>
                  <button
                    onClick={() => setActiveTab("confirm")}
                    className={`px-4 py-2 text-sm font-bold rounded-lg transition flex items-center gap-1.5 cursor-pointer ${
                      activeTab === "confirm"
                        ? "bg-amber-500 text-white shadow-sm"
                        : "text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                    }`}
                  >
                    ⚠️ 수동 확인 필요
                    {currentDetails.filter((f) => f.status === "확인필요").length > 0 && (
                      <span className={`text-[10px] font-black rounded-full px-1.5 py-0.5 ${
                        activeTab === "confirm" ? "bg-white text-amber-700" : "bg-amber-100 text-amber-800"
                      }`}>
                        {currentDetails.filter((f) => f.status === "확인필요").length}
                      </span>
                    )}
                  </button>
                </div>

                <div className="text-xs text-gray-400 font-medium">
                  {selectedAnnDetail && `출처: ${selectedAnnDetail.source}`}
                </div>
              </div>

              {/* 탭 본문 영역 */}
              {loadingDetails ? (
                <div className="py-20 text-center flex flex-col items-center justify-center gap-3">
                  <div className="w-10 h-10 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
                  <p className="text-gray-400 text-sm">자격요건 평가 상세 데이터를 집계하는 중...</p>
                </div>
              ) : detailError ? (
                <div className="py-16 text-center flex flex-col items-center justify-center gap-3 bg-red-50/40 border border-red-200 rounded-xl px-6">
                  <svg className="h-10 w-10 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-sm font-semibold text-gray-900">{detailError}</p>
                  <button
                    onClick={() => setDetailRetryNonce((n) => n + 1)}
                    className="mt-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition cursor-pointer"
                  >
                    다시 시도
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  {activeTab === "all" ? (
                    currentDetails.length === 0 ? (
                      <p className="text-gray-400 text-sm py-12 text-center">자격 요건 데이터가 존재하지 않습니다.</p>
                    ) : (
                      <div className="grid grid-cols-1 gap-5">
                        {currentDetails.map((field) => (
                          <MatchResultCard
                            key={field.field_name}
                            field={field}
                            onEvidenceClick={handleEvidenceClick}
                          />
                        ))}
                      </div>
                    )
                  ) : (
                    <ConfirmRequiredTab
                      fields={currentDetails}
                      onEvidenceClick={handleEvidenceClick}
                    />
                  )}
                </div>
              )}
            </div>

            {/* 하단 PDF / HWPX / 텍스트 원문 연동 뷰어 섹션 */}
            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2 pb-3 border-b">
                <div>
                  <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    📄 공고 원문 매칭 통합 뷰어
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    자격요건 판정 카드의 근거 버튼을 누르면 해당 증거 유형(PDF 영역, HWPX 테이블, 텍스트)에 맞는 전용 뷰어에 원문이 정밀 하이라이트됩니다.
                  </p>
                </div>
              </div>

              {/* 🌟 B-1 Evidence 분기 렌더링 적용 */}
              {(() => {
                if (selectedLocation?.location_type === "hwpx_table") {
                  return (
                    <div className="h-[500px]">
                      <HwpxTableViewer
                        tables={selectedAnnDetail?.structured_tables}
                        location={selectedLocation}
                      />
                    </div>
                  );
                }

                if (selectedLocation?.location_type === "raw_text") {
                  return (
                    <RawTextDisplay text={evidenceText || ""} />
                  );
                }

                // 기본 fallback은 기존의 첨부파일 기반 PDF Viewer 또는 플레이스홀더
                if (mainAttachment) {
                  if (mainAttachment.has_pdf) {
                    return (
                      <div className="h-[600px]">
                        <PdfViewer
                          pdfUrl={`/api/attachments/${mainAttachment.id}/file`}
                          highlightPage={highlightPage}
                          evidenceText={evidenceText}
                          location={selectedLocation}
                        />
                      </div>
                    );
                  }
                  if (mainAttachment.file_type === "hwpx") {
                    return <EvidencePlaceholder text="HWPX 첨부파일의 원문 미리보기는 준비 중입니다" />;
                  }
                  return (
                    <div className="py-20 border border-dashed rounded-xl flex flex-col items-center justify-center gap-3 bg-gray-50 text-gray-400">
                      <p className="text-sm font-semibold">원문 표시 불가 (지원하지 않는 파일 형식)</p>
                    </div>
                  );
                }

                return (
                  <div className="py-20 border border-dashed rounded-xl flex flex-col items-center justify-center gap-3 bg-gray-50 text-gray-400">
                    <svg className="h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="text-sm font-semibold">원문 표시 불가 (조회할 공고 PDF 경로 정보가 존재하지 않습니다.)</p>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
