# EDMサブジャンル自動判定システム

SoundCloudからEDMトラックを収集し、ステム分離（ドラム/ベース/サブベース/メロディ代理）ごとに特徴量を抽出、マルチブランチ融合モデルでEDMサブジャンル（Tear Out, Riddim等）を確率付きで判定し、Apple Musicプレイリストへ自動同期するシステム。

## ディレクトリ構成

```
project/
  config/
    settings.yaml          # 全体設定（サンプルレート、ジャンルラベル等）
    seed_djs.txt           # 収集対象DJのSoundCloudプロフィールURL
  data/
    raw_audio/             # ダウンロード済み音源
    stems/                 # ステム分離結果（track_idごとのサブディレクトリ）
    features/              # 特徴ベクトル（track_idごとのサブディレクトリ）
    labels/                # ジャンルラベルCSV
  db/
    schema.sql             # DBスキーマ定義（正）
    edm_classifier.db      # SQLiteデータベース（gitignore対象）
  models/                  # 学習済みモデル（バージョンごとのサブディレクトリ）
  src/
    config.py              # 設定読み込みユーティリティ
    collectors/            # SoundCloud収集・ドロップ検出
    separation/            # Demucsステム分離・帯域分割
    features/              # ステムごとの特徴量抽出
    models/                # 分類モデル学習・推論
    identify/              # Apple Music楽曲照合
    sync/                  # Apple Musicプレイリスト同期
    api/                   # FastAPI バックエンドサーバー
  tests/                   # Pytest テストスイート
  scripts/                 # CLI実行スクリプト
  run_pipeline.bat         # パイプライン一括実行用バッチ
  run_tests.bat            # テストスイート一括実行用バッチ
  CONTRACTS.md             # 全モジュール共有の契約（唯一の正）
  requirements.txt         # Python依存パッケージ
  .env.example             # シークレット変数テンプレート
```

## セットアップ

### 1. 仮想環境の作成

```bash
python -m venv .venv
```

### 2. 仮想環境の有効化

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. データベースの初期化

```bash
python scripts/init_db.py
```

### 5. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各シークレットの値を設定する:

```bash
cp .env.example .env
```

## 開発ルール

> **⚠️ 重要:** 新しいフェーズを実装する際は、必ず `CONTRACTS.md` を先に読むこと。
> CONTRACTS.md が全モジュール共有の唯一の正であり、ディレクトリ構成・命名規則・
> DBスキーマ・運用ルールはすべてこのファイルに従う。

## 実行方法

当システムは、手動でのスクリプト実行、一括バッチ実行、およびAPIサーバー経由での実行をサポートしています。

### 1. APIサーバーとしての実行（推奨）

ダッシュボードUIやブラウザからシステムを操作するためのバックエンドサーバーです。

```bash
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
起動後、ブラウザで `http://localhost:8000` にアクセスしてください。

### 2. パイプラインの一括実行（CLI）

URLを指定して、全6ステップの処理を自動で順次実行するバッチファイルです。

```powershell
.\run_pipeline.bat "https://soundcloud.com/dj-name/sets/playlist-url"
```

### 3. テストの実行

プロジェクト全体の正常性を確認するためのテストスイートです（約10秒で完了します）。

```powershell
.\run_tests.bat
```

### （参考）手動での各ステップ実行

個別にモジュールを動かしたい場合は、以下の順でスクリプトを実行します。

1. `python scripts/run_collection.py` — SoundCloudからトラック収集
2. `python scripts/run_separation.py` — ステム分離
3. `python scripts/run_features.py` — 特徴量抽出
4. `python scripts/run_inference.py` — ジャンル分類推論
5. `python scripts/run_identify.py` — Apple Music楽曲照合
6. `python scripts/run_sync.py` — プレイリスト同期

## ライセンス

Private project.
