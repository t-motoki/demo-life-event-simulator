"""SqliteClientRepository のテスト

:memory: SQLite を使い、ファイル I/O に依存しない。
テストごとに新しいインスタンスを作成して独立性を保証する。
"""

import time
from datetime import datetime

import pytest

from src.db.sqlite_repository import SqliteClientRepository


@pytest.fixture
def repository() -> SqliteClientRepository:
    return SqliteClientRepository(db_url="sqlite:///:memory:")


@pytest.fixture
def sample_scenario() -> dict:
    """minimal_request と同等の dict"""
    return {
        "client": {
            "age": 35,
            "annual_income": 5_000_000,
            "income_model": "flat",
            "raise_rate": 0.0,
            "retirement_age": 65,
            "post_retirement_income": 0,
            "pension_start_age": 65,
            "pension_annual": 0,
        },
        "spouse": None,
        "savings_initial": 3_000_000,
        "end_age": 80,
        "start_year": 2025,
        "monthly_expenses": {
            "living": 200_000,
            "insurance": 20_000,
            "other": 10_000,
        },
        "events": [],
    }


class TestCreate:
    """クライアントの新規作成が正しく動作すること"""

    def test_create_when_valid_name_and_scenario_then_returns_record(
        self, repository, sample_scenario
    ):
        record = repository.create("田中太郎", sample_scenario)

        assert record.id is not None
        assert isinstance(record.id, int)
        assert record.name == "田中太郎"
        assert record.scenario == sample_scenario

    def test_create_when_valid_then_sets_timestamps(
        self, repository, sample_scenario
    ):
        record = repository.create("田中太郎", sample_scenario)

        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)
        assert record.created_at == record.updated_at

    def test_create_when_called_twice_then_ids_are_unique(
        self, repository, sample_scenario
    ):
        r1 = repository.create("田中太郎", sample_scenario)
        r2 = repository.create("田中太郎", sample_scenario)

        assert r1.id != r2.id

    def test_create_when_name_is_empty_then_raises_error(
        self, repository, sample_scenario
    ):
        with pytest.raises(ValueError):
            repository.create("", sample_scenario)

    def test_create_when_name_is_whitespace_only_then_raises_error(
        self, repository, sample_scenario
    ):
        with pytest.raises(ValueError):
            repository.create("   ", sample_scenario)


class TestListAll:
    """クライアント一覧の取得が正しく動作すること"""

    def test_list_all_when_empty_then_returns_empty_list(self, repository):
        result = repository.list_all()
        assert result == []

    def test_list_all_when_two_clients_then_returns_two_summaries(
        self, repository, sample_scenario
    ):
        repository.create("田中太郎", sample_scenario)
        repository.create("鈴木花子", sample_scenario)

        result = repository.list_all()

        assert len(result) == 2
        for summary in result:
            assert hasattr(summary, "id")
            assert hasattr(summary, "name")
            assert hasattr(summary, "updated_at")
            # scenario は含まれない
            assert not hasattr(summary, "scenario")

    def test_list_all_returns_ordered_by_updated_at_desc(
        self, repository, sample_scenario
    ):
        repository.create("最初", sample_scenario)
        time.sleep(0.02)
        repository.create("中間", sample_scenario)
        time.sleep(0.02)
        repository.create("最後", sample_scenario)

        result = repository.list_all()

        # 最近更新したものが先頭
        assert result[0].name == "最後"
        assert result[1].name == "中間"
        assert result[2].name == "最初"


class TestGet:
    """単体クライアントの取得が正しく動作すること"""

    def test_get_when_existing_id_then_returns_record_with_scenario(
        self, repository, sample_scenario
    ):
        created = repository.create("田中太郎", sample_scenario)
        record = repository.get(created.id)

        assert record is not None
        assert record.scenario == sample_scenario

    def test_get_when_nonexistent_id_then_returns_none(self, repository):
        result = repository.get(99999)
        assert result is None


class TestUpdate:
    """クライアントデータの更新が正しく動作すること"""

    def test_update_when_existing_id_then_name_and_scenario_are_updated(
        self, repository, sample_scenario
    ):
        created = repository.create("田中太郎", sample_scenario)

        new_scenario = {**sample_scenario, "end_age": 90}
        repository.update(created.id, "田中次郎", new_scenario)

        record = repository.get(created.id)
        assert record is not None
        assert record.name == "田中次郎"
        assert record.scenario == new_scenario

    def test_update_when_existing_id_then_updated_at_changes(
        self, repository, sample_scenario
    ):
        created = repository.create("田中太郎", sample_scenario)
        time.sleep(0.02)
        updated = repository.update(created.id, "田中太郎", sample_scenario)

        assert updated.updated_at > updated.created_at
        assert updated.created_at == created.created_at

    def test_update_when_nonexistent_id_then_raises_error(
        self, repository, sample_scenario
    ):
        with pytest.raises(ValueError):
            repository.update(99999, "誰か", sample_scenario)

    def test_update_when_name_is_empty_then_raises_error(
        self, repository, sample_scenario
    ):
        created = repository.create("田中太郎", sample_scenario)
        with pytest.raises(ValueError):
            repository.update(created.id, "", sample_scenario)


class TestDelete:
    """クライアントデータの削除が正しく動作すること"""

    def test_delete_when_existing_id_then_get_returns_none(
        self, repository, sample_scenario
    ):
        created = repository.create("田中太郎", sample_scenario)
        repository.delete(created.id)

        assert repository.get(created.id) is None

    def test_delete_when_existing_id_then_list_all_excludes_it(
        self, repository, sample_scenario
    ):
        r1 = repository.create("田中太郎", sample_scenario)
        repository.create("鈴木花子", sample_scenario)

        repository.delete(r1.id)
        result = repository.list_all()

        assert len(result) == 1
        assert result[0].name == "鈴木花子"

    def test_delete_when_nonexistent_id_then_raises_error(self, repository):
        with pytest.raises(ValueError):
            repository.delete(99999)
