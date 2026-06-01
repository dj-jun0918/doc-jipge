"use client";

import { useEffect, useState, use } from "react";
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
  // Next.js 15+ Client Component에서는 로컬 dev 런타임에 params가 일반 동기 객체일 때가 있습니다.
  // 이 경우 use() 훅을 직접 호출하면 런타임 크래시가 나므로 thenable(Promise) 여부를 안전하게 확인하고 분기합니다.
  const params = isPromise<{ id: string }>(props.params)
    ? use(props.params)
    : props.params;

  const searchParams = isPromise<{ announcement_id?: string }>(props.searchParams)
    ? use(props.searchParams)
    : props.searchParams;

  const companyId = params?.id || "";
  const initialAnnId = searchParams?.announcement_id || "";

  // Core States
  const [company, setCompany] = useState<Company | null>(null);
  const [announcements, setAnnouncements] = useState<CompanyMatchSummary[]>([]);
  const [selectedAnnId, setSelectedAnnId] = useState<string>(initialAnnId);
  const [selectedAnnDetail, setSelectedAnnDetail] = useState<AnnouncementDetail | null>(null);
  const [matchDetails, setMatchDetails] = useState<MatchField[]>([]);
  const [stats, setStats] = useState<MatchResultDetailResponse["stats"] | null>(null);
  
  // UI States
  const [activeTab, setActiveTab] = useState<"all" | "confirm">("all");
  const [loadingCompany, setLoadingCompany] = useState<boolean>(true);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState<boolean>(true);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);

  // Error States
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [companyNotFound, setCompanyNotFound] = useState<boolean>(false);
  const [annError, setAnnError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailRetryNonce, setDetailRetryNonce] = useState<number>(0);
  
  // PDF Viewer & Evidence Location States
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [evidenceText, setEvidenceText] = useState<string | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<any>(null);

  // 1. 기업 정보 조회
  useEffect(() => {
    async function fetchCompany() {
      try {
        const res = await fetch(`/api/companies`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        let found = (data.items || []).find((c: Company) => c.id === companyId);
        
        /* 🧪 테스트용 Mock Company Fallback (필요시 주석 제거하여 활성화)
        if (!found) {
          found = {
            id: companyId,
            name: "테스트컴퍼니A (테스트용)",
            industry: "소프트웨어 개발업",
            region: "대구광역시 수성구",
            revenue: 350000000,
            employee_count: 8
          };
        } */

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

  // 2. 기업 매칭 공고 요약 목록 조회
  useEffect(() => {
    async function fetchAnnouncements() {
      try {
        const res = await fetch(`/api/matching/${companyId}`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        let items = data.items || [];

        /* 🧪 테스트용 Mock Announcements 주입 (필요시 주석 제거하여 활성화)
        if (items.length === 0) {
          items = [
            {
              announcement_id: "b8b63599-1f5b-4b74-9bcc-48b352ffcae6",
              title: "2026 강원 청년창업 지원사업 (테스트용)",
              match_score: 0.85,
              fulfilled_count: 3,
              total_fields: 4
            },
            {
              announcement_id: "22222222-2222-2222-2222-222222222222",
              title: "서울청년AI 창업도약 패키지 (테스트용)",
              match_score: 0.60,
              fulfilled_count: 2,
              total_fields: 4
            }
          ];
        } */

        setAnnouncements(items);

        // 쿼리 스트링에 없거나 매칭 목록에 없으면 첫 번째 공고 자동 선택
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

  // 3. 선택된 공고의 매칭 상세 및 공고 원문 메타데이터 로드
  useEffect(() => {
    if (!selectedAnnId) return;

    async function fetchDetailsAndMetadata() {
      setLoadingDetails(true);
      setHighlightPage(null);
      setEvidenceText(null);
      setSelectedLocation(null);
      setDetailError(null);

      try {
        // A. 매칭 결과 세부 정보
        const matchRes = await fetch(`/api/matching/${companyId}?announcement_id=${selectedAnnId}`);
        if (!matchRes.ok) {
          throw new Error(`매칭 결과 HTTP ${matchRes.status}`);
        }
        const matchData: MatchResultDetailResponse = await matchRes.json();
        setStats(matchData.stats);

        let detailsList: MatchField[] = (matchData.items || [])
          .filter((item) => item.status !== "해당없음")
          .map((item) => {
            // evidence 파싱
            let page: number | undefined;
            let text: string | undefined;
            let location: any = null;

            if (item.evidence) {
              try {
                const parsed = JSON.parse(item.evidence);
                page = parsed.page || parsed.page_num || parsed.location?.page;
                text = parsed.text || parsed.context;
                location = parsed.location || null;

                // 하위 호환성: 기존 파싱 구조에 page가 존재하면 pdf_page location으로 매핑
                if (!location && page) {
                  location = {
                    location_type: "pdf_page",
                    page: page,
                  };
                }
              } catch {
                // JSON이 아닌 일반 문자열인 경우 raw_text로 처리
                text = item.evidence;
                location = {
                  location_type: "raw_text",
                };
              }
            }

            /* 🧪 B-1 시각화 검증을 위한 Mock 데이터 주입 (필요시 주석 제거하여 활성화)
            if (item.field_name === "업력") {
              text = "창업 7년 이내 창업기업만 신청 가능하다고 명시됨 (2019-04-29 ~ 2026-04-28 설립)";
              page = 2;
              location = {
                location_type: "pdf_page",
                page: 2,
                bbox: [100, 150, 480, 210],
              };
            } else if (item.field_name === "매출") {
              text = "직전 사업연도(2025년) 매출액이 2억원 이상인 기업";
              page = 3;
              location = {
                location_type: "pdf_page",
                page: 3,
                bbox: [120, 240, 500, 290],
              };
            } else if (item.field_name === "지역") {
              text = "공고일 현재 대구광역시 내에 본사 또는 공장을 등록한 기업";
              location = {
                location_type: "hwpx_table",
                table_index: 0,
                row: 3,
              };
            } else if (item.field_name === "나이") {
              text = "대표자가 만 39세 이하의 청년 창업자여야 함 (1986년 5월 31일 이후 출생자)";
              location = {
                location_type: "raw_text",
              };
            }
            */

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

        /* 🧪 뷰어 검증용 목업 카드 무조건 상단 주입 (필요시 주석 제거하여 활성화)
        const mockFields: MatchField[] = [
          {
            field_name: "업력",
            status: "확인필요",
            criterion: "창업 후 7년 이내",
            current_value: "창업 3년차 (2023년 설립)",
            reason: "창업 7년 이내 요건을 충족하나, 제출 서류 대조 필요",
            evidence_source: {
              page: 2,
              text: "창업 7년 이내 창업기업만 신청 가능하다고 명시됨 (2019-04-29 ~ 2026-04-28 설립)",
              location: {
                location_type: "pdf_page",
                page: 2,
                bbox: [100, 150, 480, 210],
              }
            },
            score: 0.85,
            distance: 0.15,
            constraint_type: "soft"
          },
          {
            field_name: "매출",
            status: "충족",
            criterion: "직전년도(2025) 매출 2억원 이상",
            current_value: "직전년도 매출 3.5억원",
            reason: "2025년도 매출액이 기준치인 2억원을 초과하여 충족함",
            evidence_source: {
              page: 3,
              text: "직전 사업연도(2025년) 매출액이 2억원 이상인 기업",
              location: {
                location_type: "pdf_page",
                page: 3,
                bbox: [120, 240, 500, 290],
              }
            },
            score: 1.00,
            distance: 0.00,
            constraint_type: "hard"
          },
          {
            field_name: "지역",
            status: "충족",
            criterion: "대구광역시 내 본사 또는 공장 소재",
            current_value: "본사: 대구광역시 수성구",
            reason: "기업 본사 등록 소재지가 대구광역시로 확인됨",
            evidence_source: {
              page: 1,
              text: "공고일 현재 대구광역시 내에 본사 또는 공장을 등록한 기업",
              location: {
                location_type: "hwpx_table",
                table_index: 0,
                row: 3,
              }
            },
            score: 0.95,
            distance: 0.05,
            constraint_type: "soft"
          },
          {
            field_name: "나이",
            status: "확인필요",
            criterion: "대표자 만 39세 이하",
            current_value: "대표자 나이: 만 34세 (1992년생)",
            reason: "대표자가 만 39세 이하의 청년 요건에 부합하는지 텍스트 대조 완료",
            evidence_source: {
              page: 1,
              text: "대표자가 만 39세 이하의 청년 창업자여야 함 (1986년 5월 31일 이후 출생자)",
              location: {
                location_type: "raw_text",
              }
            },
            score: 0.50,
            distance: 0.50,
            constraint_type: "soft"
          }
        ];

        detailsList = [...mockFields, ...detailsList];
        */

        setMatchDetails(detailsList);

        // B. 공고 원본 메타데이터 (첨부파일 구조 포함)
        const annRes = await fetch(`/api/announcements?id=${selectedAnnId}`);
        if (!annRes.ok) {
          throw new Error(`공고 메타데이터 HTTP ${annRes.status}`);
        }
        const annData: AnnouncementDetail = await annRes.json();

        /* 🧪 HWPX 테이블 테스트용 Mock 데이터 주입 (필요시 주석 제거하여 활성화)
        if (!annData.structured_tables || annData.structured_tables.length === 0) {
          annData.structured_tables = [
            {
              name: "신청자격 요약 및 제외대상 목록",
              markdown: `| 구분 | 조건 | 대상자 |
|---|---|---|
| 업력 | 창업 7년 이내 | 창업기업 대표자 |
| 매출 | 직전년도 2억원 이상 | 일반 법인 및 개인사업자 |
| 지역 | 대구광역시 소재 | 본사 또는 공장 등록 기업 |
| 연령 | 만 39세 이하 | 청년 창업자 (1986년 이후 출생) |`,
            }
          ];
        }
        */

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
  }, [companyId, selectedAnnId, detailRetryNonce]);

  // 원문 근거 클릭 시 PDF 뷰어 연동 점프
  const handleEvidenceClick = (page: number, text: string, location?: any) => {
    setHighlightPage(page);
    setEvidenceText(text);
    setSelectedLocation(location || null);
  };

  // 백엔드 제공 stats 정보 직접 매핑
  const fulfilledCount = stats?.충족 ?? 0;
  const unfulfilledCount = stats?.미충족 ?? 0;
  const confirmRequiredCount = stats?.확인필요 ?? 0;
  const totalFields = matchDetails.length;

  const selectedAnnSummary = announcements.find((a) => a.announcement_id === selectedAnnId);
  const matchScorePercentage = selectedAnnSummary ? Math.round(selectedAnnSummary.match_score * 100) : 0;

  // 메인 첨부파일 선정 분기 규칙 적용
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
                          {/* 💡 임의 점수 분류 제거 및 단일 UI 테마 뱃지 적용 */}
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
                    {matchDetails.filter((f) => f.status === "확인필요").length > 0 && (
                      <span className={`text-[10px] font-black rounded-full px-1.5 py-0.5 ${
                        activeTab === "confirm" ? "bg-white text-amber-700" : "bg-amber-100 text-amber-800"
                      }`}>
                        {matchDetails.filter((f) => f.status === "확인필요").length}
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
                    matchDetails.length === 0 ? (
                      <p className="text-gray-400 text-sm py-12 text-center">자격 요건 데이터가 존재하지 않습니다.</p>
                    ) : (
                      <div className="grid grid-cols-1 gap-5">
                        {matchDetails.map((field) => (
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
                      fields={matchDetails}
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
                        pdfUrl={/* mainAttachment.id === "test-attachment-id" ? "/sample.pdf" : */ `/api/attachments/${mainAttachment.id}/file`}
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

