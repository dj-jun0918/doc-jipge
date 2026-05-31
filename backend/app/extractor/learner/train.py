"""Decision Tree Classifier 학습 및 검증 모듈."""

import logging
from pathlib import Path
from typing import Any
import joblib
from sqlalchemy.orm import Session
from sklearn.tree import DecisionTreeClassifier

from app.database import SessionLocal
from app.models.announcement import Announcement
from app.models.eligibility import EligibilityResult
from app.extractor.learner.features import extract_features, features_to_vector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent / "model.pkl"

def label_announcement(ann: Announcement, eligibility_results: list[EligibilityResult]) -> str:
    """기존 추출 결과 → 어느 경로가 가장 적합했는지 라벨링."""
    rule_results = [r for r in eligibility_results if r.processing_path == "rule_based"]
    if len(rule_results) >= 5:  # 7종 중 5개 이상 규칙으로 파싱되면 rule_based로 판단
        return "rule_based"

    text_results = [r for r in eligibility_results if r.processing_path == "text_llm"]
    structured_tables = getattr(ann, "structured_tables", []) or []
    if text_results and len(structured_tables) < 2:
        return "text_llm"

    return "vision_llm"

def build_dataset(db: Session) -> tuple[list[list[float]], list[str]]:
    """DB 내 완료된 공고들을 기반으로 학습 데이터셋 구성."""
    X, y = [], []
    # extraction_status가 "done"인 공고 대상
    anns = db.query(Announcement).filter(
        Announcement.extraction_status == "done"
    ).all()
    
    for ann in anns:
        elig = db.query(EligibilityResult).filter_by(announcement_id=ann.id).all()
        if not elig:
            continue
        features = extract_features(ann)
        label = label_announcement(ann, elig)
        X.append(features_to_vector(features))
        y.append(label)
        
    return X, y

def validate_on_gt(clf: DecisionTreeClassifier) -> float:
    """ann_001~025 GT 기준 모델 예측 정확도 검증."""
    db = SessionLocal()
    correct, total = 0, 0
    try:
        for i in range(1, 26):
            ann_id = f"ann_{i:03d}"
            ann = db.query(Announcement).filter_by(source_id=ann_id).first()
            if not ann:
                continue
            elig = db.query(EligibilityResult).filter_by(announcement_id=ann.id).all()
            if not elig:
                continue
            true_label = label_announcement(ann, elig)
            features = extract_features(ann)
            pred = clf.predict([features_to_vector(features)])[0]
            correct += int(pred == true_label)
            total += 1
    finally:
        db.close()
        
    return correct / total if total > 0 else 0.0

def train_and_save() -> float:
    """Decision Tree 모델을 학습하고 model.pkl로 저장 후 GT 검증."""
    db = SessionLocal()
    try:
        X, y = build_dataset(db)
        logger.info(f"학습 데이터 구축 완료: {len(X)}건")
        
        if len(X) < 30:
            logger.warning(f"학습 데이터 부족: 현재 {len(X)}건. 실제 프로덕션 수준의 학습을 위해선 30건 이상 권장합니다. (테스트 목적/데이터 부족 시 강제 진행)")
            # 테스트를 위해 강제 에러는 내지 않되, 0건인 경우에는 학습 불가하므로 방어
            if len(X) == 0:
                raise ValueError("학습 데이터가 0건입니다. DB에 적재된 공고 자격요건 추출 결과가 필요합니다.")

        clf = DecisionTreeClassifier(
            max_depth=5,
            min_samples_leaf=2 if len(X) < 30 else 10,  # 데이터 부족 시 min_samples_leaf 유연 조정
            random_state=42,
            class_weight="balanced",
        )
        clf.fit(X, y)
        
        # model.pkl 저장
        joblib.dump(clf, _MODEL_PATH)
        logger.info(f"모델 저장 완료: {_MODEL_PATH}")

        # GT 검증
        accuracy = validate_on_gt(clf)
        logger.info(f"GT 25건 검증 정확도: {accuracy:.2%}")
        if accuracy < 0.80:
            logger.warning(f"GT 검증 정확도 낮음: {accuracy:.2%} (목표 80% 미만)")
        return accuracy
    finally:
        db.close()

if __name__ == "__main__":
    try:
        train_and_save()
    except Exception as e:
        logger.error(f"모델 학습 실패: {e}")
