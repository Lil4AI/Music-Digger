"""
EDMサブジャンル自動判定システム — Apple Music プレイリスト同期バッチ

DB上の apple_music_id IS NOT NULL かつ synced_at IS NULL のトラックを抽出し、
Apple Musicのプレイリストに追加する。
"""

import os
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

from src.config import settings
from src.identify.apple_music import generate_developer_token
from src.sync.musickit import add_to_playlist

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "sync.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run():
    dev_token = generate_developer_token()
    music_user_token = os.environ.get("APPLE_MUSIC_USER_TOKEN")
    playlist_id = os.environ.get("APPLE_MUSIC_PLAYLIST_ID")
    
    if not all([dev_token, music_user_token, playlist_id]):
        print("必要なトークンまたはプレイリストIDが環境変数に設定されていません。")
        return

    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT track_id, apple_music_id FROM tracks WHERE apple_music_id IS NOT NULL AND synced_at IS NULL")
        rows = cursor.fetchall()
        
        if not rows:
            print("同期対象のトラックはありません。")
            return
            
        print(f"{len(rows)} 件のトラックをプレイリストに同期します...")
        
        for row in tqdm(rows, desc="Sync Playlist"):
            track_id = row['track_id']
            am_id = row['apple_music_id']
            
            success = add_to_playlist(dev_token, music_user_token, playlist_id, am_id)
            
            if success:
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "UPDATE tracks SET synced_at = ?, status = 'synced' WHERE track_id = ?",
                    (now, track_id)
                )
                conn.commit()
                logging.info(f"Synced {track_id} (AM ID: {am_id}) to playlist {playlist_id}")
            else:
                logging.error(f"Sync failed for {track_id}")
                
        print("プレイリスト同期が完了しました。")

if __name__ == "__main__":
    run()
