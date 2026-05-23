"""Precision/Recall/F1 측정 및 분석 리포트 생성 스크립트.

Ground Truth (ann_001~025)와 hybrid_engine.extract_eligibility 결과를 비교하여
필드별, 처리 경로별 메트릭 측정 및 마크다운 리포트를 자동 생성합니다.
"""

import asyncio
import glob
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 프로젝트 루트를 sys.path에 추가하여 app 패키지 임포트 가능하도록 설정
import sys
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.database import SessionLocal
from app.models.announcement import Announcement
from app.extractor import hybrid_engine
from app.schemas.eligibility import AnnouncementEligibility

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("evaluation.measure")

# 표준 7종 필드 정의
STANDARD_FIELDS = {"업력", "매출", "지역", "나이", "종업원 수", "업종", "인증"}


def _normalize(text: Any) -> str:
    """텍스트 정규화.

    - 한글 자모 분리 해결을 위해 NFC 정규화 적용 (Mac OS NFD 대응)
    - 대소문자 변환, 앞뒤 및 중복 공백 제거
    - 마크다운 표 깨짐 방지를 위해 파이프(|) 기호 이스케이프
    """
    if text is None:
        return ""
    text = str(text)
    text = unicodedata.normalize("NFC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    # 마크다운 파이프 기호 이스케이프
    text = text.replace("|", "\\|")
    return text


def load_ground_truth() -> List[Dict[str, Any]]:
    """evaluation/ground_truth/ann_* 디렉토리에서 모든 ground_truth.json 로드."""
    gt_list = []
    gt_dir = Path(project_root) / "evaluation" / "ground_truth"
    gt_files = sorted(gt_dir.glob("ann_*/ground_truth.json"))

    if not gt_files:
        logger.warning(f"Ground Truth 파일을 찾을 수 없습니다: {gt_dir}/ann_*/ground_truth.json")
        return []

    for path in gt_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 한글 NFD 대응 정규화
            data["title"] = _normalize(data.get("title", ""))
            
            normalized_fields = []
            for field in data.get("fields", []):
                field_name = unicodedata.normalize("NFC", field.get("field_name", ""))
                normalized_fields.append({
                    "field_name": field_name,
                    "condition": _normalize(field.get("condition", "")),
                    "evidence": unicodedata.normalize("NFC", field.get("evidence", "")),
                    "evidence_source": unicodedata.normalize("NFC", field.get("evidence_source", ""))
                })
            data["fields"] = normalized_fields
            
            normalized_exclusions = []
            for excl in data.get("exclusions", []):
                normalized_exclusions.append(unicodedata.normalize("NFC", excl))
            data["exclusions"] = normalized_exclusions

            gt_list.append(data)
            logger.info(f"Ground Truth 로드 완료: {data.get('announcement_id')} ({len(normalized_fields)} fields)")
        except Exception as e:
            logger.error(f"Ground Truth 로드 실패 ({path}): {e}")

    return gt_list


def _announcement_to_dict(ann: Announcement) -> dict:
    """ORM Announcement 객체를 hybrid_engine 입력용 dict로 변환."""
    return {
        "id": str(ann.id),
        "source_id": ann.source_id,
        "title": ann.title,
        "target_text": ann.target_text or "",
        "exclusion_text": ann.exclusion_text or "",
        "raw_api_data": ann.raw_api_data or {},
        "attachments": [
            {
                "file_type": att.file_type,
                "local_path": att.local_path,
                "converted_pdf_path": att.converted_pdf_path,
            }
            for att in (ann.attachments or [])
        ],
    }


async def run_predictions(gt_list: List[Dict[str, Any]]) -> Dict[str, AnnouncementEligibility]:
    """각 Ground Truth 공고에 대해 hybrid_engine.extract_eligibility 예측 실행.

    DB에 존재하면 DB 데이터를 우선적으로 사용하며,
    DB 연결이 실패하거나 없을 경우 로컬 PDF를 탐색하여 Fallback announcement dict를 자동 구성합니다.
    """
    predictions = {}
    
    # 1. DB 세션 연결 시도
    db = None
    try:
        db = SessionLocal()
        # 연결 테스트용 쿼리
        db.execute(glob.select(Announcement).limit(1))
        logger.info("데이터베이스 연결 성공. DB 기반 예측 실행을 수행합니다.")
    except Exception as e:
        logger.warning(f"데이터베이스 연결 실패. 로컬 PDF Fallback 모드로 실행합니다: {e}")
        db = None

    for gt in gt_list:
        ann_id = gt["announcement_id"]
        title = gt["title"]
        logger.info(f"[{ann_id}] 예측 실행 시작...")

        ann_dict = None

        # 2. DB 조회 시도
        if db is not None:
            try:
                # title 매칭 혹은 source_id 매칭 시도
                # ground_truth.json의 announcement_id가 'ann_001'과 같은 형식인 점 감안
                stmt = glob.select(Announcement).where(
                    (Announcement.source_id == ann_id) | 
                    (Announcement.title.ilike(f"%{title}%"))
                )
                ann_orm = db.scalars(stmt).first()
                if ann_orm:
                    ann_dict = _announcement_to_dict(ann_orm)
                    logger.info(f"[{ann_id}] DB에서 공고 정보 매칭 완료 (source_id={ann_orm.source_id})")
            except Exception as e:
                logger.warning(f"[{ann_id}] DB 조회 중 오류 발생: {e}")

        # 3. 로컬 PDF Fallback 모드 작동
        if not ann_dict:
            # 해당 ann_NNN 디렉토리 내의 PDF 파일 탐색
            ann_dir = Path(project_root) / "evaluation" / "ground_truth" / ann_id
            pdf_files = list(ann_dir.glob("*.pdf"))
            if pdf_files:
                pdf_path = str(pdf_files[0])
                logger.info(f"[{ann_id}] DB 미검색 -> 로컬 PDF Fallback 활성화: {pdf_path}")
                ann_dict = {
                    "id": ann_id,
                    "source_id": ann_id,
                    "title": title,
                    "target_text": "",
                    "exclusion_text": "",
                    "attachments": [
                        {
                            "file_type": "pdf",
                            "local_path": pdf_path,
                            "converted_pdf_path": None
                        }
                    ]
                }
            else:
                logger.error(f"[{ann_id}] DB에 공고가 없고 로컬 PDF 파일도 존재하지 않습니다. 스킵합니다.")
                continue

        # 4. 예측 수행
        try:
            pred = await hybrid_engine.extract_eligibility(ann_dict)
            predictions[ann_id] = pred
            logger.info(f"[{ann_id}] 예측 완료: {len(pred.fields)} fields")
        except Exception as e:
            logger.error(f"[{ann_id}] 자격요건 추출기 호출 중 에러 발생: {e}")

    if db:
        db.close()

    return predictions


def match_fields(
    ann_id: str,
    gt_fields: List[Dict[str, Any]],
    pred_fields: List[Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """표준 7종 필드에 맞춰 Ground Truth와 Prediction 필드를 비교하여 TP, FP, FN을 선별.

    비표준 필드는 제외하고 경고를 남깁니다.
    """
    tps, fps, fns = [], [], []

    # 1. 표준 필드 필터링 및 비표준 경고
    filtered_gt = []
    for gf in gt_fields:
        name = gf["field_name"]
        if name not in STANDARD_FIELDS:
            logger.warning(f"[{ann_id}] Ground Truth 내 비표준 필드 제외 처리: {name}")
            continue
        filtered_gt.append(gf)

    filtered_pred = []
    for pf in pred_fields:
        name = pf.field_name
        if name not in STANDARD_FIELDS:
            logger.warning(f"[{ann_id}] 추출된 항목 중 비표준 필드 제외 처리: {name}")
            continue
        filtered_pred.append(pf)

    # 2. 필드 유형별(업력, 매출 등)로 매칭 수행
    for field in STANDARD_FIELDS:
        gts = [g for g in filtered_gt if g["field_name"] == field]
        preds = [p for p in filtered_pred if p.field_name == field]

        # 각 필드에 대해 조건 비교
        for gt_item in gts:
            gt_cond_norm = _normalize(gt_item["condition"])
            matched_pred = None

            # 일치하는 예측 조건 탐색
            for pred_item in preds:
                pred_cond_norm = _normalize(pred_item.condition.raw_text)
                if gt_cond_norm == pred_cond_norm:
                    matched_pred = pred_item
                    break

            if matched_pred:
                # 2-1. field_name 일치 + condition 일치 -> True Positive
                tps.append({
                    "field_name": field,
                    "condition": gt_item["condition"],
                    "evidence": matched_pred.evidence,
                    "processing_path": matched_pred.processing_path
                })
                preds.remove(matched_pred)
            else:
                # 2-2. GT에는 있으나 일치하는 예측 없음 -> False Negative
                # 단, 만약 해당 필드명으로 예측된 다른 조건이 남아있다면 condition 불일치(FP)와 GT 누락(FN)으로 쌍을 이룸
                fns.append({
                    "field_name": field,
                    "condition": gt_item["condition"],
                    "evidence_source": gt_item.get("evidence_source", "")
                })
                
                # 예측된 다른 조건이 남아있으면 하나를 꺼내어 FP로 함께 처리 (mismatch 대응)
                if preds:
                    mismatched_pred = preds.pop(0)
                    fps.append({
                        "field_name": field,
                        "condition": mismatched_pred.condition.raw_text,
                        "evidence": mismatched_pred.evidence,
                        "processing_path": mismatched_pred.processing_path,
                        "mismatch_target": gt_item["condition"]
                    })

        # 2-3. 남은 예측 정보들은 모두 기준 초과 추출이므로 -> False Positive
        for left_pred in preds:
            fps.append({
                "field_name": field,
                "condition": left_pred.condition.raw_text,
                "evidence": left_pred.evidence,
                "processing_path": left_pred.processing_path
            })

    return tps, fps, fns


def calculate_metrics(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """Precision, Recall, F1 계산."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def aggregate_metrics(
    gt_list: List[Dict[str, Any]],
    predictions: Dict[str, AnnouncementEligibility]
) -> Dict[str, Any]:
    """전체 평가 결과를 취합하여 종합 메트릭 및 세부 메트릭 산출."""
    all_tps = 0
    all_fps = 0
    all_fns = 0

    ann_results = {}
    field_metrics = {f: {"tp": 0, "fp": 0, "fn": 0} for f in STANDARD_FIELDS}
    path_metrics = {p: {"tp": 0, "fp": 0, "fn": 0} for p in ["rule_based", "text_llm", "vision_llm"]}

    mismatches = []
    sparse_announcements = []

    for gt in gt_list:
        ann_id = gt["announcement_id"]
        if ann_id not in predictions:
            continue

        pred = predictions[ann_id]
        tps, fps, fns = match_fields(ann_id, gt["fields"], pred.fields)

        # 개별 공고 메트릭 계산
        tp_c, fp_c, fn_c = len(tps), len(fps), len(fns)
        all_tps += tp_c
        all_fps += fp_c
        all_fns += fn_c

        # 필드 카운트 집계
        gt_count = len([f for f in gt["fields"] if f["field_name"] in STANDARD_FIELDS])
        is_sparse = gt_count <= 1

        if is_sparse:
            # 빈약 라벨인 경우 분모 0 발생 시 None 허용
            p = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else None
            r = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else None
            f1 = 2 * p * r / (p + r) if (p is not None and r is not None and p + r > 0) else None
            sparse_announcements.append({
                "announcement_id": ann_id,
                "title": gt["title"],
                "gt_fields_count": gt_count,
                "precision": p,
                "recall": r,
                "f1": f1
            })
        else:
            p, r, f1 = calculate_metrics(tp_c, fp_c, fn_c)

        ann_results[ann_id] = {
            "title": gt["title"],
            "metrics": {"precision": p, "recall": r, "f1": f1},
            "counts": {"tp": tp_c, "fp": fp_c, "fn": fn_c},
            "details": {"tps": tps, "fps": fps, "fns": fns}
        }

        # 필드별 성능 누적
        for item in tps:
            field_metrics[item["field_name"]]["tp"] += 1
            path_metrics[item["processing_path"]]["tp"] += 1
        for item in fps:
            field_metrics[item["field_name"]]["fp"] += 1
            path_metrics[item["processing_path"]]["fp"] += 1
            # 오답 분석용 데이터 수집
            mismatches.append({
                "announcement_id": ann_id,
                "field_name": item["field_name"],
                "type": "FP (과추출/오인식)",
                "condition": item["condition"],
                "evidence": item["evidence"],
                "target": item.get("mismatch_target", "N/A")
            })
        for item in fns:
            field_metrics[item["field_name"]]["fn"] += 1
            mismatches.append({
                "announcement_id": ann_id,
                "field_name": item["field_name"],
                "type": "FN (미추출/누락)",
                "condition": item["condition"],
                "evidence": "N/A (미추출)",
                "target": "N/A"
            })

    # 전체 micro 메트릭 계산
    overall_p, overall_r, overall_f1 = calculate_metrics(all_tps, all_fps, all_fns)

    # 필드별 최종 메트릭 계산
    field_final = {}
    for f, counts in field_metrics.items():
        p, r, f1 = calculate_metrics(counts["tp"], counts["fp"], counts["fn"])
        field_final[f] = {
            "tp": counts["tp"], "fp": counts["fp"], "fn": counts["fn"],
            "precision": p, "recall": r, "f1": f1
        }

    # 처리 경로별 최종 메트릭 계산
    path_final = {}
    for p, counts in path_metrics.items():
        prec, rec, f1 = calculate_metrics(counts["tp"], counts["fp"], counts["fn"])
        path_final[p] = {
            "tp": counts["tp"], "fp": counts["fp"], "fn": counts["fn"],
            "precision": prec, "recall": rec, "f1": f1
        }

    return {
        "overall": {
            "tp": all_tps, "fp": all_fps, "fn": all_fns,
            "precision": overall_p, "recall": overall_r, "f1": overall_f1
        },
        "announcements": ann_results,
        "fields": field_final,
        "processing_paths": path_final,
        "mismatches": mismatches,
        "sparse_announcements": sparse_announcements
    }


def render_report(results: Dict[str, Any], output_path: Path):
    """결과 데이터를 바탕으로 마크다운 보고서(report.md) 자동 생성."""
    overall = results["overall"]
    
    # 1. 헤더 및 전체 성능 요약
    md = [
        "# [PR#4] 자격요건 추출기 Precision/Recall 측정 및 E2E 평가 보고서",
        "",
        "이 분석 리포트는 Ground Truth 라벨링 데이터셋과 하이브리드 추출 엔진의 추출 결과를 E2E로 비교하여 수집된 성능 평가 정보입니다.",
        "",
        "## 1. 종합 성능 지표 (Overall Metrics)",
        "",
        "| 지표 (Metric) | 수치 (Value) |",
        "| --- | --- |",
        f"| **True Positives (TP)** | {overall['tp']}건 |",
        f"| **False Positives (FP)** | {overall['fp']}건 |",
        f"| **False Negatives (FN)** | {overall['fn']}건 |",
        f"| **전체 정밀도 (Precision)** | `{overall['precision']:.4f}` |",
        f"| **전체 재현율 (Recall)** | `{overall['recall']:.4f}` |",
        f"| **전체 F1-Score** | **`{overall['f1']:.4f}`** |",
        "",
        "---",
        ""
    ]

    # 2. 필드별 지표 표
    md.append("## 2. 표준 7종 필드별 세부 지표 (Field Metrics)")
    md.append("")
    md.append("| 필드명 (Field) | TP | FP | FN | Precision | Recall | F1-Score |")
    md.append("| --- | --- | --- | --- | --- | --- | --- |")
    for f in sorted(results["fields"].keys()):
        fm = results["fields"][f]
        md.append(f"| {f} | {fm['tp']} | {fm['fp']} | {fm['fn']} | `{fm['precision']:.4f}` | `{fm['recall']:.4f}` | **`{fm['f1']:.4f}`** |")
    md.append("")
    md.append("---")
    md.append("")

    # 3. 처리 경로별 지표 표
    md.append("## 3. 처리 경로별 세부 지표 (Processing Path Metrics)")
    md.append("")
    md.append("| 처리 경로 (Path) | TP | FP | FN | Precision | Recall | F1-Score |")
    md.append("| --- | --- | --- | --- | --- | --- | --- |")
    for p in ["rule_based", "text_llm", "vision_llm"]:
        pm = results["processing_paths"][p]
        md.append(f"| {p} | {pm['tp']} | {pm['fp']} | {pm['fn']} | `{pm['precision']:.4f}` | `{pm['recall']:.4f}` | **`{pm['f1']:.4f}`** |")
    md.append("")
    md.append("---")
    md.append("")

    # 4. 오답 케이스 샘플 (최대 상위 5건 표시)
    md.append("## 4. 주요 오답 오인식 케이스 분석 (Error Cases - Top 5 Samples)")
    md.append("")
    md.append("| 공고 ID | 필드명 | 유형 (Type) | 인식된 조건 (Predicted) | 실제 기준 (GT Target) | 증빙 근거 (Evidence) |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    mismatches = results["mismatches"][:5]
    if mismatches:
        for m in mismatches:
            md.append(f"| {m['announcement_id']} | {m['field_name']} | {m['type']} | `{m['condition']}` | `{m['target']}` | {m['evidence']} |")
    else:
        md.append("| N/A | N/A | N/A | 오류 없음 | N/A | N/A |")
    md.append("")
    md.append("---")
    md.append("")

    # 5. 빈약 라벨 ann 리스트
    md.append("## 5. 빈약 라벨 공고 분석 (Sparse Label Announcements)")
    md.append("")
    md.append("Ground Truth 표준 자격 필드 수가 1개 이하로 포함되어 평가지표 연산 시 분모 0이 발생 가능했던 대상 목록입니다.")
    md.append("")
    md.append("| 공고 ID | 공고 제목 | GT 필드 수 | Precision | Recall | F1-Score |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    sparse_list = results["sparse_announcements"]
    if sparse_list:
        for sa in sparse_list:
            p_val = f"`{sa['precision']:.4f}`" if sa["precision"] is not None else "`None`"
            r_val = f"`{sa['recall']:.4f}`" if sa["recall"] is not None else "`None`"
            f1_val = f"**`{sa['f1']:.4f}`**" if sa["f1"] is not None else "`None`"
            md.append(f"| {sa['announcement_id']} | {sa['title']} | {sa['gt_fields_count']} | {p_val} | {r_val} | {f1_val} |")
    else:
        md.append("| N/A | N/A | 0건 | N/A | N/A | N/A |")
    md.append("")

    # 파일 저장
    output_path.write_text("\n".join(md), encoding="utf-8")
    logger.info(f"마크다운 분석 리포트 저장 완료: {output_path}")


async def main():
    logger.info("=== PR#4 Precision/Recall 측정 평가 도구 실행 ===")
    
    # 1. GT 데이터 로드
    gt_list = load_ground_truth()
    if not gt_list:
        logger.error("평가를 진행할 Ground Truth 데이터를 확보할 수 없습니다.")
        return

    # 2. 예측 실행
    predictions = await run_predictions(gt_list)

    # 3. 메트릭 계산 및 집계
    results = aggregate_metrics(gt_list, predictions)

    # 4. 결과 저장 디렉토리 생성
    results_dir = Path(project_root) / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 5. JSON 저장
    json_path = results_dir / "pr4_measurement.json"
    
    # JSON 직렬화를 위해 float('nan')이나 None이 적절히 인코딩되도록 보장
    class MetricsEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, cls=MetricsEncoder)
    logger.info(f"JSON 결과 데이터 저장 완료: {json_path}")

    # 6. 마크다운 보고서 생성
    report_path = results_dir / "report.md"
    render_report(results, report_path)

    logger.info("=== PR#4 평가 프로세스 정상 종료 ===")


if __name__ == "__main__":
    asyncio.run(main())
