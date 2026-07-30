import librosa
import numpy as np

def extract_bass_features(wav_path: str) -> np.ndarray:
    """
    ベースのwavファイルから特徴量を抽出する。
    メルスペクトログラム、スペクトル特徴（重心、ロールオフ、バンド幅）、
    MFCCの統計量（mean/std）を含む固定長ベクトルを返す。
    """
    y, sr = librosa.load(wav_path, sr=None)
    
    features = []
    
    # メルスペクトログラム
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
    S_db = librosa.power_to_db(S, ref=np.max)
    features.extend(np.mean(S_db, axis=1))  # 128
    features.extend(np.std(S_db, axis=1))   # 128
    
    # スペクトル特徴
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    
    features.extend([
        float(np.mean(centroid)), float(np.std(centroid)),
        float(np.mean(rolloff)), float(np.std(rolloff)),
        float(np.mean(bandwidth)), float(np.std(bandwidth))
    ])  # 6
    
    # MFCC
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    features.extend(np.mean(mfcc, axis=1))  # 13
    features.extend(np.std(mfcc, axis=1))   # 13
    
    return np.array(features, dtype=np.float32)
