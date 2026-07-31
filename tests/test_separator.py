import pytest
import os
import shutil
import torch
from pathlib import Path

from src.config import settings
from src.separation.separator import separate_track

@pytest.fixture
def dummy_wav():
    track_id = "test_dummy_track"
    dummy_wav_path = Path(settings.project_root) / settings.paths.raw_audio / f"{track_id}.wav"
    dummy_wav_path.parent.mkdir(parents=True, exist_ok=True)
    
    sample_rate = 44100
    t = torch.linspace(0, 1, sample_rate)
    waveform = torch.sin(2 * torch.pi * 440 * t).unsqueeze(0).repeat(2, 1)
    
    import soundfile as sf
    sf.write(str(dummy_wav_path), waveform.numpy().T, sample_rate)
    
    yield track_id, str(dummy_wav_path)
    
    # Cleanup
    if dummy_wav_path.exists():
        dummy_wav_path.unlink()
    out_dir = Path(settings.project_root) / settings.paths.stems / track_id
    if out_dir.exists():
        shutil.rmtree(out_dir)

def test_separate_track_outputs(mocker, dummy_wav):
    track_id, dummy_wav_path = dummy_wav
    
    # Mock Separator
    class MockSeparator:
        samplerate = 44100
        def separate_audio_file(self, path):
            # Create dummy tensors for 4 stems
            dummy_tensor = torch.zeros((2, 44100))
            return None, {
                "drums": dummy_tensor,
                "bass": dummy_tensor,
                "other": dummy_tensor,
                "vocals": dummy_tensor
            }
            
    mocker.patch("src.separation.separator._get_separator", return_value=MockSeparator())
    
    output_paths = separate_track(track_id, dummy_wav_path)
    
    out_dir = Path(settings.project_root) / settings.paths.stems / track_id
    
    expected_stems = ["drums", "bass", "subbass", "other"]
    for stem in expected_stems:
        stem_path = out_dir / f"{stem}.wav"
        assert stem_path.exists(), f"{stem}.wav が生成されていません"
        assert stem in output_paths, f"{stem} が戻り値の辞書に含まれていません"
        
    vocals_path = out_dir / "vocals.wav"
    assert not vocals_path.exists(), "vocals.wav が保存されています"
    assert "vocals" not in output_paths, "vocals が戻り値の辞書に含まれています"
