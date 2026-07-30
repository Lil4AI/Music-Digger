import librosa
import numpy as np

def detect_drop_segment(wav_path: str, segment_length_sec: int = 30) -> tuple:
    """
    音源から、ドロップ部分（最もエネルギーが高い30秒間）の
    開始時間と終了時間(秒)を推定して返す。
    """
    y, sr = librosa.load(wav_path, sr=None)
    
    # RMSエネルギーを計算
    rms = librosa.feature.rms(y=y)[0]
    
    # 1フレームあたりの時間
    hop_length = 512
    frame_time = hop_length / sr
    
    # セグメント長に相当するフレーム数
    segment_frames = int(segment_length_sec / frame_time)
    
    if len(rms) <= segment_frames:
        # トラック全体が短すぎる場合
        duration = librosa.get_duration(y=y, sr=sr)
        return (0.0, duration)
        
    # スライディングウィンドウで最大エネルギー区間を探索
    # np.convolveを使って移動合計を計算
    window = np.ones(segment_frames)
    rms_sum = np.convolve(rms, window, mode='valid')
    
    max_idx = np.argmax(rms_sum)
    start_time = max_idx * frame_time
    end_time = start_time + segment_length_sec
    
    return (float(start_time), float(end_time))
