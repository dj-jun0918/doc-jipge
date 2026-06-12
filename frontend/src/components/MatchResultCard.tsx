"use client";

interface EvidenceLocation {
  location_type: "pdf_page" | "hwpx_table" | "hwpx_paragraph" | "raw_text";
  page?: number;
  bbox?: [number, number, number, number];
  table_index?: number;
  row?: number;
}

interface EvidenceSource {
  page?: number;
  text?: string;
  location?: EvidenceLocation | null;
}

export interface MatchField {
  field_name: string;
  status: "충족" | "미충족" | "확인필요";
  criterion: string;
  current_value: string;
  reason: string;
  evidence_source?: EvidenceSource | null;
  score?: number | null;
  distance?: number | null;
  constraint_type?: "hard" | "soft" | null;
}

interface MatchResultCardProps {
  field: MatchField;
  onEvidenceClick: (page: number, text: string, location?: EvidenceLocation | null) => void;
}

export default function MatchResultCard({ field, onEvidenceClick }: MatchResultCardProps) {
  const { field_name, status, criterion, current_value, reason, evidence_source, score, distance, constraint_type } = field;

  // 상태별 다이내믹 컬러/뱃지 스타일 맵
  const statusStyles = {
    충족: {
      badge: "bg-green-50 text-green-700 border-green-200",
      border: "border-green-100 hover:border-green-200",
      bg: "bg-white",
      dot: "bg-green-500",
    },
    미충족: {
      badge: "bg-red-50 text-red-700 border-red-200",
      border: "border-red-100 hover:border-red-200",
      bg: "bg-white",
      dot: "bg-red-500",
    },
    확인필요: {
      badge: "bg-amber-50 text-amber-700 border-amber-200 animate-pulse",
      border: "border-amber-100 hover:border-amber-200",
      bg: "bg-amber-50/5",
      dot: "bg-amber-500",
    },
  };

  const currentStyle = statusStyles[status] || statusStyles["확인필요"];

  const handleEvidenceClick = () => {
    if (evidence_source) {
      onEvidenceClick(
        evidence_source.page || 1,
        evidence_source.text || "",
        evidence_source.location || null
      );
    }
  };

  return (
    <div
      className={`rounded-xl border p-5 transition duration-300 hover:shadow-sm ${currentStyle.border} ${currentStyle.bg}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* 필드명 및 요건 타이틀 */}
        <div>
          <h4 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${currentStyle.dot}`} />
            {field_name}
          </h4>
          <p className="text-xs text-gray-400 mt-0.5">자격 평가 기준 항목</p>
        </div>

        {/* 상태 뱃지 및 점수/우대조건 */}
        <div className="flex items-center flex-wrap gap-2 flex-shrink-0">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${currentStyle.badge}`}>
            {status}
          </span>
          {score !== undefined && score !== null && (
            <span className="text-xs text-gray-500 ml-2">
              score: {score.toFixed(2)}
              {distance !== undefined && distance !== null && ` (-${distance.toFixed(2)})`}
            </span>
          )}
          {constraint_type === "soft" && (
            <span className="text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-medium">
              soft
            </span>
          )}
        </div>
      </div>

      {/* 요건 정보 스펙 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 bg-gray-50/50 p-4 rounded-lg border border-gray-100/70 text-xs">
        <div>
          <span className="block text-gray-400 font-semibold mb-1">📋 사업 요건 기준</span>
          <span className="text-gray-800 font-medium">{criterion || "정보 없음"}</span>
        </div>
        <div>
          <span className="block text-gray-400 font-semibold mb-1">🏢 기업 보유 정보</span>
          <span className="text-gray-800 font-medium text-blue-600">{current_value || "정보 없음"}</span>
        </div>
      </div>

      {/* 처리 경로 */}
      <div className="mt-4">
        <span className="block text-[11px] text-gray-400 font-semibold mb-1">⚙️ 처리 경로</span>
        <p className="text-sm text-gray-700 leading-relaxed font-medium">
          {(() => {
            switch (reason) {
              case "rule_base":
                return "규칙 기반";
              case "text_llm":
                return "텍스트 LLM";
              case "vision_llm":
                return "비전 LLM";
              default:
                return reason || "조건 평가 완료";
            }
          })()}
        </p>
      </div>

      {/* 하단 제어부 (원문 근거 및 수동 판정 액션) */}
      <div className="mt-5 pt-4 border-t border-gray-100 flex flex-wrap items-center justify-between gap-4">
        {/* 원문 근거 점프 버튼 */}
        {evidence_source ? (
          <button
            onClick={handleEvidenceClick}
            className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 bg-blue-50/50 hover:bg-blue-50 border border-blue-100 px-3 py-1.5 rounded-lg transition font-semibold cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            원문 근거 보기
          </button>
        ) : (
          <span className="text-[11px] text-gray-400">원문 근거 정보가 존재하지 않습니다.</span>
        )}
      </div>
    </div>
  );
}
