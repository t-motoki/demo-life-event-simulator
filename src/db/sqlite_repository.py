"""SQLite による ClientRepository の実装

各メソッドで Session を開閉する（with 文）。
scenario は json.dumps / json.loads で dict <-> JSON 文字列を変換する。
"""

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.db.client_repository import ClientRecord, ClientRepository, ClientSummary
from src.db.models import Base, ClientModel


def _validate_name(name: str) -> str:
    """name のバリデーション。strip 済みの name を返す。"""
    stripped = name.strip()
    if not stripped:
        raise ValueError("name は空にできません")
    return stripped


def _to_record(model: ClientModel) -> ClientRecord:
    """SQLAlchemy モデルを ClientRecord データクラスに変換する"""
    return ClientRecord(
        id=model.id,
        name=model.name,
        scenario=json.loads(model.scenario),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_summary(model: ClientModel) -> ClientSummary:
    """SQLAlchemy モデルを ClientSummary データクラスに変換する"""
    return ClientSummary(
        id=model.id,
        name=model.name,
        updated_at=model.updated_at,
    )


class SqliteClientRepository(ClientRepository):

    def __init__(self, db_url: str = "sqlite:///clients.db") -> None:
        """SQLite に接続し、テーブルを自動作成する。

        テスト時は db_url="sqlite:///:memory:" を渡す。
        :memory: の場合は StaticPool を使い、スレッド間で同一接続を共有する。
        """
        if db_url == "sqlite:///:memory:":
            # :memory: はスレッド間で接続を共有しないと別テーブル空間になる
            self._engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self._engine = create_engine(db_url)
        Base.metadata.create_all(self._engine)

    def create(self, name: str, scenario: dict) -> ClientRecord:
        validated_name = _validate_name(name)
        now = datetime.now(timezone.utc)
        model = ClientModel(
            name=validated_name,
            scenario=json.dumps(scenario, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        with Session(self._engine) as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_record(model)

    def list_all(self) -> list[ClientSummary]:
        with Session(self._engine) as session:
            stmt = select(ClientModel).order_by(ClientModel.updated_at.desc())
            models = session.execute(stmt).scalars().all()
            return [_to_summary(m) for m in models]

    def get(self, client_id: int) -> ClientRecord | None:
        with Session(self._engine) as session:
            model = session.get(ClientModel, client_id)
            if model is None:
                return None
            return _to_record(model)

    def update(self, client_id: int, name: str, scenario: dict) -> ClientRecord:
        validated_name = _validate_name(name)
        with Session(self._engine) as session:
            model = session.get(ClientModel, client_id)
            if model is None:
                raise ValueError(f"クライアント ID {client_id} が見つかりません")
            model.name = validated_name
            model.scenario = json.dumps(scenario, ensure_ascii=False)
            model.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(model)
            return _to_record(model)

    def delete(self, client_id: int) -> None:
        with Session(self._engine) as session:
            model = session.get(ClientModel, client_id)
            if model is None:
                raise ValueError(f"クライアント ID {client_id} が見つかりません")
            session.delete(model)
            session.commit()
