import librosa
import numpy as np
from scipy.signal import find_peaks

def extract_subbass_features(wav_path: str) -> np.ndarray:
    """
    サブベースのwavファイルから特徴量を抽出する。
    RMSエネルギー包絡、自己相関（LFO周期とその強度）、
    低域エネルギー比率（Tear Out vs Riddimの重要な特徴）を含む固定長ベクトルを返す。
    """
    y, sr = librosa.load(wav_path, sr=None)
    
    features = []
    
    # RMSエネルギー包絡
    rms = librosa.feature.rms(y=y)[0]
    features.extend([float(np.mean(rms)), float(np.std(rms))])
    
    # RMSエネルギー包絡の自己相関（LFO周期の推定）
    ac_max_size = min(400, len(rms))
    if ac_max_size < 2:
        dom_hz = 0.0
        dom_amp = 0.0
    else:
        ac = librosa.autocorrelate(rms, max_size=ac_max_size)
        peaks, _ = find_peaks(ac)
        if len(peaks) > 0:
            peak_vals = ac[peaks]
            dom_idx = np.argmax(peak_vals)
            dom_lag = peaks[dom_idx]
            dom_amp = peak_vals[dom_idx]
            
            # lag(フレーム)からHzに変換
            # librosaデフォルト hop_length=512
            hop_length = 512
            frame_rate = sr / hop_length
            dom_hz = frame_rate / dom_lag if dom_lag > 0 else 0.0
        else:
            dom_hz = 0.0
            dom_amp = 0.0
        
    features.extend([float(dom_hz), float(dom_amp)])
    
    # 低域エネルギー比率 (60Hz未満)
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    
    low_freq_mask = freqs < 60
    total_energy = np.sum(S)
    low_energy = np.sum(S[low_freq_mask, :])
    ratio = low_energy / total_energy if total_energy > 0 else 0.0
    
    features.append(float(ratio))
    
    return np.nan_to_num(np.array(features, dtype=np.float32))
