"use client";

import { useState } from "react";

interface CompanyFormData {
  name: string;
  founded_date: string;
  revenue: string;
  region: string;
  industry: string;
  employee_count: string;
  ceo_birth_date: string;
  certifications: string;
}

export default function CompaniesPage() {
  const [form, setForm] = useState<CompanyFormData>({
    name: "",
    founded_date: "",
    revenue: "",
    region: "",
    industry: "",
    employee_count: "",
    ceo_birth_date: "",
    certifications: "",
  });

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const validateForm = () => {
    if (!form.name.trim()) return "기업명은 필수입니다.";
    if (!form.founded_date) return "설립일은 필수입니다.";
    if (!form.revenue) return "매출은 필수입니다.";
    if (!form.region.trim()) return "지역은 필수입니다.";
    if (!form.industry.trim()) return "업종은 필수입니다.";
    if (!form.employee_count) return "직원 수는 필수입니다.";
    if (!form.ceo_birth_date) return "대표자 생년월일은 필수입니다.";
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
        revenue: Number(form.revenue),
        region: form.region,
        industry: form.industry,
        employee_count: Number(form.employee_count),
        ceo_birth_date: form.ceo_birth_date,
        certifications: form.certifications
          ? { note: form.certifications }
          : null,
      };

      const response = await fetch("api/companies", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const text = await response.text();
        console.error("company create error:", text);
        throw new Error("기업 등록에 실패했습니다.");
      }

      setMessage("기업 프로필이 등록되었습니다.");
      setForm({
        name: "",
        founded_date: "",
        revenue: "",
        region: "",
        industry: "",
        employee_count: "",
        ceo_birth_date: "",
        certifications: "",
      });
    } catch (err) {
      console.error(err);
      setError("문제가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-10">
      <section className="mx-auto max-w-3xl rounded-2xl border bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-3xl font-bold text-gray-900">
          기업 프로필 입력
        </h1>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              기업명
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
              placeholder="기업명을 입력하세요"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              설립일
            </label>
            <input
              type="date"
              name="founded_date"
              value={form.founded_date}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              매출
            </label>
            <input
              type="number"
              name="revenue"
              value={form.revenue}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
              placeholder="예: 100000000"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              지역
            </label>
            <input
              type="text"
              name="region"
              value={form.region}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
              placeholder="예: 서울"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              업종
            </label>
            <input
              type="text"
              name="industry"
              value={form.industry}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
              placeholder="예: IT 서비스"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              직원 수
            </label>
            <input
              type="number"
              name="employee_count"
              value={form.employee_count}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
              placeholder="예: 10"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              대표자 생년월일
            </label>
            <input
              type="date"
              name="ceo_birth_date"
              value={form.ceo_birth_date}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              인증 정보
            </label>
            <textarea
              name="certifications"
              value={form.certifications}
              onChange={handleChange}
              className="w-full rounded-lg border px-4 py-3"
              rows={4}
              placeholder="예: ISO9001, 벤처기업 인증"
            />
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}
          {message && <p className="text-sm text-green-600">{message}</p>}

          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-blue-600 px-6 py-3 text-white hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? "등록 중..." : "기업 등록"}
          </button>
        </form>
      </section>
    </main>
  );
}