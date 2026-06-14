// 공고 단위 적합도 버킷 배지 — 백엔드 derive_eligibility_bucket(matcher.py)과 1:1.
// 신청가능(green) / 조건확인(amber) / 자격미달(gray). 점수와 별개의 '결정적 미충족 유무' 범주.

export type EligibilityBucket = "신청가능" | "조건확인" | "자격미달";

const BUCKET_META: Record<EligibilityBucket, { dot: string; badge: string }> = {
  신청가능: { dot: "bg-green-500", badge: "bg-green-50 text-green-700 border-green-200" },
  조건확인: { dot: "bg-amber-500", badge: "bg-amber-50 text-amber-700 border-amber-200" },
  자격미달: { dot: "bg-gray-400", badge: "bg-gray-100 text-gray-500 border-gray-200" },
};

export function BucketBadge({ bucket }: { bucket: EligibilityBucket }) {
  const m = BUCKET_META[bucket];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${m.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {bucket}
    </span>
  );
}
