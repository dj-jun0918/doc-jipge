import { NextResponse } from "next/server";

export async function GET() {
  // 사용자가 정의한 EvaluationMetricsResponse 명세 반영 Mock 데이터
  const data = {
    overall: {
      precision: 0.885,
      recall: 0.852,
      f1: 0.868
    },
    by_field: {
      age: { precision: 0.921, recall: 0.895, f1: 0.908 },
      location: { precision: 0.943, recall: 0.912, f1: 0.927 },
      company_scale: { precision: 0.875, recall: 0.844, f1: 0.859 },
      is_small_business: { precision: 0.950, recall: 0.931, f1: 0.940 },
      constraint: { precision: 0.812, recall: 0.785, f1: 0.798 },
      certification: { precision: 0.856, recall: 0.810, f1: 0.832 }
    },
    by_path: {
      rule_based: {
        precision: 0.985,
        recall: 0.712,
        f1: 0.827,
        count: 15,
        cost_usd: 0.0
      },
      text_llm: {
        precision: 0.892,
        recall: 0.861,
        f1: 0.876,
        count: 25,
        cost_usd: 12.45
      },
      vision_llm: {
        precision: 0.824,
        recall: 0.805,
        f1: 0.814,
        count: 10,
        cost_usd: 28.60
      }
    },
    total_cost_usd: 41.05
  };

  return NextResponse.json(data);
}
