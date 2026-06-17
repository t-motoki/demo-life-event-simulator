"""API レイヤー: /clients エンドポイントのテスト

:memory: SQLite の実 Repository を DI で注入する（mock しない）。
"""

import time

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_client_repository
from src.api.main import app
from src.db.sqlite_repository import SqliteClientRepository


@pytest.fixture
def repo() -> SqliteClientRepository:
    """テストごとに :memory: SQLite の Repository を生成"""
    return SqliteClientRepository(db_url="sqlite:///:memory:")


@pytest.fixture
def client(repo) -> TestClient:
    """DI で :memory: Repository を注入した TestClient"""
    app.dependency_overrides[get_client_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestPostClients:
    """POST /clients でクライアントが新規作成できること"""

    def test_post_clients_when_valid_then_returns_201(
        self, client, minimal_request
    ):
        response = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "田中太郎"
        assert "created_at" in data
        assert "updated_at" in data

    def test_post_clients_when_valid_then_scenario_is_persisted(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client_id = post_resp.json()["id"]

        get_resp = client.get(f"/clients/{client_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["scenario"] == minimal_request

    def test_post_clients_when_name_missing_then_returns_422(
        self, client, minimal_request
    ):
        response = client.post(
            "/clients",
            json={"scenario": minimal_request},
        )
        assert response.status_code == 422

    def test_post_clients_when_name_empty_then_returns_422(
        self, client, minimal_request
    ):
        response = client.post(
            "/clients",
            json={"name": "", "scenario": minimal_request},
        )
        assert response.status_code == 422

    def test_post_clients_when_scenario_missing_then_returns_422(
        self, client, minimal_request
    ):
        response = client.post(
            "/clients",
            json={"name": "田中太郎"},
        )
        assert response.status_code == 422


class TestGetClientsList:
    """GET /clients でクライアント一覧が取得できること"""

    def test_get_clients_when_empty_then_returns_200_with_empty_list(
        self, client
    ):
        response = client.get("/clients")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_clients_when_two_exist_then_returns_summaries(
        self, client, minimal_request
    ):
        client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client.post(
            "/clients",
            json={"name": "鈴木花子", "scenario": minimal_request},
        )

        response = client.get("/clients")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "updated_at" in item
            # scenario は含まれない
            assert "scenario" not in item


class TestGetClientDetail:
    """GET /clients/{id} で単体クライアントが取得できること"""

    def test_get_client_when_existing_id_then_returns_200_with_scenario(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client_id = post_resp.json()["id"]

        response = client.get(f"/clients/{client_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == client_id
        assert data["name"] == "田中太郎"
        assert "scenario" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_client_when_nonexistent_id_then_returns_404(self, client):
        response = client.get("/clients/99999")
        assert response.status_code == 404
        assert "detail" in response.json()


class TestPutClients:
    """PUT /clients/{id} でクライアントデータが更新できること"""

    def test_put_client_when_existing_id_then_returns_200(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client_id = post_resp.json()["id"]

        new_scenario = {**minimal_request, "end_age": 90}
        response = client.put(
            f"/clients/{client_id}",
            json={"name": "田中次郎", "scenario": new_scenario},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "田中次郎"
        assert data["scenario"] == new_scenario

    def test_put_client_when_existing_id_then_updated_at_changes(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        data_before = post_resp.json()
        client_id = data_before["id"]

        time.sleep(0.02)

        response = client.put(
            f"/clients/{client_id}",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        data_after = response.json()

        assert data_after["updated_at"] > data_before["updated_at"]

    def test_put_client_when_nonexistent_id_then_returns_404(
        self, client, minimal_request
    ):
        response = client.put(
            "/clients/99999",
            json={"name": "誰か", "scenario": minimal_request},
        )
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_put_client_when_name_empty_then_returns_422(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client_id = post_resp.json()["id"]

        response = client.put(
            f"/clients/{client_id}",
            json={"name": "", "scenario": minimal_request},
        )
        assert response.status_code == 422


class TestDeleteClients:
    """DELETE /clients/{id} でクライアントデータが削除できること"""

    def test_delete_client_when_existing_id_then_returns_204(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client_id = post_resp.json()["id"]

        response = client.delete(f"/clients/{client_id}")
        assert response.status_code == 204

    def test_delete_client_when_existing_id_then_get_returns_404(
        self, client, minimal_request
    ):
        post_resp = client.post(
            "/clients",
            json={"name": "田中太郎", "scenario": minimal_request},
        )
        client_id = post_resp.json()["id"]

        client.delete(f"/clients/{client_id}")
        response = client.get(f"/clients/{client_id}")
        assert response.status_code == 404

    def test_delete_client_when_nonexistent_id_then_returns_404(self, client):
        response = client.delete("/clients/99999")
        assert response.status_code == 404
        assert "detail" in response.json()


class TestClientsCORS:
    """/clients エンドポイントに CORS ヘッダーが正しく付くこと"""

    def test_cors_header_on_get_clients(self, client):
        response = client.get(
            "/clients",
            headers={"Origin": "http://localhost:3000"},
        )
        assert "access-control-allow-origin" in response.headers
