import pytest
from unittest.mock import MagicMock, patch
from src.collectors.soundcloud import fetch_candidate_tracks, passes_prefilter, download_track

def test_fetch_candidate_tracks(mocker):
    mock_ydl_class = mocker.patch('src.collectors.soundcloud.yt_dlp.YoutubeDL')
    mock_ydl_instance = mock_ydl_class.return_value.__enter__.return_value
    mock_ydl_instance.extract_info.return_value = {
        'entries': [
            {'id': '1', 'title': 'Track 1', 'url': 'http://test.com/1', 'duration': 300},
            {'id': '2', 'title': 'Track 2 Mix', 'url': 'http://test.com/2', 'duration': 700}
        ]
    }
    
    candidates = fetch_candidate_tracks('http://dummy.url')
    
    assert len(candidates) == 2
    assert candidates[0]['title'] == 'Track 1'
    assert candidates[1]['duration'] == 700

def test_passes_prefilter():
    # 正常なEDMトラック
    track_ok = {'title': 'Awesome Riddim Track', 'duration': 300}
    assert passes_prefilter(track_ok) == True
    
    # 10分以上のミックス
    track_long = {'title': 'Good Track', 'duration': 650}
    assert passes_prefilter(track_long) == False
    
    # 除外キーワードが含まれる (mix)
    track_mix = {'title': 'Awesome Riddim Mix', 'duration': 300}
    assert passes_prefilter(track_mix) == False
    
    # 除外キーワードが含まれる (podcast)
    track_podcast = {'title': 'My Podcast episode 1', 'duration': 300}
    assert passes_prefilter(track_podcast) == False

def test_download_track(mocker):
    mock_ydl_class = mocker.patch('src.collectors.soundcloud.yt_dlp.YoutubeDL')
    mock_ydl_instance = mock_ydl_class.return_value.__enter__.return_value
    
    result = download_track('http://dummy.url', 'dummy_track_id')
    
    assert result == True
    mock_ydl_instance.download.assert_called_once_with(['http://dummy.url'])
