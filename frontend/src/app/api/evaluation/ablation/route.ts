import { NextResponse } from "next/server";

export async function GET() {
  // 사용자가 정의한 AblationResponse 명세 반영 Mock 데이터
  const data = {
    conditions: [
      {
        condition_id: "C1",
        name: "Rule Parser Baseline",
        components: ["rule_parser"],
        description: "정규표현식 및 하드코딩 룰 기반 파싱. 정밀도는 높으나 재현율이 극히 낮음.",
        metrics: { precision: 0.985, recall: 0.354, f1: 0.521 },
        cost_estimate_usd: 0.0
      },
      {
        condition_id: "C2",
        name: "Rule + Text LLM",
        components: ["rule_parser", "text_llm_extractor"],
        description: "본문 텍스트 추출에 LLM을 결합하여 정형 규칙이 놓친 자격 요건 식별.",
        metrics: { precision: 0.902, recall: 0.815, f1: 0.856 },
        cost_estimate_usd: 15.50
      },
      {
        condition_id: "C3",
        name: "Rule + Text + Vision LLM",
        components: ["rule_parser", "text_llm_extractor", "vision_llm_extractor"],
        description: "공고문 내 표 이미지나 외부 이미지 박스 내 자격요건까지 Vision LLM으로 다각화 파싱.",
        metrics: { precision: 0.885, recall: 0.852, f1: 0.868 },
        cost_estimate_usd: 41.05
      },
      {
        condition_id: "C4",
        name: "Hybrid Engine with Verifier",
        components: ["rule_parser", "text_llm_extractor", "vision_llm_extractor", "fact_verifier"],
        description: "모든 오추출 및 불일치 항목을 교차 검증하는 Verifier 모듈이 포함된 완성형 파이프라인.",
        metrics: { precision: 0.923, recall: 0.864, f1: 0.893 },
        cost_estimate_usd: 48.20
      }
    ]
  };

  return NextResponse.json(data);
}
