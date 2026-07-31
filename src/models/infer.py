import joblib
import logging
from pathlib import Path
import numpy as np

from src.config import settings
from src.models.dataset import load_unlabeled_features

# キャッシュ用
_model = None

def get_model():
    global _model
    if _model is None:
        model_path = Path(settings.project_root) / settings.paths.models / "fusion_classifier_v1.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")
        _model = joblib.load(str(model_path))
    return _model

def predict_genre(track_id: str) -> dict:
    """
    指定された track_id の特徴量から、Tear Out vs Riddim の確率を予測する。
    戻り値:
        {"tearout": float, "riddim": float}
    """
    try:
        X_dict = load_unlabeled_features(track_id)
    except FileNotFoundError as e:
        logging.error(f"Track {track_id} の推論に必要な特徴量がありません: {e}")
        raise ValueError("特徴量が抽出されていません。")
        
    model = get_model()
    
    # 確率を予測 [riddim(0)の確率, tearout(1)の確率]
    probs = model.predict_proba(X_dict)[0]
    
    return {
        settings.genre_labels[0]: float(probs[0]),
        settings.genre_labels[1]: float(probs[1])
    }
