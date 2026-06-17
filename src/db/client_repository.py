"""クライアントデータの Repository 抽象クラスとデータクラス

SQLAlchemy モデルへの依存を Repository の外に漏らさないための境界オブジェクト。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClientRecord:
    """単体クライアントの完全データ（scenario 含む）"""

    id: int
    name: str
    scenario: dict  # JSON をデシリアライズ済み
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClientSummary:
    """一覧表示用の軽量データ（scenario を含まない）"""

    id: int
    name: str
    updated_at: datetime


class ClientRepository(ABC):

    @abstractmethod
    def create(self, name: str, scenario: dict) -> ClientRecord:
        """クライアントを新規作成する。

        name が空文字または空白のみの場合は ValueError を送出する。
        """

    @abstractmethod
    def list_all(self) -> list[ClientSummary]:
        """全クライアントの一覧を updated_at 降順で返す。"""

    @abstractmethod
    def get(self, client_id: int) -> ClientRecord | None:
        """指定 ID のクライアントを返す。存在しなければ None。"""

    @abstractmethod
    def update(self, client_id: int, name: str, scenario: dict) -> ClientRecord:
        """指定 ID のクライアントを更新する。

        存在しない ID の場合は ValueError を送出する。
        name が空文字または空白のみの場合は ValueError を送出する。
        """

    @abstractmethod
    def delete(self, client_id: int) -> None:
        """指定 ID のクライアントを削除する。

        存在しない ID の場合は ValueError を送出する。
        """
