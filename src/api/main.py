import sqlite3
import subprocess
import asyncio
import sys
import contextlib
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import settings

_is_pipeline_running = False

app = FastAPI(title="Music Digger API")

# フロントエンド(React)からのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイルの配信設定
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def read_root():
    """ダッシュボードUIの提供"""
    index_path = static_dir / "index.html"
    if not index_path.exists():
        return {"error": "UI not built yet."}
    return FileResponse(str(index_path), media_type="text/html")

def get_db_connection():
    db_path = Path(settings.project_root) / settings.paths.db / "edm_classifier.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/tracks")
def get_tracks():
    """全トラックのメタデータとステータスを取得"""
    with contextlib.closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
    return [dict(row) for row in rows]

class LabelUpdate(BaseModel):
    label: str

@app.post("/api/tracks/{track_id}/label")
def update_track_label(track_id: str, update: LabelUpdate):
    """人間によるラベル（Tear Out / Riddim）を更新"""
    if update.label.lower() not in ['tearout', 'riddim']:
        raise HTTPException(status_code=400, detail="Invalid label. Must be 'tearout' or 'riddim'")
        
    with contextlib.closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        
        # 存在チェック
        cursor.execute("SELECT track_id FROM tracks WHERE track_id = ?", (track_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Track not found")
            
        cursor.execute(
            "UPDATE tracks SET human_label = ? WHERE track_id = ?",
            (update.label.lower(), track_id)
        )
        conn.commit()
    
    return {"status": "success", "track_id": track_id, "human_label": update.label.lower()}

@app.get("/api/audio/{track_id}/{stem}")
def get_audio_file(track_id: str, stem: str):
    """
    指定されたトラックの特定のステム(wav)をストリーム配信する。
    stem: raw, drums, bass, subbass, other
    """
    if stem == "raw":
        audio_path = Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav"
    elif stem in ["drums", "bass", "subbass", "other"]:
        audio_path = Path(settings.project_root) / settings.paths.stems / track_id / f"{stem}.wav"
    else:
        raise HTTPException(status_code=400, detail="Invalid stem type")
        
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
        
    return FileResponse(str(audio_path), media_type="audio/wav")

class PipelineRequest(BaseModel):
    url: str = ""

def run_pipeline_task(target_url: str, log_file: Path):
    """バックグラウンドでパイプラインスクリプトを順次実行し、ログファイルに出力する"""
    import os
    global _is_pipeline_running
    try:
        python_exe = sys.executable
        venv_scripts = Path(settings.project_root) / ".venv" / "Scripts"
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(settings.project_root))
        # yt-dlpがffmpegを見つけられるようにPATHに追加
        env["PATH"] = f"{venv_scripts};{env.get('PATH', '')}"
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== Pipeline Started ===\n")
            f.flush()
            
            scripts = [
                ("scripts/run_collection.py", [target_url] if target_url else []),
                ("scripts/run_separation.py", []),
                ("scripts/run_features.py", []),
                ("scripts/run_inference.py", [])
            ]
            
            for script, args in scripts:
                f.write(f"\n>>> Running {script}...\n")
                f.flush()
                
                cmd = [str(python_exe), script] + args
                try:
                    process = subprocess.Popen(
                        cmd, 
                        cwd=str(settings.project_root), 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.STDOUT,
                        env=env,
                        text=True,
                        encoding="utf-8",
                        errors="replace"
                    )
                    
                    # リアルタイムでファイルに書き出す
                    for line in process.stdout:
                        f.write(line)
                        f.flush()
                        
                    process.wait()
                    if process.returncode != 0:
                        f.write(f"\n[ERROR] Script {script} exited with code {process.returncode}\n")
                        break # エラーが起きたら後続の処理は止める
                except Exception as e:
                    f.write(f"\n[CRITICAL ERROR] Failed to run {script}: {e}\n")
                    break
                    
            f.write("\n=== Pipeline Finished ===\n")
            f.flush()
    finally:
        _is_pipeline_running = False

@app.post("/api/pipeline/start")
def start_pipeline(req: PipelineRequest, background_tasks: BackgroundTasks):
    """パイプライン処理を開始するエンドポイント"""
    global _is_pipeline_running
    if _is_pipeline_running:
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
        
    log_dir = Path(settings.project_root) / settings.paths.logs
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline_current.log"
    
    # 既存のログをクリア
    if log_file.exists():
        log_file.unlink()
        
    _is_pipeline_running = True
    background_tasks.add_task(run_pipeline_task, req.url, log_file)
    return {"status": "started", "msg": "Pipeline has been started in the background."}

@app.post("/api/model/train")
def train_model(background_tasks: BackgroundTasks):
    """人間が付けた正解ラベルをもとに、AI判定モデルを再学習する"""
    import os
    def run_train():
        python_exe = sys.executable
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(settings.project_root))
        try:
            subprocess.run([str(python_exe), "scripts/train_model.py"], env=env, cwd=str(settings.project_root), check=True)
            print("AI Model trained successfully!")
        except Exception as e:
            print(f"Training failed: {e}")
        
    background_tasks.add_task(run_train)
    return {"status": "started", "msg": "Model training has been scheduled."}

@app.get("/api/pipeline/logs")
def get_pipeline_logs():
    """現在のパイプラインのログファイルの中身を返す"""
    log_file = Path(settings.project_root) / settings.paths.logs / "pipeline_current.log"
    if not log_file.exists():
        return {"logs": "No active pipeline or log file not found."}
        
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"logs": content}
    except Exception as e:
        return {"logs": f"Error reading log file: {e}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
