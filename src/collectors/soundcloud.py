import yt_dlp
import logging
import re
from pathlib import Path
from src.config import settings

def fetch_candidate_tracks(playlist_or_user_url: str, max_downloads: int = 10) -> list:
    """
    SoundCloudのプレイリストやユーザーURLからトラックのメタデータを取得する。
    """
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'playlistend': max_downloads,
    }
    
    candidates = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(playlist_or_user_url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        candidates.append({
                            'id': entry.get('id', ''),
                            'title': entry.get('title', 'Unknown Title'),
                            'url': entry.get('url', ''),
                            'duration': entry.get('duration', 0),
                            'uploader': entry.get('uploader', 'Unknown')
                        })
            else:
                candidates.append({
                    'id': info.get('id', ''),
                    'title': info.get('title', 'Unknown Title'),
                    'url': info.get('webpage_url', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown')
                })
        except Exception as e:
            logging.error(f"メタデータの取得に失敗しました ({playlist_or_user_url}): {e}")
            
    return candidates

def passes_prefilter(track_meta: dict) -> bool:
    """
    明らかにEDMトラックではないもの（Mix、Podcast等）を除外する。
    """
    title = track_meta.get('title', '').lower()
    duration = track_meta.get('duration') or 0
    
    # 10分以上の曲はMixとみなす
    if duration > 600:
        return False
        
    # キーワード除外 (単語境界を使用して "Sunset" のような誤爆を防ぐ)
    exclude_pattern = r'\b(mix|podcast|guest|b2b|set)\b'
    if re.search(exclude_pattern, title):
        return False
        
    return True

def download_track(original_url: str, track_id: str) -> bool:
    """
    yt-dlp を用いて SoundCloud から音源をダウンロードし、WAV形式で保存する。
    """
    output_dir = Path(settings.project_root) / settings.paths.raw_audio
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # yt-dlp は拡張子を自動補完するため、出力テンプレートから拡張子を省く
    outtmpl = str(output_dir / f"{track_id}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([original_url])
            return True
        except Exception as e:
            logging.error(f"ダウンロード失敗 ({original_url}): {e}")
            return False
