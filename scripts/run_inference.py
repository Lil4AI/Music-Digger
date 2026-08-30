"""
EDMサブジャンル自動判定システム — 推論バッチ

DB上の classified_at IS NULL (または human_label IS NULL) かつ
特徴量抽出済みのトラックに対して推論を行い、結果(AIラベルと確信度)を保存する。
"""

import sqlite3
import logging
import traceback
import sys
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
            
        print(f"{len(rows)} 件のトラックを推論します...")
        success_count = 0
        
        for row in tqdm(rows, desc="Inference"):
            track_id = row['track_id']
            try:
                probs = predict_genre(track_id)
                
                # 確率が高い方をAIラベルとする
                sorted_genres = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                ai_label, confidence = sorted_genres[0]
                
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                
                # トラック本体の更新
                cursor.execute(
                    '''UPDATE tracks 
                       SET ai_label = ?, ai_confidence = ?, classified_at = ?, status = 'classified' 
                       WHERE track_id = ?''',
                    (ai_label, confidence, now, track_id)
                )
                
                # 全ジャンルの確率を genre_probabilities テーブルに保存
                for genre_label, prob in probs.items():
                    cursor.execute(
                        '''INSERT INTO genre_probabilities 
                           (track_id, genre_label, probability, model_version, created_at)
                           VALUES (?, ?, ?, ?, ?)''',
                        (track_id, genre_label, prob, settings.model_version, now)
                    )
                    
                conn.commit()
                success_count += 1
                
            except Exception as e:
                logging.error(f"Track {track_id} の推論に失敗: {e}")
                
        print("処理が完了しました。")
        if success_count == 0:
            print("エラー: すべてのトラックの推論に失敗しました。")
            sys.exit(1)

if __name__ == "__main__":
    run()
