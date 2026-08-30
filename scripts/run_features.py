"""
EDMサブジャンル自動判定システム — 特徴量抽出バッチ処理

DBから separated_at IS NOT NULL AND features_extracted_at IS NULL の track を全件取得し、
4ブランチの特徴量を抽出して data/features/{track_id}/ に保存する。
完了したら features_extracted_at を更新する。
"""

import sqlite3
import logging
import traceback
import sys
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.features.drums import extract_drums_features
from src.features.bass import extract_bass_features
from src.features.subbass import extract_subbass_features
from src.features.other import extract_other_features

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "features.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run():
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT track_id FROM tracks WHERE separated_at IS NOT NULL AND features_extracted_at IS NULL")
        rows = cursor.fetchall()
        
        if not rows:
            print("処理対象のトラックはありません。")
            return
            
        print(f"{len(rows)} 件のトラックの特徴量を抽出します...")
        success_count = 0
        
        for row in tqdm(rows, desc="Feature Extraction"):
            track_id = row['track_id']
            stems_dir = Path(settings.project_root) / settings.paths.stems / track_id
            feat_dir = Path(settings.project_root) / settings.paths.features / track_id
            feat_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # 各ステムが存在することを確認
                for stem in ["drums", "bass", "subbass", "other"]:
                    if not (stems_dir / f"{stem}.wav").exists():
                        raise FileNotFoundError(f"{stem}.wav が見つかりません: {stems_dir}")

                # 特徴量抽出と保存
                drums_feat = extract_drums_features(str(stems_dir / "drums.wav"))
                np.save(str(feat_dir / "drums.npy"), drums_feat)
                
                bass_feat = extract_bass_features(str(stems_dir / "bass.wav"))
                np.save(str(feat_dir / "bass.npy"), bass_feat)
                
                subbass_feat = extract_subbass_features(str(stems_dir / "subbass.wav"))
                np.save(str(feat_dir / "subbass.npy"), subbass_feat)
                
                other_feat = extract_other_features(str(stems_dir / "other.wav"))
                np.save(str(feat_dir / "other.npy"), other_feat)
                
                # 成功したらタイムスタンプを更新
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "UPDATE tracks SET features_extracted_at = ?, status = 'features_extracted' WHERE track_id = ?",
                    (now, track_id)
                )
                conn.commit()
                success_count += 1
                
            except Exception as e:
                error_msg = f"Track {track_id} の特徴量抽出に失敗しました: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                
        print("処理が完了しました。")
        if success_count == 0:
            print("エラー: すべてのトラックの特徴量抽出に失敗しました。")
            sys.exit(1)

if __name__ == "__main__":
    run()
