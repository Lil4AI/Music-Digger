"""
EDMサブジャンル自動判定システム — 楽曲収集バッチ

SoundCloudのユーザーURLからトラック情報を取得し、
条件を満たすものをダウンロードしてDBに登録する。
"""

import sys
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.collectors.soundcloud import fetch_candidate_tracks, passes_prefilter, download_track

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "collection.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run(target_url: str):
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    print(f"URLからトラックを取得中: {target_url}")
    candidates = fetch_candidate_tracks(target_url, max_downloads=10)
    
    if not candidates:
        print("トラックが見つかりませんでした。")
        return
        
    print(f"{len(candidates)} 件の候補が見つかりました。")
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        for track in candidates:
            # 事前フィルタ
            if not passes_prefilter(track):
                print(f"スキップ: {track['title']} (フィルタ除外)")
                continue
                
            track_id = f"sc_{track['id']}"
            
            # 既に存在するかチェック
            cursor.execute("SELECT 1 FROM tracks WHERE track_id = ?", (track_id,))
            if cursor.fetchone():
                print(f"スキップ: {track['title']} (既に存在)")
                continue
                
            print(f"ダウンロード開始: {track['title']}")
            success = download_track(track['url'], track_id)
            
            if success:
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                raw_audio_path = str(Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav")
                cursor.execute(
                    '''INSERT INTO tracks (track_id, source, source_url, status, raw_audio_path, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (track_id, 'soundcloud', track['url'], 'collected', raw_audio_path, now)
                )
                conn.commit()
                print(" -> 完了")
                logging.info(f"Collected track: {track_id} - {track['title']}")
            else:
                print(" -> 失敗")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        # デフォルトのテスト用URL (例: 特定のアーティスト)
        target = "https://soundcloud.com/skrillex"
    
    run(target)
