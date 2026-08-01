"""
EDMサブジャンル自動判定システム — 楽曲収集バッチ

SoundCloudのユーザーURLからトラック情報を取得し、
条件を満たすものをダウンロードしてDBに登録する。
"""

import sys
import sqlite3
import logging
import hashlib
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

def run(target_url: str, max_downloads: int = 10):
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    print(f"URLからトラックを取得中: {target_url} (最大取得件数: {max_downloads})")
    candidates = fetch_candidate_tracks(target_url, max_downloads=max_downloads)
    
    if not candidates:
        print("トラックが見つかりませんでした。")
        sys.exit(1)
        
    print(f"{len(candidates)} 件の候補が見つかりました。")
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        success_count = 0
        attempt_count = 0
        
        for track in candidates:
            # 事前フィルタ
            if not passes_prefilter(track):
                print(f"スキップ: {track['title']} (フィルタ除外)")
                continue
                
            track_id = hashlib.sha256(track['url'].encode()).hexdigest()[:16]
            
            # 既に存在するかチェック
            cursor.execute("SELECT 1 FROM tracks WHERE track_id = ?", (track_id,))
            if cursor.fetchone():
                print(f"スキップ: {track['title']} (既に存在)")
                continue
                
            attempt_count += 1
            print(f"ダウンロード開始: {track['title']}")
            success = download_track(track['url'], track_id)
            
            if success:
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                raw_audio_path = str(Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav")
                cursor.execute(
                    '''INSERT INTO tracks (track_id, source, source_url, title, artist, status, raw_audio_path, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (track_id, 'soundcloud', track['url'], track['title'], track.get('user', {}).get('username', 'Unknown Artist'), 'collected', raw_audio_path, now)
                )
                conn.commit()
                print(" -> 完了")
                logging.info(f"Collected track: {track_id} - {track['title']}")
                success_count += 1
            else:
                print(" -> 失敗")

        if attempt_count > 0 and success_count == 0:
            print("新たに収集したトラックはありませんでした（処理は継続します）。")
            sys.exit(0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SoundCloudから楽曲を収集・ダウンロードします")
    parser.add_argument("url", type=str, nargs="?", default="https://soundcloud.com/skrillex", help="収集対象のSoundCloud URL")
    parser.add_argument("--max-downloads", type=int, default=10, help="最大ダウンロード件数 (デフォルト: 10)")
    
    args = parser.parse_args()
    run(args.url, max_downloads=args.max_downloads)
