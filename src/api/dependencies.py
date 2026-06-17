"""DI 設定: Repository のファクトリ

FastAPI の Depends で注入する。テスト時は dependency_overrides で差し替える。
"""

import os
from functools import lru_cache

from src.db.client_repository import ClientRepository
from src.db.sqlite_repository import SqliteClientRepository


@lru_cache(maxsize=1)
def _get_repository() -> SqliteClientRepository:
    """アプリケーション全体で1つの Repository インスタンスを共有する。"""
    db_path = os.environ.get("LES_DB_PATH", "clients.db")
    return SqliteClientRepository(db_url=f"sqlite:///{db_path}")


def get_client_repository() -> ClientRepository:
    """FastAPI Depends で注入する。テスト時は dependency_overrides で差し替える。"""
    return _get_repository()
