"""
EDMサブジャンル自動判定システム — 推論バッチ

DB上の classified_at IS NULL (または human_label IS NULL) かつ
特徴量抽出済みのトラックに対して推論を行い、結果(AIラベルと確信度)を保存する。
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

from src.config import settings
from src.models.infer import predict_genre

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "inference.log"
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
        
        # 特徴量抽出済みで、かつ人間によるラベルがなく、かつ未分類のものを対象とする
        cursor.execute('''
            SELECT track_id FROM tracks 
            WHERE features_extracted_at IS NOT NULL 
              AND human_label IS NULL 
              AND classified_at IS NULL
        ''')
        rows = cursor.fetchall()
        
        if not rows:
            print("推論対象のトラックはありません。")
            return
            
        print(f"{len(rows)} 件のトラックのジャンル推論を開始します...")
        
        for row in tqdm(rows, desc="Inference"):
            track_id = row['track_id']
            try:
                probs = predict_genre(track_id)
                
                # 確率が高い方をAIラベルとする
                if probs['tearout'] >= 0.5:
                    ai_label = 'tearout'
                    confidence = probs['tearout']
                else:
                    ai_label = 'riddim'
                    confidence = probs['riddim']
                
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''UPDATE tracks 
                       SET ai_label = ?, ai_confidence = ?, classified_at = ?, status = 'classified' 
                       WHERE track_id = ?''',
                    (ai_label, confidence, now, track_id)
                )
                conn.commit()
                
            except Exception as e:
                logging.error(f"Track {track_id} の推論に失敗: {e}")
                
        print("推論が完了しました。")

if __name__ == "__main__":
    run()
