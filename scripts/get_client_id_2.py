import urllib.request
import re

req = urllib.request.Request(
    "https://a-v2.sndcdn.com/assets/2-d17e6e58.js",
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
)

try:
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        client_ids = re.findall(r'client_id[:=]\s*["\']([a-zA-Z0-9]{32})["\']', content)
        print("Found client_ids:", client_ids)
except Exception as e:
        print("Asset fetch failed:", e)

# Try fetching main soundcloud page script tags directly
req2 = urllib.request.Request(
    "https://soundcloud.com/discover",
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
)
try:
    with urllib.request.urlopen(req2) as resp:
        html = resp.read().decode("utf-8")
        js_files = re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html)
        print(f"Found {len(js_files)} JS asset URLs")
        for js_url in js_files:
            try:
                js_req = urllib.request.Request(js_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                js_text = urllib.request.urlopen(js_req).read().decode("utf-8")
                matches = re.findall(r'client_id[:=]\s*["\']([a-zA-Z0-9]{32})["\']', js_text)
                if matches:
                    print(f"Found client_id in {js_url}:", matches[0])
                    break
            except Exception as ex:
                print("JS fetch error:", ex)
                continue
except Exception as e:
    print("Discover page fetch failed:", e)
