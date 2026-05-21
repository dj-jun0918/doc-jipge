import { NextResponse } from "next/server";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;
    const id = searchParams.get("id");

    // 💡 테스트 공고 ID(99999999-9999-9999-9999-999999999999) 메타데이터 모킹 처리
    if (id === "99999999-9999-9999-9999-999999999999") {
      return NextResponse.json({
        id: "99999999-9999-9999-9999-999999999999",
        title: "2026 강원 청년창업 및 IT기업 도약 패키지 지원사업",
        source: "kstartup",
        source_id: "MOCK-2026-GW-IT",
        organization: "강원창조경제혁신센터",
        executor: "강원테크노파크",
        period_start: "2026-05-01",
        period_end: "2026-06-30",
        target_text: "강원도 내 창업 3년 미만의 청년 창업 IT 서비스 기업 대상 패키지 지원",
        exclusion_text: "금융 및 사행성 업종",
        category: "창업지원",
        region: "강원",
        detail_url: "https://example.com",
        extraction_status: "completed",
        converted_pdf_path: "/mock_announcement.pdf", // frontend/public/mock_announcement.pdf 로딩
        created_at: "2026-04-26T09:37:59.344Z"
      }, { status: 200 });
    }

    let backendUrlString = "http://localhost:8000/api/announcements";

    if (id) {
      backendUrlString = `http://localhost:8000/api/announcements/${id}`;
    } else {
      const backendUrl = new URL(backendUrlString);
      searchParams.forEach((value, key) => {
        backendUrl.searchParams.append(key, value);
      });
      backendUrlString = backendUrl.toString();
    }

    const response = await fetch(backendUrlString, {
      cache: "no-store",
    });

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("GET /api/announcements route handler error:", error);
    return NextResponse.json(
      { message: "서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}