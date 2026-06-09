import { NextResponse } from "next/server";

export async function GET() {
  // 사용자가 정의한 IaaResponse 명세 반영 Mock 데이터
  const data = {
    overall_kappa: 0.765,
    by_field: [
      { field_name: "age", kappa: 0.842, agreement_level: "거의 완전한 합의 (Almost Perfect)" },
      { field_name: "location", kappa: 0.889, agreement_level: "거의 완전한 합의 (Almost Perfect)" },
      { field_name: "company_scale", kappa: 0.723, agreement_level: "상당한 합의 (Substantial)" },
      { field_name: "is_small_business", kappa: 0.910, agreement_level: "거의 완전한 합의 (Almost Perfect)" },
      { field_name: "constraint", kappa: 0.584, agreement_level: "보통 수준의 합의 (Moderate)" },
      { field_name: "certification", kappa: 0.645, agreement_level: "상당한 합의 (Substantial)" }
    ],
    evaluated_count: 10
  };

  return NextResponse.json(data);
}
