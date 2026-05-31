"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface EvidenceLocation {
  location_type: "pdf_page" | "hwpx_table" | "hwpx_paragraph" | "raw_text";
  page?: number;
  bbox?: [number, number, number, number];
  table_index?: number;
  row?: number;
}

interface Props {
  tables?: Array<{ name: string; markdown: string }> | null;
  location: EvidenceLocation | null;
}

export default function HwpxTableViewer({ tables, location }: Props) {
  if (!tables || tables.length === 0) {
    return (
      <div className="py-12 border border-dashed rounded-xl flex flex-col items-center justify-center bg-gray-50 text-gray-400">
        <p className="text-sm font-semibold">구조화된 테이블 데이터가 존재하지 않습니다.</p>
      </div>
    );
  }

  const tableIdx = location?.table_index !== undefined ? location.table_index : 0;
  const target = tables[tableIdx] || tables[0];

  if (!target) {
    return (
      <div className="py-12 border border-dashed rounded-xl flex flex-col items-center justify-center bg-gray-50 text-gray-400">
        <p className="text-sm font-semibold">표를 찾을 수 없습니다</p>
      </div>
    );
  }

  // location.row는 보통 1-indexed (첫 번째 데이터 행이 1)
  const targetRowIndex = location?.row !== undefined ? location.row - 1 : -1;

  return (
    <div className="bg-white rounded-2xl border border-gray-150 shadow-sm overflow-hidden flex flex-col h-full">
      {/* 테이블 정보 헤더 */}
      <div className="bg-gradient-to-r from-slate-50 to-white px-5 py-4 border-b flex items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-bold text-gray-800 flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            구조화 HWPX 테이블 뷰어 {tables.length > 1 && `(${tableIdx + 1}/${tables.length})`}
          </h4>
          <p className="text-xs text-gray-400 mt-1">
            테이블 이름: <span className="font-semibold text-gray-700">{target.name || `Table ${tableIdx + 1}`}</span>
          </p>
        </div>

        {location?.row !== undefined && (
          <span className="text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full animate-pulse shadow-sm">
            🎯 근거 행: {location.row}행 매칭 완료
          </span>
        )}
      </div>

      {/* 테이블 렌더링 영역 */}
      <div className="flex-1 overflow-auto p-5">
        <div className="prose prose-sm max-w-none text-xs">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              table: ({ children }) => (
                <div className="overflow-x-auto rounded-xl border border-gray-100 shadow-inner">
                  <table className="w-full text-left border-collapse text-xs">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="bg-slate-50 border-b border-gray-200">
                  {children}
                </thead>
              ),
              th: ({ children }) => (
                <th className="px-4 py-3.5 font-bold text-gray-700 uppercase tracking-wider">
                  {children}
                </th>
              ),
              tbody: ({ children }) => {
                const rows = React.Children.toArray(children);
                return (
                  <tbody className="divide-y divide-gray-100">
                    {rows.map((row, index) => {
                      const isHighlighted = index === targetRowIndex;
                      return React.cloneElement(row as any, {
                        className: `transition-colors duration-300 relative ${
                          isHighlighted
                            ? "bg-yellow-50/75 font-medium text-amber-950 shadow-[inset_3px_0_0_#eab308] border-y border-yellow-200/50"
                            : "hover:bg-gray-50/50 text-gray-600"
                        }`
                      });
                    })}
                  </tbody>
                );
              },
              td: ({ children }) => (
                <td className="px-4 py-3.5">
                  {children}
                </td>
              )
            }}
          >
            {target.markdown}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
