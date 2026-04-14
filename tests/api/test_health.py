"""GET /health エンドポイントのテスト"""


class TestHealth:
    def test_returns_200(self, client):
        """AC4: GET /health が HTTP 200 を返す"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_status_ok(self, client):
        """AC4: GET /health のボディが {"status": "ok"} である"""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}
