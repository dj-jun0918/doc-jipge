interface DdayBadgeProps {
  endDate?: string;
}

function calculateDday(endDate?: string) {
  if (!endDate) {
    return { label: "일정 미정", className: "bg-gray-100 text-gray-600" };
  }

  const today = new Date();
  const end = new Date(endDate);

  today.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);

  const diffTime = end.getTime() - today.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return { label: "마감", className: "bg-gray-200 text-gray-700" };
  }

  if (diffDays === 0) {
    return { label: "D-Day", className: "bg-red-100 text-red-700" };
  }

  if (diffDays <= 3) {
    return { label: `D-${diffDays}`, className: "bg-red-100 text-red-700" };
  }

  if (diffDays <= 7) {
    return { label: `D-${diffDays}`, className: "bg-orange-100 text-orange-700" };
  }

  return { label: `D-${diffDays}`, className: "bg-gray-100 text-gray-700" };
}

export default function DdayBadge({ endDate }: DdayBadgeProps) {
  const { label, className } = calculateDday(endDate);

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-medium ${className}`}
    >
      {label}
    </span>
  );
}