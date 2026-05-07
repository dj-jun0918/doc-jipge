"use client";

import { useEffect, useState } from "react";
import { isBookmarked, toggleBookmark } from "@/lib/bookmark";

interface BookmarkButtonProps {
  id: string | number;
  className?: string;
  size?: number;
}

export default function BookmarkButton({ id, className = "", size = 24 }: BookmarkButtonProps) {
  const [bookmarked, setBookmarked] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setBookmarked(isBookmarked(id));
    setMounted(true);
  }, [id]);

  const handleToggle = (e: React.MouseEvent) => {
    e.preventDefault(); // 링크 이동 방지
    e.stopPropagation(); // 이벤트 버블링 방지
    
    const newState = toggleBookmark(id);
    setBookmarked(newState);
  };

  if (!mounted) {
    // Hydration 불일치를 막기 위해 마운트 전에는 빈 공간 렌더링
    return <div style={{ width: size, height: size }} className={className} />;
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={`focus:outline-none transition-colors ${className}`}
      aria-label={bookmarked ? "북마크 해제" : "북마크 추가"}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill={bookmarked ? "#EAB308" : "none"} // Tailwind yellow-500
        stroke={bookmarked ? "#EAB308" : "currentColor"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={bookmarked ? "text-yellow-500" : "text-gray-400 hover:text-gray-600"}
      >
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
      </svg>
    </button>
  );
}
