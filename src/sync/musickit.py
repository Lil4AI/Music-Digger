import requests
import logging

def add_to_playlist(dev_token: str, music_user_token: str, playlist_id: str, track_id: str) -> bool:
    """
    指定された Apple Music のトラックをユーザーのプレイリストに追加する。
    """
    if not all([dev_token, music_user_token, playlist_id, track_id]):
        logging.warning("プレイリスト追加に必要なトークンまたはIDが不足しています。")
        return False
        
    url = f"https://api.music.apple.com/v1/me/library/playlists/{playlist_id}/tracks"
    
    headers = {
        "Authorization": f"Bearer {dev_token}",
        "Music-User-Token": music_user_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "data": [
            {
                "id": track_id,
                "type": "songs"
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        logging.error(f"プレイリストへの追加に失敗しました (Track: {track_id}): {e}")
        return False
