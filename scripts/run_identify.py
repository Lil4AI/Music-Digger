"""
EDMサブジャンル自動判定システム — Apple Music ID照合バッチ

DB上の ai_label が 'tearout' かつ apple_music_id IS NULL のトラックを抽出し、
Apple MusicのCatalog SearchまたはAudDで照合し、取得できたIDをDBに保存する。
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

from src.config import settings
from src.identify.apple_music import generate_developer_token, search_catalog, identify_via_audd

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "identify.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run():
    dev_token = generate_developer_token()
    if not dev_token:
        print("Developer Tokenが生成できないため終了します。環境変数を確認してください。")
        return

    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT track_id FROM tracks WHERE ai_label = 'tearout' AND apple_music_id IS NULL")
        rows = cursor.fetchall()
        
        if not rows:
            print("照合対象のトラックはありません。")
            return
            
        print(f"{len(rows)} 件のトラックのApple Music照合を開始します...")
        
        for row in tqdm(rows, desc="Identify"):
            track_id = row['track_id']
            # DBからタイトル等のメタデータは保存していないため、ファイルシステムから直接WAVを使うか、
            # もしくはダミーでトラックIDをベースに検索する。
            # 通常はDBにメタデータ(title, artist)が入っている想定。
            # 今回は音響指紋(AudD)をメインのフォールバックとして試す。
            
            # TODO: DBから title/artist を取得するロジック（現在スキーマにない場合は拡張が必要）
            # ここでは AudD を用いた照合を優先する。
            
            raw_audio_path = Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav"
            am_id = ""
            
            if raw_audio_path.exists():
                am_id = identify_via_audd(str(raw_audio_path))
                
            if am_id:
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "UPDATE tracks SET apple_music_id = ?, identified_at = ?, status = 'identified' WHERE track_id = ?",
                    (am_id, now, track_id)
                )
                conn.commit()
                logging.info(f"Identified {track_id} -> {am_id}")
            else:
                logging.warning(f"Track {track_id} の照合に失敗しました。")
                
        print("照合が完了しました。")

if __name__ == "__main__":
    run()
