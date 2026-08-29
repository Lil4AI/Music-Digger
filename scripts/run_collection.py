"""
EDMサブジャンル自動判定システム — 楽曲収集バッチ

config/seed_djs.txt（フォーマット: ジャンル|SoundCloud_URL）を読み込み、
各アーティストの曲をダウンロードしてDBに登録する。
ジャンルラベルは収集時に human_label へ自動セット。
"""

import sys
import sqlite3
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Windowsの標準出力エンコーディング対策
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# プロジェクトルートを sys.path に追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def parse_seed_file(seed_path: Path) -> list[tuple[str, str]]:
    """
    seed_djs.txt を読み込み、(genre_label, url) のリストを返す。
    フォーマット: genre_label|https://soundcloud.com/...
    「#」で始まる行・空行は無視。
    """
    entries = []
    for line in seed_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            logging.warning(f"フォーマット不正のためスキップ: {line}")
            continue
        genre, url = line.split("|", 1)
        entries.append((genre.strip(), url.strip()))
    return entries


def collect_from_artist(genre: str, artist_url: str, max_downloads: int,
                        db_path: Path, valid_genres: list[str]) -> tuple[int, int]:
    """
    1アーティストの曲を収集しDBに登録する。
    戻り値: (success_count, skip_count)
    """
    if genre not in valid_genres:
        print(f"  ⚠ 不明なジャンル '{genre}' — settings.yaml の genre_labels を確認してください")
        return 0, 0

    print(f"\n📂 [{genre}] {artist_url}")
    candidates = fetch_candidate_tracks(artist_url, max_downloads=max_downloads)

    if not candidates:
        print("  トラックが見つかりませんでした。")
        return 0, 0

    print(f"  {len(candidates)} 件の候補")
    success = 0
    skipped = 0

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        for track in candidates:
            if not passes_prefilter(track):
                skipped += 1
                continue

            track_id = hashlib.sha256(track["url"].encode()).hexdigest()[:16]

            # 重複チェック
            cursor.execute("SELECT 1 FROM tracks WHERE track_id = ?", (track_id,))
            if cursor.fetchone():
                skipped += 1
                continue

            print(f"  ⬇ {track['title']}", end=" ... ", flush=True)
            ok = download_track(track["url"], track_id)

            if ok:
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                raw_path = str(
                    Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav"
                )
                artist_name = track.get("uploader", "Unknown Artist")
                cursor.execute(
                    """INSERT INTO tracks
                       (track_id, source, source_url, title, artist,
                        status, raw_audio_path, genre_hint, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (track_id, "soundcloud", track["url"], track["title"],
                     artist_name, "collected", raw_path, f"Seed: {genre}", now),
                )
                conn.commit()
                print("✅")
                logging.info(f"Collected [{genre}]: {track_id} - {track['title']}")
                success += 1
            else:
                print("❌")
                logging.warning(f"Download failed: {track['url']}")

    return success, skipped


def run(target_url: str = "", max_downloads: int = 10, target_genre: str = ""):
    """
    メイン実行関数。
    - target_url が指定された場合: そのURLのみ収集（ジャンルは 'unknown'）
    - 未指定の場合: seed_djs.txt を全件処理（target_genreでフィルタ可）
    """
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    valid_genres = [g.lower() for g in settings.genre_labels]

    if target_url:
        # 単一URL指定モード（後方互換）
        collect_from_artist("unknown", target_url, max_downloads, db_path, valid_genres + ["unknown"])
        return

    # seed_djs.txt 一括モード
    seed_path = Path(settings.project_root) / "config" / "seed_djs.txt"
    if not seed_path.exists():
        print(f"エラー: {seed_path} が見つかりません。")
        sys.exit(1)

    entries = parse_seed_file(seed_path)
    if target_genre:
        entries = [(g, u) for g, u in entries if g.lower() == target_genre.lower()]
        
    if not entries:
        print(f"対象のシードエントリがありません (target_genre={target_genre})。")
        sys.exit(0)

    print(f"🎵 {len(entries)} アーティストから収集を開始します（各最大 {max_downloads} 曲）\n")
    total_success = 0
    total_skipped = 0

    for genre, url in entries:
        s, sk = collect_from_artist(genre, url, max_downloads, db_path, valid_genres)
        total_success += s
        total_skipped += sk

    print(f"\n✅ 収集完了: {total_success} 件取得, {total_skipped} 件スキップ")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SoundCloudから楽曲を収集・ダウンロードします")
    parser.add_argument("url", type=str, nargs="?", default="",
                        help="単一URLを指定（省略時は seed_djs.txt を全件処理）")
    parser.add_argument("--max-downloads", type=int, default=10,
                        help="1アーティストあたりの最大ダウンロード件数 (デフォルト: 10)")
    parser.add_argument("--target-genre", type=str, default="",
                        help="特定のジャンルシード（例: trap, riddim）のみ収集")
    args = parser.parse_args()
    run(args.url, max_downloads=args.max_downloads, target_genre=args.target_genre)
