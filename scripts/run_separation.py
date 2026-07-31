"""
EDMサブジャンル自動判定システム — ステム分離バッチ処理

DBから separated_at IS NULL の track を全件取得し、
各トラックに対して Demucs で分離し、完了したら separated_at を更新する。
"""

import sqlite3
import logging
import traceback
import sys
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

from src.config import settings
from src.separation.separator import separate_track

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "separation.log"
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
        
        # 処理対象を取得
        cursor.execute("SELECT track_id, raw_audio_path FROM tracks WHERE separated_at IS NULL AND raw_audio_path IS NOT NULL")
        rows = cursor.fetchall()
        
        if not rows:
            print("処理対象のトラックはありません。")
            return
            
        print(f"{len(rows)} 件のトラックを分離します...")
        success_count = 0
        
        for row in tqdm(rows, desc="Stem Separation"):
            track_id = row['track_id']
            raw_audio_path = row['raw_audio_path']
            
            try:
                # 分離処理
                separate_track(track_id, raw_audio_path)
                
                # 成功したらタイムスタンプを更新
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "UPDATE tracks SET separated_at = ?, status = 'separated' WHERE track_id = ?",
                    (now, track_id)
                )
                conn.commit()
                success_count += 1
                
            except Exception as e:
                # 失敗時はログに記録してスキップ
                error_msg = f"Track {track_id} の分離に失敗しました: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                
        print("処理が完了しました。")
        if success_count == 0:
            print("エラー: すべてのトラックの分離に失敗しました。")
            sys.exit(1)

if __name__ == "__main__":
    run()
