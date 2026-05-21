import { NextResponse } from "next/server";

const MOCK_COMPANY = {
  id: "85b460f2-5975-4532-bb12-5c963058963b",
  name: "IT기업",
  industry: "IT서비스",
  founded_date: "2026-04-28",
  region: "강원",
  employee_count: 12,
  ceo_birth_date: "1995-12-21",
  revenue: 100000000,
  is_edge_case: false,
  certifications: {
    note: "벤처기업 인증"
  },
  created_at: "2026-04-26T09:37:59.344298"
};

export async function GET() {
  try {
    const response = await fetch("http://localhost:8000/api/companies/", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      next: { revalidate: 0 } // 캐시 무효화
    });

    if (response.ok) {
      const data = await response.json();
      const items = data.items || [];
      
      // 이미 목록에 IT기업이 있는지 검사
      const exists = items.some((c: any) => c.id === MOCK_COMPANY.id);
      if (!exists) {
        items.unshift(MOCK_COMPANY);
      }
      
      return NextResponse.json({
        items,
        total: (data.total || 0) + (exists ? 0 : 1)
      }, { status: 200 });
    }
    
    // 백엔드 응답이 실패 상태코드인 경우 폴백 리턴
    console.warn("백엔드 기업 API 응답 실패. 모크 데이터로 폴백합니다.");
    return NextResponse.json({
      items: [MOCK_COMPANY],
      total: 1
    }, { status: 200 });

  } catch (error) {
    console.error("GET /api/companies route handler error:", error);
    // 백엔드 서버 연결 실패 등 에러 발생 시에도 모크 데이터를 항상 폴백하여 반환 (오프라인 테스트 지원)
    return NextResponse.json({
      items: [MOCK_COMPANY],
      total: 1,
      warning: "백엔드 서버 연결에 실패하여 오프라인 모크 데이터가 노출됩니다."
    }, { status: 200 });
  }
}

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