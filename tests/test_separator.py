"""
EDMサブジャンル自動判定システム — ステム分離モジュールのテスト

ダミーの短い正弦波wavファイルを入力として、
4つの出力ファイルが期待したパスに生成されることだけを確認する。
（分離精度のテストではなく、パイプラインの配線が壊れていないかの確認）
"""

import unittest
import os
import shutil
import torch
import torchaudio
from pathlib import Path

from src.config import settings
from src.separation.separator import separate_track

class TestSeparator(unittest.TestCase):
    
    def setUp(self):
        self.track_id = "test_dummy_track"
        self.dummy_wav_path = Path(settings.project_root) / settings.paths.raw_audio / f"{self.track_id}.wav"
        self.dummy_wav_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 1秒間のステレオ正弦波 (440Hz) を作成
        sample_rate = 44100
        t = torch.linspace(0, 1, sample_rate)
        # (channels, frames)
        waveform = torch.sin(2 * torch.pi * 440 * t).unsqueeze(0).repeat(2, 1)
        
        import soundfile as sf
        sf.write(str(self.dummy_wav_path), waveform.numpy().T, sample_rate)
        
    def tearDown(self):
        # クリーンアップ
        if self.dummy_wav_path.exists():
            self.dummy_wav_path.unlink()
            
        out_dir = Path(settings.project_root) / settings.paths.stems / self.track_id
        if out_dir.exists():
            shutil.rmtree(out_dir)

    def test_separate_track_outputs(self):
        # 実行
        output_paths = separate_track(self.track_id, str(self.dummy_wav_path))
        
        out_dir = Path(settings.project_root) / settings.paths.stems / self.track_id
        
        # 期待される出力ファイルが存在するか確認
        expected_stems = ["drums", "bass", "subbass", "other"]
        for stem in expected_stems:
            stem_path = out_dir / f"{stem}.wav"
            self.assertTrue(stem_path.exists(), f"{stem}.wav が生成されていません")
            self.assertIn(stem, output_paths, f"{stem} が戻り値の辞書に含まれていません")
            
        # vocals は保存されないことを確認
        vocals_path = out_dir / "vocals.wav"
        self.assertFalse(vocals_path.exists(), "vocals.wav が保存されています")
        self.assertNotIn("vocals", output_paths, "vocals が戻り値の辞書に含まれています")

if __name__ == "__main__":
    unittest.main()
