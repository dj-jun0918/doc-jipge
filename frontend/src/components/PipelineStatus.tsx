"use client";

import React, { useEffect, useState } from "react";

export interface PipelineJob {
  id: string;
  announcement_id: string | null;
  job_type: "collect" | "match" | "convert" | "extract";
  status: "pending" | "processing" | "done" | "failed";
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
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

const jobTypeLabels = {
  collect: "공고 수집",
  match: "공고 매칭",
  convert: "PDF 변환",
  extract: "요건 추출",
};

const statusLabels = {
  pending: "대기 중",
  processing: "진행 중",
  done: "완료",
  failed: "실패",
};

export default function PipelineStatus({ job }: PipelineStatusProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isFailed = job.status === "failed";
  const isDone = job.status === "done";

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm flex flex-col gap-3">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-gray-900">
            {jobTypeLabels[job.job_type]}
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
          <span className="text-gray-600">진행률</span>
          <span className="font-medium text-gray-900">{job.progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ease-in-out ${isFailed ? "bg-red-500" : isDone ? "bg-green-500" : "bg-blue-600"
              }`}
            style={{ width: `${job.progress}%` }}
          ></div>
        </div>
      </div>

      {isFailed && job.error_message && (
        <div className="mt-2 p-3 bg-red-50 border border-red-100 rounded-md">
          <p className="text-sm text-red-700 font-medium">오류 발생</p>
          <p className="text-xs text-red-600 mt-1 break-words">
            {job.error_message}
          </p>
        </div>
      )}

      <div className="text-xs text-gray-400 text-right mt-1">
        업데이트: {mounted ? new Date(job.updated_at).toLocaleTimeString("ko-KR") : "..."}
      </div>
    </div>
  );
}
