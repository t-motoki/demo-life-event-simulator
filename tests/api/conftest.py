"""API テスト共通フィクスチャ"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def minimal_request() -> dict:
    """バリデーション通過・イベントなしの最小シナリオ JSON

    tests/input/test_validator.py の _valid_scenario() と同じ値を JSON 形式で定義する。
    テスト層の独立性を優先して重複を許容する。
    """
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
