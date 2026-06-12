"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";

// CDN 대신 로컬 정적 워커를 사용합니다 (오프라인/로컬 환경 대응).
// 워커 파일은 frontend/public/pdf.worker.min.mjs 경로에 위치해야 합니다.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

// CSS Styles (react-pdf 기본 텍스트 레이어 및 어노테이션 레이어 깨짐 방지)
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

interface EvidenceLocation {
  location_type: "pdf_page" | "hwpx_table" | "hwpx_paragraph" | "raw_text";
  page?: number;
  bbox?: [number, number, number, number];  // x0, y0, x1, y1 (PDF 좌표)
  table_index?: number;
  row?: number;
}

interface PdfViewerProps {
  pdfUrl: string;
  highlightPage?: number | null;
  evidenceText?: string | null;
  location?: EvidenceLocation | null;
}

export default function PdfViewer({ pdfUrl, highlightPage, evidenceText, location }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // 반응형 너비 추적을 위한 ResizeObserver 연동
  const [containerWidth, setContainerWidth] = useState<number>(650);
  const containerRef = useRef<HTMLDivElement>(null);
  // 로드된 PDF Page 정보를 보관하여 bbox 스케일 계산에 사용
  const [pdfPage, setPdfPage] = useState<any>(null);

  const [pdfDocument, setPdfDocument] = useState<any>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [highlightRanges, setHighlightRanges] = useState<any[]>([]);

  // 자가 치유(Self-healing) Fallback 상태
  const [currentPdfUrl, setCurrentPdfUrl] = useState<string>(pdfUrl);

  useEffect(() => {
    setCurrentPdfUrl(pdfUrl);
  }, [pdfUrl]);

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

  // 페이지 클램핑 헬퍼
  const clampPage = useCallback((page: number, maxPages: number | null) => {
    if (page < 1) return 1;
    if (maxPages && page > maxPages) return maxPages;
    return page;
  }, []);

  // highlightPage가 변할 때 또는 텍스트 검색을 통한 페이지 점프
  useEffect(() => {
    if (highlightPage && highlightPage > 0) {
      setPageNumber(clampPage(highlightPage, numPages));
      setSearchError(null);
    } else if (location?.page && location.page > 0) {
      setPageNumber(clampPage(location.page, numPages));
      setSearchError(null);
    } else if (pdfDocument && evidenceText) {
      let active = true;
      async function searchPdf() {
        setSearchError(null);
        const cleanTarget = evidenceText.replace(/\s+/g, "").toLowerCase();
        if (!cleanTarget) return;

        for (let i = 1; i <= pdfDocument.numPages; i++) {
          try {
            const page = await pdfDocument.getPage(i);
            const textContent = await page.getTextContent();
            if (!active) return;

            const pageText = textContent.items
              .map((item: any) => item.str)
              .join(" ");
            const cleanPageText = pageText.replace(/\s+/g, "").toLowerCase();

            if (cleanPageText.includes(cleanTarget)) {
              setPageNumber(clampPage(i, pdfDocument.numPages));
              return;
            }
          } catch (err) {
            console.error(`Error searching page ${i}:`, err);
          }
        }

        if (active) {
          setSearchError("원문에서 위치를 찾을 수 없습니다. 전체 PDF를 표시합니다.");
        }
      }

      searchPdf();
      return () => {
        active = false;
      };
    }
  }, [highlightPage, location, pdfDocument, evidenceText, numPages, clampPage]);

  // pdfUrl이 바뀌면 페이지 및 상태 초기화
  useEffect(() => {
    setPageNumber(1);
    setLoading(true);
    setError(null);
    setPdfPage(null);
    setPdfDocument(null);
    setSearchError(null);
    setHighlightRanges([]);
  }, [pdfUrl]);

  // 텍스트 하이라이트 범위 계산
  useEffect(() => {
    if (!pdfPage) {
      setHighlightRanges([]);
      return;
    }

    let active = true;
    async function computeHighlight() {
      try {
        const textContent = await pdfPage.getTextContent();
        if (!active) return;

        const items = textContent.items;
        let concatenated = "";
        const itemRanges = items.map((item: any) => {
          const start = concatenated.length;
          concatenated += item.str;
          const end = concatenated.length;
          return { start, end };
        });

        if (!evidenceText) {
          setHighlightRanges([]);
          return;
        }

        const cleanTarget = evidenceText.replace(/\s+/g, "").toLowerCase();
        if (!cleanTarget) {
          setHighlightRanges([]);
          return;
        }

        // Clean and map concatenated page text
        let cleanPage = "";
        const pageMap: number[] = [];
        for (let i = 0; i < concatenated.length; i++) {
          const char = concatenated[i];
          if (!/\s/.test(char)) {
            cleanPage += char.toLowerCase();
            pageMap.push(i);
          }
        }

        const matchStartInClean = cleanPage.indexOf(cleanTarget);
        if (matchStartInClean !== -1) {
          const matchEndInClean = matchStartInClean + cleanTarget.length - 1;
          const originalStart = pageMap[matchStartInClean];
          const originalEnd = pageMap[matchEndInClean] + 1; // exclusive

          const ranges: any[] = [];
          itemRanges.forEach((range: any, idx: number) => {
            const overlapStart = Math.max(range.start, originalStart);
            const overlapEnd = Math.min(range.end, originalEnd);
            if (overlapStart < overlapEnd) {
              ranges[idx] = {
                start: overlapStart - range.start,
                end: overlapEnd - range.start,
              };
            }
          });
          setHighlightRanges(ranges);
        } else {
          setHighlightRanges([]);
        }
      } catch (err) {
        console.error("Error computing text highlights:", err);
        setHighlightRanges([]);
      }
    }

    computeHighlight();
    return () => {
      active = false;
    };
  }, [pdfPage, evidenceText]);

  const textRenderer = useCallback(({ str, itemIndex }: { str: string; itemIndex: number }) => {
    const range = highlightRanges[itemIndex];
    if (range && range.start < range.end) {
      const before = str.slice(0, range.start);
      const match = str.slice(range.start, range.end);
      const after = str.slice(range.end);
      return (
        <span>
          {before}
          <mark className="bg-yellow-300 text-yellow-900 rounded-sm px-0.5 shadow-sm">{match}</mark>
          {after}
        </span>
      );
    }
    return str;
  }, [highlightRanges]);

  function onDocumentLoadSuccess(pdf: any) {
    setPdfDocument(pdf);
    setNumPages(pdf.numPages);
    setLoading(false);
    setError(null);
    setPageNumber((prev) => clampPage(prev, pdf.numPages));
  }

  function onDocumentLoadError(err: Error) {
    console.error("PDF load error:", err);
    setError("PDF 문서를 불러올 수 없습니다. 경로가 올바르지 않거나 손상된 파일일 수 있습니다.");
    setLoading(false);
  }

  const changePage = (offset: number) => {
    setPageNumber((prevPageNumber) => {
      const target = prevPageNumber + offset;
      return clampPage(target, numPages);
    });
  };

  return (
    <div className="flex flex-col h-full bg-gray-100 rounded-2xl overflow-hidden border shadow-sm">
      {/* 툴바 컨트롤러 */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between gap-4 text-sm font-semibold shadow-sm animate-fade-in">
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

        {searchError ? (
          <div className="hidden md:block max-w-[50%] truncate text-xs text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-full font-medium">
            ⚠️ {searchError}
          </div>
        ) : evidenceText ? (
          <div className="hidden md:block max-w-[50%] truncate text-xs text-blue-600 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-full font-medium">
            🔍 근거: &quot;{evidenceText}&quot;
          </div>
        ) : null}
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
          <div className="my-auto text-center px-6 py-10 max-w-md bg-white border border-red-200 rounded-2xl shadow-sm animate-fade-in">
            <svg className="mx-auto h-12 w-12 text-red-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-gray-900 font-semibold mb-2">{error}</p>
            <p className="text-gray-500 text-xs leading-relaxed">
              백엔드 서버가 실행 중인지, 첨부파일 ID가 올바른지 확인해 주세요.
            </p>
          </div>
        )}

        {!error && currentPdfUrl && (
          <div className="bg-white p-4 rounded-xl border shadow-sm max-w-full overflow-hidden">
            <Document
              file={currentPdfUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading=""
            >
              <div className="relative" style={{ width: containerWidth }}>
                <Page
                  pageNumber={pageNumber}
                  width={containerWidth}
                  loading=""
                  renderAnnotationLayer={false}
                  renderTextLayer={true}
                  onLoadSuccess={(page) => setPdfPage(page)}
                  customTextRenderer={textRenderer}
                />

                {/* 🎯 BBox 정밀 하이라이트 오버레이 (location bbox가 있을 때만 유지) */}
                {pdfPage && location?.bbox && (
                  (() => {
                    const bbox = location.bbox;
                    const scale = containerWidth / pdfPage.width;
                    const left = bbox[0] * scale;
                    const top = bbox[1] * scale;
                    const width = (bbox[2] - bbox[0]) * scale;
                    const height = (bbox[3] - bbox[1]) * scale;

                    return (
                      <div
                        className="absolute bg-yellow-400/35 border-2 border-yellow-500 rounded-sm pointer-events-none animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.5)]"
                        style={{
                          left: `${left}px`,
                          top: `${top}px`,
                          width: `${width}px`,
                          height: `${height}px`,
                          zIndex: 10,
                        }}
                      />
                    );
                  })()
                )}
              </div>
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
