import { NextResponse } from "next/server";

export async function GET() {
  // 사용자가 정의한 ErrorAnalysisResponse 명세 반영 Mock 데이터
  const data = {
    total_errors: 28,
    patterns: [
      {
        pattern_name: "누락 (False Negative)",
        count: 15,
        ratio: 0.536,
        description: "공고문 본문 내의 우대사항 또는 예외 조건 텍스트를 파이프라인이 누락하여 추출하지 못한 오류",
        examples: [
          {
            announcement_id: "ann_005",
            title: "2026년 청년창업지원사업 공고",
            field_name: "age",
            ground_truth: { value: 39, operator: "이하" },
            prediction: null
          },
          {
            announcement_id: "ann_012",
            title: "글로벌 강소기업 육성사업 모집",
            field_name: "certification",
            ground_truth: { cert_keys: ["GLOBAL_CHAMPION"] },
            prediction: null
          }
        ]
      },
      {
        pattern_name: "과탐지 (False Positive)",
        count: 8,
        ratio: 0.286,
        description: "단순 설명 텍스트나 예시를 실제 필수 자격요건으로 과장 해석하여 불필요하게 추출한 오류",
        examples: [
          {
            announcement_id: "ann_008",
            title: "소상공인 스마트 설비 보급사업",
            field_name: "constraint",
            ground_truth: null,
            prediction: { value: "폐업 이력이 없는 자", operator: "equal" }
          }
        ]
      },
      {
        pattern_name: "값/범위 오인식 (Value Mismatch)",
        count: 5,
        ratio: 0.178,
        description: "자격조건은 식별하였으나 연산자(이상/초과/이하) 또는 수치를 잘못 파싱한 오류",
        examples: [
          {
            announcement_id: "ann_019",
            title: "스타트업 특허 디딤돌 지원사업",
            field_name: "company_scale",
            ground_truth: { value: 7, operator: "이하", unit: "년" },
            prediction: { value: 7, operator: "미만", unit: "년" }
          }
        ]
      }
    ]
  };

  return NextResponse.json(data);
}
