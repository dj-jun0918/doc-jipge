import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;
    const id = searchParams.get("id");

    let backendUrlString = `${BACKEND_URL}/api/announcements`;

    if (id) {
      backendUrlString = `${BACKEND_URL}/api/announcements/${id}`;
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

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("GET /api/announcements route handler error:", error);
    return NextResponse.json(
      { message: "서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}