"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";

// CDN 대신 로컬 정적 워커를 사용합니다 (오프라인/로컬 환경 대응).
// 워커 파일은 frontend/public/pdf.worker.min.mjs 경로에 위치해야 합니다.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

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
  // 반응형 너비 추적을 위한 ResizeObserver 연동
  const [containerWidth, setContainerWidth] = useState<number>(650);
  const containerRef = useRef<HTMLDivElement>(null);

  // ResizeObserver로 컨테이너 너비 동적 감지 (반응형 PDF 렌더링)
  const observeResize = useCallback(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        // 좌우 패딩(32px) 및 최소/최대 너비 제한 적용
        const usableWidth = Math.min(Math.max(width - 32, 300), 900);
        setContainerWidth(usableWidth);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const cleanup = observeResize();
    return cleanup;
  }, [observeResize]);

  // highlightPage가 변할 때 해당 페이지로 자동 점프
  useEffect(() => {
    if (highlightPage && highlightPage > 0) {
      setPageNumber(highlightPage);
    }
  }, [highlightPage]);

  // pdfUrl이 바뀌면 페이지 및 상태 초기화
  useEffect(() => {
    setPageNumber(1);
    setLoading(true);
    setError(null);
  }, [pdfUrl]);

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
          <div className="hidden md:block max-w-[50%] truncate text-xs text-blue-600 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-full font-medium">
            🔍 근거: &quot;{evidenceText}&quot;
          </div>
        )}
      </div>

      {/* PDF 본문 영역 (반응형 너비 추적) */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-4 flex justify-center items-start min-h-[450px]"
      >
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
              백엔드 서버가 실행 중인지, 첨부파일 ID가 올바른지 확인해 주세요.
            </p>
          </div>
        )}

        {!error && pdfUrl && (
          <div className="bg-white p-4 rounded-xl border shadow-sm max-w-full overflow-hidden">
            <Document
              file={pdfUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading=""
            >
              <Page
                pageNumber={pageNumber}
                width={containerWidth}
                loading=""
                renderAnnotationLayer={false}
                renderTextLayer={true}
              />
            </Document>
          </div>
        )}

        {!pdfUrl && !loading && (
          <div className="my-auto text-gray-400 text-sm">
            조회할 공고 PDF 경로 정보가 존재하지 않습니다.
          </div>
        )}
      </div>
    </div>
  );
}
