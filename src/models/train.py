import joblib
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import sys

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV

from src.config import settings
from src.models.dataset import load_labeled_dataset

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "training.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class FeatureFusionPipeline:
    def __init__(self, classifier_name="xgboost"):
        self.scalers = {
            "drums": StandardScaler(),
            "bass": StandardScaler(),
            "subbass": StandardScaler(),
            "other": StandardScaler()
        }
        
        if classifier_name == "xgboost":
            self.base_clf = XGBClassifier(eval_metric='logloss', random_state=42)
        elif classifier_name == "rf":
            self.base_clf = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            self.base_clf = LogisticRegression(max_iter=1000, random_state=42)
            
        # 確率出力のキャリブレーション用
        self.clf = CalibratedClassifierCV(self.base_clf, method='sigmoid', cv=3)

    def _concat_features(self, X_dict, fit=False):
        scaled_parts = []
        for branch in ["drums", "bass", "subbass", "other"]:
            X_branch = X_dict[branch]
            if fit:
                X_scaled = self.scalers[branch].fit_transform(X_branch)
            else:
                X_scaled = self.scalers[branch].transform(X_branch)
            scaled_parts.append(X_scaled)
        
        return np.hstack(scaled_parts)

    def fit(self, X_dict, y):
        X_concat = self._concat_features(X_dict, fit=True)
        unique_classes, counts = np.unique(y, return_counts=True)
        
        if len(unique_classes) < 2:
            print("エラー: 学習には最低2つ以上のクラスのデータが必要です。")
            sys.exit(1)
            
        min_class_count = np.min(counts)
        if min_class_count < 3:
            logging.warning("Skipped calibration due to small class count")
            self.clf = self.base_clf
            
        self.clf.fit(X_concat, y)
        return self

    def predict(self, X_dict):
        X_concat = self._concat_features(X_dict, fit=False)
        return self.clf.predict(X_concat)

    def predict_proba(self, X_dict):
        X_concat = self._concat_features(X_dict, fit=False)
        return self.clf.predict_proba(X_concat)

def train_and_evaluate():
    X_dict, y, track_ids = load_labeled_dataset()
    if X_dict is None or len(y) == 0:
        logging.error("学習用データが見つかりません。DBに human_label が設定されているか確認してください。")
        print("エラー: 学習データなし")
        sys.exit(1)

    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        logging.error("学習には最低2つ以上のクラス（ジャンル）のデータが必要です。")
        print("エラー: 複数クラスの学習データがありません。")
        sys.exit(1)

    print(f"{len(y)} 件のデータで学習を開始します...")
    logging.info(f"学習開始: {len(y)} samples")

    avg_acc, avg_f1, avg_auc = 0.0, 0.0, 0.0
    
    # 十分なデータがある場合のみ K-Fold CV を実行
    # 十分なデータがある場合のみ K-Fold CV を実行
    min_samples_per_class = min([np.sum(y == c) for c in unique_classes]) if len(unique_classes) > 1 else 0
    
    if len(y) >= 10 and len(unique_classes) > 1 and min_samples_per_class >= 5:
        # K-Fold CV でモデル比較 (XGBoost がメイン想定だが、他も比較可能)
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        metrics = {"accuracy": [], "f1": [], "auc": []}
        
        for train_idx, val_idx in skf.split(np.zeros(len(y)), y):
            X_train = {k: v[train_idx] for k, v in X_dict.items()}
            y_train = y[train_idx]
            
            X_val = {k: v[val_idx] for k, v in X_dict.items()}
            y_val = y[val_idx]
            
            pipeline = FeatureFusionPipeline(classifier_name="xgboost")
            
            # サンプル数が少ない場合はキャリブレーションのCVが失敗するためフォールバック
            if len(y_train) < 10:
                pipeline.clf = pipeline.base_clf
                
            pipeline.fit(X_train, y_train)
            
            y_pred = pipeline.predict(X_val)
            y_prob = pipeline.predict_proba(X_val)[:, 1] if hasattr(pipeline.clf, "predict_proba") else y_pred
            
            metrics["accuracy"].append(accuracy_score(y_val, y_pred))
            metrics["f1"].append(f1_score(y_val, y_pred, average='weighted', zero_division=0))
                
        avg_acc = np.mean(metrics["accuracy"])
        avg_f1 = np.mean(metrics["f1"])
        avg_auc = np.mean(metrics["auc"]) if metrics["auc"] else 0.0
        print(f"5-Fold CV 結果: Accuracy={avg_acc:.4f}, F1={avg_f1:.4f}, AUC={avg_auc:.4f}")
        logging.info(f"CV Metrics: {avg_acc:.4f} / {avg_f1:.4f} / {avg_auc:.4f}")
    else:
        print("警告: サンプル数が少なすぎるため、クロスバリデーション(評価)をスキップし、全データで直接モデルを学習します。")
        logging.warning("Skipped CV due to small dataset size")

    # 全データで最終モデルを学習
    final_pipeline = FeatureFusionPipeline(classifier_name="xgboost")
    if len(y) < 10:
        final_pipeline.clf = final_pipeline.base_clf
    final_pipeline.fit(X_dict, y)
    
    # モデル保存
    model_dir = Path(settings.project_root) / settings.paths.models
    model_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = model_dir / "fusion_classifier_v1.pkl"
    joblib.dump(final_pipeline, model_path)
    print(f"モデルを保存しました: {model_path}")
    logging.info(f"モデル保存完了: {model_path}")
    
    # metricsをJSONで保存
    metrics_path = model_dir / "metrics_v1.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "samples": len(y),
            "cv_metrics": {
                "accuracy": avg_acc,
                "f1": avg_f1,
                "auc": avg_auc
            }
        }, f, indent=2)

if __name__ == "__main__":
    train_and_evaluate()
