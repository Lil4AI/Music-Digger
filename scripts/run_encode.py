"""
EDMサブジャンル自動判定システム — 音声エンコード処理
Web GUIのストリーミング再生負荷を下げるため、WAVをMP3に圧縮する。
"""

import sys
import sqlite3
import logging
from pathlib import Path

# static-ffmpegをインポートしてPATHに通す（pydubがffmpegを見つけられるようにする）
import static_ffmpeg
static_ffmpeg.add_paths()

from pydub import AudioSegment

from src.config import settings

# ログ設定
log_path = Path(settings.project_root) / settings.paths.logs / "encode.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def ensure_mp3(wav_path: Path, mp3_path: Path):
    """WAVが存在しMP3が存在しない場合のみエンコードする"""
    if not wav_path.exists():
        return False
    if mp3_path.exists():
        return True
    
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        audio = AudioSegment.from_wav(str(wav_path))
        # 128kbps mp3 で十分な音質かつ軽量
        audio.export(str(mp3_path), format="mp3", bitrate="128k")
        return True
    except Exception as e:
        logging.error(f"Failed to encode {wav_path}: {e}")
        return False

def run():
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 分離済みのトラックのみ対象
        cursor.execute("SELECT track_id, status FROM tracks WHERE separated_at IS NOT NULL")
        tracks = cursor.fetchall()

    if not tracks:
        print("エンコード対象のトラックがありません。")
        return

    print(f"{len(tracks)} 件のトラックのエンコードを確認します...")
    
    web_audio_dir = Path(settings.project_root) / settings.paths.web_audio
    raw_dir = Path(settings.project_root) / settings.paths.raw_audio
    stems_dir = Path(settings.project_root) / settings.paths.stems
    
    for track in tracks:
        track_id = track['track_id']
        print(f"[{track_id}] ", end="", flush=True)
        
        encoded_any = False
        
        # Raw audio
        raw_wav = raw_dir / f"{track_id}.wav"
        raw_mp3 = web_audio_dir / "raw" / f"{track_id}.mp3"
        if ensure_mp3(raw_wav, raw_mp3):
            encoded_any = True
            
        # Stems
        for stem in settings.stems:
            stem_wav = stems_dir / track_id / f"{stem}.wav"
            stem_mp3 = web_audio_dir / "stems" / track_id / f"{stem}.mp3"
            if ensure_mp3(stem_wav, stem_mp3):
                encoded_any = True
                
        if encoded_any:
            print("OK")
        else:
            print("スキップ (ファイル不在)")

if __name__ == "__main__":
    run()
