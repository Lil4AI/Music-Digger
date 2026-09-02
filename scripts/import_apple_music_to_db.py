import sys
from pathlib import Path

# Project root path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import sqlite3
import hashlib
import urllib.request
import json
import urllib.parse
from datetime import datetime, timezone

from scripts.parse_apple_music import parse_apple_music_playlist
from src.collectors.soundcloud import CLIENT_ID, HEADERS, download_track, passes_prefilter
from src.config import settings

def search_soundcloud_track(artist: str, title: str):
    """
    SoundCloud API v2 検索エンドポイントを用いて、アーティストと曲名からベストマッチのSoundCloud URLを取得する。
    """
    clean_artist = re.sub(r'\(.*?\)|\[.*?\]', '', artist).strip()
    clean_title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
    query = f"{clean_artist} {clean_title}".strip()
    
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://api-v2.soundcloud.com/search/tracks?q={encoded_query}&client_id={CLIENT_ID}&limit=5"
    
    req = urllib.request.Request(search_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            collection = data.get('collection', [])
            for item in collection:
                web_url = item.get('permalink_url')
                item_title = item.get('title', '')
                duration = item.get('duration', 0) / 1000.0
                
                # 簡単な事前検証（10分以上のMixは除外）
                if web_url and duration <= 600:
                    return {
                        'url': web_url,
                        'title': item_title,
                        'artist': item.get('user', {}).get('username', artist),
                        'duration': duration
                    }
    except Exception as e:
        print(f"SoundCloud Search failed for '{query}': {e}")
        
    return None

def import_apple_music_riddim_playlist(apple_music_url: str):
    print(f"==================================================")
    print(f"[Apple Music Import] Parsing playlist: {apple_music_url}")
    print(f"==================================================")
    
    tracks = parse_apple_music_playlist(apple_music_url)
    print(f"[FOUND] {len(tracks)} tracks from Apple Music.")
    
    db_path = Path(settings.project_root) / "db" / "edm_classifier.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = 0
    skipped = 0
    failed = 0
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        
        for i, tr in enumerate(tracks, 1):
            artist = tr['artist']
            title = tr['title']
            print(f"\n[{i}/{len(tracks)}] Searching SoundCloud for: {artist} - {title}")
            
            match = search_soundcloud_track(artist, title)
            if not match:
                print(f"  ❌ SoundCloud search returned no results.")
                failed += 1
                continue
                
            sc_url = match['url']
            sc_title = match['title']
            print(f"  🎯 Found match: {sc_title} ({sc_url})")
            
            track_id = hashlib.sha256(sc_url.encode()).hexdigest()[:16]
            
            # DB重複チェック
            cursor.execute("SELECT human_label FROM tracks WHERE track_id = ?", (track_id,))
            existing = cursor.fetchone()
            if existing:
                if not existing[0]:
                    # ラベルのみ 'riddim' で更新
                    cursor.execute("UPDATE tracks SET human_label = 'riddim', genre_hint = 'Seed: riddim' WHERE track_id = ?", (track_id,))
                    conn.commit()
                    print(f"  🏷️ Updated existing track in DB with human_label='riddim'")
                else:
                    print(f"  ⏭️ Already in DB with human_label='{existing[0]}'")
                skipped += 1
                continue
                
            # ダウンロード処理
            print(f"  📥 Downloading WAV audio ... ", end="", flush=True)
            ok = download_track(sc_url, track_id)
            if ok:
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO tracks (
                        track_id, title, artist, source, source_url, raw_audio_path,
                        genre_hint, human_label, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track_id,
                    sc_title,
                    match['artist'],
                    'soundcloud',
                    sc_url,
                    str(Path(settings.paths.raw_audio) / f"{track_id}.wav"),
                    'Seed: riddim',
                    'riddim',  # ユーザー指示によりすべて riddim ラベルを設定
                    'collected',
                    now
                ))
                conn.commit()
                print("OK (Registered as 'riddim')")
                success += 1
            else:
                print("FAILED")
                failed += 1
                
    print("\n==================================================")
    print(f"[COMPLETE] Success: {success}, Skipped: {skipped}, Failed: {failed}")
    print("==================================================")

import re

if __name__ == '__main__':
    apple_url = "https://music.apple.com/jp/playlist/og-riddim/pl.u-AkAmma9ixLEvqR5"
    import_apple_music_riddim_playlist(apple_url)
