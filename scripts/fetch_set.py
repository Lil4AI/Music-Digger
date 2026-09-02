import urllib.request
import re
import json

url = "https://soundcloud.com/mildfre/sets/brostep"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
)

try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode("utf-8")
        print(f"HTML fetch successful: {len(html)} bytes")
        
        # SoundCloud embeds JSON hydration payload in <script>
        hydration_match = re.search(r'window\.__sc_hydration\s*=\s*(\[.*?\]);</script>', html, re.DOTALL)
        track_urls = []
        if hydration_match:
            data = json.loads(hydration_match.group(1))
            for item in data:
                hydrated = item.get("data", {})
                if isinstance(hydrated, dict) and hydrated.get("kind") == "playlist":
                    tracks = hydrated.get("tracks", [])
                    for t in tracks:
                        permalink = t.get("permalink_url")
                        if permalink:
                            track_urls.append(permalink)
                        elif t.get("user") and t.get("permalink"):
                            user_permalink = t["user"].get("permalink")
                            track_permalink = t.get("permalink")
                            track_urls.append(f"https://soundcloud.com/{user_permalink}/{track_permalink}")
        
        print(f"Extracted {len(track_urls)} total track URLs from hydration payload:")
        for u in track_urls[:15]:
            print(" -", u)
            
        with open("scripts/brostep_track_urls.json", "w", encoding="utf-8") as f:
            json.dump(track_urls, f, ensure_ascii=False, indent=2)
except Exception as e:
    print("Error:", e)
