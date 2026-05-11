"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PipelineStatus, { PipelineJob } from "@/components/PipelineStatus";

const POLL_INTERVAL_MS = 5000; // 5초마다 갱신

type FetchState = "idle" | "loading" | "error";

export default function PipelinePage() {
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [fetchState, setFetchState] = useState<FetchState>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      setFetchState("loading");
      const res = await fetch("/api/pipeline/jobs?limit=50&offset=0", {
        cache: "no-store",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.message ?? `HTTP ${res.status}`);
      }

      const data: { items: PipelineJob[]; total: number } = await res.json();
      setJobs(data.items ?? []);
      setErrorMsg(null);
      setLastUpdated(new Date());
      setFetchState("idle");
    } catch (err) {
      console.error("파이프라인 데이터 조회 실패:", err);
      setErrorMsg(err instanceof Error ? err.message : "알 수 없는 오류");
      setFetchState("error");
    }
  }, []);

  // 초기 로드 + 폴링
  useEffect(() => {
    fetchJobs();
    pollingRef.current = setInterval(fetchJobs, POLL_INTERVAL_MS);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [fetchJobs]);

  const stats = {
    pending: jobs.filter((j) => j.status === "pending").length,
    processing: jobs.filter((j) => j.status === "processing").length,
    done: jobs.filter((j) => j.status === "done").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  };

  const isActiveJob = (j: PipelineJob) =>
    j.status === "pending" || j.status === "processing";
  const activeJobs = jobs.filter(isActiveJob);
  const finishedJobs = jobs.filter((j) => !isActiveJob(j));

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      {/* 헤더 */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          파이프라인 진행 상태
        </h1>
        <div className="flex items-center gap-3">
          <p className="text-gray-600">
            데이터 수집, 변환, 추출 등 백엔드 작업들의 진행 상황을 모니터링합니다.
          </p>
          {lastUpdated && (
            <span className="text-xs text-gray-400 ml-auto whitespace-nowrap">
              마지막 갱신: {lastUpdated.toLocaleTimeString("ko-KR")}
            </span>
          )}
        </div>
      </div>

      {/* 에러 배너 */}
      {fetchState === "error" && errorMsg && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <span className="text-red-500 text-lg">⚠️</span>
          <div>
            <p className="text-sm font-medium text-red-800">
              API 조회 중 오류가 발생했습니다
            </p>
            <p className="text-xs text-red-600 mt-0.5">{errorMsg}</p>
          </div>
          <button
            onClick={fetchJobs}
            className="ml-auto text-xs text-red-700 underline hover:text-red-900"
          >
            재시도
          </button>
        </div>
      )}

      {/* 통계 카드 */}
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

      {/* 진행 중 작업 */}
      <div className="bg-gray-50 rounded-xl p-6 border mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          진행 중인 작업
          <span className="text-xs font-normal text-gray-500 bg-gray-200 px-2 py-1 rounded-full">
            {fetchState === "loading" ? "갱신 중…" : `${POLL_INTERVAL_MS / 1000}초마다 자동 갱신`}
          </span>
        </h2>
        <div className="flex flex-col gap-4">
          {activeJobs.length === 0 ? (
            <p className="text-center text-gray-500 py-8">
              {fetchState === "loading" && jobs.length === 0
                ? "데이터를 불러오는 중입니다…"
                : "진행 중인 작업이 없습니다."}
            </p>
          ) : (
            activeJobs.map((job) => <PipelineStatus key={job.id} job={job} />)
          )}
        </div>
      </div>

      {/* 완료/실패 작업 */}
      {finishedJobs.length > 0 && (
        <div className="bg-gray-50 rounded-xl p-6 border">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            완료된 작업 ({finishedJobs.length})
          </h2>
          <div className="flex flex-col gap-4">
            {finishedJobs.map((job) => (
              <PipelineStatus key={job.id} job={job} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
