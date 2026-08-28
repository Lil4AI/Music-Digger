"""
EDMサブジャンル自動判定システム — ジャンルリサーチ

DBに登録済みのトラックに対し、Last.fm APIを使ってジャンルヒントを自動収集し
tracks.genre_hint カラムに書き込む。

実行前提:
  .env に LASTFM_API_KEY が設定されていること。
  Last.fm APIキーの無料取得: https://www.last.fm/api/account/create
"""

import sqlite3
import logging
import time
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "genre_research.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
REQUEST_DELAY_SEC = 0.3  # Last.fm の制限: 5リクエスト/秒を超えない


def fetch_lastfm_tags(artist: str, title: str, api_key: str) -> list[str]:
    """
    Last.fm APIでトラックのタグ（ジャンル）を取得する。
    取得できなければ空リストを返す。
    """
    params = {
        "method": "track.getInfo",
        "api_key": api_key,
        "artist": artist,
        "track": title,
        "format": "json",
        "autocorrect": "1",
    }
    url = LASTFM_API_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        track_data = data.get("track", {})
        tags_data = track_data.get("toptags", {}).get("tag", [])
        tags = [t["name"] for t in tags_data if isinstance(t, dict)]
        return tags[:10]  # 上位10タグ
    except Exception as e:
        logging.warning(f"Last.fm fetch failed for '{artist} - {title}': {e}")
        return []


def fetch_lastfm_artist_tags(artist: str, api_key: str) -> list[str]:
    """
    トラックタグが取れなかった場合のフォールバック: アーティストタグを取得。
    """
    params = {
        "method": "artist.getInfo",
        "api_key": api_key,
        "artist": artist,
        "format": "json",
        "autocorrect": "1",
    }
    url = LASTFM_API_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        tags_data = data.get("artist", {}).get("tags", {}).get("tag", [])
        tags = [t["name"] for t in tags_data if isinstance(t, dict)]
        return tags[:5]
    except Exception as e:
        logging.warning(f"Last.fm artist fetch failed for '{artist}': {e}")
        return []


def build_hint_text(track_tags: list[str], artist_tags: list[str]) -> str | None:
    """タグリストからジャンルヒント文字列を組み立てる。"""
    parts = []
    if track_tags:
        parts.append("Last.fm(曲): " + ", ".join(track_tags))
    if artist_tags:
        parts.append("Last.fm(アーティスト): " + ", ".join(artist_tags))
    return " | ".join(parts) if parts else None


def run():
    api_key = settings.secrets.lastfm_api_key if hasattr(settings.secrets, "lastfm_api_key") else None
    if not api_key:
        print("エラー: LASTFM_API_KEY が .env に設定されていません。")
        print("取得先: https://www.last.fm/api/account/create")
        return

    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # genre_hint が未設定かつ title/artist が揃っているトラックを対象
        cursor.execute("""
            SELECT track_id, title, artist FROM tracks
            WHERE genre_hint IS NULL
              AND researched_at IS NULL
              AND title IS NOT NULL
              AND artist IS NOT NULL
        """)
        rows = cursor.fetchall()

    if not rows:
        print("リサーチ対象のトラックはありません。")
        return

    print(f"{len(rows)} 件のトラックをリサーチします...")
    success = 0
    skipped = 0

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        for i, row in enumerate(rows, 1):
            track_id = row["track_id"]
            title    = row["title"] or ""
            artist   = row["artist"] or ""

            print(f"[{i}/{len(rows)}] {artist} - {title}", end=" ... ", flush=True)

            # トラックタグ取得
            track_tags = fetch_lastfm_tags(artist, title, api_key)
            time.sleep(REQUEST_DELAY_SEC)

            # フォールバック: アーティストタグ
            artist_tags = []
            if not track_tags:
                artist_tags = fetch_lastfm_artist_tags(artist, api_key)
                time.sleep(REQUEST_DELAY_SEC)

            hint = build_hint_text(track_tags, artist_tags)
            now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                "UPDATE tracks SET genre_hint = ?, researched_at = ? WHERE track_id = ?",
                (hint, now, track_id)
            )
            conn.commit()

            if hint:
                print(f"OK ({len(track_tags)} track tags, {len(artist_tags)} artist tags)")
                logging.info(f"{track_id} | {artist} - {title} | {hint}")
                success += 1
            else:
                print("ヒントなし（タグ未登録）")
                skipped += 1

    print(f"\n完了: {success} 件成功, {skipped} 件ヒントなし")


if __name__ == "__main__":
    run()
