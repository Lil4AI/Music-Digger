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
    指定された track_id の特徴量から、各ジャンルの存在確率を予測する。
    戻り値:
        {"heavy_dubstep": 0.8, "riddim": 0.2, ...}
    """
    try:
        X_dict = load_unlabeled_features(track_id)
    except FileNotFoundError as e:
        logging.error(f"Track {track_id} の推論に必要な特徴量がありません: {e}")
        raise ValueError("特徴量が抽出されていません。")
        
    model = get_model()
    
    # 確率を予測
    probs = model.predict_proba(X_dict)[0]
    
    # 学習済みモデルが保持しているクラスラベル（model.clf.classes_）を取得
    raw_classes = model.clf.classes_ if hasattr(model, 'clf') and hasattr(model.clf, 'classes_') else list(range(len(settings.genre_labels)))
    
    genre_names = []
    for cls in raw_classes:
        try:
            idx = int(cls)
            if 0 <= idx < len(settings.genre_labels):
                genre_names.append(settings.genre_labels[idx])
            else:
                genre_names.append(str(cls))
        except (ValueError, TypeError):
            genre_names.append(str(cls))

    return {name: float(prob) for name, prob in zip(genre_names, probs)}
