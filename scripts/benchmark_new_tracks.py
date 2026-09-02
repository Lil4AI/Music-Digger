import sys
import os
import json
import urllib.request
import urllib.parse
import hashlib
import sqlite3
import re
import joblib
from pathlib import Path

# Project root path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.config import settings
from src.collectors.soundcloud import CLIENT_ID, HEADERS, download_track
from src.features.drums import extract_drums_features
from src.features.bass import extract_bass_features
from src.features.subbass import extract_subbass_features
from src.features.other import extract_other_features
import numpy as np

# 既存DBから重複を排除するためのロード
def get_existing_db_urls():
    db_path = Path(settings.project_root) / "db" / "edm_classifier.db"
    if not db_path.exists():
        return set()
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        urls = set(row[0] for row in cursor.execute("SELECT source_url FROM tracks WHERE source_url IS NOT NULL").fetchall())
        return urls

# SoundCloudから新曲を検索
def search_new_tracks_for_genre(genre: str, count: int = 5, existing_urls: set = None):
    if existing_urls is None:
        existing_urls = set()
        
    query_map = {
        'heavy_dubstep': 'heavy dubstep original',
        'trap': 'trap edm original',
        'bass_house': 'bass house vip',
        'riddim': 'riddim dubstep original',
        'briddim': 'briddim dubstep',
        'future_bass': 'future bass original',
        'melodic_dubstep': 'melodic dubstep original',
        'drum_and_bass': 'drum and bass original',
        'color_bass': 'color bass original',
        'progressive_house': 'progressive house original'
    }
    
    q = query_map.get(genre, f"{genre} edm")
    encoded_q = urllib.parse.quote(q)
    search_url = f"https://api-v2.soundcloud.com/search/tracks?q={encoded_q}&client_id={CLIENT_ID}&limit=30"
    
    found_tracks = []
    req = urllib.request.Request(search_url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for item in data.get('collection', []):
                web_url = item.get('permalink_url')
                title = item.get('title', '')
                duration = item.get('duration', 0) / 1000.0
                uploader = item.get('user', {}).get('username', 'Unknown Artist')
                
                if not web_url or web_url in existing_urls:
                    continue
                    
                # Mixや長尺/短尺を除外
                if duration > 600 or duration < 90:
                    continue
                    
                exclude_pattern = r'(\b(mix|mixtape|megamix|podcast|guest|b2b|set|radio|episode)\b)'
                if re.search(exclude_pattern, title.lower()) or re.search(exclude_pattern, web_url.lower()):
                    continue
                    
                found_tracks.append({
                    'title': title,
                    'artist': uploader,
                    'url': web_url,
                    'duration': duration,
                    'expected_genre': genre
                })
                
                if len(found_tracks) >= count:
                    break
    except Exception as e:
        print(f"Search failed for {genre}: {e}")
        
    return found_tracks

def run_benchmark():
    print("==================================================")
    print("[BENCHMARK TEST] AI Classifier Evaluation on New Unimported Tracks")
    print("==================================================")
    
    existing_urls = get_existing_db_urls()
    print(f"Existing DB track count: {len(existing_urls)} (will be excluded from benchmark)")
    
    genres_to_test = [
        'heavy_dubstep', 'trap', 'bass_house', 'riddim', 
        'briddim', 'melodic_dubstep', 'drum_and_bass', 'color_bass'
    ]
    
    # テンポラリフォルダ準備
    benchmark_dir = Path(settings.project_root) / "storage" / "temp_benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    
    # 学習済みモデルロード
    model_path = Path(settings.project_root) / "models" / "fusion_classifier_v1.pkl"
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        return
        
    model_pipeline = joblib.load(str(model_path))
    
    results = []
    
    for g in genres_to_test:
        print(f"\n🔍 Searching 3 new benchmark tracks for genre: {g.upper()}...")
        new_tracks = search_new_tracks_for_genre(g, count=3, existing_urls=existing_urls)
        print(f"Found {len(new_tracks)} new candidate tracks.")
        
        for idx, tr in enumerate(new_tracks, 1):
            track_id = f"bench_{hashlib.sha256(tr['url'].encode()).hexdigest()[:12]}"
            title = tr['title']
            artist = tr['artist']
            
            print(f" [{idx}/{len(new_tracks)}] Downloading & Testing: {artist} - {title[:30]} ... ", end="", flush=True)
            
            # 音声ファイルをテンポラリにダウンロード
            wav_path = benchmark_dir / f"{track_id}.wav"
            ok = download_track(tr['url'], track_id)
            
            # download_track は storage/raw_audio/ に保存するため移動
            default_wav = Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav"
            if default_wav.exists():
                default_wav.rename(wav_path)
                
            if not wav_path.exists():
                print("FAILED (Download error)")
                continue
                
            try:
                # 生音源から高速特徴量を抽出 (4ブランチ疑似ダミー抽出で高速推論)
                # drums, bass, subbass, other
                f_drums = extract_drums_features(str(wav_path))
                f_bass = extract_bass_features(str(wav_path))
                f_sub = extract_subbass_features(str(wav_path))
                f_other = extract_other_features(str(wav_path))
                
                X_dict = {
                    "drums": np.array([f_drums]),
                    "bass": np.array([f_bass]),
                    "subbass": np.array([f_sub]),
                    "other": np.array([f_other])
                }
                
                # 推論実行
                probs_arr = model_pipeline.predict_proba(X_dict)[0]
                raw_classes = model_pipeline.clf.classes_ if hasattr(model_pipeline, 'clf') and hasattr(model_pipeline.clf, 'classes_') else list(range(len(settings.genre_labels)))
                
                probs = {}
                for c_idx, cls_val in enumerate(raw_classes):
                    g_name = settings.genre_labels[int(cls_val)] if str(cls_val).isdigit() else str(cls_val)
                    probs[g_name] = float(probs_arr[c_idx])
                    
                sorted_p = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                top_genre, top_conf = sorted_p[0]
                
                results.append({
                    'expected': g,
                    'predicted': top_genre,
                    'confidence': top_conf,
                    'title': title,
                    'artist': artist,
                    'url': tr['url']
                })
                
                print(f"OK -> AI Predicted: {top_genre.upper()} ({top_conf*100:.1f}%)")
                
            except Exception as ex:
                print(f"FAILED (Feature error: {ex})")
            finally:
                # テンポラリ音声ファイル削除 (DB未登録・クリーンアップ)
                if wav_path.exists():
                    try:
                        wav_path.unlink()
                    except Exception:
                        pass

    # ベンチマークレポート表示
    print("\n==================================================")
    print("📊 BENCHMARK PREDICTION REPORT (No DB Changes)")
    print("==================================================")
    
    correct_count = 0
    for i, r in enumerate(results, 1):
        is_match = (r['expected'].lower() == r['predicted'].lower())
        if is_match:
            correct_count += 1
        status_icon = "✅" if is_match else "❌"
        print(f"[{i:02d}] {status_icon} Expected: {r['expected'].upper():15s} | AI Predicted: {r['predicted'].upper():15s} ({r['confidence']*100:.1f}%) | {r['artist']} - {r['title'][:25]}")
        
    acc = (correct_count / len(results) * 100) if results else 0
    print(f"\n🎯 Benchmark Accuracy on New Unknown Tracks: {correct_count} / {len(results)} ({acc:.1f}%)")
    print("==================================================")

if __name__ == '__main__':
    run_benchmark()
