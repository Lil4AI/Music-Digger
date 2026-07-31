import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from src.config import settings

def load_labeled_dataset():
    """
    DBのtracksテーブルから human_label が付与されているトラックを取得し、
    特徴量(.npy)をロードしてデータセットを構成する。
    戻り値:
        X_dict: {"drums": np.ndarray, "bass": np.ndarray, "subbass": np.ndarray, "other": np.ndarray}
        y: np.ndarray (tearout=1, riddim=0)
        track_ids: list of str
    """
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql("SELECT track_id, human_label FROM tracks WHERE human_label IS NOT NULL", conn)
        
    if df.empty:
        return None, None, None
        
    X_drums = []
    X_bass = []
    X_subbass = []
    X_other = []
    y = []
    valid_track_ids = []
    
    for _, row in df.iterrows():
        track_id = row['track_id']
        label = row['human_label']
        
        feat_dir = Path(settings.project_root) / settings.paths.features / track_id
        
        try:
            d = np.load(str(feat_dir / "drums.npy"))
            b = np.load(str(feat_dir / "bass.npy"))
            sb = np.load(str(feat_dir / "subbass.npy"))
            o = np.load(str(feat_dir / "other.npy"))
        except FileNotFoundError:
            # 特徴量が抽出されていないトラックはスキップ
            continue
            
        X_drums.append(d)
        X_bass.append(b)
        X_subbass.append(sb)
        X_other.append(o)
        
        # ラベルの数値化 (settings.genre_labelsのインデックスに合わせる)
        genres_lower = [g.lower() for g in settings.genre_labels]
        if label.lower() in genres_lower:
            y.append(genres_lower.index(label.lower()))
        else:
            y.append(0) # デフォルトフォールバック
        valid_track_ids.append(track_id)
        
    if not valid_track_ids:
        return None, None, None
        
    X_dict = {
        "drums": np.vstack(X_drums),
        "bass": np.vstack(X_bass),
        "subbass": np.vstack(X_subbass),
        "other": np.vstack(X_other)
    }
    
    return X_dict, np.array(y), valid_track_ids

def load_unlabeled_features(track_id: str):
    """
    推論用に単一のトラックの特徴量をロードする。
    戻り値:
        X_dict (batch_size=1)
    """
    feat_dir = Path(settings.project_root) / settings.paths.features / track_id
    
    d = np.load(str(feat_dir / "drums.npy"))
    b = np.load(str(feat_dir / "bass.npy"))
    sb = np.load(str(feat_dir / "subbass.npy"))
    o = np.load(str(feat_dir / "other.npy"))
    
    X_dict = {
        "drums": d.reshape(1, -1),
        "bass": b.reshape(1, -1),
        "subbass": sb.reshape(1, -1),
        "other": o.reshape(1, -1)
    }
    return X_dict
