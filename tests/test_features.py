import pytest
import numpy as np
import soundfile as sf
from pathlib import Path

from src.features.drums import extract_drums_features
from src.features.bass import extract_bass_features
from src.features.subbass import extract_subbass_features
from src.features.other import extract_other_features

@pytest.fixture
def dummy_stem_wav(tmp_path):
    # 1秒間のステレオ正弦波 (440Hz) を作成
    sample_rate = 22050
    t = np.linspace(0, 1, sample_rate)
    waveform = np.sin(2 * np.pi * 440 * t)
    
    wav_path = tmp_path / "dummy_stem.wav"
    sf.write(str(wav_path), waveform, sample_rate)
    
    return str(wav_path)

def test_extract_drums_features(dummy_stem_wav):
    feat = extract_drums_features(dummy_stem_wav)
    assert isinstance(feat, np.ndarray)
    # tempo, density, 3 peaks * 2 (pos, amp) = 8 features
    assert feat.shape == (8,)
    assert not np.isnan(feat).any()

def test_extract_bass_features(dummy_stem_wav):
    feat = extract_bass_features(dummy_stem_wav)
    assert isinstance(feat, np.ndarray)
    # RMSE(mean, std), centroid(mean, std), rolloff(mean, std), bandwidth(mean, std), mel(128*2), mfcc(13*2) = 288
    assert feat.shape == (288,)
    assert not np.isnan(feat).any()

def test_extract_subbass_features(dummy_stem_wav):
    feat = extract_subbass_features(dummy_stem_wav)
    assert isinstance(feat, np.ndarray)
    # RMSE(mean, std), AC(hz, amp), low_ratio = 5
    assert feat.shape == (5,)
    assert not np.isnan(feat).any()

def test_extract_other_features(dummy_stem_wav):
    feat = extract_other_features(dummy_stem_wav)
    assert isinstance(feat, np.ndarray)
    # PANNs(2048) + Chroma(12 * 2) = 2072
    assert feat.shape == (2072,)
    assert not np.isnan(feat).any()
