"""
EDMサブジャンル自動判定システム — プレイリストAI自動判定テストスクリプト

指定された SoundCloud プレイリスト/楽曲 URL から音源を取得し、
Demucs分離 ➔ 特徴量抽出 ➔ 学習済みXGBoostモデルによるAIジャンル推論を一括実行し、
結果を端末およびデータベースに反映します。
"""

import sys
import sqlite3
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windowsの標準出力エンコーディング対策
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from src.config import settings
from src.collectors.soundcloud import fetch_candidate_tracks, passes_prefilter, download_track
from src.separation.separator import separate_track
from src.features.drums import extract_drums_features
from src.features.bass import extract_bass_features
from src.features.subbass import extract_subbass_features
from src.features.other import extract_other_features
from src.models.infer import predict_genre
import numpy as np

GENRE_EMOJIS = {
    'heavy_dubstep':    '💥',
    'color_bass':       '🎨',
    'riddim':           '🔁',
    'briddim':          '🌋',
    'bass_house':       '🏠',
    'future_bass':      '🌊',
    'melodic_dubstep':  '✨',
    'progressive_house':'🏟',
    'drum_and_bass':    '🥁',
    'trap':             '🎪',
}


def process_playlist_ai(playlist_url: str, max_tracks: int = 10):
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    raw_dir = Path(settings.project_root) / settings.paths.raw_audio
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🔍 SoundCloud プレイリストのメタデータを取得中... ({playlist_url})")
    candidates = fetch_candidate_tracks(playlist_url, max_downloads=max_tracks)

    if not candidates:
        print("❌ 有効なトラックが見つかりませんでした。URLを確認してください。")
        return

    print(f"🎵 {len(candidates)} 件のトラックを抽出しました。AI判定処理を開始します...\n")

    results = []

    for item in candidates:
        url = item['url']
        title = item['title']
        uploader = item['uploader']
        duration = item.get('duration', 0)

        # 事前フィルタチェック (10分超の長尺Mixのみスキップ)
        duration = item.get('duration', 0)
        if duration > 600:
            print(f"⏩ スキップ (10分超の長尺Mix): {title}")
            continue
        if 0 < duration < 40:
            print(f"⏩ スキップ (40秒未満の試聴音源): {title}")
            continue

        track_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:16]

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # すでにDBに登録があるか確認
            cursor.execute("SELECT track_id, ai_label, ai_confidence FROM tracks WHERE track_id = ?", (track_id,))
            existing = cursor.fetchone()

        raw_path = raw_dir / f"{track_id}.wav"

        # 1. 音声ダウンロード
        if not raw_path.exists():
            print(f"⬇ ダウンロード中: {uploader} - {title}...")
            dl_success = download_track(url, track_id)
            if not dl_success:
                print(f"❌ ダウンロード失敗: {title}")
                continue

        # DBへ基本情報を保存/更新
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO tracks (track_id, title, artist, source_url, genre_hint, raw_audio_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'downloaded', ?)
            """, (track_id, title, uploader, url, 'Test: playlist', str(raw_path), now))
            conn.commit()

        # 2. Demucs 音源分離
        stems_dir = Path(settings.project_root) / settings.paths.stems / track_id
        if not (stems_dir / "drums.wav").exists():
            print(f"🎛 音源分離中 (Demucs): {title}...")
            try:
                separate_track(track_id, str(raw_path))
                with sqlite3.connect(str(db_path)) as conn:
                    conn.execute("UPDATE tracks SET separated_at = ?, status = 'separated' WHERE track_id = ?", (now, track_id))
                    conn.commit()
            except Exception as e:
                print(f"❌ 音源分離失敗: {e}")
                continue

        # 3. 特徴量抽出
        feat_dir = Path(settings.project_root) / settings.paths.features / track_id
        feat_dir.mkdir(parents=True, exist_ok=True)
        if not (feat_dir / "drums.npy").exists():
            print(f"📊 特徴量抽出中: {title}...")
            try:
                drums_f = extract_drums_features(str(stems_dir / "drums.wav"))
                bass_f = extract_bass_features(str(stems_dir / "bass.wav"))
                sub_f = extract_subbass_features(str(stems_dir / "subbass.wav"))
                other_f = extract_other_features(str(stems_dir / "other.wav"))

                np.save(str(feat_dir / "drums.npy"), drums_f)
                np.save(str(feat_dir / "bass.npy"), bass_f)
                np.save(str(feat_dir / "subbass.npy"), sub_f)
                np.save(str(feat_dir / "other.npy"), other_f)

                with sqlite3.connect(str(db_path)) as conn:
                    conn.execute("UPDATE tracks SET features_extracted_at = ?, status = 'features_extracted' WHERE track_id = ?", (now, track_id))
                    conn.commit()
            except Exception as e:
                print(f"❌ 特徴量抽出失敗: {e}")
                continue

        # 4. XGBoost AIモデル推論
        print(f"🤖 AIジャンル判定中: {title}...")
        try:
            probs = predict_genre(track_id)
            sorted_genres = sorted(probs.items(), key=lambda x: x[1], reverse=True)
            top_genre, confidence = sorted_genres[0]

            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tracks
                    SET ai_label = ?, ai_confidence = ?, classified_at = ?, status = 'classified'
                    WHERE track_id = ?
                """, (top_genre, confidence, now, track_id))

                for g_label, p in probs.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO genre_probabilities (track_id, genre_label, probability, model_version, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (track_id, g_label, float(p), settings.model_version, now))
                conn.commit()

            results.append({
                'title': title,
                'artist': uploader,
                'top_genre': top_genre,
                'confidence': confidence,
                'probs': probs
            })

        except Exception as e:
            print(f"❌ AI判定失敗: {e}")
            continue

    # レポート表示
    print("\n" + "=" * 60)
    print(" 🤖 SoundCloud プレイリスト AIジャンル自動判定レポート ")
    print("=" * 60)

    for i, res in enumerate(results, 1):
        emoji = GENRE_EMOJIS.get(res['top_genre'], '🎵')
        conf_pct = round(res['confidence'] * 100, 1)
        print(f"\n【#{i}】 {res['artist']} - {res['title']}")
        print(f"  AI判定 ➔ {emoji} {res['top_genre'].upper()} ({conf_pct}%)")

        sorted_p = sorted(res['probs'].items(), key=lambda x: x[1], reverse=True)[:4]
        prob_str = " | ".join([f"{g}: {round(p*100)}%" for g, p in sorted_p if round(p*100) > 0])
        print(f"  確信度分布: [ {prob_str} ]")

    print("\n" + "=" * 60)
    print(f"✅ AI判定完了: 全 {len(results)} 曲の推論が終了し、Webダッシュボード (http://localhost:8000/) に保存されました。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SoundCloudプレイリストのAIジャンル自動判定テスト")
    parser.add_argument("url", type=str, help="SoundCloudのプレイリスト/トラックURL")
    parser.add_argument("--max-tracks", type=int, default=5, help="最大処理曲数 (デフォルト: 5)")
    args = parser.parse_args()

    process_playlist_ai(args.url, max_tracks=args.max_tracks)
