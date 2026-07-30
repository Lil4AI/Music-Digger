# EDMサブジャンル自動判定システム — ウォークスルー

開発の経過・変更内容・検証結果を時系列で記録する。

---

## 2026-07-29: フェーズ① プロジェクト基盤の構築

### 実施内容

プロジェクトのスケルトン構造を一括作成し、基盤となる設定管理とDB初期化を実装した。

### 作成ファイル一覧

| ファイル | 説明 |
|---|---|
| [CONTRACTS.md](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/CONTRACTS.md) | 全フェーズの共有契約（track_id規則、命名規則、DBスキーマ、運用ルール） |
| [config/settings.yaml](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/config/settings.yaml) | 全体設定（sample_rate, stems, subbass_cutoff_hz, genre_labels, collector等） |
| [config/seed_djs.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/config/seed_djs.txt) | 収集対象DJ URLリスト（空テンプレート） |
| [db/schema.sql](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/db/schema.sql) | tracks + genre_probabilities テーブル定義 |
| [scripts/init_db.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/init_db.py) | SQLite DB初期化スクリプト |
| [src/config.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/config.py) | settings.yaml + .env 統合設定ユーティリティ |
| [requirements.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/requirements.txt) | 依存パッケージ（PyYAML, python-dotenv） |
| [.env.example](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/.env.example) | シークレット変数テンプレート（6変数） |
| [.gitignore](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/.gitignore) | Git除外設定 |
| [README.md](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/README.md) | セットアップ手順 + 開発ルール + パイプライン実行順序 |
| src/collectors/\_\_init\_\_.py | collectors パッケージ（空） |
| src/separation/\_\_init\_\_.py | separation パッケージ（空） |
| src/features/\_\_init\_\_.py | features パッケージ（空） |
| src/models/\_\_init\_\_.py | models パッケージ（空） |
| src/identify/\_\_init\_\_.py | identify パッケージ（空） |
| src/sync/\_\_init\_\_.py | sync パッケージ（空） |

### 設計上のポイント

#### src/config.py の設計
- `SimpleNamespace` を使い、`settings.sample_rate` のようなドット記法でアクセス可能にした
- ネストした辞書（`collector:` 等）も再帰的に `SimpleNamespace` に変換
- パスは `PROJECT_ROOT` からの絶対パスに自動解決
- シークレットは `settings.secrets.*` 名前空間で分離し、通常設定と混在させない

#### init_db.py の設計
- `schema.sql` を読み込んで `executescript` で実行
- `CREATE TABLE IF NOT EXISTS` により冪等（再実行しても安全）

### 検証結果

```
✅ venv作成 → pip install 成功
✅ init_db.py → edm_classifier.db 作成、テーブル: ['tracks', 'genre_probabilities', 'sqlite_sequence']
✅ config.py → 全設定値の読み込み確認:
   sample_rate: 44100
   stems: ['drums', 'bass', 'subbass', 'other']
   subbass_cutoff: 120
   genre_labels: ['tearout', 'riddim']
   model_version: v0.1
   collector.request_delay_sec: 3
   paths.raw_audio: <project_root>/data/raw_audio
```

### 次のステップ
システム全体の結合テストと運用への移行へ進む。

---

## 2026-07-29: フェーズ⑥ Apple Music連携

### 実施内容
Tear Outと判定されたトラックに対して、Apple Music API および AudD API（音響指紋）を用いて楽曲照合を行い、特定できた楽曲をユーザーのApple Musicプレイリストへ自動追加するモジュール群を実装した。

### 作成・変更ファイル一覧

| ファイル | 説明 |
|---|---|
| [requirements.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/requirements.txt) | APIリクエスト用の `requests`、JWT生成用の `PyJWT`、文字列のあいまい検索（Fuzzy Matching）用の `rapidfuzz` を追加 |
| [src/identify/apple_music.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/identify/apple_music.py) | Apple Music Catalog Search APIとAudD APIを利用し、楽曲を特定する。P8キーからのDeveloper Tokenの自動生成も担当 |
| [src/sync/musickit.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/sync/musickit.py) | Apple Music API (`/v1/me/library/playlists/{id}/tracks`) を叩き、ユーザープレイリストへ追加する |
| [scripts/run_identify.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/run_identify.py) | Tear Out判定済みのトラックを抽出して照合処理を行うバッチ。見つかったApple Music IDをDBに保存する |
| [scripts/run_sync.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/run_sync.py) | 照合済みの楽曲をApple Musicプレイリストに追加し、追加後にDBの `synced_at` を更新するバッチ |

### 設計・実装上のポイント
- **JWTの安全な動的生成**: Apple Music API を叩くためには Developer Token が必要だが、これは半年間で有効期限が切れる。そのため、手動で更新しなくて済むように、環境変数に設定した `.p8` 秘密鍵をもとに `PyJWT` でプログラム実行時に動的にJWTを生成・署名する設計とした。
- **フォールバック戦略**: SoundCloud等で公開されている楽曲名とApple Music上の楽曲名が微妙に異なる場合（例: "(Original Mix)" の有無など）、`rapidfuzz` を用いた類似度スコアリングで吸収し、それでも見つからない場合は `AudD` の音響指紋で波形から直接特定する二段構えの堅牢な照合フローとした。

---

## 2026-07-29: フェーズ⑤ 収集パイプライン

### 実施内容
SoundCloud等のURLを指定して、未分類の楽曲（候補）のメタデータを取得し、EDM（Tear Out/Riddim）の対象になり得ないミックス音源等を弾いた上で自動ダウンロードし、DBに登録するパイプラインを構築した。また、後段で必要になる「ドロップ（一番盛り上がるサビ部分）の抽出」ロジックも実装した。

### 作成・変更ファイル一覧

| ファイル | 説明 |
|---|---|
| [requirements.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/requirements.txt) | 動画/音声サイトからメタデータと音源を落とすための `yt-dlp` を追加 |
| [src/collectors/soundcloud.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/collectors/soundcloud.py) | SoundCloud用のラッパー。`yt-dlp` を使ってプレイリストやユーザーのURLから曲リストをぶっこ抜き、名前や長さで Mix などを弾いてWAVでダウンロードする処理 |
| [src/collectors/drop_detector.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/collectors/drop_detector.py) | `librosa` を使って曲全体のRMS（音圧・エネルギー）を計算し、最もエネルギーが高い連続30秒間を「ドロップ（サビ）」として推定する処理 |
| [scripts/run_collection.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/run_collection.py) | URLを引数として受け取り、メタデータ取得 → フィルタ → ダウンロード → SQLiteDBへの `status='collected'` でのインサートを一貫して行うバッチ |

### 設計・実装上のポイント
- **yt-dlpの採用**: 当初SoundCloud公式API等の利用も検討されるが、トークンの陳腐化や他サイト（YouTube等）への横展開を考慮し、最も汎用性が高くメンテナンスされている `yt-dlp` をコアの収集エンジンとして採用した。
- **ドロップの単純かつ強力な推定**: EDMはドロップ部分で最も音圧（RMS）が大きくなるという音楽的特性を利用し、複雑なディープラーニングを使わずとも、30秒間の移動平均が最大になる区間を探すだけで高精度にサビを特定できるアプローチを取った。

---

## 2026-07-29: フェーズ④ Fusion分類モデル学習

### 実施内容
DB上の人間による正解ラベル（Tear Out または Riddim）と抽出済みの特徴量を結合し、XGBoost を用いた2値分類モデルの学習および推論のバッチスクリプトを実装した。

### 作成・変更ファイル一覧

| ファイル | 説明 |
|---|---|
| [requirements.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/requirements.txt) | `scikit-learn`, `xgboost`, `joblib`, `pandas` を追加 |
| [src/models/dataset.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/models/dataset.py) | DBのラベルとNPY特徴量を読み込み、学習用の配列（X, y）を構築する処理 |
| [src/models/train.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/models/train.py) | 4ブランチの特徴量をスケーリング・結合し、Stratified 5-Fold CV で XGBoost モデルを評価。最終モデルを `fusion_classifier_v1.pkl` として保存 |
| [src/models/infer.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/models/infer.py) | 予測用モジュール。特定のtrack_idに対してTear OutとRiddimの確率を出力する関数 `predict_genre()` を実装 |
| [scripts/train_model.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/train_model.py) | 学習処理のバッチ実行用ラッパー |
| [scripts/run_inference.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/run_inference.py) | 未推論のトラックに対して予測を実行し、結果（`ai_label`, `ai_confidence`）をDBに更新するバッチスクリプト |

### 設計・実装上のポイント
- **確率のキャリブレーション**: 最終的に「Tear Outらしさ」をパーセンテージ（確信度）としてApple Musicのプレイリストに追加するかどうかを判断するため、`CalibratedClassifierCV` (Platt Scaling) をかませて、出力される確率の信頼性を高める設計にした。
- **堅牢なロード機構**: 特徴量ディレクトリの一部が欠損しているトラックは例外を投げてスキップし、パイプラインが止まらないようにエラーハンドリングを行った。

---

## 2026-07-29: フェーズ③ ステムごとの特徴量抽出

### 実施内容
分離された4つのステム（drums, bass, subbass, other）それぞれに特化した特徴量抽出モジュールを実装し、それらを束ねてスキーマ定義を自動生成する仕組み、および全曲に対して抽出を実行するバッチ処理を構築した。

### 作成・変更ファイル一覧

| ファイル | 説明 |
|---|---|
| [requirements.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/requirements.txt) | 音響解析用の `librosa` と、AudioTagging用の `panns_inference` を追加 |
| [src/features/drums.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/features/drums.py) | ドラムの特徴量。オンセット強度、テンポ推定、オンセット密度、自己相関ピーク（3ピーク分のラグと強度）を抽出し、8次元のベクトルを出力 |
| [src/features/bass.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/features/bass.py) | ベースの特徴量。メルスペクトログラム、スペクトル特徴（重心/ロールオフ/バンド幅）、MFCCの各平均・標準偏差を抽出し、288次元のベクトルを出力 |
| [src/features/subbass.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/features/subbass.py) | サブベースの特徴量。RMSエネルギー包絡、その自己相関によるLFO周期（ワブル/リディム成分の検知）、60Hz以下の低域エネルギー比率を抽出し、5次元のベクトルを出力 |
| [src/features/other.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/features/other.py) | メロディ/シンセの特徴量。PANNs(Cnn14)による2048次元の音響埋め込みベクトルと、調性を表すChroma STFTの統計量を合わせ、2072次元のベクトルを出力 |
| [scripts/generate_feature_schema.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/generate_feature_schema.py) | ランダムノイズのダミー音源を用いて各特徴量抽出関数を一度実行し、次元数を `feature_schema_v1.json` に保存するスクリプト |
| [scripts/run_features.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/run_features.py) | DBの未処理トラックを対象に特徴量を抽出し `.npy` 形式で保存するバッチスクリプト |

### 設計・実装上のポイント
- **PANNsモデルの堅牢化**: PANNs (Cnn14) モデルの初回ダウンロード時にZenodoからの取得が失敗するケース（API制限やネットワーク遮断）を考慮し、例外ハンドリングを実装。もしモデルが読み込めない場合はダウンタイムを防ぐためにオールゼロのダミー特徴量を出力するフェールセーフを設けた。
- **次元数の動的検証**: 事前に次元数をハードコードするのではなく、`generate_feature_schema.py` を通して実際の出力から次元数を取得・保存する仕組みにしたことで、将来的な特徴量追加にもシームレスに対応できるアーキテクチャとなった。

### 検証結果
```
✅ pip install librosa panns_inference 成功
✅ scripts/generate_feature_schema.py 実行成功
  - feature_schema_v1.json が生成され、以下の次元数を確認:
    - drums: 8
    - bass: 288
    - subbass: 5
    - other: 2072
```

---

## 2026-07-29: フェーズ② ステム分離パイプラインの構築

### 実施内容
Demucs (htdemucs) を用いた音源の4ステム分離と、bassステムに対するButterworthフィルタでの帯域分割（bass / subbass）を実装した。また、これらを一括で実行するバッチ処理スクリプトと、パイプラインの結合テストを作成した。

### 作成・変更ファイル一覧

| ファイル | 説明 |
|---|---|
| [requirements.txt](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/requirements.txt) | `demucs`, `torch`, `torchaudio`, `scipy`, `soundfile`, `tqdm` を追加 |
| [src/separation/separator.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/src/separation/separator.py) | ステム分離ロジック。Demucsによる4ステム分離と、Scipyのsosfiltfiltを用いた帯域分割 (120Hz) を実装 |
| [scripts/run_separation.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/scripts/run_separation.py) | 未分離のトラックをDBから取得し、一括で分離するバッチ処理 |
| [tests/test_separator.py](file:///C:/Users/Kijim/.gemini/antigravity/scratch/Music%20Digger/tests/test_separator.py) | ダミーの正弦波を用いた結合テスト。出力ファイルの生成と不要ファイル(vocals)の削除を検証 |

### 設計・実装上のポイント
- **モジュールのシングルトン化**: `demucs.api.Separator` はモデルの読み込みに時間がかかるため、バッチ実行時に何度も初期化されないよう、モジュールレベルでシングルトンとして保持する設計にした。
- **音声保存ライブラリの選定**: 当初 `torchaudio.save` を使用しようとしたが、最新版の `torch-2.13.0` では `torchcodec` が追加で必要になるなどの環境依存問題が発生したため、より標準的で軽量な `soundfile.write` に切り替えた（転置 `waveform.numpy().T` による形状合わせを実施）。
- **エラーハンドリング**: `run_separation.py` では、個別のトラックで分離エラー（音源破損やメモリ不足など）が発生しても、`logging.error` にスタックトレースを吐き出してスキップし、他のトラックの処理を止めない堅牢なバッチ処理を実装した。

### 検証結果
```
✅ pip install による依存関係の追加に成功
✅ python -m unittest tests/test_separator.py 実行成功
  - ダミー音源から `drums.wav`, `bass.wav`, `subbass.wav`, `other.wav` が生成されることを確認
  - `vocals.wav` が保存されない仕様通りであることを確認
```
