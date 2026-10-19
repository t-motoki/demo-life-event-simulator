"""DI 設定: Repository のファクトリ

FastAPI の Depends で注入する。テスト時は dependency_overrides で差し替える。
"""

import os
from functools import lru_cache
from pathlib import Path

from src.data_paths import DEFAULT_DB_PATH
from src.db.client_repository import ClientRepository
from src.db.sqlite_repository import SqliteClientRepository


@lru_cache(maxsize=1)
def _get_repository() -> SqliteClientRepository:
    """アプリケーション全体で1つの Repository インスタンスを共有する。"""
    db_path = os.environ.get("LES_DB_PATH", str(DEFAULT_DB_PATH))
    if db_path:
        # SQLite は親フォルダが無いと開けない。data/ は git に入らないので clone 直後は無い。
        # LES_DB_PATH を明示したときも同じ扱いにする。
        # 空文字は sqlite:/// （メモリ DB）になりファイルを作らないので、フォルダも作らない。
        # URL は Path を通さず文字列から組み立てる（Path("") は "." になり URL が変わるため）
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteClientRepository(db_url=f"sqlite:///{db_path}")


def get_client_repository() -> ClientRepository:
    """FastAPI Depends で注入する。テスト時は dependency_overrides で差し替える。"""
    return _get_repository()
