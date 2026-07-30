# EDMサブジャンル自動判定システム — タスクリスト

---

## フェーズ① プロジェクト基盤
- [x] ディレクトリ構成の作成（data/, db/, src/, config/, scripts/, logs/）
- [x] CONTRACTS.md — 全モジュール共有契約
- [x] config/settings.yaml — 全体設定ファイル
- [x] config/seed_djs.txt — 空テンプレート
- [x] db/schema.sql — tracks + genre_probabilities テーブル定義
- [x] scripts/init_db.py — SQLite DB初期化（冪等）
- [x] src/config.py — settings.yaml + .env 統合ユーティリティ
- [x] requirements.txt — PyYAML, python-dotenv
- [x] .env.example — シークレット変数テンプレート
- [x] .gitignore — data/, db/*.db, .env, __pycache__, .venv/, models/
- [x] README.md — セットアップ手順 + 開発ルール
- [x] src/ 配下6パッケージの __init__.py
- [x] 動作検証: venv作成 → pip install → init_db.py → config.py読み込み

---

## フェーズ② ステム分離パイプライン
- [x] requirements.txt に demucs, torch, torchaudio, scipy, soundfile を追加
- [x] src/separation/separator.py — separate_track() 関数
  - [x] Demucs htdemucs で4ステム分離
  - [x] vocals は保存しない
  - [x] Butterworthフィルタで bass/subbass 帯域分割
  - [x] GPU/CPU 自動フォールバック
- [x] scripts/run_separation.py — バッチ処理スクリプト
  - [x] separated_at IS NULL のトラックを処理
  - [x] tqdm 進捗表示
  - [x] 失敗ログ記録
- [x] tests/test_separator.py — ダミー正弦波テスト

---

## フェーズ③ ステムごとの特徴量抽出
- [x] requirements.txt に librosa, panns_inference を追加
- [x] src/features 配下の抽出モジュール作成
  - [x] drums.py (オンセット、テンポ、自己相関ピーク)
  - [x] bass.py (メルスペクトログラム、重心、MFCCの統計量)
  - [x] subbass.py (RMSエネルギー、LFO周期、低域エネルギー比率)
  - [x] other.py (PANNsの音響埋め込み、Chroma)
  - [x] 1次元配列(float32)を返す統一インターフェース
- [x] scripts/generate_feature_schema.py 作成
  - [x] 各関数の次元数確認と feature_schema_v1.json 出力
- [x] scripts/run_features.py (バッチスクリプト) 作成
  - [x] db上の features_extracted_at IS NULL を対象に抽出・NPY保存

---

## フェーズ④ Fusion分類モデル学習
- [x] requirements.txt に scikit-learn, xgboost, joblib, pandas を追加
- [x] src/models/dataset.py — load_labeled_dataset()
  - [x] 特徴量(NPY)とDBの正解ラベルを結合して出力
- [x] src/models/train.py — K-Fold CV & モデル学習
  - [x] StandardScaler で正規化し XGBoost 等で学習
  - [x] CalibratedClassifierCV で確率を補正し、モデルとmetricsを保存
- [x] src/models/infer.py — predict_genre()
  - [x] 保存したモデルをロードし、特定のtrack_idに対してTear Out/Riddimの確率を出力
- [x] scripts/train_model.py — バッチ用ラッパー
- [x] scripts/run_inference.py — バッチ推論スクリプト
  - [x] classified_at IS NULL のトラックを対象に推論し、DBを更新

---

## フェーズ⑤ 収集パイプライン
- [x] requirements.txt に yt-dlp を追加
- [x] src/collectors/soundcloud.py
  - [x] yt-dlp によるプレイリスト等のメタデータ取得
  - [x] ミックス音源や関係ないキーワードの除外 (prefilter)
  - [x] WAV形式での音声ダウンロード
- [x] src/collectors/drop_detector.py
  - [x] RMSエネルギーベースでのドロップ区間推定 (30秒)
- [x] scripts/run_collection.py
  - [x] 指定URLからメタデータ取得 → フィルタ → DL → DB登録 の一連フロー実行

---

## フェーズ⑥ Apple Music連携
- [x] requirements.txt に requests, pyjwt, rapidfuzz を追加
- [x] config/settings.yaml に identify, sync_rules セクション追加
- [x] src/identify/apple_music.py
  - [x] JWT Developer Tokenの自動生成
  - [x] Apple Music API (Catalog Search) によるテキストベース照合 + rapidfuzz 類似度判定
  - [x] AudD APIによる音響指紋ベースの照合 (フォールバック)
- [x] src/sync/musickit.py
  - [x] Music User Token を用いたプレイリストへの曲追加API実行
- [x] scripts/run_identify.py — 楽曲照合バッチ
- [x] scripts/run_sync.py — プレイリスト同期バッチ
- [x] README.md にcron設定例を追記
- [x] .gitignore に .music_user_token を追加
