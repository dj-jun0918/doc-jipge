import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  try {
    // 백엔드 기본 limit=20이라 쿼리를 전달하지 않으면 21번째 이후 기업이 조용히 누락됨
    const backendUrl = new URL(`${BACKEND_URL}/api/companies/`);
    new URL(request.url).searchParams.forEach((value, key) => {
      backendUrl.searchParams.append(key, value);
    });
    if (!backendUrl.searchParams.has("limit")) {
      backendUrl.searchParams.set("limit", "100");
    }

    const response = await fetch(backendUrl.toString(), {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      next: { revalidate: 0 } // 캐시 무효화
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data, { status: 200 });
    }

    const errorData = await response.json().catch(() => ({}));
    return NextResponse.json(
      { message: errorData.detail || "백엔드 서버 응답 실패" },
      { status: response.status }
    );
  } catch (error) {
    console.error("GET /api/companies route handler error:", error);
    return NextResponse.json(
      { message: "백엔드 서버 연결에 실패했습니다." },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await fetch(`${BACKEND_URL}/api/companies/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("POST /api/companies route handler error:", error);
    return NextResponse.json(
      { message: "서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}