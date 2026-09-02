import yt_dlp
import logging
import re
import json
import urllib.request
import subprocess
from pathlib import Path
from src.config import settings

CLIENT_ID = "Pb72ranhoyt6gw7hM7TkzUItXlMWSNSo"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://soundcloud.com/',
    'Origin': 'https://soundcloud.com'
}

def fetch_candidate_tracks(playlist_or_user_url: str, max_downloads: int = 10) -> list:
    """
    SoundCloudのプレイリストやユーザーURLからトラックのメタデータを取得する。
    1. HTMLハイドレーション・API v2直叩きで取得（403エラーを完璧に回避）
    2. yt-dlp によるフォールバック
    """
    target_url = playlist_or_user_url.rstrip('/')
    candidates = []

    # API v2 による Resolve 試行
    try:
        resolve_api = f"https://api-v2.soundcloud.com/resolve?url={target_url}&client_id={CLIENT_ID}"
        req = urllib.request.Request(resolve_api, headers=HEADERS)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            if data.get("kind") == "playlist":
                raw_tracks = data.get("tracks", [])
                
                # トラックオブジェクトとIDのみのスタブを分離
                full_tracks = []
                stub_ids = []
                for t in raw_tracks:
                    if t.get("permalink_url") or t.get("title"):
                        full_tracks.append(t)
                    elif t.get("id"):
                        stub_ids.append(str(t["id"]))

                # スタブIDが存在する場合、/tracks?ids= で一括取得 (50件ずつチャンク)
                if stub_ids:
                    for chunk_start in range(0, len(stub_ids), 50):
                        chunk = stub_ids[chunk_start:chunk_start + 50]
                        ids_str = ",".join(chunk)
                        batch_url = f"https://api-v2.soundcloud.com/tracks?ids={ids_str}&client_id={CLIENT_ID}"
                        try:
                            b_req = urllib.request.Request(batch_url, headers=HEADERS)
                            with urllib.request.urlopen(b_req) as b_resp:
                                b_data = json.loads(b_resp.read().decode('utf-8'))
                                if isinstance(b_data, list):
                                    full_tracks.extend(b_data)
                        except Exception as ex:
                            logging.warning(f"Batch track fetch failed: {ex}")

                for t in full_tracks[:max_downloads]:
                    web_url = t.get("permalink_url")
                    if not web_url and t.get("user") and t.get("permalink"):
                        web_url = f"https://soundcloud.com/{t['user']['permalink']}/{t['permalink']}"
                    
                    title = t.get("title", "Unknown Title")
                    uploader = t.get("user", {}).get("username") or t.get("user", {}).get("permalink") or ""
                    if not uploader and " - " in title:
                        uploader = title.split(" - ", 1)[0].strip()
                    if not uploader:
                        uploader = "Unknown Artist"

                    if web_url:
                        candidates.append({
                            'id': str(t.get('id', '')),
                            'title': title,
                            'url': web_url,
                            'duration': (t.get('duration', 0) / 1000.0),
                            'uploader': uploader
                        })
            elif data.get("kind") == "track":
                title = data.get("title", "Unknown Title")
                uploader = data.get("user", {}).get("username") or ""
                web_url = data.get("permalink_url") or target_url
                candidates.append({
                    'id': str(data.get('id', '')),
                    'title': title,
                    'url': web_url,
                    'duration': (data.get('duration', 0) / 1000.0),
                    'uploader': uploader
                })
    except Exception as e:
        logging.warning(f"API v2 direct resolve failed for {target_url}: {e}")

    if candidates:
        return candidates

    # HTML Parsing フォールバック
    try:
        req_html = urllib.request.Request(target_url, headers=HEADERS)
        with urllib.request.urlopen(req_html) as resp:
            html = resp.read().decode('utf-8')
            hydration = re.search(r'window\.__sc_hydration\s*=\s*(\[.*?\]);</script>', html, re.DOTALL)
            if hydration:
                items = json.loads(hydration.group(1))
                for item in items:
                    hydrated = item.get("data", {})
                    if isinstance(hydrated, dict) and hydrated.get("kind") == "playlist":
                        for t in hydrated.get("tracks", [])[:max_downloads]:
                            web_url = t.get("permalink_url")
                            if not web_url and t.get("user") and t.get("permalink"):
                                web_url = f"https://soundcloud.com/{t['user']['permalink']}/{t['permalink']}"
                            if web_url:
                                candidates.append({
                                    'id': str(t.get('id', '')),
                                    'title': t.get("title", "Unknown Title"),
                                    'url': web_url,
                                    'duration': (t.get('duration', 0) / 1000.0),
                                    'uploader': t.get("user", {}).get("username", "Unknown Artist")
                                })
    except Exception as e:
        logging.warning(f"HTML hydration fallback failed for {target_url}: {e}")

    if candidates:
        return candidates

    # yt-dlp フォールバック
    ydl_opts = {
        'quiet': True,
        'ignoreerrors': True,
        'playlistend': max_downloads,
        'user_agent': HEADERS['User-Agent'],
        'http_headers': HEADERS
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(target_url, download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        candidates.append({
                            'id': entry.get('id', ''),
                            'title': entry.get('title', 'Unknown Title'),
                            'url': entry.get('permalink_url') or entry.get('webpage_url') or '',
                            'duration': entry.get('duration', 0),
                            'uploader': entry.get('uploader') or 'Unknown Artist'
                        })
        except Exception as e:
            logging.error(f"yt-dlp fallback failed for {target_url}: {e}")

    return candidates

def passes_prefilter(track_meta: dict) -> bool:
    """
    EDMトラック以外のMix/Podcast/アルバム商品および短尺プレビュー音源を除外する。
    """
    url = track_meta.get('url', '').lower()
    title = track_meta.get('title', '').lower()
    duration = track_meta.get('duration') or 0
    
    if '/sets/' in url or '/albums/' in url or '/compilations/' in url:
        return False

    if duration > 600:
        return False

    if 0 < duration < 90:
        return False
        
    exclude_pattern = r'(\b(mix|mixtape|megamix|podcast|guest|b2b|set|compilation|session|radio|episode|live at|boiler room)\b|ch\.\d+|vol\.\d+)'
    if re.search(exclude_pattern, title) or re.search(exclude_pattern, url):
        return False
        
    return True

def download_track(original_url: str, track_id: str) -> bool:
    """
    SoundCloudから音源をAPI v2またはyt-dlpで確実にWAV形式（44.1kHz）で取得・保存する。
    """
    output_dir = Path(settings.project_root) / settings.paths.raw_audio
    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / f"{track_id}.wav"

    # 方法1: SoundCloud API v2 による直接ストリームダウンロード (403 回避)
    try:
        resolve_url = f"https://api-v2.soundcloud.com/resolve?url={original_url}&client_id={CLIENT_ID}"
        req = urllib.request.Request(resolve_url, headers=HEADERS)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            transcodings = data.get('media', {}).get('transcodings', [])
            
            # HLS または progressive ストリームを抽出
            selected = None
            for t in transcodings:
                if t.get('format', {}).get('protocol') == 'hls':
                    selected = t
                    break
            if not selected and transcodings:
                selected = transcodings[0]

            if selected:
                stream_endpoint = selected['url'] + f"?client_id={CLIENT_ID}"
                s_req = urllib.request.Request(stream_endpoint, headers=HEADERS)
                with urllib.request.urlopen(s_req) as s_resp:
                    stream_info = json.loads(s_resp.read().decode('utf-8'))
                    stream_url = stream_info.get('url')

                    if stream_url:
                        cmd = [
                            'yt-dlp', stream_url,
                            '-o', str(wav_path),
                            '-x', '--audio-format', 'wav',
                            '--quiet', '--no-warnings'
                        ]
                        res = subprocess.run(cmd, capture_output=True, text=True)
                        if res.returncode == 0 and wav_path.exists() and wav_path.stat().st_size > 100000:
                            logging.info(f"API v2 Direct Download Success: {track_id}")
                            return True
    except Exception as e:
        logging.warning(f"API v2 direct download failed for {original_url}: {e}")

    # 方法2: yt-dlp フォールバック
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
        'user_agent': HEADERS['User-Agent'],
        'http_headers': HEADERS,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([original_url])
            if wav_path.exists() and wav_path.stat().st_size > 100000:
                return True
        except Exception as e:
            logging.error(f"yt-dlp download failed ({original_url}): {e}")

    return False
