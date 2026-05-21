"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import MatchResultCard, { MatchField } from "@/components/MatchResultCard";
import ConfirmRequiredTab from "@/components/ConfirmRequiredTab";

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
}

interface CompanyMatchSummary {
  announcement_id: string;
  title: string;
  match_score: number;
  fulfilled_count: number;
  total_fields: number;
}

interface MatchResultDetailItem {
  field_name: string;
  status: "충족" | "미충족" | "확인필요" | "해당없음";
  company_value: any;
  requirement_value: any;
  evidence: any;
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

interface AnnouncementDetail {
  id: string;
  title: string;
  source: string;
  doc_url?: string;
  local_path?: string;
  converted_pdf_path?: string;
}

export default function CompanyMatchingDetailPage(props: PageProps) {
  // Next.js 15+ Client Component에서는 로컬 dev 런타임에 params가 일반 동기 객체일 때가 있습니다.
  // 이 경우 use() 훅을 직접 호출하면 런타임 크래시가 나므로 thenable(Promise) 여부를 안전하게 확인하고 분기합니다.
  const params = (props.params && typeof (props.params as any).then === "function")
    ? use(props.params as any)
    : (props.params as any);

  const searchParams = (props.searchParams && typeof (props.searchParams as any).then === "function")
    ? use(props.searchParams as any)
    : (props.searchParams as any);
  
  const companyId = params?.id || "";
  const initialAnnId = searchParams?.announcement_id || "";

  // Core States
  const [company, setCompany] = useState<Company | null>(null);
  const [announcements, setAnnouncements] = useState<CompanyMatchSummary[]>([]);
  const [selectedAnnId, setSelectedAnnId] = useState<string>(initialAnnId);
  const [selectedAnnDetail, setSelectedAnnDetail] = useState<AnnouncementDetail | null>(null);
  const [matchDetails, setMatchDetails] = useState<MatchField[]>([]);
  
  // UI States
  const [activeTab, setActiveTab] = useState<"all" | "confirm">("all");
  const [loadingCompany, setLoadingCompany] = useState<boolean>(true);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState<boolean>(true);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  
  // PDF Viewer States
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [evidenceText, setEvidenceText] = useState<string | null>(null);

  // 💡 WOW 수동 판정 로컬 오버라이드 State (필드명 -> 새로운 상태)
  const [localOverrides, setLocalOverrides] = useState<Record<string, "충족" | "미충족">>({});

  // 1. 기업 정보 조회
  useEffect(() => {
    async function fetchCompany() {
      try {
        const res = await fetch(`/api/companies`);
        if (res.ok) {
          const data = await res.json();
          const found = (data.items || []).find((c: Company) => c.id === companyId);
          if (found) setCompany(found);
        }
      } catch (err) {
        console.error("기업 정보 로드 실패:", err);
      } finally {
        setLoadingCompany(false);
      }
    }
    fetchCompany();
  }, [companyId]);

  // 2. 기업 매칭 공고 요약 목록 조회
  useEffect(() => {
    async function fetchAnnouncements() {
      try {
        const res = await fetch(`/api/matching/${companyId}`);
        if (res.ok) {
          const data = await res.json();
          const items = data.items || [];
          setAnnouncements(items);
          
          // 쿼리 스트링에 없거나 매칭 목록에 없으면 첫 번째 공고 자동 선택
          if (!selectedAnnId && items.length > 0) {
            setSelectedAnnId(items[0].announcement_id);
          }
        }
      } catch (err) {
        console.error("매칭 공고 목록 로드 실패:", err);
      } finally {
        setLoadingAnnouncements(false);
      }
    }
    fetchAnnouncements();
  }, [companyId, selectedAnnId]);

  // 3. 선택된 공고의 매칭 상세 및 공고 원문 메타데이터 로드
  useEffect(() => {
    if (!selectedAnnId) return;

    async function fetchDetailsAndMetadata() {
      setLoadingDetails(true);
      // 신규 공고 선택 시 수동 판정 오버라이드 초기화
      setLocalOverrides({});
      setHighlightPage(null);
      setEvidenceText(null);

      try {
        // A. 매칭 결과 세부 정보
        const matchRes = await fetch(`/api/matching/${companyId}?announcement_id=${selectedAnnId}`);
        let detailsList: MatchField[] = [];
        if (matchRes.ok) {
          const matchData: MatchResultDetailResponse = await matchRes.json();
          detailsList = (matchData.items || [])
            .filter((item) => item.status !== "해당없음")
            .map((item) => {
              // evidence 파싱
              let page: number | undefined;
              let text: string | undefined;
              if (item.evidence) {
                page = item.evidence.page || item.evidence.page_num;
                text = item.evidence.text || item.evidence.context;
              }

              return {
                field_name: item.field_name,
                status: item.status as "충족" | "미충족" | "확인필요",
                criterion: String(item.requirement_value || ""),
                current_value: String(item.company_value || ""),
                reason: item.processing_path || "조건 평가 완료",
                evidence_source: page ? { page, text } : null,
              };
            });
          setMatchDetails(detailsList);
        }

        // B. 공고 원본 메타데이터 (PDF 경로 등)
        const annRes = await fetch(`/api/announcements?id=${selectedAnnId}`);
        if (annRes.ok) {
          const annData: AnnouncementDetail = await annRes.json();
          setSelectedAnnDetail(annData);
        }
      } catch (err) {
        console.error("상세 매칭 결과 로드 실패:", err);
      } finally {
        setLoadingDetails(false);
      }
    }

    fetchDetailsAndMetadata();
  }, [companyId, selectedAnnId]);

  // 💡 WOW 수동 판정 제어 핸들러
  const handleOverrideStatus = (fieldName: string, newStatus: "충족" | "미충족") => {
    setLocalOverrides((prev) => ({
      ...prev,
      [fieldName]: newStatus,
    }));
  };

  // 원문 근거 클릭 시 PDF 뷰어 연동 점프
  const handleEvidenceClick = (page: number, text: string) => {
    setHighlightPage(page);
    setEvidenceText(text);
  };

  // 💡 오버라이드 상태가 반영된 갱신형 필드 정보 산출
  const finalMatchDetails = matchDetails.map((field) => {
    const override = localOverrides[field.field_name];
    if (override) {
      return {
        ...field,
        status: override,
        reason: `🚨 사용자 수동 확인 및 판정 완료 (기존: ${field.status})`,
      };
    }
    return field;
  });

  // 💡 WOW 오버라이드 상태 기반 매칭 점수 실시간 재계산 (기획서 스펙 준수)
  // matched: status === "충족" 개수
  // total: 전체 필드 수 (확인필요 제외)
  const matchedCount = finalMatchDetails.filter((f) => f.status === "충족").length;
  const totalWithoutConfirm = finalMatchDetails.filter((f) => f.status !== "확인필요").length;
  const liveScorePercentage = totalWithoutConfirm > 0 
    ? Math.round((matchedCount / totalWithoutConfirm) * 100) 
    : 0;

  const totalFields = finalMatchDetails.length;
  const fulfilledCount = matchedCount;
  const unfulfilledCount = finalMatchDetails.filter((f) => f.status === "미충족").length;
  const confirmRequiredCount = finalMatchDetails.filter((f) => f.status === "확인필요").length;

  const selectedAnnSummary = announcements.find((a) => a.announcement_id === selectedAnnId);
  const pdfUrl = selectedAnnDetail?.converted_pdf_path || selectedAnnDetail?.doc_url || "";

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

        {/* 상단 기업 분석 요약 헤더 */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm mb-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              📂 기업 맞춤형 매칭 상세 분석
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              선택한 정부지원사업의 세부 자격요건 항목들과 매칭 엔진 분석 결과를 원문 근거와 비교 검토합니다.
            </p>
          </div>

          {/* 실시간 매칭률 게이지 보드 (WOW 기능) */}
          <div className="bg-gray-50 border p-4 rounded-xl flex items-center gap-4 min-w-[240px]">
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-gray-400">실시간 반영 매칭률</span>
              <span className="text-2xl font-black text-blue-600 mt-1">{liveScorePercentage}%</span>
            </div>
            <div className="flex-1">
              <div className="w-full h-2 rounded-full bg-gray-200 overflow-hidden shadow-inner mb-1">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-500"
                  style={{ width: `${liveScorePercentage}%` }}
                />
              </div>
              <span className="text-[10px] text-gray-400 font-medium">
                {fulfilledCount} / {totalFields}개 요건 충족
              </span>
            </div>
          </div>
        </div>

        {/* 회사별 공고 매칭 결과 요약 카드 (기획서 UI 완벽 대응 및 점수 계산 공식 시각화) */}
        {company && selectedAnnDetail && (
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm mb-8 overflow-hidden">
            <div className="bg-gray-50/50 border-b border-gray-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h2 className="text-base font-bold text-gray-800 flex items-center gap-2">
                🤝 [{company.industry || "기업"}] vs {selectedAnnDetail.title}
              </h2>
              <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1 rounded-full font-bold">
                실시간 매칭률: {liveScorePercentage}%
              </span>
            </div>
            
            <div className="p-6 grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* 요약 카운트 뱃지들 */}
              <div className="md:col-span-3 flex flex-wrap gap-4 items-center">
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

              {/* 실시간 점수 계산 디스플레이 */}
              <div className="border-t md:border-t-0 md:border-l border-gray-150 pt-4 md:pt-0 md:pl-6 flex flex-col justify-center gap-1.5">
                <span className="text-xs font-semibold text-gray-400">매칭 점수 산출 방식</span>
                <div className="flex items-baseline gap-1 text-2xl font-black text-blue-600">
                  <span>{liveScorePercentage}</span>
                  <span className="text-xs font-bold text-gray-500"> / 100점</span>
                </div>
                <div className="text-[10px] text-gray-500 bg-gray-50 p-2.5 rounded border border-gray-150 font-mono leading-normal">
                  <span className="text-blue-600 font-bold">score</span> = (matched / total) * 100<br />
                  <span className="text-gray-400">= ({fulfilledCount} / ({totalFields} - {confirmRequiredCount})) * 100</span><br />
                  <span className="text-gray-400">= ({fulfilledCount} / {totalWithoutConfirm}) * 100</span><br />
                  <span className="text-green-600 font-bold">= {liveScorePercentage}점</span>
                </div>
              </div>
            </div>
          </div>
        )}

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
                  <div className="w-8 h-8 border-3 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
                  <p className="text-xs text-gray-400">공고 목록 불러오는 중...</p>
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
                          <span className={`font-black px-2 py-0.5 rounded-full ${
                            scorePct === 100 ? "bg-green-50 text-green-700 border border-green-200" :
                            scorePct >= 70 ? "bg-yellow-50 text-yellow-700 border border-yellow-200" :
                            "bg-red-50 text-red-700 border border-red-200"
                          }`}>
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
                    {finalMatchDetails.filter((f) => f.status === "확인필요").length > 0 && (
                      <span className={`text-[10px] font-black rounded-full px-1.5 py-0.5 ${
                        activeTab === "confirm" ? "bg-white text-amber-700 animate-bounce" : "bg-amber-100 text-amber-800"
                      }`}>
                        {finalMatchDetails.filter((f) => f.status === "확인필요").length}
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
                  <p className="text-gray-400 text-sm animate-pulse">자격요건 평가 상세 데이터를 집계하는 중...</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {activeTab === "all" ? (
                    finalMatchDetails.length === 0 ? (
                      <p className="text-gray-400 text-sm py-12 text-center">자격 요건 데이터가 존재하지 않습니다.</p>
                    ) : (
                      <div className="grid grid-cols-1 gap-5">
                        {finalMatchDetails.map((field) => (
                          <MatchResultCard
                            key={field.field_name}
                            field={field}
                            onEvidenceClick={handleEvidenceClick}
                            onOverrideStatus={handleOverrideStatus}
                          />
                        ))}
                      </div>
                    )
                  ) : (
                    <ConfirmRequiredTab
                      fields={finalMatchDetails}
                      onEvidenceClick={handleEvidenceClick}
                      onOverrideStatus={handleOverrideStatus}
                    />
                  )}
                </div>
              )}
            </div>

            {/* 하단 PDF 뷰어 연동 섹션 */}
            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2 pb-3 border-b">
                <div>
                  <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    📄 공고 원문 PDF 뷰어
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    자격요건 판정 카드의 'PDF 원문 근거 보기' 단추를 누르면 근거 텍스트가 명시된 원본 위치로 즉각 점프합니다.
                  </p>
                </div>
              </div>

              {pdfUrl ? (
                <div className="h-[600px]">
                  <PdfViewer
                    pdfUrl={pdfUrl}
                    highlightPage={highlightPage}
                    evidenceText={evidenceText}
                  />
                </div>
              ) : (
                <div className="py-20 border border-dashed rounded-xl flex flex-col items-center justify-center gap-3 bg-gray-50 text-gray-400">
                  <svg className="h-10 w-10 text-gray-300 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-sm font-semibold">이 공고에 연결된 PDF 원문이 존재하지 않습니다.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
