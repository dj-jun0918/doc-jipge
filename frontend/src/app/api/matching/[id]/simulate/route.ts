import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> | { id: string } }
) {
  try {
    const resolvedParams = await params;
    const { id } = resolvedParams;
    const body = await request.json();

    const backendUrl = `${BACKEND_URL}/api/matching/${id}/simulate`;

    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("POST /api/matching/[id]/simulate route handler error:", error);
    return NextResponse.json(
      { message: "시뮬레이션 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}
