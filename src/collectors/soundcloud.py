import yt_dlp
import logging
import re
from pathlib import Path
from src.config import settings

def fetch_candidate_tracks(playlist_or_user_url: str, max_downloads: int = 10) -> list:
    """
    SoundCloudのプレイリストやユーザーURLからトラックのメタデータを取得する。
    ユーザーURLの場合は自動的に /tracks を付与して単一楽曲トラックのみを取得対象にする。
    """
    target_url = playlist_or_user_url.rstrip('/')
    if 'soundcloud.com/' in target_url and not any(target_url.endswith(x) for x in ['/tracks', '/popular-tracks', '/sets']):
        # SoundCloudユーザーTOPの場合、単曲トラックタブ (/tracks) を明示指定
        if target_url.count('/') == 3:  # https://soundcloud.com/username
            target_url += '/tracks'

    ydl_opts = {
        'quiet': True,
        'playlistend': max_downloads,
    }
    
    candidates = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(target_url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        web_url = entry.get('webpage_url') or entry.get('url', '')
                        title = entry.get('title', 'Unknown Title')
                        uploader = entry.get('uploader') or entry.get('uploader_id') or ''
                        if not uploader and ' - ' in title:
                            uploader = title.split(' - ', 1)[0].strip()
                        if not uploader:
                            uploader = 'Unknown Artist'

                        candidates.append({
                            'id': entry.get('id', ''),
                            'title': title,
                            'url': web_url,
                            'duration': entry.get('duration', 0),
                            'uploader': uploader
                        })
            else:
                web_url = info.get('webpage_url') or info.get('url', '')
                title = info.get('title', 'Unknown Title')
                uploader = info.get('uploader') or info.get('uploader_id') or ''
                if not uploader and ' - ' in title:
                    uploader = title.split(' - ', 1)[0].strip()
                if not uploader:
                    uploader = 'Unknown Artist'

                candidates.append({
                    'id': info.get('id', ''),
                    'title': title,
                    'url': web_url,
                    'duration': info.get('duration', 0),
                    'uploader': uploader
                })
        except Exception as e:
            logging.error(f"メタデータの取得に失敗しました ({target_url}): {e}")
            
    return candidates

def passes_prefilter(track_meta: dict) -> bool:
    """
    明らかにEDMトラックではないもの、Mix、Podcast、セット商品（/sets/）を除外する。
    """
    url = track_meta.get('url', '').lower()
    title = track_meta.get('title', '').lower()
    duration = track_meta.get('duration') or 0
    
    # プレイリスト・アルバム・セット音源は除外
    if '/sets/' in url or '/albums/' in url or '/compilations/' in url:
        return False

    # 10分以上の長尺音源はMix/Setとみなして除外
    if duration > 600:
        return False
        
    # キーワード除外 (ミックス、ラジオ、ポッドキャスト、ライブセット等)
    exclude_pattern = r'(\b(mix|mixtape|megamix|podcast|guest|b2b|set|compilation|session|radio|episode|live at|boiler room)\b|ch\.\d+|vol\.\d+)'
    if re.search(exclude_pattern, title) or re.search(exclude_pattern, url):
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
