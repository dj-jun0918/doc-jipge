"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar
} from "recharts";

// ==========================================
// Types & Interfaces
// ==========================================
interface MetricItem {
  precision: number;
  recall: number;
  f1: number;
}

interface PathMetricItem extends MetricItem {
  count: number;
  cost_usd: number;
}

interface EvaluationMetrics {
  overall: MetricItem;
  by_field: Record<string, MetricItem>;
  by_path: Record<string, PathMetricItem>;
  total_cost_usd: number;
}

interface AblationCondition {
  condition_id: string;
  name: string;
  components: string[];
  description: string;
  metrics: MetricItem;
  cost_estimate_usd: number;
}

interface AblationResponse {
  conditions: AblationCondition[];
}

interface IaaFieldScore {
  field_name: string;
  kappa: number;
  agreement_level: string;
}

interface IaaResponse {
  overall_kappa: number;
  by_field: IaaFieldScore[];
  evaluated_count: number;
}

interface BootstrapMetricCi {
  point_estimate: number;
  ci_low: number;
  ci_high: number;
}

interface BootstrapResponse {
  precision: BootstrapMetricCi;
  recall: BootstrapMetricCi;
  f1: BootstrapMetricCi;
  resampling_iterations: number;
}

interface ErrorCaseExample {
  announcement_id: string;
  title: string;
  field_name: string;
  ground_truth: any;
  prediction: any;
}

interface ErrorPatternItem {
  pattern_name: string;
  count: number;
  ratio: number;
  description: string;
  examples: ErrorCaseExample[];
}

interface ErrorAnalysisResponse {
  total_errors: number;
  patterns: ErrorPatternItem[];
}

// 필드 키 한글 맵핑용 사전
const FIELD_KOREAN_NAMES: Record<string, string> = {
  age: "업력 / 연령",
  location: "소재 지역",
  company_scale: "기업 규모",
  is_small_business: "소상공인 여부",
  constraint: "제한 조건",
  certification: "인증 자격"
};

const ERROR_COLORS = ["#FF6B6B", "#FFD93D", "#6BCB77"];

export default function EvaluationDashboardPage() {
  // States for APIs
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null);
  const [ablation, setAblation] = useState<AblationResponse | null>(null);
  const [iaa, setIaa] = useState<IaaResponse | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [errors, setErrors] = useState<ErrorAnalysisResponse | null>(null);

  // UI States
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedErrorPattern, setExpandedErrorPattern] = useState<string | null>(null);

  useEffect(() => {
    async function loadEvaluationData() {
      setLoading(true);
      setErrorMsg(null);
      try {
        const [resMetrics, resAblation, resIaa, resBootstrap, resErrors] = await Promise.all([
          fetch("/api/evaluation/metrics").then((r) => r.json()),
          fetch("/api/evaluation/ablation").then((r) => r.json()),
          fetch("/api/evaluation/iaa").then((r) => r.json()),
          fetch("/api/evaluation/bootstrap").then((r) => r.json()),
          fetch("/api/evaluation/errors").then((r) => r.json())
        ]);

        setMetrics(resMetrics);
        setAblation(resAblation);
        setIaa(resIaa);
        setBootstrap(resBootstrap);
        setErrors(resErrors);
      } catch (err) {
        console.error("평가 데이터 로드 에러:", err);
        setErrorMsg("평가 지표 데이터를 불러오는 중 오류가 발생했습니다.");
      } finally {
        setLoading(false);
      }
    }

    loadEvaluationData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
        <div className="w-12 h-12 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
        <p className="text-gray-500 font-semibold text-sm">평가 결과 지표 분석용 대시보드를 로딩하는 중...</p>
      </div>
    );
  }

  if (errorMsg || !metrics || !ablation || !iaa || !bootstrap || !errors) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6">
        <div className="max-w-md bg-white border rounded-2xl shadow-sm p-8 text-center">
          <svg className="mx-auto h-12 w-12 text-red-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h2 className="text-lg font-bold text-gray-900 mb-2">데이터 로드 실패</h2>
          <p className="text-sm text-gray-500 mb-6">{errorMsg || "일부 지표 데이터를 불러올 수 없습니다."}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition"
          >
            다시 시도
          </button>
        </div>
      </div>
    );
  }

  // 필드별 성능 시각화용 데이터 포맷터
  const radarData = Object.entries(metrics.by_field).map(([key, value]) => ({
    subject: FIELD_KOREAN_NAMES[key] || key,
    precision: Math.round(value.precision * 100),
    recall: Math.round(value.recall * 100),
    f1: Math.round(value.f1 * 100)
  }));

  // Ablation 차트용 데이터 포맷터 (비용은 usd, f1은 % 변환)
  const ablationChartData = ablation.conditions.map((c) => ({
    name: c.condition_id,
    fullName: c.name,
    "F1-Score (%)": Math.round(c.metrics.f1 * 100),
    "정밀도 (%)": Math.round(c.metrics.precision * 100),
    "재현율 (%)": Math.round(c.metrics.recall * 100),
    "추정 비용 (USD)": c.cost_estimate_usd
  }));

  // 오류 파이 차트 데이터
  const errorPieData = errors.patterns.map((p) => ({
    name: p.pattern_name.split(" ")[0],
    value: p.count,
    ratio: Math.round(p.ratio * 100)
  }));

  // IAA 카파 등급 색상 정의
  const getKappaColor = (kappa: number) => {
    if (kappa >= 0.6) return "text-emerald-700 bg-emerald-50 border-emerald-200";
    if (kappa >= 0.4) return "text-amber-700 bg-amber-50 border-amber-200";
    return "text-red-700 bg-red-50 border-red-200";
  };

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 px-6 py-10">
      <section className="mx-auto max-w-7xl">
        
        {/* 상단 브레드크럼 */}
        <div className="mb-6">
          <Link
            href="/matching"
            className="inline-flex items-center gap-2 text-sm font-semibold text-gray-500 hover:text-blue-600 transition"
          >
            ← 대시보드로 돌아가기
          </Link>
        </div>

        {/* 상단 헤더 섹션 */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm mb-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              🔬 매칭 엔진 통합 성능 평가 리포트
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              GT 라벨링 정합성 기준 시스템의 종합 정밀도, 재현율, Ablation 실험, 신뢰도 한계치 및 오답 분석 통계를 보여줍니다.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-2 text-center">
              <span className="text-[10px] font-bold text-blue-500 block uppercase tracking-wider">누적 평가 비용</span>
              <span className="text-lg font-black text-blue-700">${metrics.total_cost_usd.toFixed(2)}</span>
            </div>
            <div className="bg-purple-50 border border-purple-100 rounded-xl px-4 py-2 text-center">
              <span className="text-[10px] font-bold text-purple-500 block uppercase tracking-wider">GT 합의도 (Kappa)</span>
              <span className="text-lg font-black text-purple-700">{iaa.overall_kappa.toFixed(3)}</span>
            </div>
          </div>
        </div>

        {/* 1. 종합 메트릭 카드 및 Bootstrap 95% CI 영역 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Precision Card */}
          <div className="bg-white rounded-2xl border p-6 shadow-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-gray-400">정밀도 (Precision)</span>
              <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-semibold border border-indigo-100">발굴 정확도</span>
            </div>
            <div>
              <h2 className="text-4xl font-black text-slate-800 leading-none">
                {Math.round(bootstrap.precision.point_estimate * 1000) / 10}%
              </h2>
              {/* Bootstrap CI Range 표시 */}
              <div className="mt-4 bg-gray-50 rounded-lg border p-3 flex flex-col gap-1">
                <div className="flex justify-between text-[10px] text-gray-400 font-semibold">
                  <span>95% 신뢰 하한</span>
                  <span>95% 신뢰 상한</span>
                </div>
                <div className="flex justify-between text-xs font-bold text-gray-700">
                  <span>{(bootstrap.precision.ci_low * 100).toFixed(1)}%</span>
                  <span>{(bootstrap.precision.ci_high * 100).toFixed(1)}%</span>
                </div>
                {/* 시각적인 레인지 바 */}
                <div className="w-full h-1.5 bg-gray-200 rounded-full relative mt-1.5 overflow-hidden">
                  <div
                    className="absolute h-full bg-indigo-600 rounded-full"
                    style={{
                      left: `${bootstrap.precision.ci_low * 100}%`,
                      right: `${100 - bootstrap.precision.ci_high * 100}%`
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Recall Card */}
          <div className="bg-white rounded-2xl border p-6 shadow-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-gray-400">재현율 (Recall)</span>
              <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-semibold border border-emerald-100">발굴 커버리지</span>
            </div>
            <div>
              <h2 className="text-4xl font-black text-slate-800 leading-none">
                {Math.round(bootstrap.recall.point_estimate * 1000) / 10}%
              </h2>
              {/* Bootstrap CI Range 표시 */}
              <div className="mt-4 bg-gray-50 rounded-lg border p-3 flex flex-col gap-1">
                <div className="flex justify-between text-[10px] text-gray-400 font-semibold">
                  <span>95% 신뢰 하한</span>
                  <span>95% 신뢰 상한</span>
                </div>
                <div className="flex justify-between text-xs font-bold text-gray-700">
                  <span>{(bootstrap.recall.ci_low * 100).toFixed(1)}%</span>
                  <span>{(bootstrap.recall.ci_high * 100).toFixed(1)}%</span>
                </div>
                {/* 시각적인 레인지 바 */}
                <div className="w-full h-1.5 bg-gray-200 rounded-full relative mt-1.5 overflow-hidden">
                  <div
                    className="absolute h-full bg-emerald-600 rounded-full"
                    style={{
                      left: `${bootstrap.recall.ci_low * 100}%`,
                      right: `${100 - bootstrap.recall.ci_high * 100}%`
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* F1-Score Card */}
          <div className="bg-white rounded-2xl border p-6 shadow-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-gray-400">조화 평균 (F1-Score)</span>
              <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded font-semibold border border-purple-100">종합 성능 균형</span>
            </div>
            <div>
              <h2 className="text-4xl font-black text-slate-800 leading-none">
                {Math.round(bootstrap.f1.point_estimate * 1000) / 10}%
              </h2>
              {/* Bootstrap CI Range 표시 */}
              <div className="mt-4 bg-gray-50 rounded-lg border p-3 flex flex-col gap-1">
                <div className="flex justify-between text-[10px] text-gray-400 font-semibold">
                  <span>95% 신뢰 하한</span>
                  <span>95% 신뢰 상한</span>
                </div>
                <div className="flex justify-between text-xs font-bold text-gray-700">
                  <span>{(bootstrap.f1.ci_low * 100).toFixed(1)}%</span>
                  <span>{(bootstrap.f1.ci_high * 100).toFixed(1)}%</span>
                </div>
                {/* 시각적인 레인지 바 */}
                <div className="w-full h-1.5 bg-gray-200 rounded-full relative mt-1.5 overflow-hidden">
                  <div
                    className="absolute h-full bg-purple-600 rounded-full"
                    style={{
                      left: `${bootstrap.f1.ci_low * 100}%`,
                      right: `${100 - bootstrap.f1.ci_high * 100}%`
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 2. Ablation실험 & 필드별 성능 시각화 그래프 영역 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8 items-stretch">
          {/* Ablation Chart (lg: 7/12) */}
          <div className="lg:col-span-7 bg-white rounded-2xl border p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h3 className="text-base font-bold text-gray-900 mb-1 flex items-center gap-2">
                🧩 Component Ablation Study (소거 실험 분석)
              </h3>
              <p className="text-xs text-gray-400 mb-6">
                규칙 Baseline(C1)부터 Verifier를 적용한 최종 하이브리드 파이프라인(C4)까지의 F1성능과 예상 토큰 비용의 흐름.
              </p>
            </div>
            
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={ablationChartData} margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis yAxisId="left" domain={[40, 100]} unit="%" tickCount={4} />
                  <YAxis yAxisId="right" orientation="right" domain={[0, 60]} unit="$" />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-white border rounded-xl shadow-lg p-3 text-xs leading-normal">
                            <p className="font-bold text-gray-800 mb-1">[{data.name}] {data.fullName}</p>
                            <p className="text-purple-600 font-semibold">F1-Score: {data["F1-Score (%)"]}%</p>
                            <p className="text-indigo-600">정밀도: {data["정밀도 (%)"]}% | 재현율: {data["재현율 (%)"]}%</p>
                            <p className="text-amber-600 font-semibold mt-1">예상 비용: ${data["추정 비용 (USD)"].toFixed(2)}</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Legend />
                  <Bar yAxisId="right" dataKey="추정 비용 (USD)" fill="#FFD93D" radius={[4, 4, 0, 0]} opacity={0.8} barSize={40} />
                  <Line yAxisId="left" type="monotone" dataKey="F1-Score (%)" stroke="#8884d8" strokeWidth={3} dot={{ r: 5 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Radar Chart for by_field (lg: 5/12) */}
          <div className="lg:col-span-5 bg-white rounded-2xl border p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h3 className="text-base font-bold text-gray-900 mb-1">
                🏷️ 자격 요건 필드별 매칭 정확도
              </h3>
              <p className="text-xs text-gray-400 mb-4">
                각 파싱 필드별 Precision, Recall, F1 지표 분포도.
              </p>
            </div>
            
            <div className="h-[280px] w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                  <PolarGrid stroke="#E2E8F0" />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: "#64748B", fontWeight: 600 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8 }} />
                  <Radar name="F1-Score" dataKey="f1" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
                  <Radar name="Precision" dataKey="precision" stroke="#38BDF8" fill="#38BDF8" fillOpacity={0.1} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: "10px", marginTop: "10px" }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* 3. 처리 경로별 비용 분석 및 IAA 합의 지표 영역 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8 items-stretch">
          {/* Path Metrics (lg: 6/12) */}
          <div className="lg:col-span-6 bg-white rounded-2xl border p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h3 className="text-base font-bold text-gray-900 mb-1">
                ⚡ 라우팅 경로별 처리량 및 효율성
              </h3>
              <p className="text-xs text-gray-400 mb-4">
                정규표현 규칙과 LLM 추출 파이프라인별 판정 성공 수량과 소요 비용 대조.
              </p>
            </div>

            <div className="flex-1 overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b text-gray-400 font-semibold bg-gray-50/50">
                    <th className="py-2.5 px-3 rounded-l-lg">라우팅 경로</th>
                    <th className="py-2.5 px-2">건수 (Count)</th>
                    <th className="py-2.5 px-2">정밀도</th>
                    <th className="py-2.5 px-2">재현율</th>
                    <th className="py-2.5 px-2">F1</th>
                    <th className="py-2.5 px-3 rounded-r-lg text-right">소요 비용</th>
                  </tr>
                </thead>
                <tbody className="divide-y font-medium text-gray-700">
                  {Object.entries(metrics.by_path).map(([pathKey, val]) => (
                    <tr key={pathKey} className="hover:bg-gray-50/40">
                      <td className="py-3 px-3 font-bold text-slate-800 capitalize">
                        {pathKey.replace("_", " ")}
                      </td>
                      <td className="py-3 px-2">{val.count}건</td>
                      <td className="py-3 px-2">{(val.precision * 100).toFixed(1)}%</td>
                      <td className="py-3 px-2">{(val.recall * 100).toFixed(1)}%</td>
                      <td className="py-3 px-2 text-indigo-600 font-bold">{(val.f1 * 100).toFixed(1)}%</td>
                      <td className="py-3 px-3 text-right font-bold text-amber-600">
                        ${val.cost_usd.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* IAA Cohen's Kappa (lg: 6/12) */}
          <div className="lg:col-span-6 bg-white rounded-2xl border p-6 shadow-sm flex flex-col justify-between">
            <div className="flex items-start justify-between gap-4 mb-1">
              <div>
                <h3 className="text-base font-bold text-gray-900">
                  🤝 라벨러 신뢰성 합의도 (IAA - Cohen's κ)
                </h3>
                <p className="text-xs text-gray-400">
                  독립 작업자(임태규, 방정우) 간 교차 평가 {iaa.evaluated_count}건에 대한 필드별 일치도.
                </p>
              </div>
              <span className={`text-xs px-2.5 py-1 rounded-full border font-black block tracking-wide ${getKappaColor(iaa.overall_kappa)}`}>
                종합 κ: {iaa.overall_kappa.toFixed(3)}
              </span>
            </div>

            <div className="flex-1 overflow-x-auto mt-4">
              <table className="w-full text-left text-[11px] border-collapse">
                <thead>
                  <tr className="border-b text-gray-400 font-semibold bg-gray-50/50">
                    <th className="py-2 px-3 rounded-l-lg">필드명</th>
                    <th className="py-2 px-2">카파 계수 (Kappa)</th>
                    <th className="py-2 px-3 rounded-r-lg">합의 신뢰도 수준</th>
                  </tr>
                </thead>
                <tbody className="divide-y font-medium text-gray-700">
                  {iaa.by_field.map((item) => (
                    <tr key={item.field_name} className="hover:bg-gray-50/40">
                      <td className="py-2 px-3 font-bold text-slate-800">
                        {FIELD_KOREAN_NAMES[item.field_name] || item.field_name}
                      </td>
                      <td className="py-2 px-2 font-mono">
                        <span className={`px-1.5 py-0.5 rounded border text-xs font-bold ${getKappaColor(item.kappa)}`}>
                          {item.kappa.toFixed(3)}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-gray-500">{item.agreement_level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 4. 오류 Taxonomy 및 실제 불일치 케이스 디버깅 영역 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Error Taxonomy Pie Chart (lg: 5/12) */}
          <div className="lg:col-span-5 bg-white rounded-2xl border p-6 shadow-sm">
            <h3 className="text-base font-bold text-gray-900 mb-1">
              🚨 Error Taxonomy (오답 패턴 비율)
            </h3>
            <p className="text-xs text-gray-400 mb-6">
              총 {errors.total_errors}개 오추출 불일치 항목의 원인별 비율 분석.
            </p>

            <div className="h-[220px] w-full relative flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={errorPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {errorPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={ERROR_COLORS[index % ERROR_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-white border rounded-xl shadow-md p-2 text-xs">
                            <span className="font-bold">{data.name}</span>: {data.value}건 ({data.ratio}%)
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              
              {/* 도넛 차트 중앙에 에러 개수 바인딩 */}
              <div className="absolute flex flex-col items-center justify-center">
                <span className="text-3xl font-black text-slate-800">{errors.total_errors}건</span>
                <span className="text-[10px] text-gray-400 font-bold">오예측 누적</span>
              </div>
            </div>

            {/* 범례 카드 형태 */}
            <div className="mt-4 flex flex-col gap-2">
              {errors.patterns.map((p, index) => (
                <div key={p.pattern_name} className="flex justify-between items-center text-xs p-2 rounded-lg bg-gray-50 border border-gray-100">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: ERROR_COLORS[index % ERROR_COLORS.length] }} />
                    <span className="font-bold text-slate-700">{p.pattern_name}</span>
                  </div>
                  <span className="font-mono text-gray-500">
                    {p.count}건 ({Math.round(p.ratio * 100)}%)
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive Debugging List (lg: 7/12) */}
          <div className="lg:col-span-7 bg-white rounded-2xl border p-6 shadow-sm">
            <h3 className="text-base font-bold text-gray-900 mb-1">
              🔎 오답 디버그 콘솔 (GT vs Prediction 대조)
            </h3>
            <p className="text-xs text-gray-400 mb-6">
              패턴별 카드 클릭 시 실제 불일치가 발생한 공고 ID와 원본-예측 추출 데이터 대조표를 확인합니다.
            </p>

            <div className="space-y-4">
              {errors.patterns.map((p) => {
                const isExpanded = expandedErrorPattern === p.pattern_name;

                return (
                  <div
                    key={p.pattern_name}
                    className="border rounded-xl overflow-hidden transition-all duration-300 bg-white"
                  >
                    <button
                      onClick={() => setExpandedErrorPattern(isExpanded ? null : p.pattern_name)}
                      className="w-full text-left p-4 hover:bg-gray-50/50 flex items-center justify-between gap-4 cursor-pointer"
                    >
                      <div>
                        <h4 className="font-bold text-sm text-slate-800 flex items-center gap-2">
                          {p.pattern_name}
                          <span className="text-[10px] bg-red-50 text-red-600 border border-red-100 rounded px-1.5 py-0.5">
                            {p.count}건
                          </span>
                        </h4>
                        <p className="text-xs text-gray-400 mt-1 leading-snug">{p.description}</p>
                      </div>
                      <svg
                        className={`w-4 h-4 text-gray-400 transform transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {isExpanded && (
                      <div className="p-4 bg-gray-50/30 border-t space-y-4.5">
                        {p.examples.map((ex, idx) => (
                          <div key={idx} className="bg-white border rounded-lg p-3.5 shadow-sm text-xs space-y-2.5">
                            <div className="flex justify-between items-center border-b pb-1.5">
                              <span className="font-bold text-slate-800 truncate max-w-[240px]">
                                {ex.title}
                              </span>
                              <span className="font-semibold text-gray-400 font-mono text-[10px]">
                                ID: {ex.announcement_id}
                              </span>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                              <div className="bg-emerald-50/20 border border-emerald-100 rounded-lg p-2">
                                <span className="text-[9px] font-bold text-emerald-600 block mb-1">GT (정답 라벨)</span>
                                <pre className="font-mono text-[10px] text-emerald-800 whitespace-pre-wrap leading-tight">
                                  {JSON.stringify(ex.ground_truth, null, 2)}
                                </pre>
                              </div>
                              <div className="bg-rose-50/20 border border-rose-100 rounded-lg p-2">
                                <span className="text-[9px] font-bold text-rose-600 block mb-1">PREDICTION (예측 추출)</span>
                                <pre className="font-mono text-[10px] text-rose-800 whitespace-pre-wrap leading-tight">
                                  {ex.prediction ? JSON.stringify(ex.prediction, null, 2) : "None (추출 누락됨)"}
                                </pre>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

      </section>
    </main>
  );
}
