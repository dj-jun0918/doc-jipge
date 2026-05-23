"use client";

import { useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";

// unpkg CDN을 통해 안전하게 pdf.worker를 로드합니다.
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// CSS Styles (react-pdf 기본 텍스트 레이어 및 어노테이션 레이어 깨짐 방지)
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

interface PdfViewerProps {
  pdfUrl: string;
  highlightPage?: number | null;
  evidenceText?: string | null;
}

export default function PdfViewer({ pdfUrl, highlightPage, evidenceText }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // local_path나 외부 경로에 따른 URL Fallback 매핑
  const getResolvedPdfUrl = (url: string): string => {
    if (!url) return "";

    // 1. 만약 DB의 물리적 절대 경로(c:\Users\...) 형태로 제공되는 경우
    // 프론트엔드 static 폴더인 /ground_truth/ann_XXX/ 형식으로 Fallback 처리합니다.
    if (url.includes("ground_truth") || url.includes("evaluation")) {
      const match = url.match(/ann_\d+/);
      if (match) {
        const annId = match[0]; // e.g. ann_021
        return `/ground_truth/${annId}/${annId}.pdf`;
      }
    }

    // 2. 외부 원격 PDF url의 경우 브라우저 CORS 회피를 위해 PDF Proxy API를 경유시킵니다.
    if (url.startsWith("http://") || url.startsWith("https://")) {
      return `/api/pdf-proxy?url=${encodeURIComponent(url)}`;
    }

    return url;
  };

  const resolvedUrl = getResolvedPdfUrl(pdfUrl);

  // highlightPage가 변할 때 해당 페이지로 자동 점프
  useEffect(() => {
    if (highlightPage && highlightPage > 0) {
      setPageNumber(highlightPage);
    }
  }, [highlightPage]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setLoading(false);
    setError(null);
  }

  function onDocumentLoadError(err: Error) {
    console.error("PDF load error:", err);
    setError("PDF 문서를 불러올 수 없습니다. 경로가 올바르지 않거나 손상된 파일일 수 있습니다.");
    setLoading(false);
  }

  const changePage = (offset: number) => {
    setPageNumber((prevPageNumber) => {
      const target = prevPageNumber + offset;
      if (numPages && target >= 1 && target <= numPages) {
        return target;
      }
      return prevPageNumber;
    });
  };

  return (
    <div className="flex flex-col h-full bg-gray-100 rounded-2xl overflow-hidden border shadow-sm">
      {/* 툴바 컨트롤러 */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between gap-4 text-sm font-semibold shadow-sm">
        <div className="flex items-center gap-2">
          <button
            onClick={() => changePage(-1)}
            disabled={pageNumber <= 1 || loading}
            className="p-2 rounded-lg hover:bg-gray-100 border text-gray-700 disabled:opacity-50 disabled:hover:bg-transparent transition cursor-pointer"
          >
            이전
          </button>
          <span className="text-gray-700">
            {loading ? "..." : `${pageNumber} / ${numPages || 1}`}
          </span>
          <button
            onClick={() => changePage(1)}
            disabled={(numPages !== null && pageNumber >= numPages) || loading}
            className="p-2 rounded-lg hover:bg-gray-100 border text-gray-700 disabled:opacity-50 disabled:hover:bg-transparent transition cursor-pointer"
          >
            다음
          </button>
        </div>

        {evidenceText && (
          <div className="hidden md:block max-w-[50%] truncate text-xs text-blue-600 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-full font-medium animate-pulse">
            🔍 근거: "{evidenceText}"
          </div>
        )}
      </div>

      {/* PDF 본문 영역 */}
      <div className="flex-1 overflow-auto p-6 flex justify-center items-start min-h-[450px]">
        {loading && (
          <div className="my-auto flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
            <p className="text-gray-500 text-sm">PDF 뷰어를 로드하는 중...</p>
          </div>
        )}

        {error && (
          <div className="my-auto text-center px-6 py-10 max-w-md bg-white border border-red-200 rounded-2xl shadow-sm">
            <svg className="mx-auto h-12 w-12 text-red-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-gray-900 font-semibold mb-2">{error}</p>
            <p className="text-gray-500 text-xs leading-relaxed">
              만약 로컬 PDF 파일 분석 환경이라면, <code className="bg-gray-100 px-1.5 py-0.5 rounded text-red-600">evaluation/ground_truth</code> 폴더의 PDF 파일들이 프론트엔드의 <code className="bg-gray-100 px-1.5 py-0.5 rounded">public/ground_truth/</code> 폴더 하위로 복사되었는지 확인해 주세요.
            </p>
          </div>
        )}

        {!error && resolvedUrl && (
          <div className="bg-white p-4 rounded-xl border shadow-sm max-w-full overflow-hidden">
            <Document
              file={resolvedUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading=""
            >
              <Page
                pageNumber={pageNumber}
                width={650}
                loading=""
                renderAnnotationLayer={false}
                renderTextLayer={true}
              />
            </Document>
          </div>
        )}

        {!resolvedUrl && !loading && (
          <div className="my-auto text-gray-400 text-sm">
            조회할 공고 PDF 경로 정보가 존재하지 않습니다.
          </div>
        )}
      </div>
    </div>
  );
}
