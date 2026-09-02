import sys
import os
import subprocess
from pathlib import Path

# Project root path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.config import settings

def run_step(script_name: str, desc: str):
    print(f"\n==================================================")
    print(f"▶ Step: {desc} ({script_name})")
    print(f"==================================================")
    python_exe = sys.executable
    cmd = [str(python_exe), script_name]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(settings.project_root))
    res = subprocess.run(cmd, cwd=str(settings.project_root), env=env)
    if res.returncode != 0:
        print(f"❌ Step {script_name} failed with return code {res.returncode}")
        sys.exit(res.returncode)
    print(f"✅ Step {desc} completed successfully.")

def main():
    print("==================================================")
    print("[RIDDIM FULL PIPELINE & SEQUENTIAL BENCHMARK]")
    print("==================================================")
    
    # 1. 71曲のOG RiddimトラックのDemucs 4パート分離
    run_step("scripts/run_separation.py", "Demucs 4-Stem Separation for 71 Riddim tracks")
    
    # 2. Web用MP3エンコード
    run_step("scripts/run_encode.py", "Web MP3 Encoding for stem audio previews")
    
    # 3. 152次元音響特徴量の抽出
    run_step("scripts/run_features.py", "152-Dimensional Feature Extraction")
    
    # 4. AI分類器モデルの再学習 (73曲のRiddim正解データを含めてモデル強化)
    run_step("scripts/train_model.py", "Retrain AI Model with Expanded Riddim Dataset (73 Riddim tracks)")
    
    # 5. DB内全曲へのAI推論更新
    run_step("scripts/run_inference.py", "Run AI Inference Update on all DB tracks")
    
    # 6. 新モデルでの10曲/ジャンル Demucsベンチマークテストの再開 (DBへは追加しない)
    run_step("scripts/benchmark_10_tracks_with_separation.py", "Run 10-Tracks-Per-Genre Demucs Benchmark Test on New Riddim-Boosted Model")
    
    print("\n==================================================")
    print("🎉 ALL STEPS COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    main()
