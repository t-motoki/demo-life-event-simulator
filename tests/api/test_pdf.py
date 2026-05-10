"""POST /download-pdf エンドポイントのテスト（AC-3-10・AC-3-11）

pdf_writer.generate_pdf をモックして PDF バイナリを返す。
WeasyPrint の実行はこのテストでは不要。
"""

import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def pdf_request_body(minimal_request) -> dict:
    """download-pdf エンドポイント用リクエスト（scenario + rows + fp_comment）"""
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
    return {"scenario": minimal_request, "rows": rows, "fp_comment": ""}


# モック用 PDF バイナリ（本物っぽいシグネチャ）
MOCK_PDF_BYTES = b"%PDF-1.4 mock pdf content"


class TestDownloadPdfEndpoint:
    def test_download_pdf_returns_200_with_pdf_content_type(
        self, client, pdf_request_body
    ):
        """有効なリクエストに HTTP 200 + application/pdf が返る（AC-3-1）"""
        with patch(
            "src.api.routes.pdf.generate_pdf",
            return_value=MOCK_PDF_BYTES,
        ):
            response = client.post("/download-pdf", json=pdf_request_body)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    def test_download_pdf_content_disposition_header(self, client, pdf_request_body):
        """Content-Disposition ヘッダーが cf_simulation_YYYYMMDD.pdf 形式（AC-3-11）"""
        with patch(
            "src.api.routes.pdf.generate_pdf",
            return_value=MOCK_PDF_BYTES,
        ):
            response = client.post("/download-pdf", json=pdf_request_body)

        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        # cf_simulation_YYYYMMDD.pdf のパターンを確認
        assert re.search(r"cf_simulation_\d{8}\.pdf", content_disp)

    def test_download_pdf_returns_422_on_invalid_body(self, client):
        """必須フィールド欠落のリクエストには HTTP 422 が返る（AC-3-10）"""
        response = client.post("/download-pdf", json={"scenario": {}, "rows": []})
        assert response.status_code == 422
        assert "detail" in response.json()
