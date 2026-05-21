"use client";

interface EvidenceSource {
  page?: number;
  text?: string;
}

export interface MatchField {
  field_name: string;
  status: "충족" | "미충족" | "확인필요";
  criterion: string;
  current_value: string;
  reason: string;
  evidence_source?: EvidenceSource | null;
}

interface MatchResultCardProps {
  field: MatchField;
  onEvidenceClick: (page: number, text: string) => void;
  onOverrideStatus?: (fieldName: string, newStatus: "충족" | "미충족") => void;
}

export default function MatchResultCard({ field, onEvidenceClick, onOverrideStatus }: MatchResultCardProps) {
  const { field_name, status, criterion, current_value, reason, evidence_source } = field;

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
    if (evidence_source && evidence_source.page) {
      onEvidenceClick(evidence_source.page, evidence_source.text || "");
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

        {/* 상태 뱃지 */}
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${currentStyle.badge}`}>
          {status}
        </span>
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

      {/* 판정 세부 사유 */}
      <div className="mt-4">
        <span className="block text-[11px] text-gray-400 font-semibold mb-1">✍️ 판정 사유</span>
        <p className="text-sm text-gray-700 leading-relaxed font-medium">{reason}</p>
      </div>

      {/* 하단 제어부 (원문 근거 및 수동 판정 액션) */}
      <div className="mt-5 pt-4 border-t border-gray-100 flex flex-wrap items-center justify-between gap-4">
        {/* 원문 근거 점프 버튼 */}
        {evidence_source && evidence_source.page ? (
          <button
            onClick={handleEvidenceClick}
            className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 bg-blue-50/50 hover:bg-blue-50 border border-blue-100 px-3 py-1.5 rounded-lg transition font-semibold cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            PDF 원문 근거 보기 (p. {evidence_source.page})
          </button>
        ) : (
          <span className="text-[11px] text-gray-400">원문 근거 정보가 존재하지 않습니다.</span>
        )}

        {/* 수동 상태 오버라이드 제어 */}
        {status === "확인필요" && onOverrideStatus && (
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-[11px] text-gray-400 font-semibold mr-1">직접 확인:</span>
            <button
              onClick={() => onOverrideStatus(field_name, "충족")}
              className="px-2.5 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded text-xs font-semibold shadow-sm hover:shadow active:scale-95 transition cursor-pointer"
            >
              충족함
            </button>
            <button
              onClick={() => onOverrideStatus(field_name, "미충족")}
              className="px-2.5 py-1.5 bg-red-500 hover:bg-red-600 text-white rounded text-xs font-semibold shadow-sm hover:shadow active:scale-95 transition cursor-pointer"
            >
              미충족
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
