import { NextResponse } from "next/server";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;

    const backendUrl = new URL("http://localhost:8000/api/announcements");

    searchParams.forEach((value, key) => {
      backendUrl.searchParams.append(key, value);
    });

    const response = await fetch(backendUrl.toString(), {
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