import { NextResponse } from "next/server";

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

    // 💡 테스트 기업 ID(85b460f2-5975-4532-bb12-5c963058963b) 매칭 데이터 모킹 처리
    if (id === "85b460f2-5975-4532-bb12-5c963058963b") {
      const mockAnnId = "99999999-9999-9999-9999-999999999999";
      
      // A. 특정 공고별 상세 매칭 결과 요청인 경우
      if (announcementId === mockAnnId || request.url.includes(mockAnnId)) {
        return NextResponse.json({
          company_id: id,
          announcement_id: mockAnnId,
          items: [
            {
              field_name: "업력",
              status: "충족",
              company_value: "2026-04-28 (설립 23일)",
              requirement_value: "창업 3년 미만 초기 기업",
              evidence: {
                page: 2,
                text: "본 사업은 강원도 내 창업 3년 미만의 초기 기업을 대상으로 우수한 기술력을 지닌 유망 기업을 선발합니다."
              },
              processing_path: "기업 설립일(2026-04-28) 기준 업력 3년 미만 조건 충족"
            },
            {
              field_name: "지역",
              status: "충족",
              company_value: "강원",
              requirement_value: "강원도 지역 내에 본점 또는 지점을 둔 기업",
              evidence: {
                page: 1,
                text: "지원 대상은 공고일 기준 강원도 내에 소재지(본점 또는 지점)를 둔 중소기업으로 제한합니다."
              },
              processing_path: "기업 소재지(강원) 일치로 지역 조건 충족"
            },
            {
              field_name: "대표자 연령",
              status: "충족",
              company_value: "1995-12-21 (만 30세)",
              requirement_value: "대표자가 신청일 기준 만 39세 이하의 청년에 해당",
              evidence: {
                page: 3,
                text: "청년 창업 활성화를 위해 대표자가 만 39세 이하인 청년 창업 기업에 대해 가점 또는 전용 트랙으로 지원합니다."
              },
              processing_path: "대표 생년월일(1995-12-21) 기준 만 30세 청년 요건 충족"
            },
            {
              field_name: "업종",
              status: "충족",
              company_value: "IT서비스",
              requirement_value: "정보통신(IT), 소프트웨어 및 컴퓨터 서비스업 관련 업종",
              evidence: {
                page: 1,
                text: "대상 분야: IT 서비스, 컴퓨터 프로그래밍, 정보통신 및 디지털 신기술 융합 산업 분야"
              },
              processing_path: "업종(IT서비스) 일치로 대상 분야 요건 만족"
            },
            {
              field_name: "종업원 수",
              status: "충족",
              company_value: "12명",
              requirement_value: "상시 근로자 5인 이상 50인 이하",
              evidence: {
                page: 4,
                text: "신청 가능 대상은 상시 근로자 5인 이상을 고용하고 있는 소기업 및 중소기업입니다."
              },
              processing_path: "상시 근로자 수(12명)가 5인 이상 조건 충족"
            },
            {
              field_name: "매출액",
              status: "충족",
              company_value: "100,000,000원 (1억 원)",
              requirement_value: "최근 사업연도 매출액 5억 원 이하",
              evidence: {
                page: 2,
                text: "지원 규모 및 선발을 위해 연간 매출액이 5억 원 이하의 마이크로 IT 기업군을 우대 지원합니다."
              },
              processing_path: "직전 연도 매출액(1억 원)이 5억 원 이하 조건 만족"
            },
            {
              field_name: "특허 등록 여부",
              status: "미충족",
              company_value: "정보 없음 (특허 미보유)",
              requirement_value: "신청일 기준 본사 명의의 등록 완료된 특허 1건 이상 보유",
              evidence: {
                page: 6,
                text: "기술성 검증을 위해 접수 마감일까지 등록이 완료된 특허 지식재산권을 최소 1건 이상 보유 및 소유하고 있어야 합니다."
              },
              processing_path: "기업 프로필 상 등록된 특허 지식재산권 정보가 조회되지 않아 미충족 판정"
            },
            {
              field_name: "우대 가점 (벤처기업)",
              status: "확인필요",
              company_value: "벤처기업 인증",
              requirement_value: "유효한 벤처기업 확인서 보유 기업",
              evidence: {
                page: 5,
                text: "우대 사항: 유효한 벤처기업 확인서 사본을 제출한 기업에게 서류평가 시 가점 5점을 추가 부여합니다."
              },
              processing_path: "기업 프로필에 벤처기업 인증 정보가 명시되어 있으나, 유효기간 및 실제 사본 업로드를 통한 검증이 요구됩니다."
            }
          ],
          stats: {
            "충족": 6,
            "미충족": 1,
            "확인필요": 1,
            "해당없음": 0
          },
          matched_at: "2026-05-21T09:37:59.344Z"
        }, { status: 200 });
      }

      // B. 기업의 전체 매칭 목록 요청인 경우 (대시보드 리스트 및 좌측 사이드바)
      return NextResponse.json({
        company_id: id,
        items: [
          {
            announcement_id: mockAnnId,
            title: "2026 강원 청년창업 및 IT기업 도약 패키지 지원사업",
            match_score: 0.857, // 7개 중 충족 6개 (확인필요 제외하고 계산 시 충족 6 / 전체 7 = 0.857)
            fulfilled_count: 6,
            total_fields: 8
          }
        ],
        total: 1
      }, { status: 200 });
    }

    let backendUrl = `http://localhost:8000/api/matching/${id}`;
    
    if (announcementId) {
      backendUrl = `http://localhost:8000/api/matching/${id}/${announcementId}`;
    } else {
      backendUrl = `${backendUrl}?limit=${limit}`;
    }

    const response = await fetch(backendUrl, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("GET /api/matching/[id] route handler error:", error);
    return NextResponse.json(
      { message: "서버 요청 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}
