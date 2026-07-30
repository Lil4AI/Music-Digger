"""
EDMサブジャンル自動判定システム — ステム分離モジュール

Demucsを用いてトラックを4ステム（drums, bass, vocals, other）に分離し、
bassをさらに帯域分割してbassとsubbassを生成する。
"""

import torch
import torchaudio
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import butter, sosfiltfilt
from demucs.api import Separator

from src.config import settings

_separator = None

def _get_separator() -> Separator:
    """Separatorインスタンスをシングルトンとして取得する。"""
    global _separator
    if _separator is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Demucsのhtdemucsモデルをロード。初回は自動ダウンロードされる。
        _separator = Separator("htdemucs", device=device)
    return _separator

def _butter_bandpass_filter(data: np.ndarray, cutoff: float, fs: float, btype: str, order: int = 4) -> np.ndarray:
    """Butterworthフィルタを適用する"""
    sos = butter(order, cutoff, fs=fs, btype=btype, output='sos')
    return sosfiltfilt(sos, data, axis=-1)

def separate_track(track_id: str, raw_audio_path: str) -> dict:
    """
    指定された音声ファイルを分離し、指定されたディレクトリに保存する。
    
    Args:
        track_id: 楽曲ID
        raw_audio_path: 入力音声ファイルのパス
        
    Returns:
        生成されたステムのファイルパスを格納した辞書
    """
    out_dir = Path(settings.project_root) / settings.paths.stems / track_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    separator = _get_separator()
    
    # Demucsで分離
    # 返り値: origin(テンソル), separated(ステム辞書)
    _, separated = separator.separate_audio_file(raw_audio_path)
    
    sample_rate = separator.samplerate
    output_paths = {}
    
    for stem_name, stem_tensor in separated.items():
        if stem_name == "vocals":
            continue
            
        if stem_name == "bass":
            # numpy配列に変換して帯域分割
            bass_np = stem_tensor.cpu().numpy()
            cutoff = settings.subbass_cutoff_hz
            
            # Subbass (lowpass)
            subbass_np = _butter_bandpass_filter(bass_np, cutoff, sample_rate, btype='lowpass')
            subbass_path = out_dir / "subbass.wav"
            sf.write(str(subbass_path), subbass_np.T, sample_rate)
            output_paths["subbass"] = str(subbass_path)
            
            # Bass (highpass)
            bass_high_np = _butter_bandpass_filter(bass_np, cutoff, sample_rate, btype='highpass')
            bass_path = out_dir / "bass.wav"
            sf.write(str(bass_path), bass_high_np.T, sample_rate)
            output_paths["bass"] = str(bass_path)
        else:
            # drums, other
            stem_path = out_dir / f"{stem_name}.wav"
            sf.write(str(stem_path), stem_tensor.cpu().numpy().T, sample_rate)
            output_paths[stem_name] = str(stem_path)
            
    return output_paths
