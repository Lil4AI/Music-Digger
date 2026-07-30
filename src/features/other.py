import librosa
import numpy as np
import torch
from panns_inference import AudioTagging

_panns_model = None

def _get_panns_model():
    """PANNsのAudioTaggingモデルをシングルトンとして取得する。"""
    global _panns_model
    if _panns_model is None:
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _panns_model = AudioTagging(checkpoint_path=None, device=device)
        except Exception as e:
            import logging
            logging.warning(f"PANNsモデルの読み込みに失敗しました。ダミーを出力します。エラー: {e}")
            _panns_model = "FAILED"
    return _panns_model

def extract_other_features(wav_path: str) -> np.ndarray:
    """
    その他のステム（メロディ/シンセ等）から特徴量を抽出する。
    PANNs Cnn14の埋め込みベクトル(2048次元)と、Chroma STFTの統計量を結合した固定長ベクトルを返す。
    """
    y, sr = librosa.load(wav_path, sr=None)
    
    features = []
    
    # PANNsは32kHzの入力を想定しているためリサンプリング
    if sr != 32000:
        y_32k = librosa.resample(y, orig_sr=sr, target_sr=32000)
    else:
        y_32k = y
        
    # PANNsの入力形状 (batch_size, samples) に合わせる
    y_32k_batch = y_32k[None, :]
    
    model = _get_panns_model()
    if model == "FAILED":
        # 2048 dims for Cnn14 embedding
        features.extend([0.0] * 2048)
    else:
        # inference は (clipwise_output, embedding) を返す
        _, embedding = model.inference(y_32k_batch)
        features.extend(embedding[0].tolist())
    
    # Chroma特徴量（調性/メロディの補助特徴）
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    features.extend(np.nan_to_num(np.mean(chroma, axis=1)).tolist())
    features.extend(np.nan_to_num(np.std(chroma, axis=1)).tolist())
    
    return np.nan_to_num(np.array(features, dtype=np.float32))
