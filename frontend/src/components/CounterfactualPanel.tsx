"use client";

import { useEffect, useState } from "react";

interface CounterfactualItem {
  field_name: string;
  current_value: string | null;
  requirement: string | null;
  suggested_value: string | null;
  explanation: string | null;
  changeable: boolean;
}

interface CounterfactualResponse {
  company_id: string;
  announcement_id: string;
  unmet: CounterfactualItem[];
  achievable: boolean;
  note: string | null;
}

interface Props {
  company_id: string;
  ann_id: string;
}

function ActionIcon({ fieldName }: { fieldName: string }) {
  switch (fieldName) {
    case "인증":
      return <span className="text-xl">📜</span>;
    case "지역":
      return <span className="text-xl">📍</span>;
    case "종업원 수":
    case "임직원 수":
      return <span className="text-xl">👥</span>;
    case "매출":
    case "매출액":
      return <span className="text-xl">💰</span>;
    case "업력":
    case "나이":
      return <span className="text-xl">⏳</span>;
    default:
      return <span className="text-xl">⚡</span>;
  }
}

export default function CounterfactualPanel({ company_id, ann_id }: Props) {
  const [data, setData] = useState<CounterfactualResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!company_id || !ann_id) return;
    setLoading(true);
    setError(null);

    fetch(`/api/matching/${company_id}/counterfactual`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ announcement_id: ann_id }),
    })
      .then((r) => {
        if (!r.ok) {
          throw new Error(`HTTP error! status: ${r.status}`);
        }
        return r.json();
      })
      .then((res) => {
        setData(res);
      })
      .catch((err) => {
        console.error("반사실 분석 로드 실패:", err);
        setError("반사실 분석 데이터를 가져오지 못했습니다.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [company_id, ann_id]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-12 bg-gray-100 rounded-xl" />
        <div className="h-32 bg-gray-100 rounded-xl" />
        <div className="h-32 bg-gray-100 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-center">
        <p className="text-sm font-semibold text-red-700">{error}</p>
      </div>
    );
  }

  if (!data || !data.unmet || data.unmet.length === 0) {
    return (
      <div className="rounded-2xl border border-green-200 bg-green-50/30 p-8 text-center flex flex-col items-center justify-center gap-3">
        <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center text-2xl">🎉</div>
        <h3 className="text-base font-bold text-green-900">모든 요건을 충족합니다</h3>
        <p className="text-xs text-green-600">
          현재 기업 프로필 상태로 이 공고의 모든 자격 조건을 충족하고 있습니다. 별도의 추가 준비 조치가 필요하지 않습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 상태 배너 */}
      <div
        className={`rounded-2xl border p-5 flex items-start gap-4 transition-all ${
          data.achievable
            ? "border-emerald-200 bg-emerald-50/40 text-emerald-900"
            : "border-amber-200 bg-amber-50/40 text-amber-900"
        }`}
      >
        <div className="text-2xl mt-0.5">
          {data.achievable ? "✨" : "⚠️"}
        </div>
        <div className="flex-1 space-y-1">
          <h4 className="font-bold text-sm">
            {data.achievable
              ? "프로필 보완 시 모든 자격요건 충족이 가능합니다!"
              : "지원 조건의 일부 조율 또는 보완이 필요한 상태입니다."}
          </h4>
          <p className="text-xs leading-relaxed opacity-90">
            {data.achievable
              ? "제시된 변경 가능 조건을 충족할 경우 정상적으로 사업 지원 자격을 획득하실 수 있습니다."
              : data.note || "시간 경과 대기, 소재지 원천 이전 등 단기 조치로 해결하기 어려운 조건이 포함되어 있습니다."}
          </p>
        </div>
      </div>

      {/* 미충족 요건 대안 가이드 목록 */}
      <div className="grid grid-cols-1 gap-4">
        {data.unmet.map((item) => (
          <div
            key={item.field_name}
            className={`rounded-2xl border p-5 bg-white shadow-sm hover:shadow-md transition-all duration-200 border-gray-150 flex flex-col sm:flex-row gap-4 justify-between items-start`}
          >
            <div className="flex items-start gap-3.5 flex-1">
              <div className="w-10 h-10 bg-slate-50 border rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm">
                <ActionIcon fieldName={item.field_name} />
              </div>
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-2.5">
                  <h4 className="font-bold text-slate-800 text-sm">{item.field_name}</h4>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                      item.changeable
                        ? "bg-blue-50 text-blue-700 border-blue-200"
                        : "bg-rose-50 text-rose-700 border-rose-200"
                    }`}
                  >
                    {item.changeable ? "개선 가능" : "조정 불가"}
                  </span>
                </div>
                
                {/* 대조 상태 및 요건 정보 */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-slate-50/50 border p-3 rounded-xl">
                  <div>
                    <span className="text-gray-400 block font-medium">현재 기업 상태</span>
                    <span className="font-bold text-slate-700 mt-0.5 block">{item.current_value || "미보유/해당없음"}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block font-medium">공고 자격 요건</span>
                    <span className="font-bold text-slate-700 mt-0.5 block">{item.requirement || "-"}</span>
                  </div>
                </div>

                {/* 해결 실행 액션 가이드 */}
                {item.explanation && (
                  <div className="text-xs text-slate-600 mt-2 bg-blue-50/10 border border-blue-50/50 p-3 rounded-xl flex items-start gap-2">
                    <span className="text-blue-500 font-bold">💡 조치 방안:</span>
                    <p className="leading-relaxed flex-1">{item.explanation}</p>
                  </div>
                )}
              </div>
            </div>

            {/* 권장 도달 값 */}
            {item.suggested_value && (
              <div className="flex flex-col sm:items-end justify-center bg-indigo-50/30 border border-indigo-100 p-4 rounded-2xl w-full sm:w-auto min-w-[140px] text-center sm:text-right flex-shrink-0">
                <span className="text-[10px] font-semibold text-indigo-400">목표 권장값</span>
                <span className="text-sm font-black text-indigo-700 mt-1 block">
                  {item.suggested_value}
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
