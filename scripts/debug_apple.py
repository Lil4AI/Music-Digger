import urllib.request
import re
import json

url = 'https://music.apple.com/jp/playlist/og-riddim/pl.u-AkAmma9ixLEvqR5'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
html = urllib.request.urlopen(req).read().decode('utf-8')

print("Searching all script tags...")
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"Found {len(scripts)} total script tags")
for idx, s in enumerate(scripts):
    if 'Subfiltronik' in s or 'INFEKT' in s or 'Berrix' in s or 'SampliFire' in s:
        print(f"Script {idx} contains track keywords! Length: {len(s)}")
        print("Snippet:", s[:500])
        break
