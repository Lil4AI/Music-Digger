import sys
from pathlib import Path

# プロジェクトルートパス追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import sqlite3
import hashlib
from datetime import datetime, timezone

from src.collectors.soundcloud import fetch_candidate_tracks, passes_prefilter, download_track
from src.config import settings

def collect_playlist(url: str, genre_label: str = "heavy_dubstep", max_downloads: int = 500):
    db_path = Path(settings.project_root) / "db" / "edm_classifier.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[FETCH] Playlist: {url} (Seed: {genre_label})")
    candidates = fetch_candidate_tracks(url, max_downloads=max_downloads)
    print(f"[FOUND] {len(candidates)} candidate tracks.")

    success = 0
    skipped = 0

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        for i, track in enumerate(candidates, 1):
            title = track.get("title", "Unknown Title")
            track_url = track.get("url", "")
            
            if not passes_prefilter(track):
                print(f"[{i}/{len(candidates)}] Skip (Filtered): {title}")
                skipped += 1
                continue

            track_id = hashlib.sha256(track_url.encode()).hexdigest()[:16]

            cursor.execute("SELECT 1 FROM tracks WHERE track_id = ?", (track_id,))
            if cursor.fetchone():
                print(f"[{i}/{len(candidates)}] Skip (In DB): {title}")
                skipped += 1
                continue

            print(f"[{i}/{len(candidates)}] Downloading: {title} ... ", end="", flush=True)
            ok = download_track(track_url, track_id)

            if ok:
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                raw_path = str(Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav")
                artist_name = track.get("uploader", "Unknown Artist")
                cursor.execute(
                    """INSERT INTO tracks
                       (track_id, source, source_url, title, artist,
                        status, raw_audio_path, genre_hint, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (track_id, "soundcloud", track_url, title,
                     artist_name, "collected", raw_path, f"Seed: {genre_label}", now),
                )
                conn.commit()
                print("OK (Registered)")
                success += 1
            else:
                print("FAILED")

    print(f"\n[DONE] Success: {success}, Skipped: {skipped}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://soundcloud.com/mildfre/sets/brostep"
    genre = sys.argv[2] if len(sys.argv) > 2 else "heavy_dubstep"
    collect_playlist(url, genre)
