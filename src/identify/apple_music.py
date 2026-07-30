import os
import jwt
import requests
import datetime
import logging
from rapidfuzz import fuzz

def generate_developer_token() -> str:
    """
    環境変数から Apple Music API の認証情報を読み取り、
    Developer Token (JWT) を生成して返す。
    """
    team_id = os.environ.get("APPLE_MUSIC_TEAM_ID")
    key_id = os.environ.get("APPLE_MUSIC_KEY_ID")
    private_key_path = os.environ.get("APPLE_MUSIC_PRIVATE_KEY_PATH")
    
    if not all([team_id, key_id, private_key_path]):
        logging.warning("Apple Music API の認証情報が不足しています。")
        return ""
        
    try:
        with open(private_key_path, 'r') as f:
            private_key = f.read()
            
        headers = {
            "alg": "ES256",
            "kid": key_id
        }
        
        # 半年間の有効期限
        payload = {
            "iss": team_id,
            "iat": int(datetime.datetime.now().timestamp()),
            "exp": int((datetime.datetime.now() + datetime.timedelta(days=180)).timestamp())
        }
        
        token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
        return token
    except Exception as e:
        logging.error(f"Developer Token の生成に失敗しました: {e}")
        return ""

def search_catalog(term: str, dev_token: str, storefront: str = 'jp') -> str:
    """
    Apple Music Catalog Search API を用いて楽曲を検索し、
    テキスト類似度が高い最初の曲の Apple Music ID を返す。
    """
    if not dev_token:
        return ""
        
    url = f"https://api.music.apple.com/v1/catalog/{storefront}/search"
    headers = {
        "Authorization": f"Bearer {dev_token}"
    }
    params = {
        "term": term,
        "types": "songs",
        "limit": 5
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        songs = data.get('results', {}).get('songs', {}).get('data', [])
        if not songs:
            return ""
            
        # 類似度で最も近いものを選ぶ
        best_match_id = ""
        highest_score = 0
        
        for song in songs:
            am_title = song['attributes']['name']
            am_artist = song['attributes']['artistName']
            am_full = f"{am_artist} {am_title}"
            
            score = fuzz.token_set_ratio(term.lower(), am_full.lower())
            if score > highest_score:
                highest_score = score
                best_match_id = song['id']
                
        # 類似度が低すぎる場合は誤検出として空を返す
        if highest_score < 70:
            return ""
            
        return best_match_id
        
    except Exception as e:
        logging.error(f"Catalog Search に失敗しました ({term}): {e}")
        return ""

def identify_via_audd(wav_path: str) -> str:
    """
    AudD API を用いて音源から楽曲を識別し、Apple Music ID を取得する。
    """
    api_token = os.environ.get("AUDD_API_KEY")
    if not api_token:
        return ""
        
    url = "https://api.audd.io/"
    
    data = {
        'api_token': api_token,
        'return': 'apple_music',
    }
    
    try:
        with open(wav_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, data=data, files=files)
            
        response.raise_for_status()
        result = response.json()
        
        if result.get('status') == 'success' and result.get('result'):
            am_info = result['result'].get('apple_music', {})
            # urlからIDを抽出 (例: https://music.apple.com/us/album/title/id?i=TRACK_ID)
            # または APIの特定のフィールドから取得
            track_id = am_info.get('playParams', {}).get('id')
            if not track_id: # fallback
                url = am_info.get('url', '')
                if 'i=' in url:
                    track_id = url.split('i=')[1]
            return track_id or ""
            
    except Exception as e:
        logging.error(f"AudD API の呼び出しに失敗しました: {e}")
        
    return ""
