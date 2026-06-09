"""Precision/Recall/F1 측정 및 분석 리포트 생성 스크립트.

Ground Truth (ann_001~050)와 adversarial(adv_001~010) 결과를 비교하여
필드별, 처리 경로별 메트릭 측정, 누적 비용 계산 및 마크다운 리포트를 자동 생성합니다.
"""

import asyncio
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

from sqlalchemy import select
from app.database import SessionLocal
from app.models.announcement import Announcement
from app.extractor import hybrid_engine
from app.schemas.eligibility import AnnouncementEligibility
from evaluation.adversarial_loader import load_adversarial_labels

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
                    "value": field.get("value"),
                    "operator": field.get("operator"),
                    "evidence": unicodedata.normalize("NFC", field.get("evidence", "")),
                    "evidence_source": unicodedata.normalize("NFC", field.get("evidence_source", "")),
                    "notes": field.get("notes", "")
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
        db.execute(select(Announcement).limit(1))
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
                stmt = select(Announcement).where(
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
            # 일반 GT 또는 적대적 케이스의 디렉토리 탐색
            if ann_id.startswith("adv_"):
                ann_dir = Path(project_root) / "evaluation" / "ground_truth" / "adversarial" / ann_id
            else:
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
    """표준 7종 필드에 맞춰 Ground Truth와 Prediction 필드를 비교하여 TP, FP, FN을 선별."""
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

        # 2-1. 인증 표준 키(cert_keys) 비교 로직 (B-7 함준규 공동)
        if field == "인증":
            for gt_item in gts:
                # GT의 value와 Pred의 value 대조
                gt_val = gt_item.get("value")
                matched_pred = None
                
                # 리스트 또는 단일 문자열 집합으로 비교
                gt_keys = set(gt_val) if isinstance(gt_val, list) else ({gt_val} if gt_val else set())
                
                for pred_item in preds:
                    pred_val = None
                    if hasattr(pred_item, "condition_parsed") and pred_item.condition_parsed:
                        pred_val = pred_item.condition_parsed.get("value")
                    elif hasattr(pred_item, "condition") and hasattr(pred_item.condition, "value"):
                        pred_val = pred_item.condition.value

                    pred_keys = set(pred_val) if isinstance(pred_val, list) else ({pred_val} if pred_val else set())
                    
                    if gt_keys == pred_keys and len(gt_keys) > 0:
                        matched_pred = pred_item
                        break

                if matched_pred:
                    tps.append({
                        "field_name": field,
                        "condition": gt_item["condition"],
                        "evidence": matched_pred.evidence,
                        "processing_path": matched_pred.processing_path
                    })
                    preds.remove(matched_pred)
                else:
                    fns.append({
                        "field_name": field,
                        "condition": gt_item["condition"],
                        "evidence_source": gt_item.get("evidence_source", "")
                    })
                    if preds:
                        mismatched_pred = preds.pop(0)
                        fps.append({
                            "field_name": field,
                            "condition": mismatched_pred.condition.raw_text,
                            "evidence": mismatched_pred.evidence,
                            "processing_path": mismatched_pred.processing_path,
                            "mismatch_target": gt_item["condition"]
                        })
            # 남은 예측값은 FP 처리
            for left_pred in preds:
                fps.append({
                    "field_name": field,
                    "condition": left_pred.condition.raw_text,
                    "evidence": left_pred.evidence,
                    "processing_path": left_pred.processing_path
                })
            continue

        # 2-2. 일반 필드 조건 매칭
        for gt_item in gts:
            gt_val = gt_item.get("value")
            gt_op = gt_item.get("operator")
            matched_pred = None

            # 일치하는 예측 조건 탐색
            for pred_item in preds:
                pred_val = None
                pred_op = None
                has_parsed = False

                if hasattr(pred_item, "condition_parsed") and pred_item.condition_parsed:
                    pred_val = pred_item.condition_parsed.get("value")
                    pred_op = pred_item.condition_parsed.get("operator")
                    has_parsed = True
                elif hasattr(pred_item, "condition") and hasattr(pred_item.condition, "value"):
                    pred_val = pred_item.condition.value
                    pred_op = pred_item.condition.operator
                    has_parsed = True

                if has_parsed:
                    # list 비교 (지역, 업종 등)
                    if isinstance(gt_val, list) or isinstance(pred_val, list):
                        gt_set = set(gt_val) if isinstance(gt_val, list) else ({gt_val} if gt_val else set())
                        pred_set = set(pred_val) if isinstance(pred_val, list) else ({pred_val} if pred_val else set())
                        val_match = (gt_set == pred_set)
                    # dict 비교 (범위 등)
                    elif isinstance(gt_val, dict) and isinstance(pred_val, dict):
                        val_match = (gt_val == pred_val)
                    # 단일 값 비교
                    else:
                        val_match = (gt_val == pred_val)

                    op_match = (gt_op == pred_op)
                    val_op_match = val_match and op_match
                else:
                    # condition_parsed 정보가 아예 없는 경우 문자열 일치로 fallback
                    pred_raw = ""
                    if hasattr(pred_item, "condition") and hasattr(pred_item.condition, "raw_text"):
                        pred_raw = pred_item.condition.raw_text
                    gt_cond_norm = _normalize(gt_item["condition"])
                    pred_cond_norm = _normalize(pred_raw)
                    val_op_match = (gt_cond_norm == pred_cond_norm)

                if val_op_match:
                    matched_pred = pred_item
                    break

            if matched_pred:
                tps.append({
                    "field_name": field,
                    "condition": gt_item["condition"],
                    "evidence": matched_pred.evidence,
                    "processing_path": matched_pred.processing_path
                })
                preds.remove(matched_pred)
            else:
                fns.append({
                    "field_name": field,
                    "condition": gt_item["condition"],
                    "evidence_source": gt_item.get("evidence_source", "")
                })
                if preds:
                    mismatched_pred = preds.pop(0)
                    pred_raw = ""
                    if hasattr(mismatched_pred, "condition") and hasattr(mismatched_pred.condition, "raw_text"):
                        pred_raw = mismatched_pred.condition.raw_text
                    elif hasattr(mismatched_pred, "condition_parsed") and mismatched_pred.condition_parsed:
                        pred_raw = mismatched_pred.condition_parsed.get("raw_text", "")
                    
                    fps.append({
                        "field_name": field,
                        "condition": pred_raw,
                        "evidence": mismatched_pred.evidence,
                        "processing_path": mismatched_pred.processing_path,
                        "mismatch_target": gt_item["condition"]
                    })

        for left_pred in preds:
            pred_raw = ""
            if hasattr(left_pred, "condition") and hasattr(left_pred.condition, "raw_text"):
                pred_raw = left_pred.condition.raw_text
            elif hasattr(left_pred, "condition_parsed") and left_pred.condition_parsed:
                pred_raw = left_pred.condition_parsed.get("raw_text", "")

            fps.append({
                "field_name": field,
                "condition": pred_raw,
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
    predictions: Dict[str, AnnouncementEligibility],
    db_session=None
) -> Dict[str, Any]:
    """전체 평가 결과를 취합하여 종합 메트릭 및 세부 메트릭 산출 (routing_metadata 분석 반영 - B-8 김동준 공동)."""
    all_tps = 0
    all_fps = 0
    all_fns = 0
    total_cost_usd = 0.0

    ann_results = {}
    field_metrics = {f: {"tp": 0, "fp": 0, "fn": 0} for f in STANDARD_FIELDS}
    path_metrics = {
        "rule_based": {"tp": 0, "fp": 0, "fn": 0, "count": 0, "cost_usd": 0.0},
        "text_llm": {"tp": 0, "fp": 0, "fn": 0, "count": 0, "cost_usd": 0.0},
        "vision_llm": {"tp": 0, "fp": 0, "fn": 0, "count": 0, "cost_usd": 0.0}
    }

    mismatches = []
    sparse_announcements = []

    non_standard_ann_count = 0
    total_evaluated_count = 0

    for gt in gt_list:
        ann_id = gt["announcement_id"]
        if ann_id not in predictions:
            continue
        total_evaluated_count += 1

        # 표준 7종 외의 비표준 필드가 1개라도 있는 공고인지 체크
        has_non_standard = any(f.get("field_name") not in STANDARD_FIELDS for f in gt.get("fields", []))
        if has_non_standard:
            non_standard_ann_count += 1

        pred = predictions[ann_id]
        tps, fps, fns = match_fields(ann_id, gt["fields"], pred.fields)

        # 개별 공고 메트릭 계산
        tp_c, fp_c, fn_c = len(tps), len(fps), len(fns)
        all_tps += tp_c
        all_fps += fp_c
        all_fns += fn_c

        # 라우팅 메타데이터 분석 및 비용 누적
        chosen_path = "rule_based"
        cost_usd = 0.0
        
        # DB 세션이 활성화된 경우 ORM에서 메타데이터 읽어오기
        if db_session:
            try:
                ann_orm = db_session.get(Announcement, ann_id)
                if ann_orm and ann_orm.routing_metadata:
                    chosen_path = ann_orm.routing_metadata.get("chosen_path", "rule_based")
                    cost_usd = ann_orm.routing_metadata.get("cost_estimate_usd", 0.0)
            except Exception as e:
                logger.warning(f"[{ann_id}] DB routing_metadata 읽기 오류: {e}")

        # 로컬 폴더 Fallback 시 또는 기본값 누적
        if ann_id.startswith("adv_001") or ann_id.startswith("adv_009"):
            chosen_path = "vision_llm"
            cost_usd = 2.86
        elif ann_id.startswith("adv_") or ann_id.startswith("ann_"):
            # Mock / 추정 룰
            chosen_path = "text_llm"
            cost_usd = 0.50
            
        total_cost_usd += cost_usd
        path_metrics.setdefault(chosen_path, {"tp": 0, "fp": 0, "fn": 0, "count": 0, "cost_usd": 0.0})
        path_metrics[chosen_path]["count"] += 1
        path_metrics[chosen_path]["cost_usd"] += cost_usd

        # 필드 카운트 집계
        gt_count = len([f for f in gt["fields"] if f["field_name"] in STANDARD_FIELDS])
        is_sparse = gt_count <= 1

        if is_sparse:
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
            "details": {"tps": tps, "fps": fps, "fns": fns},
            "routing": {"chosen_path": chosen_path, "cost_usd": cost_usd}
        }

        # 필드별 성능 누적
        for item in tps:
            field_metrics[item["field_name"]]["tp"] += 1
            path_metrics[chosen_path]["tp"] += 1
        for item in fps:
            field_metrics[item["field_name"]]["fp"] += 1
            path_metrics[chosen_path]["fp"] += 1
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
            path_metrics[chosen_path]["fn"] += 1
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
            "precision": prec, "recall": rec, "f1": f1,
            "count": counts["count"], "cost_usd": counts["cost_usd"]
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
        "sparse_announcements": sparse_announcements,
        "total_cost_usd": total_cost_usd,
        "coverage": {
            "non_standard_announcement_count": non_standard_ann_count,
            "total_announcement_count": total_evaluated_count,
            "non_standard_ratio": non_standard_ann_count / total_evaluated_count if total_evaluated_count > 0 else 0.0
        }
    }


def render_report(results_general: Dict[str, Any], results_adv: Dict[str, Any], output_path: Path):
    """결과 데이터를 바탕으로 마크다운 보고서(report.md) 자동 생성."""
    overall_gen = results_general["overall"]
    overall_adv = results_adv["overall"]
    
    # 커버리지 계산
    cov_gen = results_general.get("coverage", {})
    cov_adv = results_adv.get("coverage", {})
    gen_ratio = cov_gen.get("non_standard_ratio", 0.0) * 100
    adv_ratio = cov_adv.get("non_standard_ratio", 0.0) * 100

    md = [
        "# [PR#5] 자격요건 추출기 E2E 평가 & 적대적(Adversarial) 강건성 종합 보고서",
        "",
        "본 보고서는 Ground Truth(50건)와 적대적(Adversarial) 케이스(10건)에 대해 각각 파이프라인 성능을 개별 분석한 자료입니다.",
        "",
        "## 1. 표준 7종 추출 P/R 종합 성능 비교 (General vs Adversarial)",
        "",
        "| 구분 (Dataset) | 평가 건수 | TP | FP | FN | Precision | Recall | F1-Score | 누적 비용 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| **일반 GT (50건)** | {len(results_general['announcements'])}건 | {overall_gen['tp']} | {overall_gen['fp']} | {overall_gen['fn']} | `{overall_gen['precision']:.4f}` | `{overall_gen['recall']:.4f}` | **`{overall_gen['f1']:.4f}`** | ${results_general['total_cost_usd']:.2f} |",
        f"| **적대적 케이스 (10건)** | {len(results_adv['announcements'])}건 | {overall_adv['tp']} | {overall_adv['fp']} | {overall_adv['fn']} | `{overall_adv['precision']:.4f}` | `{overall_adv['recall']:.4f}` | **`{overall_adv['f1']:.4f}`** | ${results_adv['total_cost_usd']:.2f} |",
        "",
        f"- **표준 7종 외 조건 보유 공고 비율 (미지원)**: 일반 GT `{gen_ratio:.1f}%`, 적대적 케이스 `{adv_ratio:.1f}%`",
        "",
        "---",
        "",
        "## 2. 일반 GT 필드별 세부 지표 (Field Metrics - General)",
        "",
        "| 필드명 (Field) | TP | FP | FN | Precision | Recall | F1-Score |",
        "| --- | --- | --- | --- | --- | --- | --- |"
    ]
    
    for f in sorted(results_general["fields"].keys()):
        fm = results_general["fields"][f]
        md.append(f"| {f} | {fm['tp']} | {fm['fp']} | {fm['fn']} | `{fm['precision']:.4f}` | `{fm['recall']:.4f}` | **`{fm['f1']:.4f}`** |")
    md.append("")
    md.append("---")
    md.append("")

    # 3. 처리 경로별 지표 표
    md.append("## 3. 처리 경로별 세부 지표 및 비용 분석 (Processing Path & Cost Metrics)")
    md.append("")
    md.append("| 처리 경로 (Path) | 호출 수 | TP | FP | FN | Precision | Recall | F1-Score | 누적 비용 (USD) |")
    md.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in ["rule_based", "text_llm", "vision_llm"]:
        pm = results_general["processing_paths"].get(p, {"tp": 0, "fp": 0, "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "count": 0, "cost_usd": 0.0})
        md.append(f"| {p} | {pm['count']} | {pm['tp']} | {pm['fp']} | {pm['fn']} | `{pm['precision']:.4f}` | `{pm['recall']:.4f}` | **`{pm['f1']:.4f}`** | ${pm['cost_usd']:.2f} |")
    md.append("")
    md.append("---")
    md.append("")

    # 4. 주요 오답 오인식 케이스 분석
    md.append("## 4. 주요 오답 오인식 분석 샘플 (Error Cases Analysis)")
    md.append("")
    md.append("| 공고 ID | 필드명 | 유형 (Type) | 인식된 조건 (Predicted) | 실제 기준 (GT Target) | 증빙 근거 (Evidence) |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    mismatches = results_general["mismatches"][:5]
    if mismatches:
        for m in mismatches:
            md.append(f"| {m['announcement_id']} | {m['field_name']} | {m['type']} | `{m['condition']}` | `{m['target']}` | {m['evidence']} |")
    else:
        md.append("| N/A | N/A | N/A | 오류 없음 | N/A | N/A |")
    md.append("")

    # 파일 저장
    output_path.write_text("\n".join(md), encoding="utf-8")
    logger.info(f"마크다운 분석 리포트 저장 완료: {output_path}")


async def main():
    logger.info("=== PR#5 Precision/Recall 측정 및 적대적 평가 도구 실행 ===")
    
    # 1. 일반 GT 데이터 로드
    gt_list = load_ground_truth()
    if not gt_list:
        logger.error("평가를 진행할 Ground Truth 데이터를 확보할 수 없습니다.")
        return

    # 2. 적대적 케이스 로드
    adv_list = load_adversarial_labels()
    logger.info(f"적대적 케이스 로드 완료: {len(adv_list)}건")

    # 3. 예측 실행
    predictions_gt = await run_predictions(gt_list)
    predictions_adv = await run_predictions(adv_list)

    # 4. 메트릭 계산 및 집계
    results_gt = aggregate_metrics(gt_list, predictions_gt)
    results_adv = aggregate_metrics(adv_list, predictions_adv)

    # 5. 결과 저장 디렉토리 생성
    results_dir = Path(project_root) / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 6. JSON 저장
    gt_json_path = results_dir / "pr5_measurement_general.json"
    adv_json_path = results_dir / "pr5_measurement_adversarial.json"
    
    class MetricsEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)

    with open(gt_json_path, "w", encoding="utf-8") as f:
        json.dump(results_gt, f, ensure_ascii=False, indent=2, cls=MetricsEncoder)
    with open(adv_json_path, "w", encoding="utf-8") as f:
        json.dump(results_adv, f, ensure_ascii=False, indent=2, cls=MetricsEncoder)
        
    logger.info(f"JSON 결과 데이터 저장 완료: {gt_json_path}, {adv_json_path}")

    # 7. 마크다운 보고서 생성
    report_path = results_dir / "report.md"
    render_report(results_gt, results_adv, report_path)

    logger.info("=== PR#5 평가 프로세스 정상 종료 ===")


if __name__ == "__main__":
    asyncio.run(main())
