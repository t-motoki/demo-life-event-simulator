"""POST /generate-comment エンドポイントのテスト（AC-2-6〜AC-2-8）

comment_generator.generate_comment を pytest-mock でパッチして
Claude API を呼び出さずにテストする。
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def comment_request_body(minimal_request) -> dict:
    """generate-comment エンドポイント用リクエスト（scenario + rows）"""
    rows = [
        {
            "year": 2026,
            "age_client": 35,
            "age_spouse": None,
            "income_total": 5_000_000,
            "expense_total": 4_560_000,
            "loan_deduction": 0,
            "net": 440_000,
            "savings": 3_440_000,
            "events_label": "",
        }
    ]
    return {"scenario": minimal_request, "rows": rows}


class TestGenerateCommentEndpoint:
    def test_generate_comment_returns_200_with_comment_field(
        self, client, comment_request_body
    ):
        """有効なリクエストに HTTP 200 + comment フィールドが返る（AC-2-6）"""
        with patch(
            "src.api.routes.comment.generate_comment",
            return_value="テストコメントです。",
        ):
            response = client.post("/generate-comment", json=comment_request_body)

        assert response.status_code == 200
        assert "comment" in response.json()

    def test_generate_comment_response_shape(self, client, comment_request_body):
        """レスポンスが {"comment": "<文字列>"} の形式（AC-2-7）"""
        with patch(
            "src.api.routes.comment.generate_comment",
            return_value="テストコメント",
        ):
            response = client.post("/generate-comment", json=comment_request_body)

        data = response.json()
        assert isinstance(data["comment"], str)

    def test_generate_comment_returns_503_on_api_failure(
        self, client, comment_request_body
    ):
        """Claude API 障害時に HTTP 503 が返る（AC-2-8）"""
        from src.output.comment_generator import CommentGenerationError

        with patch(
            "src.api.routes.comment.generate_comment",
            side_effect=CommentGenerationError("API接続エラー"),
        ):
            response = client.post("/generate-comment", json=comment_request_body)

        assert response.status_code == 503
        assert "detail" in response.json()
