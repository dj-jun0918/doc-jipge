"use client";

import { useEffect, useState } from "react";

// Types matching backend app/schemas/evaluation.py
interface MetricValue {
  precision: number;
  recall: number;
  f1: number;
}

interface PathMetric extends MetricValue {
  count: number;
  cost_usd: number;
}

interface MetricsData {
  overall: MetricValue;
  by_field: { [key: string]: MetricValue };
  by_path: { [key: string]: PathMetric };
  total_cost_usd: number;
}

interface AblationCondition {
  condition_id: string;
  name: string;
  components: string[];
  description: string;
  metrics: MetricValue;
  cost_estimate_usd: number;
}

interface AblationData {
  conditions: AblationCondition[];
}

interface FieldKappa {
  field_name: string;
  kappa: number;
  agreement_level: string;
}

interface IaaData {
  overall_kappa: number;
  by_field: FieldKappa[];
  evaluated_count: number;
}

// Landis & Koch κ 해석 — 하드코딩 금지, 실제 κ값에 따라 라벨 산출
function kappaLabel(k: number): string {
  if (k < 0.0) return "음의 일치 (Poor)";
  if (k < 0.21) return "약한 일치 (Slight)";
  if (k < 0.41) return "어느 정도 일치 (Fair)";
  if (k < 0.61) return "보통 일치 (Moderate)";
  if (k < 0.81) return "상당한 합의 (Substantial)";
  return "거의 완벽한 합의 (Almost Perfect)";
}

interface CiBound {
  point_estimate: number;
  ci_low: number;
  ci_high: number;
}

interface BootstrapData {
  precision: CiBound;
  recall: CiBound;
  f1: CiBound;
  resampling_iterations: number;
}

interface ErrorExample {
  announcement_id: string;
  title: string;
  field_name: string;
  ground_truth: any;
  prediction: any;
}

interface ErrorPattern {
  pattern_name: string;
  count: number;
  ratio: number;
  description: string;
  examples: ErrorExample[];
}

interface ErrorsData {
  total_errors: number;
  patterns: ErrorPattern[];
}

export default function EvaluationDashboardPage() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [ablation, setAblation] = useState<AblationData | null>(null);
  const [iaa, setIaa] = useState<IaaData | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapData | null>(null);
  const [errors, setErrors] = useState<ErrorsData | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("overall");

  useEffect(() => {
    async function fetchAllEvaluationData() {
      setLoading(true);
      setErrorMessage(null);
      try {
        const [resMetrics, resAblation, resIaa, resBootstrap, resErrors] = await Promise.all([
          fetch("/backend-api/evaluation/metrics"),
          fetch("/backend-api/evaluation/ablation"),
          fetch("/backend-api/evaluation/iaa"),
          fetch("/backend-api/evaluation/bootstrap"),
          fetch("/backend-api/evaluation/errors"),
        ]);

        if (!resMetrics.ok || !resAblation.ok || !resIaa.ok || !resBootstrap.ok || !resErrors.ok) {
          throw new Error("평가 API 호출 중 오류가 발생했습니다.");
        }

        const [dataMetrics, dataAblation, dataIaa, dataBootstrap, dataErrors] = await Promise.all([
          resMetrics.json(),
          resAblation.json(),
          resIaa.json(),
          resBootstrap.json(),
          resErrors.json(),
        ]);

        setMetrics(dataMetrics);
        setAblation(dataAblation);
        setIaa(dataIaa);
        setBootstrap(dataBootstrap);
        setErrors(dataErrors);
      } catch (err) {
        console.error("평가 프레임워크 데이터 로드 실패:", err);
        setErrorMessage("평가 데이터를 로드하지 못했습니다. 백엔드 서비스(FastAPI)가 기동 중인지 확인하세요.");
      } finally {
        setLoading(false);
      }
    }

    fetchAllEvaluationData();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4 text-gray-900 px-6 py-10">
        <div className="w-12 h-12 rounded-full border-4 border-gray-200 border-t-blue-600 animate-spin" />
        <p className="text-gray-500 text-sm font-semibold">평가 프레임워크 실시간 결과 집계 중...</p>
      </main>
    );
  }

  if (errorMessage) {
    return (
      <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-3 text-gray-900 px-6 py-10 text-center">
        <svg className="h-12 w-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p className="text-base font-semibold text-gray-900">{errorMessage}</p>
        <p className="text-xs text-gray-500 max-w-md">이 오류는 백엔드 서버(FastAPI)가 포트 8000에서 정상 동작하지 않거나 네트워크 연동에 문제가 있을 때 발생할 수 있습니다.</p>
      </main>
    );
  }

  // Helper for displaying percentages
  const pct = (num: number) => `${Math.round(num * 1000) / 10}%`;

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 px-6 py-10">
      <section className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">
            📊 평가 프레임워크 & IAA 분석 대시보드
          </h1>
          <p className="text-gray-600 mt-2 text-sm max-w-2xl">
            추출 정확도, 소거법(Ablation) 연구, Bootstrap 95% 신뢰구간 측정, 라벨러 합의도(IAA)를 투명하게 시각화한 종합 통계 보드입니다.
          </p>
        </div>

        {/* Tab navigation */}
        <div className="flex border-b border-gray-200 mb-8 overflow-x-auto gap-1">
          {[
            { id: "overall", label: "📈 종합 정확도 & 신뢰구간" },
            { id: "ablation", label: "🧪 소거법(Ablation) 연구" },
            { id: "iaa", label: "🤝 라벨러 합의도(IAA)" },
            { id: "errors", label: "❌ 오답 패턴 분석(Taxonomy)" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`whitespace-nowrap px-5 py-3.5 text-sm font-bold border-b-2 transition cursor-pointer ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-900 hover:border-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* 1. 종합 정확도 & 신뢰구간 탭 */}
        {activeTab === "overall" && (
          <div className="space-y-8 animate-fadeIn">
            {/* Top row overall cards */}
            <div className="grid md:grid-cols-3 gap-6">
              {[
                { title: "정밀도 (Precision)", data: bootstrap?.precision, desc: "추출한 조건 중 실제 정답인 비율" },
                { title: "재현율 (Recall)", data: bootstrap?.recall, desc: "정답 자격조건 중 실제 추출해낸 비율" },
                { title: "F1-Score", data: bootstrap?.f1, desc: "정밀도와 재현율의 균형 조화 평균값" },
              ].map((item) => (
                <div key={item.title} className="rounded-2xl border bg-white p-6 shadow-sm flex flex-col justify-between relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-bl-full pointer-events-none" />
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">{item.title}</h4>
                    <h3 className="text-4xl font-black text-blue-600 mt-3">{metrics ? pct(item.data?.point_estimate || 0) : "-"}</h3>
                    <p className="text-[11px] text-gray-400 mt-1">{item.desc}</p>
                  </div>
                  {item.data && (
                    <div className="mt-4 border-t pt-3 flex justify-between items-center text-xs text-gray-600">
                      <span>95% 신뢰구간 (CI):</span>
                      <span className="font-bold text-gray-900 bg-gray-100 px-2 py-0.5 rounded">
                        {pct(item.data.ci_low)} ~ {pct(item.data.ci_high)}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Bootstrap Resampling Iterations Note */}
            {bootstrap && (
              <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 text-xs text-blue-800 flex items-center gap-2">
                <svg className="w-4 h-4 text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  전체 메트릭의 95% 신뢰구간(Confidence Interval)은 <strong>Bootstrap Resampling {bootstrap.resampling_iterations}회</strong> 모사 수행을 통해 정교하게 측정되었습니다.
                </span>
              </div>
            )}

            {/* Grid for field-specific and path-specific */}
            <div className="grid lg:grid-cols-2 gap-8">
              {/* Field specific metrics */}
              <div className="rounded-2xl border bg-white p-6 shadow-sm">
                <h3 className="text-lg font-bold text-gray-900 border-b pb-3 mb-5">
                  🏷️ 표준 조건 항목별 정확도
                </h3>
                <div className="space-y-4">
                  {metrics &&
                    Object.entries(metrics.by_field).map(([field, m]) => {
                      // Translate key to Korean display name
                      const fieldNamesKo: { [key: string]: string } = {
                        age: "나이",
                        location: "지역",
                        company_scale: "업력",
                        is_small_business: "업종",
                        certification: "인증",
                        employee_count: "종업원 수",
                        revenue: "매출",
                      };
                      return (
                        <div key={field} className="group">
                          <div className="flex items-center justify-between mb-1.5 text-xs font-semibold">
                            <span className="text-gray-700 font-bold group-hover:text-blue-600 transition-colors">
                              {fieldNamesKo[field] || field}
                            </span>
                            <div className="flex gap-3 text-[11px]">
                              <span className="text-gray-500">P: {pct(m.precision)}</span>
                              <span className="text-gray-500">R: {pct(m.recall)}</span>
                              <span className="text-gray-900 font-extrabold">F1: {pct(m.f1)}</span>
                            </div>
                          </div>
                          <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden shadow-inner">
                            <div
                              className="h-full bg-blue-600 rounded-full transition-all duration-500"
                              style={{ width: `${Math.round(m.f1 * 100)}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* Path specific metrics */}
              <div className="rounded-2xl border bg-white p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <h3 className="text-lg font-bold text-gray-900 border-b pb-3 mb-5">
                    ⚙️ 추출 파이프라인(Path)별 효율 & 비용
                  </h3>
                  <div className="space-y-5">
                    {metrics &&
                      Object.entries(metrics.by_path).map(([path, m]) => {
                        const pathLabels: { [key: string]: string } = {
                          rule_based: "규칙 엔진 (Rule Parser)",
                          text_llm: "텍스트 거대언어모델 (Text LLM)",
                          vision_llm: "시각 거대언어모델 (Vision LLM)",
                        };
                        return (
                          <div key={path} className="rounded-xl border p-4 bg-gray-50/50 hover:bg-gray-50 transition">
                            <div className="flex items-center justify-between mb-2">
                              <h4 className="text-sm font-bold text-gray-900">{pathLabels[path] || path}</h4>
                              <span className="text-xs font-extrabold bg-blue-50 text-blue-600 px-2 py-0.5 rounded">
                                F1: {pct(m.f1)}
                              </span>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-center text-xs mt-3">
                              <div className="border-r">
                                <p className="text-gray-500 text-[10px]">처리 수</p>
                                <p className="font-bold text-gray-800 mt-1">{m.count}건</p>
                              </div>
                              <div className="border-r">
                                <p className="text-gray-500 text-[10px]">정밀도/재현율</p>
                                <p className="font-bold text-gray-800 mt-1">{pct(m.precision)} / {pct(m.recall)}</p>
                              </div>
                              <div>
                                <p className="text-gray-500 text-[10px]">사용 비용</p>
                                <p className="font-bold text-emerald-600 mt-1">${m.cost_usd.toFixed(2)}</p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>

                {metrics && (
                  <div className="mt-6 border-t pt-5 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold text-gray-500 uppercase">분석 비용 추정 (USD)</p>
                      <p className="text-xs text-gray-400 mt-0.5">경로별 단가 기반 추정치 (실제 청구액 아님)</p>
                    </div>
                    <p className="text-3xl font-black text-emerald-600">${metrics.total_cost_usd.toFixed(2)}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 2. 소거법(Ablation) 연구 탭 */}
        {activeTab === "ablation" && ablation && (
          <div className="space-y-6 animate-fadeIn">
            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <h3 className="text-lg font-bold text-gray-900 border-b pb-3 mb-6">
                🧪 Component-wise Ablation 실험 결과
              </h3>
              <div className="space-y-6">
                {ablation.conditions.map((cond, idx) => {
                  const scorePct = Math.round(cond.metrics.f1 * 100);
                  return (
                    <div key={cond.condition_id} className="relative overflow-hidden group rounded-xl border p-5 bg-white hover:bg-blue-50/5 transition duration-300 hover:shadow-sm">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="space-y-2">
                          <div className="flex items-center gap-3">
                            <span className="w-8 h-8 rounded-lg bg-blue-600 text-white font-extrabold flex items-center justify-center text-xs">
                              {cond.condition_id}
                            </span>
                            <h4 className="text-base font-bold text-gray-900">{cond.name}</h4>
                          </div>
                          <p className="text-xs text-gray-600 max-w-2xl">{cond.description}</p>
                          <div className="flex flex-wrap gap-1.5 pt-2">
                            {cond.components.map((c) => (
                              <span key={c} className="text-[10px] bg-gray-100 font-semibold px-2 py-0.5 rounded text-gray-600 border">
                                {c}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Ablation Metrics */}
                        <div className="flex items-center gap-6 self-start md:self-auto min-w-[240px] justify-between md:justify-end">
                          <div className="text-right">
                            <p className="text-[10px] text-gray-400 font-semibold">예상 비용 (USD)</p>
                            <p className="text-xs font-bold text-gray-800 mt-1">${cond.cost_estimate_usd.toFixed(2)}</p>
                          </div>
                          <div className="border-r h-8" />
                          <div className="text-right">
                            <p className="text-[10px] text-gray-400 font-semibold">Precision / Recall</p>
                            <p className="text-xs font-bold text-gray-800 mt-1">
                              {pct(cond.metrics.precision)} / {pct(cond.metrics.recall)}
                            </p>
                          </div>
                          <div className="border-r h-8" />
                          <div className="flex flex-col items-end">
                            <span className="text-2xl font-black text-blue-600">{scorePct}%</span>
                            <span className="text-[9px] text-gray-400 font-semibold">F1 Score</span>
                          </div>
                          <div className="w-20 h-2 bg-gray-100 rounded-full overflow-hidden shadow-inner">
                            <div className="h-full bg-blue-600 rounded-full" style={{ width: `${scorePct}%` }} />
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* 3. 라벨러 합의도(IAA) 탭 */}
        {activeTab === "iaa" && iaa && (
          <div className="space-y-8 animate-fadeIn">
            {/* Top overall card */}
            <div className="rounded-2xl border bg-white p-8 shadow-sm flex flex-col md:flex-row items-center justify-between gap-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-bl-full pointer-events-none" />
              <div className="space-y-2">
                <h3 className="text-xl font-extrabold text-gray-900">
                  🤝 Inter-Annotator Agreement (Inter-라벨러 합의도)
                </h3>
                <p className="text-sm text-gray-500 max-w-2xl leading-relaxed">
                  임태규 라벨러와 방정우 라벨러가 구축한 동일 공고 자격요건에 대한 교차검증(Cross-Labeling) 일치 지표입니다. 
                  신뢰도 지표 산출에는 통계적으로 정교한 <strong>Cohen's Kappa (코헨의 카파 계수 κ)</strong> 통계식이 사용됩니다.
                </p>
                <div className="flex gap-4 text-xs text-gray-500 pt-2">
                  <span>📊 교차 평가 공고 수: <strong className="text-gray-900">{iaa.evaluated_count}개</strong></span>
                  <span>•</span>
                  <span>📝 Cohen's κ 일치 평가 규모: <strong className="text-gray-900">{kappaLabel(iaa.overall_kappa)}</strong></span>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 text-center min-w-[200px]">
                <p className="text-[11px] font-bold uppercase tracking-wider text-blue-700">종합 Cohen's κ 수치</p>
                <h2 className="text-5xl font-black text-blue-600 mt-2">{iaa.overall_kappa.toFixed(3)}</h2>
                <span className="inline-block mt-3 text-xs bg-blue-600 text-white font-bold px-3 py-1 rounded-full shadow-sm">
                  {kappaLabel(iaa.overall_kappa)}
                </span>
              </div>
            </div>

            {/* Field kappa scores grid */}
            <div className="rounded-2xl border bg-white p-6 shadow-sm">
              <h3 className="text-lg font-bold text-gray-900 border-b pb-3 mb-6">
                📝 표준 조건별 Cohen's κ 지표 상세
              </h3>
              <div className="grid md:grid-cols-2 gap-6">
                {iaa.by_field.map((f) => {
                  const fieldNamesKo: { [key: string]: string } = {
                    age: "나이",
                    location: "지역",
                    company_scale: "업력",
                    is_small_business: "업종",
                    constraint: "종업원 수/기타 요건",
                    certification: "인증",
                  };
                  return (
                    <div key={f.field_name} className="flex items-center justify-between p-4 rounded-xl border hover:border-blue-200 hover:bg-blue-50/5 transition">
                      <div className="space-y-1">
                        <h4 className="text-sm font-bold text-gray-900">{fieldNamesKo[f.field_name] || f.field_name}</h4>
                        <p className="text-[10px] text-gray-400 font-semibold">{f.agreement_level}</p>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-black text-blue-600">{f.kappa.toFixed(3)}</span>
                        <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden shadow-inner mt-1.5">
                          <div className="h-full bg-blue-600 rounded-full" style={{ width: `${Math.round(f.kappa * 100)}%` }} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* 4. 오답 패턴 분석(Taxonomy) 탭 */}
        {activeTab === "errors" && errors && (
          <div className="space-y-8 animate-fadeIn">
            {/* Total errors header card */}
            <div className="rounded-2xl border bg-white p-6 shadow-sm flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-gray-900">❌ 오답 패턴 분석 (Error Taxonomy)</h3>
                <p className="text-gray-500 text-xs mt-1">파이프라인 추론 결과 중 실패 사례들을 분석해 분류한 결과입니다.</p>
              </div>
              <div className="text-right">
                <span className="text-xs font-bold text-gray-400">발견된 총 오류</span>
                <p className="text-3xl font-black text-red-600 mt-1">{errors.total_errors}건</p>
              </div>
            </div>

            {/* Error patterns lists */}
            <div className="space-y-6">
              {errors.patterns.map((p) => (
                <div key={p.pattern_name} className="rounded-2xl border bg-white p-6 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 border-b pb-4 gap-2">
                    <div>
                      <h4 className="text-base font-bold text-gray-900">{p.pattern_name}</h4>
                      <p className="text-xs text-gray-500 mt-1">{p.description}</p>
                    </div>
                    <div className="text-right sm:self-center">
                      <span className="text-lg font-extrabold text-red-600">{p.count}건</span>
                      <span className="text-xs text-gray-400 font-semibold ml-2">({pct(p.ratio)})</span>
                    </div>
                  </div>

                  {/* Examples table */}
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-gray-50 text-gray-500 border-b">
                          <th className="px-4 py-3 font-semibold">공고 ID</th>
                          <th className="px-4 py-3 font-semibold">공고 제목</th>
                          <th className="px-4 py-3 font-semibold">해당 항목</th>
                          <th className="px-4 py-3 font-semibold text-red-600">Ground Truth (실제 정답)</th>
                          <th className="px-4 py-3 font-semibold text-gray-500">Prediction (모델 추출값)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.examples.map((ex, idx) => {
                          const gtStr = ex.ground_truth ? JSON.stringify(ex.ground_truth) : "누락(None)";
                          const predStr = ex.prediction ? JSON.stringify(ex.prediction) : "미추출(None)";
                          return (
                            <tr key={idx} className="border-b hover:bg-gray-50/50">
                              <td className="px-4 py-3 font-bold text-gray-700">{ex.announcement_id}</td>
                              <td className="px-4 py-3 text-gray-900 font-medium">{ex.title}</td>
                              <td className="px-4 py-3 font-semibold text-gray-600 bg-gray-100/50 rounded px-1.5 py-0.5 inline-block my-2">
                                {ex.field_name === "age" ? "나이" : ex.field_name === "location" ? "지역" : ex.field_name === "company_scale" ? "업력" : ex.field_name === "is_small_business" ? "업종" : ex.field_name === "certification" ? "인증" : ex.field_name}
                              </td>
                              <td className="px-4 py-3 text-red-700 font-semibold bg-red-50/30">{gtStr}</td>
                              <td className="px-4 py-3 text-gray-600 font-medium">{predStr}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
