import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    const response = await fetch("http://localhost:8000/api/companies", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("POST /api/companies route handler error:", error);
    return NextResponse.json(
      { message: "서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}