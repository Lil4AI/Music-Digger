# CONTRACTS.md — 全モジュール共有の契約(このファイルが唯一の正)

## track_id
sha256(source_url) の先頭16文字(hex)。同じ曲を再取得しても同じIDに
なる(冪等性)。Pythonでの生成例: hashlib.sha256(url.encode()).hexdigest()[:16]

## ディレクトリ / ファイル命名規則
- data/raw_audio/{track_id}.{ext}
- data/stems/{track_id}/drums.wav
- data/stems/{track_id}/bass.wav       # subbass_cutoff_hz以上(帯域分割後)
- data/stems/{track_id}/subbass.wav    # subbass_cutoff_hz未満
- data/stems/{track_id}/other.wav      # メロディ/シンセ/パッドの代理ステム
  (vocalsステムは分類に使わないため保存しない)
- data/features/{track_id}/drums.npy
- data/features/{track_id}/bass.npy
- data/features/{track_id}/subbass.npy
- data/features/{track_id}/other.npy
- data/features/feature_schema_v1.json  # 各npyの次元・特徴名の並び順を
  定義する唯一のファイル。全trackで共通。
- data/labels/{genre_pair}_labels.csv   # columns: track_id,genre_label
- models/{model_version}/model.pkl
- models/{model_version}/calibration.pkl
- models/{model_version}/metrics.json

## DBスキーマ (db/schema.sql が正、ここは要約)
tracks(
  track_id TEXT PRIMARY KEY,
  source TEXT,
  source_url TEXT UNIQUE,
  title TEXT,
  artist TEXT,
  raw_audio_path TEXT,
  drop_start_sec REAL,
  drop_end_sec REAL,
  separated_at TIMESTAMP,
  features_extracted_at TIMESTAMP,
  classified_at TIMESTAMP,
  apple_music_id TEXT,
  identified_at TIMESTAMP,
  sync_status TEXT,
  synced_at TIMESTAMP,
  status TEXT,
  ai_label TEXT,
  ai_confidence REAL,
  human_label TEXT,
  created_at TIMESTAMP
)
genre_probabilities(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  track_id TEXT REFERENCES tracks(track_id),
  genre_label TEXT,
  probability REAL,
  model_version TEXT,
  created_at TIMESTAMP
)

## .envで渡すシークレット(コミットしない。.env.exampleに変数名だけ列挙)
SOUNDCLOUD_CLIENT_ID
SOUNDCLOUD_CLIENT_SECRET
APPLE_MUSIC_TEAM_ID
APPLE_MUSIC_KEY_ID
APPLE_MUSIC_PRIVATE_KEY_PATH
AUDD_API_KEY

## 運用ルール
- 新しいテーブル列・新しいファイル形式が必要になったら、実装前に必ず
  このファイルとdb/schema.sqlを更新してから着手すること。
- 各フェーズのCLIスクリプトは、対象となる*_atカラムがNULLのtrackだけを
  処理し、完了したら該当カラムにタイムスタンプを書き込むこと
  (冪等・再実行可能にする。cronでの定期実行を前提とするため)。
- 失敗したtrackはクラッシュさせず、ログに記録してバッチ処理を継続する。
