import urllib.request
import re
import json

def parse_apple_music_playlist(url: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    req = urllib.request.Request(url, headers=headers)
    html = urllib.request.urlopen(req).read().decode('utf-8')

    tracks = []
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for s in scripts:
        if 'title' in s and 'artistName' in s:
            try:
                data = json.loads(s.strip())
                # Recursively search for song objects in JSON
                def extract_songs(obj):
                    if isinstance(obj, dict):
                        if obj.get('type') == 'songs' or (obj.get('title') and obj.get('artistName')):
                            t = obj.get('title') or obj.get('name')
                            a = obj.get('artistName')
                            if t and a:
                                tracks.append({'title': t, 'artist': a})
                        for v in obj.values():
                            extract_songs(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            extract_songs(item)

                extract_songs(data)
            except Exception:
                # Fallback to regex pattern matching inside JSON string
                matches = re.findall(r'"artistName"\s*:\s*"([^"]+)"\s*,\s*"title"\s*:\s*"([^"]+)"', s)
                for a, t in matches:
                    tracks.append({'title': t, 'artist': a})
                
                matches2 = re.findall(r'"title"\s*:\s*"([^"]+)"\s*,\s*"artistName"\s*:\s*"([^"]+)"', s)
                for t, a in matches2:
                    tracks.append({'title': t, 'artist': a})

    # Deduplicate tracks preserving order
    seen = set()
    unique_tracks = []
    for tr in tracks:
        key = (tr['artist'].lower(), tr['title'].lower())
        if key not in seen:
            seen.add(key)
            unique_tracks.append(tr)

    return unique_tracks

if __name__ == '__main__':
    url = "https://music.apple.com/jp/playlist/og-riddim/pl.u-AkAmma9ixLEvqR5"
    t_list = parse_apple_music_playlist(url)
    print(f"Extracted {len(t_list)} unique tracks from Apple Music:")
    for idx, t in enumerate(t_list, 1):
        print(f"[{idx}] {t['artist']} - {t['title']}")
