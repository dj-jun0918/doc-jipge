"use client";

import { useState } from "react";

interface RawTextDisplayProps {
  text: string;
}

export default function RawTextDisplay({ text }: RawTextDisplayProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  return (
    <div className="bg-gradient-to-br from-gray-50 to-white rounded-2xl p-6 border border-gray-150 shadow-sm relative group overflow-hidden">
      {/* Decorative background shape */}
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-blue-500/5 rounded-full pointer-events-none group-hover:scale-110 transition-transform duration-500" />
      
      <div className="flex items-center justify-between mb-4 border-b pb-3">
        <h4 className="text-sm font-bold text-gray-800 flex items-center gap-2">
          <span className="flex h-2.5 w-2.5 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500"></span>
          </span>
          텍스트 원문 근거
        </h4>

        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-600 hover:text-gray-900 transition shadow-sm cursor-pointer"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-green-600 font-bold">복사 완료!</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m-5 4h6m-6 4h6m-6 4h4" />
              </svg>
              <span>복사하기</span>
            </>
          )}
        </button>
      </div>

      <div className="relative pl-6 py-1">
        {/* Left vertical visual line */}
        <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-blue-500 to-indigo-500 rounded-full" />
        
        {/* Large Decorative Quote icon */}
        <span className="absolute -left-1 -top-3 text-4xl font-serif text-blue-500/10 pointer-events-none">
          “
        </span>

        <p className="text-sm text-gray-700 leading-relaxed font-medium whitespace-pre-wrap select-all">
          {text || "근거 텍스트 내용이 존재하지 않습니다."}
        </p>
      </div>
    </div>
  );
}
