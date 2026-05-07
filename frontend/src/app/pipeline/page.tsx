"use client";

import { useEffect, useState } from "react";
import PipelineStatus, { PipelineJob } from "@/components/PipelineStatus";

const MOCK_INITIAL_JOBS: PipelineJob[] = [
  {
    id: "job-1-col",
    announcement_id: null,
    job_type: "collect",
    status: "processing",
    progress: 45,
    error_message: null,
    created_at: new Date(Date.now() - 10000).toISOString(),
    updated_at: new Date(Date.now() - 2000).toISOString(),
  },
  {
    id: "job-2-match",
    announcement_id: "ann_011",
    job_type: "match",
    status: "pending",
    progress: 0,
    error_message: null,
    created_at: new Date(Date.now() - 5000).toISOString(),
    updated_at: new Date(Date.now() - 5000).toISOString(),
  },
  {
    id: "job-3-conv",
    announcement_id: "ann_012",
    job_type: "convert",
    status: "done",
    progress: 100,
    error_message: null,
    created_at: new Date(Date.now() - 60000).toISOString(),
    updated_at: new Date(Date.now() - 10000).toISOString(),
  },
  {
    id: "job-4-ext",
    announcement_id: "ann_013",
    job_type: "extract",
    status: "failed",
    progress: 30,
    error_message: "LLM API 호출 중 시간 초과가 발생했습니다.",
    created_at: new Date(Date.now() - 30000).toISOString(),
    updated_at: new Date(Date.now() - 5000).toISOString(),
  },
];

export default function PipelinePage() {
  const [jobs, setJobs] = useState<PipelineJob[]>(MOCK_INITIAL_JOBS);

  // Mock interval to simulate progress
  useEffect(() => {
    const interval = setInterval(() => {
      setJobs((prevJobs) =>
        prevJobs.map((job) => {
          if (job.status === "done" || job.status === "failed") return job;

          let newProgress = job.progress;
          let newStatus: PipelineJob["status"] = job.status;

          if (job.status === "pending") {
            // 20% chance to start processing
            if (Math.random() > 0.8) {
              newStatus = "processing";
              newProgress = 5;
            }
          } else if (job.status === "processing") {
            // Increase progress randomly between 10% and 30%
            newProgress += Math.floor(Math.random() * 20) + 10;
            if (newProgress >= 100) {
              newProgress = 100;
              newStatus = "done";
            }
          }

          return {
            ...job,
            progress: newProgress,
            status: newStatus,
            updated_at: new Date().toISOString(),
          };
        })
      );
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const stats = {
    pending: jobs.filter((j) => j.status === "pending").length,
    processing: jobs.filter((j) => j.status === "processing").length,
    done: jobs.filter((j) => j.status === "done").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">파이프라인 진행 상태</h1>
        <p className="text-gray-600">
          데이터 수집, 변환, 추출 등 백엔드 작업들의 진행 상황을 모니터링합니다.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg border p-4 shadow-sm text-center">
          <p className="text-sm text-gray-500 mb-1">대기 중</p>
          <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
        </div>
        <div className="bg-white rounded-lg border p-4 shadow-sm text-center">
          <p className="text-sm text-gray-500 mb-1">진행 중</p>
          <p className="text-2xl font-bold text-blue-600">{stats.processing}</p>
        </div>
        <div className="bg-white rounded-lg border p-4 shadow-sm text-center">
          <p className="text-sm text-gray-500 mb-1">완료</p>
          <p className="text-2xl font-bold text-green-600">{stats.done}</p>
        </div>
        <div className="bg-white rounded-lg border p-4 shadow-sm text-center">
          <p className="text-sm text-gray-500 mb-1">실패</p>
          <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
        </div>
      </div>

      <div className="bg-gray-50 rounded-xl p-6 border">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          현재 작업 목록
          <span className="text-xs font-normal text-gray-500 bg-gray-200 px-2 py-1 rounded-full">
            자동 갱신 중 (Mock)
          </span>
        </h2>

        <div className="flex flex-col gap-4">
          {jobs.length === 0 ? (
            <p className="text-center text-gray-500 py-8">진행 중인 작업이 없습니다.</p>
          ) : (
            jobs.map((job) => <PipelineStatus key={job.id} job={job} />)
          )}
        </div>
      </div>
    </div>
  );
}
