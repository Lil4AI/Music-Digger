import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.main import app, get_db_connection

client = TestClient(app)

def test_read_root(mocker):
    # staticディレクトリのindex.htmlの存在をモック
    mock_exists = mocker.patch("pathlib.Path.exists")
    mock_exists.return_value = True
    
    # FileResponseはそのまま実行できないのでモック
    mocker.patch("src.api.main.FileResponse", return_value={"file": "index.html"})
    
    response = client.get("/")
    assert response.status_code == 200

def test_get_tracks(mocker):
    # DB接続をモック
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cursor.fetchall.return_value = [
        {"track_id": "1", "title": "Track 1"},
        {"track_id": "2", "title": "Track 2"}
    ]
    
    mocker.patch("src.api.main.get_db_connection", return_value=mock_conn)
    
    response = client.get("/api/tracks")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["title"] == "Track 1"

def test_update_track_label_invalid():
    # 'tearout' か 'riddim' 以外は400
    response = client.post("/api/tracks/dummy/label", json={"label": "dubstep"})
    assert response.status_code == 400

def test_start_pipeline(mocker):
    # BackgroundTasksをモックしても良いが、エンドポイント自体はすぐ返る
    mocker.patch("src.api.main.run_pipeline_task")
    response = client.post("/api/pipeline/start", json={"url": "http://test.url"})
    
    assert response.status_code == 200
    assert response.json()["status"] == "started"
