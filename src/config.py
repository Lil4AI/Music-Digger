"""
EDMサブジャンル自動判定システム — 設定ユーティリティ

settings.yaml と .env の両方を読み込み、1つの設定オブジェクトにまとめる。
他モジュールからは `from src.config import settings` の形で使う。

シークレットは settings.secrets.soundcloud_client_id のように名前空間で分離。
"""

import os
from pathlib import Path
from types import SimpleNamespace

import yaml
from dotenv import load_dotenv

# プロジェクトルートの解決（src/ の親ディレクトリ）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# .env を読み込む（存在しなくてもエラーにしない）
load_dotenv(PROJECT_ROOT / ".env")


def _dict_to_namespace(d: dict) -> SimpleNamespace:
    """ネストした辞書を再帰的に SimpleNamespace に変換する。"""
    ns = SimpleNamespace()
    for key, value in d.items():
        if isinstance(value, dict):
            setattr(ns, key, _dict_to_namespace(value))
        else:
            setattr(ns, key, value)
    return ns


def _load_settings() -> SimpleNamespace:
    """settings.yaml と .env を統合した設定オブジェクトを返す。"""
    settings_path = PROJECT_ROOT / "config" / "settings.yaml"

    with open(settings_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    cfg = _dict_to_namespace(raw)

    # プロジェクトルートを設定オブジェクトに追加
    cfg.project_root = PROJECT_ROOT

    # パスを絶対パスに解決
    if hasattr(cfg, "paths"):
        resolved = SimpleNamespace()
        for key in vars(cfg.paths):
            rel = getattr(cfg.paths, key)
            setattr(resolved, key, str(PROJECT_ROOT / rel))
        cfg.paths = resolved

    # シークレット（.env から読み込み、名前空間で分離）
    cfg.secrets = SimpleNamespace(
        soundcloud_client_id=os.getenv("SOUNDCLOUD_CLIENT_ID", ""),
        soundcloud_client_secret=os.getenv("SOUNDCLOUD_CLIENT_SECRET", ""),
        apple_music_team_id=os.getenv("APPLE_MUSIC_TEAM_ID", ""),
        apple_music_key_id=os.getenv("APPLE_MUSIC_KEY_ID", ""),
        apple_music_private_key_path=os.getenv("APPLE_MUSIC_PRIVATE_KEY_PATH", ""),
        audd_api_key=os.getenv("AUDD_API_KEY", ""),
    )

    return cfg


# モジュールレベルで設定を公開
# 他モジュールから: from src.config import settings
settings = _load_settings()
