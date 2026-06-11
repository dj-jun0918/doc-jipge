import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;

    const backendUrl = new URL(`${BACKEND_URL}/api/pipeline/jobs`);

    searchParams.forEach((value, key) => {
      backendUrl.searchParams.append(key, value);
    });

    const response = await fetch(backendUrl.toString(), {
      cache: "no-store",
    });

    // 비JSON 응답(프록시 에러 페이지 등)이 와도 백엔드 상태코드를 보존
    const data = await response.json().catch(() => ({}));

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("GET /api/pipeline/jobs route handler error:", error);
    return NextResponse.json(
      { message: "파이프라인 서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}
