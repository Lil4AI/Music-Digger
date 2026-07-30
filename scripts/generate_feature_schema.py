"""
EDMサブジャンル自動判定システム — 特徴量スキーマ生成スクリプト

各ブランチの特徴量抽出関数をダミー音源に対して実行し、
出力次元数とスキーマを feature_schema_v1.json に保存する。
"""

import json
import soundfile as sf
import numpy as np
from pathlib import Path

from src.config import settings
from src.features.drums import extract_drums_features
from src.features.bass import extract_bass_features
from src.features.subbass import extract_subbass_features
from src.features.other import extract_other_features

def run():
    print("ダミー音源を生成中...")
    dummy_path = Path(settings.project_root) / "data" / "dummy_feature_test.wav"
    sr = 44100
    # 1秒間のダミー音源 (ノイズ)
    dummy_y = np.random.randn(sr).astype(np.float32)
    sf.write(str(dummy_path), dummy_y, sr)
    
    schema = {
        "version": "v1",
        "branches": {}
    }
    
    try:
        print("drums の特徴量を抽出中...")
        drums_feat = extract_drums_features(str(dummy_path))
        schema["branches"]["drums"] = {"dim": len(drums_feat)}
        
        print("bass の特徴量を抽出中...")
        bass_feat = extract_bass_features(str(dummy_path))
        schema["branches"]["bass"] = {"dim": len(bass_feat)}
        
        print("subbass の特徴量を抽出中...")
        subbass_feat = extract_subbass_features(str(dummy_path))
        schema["branches"]["subbass"] = {"dim": len(subbass_feat)}
        
        print("other の特徴量を抽出中...")
        other_feat = extract_other_features(str(dummy_path))
        schema["branches"]["other"] = {"dim": len(other_feat)}
        
        schema_path = Path(settings.project_root) / settings.paths.features / "feature_schema_v1.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
            
        print(f"スキーマを保存しました: {schema_path}")
        print(json.dumps(schema, indent=2))
        
    finally:
        if dummy_path.exists():
            dummy_path.unlink()

if __name__ == "__main__":
    run()
