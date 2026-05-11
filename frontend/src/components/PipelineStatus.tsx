"use client";

import React, { useEffect, useState } from "react";

/** 백엔드 pipeline_jobs 테이블 스키마와 일치 */
export interface PipelineJob {
  id: string;
  job_type: "collect" | "download" | "convert" | "extract" | "match";
  announcement_id: string | null;
  status: "pending" | "processing" | "done" | "failed";
  total_count: number;
  success_count: number;
  fail_count: number;
  skip_count: number;
  error_summary: Record<string, unknown> | null;
  started_at: string;
  finished_at: string | null;
}

interface PipelineStatusProps {
  job: PipelineJob;
}

const statusColors = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  processing: "bg-blue-100 text-blue-800 border-blue-200",
  done: "bg-green-100 text-green-800 border-green-200",
  failed: "bg-red-100 text-red-800 border-red-200",
};

const jobTypeLabels: Record<PipelineJob["job_type"], string> = {
  collect: "공고 수집",
  download: "PDF 다운로드",
  convert: "PDF 변환",
  extract: "요건 추출",
  match: "공고 매칭",
};

const statusLabels: Record<PipelineJob["status"], string> = {
  pending: "대기 중",
  processing: "진행 중",
  done: "완료",
  failed: "실패",
};

/** total_count 기반 진행률 계산 (총 0이면 status로 대체) */
function calcProgress(job: PipelineJob): number {
  if (job.status === "done") return 100;
  if (job.status === "pending") return 0;
  if (job.total_count > 0) {
    const done = job.success_count + job.fail_count + job.skip_count;
    return Math.min(Math.round((done / job.total_count) * 100), 99);
  }
  // total_count가 아직 집계되지 않은 processing 상태
  return job.status === "processing" ? 5 : 0;
}

export default function PipelineStatus({ job }: PipelineStatusProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const isFailed = job.status === "failed";
  const isDone = job.status === "done";
  const progress = calcProgress(job);

  // 오류 요약 문자열 추출
  const errorMessage = isFailed && job.error_summary
    ? (job.error_summary.message as string) ?? JSON.stringify(job.error_summary)
    : null;

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm flex flex-col gap-3">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-gray-900">
            {jobTypeLabels[job.job_type] ?? job.job_type}
          </span>
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusColors[job.status]}`}
          >
            {statusLabels[job.status]}
          </span>
        </div>
        <span className="text-sm text-gray-500">
          ID: <span className="font-mono text-xs">{job.id.slice(0, 8)}</span>
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">
            진행률
            {job.total_count > 0 && (
              <span className="ml-1 text-gray-400 text-xs">
                ({job.success_count}/{job.total_count})
              </span>
            )}
          </span>
          <span className="font-medium text-gray-900">{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ease-in-out ${
              isFailed ? "bg-red-500" : isDone ? "bg-green-500" : "bg-blue-600"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {job.fail_count > 0 && (
        <div className="flex gap-4 text-xs text-gray-500">
          <span>✅ 성공 {job.success_count}</span>
          <span>❌ 실패 {job.fail_count}</span>
          {job.skip_count > 0 && <span>⏭ 스킵 {job.skip_count}</span>}
        </div>
      )}

      {isFailed && errorMessage && (
        <div className="mt-1 p-3 bg-red-50 border border-red-100 rounded-md">
          <p className="text-sm text-red-700 font-medium">오류 발생</p>
          <p className="text-xs text-red-600 mt-1 break-words">{errorMessage}</p>
        </div>
      )}

      <div className="text-xs text-gray-400 text-right mt-1">
        시작:{" "}
        {mounted ? new Date(job.started_at).toLocaleString("ko-KR") : "..."}
        {job.finished_at && (
          <>
            {" · "}완료:{" "}
            {mounted ? new Date(job.finished_at).toLocaleString("ko-KR") : "..."}
          </>
        )}
      </div>
    </div>
  );
}
