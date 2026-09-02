import urllib.request
import re

def get_soundcloud_client_id():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    req = urllib.request.Request('https://soundcloud.com/discover', headers=headers)
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
        scripts = re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html)
        for s in reversed(scripts):
            try:
                js = urllib.request.urlopen(s).read().decode('utf-8')
                m = re.search(r'client_id[:=]\s*["\']([a-zA-Z0-9]{32})["\']', js)
                if m:
                    return m.group(1)
            except Exception:
                continue
    except Exception as e:
        print("Failed to fetch main page:", e)
    return None

if __name__ == '__main__':
    cid = get_soundcloud_client_id()
    print("SoundCloud Client ID:", cid)
