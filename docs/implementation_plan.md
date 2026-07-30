# EDMサブジャンル自動判定システム — 実装計画

全6フェーズで段階的に構築する。各フェーズは独立してテスト可能な単位。

---

## フェーズ① プロジェクト基盤 ✅ 完了

> **ステータス:** 実装・検証完了（2026-07-29）

### 概要
プロジェクトのスケルトン構造、設定管理、DB初期化、共有契約ファイルを構築。

### 成果物
- [CONTRACTS.md](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/CONTRACTS.md) — 全フェーズの共有契約
- [config/settings.yaml](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/config/settings.yaml) — 全体設定
- [db/schema.sql](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/db/schema.sql) — DBスキーマ定義
- [scripts/init_db.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/init_db.py) — DB初期化
- [src/config.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/config.py) — 設定ユーティリティ
- `src/` 配下6パッケージの `__init__.py`

### 依存パッケージ
PyYAML, python-dotenv

---

## フェーズ② ステム分離パイプライン ✅ 完了

> **ステータス:** 実装・検証完了（2026-07-29）

### 概要
Demucsで4ステム分離 → Butterworthフィルタでbass/subbass帯域分割。

### 実装対象

#### [NEW] src/separation/separator.py
- `separate_track(track_id, raw_audio_path) -> dict`
- Demucs htdemucs モデルで4ステム分離
- drums, other → そのまま保存
- vocals → 保存しない
- bass → Butterworthフィルタで subbass_cutoff_hz (120Hz) を境に帯域分割
- GPU自動検出、CPU フォールバック

#### [NEW] scripts/run_separation.py
- `separated_at IS NULL` のトラックをバッチ処理
- 成功 → `separated_at` 更新、失敗 → ログ記録してスキップ
- tqdm で進捗表示

#### [NEW] tests/test_separator.py
- ダミー正弦波でパイプライン配線の確認

### 追加依存
demucs, torch, torchaudio, scipy, soundfile

---

## フェーズ③ 特徴量抽出 ✅ 完了

> **ステータス:** 実装・検証完了（2026-07-29）

### 概要
4ステムそれぞれから固定長特徴ベクトルを抽出。

### 実装対象

#### [NEW] src/features/drums.py
- オンセット強度、テンポ推定、オンセット密度、自己相関ピーク

#### [NEW] src/features/bass.py
- メルスペクトログラム統計、スペクトル特徴、MFCC

#### [NEW] src/features/subbass.py
- RMSエネルギー包絡、自己相関周期性（ワブル/LFO検出）、低域エネルギー比率

#### [NEW] src/features/other.py
- PANNs Cnn14 埋め込み + Chroma STFT 統計

#### [NEW] scripts/generate_feature_schema.py
- ダミー音源で各ブランチの出力次元数を記録 → `feature_schema_v1.json`

#### [NEW] scripts/run_features.py
- `separated_at IS NOT NULL AND features_extracted_at IS NULL` をバッチ処理

### 追加依存
librosa, panns_inference

---

## フェーズ④ Fusion分類モデル学習 ✅ 完了

> **ステータス:** 実装完了（2026-07-29）

### 概要
4ブランチ特徴を concat → ロジスティック回帰/GBM/XGBoost で Tear Out vs Riddim 2値分類。

### 実装対象

#### [NEW] src/models/dataset.py
- `load_labeled_dataset(labels_csv)` → 4ブランチ辞書 + ラベル配列

#### [NEW] src/models/train.py
- ブランチごとStandardScaler → concat → 5-fold StratifiedKFold
- 3モデル比較 → 最良モデルで全データ再学習 → CalibratedClassifierCV

#### [NEW] src/models/infer.py
- `predict_proba(track_id, model)` → `{"tearout": 0.8, "riddim": 0.2}`

#### [NEW] scripts/train_model.py, scripts/run_inference.py

### 追加依存
scikit-learn, xgboost, joblib

---

## フェーズ⑤ 収集パイプライン ✅ 完了

> **ステータス:** 実装完了（2026-07-29）

### 概要
SoundCloud → yt-dlp ダウンロード → ドロップ区間自動検出 → DB登録。

### 実装対象

#### [NEW] src/collectors/soundcloud.py
- `fetch_candidate_tracks`, `passes_prefilter`, `download_track`
- レート制限・並列数制限

#### [NEW] src/collectors/drop_detector.py
- `detect_drop_segment` — RMSスライディングウィンドウで最大エネルギー区間

#### [NEW] scripts/run_collection.py

### 追加依存
yt-dlp, librosa

---

## フェーズ⑥ Apple Music連携 ✅ 完了

> **ステータス:** 実装完了（2026-07-29）

### 概要
楽曲照合（テキスト→AudDフォールバック）→ プレイリスト自動同期。

### 実装対象

#### [NEW] src/identify/apple_music.py
- `generate_developer_token`, `search_catalog`, `identify_via_audd`

#### [NEW] src/sync/musickit.py
- Music User Token取得（ローカルHTTPサーバー + ブラウザ認可）
- `add_to_playlist`

#### [NEW] scripts/run_identify.py, scripts/run_sync.py
- README.md にcron設定例を追記

### 追加依存
requests, pyjwt, rapidfuzz

---

## 検証計画

### 各フェーズの検証
| フェーズ | 検証方法 |
|---|---|
| ① 基盤 | `init_db.py` 実行、`config.py` 読み込み確認 |
| ② ステム分離 | ダミー正弦波テスト（`test_separator.py`） |
| ③ 特徴量抽出 | `generate_feature_schema.py` でスキーマ生成確認 |
| ④ 分類モデル | `train_model.py` で metrics.json の F1/accuracy 確認 |
| ⑤ 収集 | テスト用DJで `run_collection.py` 実行 |
| ⑥ Apple Music | developer token 生成 → catalog search 動作確認 |

### エンドツーエンド
全スクリプトを順番に実行し、DBの各 `*_at` カラムが正しく更新されることを確認。
