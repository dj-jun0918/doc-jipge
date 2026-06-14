"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

// 인증: backend CERT_MAPPING(matcher/cert_mapping.py) 표준 키와 1:1 — 선택 시 {key:true}로 저장돼
// matcher의 company_certs.get(key) is True 경로(즉시 충족)와 맞물린다.
const CERT_OPTIONS: { key: string; label: string }[] = [
  { key: "venture_company", label: "벤처기업" },
  { key: "inno_biz", label: "이노비즈 (기술혁신형)" },
  { key: "main_biz", label: "메인비즈 (경영혁신형)" },
  { key: "iso_9001", label: "ISO 9001 (품질경영)" },
  { key: "iso_14001", label: "ISO 14001 (환경경영)" },
  { key: "iso_27001", label: "ISO 27001 (정보보안)" },
  { key: "iso_22000", label: "ISO 22000 (식품안전)" },
  { key: "gmp", label: "GMP" },
  { key: "haccp", label: "HACCP" },
  { key: "ce_marking", label: "CE 마킹" },
  { key: "kc_certification", label: "KC 인증" },
  { key: "women_owned", label: "여성기업" },
  { key: "social_enterprise", label: "사회적기업" },
  { key: "rd_lab", label: "기업부설연구소" },
  { key: "ip_protection", label: "특허/지식재산권" },
  { key: "nep", label: "신제품 (NEP)" },
  { key: "net", label: "신기술 (NET)" },
  { key: "gs", label: "GS 인증 (SW품질)" },
];
const CERT_LABEL: Record<string, string> = Object.fromEntries(
  CERT_OPTIONS.map((c) => [c.key, c.label])
);

// 지역: matcher REGION_GROUPS의 17개 광역 시도(공식 명칭은 alias로 정규화됨) — 자유입력의 '확인필요' 누수 차단.
const REGIONS = [
  "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
  "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도",
  "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
];

// 업종: 표준산업분류(KSIC) 대분류 — datalist 제안(자유 입력도 허용). 표준 용어로 유도해 매칭 어휘를 맞춘다.
const INDUSTRY_SUGGESTIONS = [
  "제조업", "정보통신업", "도매 및 소매업", "건설업", "전문·과학 및 기술 서비스업",
  "농업·임업 및 어업", "금융 및 보험업", "부동산업", "숙박 및 음식점업", "운수 및 창고업",
  "교육 서비스업", "보건업 및 사회복지 서비스업", "예술·스포츠 및 여가관련 서비스업",
  "출판·영상·방송통신 및 정보서비스업", "사업시설관리·사업지원 및 임대 서비스업",
  "전기·가스·증기 및 공기조절 공급업", "수도·하수 및 폐기물 처리업", "광업",
];

const REVENUE_UNITS = [
  { key: "억", label: "억원", factor: 100_000_000 },
  { key: "만", label: "만원", factor: 10_000 },
  { key: "원", label: "원", factor: 1 },
] as const;
type RevenueUnit = (typeof REVENUE_UNITS)[number]["key"];

interface Company {
  id: string;
  name: string;
  founded_date: string;
  revenue: number;
  region: string;
  industry: string;
  employee_count: number;
  ceo_birth_date: string;
  certifications: Record<string, unknown> | null;
}

interface SimpleForm {
  name: string;
  founded_date: string;
  region: string;
  industry: string;
  employee_count: string;
  ceo_birth_date: string;
}

const EMPTY_FORM: SimpleForm = {
  name: "",
  founded_date: "",
  region: "",
  industry: "",
  employee_count: "",
  ceo_birth_date: "",
};

function revenueToUnit(won: number): { value: string; unit: RevenueUnit } {
  if (won > 0 && won % 100_000_000 === 0)
    return { value: String(won / 100_000_000), unit: "억" };
  if (won > 0 && won % 10_000 === 0) return { value: String(won / 10_000), unit: "만" };
  return { value: String(won), unit: "원" };
}

function certsToState(certs: Company["certifications"]): {
  keys: Record<string, boolean>;
  other: string;
} {
  const keys: Record<string, boolean> = {};
  let other = "";
  if (certs) {
    Object.entries(certs).forEach(([k, v]) => {
      if (k === "note" && typeof v === "string") other = v;
      else if (v === true) keys[k] = true;
    });
  }
  return { keys, other };
}

function certSummary(certs: Company["certifications"]): string {
  const { keys, other } = certsToState(certs);
  const labels = Object.keys(keys).map((k) => CERT_LABEL[k] ?? k);
  if (other) labels.push(other);
  return labels.length ? labels.join(", ") : "-";
}

export default function CompaniesPage() {
  const today = new Date().toISOString().split("T")[0];

  const [companies, setCompanies] = useState<Company[]>([]);
  const [listError, setListError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  const [form, setForm] = useState<SimpleForm>(EMPTY_FORM);
  const [revenueValue, setRevenueValue] = useState("");
  const [revenueUnit, setRevenueUnit] = useState<RevenueUnit>("억");
  const [certKeys, setCertKeys] = useState<Record<string, boolean>>({});
  const [certOther, setCertOther] = useState("");

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const unitFactor =
    REVENUE_UNITS.find((u) => u.key === revenueUnit)?.factor ?? 1;
  const revenueWon = revenueValue ? Math.round(Number(revenueValue) * unitFactor) : NaN;

  const loadCompanies = useCallback(async () => {
    setListError("");
    try {
      const res = await fetch("/api/companies?limit=100");
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setCompanies(Array.isArray(data) ? data : data.items ?? []);
    } catch (err) {
      console.error("load companies error:", err);
      setListError("등록된 기업을 불러오지 못했습니다.");
    }
  }, []);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  const resetForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setRevenueValue("");
    setRevenueUnit("억");
    setCertKeys({});
    setCertOther("");
  };

  const startEdit = (c: Company) => {
    setEditingId(c.id);
    setMessage("");
    setError("");
    setForm({
      name: c.name ?? "",
      founded_date: (c.founded_date ?? "").slice(0, 10),
      region: c.region ?? "",
      industry: c.industry ?? "",
      employee_count: String(c.employee_count ?? ""),
      ceo_birth_date: (c.ceo_birth_date ?? "").slice(0, 10),
    });
    const rev = revenueToUnit(c.revenue ?? 0);
    setRevenueValue(rev.value);
    setRevenueUnit(rev.unit);
    const certState = certsToState(c.certifications);
    setCertKeys(certState.keys);
    setCertOther(certState.other);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const toggleCert = (key: string) =>
    setCertKeys((prev) => ({ ...prev, [key]: !prev[key] }));

  const buildCertifications = (): Record<string, unknown> | null => {
    const dict: Record<string, unknown> = {};
    Object.entries(certKeys).forEach(([k, v]) => {
      if (v) dict[k] = true;
    });
    if (certOther.trim()) dict.note = certOther.trim();
    return Object.keys(dict).length ? dict : null;
  };

  const validateForm = (): string => {
    if (!form.name.trim()) return "기업명은 필수입니다.";
    if (!form.founded_date) return "설립일은 필수입니다.";
    if (form.founded_date > today) return "설립일은 미래일 수 없습니다.";
    if (!revenueValue || Number.isNaN(revenueWon) || revenueWon <= 0)
      return "매출을 올바르게 입력하세요.";
    if (!form.region) return "지역을 선택하세요.";
    if (!form.industry.trim()) return "업종은 필수입니다.";
    if (form.employee_count === "" || Number(form.employee_count) < 0)
      return "직원 수를 올바르게 입력하세요.";
    if (!form.ceo_birth_date) return "대표자 생년월일은 필수입니다.";
    if (form.ceo_birth_date > today) return "대표자 생년월일은 미래일 수 없습니다.";
    return "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage("");
    setError("");

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      setLoading(true);

      const payload = {
        name: form.name,
        founded_date: form.founded_date,
        revenue: revenueWon,
        region: form.region,
        industry: form.industry,
        employee_count: Number(form.employee_count),
        ceo_birth_date: form.ceo_birth_date,
        certifications: buildCertifications(),
      };

      const url = editingId ? `/api/companies/${editingId}` : "/api/companies";
      const response = await fetch(url, {
        method: editingId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const text = await response.text();
        console.error("company save error:", text);
        throw new Error(text);
      }

      setMessage(
        editingId
          ? "기업 정보가 수정되었습니다."
          : "기업 프로필이 등록되었습니다. 매칭 대시보드에서 결과를 확인하세요."
      );
      resetForm();
      loadCompanies();
    } catch (err) {
      console.error(err);
      const detail = err instanceof Error ? err.message : "";
      setError(
        detail
          ? `저장에 실패했습니다 (${detail.slice(0, 160)})`
          : "문제가 발생했습니다. 다시 시도해주세요."
      );
    } finally {
      setLoading(false);
    }
  };

  const labelCls = "mb-2 block text-sm font-medium text-gray-700";
  const inputCls = "w-full rounded-lg border px-4 py-3";
  const hintCls = "mt-1 text-xs text-gray-400";

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <div className="mx-auto max-w-3xl space-y-6">
        {/* 등록된 기업 목록 */}
        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">등록된 기업</h2>
            <Link href="/matching" className="text-sm text-blue-600 hover:underline">
              매칭 대시보드 →
            </Link>
          </div>
          {listError && <p className="text-sm text-red-500">{listError}</p>}
          {!listError && companies.length === 0 && (
            <p className="text-sm text-gray-400">
              아직 등록된 기업이 없습니다. 아래에서 첫 기업을 등록하세요.
            </p>
          )}
          <ul className="divide-y">
            {companies.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-gray-900">{c.name}</p>
                  <p className="truncate text-xs text-gray-500">
                    {c.region} · {c.industry} · 직원 {c.employee_count}명 · 인증{" "}
                    {certSummary(c.certifications)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => startEdit(c)}
                  className="shrink-0 rounded-lg border px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                >
                  수정
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* 입력 / 수정 폼 */}
        <section className="rounded-2xl border bg-white p-8 shadow-sm">
          <div className="mb-1 flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-900">
              {editingId ? "기업 정보 수정" : "기업 프로필 입력"}
            </h1>
            {editingId && (
              <button
                type="button"
                onClick={resetForm}
                className="text-sm text-gray-500 hover:underline"
              >
                취소 (새 기업 등록)
              </button>
            )}
          </div>
          <p className="mb-6 text-sm text-gray-500">
            입력한 값으로 공고 자격요건을 자동 매칭합니다. 표준 항목으로 입력해야 매칭이 정확합니다.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className={labelCls}>기업명</label>
              <input
                type="text"
                name="name"
                value={form.name}
                onChange={handleChange}
                className={inputCls}
                placeholder="기업명을 입력하세요"
              />
              <p className={hintCls}>식별용 — 매칭 점수에는 사용되지 않습니다.</p>
            </div>

            <div>
              <label className={labelCls}>설립일</label>
              <input
                type="date"
                name="founded_date"
                value={form.founded_date}
                onChange={handleChange}
                max={today}
                className={inputCls}
              />
              <p className={hintCls}>
                법인설립등기일 또는 사업자등록일 기준 — 업력(3년/7년 등) 산정에 사용됩니다.
              </p>
            </div>

            <div>
              <label className={labelCls}>매출 (직전연도 기준)</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={0}
                  value={revenueValue}
                  onChange={(e) => setRevenueValue(e.target.value)}
                  className={inputCls}
                  placeholder="예: 3"
                />
                <select
                  value={revenueUnit}
                  onChange={(e) => setRevenueUnit(e.target.value as RevenueUnit)}
                  className="rounded-lg border px-3 py-3"
                >
                  {REVENUE_UNITS.map((u) => (
                    <option key={u.key} value={u.key}>
                      {u.label}
                    </option>
                  ))}
                </select>
              </div>
              {revenueValue && !Number.isNaN(revenueWon) && (
                <p className={hintCls}>= {revenueWon.toLocaleString()}원</p>
              )}
            </div>

            <div>
              <label className={labelCls}>지역 (본사 소재 시도)</label>
              <select
                name="region"
                value={form.region}
                onChange={handleChange}
                className={inputCls}
              >
                <option value="">시/도를 선택하세요</option>
                {REGIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelCls}>업종</label>
              <input
                type="text"
                name="industry"
                value={form.industry}
                onChange={handleChange}
                className={inputCls}
                placeholder="표준산업분류에서 선택하거나 입력"
                list="industry-suggestions"
              />
              <datalist id="industry-suggestions">
                {INDUSTRY_SUGGESTIONS.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
              <p className={hintCls}>
                표준 분류 용어로 입력하면 공고 업종 요건과 더 정확히 매칭됩니다.
              </p>
            </div>

            <div>
              <label className={labelCls}>직원 수 (상시근로자)</label>
              <input
                type="number"
                name="employee_count"
                min={0}
                value={form.employee_count}
                onChange={handleChange}
                className={inputCls}
                placeholder="예: 10"
              />
            </div>

            <div>
              <label className={labelCls}>대표자 생년월일</label>
              <input
                type="date"
                name="ceo_birth_date"
                value={form.ceo_birth_date}
                onChange={handleChange}
                max={today}
                className={inputCls}
              />
              <p className={hintCls}>청년창업 등 대표자 나이 요건 산정에 사용됩니다.</p>
            </div>

            <div>
              <label className={labelCls}>보유 인증</label>
              <div className="grid grid-cols-2 gap-2 rounded-lg border p-3 sm:grid-cols-3">
                {CERT_OPTIONS.map((c) => (
                  <label
                    key={c.key}
                    className="flex cursor-pointer items-center gap-2 text-sm text-gray-700"
                  >
                    <input
                      type="checkbox"
                      checked={!!certKeys[c.key]}
                      onChange={() => toggleCert(c.key)}
                      className="h-4 w-4"
                    />
                    {c.label}
                  </label>
                ))}
              </div>
              <input
                type="text"
                value={certOther}
                onChange={(e) => setCertOther(e.target.value)}
                className={`${inputCls} mt-2`}
                placeholder="기타 인증 (자유 입력)"
              />
              <p className={hintCls}>
                해당하는 인증을 선택하세요. 목록에 없으면 기타에 입력합니다.
              </p>
            </div>

            {error && <p className="text-sm text-red-500">{error}</p>}
            {message && <p className="text-sm text-green-600">{message}</p>}

            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-blue-600 px-6 py-3 text-white hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? "저장 중..." : editingId ? "수정 저장" : "기업 등록"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
