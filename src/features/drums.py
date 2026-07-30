import librosa
import numpy as np
from scipy.signal import find_peaks

def extract_drums_features(wav_path: str) -> np.ndarray:
    """
    ドラムのwavファイルから特徴量を抽出する。
    オンセット強度、テンポ、オンセット密度、自己相関ピーク（周期性）を含む固定長ベクトルを返す。
    """
    y, sr = librosa.load(wav_path, sr=None)
    
    # オンセット強度包絡
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    
    # テンポ推定
    tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)
    tempo_val = float(tempo[0])
    
    # オンセット密度（1秒あたりのオンセット数）
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    duration = librosa.get_duration(y=y, sr=sr)
    onset_density = len(onsets) / duration if duration > 0 else 0.0
    
    # オンセット強度包絡の自己相関（リズムパターンの反復性）
    # max_sizeは数秒分のフレーム数（hop_length=512なら約2秒=172フレーム程度）
    ac = librosa.autocorrelate(onset_env, max_size=200)
    
    # ピーク検出 (自己相関のピーク)
    peaks, _ = find_peaks(ac)
    if len(peaks) > 0:
        peak_vals = ac[peaks]
        # 強度順にソート
        sorted_idx = np.argsort(peak_vals)[::-1]
        top_peaks = peaks[sorted_idx][:3]
        top_amps = peak_vals[sorted_idx][:3]
    else:
        top_peaks = np.array([])
        top_amps = np.array([])
        
    # 3ピーク分にパディング
    top_3_peaks = np.zeros(3)
    top_3_amps = np.zeros(3)
    for i in range(min(len(top_peaks), 3)):
        top_3_peaks[i] = top_peaks[i]
        top_3_amps[i] = top_amps[i]
        
    features = [
        tempo_val,
        onset_density,
        float(top_3_peaks[0]), float(top_3_amps[0]),
        float(top_3_peaks[1]), float(top_3_amps[1]),
        float(top_3_peaks[2]), float(top_3_amps[2])
    ]
    
    return np.array(features, dtype=np.float32)
