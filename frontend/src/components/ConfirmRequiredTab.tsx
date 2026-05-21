"use client";

import MatchResultCard, { MatchField } from "./MatchResultCard";

interface ConfirmRequiredTabProps {
  fields: MatchField[];
  onEvidenceClick: (page: number, text: string) => void;
  onOverrideStatus: (fieldName: string, newStatus: "충족" | "미충족") => void;
}

export default function ConfirmRequiredTab({ fields, onEvidenceClick, onOverrideStatus }: ConfirmRequiredTabProps) {
  // 확인필요 상태인 항목만 필터링
  const confirmRequiredFields = fields.filter((f) => f.status === "확인필요");

  return (
    <div className="space-y-6">
      {/* 탭 헤더 정보 */}
      <div className="flex items-center justify-between border-b pb-4 mb-4 gap-4">
        <div>
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            ⚠️ 수동 검토 필요 항목
            {confirmRequiredFields.length > 0 && (
              <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full font-bold animate-bounce">
                {confirmRequiredFields.length}
              </span>
            )}
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            엔진이 자동으로 판단하지 못한 모호한 기준이나 기업 추가 정보 검토가 요구되는 핵심 요건들입니다.
          </p>
        </div>
      </div>

      {confirmRequiredFields.length === 0 ? (
        /* 검토 완료 상태 축하 UI */
        <div className="bg-green-50 border border-green-200 rounded-2xl p-8 text-center max-w-xl mx-auto shadow-sm my-6">
          <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-300">
            <svg className="h-8 w-8 text-green-600 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h4 className="text-lg font-bold text-green-900">모든 요건 검토 완료!</h4>
          <p className="text-sm text-green-700 mt-2 leading-relaxed font-medium">
            현재 확인이 필요한 모호한 요건 항목이 존재하지 않습니다.<br />
            수동으로 판정했거나 자동으로 매칭된 결과를 통해 최종 보고서를 확정할 수 있습니다.
          </p>
        </div>
      ) : (
        /* 확인 필요 카드 리스트 */
        <div className="grid grid-cols-1 gap-5">
          {confirmRequiredFields.map((field) => (
            <MatchResultCard
              key={field.field_name}
              field={field}
              onEvidenceClick={onEvidenceClick}
              onOverrideStatus={onOverrideStatus}
            />
          ))}
        </div>
      )}
    </div>
  );
}
