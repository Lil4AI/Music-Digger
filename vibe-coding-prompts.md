# EDMサブジャンル自動判定システム — バイブコーディング用プロンプト集

全6フェーズ。**必ず①から順番に実行すること。** 各プロンプトの冒頭にある
「CONTRACTS.mdを読め」という指示は省略しないこと。これが複数セッションに
分けて開発する際の一貫性を保つ唯一の仕組み。

---

## フェーズ①: プロジェクト基盤（最初に実行）

```
あなたはPython音楽解析システムの開発を手伝うエンジニアです。
以下の仕様で、EDMサブジャンル自動判定システムのプロジェクト基盤を作ってください。

【目的】
ステム分離(ドラム/ベース/サブベース/メロディ代理)ごとに特徴量を抽出し、
マルチブランチ融合モデルでEDMサブジャンル(Tear Out, Riddim等)を
確率付きで判定し、Apple Musicプレイリストへ自動同期するシステムの基盤を作る。
この後複数回に分けて別セッションで開発を続けるため、今回作る
CONTRACTS.mdが以降すべてのフェーズの「唯一の正」になる。

【要件】

1. Python 3.11を前提にする。venv作成手順をREADMEに書く。

2. 以下のディレクトリ構成でプロジェクトを初期化する:
   project/
     config/settings.yaml
     config/seed_djs.txt          # 空ファイルでよい(収集対象DJのURLリスト用)
     data/raw_audio/
     data/stems/
     data/features/
     data/labels/
     db/
     models/
     src/collectors/__init__.py
     src/separation/__init__.py
     src/features/__init__.py
     src/models/__init__.py
     src/identify/__init__.py
     src/sync/__init__.py
     src/config.py
     scripts/init_db.py
     CONTRACTS.md
     README.md
     requirements.txt
     .env.example
     .gitignore

3. CONTRACTS.md を作成し、以下の内容をそのまま記載する(これが以降の
   全フェーズが参照する共有契約。中身は変更せずそのまま書くこと):

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

4. config/settings.yaml に以下を含める(YAML形式、コメント付き):
   - sample_rate: 44100
   - stems: [drums, bass, subbass, other]
   - subbass_cutoff_hz: 120
   - genre_labels: [tearout, riddim]  # MVPは2値、後で拡張
   - drop_segment_seconds: 18
   - model_version: "v0.1"
   - collector:
       request_delay_sec: 3
       max_concurrency: 2
       min_follower_count: 500
   - paths: (上記ディレクトリを変数として定義)

5. db/schema.sql を作成し、CONTRACTS.mdに記載したスキーマ通りに定義する。

6. scripts/init_db.py を作成(SQLite、schema.sqlを読み込んで実行、
   既に存在する場合はスキップするようにする)。

7. src/config.py に、settings.yamlと.envの両方を読み込んで1つの
   設定オブジェクトにまとめるユーティリティを作成。他モジュールから
   `from src.config import settings` の形で使えるようにする。
   シークレットは settings.secrets.soundcloud_client_id のように
   名前空間を分ける。

8. requirements.txt: PyYAML, python-dotenv のみ(音声処理系は次フェーズ以降)。

9. .env.example に、CONTRACTS.mdのシークレット変数名を空値で列挙。

10. .gitignore に以下を含める: data/, db/*.db, .env, __pycache__/, *.pyc,
    .venv/, models/

11. README.md に、プロジェクトの目的、ディレクトリ構成、セットアップ手順
    (venv作成→pip install→python scripts/init_db.py)、そして
    「新しいフェーズを実装する際は必ずCONTRACTS.mdを先に読むこと」という
    一文を書く。

【注意】
- この段階では音声処理のロジックは書かない。基盤(config, DB, ディレクトリ,
  CONTRACTS.md)のみ。
- src/配下の各サブディレクトリは __init__.py だけ置いて空にしておく。
```

---

## フェーズ②: ステム分離パイプライン

```
プロジェクトルートにある CONTRACTS.md と config/settings.yaml を
必ず最初に読み込んで、そこに書かれているディレクトリ構成・命名規則・
DBスキーマに厳密に従ってください。矛盾する実装をしないこと。

【目的】
data/raw_audio/ にある音源をDemucsで4ステムに分離し、bassステムを
さらに帯域分割してsubbassを作る、src/separation/ のパイプラインを実装する。

【要件】

1. requirements.txt に demucs, torch, torchaudio, scipy, soundfile を追加。

2. src/separation/separator.py を作成し、以下の関数を実装:
   - separate_track(track_id: str, raw_audio_path: str) -> dict
     - Demucs(htdemucsモデル)で4ステム(drums, bass, vocals, other)に分離
     - drums, other はそのまま data/stems/{track_id}/ に保存
     - vocals は保存しない(分類に使わないため、ディスク節約)
     - bass ステムに対して scipy.signal のButterworthフィルタで帯域分割:
       - subbass_cutoff_hz(config値)未満 → data/stems/{track_id}/subbass.wav
       - subbass_cutoff_hz以上         → data/stems/{track_id}/bass.wav
     - 処理が成功したら戻り値として各ファイルパスの辞書を返す

3. scripts/run_separation.py を作成:
   - DBから `separated_at IS NULL` の track を全件取得
   - 各trackに対して separate_track を呼ぶ
   - 成功したら tracks.separated_at を現在時刻で更新
   - 失敗した場合はスタックトレースをログファイル(logs/separation.log)に
     出力し、そのtrackはスキップして次に進む(バッチ全体を止めない)
   - 進捗をコンソールに表示(tqdm等)

4. GPU利用可能なら自動でGPUを使い、無ければCPUにフォールバックする
   (torch.cuda.is_available()で判定)。

5. 簡単な単体テスト(tests/test_separator.py)を1つ用意し、ダミーの
   短い正弦波wavファイルを入力として、4つの出力ファイルが期待した
   パスに生成されることだけを確認する(分離精度のテストではなく、
   パイプラインの配線が壊れていないかの確認)。

【注意】
- 特徴量抽出やモデル学習のロジックはここでは書かない。ステム分離まで。
- Demucsのモデルダウンロードは初回実行時に自動で行われる前提でよい。
```

---

## フェーズ③: ステムごとの特徴量抽出

```
プロジェクトルートにある CONTRACTS.md と config/settings.yaml を
必ず最初に読み込んで、ディレクトリ構成・命名規則に厳密に従ってください。

【目的】
data/stems/{track_id}/ の4つのwavファイルそれぞれから、固定長の
特徴ベクトルを抽出し、data/features/{track_id}/ に保存する
src/features/ パイプラインを実装する。

【重要な制約】
どのブランチの特徴抽出関数も、音源の長さに関わらず必ず同じ次元数の
1次元float32配列を返すこと(後段のFusionモデルが固定長入力を要求する
ため)。時系列特徴は必ず統計量(mean, std, max等)に集約してから返す。

【要件】

1. requirements.txt に librosa, panns_inference を追加。

2. src/features/drums.py — extract_drums_features(wav_path) -> np.ndarray
   - librosa.onset.onset_strength でオンセット強度包絡を計算
   - テンポ推定(librosa.beat.tempo)
   - オンセット密度(1秒あたりのオンセット数)
   - オンセット強度包絡の自己相関を計算し、上位3ピークのlag(周期性)と
     強度を抽出(リズムパターンの反復性を捉える)
   - 上記すべてを結合した固定長ベクトルを返す

3. src/features/bass.py — extract_bass_features(wav_path) -> np.ndarray
   - メルスペクトログラムを計算し、mel bin方向にmean/stdで集約
   - スペクトル重心・ロールオフ・バンド幅のmean/std
   - MFCC 13次元のmean/std(26次元)
   - 固定長ベクトルとして結合して返す
   ※ subbass.py も同一ロジックの関数として用意してよいが、後述の
   wobble周期性の方がsubbassでは重要なので4を優先実装すること。

4. src/features/subbass.py — extract_subbass_features(wav_path) -> np.ndarray
   - 短時間フレームでRMSエネルギー包絡を計算
   - RMSエネルギー包絡の自己相関から、支配的な周期(lag→Hz変換)と
     そのピーク強度を抽出(ワブル/リディムパターンのLFO周期を捉える
     ための特徴。ここが Tear Out と Riddim を分ける鍵になる想定)
   - 低域エネルギー比率(全体エネルギーに対するサブベース帯域の割合)
   - 固定長ベクトルとして結合して返す

5. src/features/other.py — extract_other_features(wav_path) -> np.ndarray
   - panns_inference(Cnn14の事前学習モデル)で埋め込みベクトルを抽出
   - librosa.feature.chroma_stft のmean/stdも追加(調性/メロディの補助特徴)
   - 埋め込み+chroma統計量を結合して返す

6. data/features/feature_schema_v1.json を生成するスクリプト
   scripts/generate_feature_schema.py を作成:
   - 上記4関数をダミー音源に対して1回ずつ実行し、各ブランチの出力次元数と
     (可能な範囲で)特徴名リストを記録したJSONを feature_schema_v1.json
     として保存する

7. scripts/run_features.py を作成:
   - DBから `separated_at IS NOT NULL AND features_extracted_at IS NULL`
     のtrackを全件取得
   - 4ブランチそれぞれの特徴抽出関数を呼び、data/features/{track_id}/ に
     drums.npy, bass.npy, subbass.npy, other.npy として保存
   - 成功したら tracks.features_extracted_at を更新
   - 失敗はログに記録してスキップ、バッチは継続

【注意】
- モデル学習のロジックはここでは書かない。特徴抽出と保存まで。
- panns_inferenceの事前学習済み重みは初回実行時に自動ダウンロードされる
  前提でよい。
```

---

## フェーズ④: Fusion分類モデル学習(Tear Out vs Riddim MVP)

```
プロジェクトルートにある CONTRACTS.md と config/settings.yaml を
必ず最初に読み込んで、特徴量の保存場所・DBスキーマに厳密に従ってください。

【目的】
data/labels/tearout_riddim_labels.csv(track_id, genre_label の2列、
手動またはブートストラップで用意済みの想定)をもとに、4ブランチの
特徴ベクトルを使ってTear Out / Riddimの2値分類モデルを学習し、
較正済み確率を出力できるようにする。

【設計方針(重要)】
ラベル付きデータが少ない前提(数百件規模を想定)なので、深いニューラル
ネットではなく、まず低容量のモデル(ロジスティック回帰またはGradient
Boosting)から始める。ただし4ブランチの特徴を「まとめて1本のベクトルに
concatしてから学習する」書き方にはするが、後で多ブランチニューラルネット
に差し替えやすいよう、データローディング部分は4ブランチを辞書として
分離したまま扱えるようにしておく。

【要件】

1. requirements.txt に scikit-learn, xgboost, joblib を追加。

2. src/models/dataset.py — 以下を実装:
   - load_labeled_dataset(labels_csv_path) -> (features_dict, labels)
     - labels_csv_path を読み込み、各track_idについて
       data/features/{track_id}/{drums,bass,subbass,other}.npy を読み込む
     - 4ブランチをキーとする辞書 {branch_name: np.ndarray(N, dim)} と、
       ラベル配列(N,)を返す
     - 欠損している特徴ファイルがあるtrackはスキップし、警告をログ出力

3. src/models/train.py — 以下を実装:
   - 4ブランチの特徴を標準化(StandardScaler、ブランチごとに別々にfit)
   - 標準化後、4ブランチをconcatして1本のベクトルにする
   - 5-fold層化交差検証(StratifiedKFold)で以下を比較できるようにする:
     a) LogisticRegression(class_weight='balanced')
     b) GradientBoostingClassifier
     c) xgboost.XGBClassifier
   - 各foldでaccuracy, F1, 混同行列を記録し、平均を metrics.json に保存
   - 最も良かったモデルタイプを全データで再学習
   - sklearn.calibration.CalibratedClassifierCV で確率較正をかける
     (method='sigmoid'、cv=5)
   - 学習済みスケーラー・較正済みモデルを
     models/{model_version}/model.pkl として joblib で保存
     (settings.model_versionをディレクトリ名に使う)

4. scripts/train_model.py — train.pyの関数を呼び出すだけの実行スクリプト。
   実行後、models/{model_version}/metrics.json の中身をコンソールに
   要約表示する(accuracy, F1, 各foldの値)。

5. src/models/infer.py — 以下を実装:
   - load_model(model_version) -> モデル・スケーラーのロード
   - predict_proba(track_id, model) -> dict
     - data/features/{track_id}/ の4ブランチを読み込み→標準化→concat→
       較正済みモデルで予測確率を計算
     - {"tearout": 0.8, "riddim": 0.2} のような辞書を返す

6. scripts/run_inference.py — 以下を実装:
   - DBから `features_extracted_at IS NOT NULL AND classified_at IS NULL`
     のtrackを全件取得
   - 各trackについて predict_proba を実行
   - 結果を genre_probabilities テーブルに
     (track_id, genre_label, probability, model_version)として複数行
     INSERT(ジャンルごとに1行)
   - tracks.classified_at を更新
   - 失敗はログに記録してスキップ

【注意】
- Apple Music連携やSoundCloud収集のコードはここでは書かない。
- ラベルCSVの中身を生成するスクリプトは別フェーズ(収集パイプライン)の
  範囲外の想定。このフェーズでは「CSVは既に存在する」前提で進めてよい。
```

---

## フェーズ⑤: 収集パイプライン(SoundCloud → ダウンロード → ドロップ検出)

```
プロジェクトルートにある CONTRACTS.md と config/settings.yaml を
必ず最初に読み込んで、track_idの生成規則・DBスキーマ・レート制限
設定に厳密に従ってください。

【目的】
config/seed_djs.txt に列挙されたSoundCloudユーザーのいいね/リポストから
トラックURLを収集し、音源をダウンロード、メタデータで事前フィルタし、
ドロップ区間を自動検出してDBに登録する src/collectors/ パイプラインを
実装する。

【要件】

1. requirements.txt に yt-dlp, librosa を追加。

2. config/seed_djs.txt の各行にSoundCloudのユーザープロフィールURLを
   1つずつ書く形式とする(例のコメント行を追加しておく)。

3. src/collectors/soundcloud.py — 以下を実装:
   - fetch_candidate_tracks(user_url: str) -> list[dict]
     - yt-dlpの --flat-playlist 相当の機能で、そのユーザーの
       いいね/リポスト一覧からトラックURL・タイトル・アップローダー名・
       フォロワー数などのメタデータを取得(ダウンロードはまだしない)
   - passes_prefilter(track_meta: dict) -> bool
     - config.collector.min_follower_count 未満のアップローダーは除外
     - その他タグベースのフィルタ(必要なら実装、なければタイトル/
       アップローダー情報のみでよい)
   - download_track(track_url: str) -> dict
     - yt-dlpで音源をダウンロードし、data/raw_audio/{track_id}.{ext}
       に保存(track_idはCONTRACTS.mdの規則通りsource_urlのhash)
     - リクエスト間に config.collector.request_delay_sec 秒のスリープを
       必ず入れる
     - config.collector.max_concurrency を超える同時ダウンロードを
       しないよう、非同期処理の並列数を制限する
     - ダウンロード後、tracks テーブルに
       (track_id, source='soundcloud', source_url, title, artist,
       raw_audio_path, created_at) をINSERT。source_urlがすでに
       存在する場合はスキップ(重複防止)

4. src/collectors/drop_detector.py — 以下を実装:
   - detect_drop_segment(wav_path: str, segment_seconds: float) -> tuple
     - librosaでRMSエネルギー包絡を計算
     - segment_seconds幅のスライディングウィンドウで、平均エネルギーが
       最大になる区間を探す
     - (drop_start_sec, drop_end_sec) を返す

5. scripts/run_collection.py — 以下を実装:
   - config/seed_djs.txt を読み込み、各DJについて
     fetch_candidate_tracks → passes_prefilterでフィルタ →
     download_track の順で処理
   - ダウンロード成功後、detect_drop_segmentを実行し、
     tracks.drop_start_sec / drop_end_sec を更新
   - 失敗(非公開トラック、地域制限、yt-dlpエラー等)はログ
     (logs/collection.log)に記録してスキップ、バッチは継続
   - 実行完了後、今回新規追加した件数をコンソールに表示

【注意】
- ステム分離・特徴抽出・モデル学習のコードはここでは書かない。
- yt-dlpの内部APIは予告なく変更される可能性があるため、ダウンロード
  部分の関数はsrc/collectors/soundcloud.py内で完結させ、他モジュールから
  直接yt-dlpを呼ばないようにする(将来の修正を1ファイルに閉じ込めるため)。
```

---

## フェーズ⑥: Apple Music連携(照合 + プレイリスト同期)

```
プロジェクトルートにある CONTRACTS.md と config/settings.yaml を
必ず最初に読み込んで、DBスキーマ・シークレットの受け渡し方法に
厳密に従ってください。

【目的】
genre_probabilitiesに確率が入っているtrackについて、Apple Music
カタログ上の曲を特定し(まずテキスト照合、ダメならAudDでフォールバック)、
config.yamlのルールに従って対象プレイリストへ自動追加する
src/identify/ と src/sync/ を実装する。

【要件】

1. requirements.txt に requests, pyjwt, rapidfuzz を追加。

2. config/settings.yaml に以下を追加:
   - identify:
       text_match_min_score: 85   # rapidfuzzのスコア閾値(0-100)
   - sync_rules:
       - genre: tearout
         min_probability: 0.6
         playlist_id: "REPLACE_ME"
       - genre: riddim
         min_probability: 0.6
         playlist_id: "REPLACE_ME"

3. src/identify/apple_music.py — 以下を実装:
   - generate_developer_token() -> str
     - .envのAPPLE_MUSIC_TEAM_ID, APPLE_MUSIC_KEY_ID,
       APPLE_MUSIC_PRIVATE_KEY_PATHを使い、ES256でJWTを署名して
       developer tokenを生成(pyjwt使用)
   - search_catalog(title: str, artist: str) -> dict | None
     - Apple Music Catalog Search API(developer tokenのみ、ユーザー
       トークン不要)にtitle+artistでクエリ
     - 上位候補とrapidfuzzで類似度スコアを計算し、
       identify.text_match_min_score 以上ならその曲のIDを返す
     - 閾値未満ならNoneを返す
   - identify_via_auddfallback(audio_clip_path: str) -> str | None
     - .envのAUDD_API_KEYを使い、drop区間の音声クリップをAudDに送信して
       フィンガープリント照合、Apple Music IDが取れればそれを返す
     - (AudDのレスポンスにApple Music IDが含まれない場合は、
       返ってきたタイトル/アーティストで再度search_catalogを呼ぶ
       フォールバックにする)

4. scripts/run_identify.py:
   - DBから `classified_at IS NOT NULL AND identified_at IS NULL` の
     trackを全件取得
   - まずsearch_catalogでテキスト照合
   - スコア不足ならidentify_via_auddfallbackを実行
   - 結果が得られたら tracks.apple_music_id, identified_at を更新
   - 得られなければログに記録してスキップ(次回再試行できるよう
     identified_atは更新しない)

5. src/sync/musickit.py — 以下を実装:
   - このモジュールはプレイリスト書き込み(ユーザーのライブラリ変更)を
     行うため、Music User Tokenが必要。初回のみブラウザベースの
     MusicKit JS認可フローを踏んで取得し、ローカルファイル
     (例: .music_user_token、.gitignoreに追加済みのはず)に保存して
     再利用する仕組みにする(認可フローの実装は簡易なローカルHTTPサーバー
     +ブラウザ起動でよい)
   - add_to_playlist(apple_music_id: str, playlist_id: str) -> bool
     - developer token + music user token を使い、MusicKit APIで
       指定プレイリストに曲を追加

6. scripts/run_sync.py:
   - DBから `identified_at IS NOT NULL AND sync_status IS NULL` の
     trackを全件取得
   - 各trackについて、genre_probabilitiesを見て
     config.sync_rulesの条件(genre一致 かつ probability >= min_probability)
     に該当するルールがあれば、そのplaylist_idにadd_to_playlist
   - 成功したら tracks.sync_status='synced', synced_at を更新
   - どのルールにも該当しなければ tracks.sync_status='no_match'を設定
     (再試行不要として扱う)
   - 失敗(API エラー等)はログに記録し、sync_statusは更新しない
     (次回再試行対象として残す)

【注意】
- ここまででパイプライン全体が完成する。scripts/配下の
  run_collection.py → run_separation.py → run_features.py →
  run_inference.py → run_identify.py → run_sync.py を順番にcronで
  実行すれば全自動になる、という前提で最後にREADME.mdに
  実行順序とcron設定例を追記すること。
```
