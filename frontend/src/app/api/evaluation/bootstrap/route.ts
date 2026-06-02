import { NextResponse } from "next/server";

export async function GET() {
  // 사용자가 정의한 BootstrapResponse 명세 반영 Mock 데이터
  const data = {
    precision: {
      point_estimate: 0.885,
      ci_low: 0.832,
      ci_high: 0.927
    },
    recall: {
      point_estimate: 0.852,
      ci_low: 0.798,
      ci_high: 0.899
    },
    f1: {
      point_estimate: 0.868,
      ci_low: 0.817,
      ci_high: 0.911
    },
    resampling_iterations: 1000
  };

  return NextResponse.json(data);
}
