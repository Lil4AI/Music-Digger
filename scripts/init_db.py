"""
EDMサブジャンル自動判定システム — DB初期化スクリプト

db/schema.sql を読み込み、SQLiteデータベースを作成する。
既にテーブルが存在する場合はスキップ（CREATE TABLE IF NOT EXISTS）。
"""

import sqlite3
import sys
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def init_db():
    """schema.sql を読み込んでSQLiteデータベースを初期化する。"""
    schema_path = PROJECT_ROOT / "db" / "schema.sql"
    db_path = PROJECT_ROOT / "db" / "edm_classifier.db"

    # db/ ディレクトリが存在することを確認
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not schema_path.exists():
        print(f"エラー: スキーマファイルが見つかりません: {schema_path}")
        sys.exit(1)

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()

        # スキーマ更新時に既存DBへ新列を追加するマイグレーション
        # ALTER TABLE IF NOT EXISTS はSQLiteで非対応のため try/except で対応
        migrations = [
            "ALTER TABLE tracks ADD COLUMN genre_hint TEXT",
            "ALTER TABLE tracks ADD COLUMN researched_at TIMESTAMP",
        ]
        for sql in migrations:
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 既に存在する列はスキップ

        print(f"データベースを初期化しました: {db_path}")
    except sqlite3.Error as e:
        print(f"DB初期化エラー: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
