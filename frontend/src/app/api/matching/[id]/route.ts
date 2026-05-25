import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> | { id: string } }
) {
  try {
    const resolvedParams = await params;
    const { id } = resolvedParams;
    const { searchParams } = new URL(request.url);
    
    const announcementId = searchParams.get("announcement_id");
    const limit = searchParams.get("limit") || "50";

    let backendUrl = `${BACKEND_URL}/api/matching/${id}`;
    
    if (announcementId) {
      backendUrl = `${BACKEND_URL}/api/matching/${id}/${announcementId}`;
    } else {
      backendUrl = `${backendUrl}?limit=${limit}`;
    }

    const response = await fetch(backendUrl, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("GET /api/matching/[id] route handler error:", error);
    return NextResponse.json(
      { message: "서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}

