"""POST /simulate エンドポイントのアクセプタンステスト"""

import pytest

from src.domain.cashflow import simulate
from src.domain.models import (
    BirthEvent,
    CareEvent,
    Client,
    EducationEvent,
    HousingEvent,
    IncomeModel,
    MarriageEvent,
    MonthlyExpenses,
    OtherExpenseEvent,
    Scenario,
    SchoolType,
)
from src.input.validator import validate


class TestSimulateNormal:
    def test_minimal_scenario_returns_200(self, client, minimal_request):
        """AC1: 最小シナリオで HTTP 200 が返る"""
        response = client.post("/simulate", json=minimal_request)
        assert response.status_code == 200

    def test_minimal_scenario_matches_domain_result(self, client, minimal_request):
        """AC1: 最小シナリオのレスポンスがドメインロジックと同一である"""
        # ドメインを直接呼んで期待値を計算する
        scenario = Scenario(
            client=Client(
                age=35,
                annual_income=5_000_000,
                income_model=IncomeModel.FLAT,
                raise_rate=0.0,
                retirement_age=65,
                post_retirement_income=0,
                pension_start_age=65,
                pension_annual=0,
            ),
            spouse=None,
            savings_initial=3_000_000,
            end_age=80,
            start_year=2025,
            monthly_expenses=MonthlyExpenses(
                living=200_000,
                insurance=20_000,
                other=10_000,
            ),
            events=[],
        )
        expected_rows = simulate(scenario)

        response = client.post("/simulate", json=minimal_request)
        assert response.status_code == 200
        actual = response.json()

        assert len(actual) == len(expected_rows)
        for actual_row, expected_row in zip(actual, expected_rows):
            assert actual_row["year"] == expected_row.year
            assert actual_row["age_client"] == expected_row.age_client
            assert actual_row["age_spouse"] == expected_row.age_spouse
            assert actual_row["income_total"] == expected_row.income_total
            assert actual_row["expense_total"] == expected_row.expense_total
            assert actual_row["loan_deduction"] == expected_row.loan_deduction
            assert actual_row["net"] == expected_row.net
            assert actual_row["savings"] == expected_row.savings
            assert actual_row["events_label"] == expected_row.events_label

    def test_all_event_types_return_200(self, client, minimal_request):
        """AC1: 全イベント種別を含むシナリオで HTTP 200 が返る"""
        request = dict(minimal_request)
        # housing: ローン完済年齢チェックを通過させるため loan_years=20（完済55歳 < 65歳）
        request["events"] = [
            {"type": "marriage", "year": 2025, "cost": 3_000_000},
            {
                "type": "birth",
                "year": 2026,
                "child_count": 1,
                "client_maternity_rate": 0.6,
                "client_maternity_years": 1,
                "spouse_maternity_rate": 1.0,
                "spouse_maternity_years": 0,
            },
            {
                "type": "housing",
                "year": 2027,
                "price": 30_000_000,
                "down_payment": 5_000_000,
                "loan_years": 20,
                "interest_rate": 0.015,
                "use_tax_deduction": True,
            },
            {
                "type": "education",
                "year": 2026,
                "child_birth_year": 2026,
                "kindergarten": "public",
                "elementary": "public",
                "junior_high": "public",
                "high_school": "public",
                "university": "private",
            },
            {
                "type": "care",
                "year": 2030,
                "duration_years": 3,
                "monthly_cost": 100_000,
            },
            {
                "type": "other_expense",
                "year": 2035,
                "amount": 500_000,
                "name": "車買い替え",
            },
        ]
        response = client.post("/simulate", json=request)
        assert response.status_code == 200
        data = response.json()
        # 年次データが配列として返ってくることを確認する
        assert isinstance(data, list)
        assert len(data) > 0
        # 各行に必須フィールドが揃っていることを確認する
        for row in data:
            assert "year" in row
            assert "age_client" in row
            assert "income_total" in row
            assert "savings" in row


class TestSimulateValidation:
    """AC2: validator.py のエラー条件が HTTP 422 になることを確認する"""

    @pytest.mark.parametrize("age,desc", [
        (-1, "本人年齢が負数"),
        (101, "本人年齢が101以上"),
    ])
    def test_invalid_client_age_returns_422(self, client, minimal_request, age, desc):
        """本人年齢が範囲外なら 422"""
        request = dict(minimal_request)
        request["client"] = dict(minimal_request["client"])
        request["client"]["age"] = age
        response = client.post("/simulate", json=request)
        assert response.status_code == 422, f"{desc} のとき 422 を期待"

    def test_negative_savings_returns_422(self, client, minimal_request):
        """貯蓄初期残高が負数なら 422"""
        request = dict(minimal_request)
        request["savings_initial"] = -1
        response = client.post("/simulate", json=request)
        assert response.status_code == 422

    def test_end_age_le_client_age_returns_422(self, client, minimal_request):
        """end_age <= client.age なら 422"""
        request = dict(minimal_request)
        request["end_age"] = 35  # client.age=35 と同じ
        response = client.post("/simulate", json=request)
        assert response.status_code == 422

    def test_spouse_age_out_of_range_returns_422(self, client, minimal_request):
        """配偶者年齢が範囲外なら 422"""
        request = dict(minimal_request)
        request["spouse"] = {
            "age": 101,
            "annual_income": 0,
            "income_model": "flat",
            "raise_rate": 0.0,
            "retirement_age": 65,
            "post_retirement_income": 0,
            "pension_start_age": 65,
            "pension_annual": 0,
        }
        response = client.post("/simulate", json=request)
        assert response.status_code == 422

    @pytest.mark.parametrize("down_payment,price,desc", [
        (30_000_000, 30_000_000, "頭金==物件価格"),
        (35_000_000, 30_000_000, "頭金>物件価格"),
    ])
    def test_housing_down_payment_ge_price_returns_422(
        self, client, minimal_request, down_payment, price, desc
    ):
        """頭金 >= 物件価格なら 422"""
        request = dict(minimal_request)
        request["events"] = [{
            "type": "housing",
            "year": 2025,
            "price": price,
            "down_payment": down_payment,
            "loan_years": 20,
            "interest_rate": 0.015,
            "use_tax_deduction": True,
        }]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422, f"{desc} のとき 422 を期待"

    @pytest.mark.parametrize("interest_rate,desc", [
        (-0.01, "金利が負数"),
        (1.01, "金利が1超"),
    ])
    def test_housing_interest_rate_out_of_range_returns_422(
        self, client, minimal_request, interest_rate, desc
    ):
        """金利が範囲外なら 422"""
        request = dict(minimal_request)
        request["events"] = [{
            "type": "housing",
            "year": 2025,
            "price": 30_000_000,
            "down_payment": 5_000_000,
            "loan_years": 20,
            "interest_rate": interest_rate,
            "use_tax_deduction": True,
        }]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422, f"{desc} のとき 422 を期待"

    @pytest.mark.parametrize("loan_years,desc", [
        (0, "ローン年数が0"),
        (51, "ローン年数が51以上"),
    ])
    def test_housing_loan_years_out_of_range_returns_422(
        self, client, minimal_request, loan_years, desc
    ):
        """ローン年数が範囲外なら 422"""
        request = dict(minimal_request)
        request["events"] = [{
            "type": "housing",
            "year": 2025,
            "price": 30_000_000,
            "down_payment": 5_000_000,
            "loan_years": loan_years,
            "interest_rate": 0.015,
            "use_tax_deduction": True,
        }]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422, f"{desc} のとき 422 を期待"

    def test_housing_loan_exceeds_retirement_returns_422(self, client, minimal_request):
        """ローン完済年齢が定年以上なら 422（35歳 + 35年ローン = 70歳 >= retirement_age=65）"""
        request = dict(minimal_request)
        request["events"] = [{
            "type": "housing",
            "year": 2025,
            "price": 30_000_000,
            "down_payment": 5_000_000,
            "loan_years": 35,
            "interest_rate": 0.015,
            "use_tax_deduction": True,
        }]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422

    @pytest.mark.parametrize("rate,field,desc", [
        (-0.1, "client_maternity_rate", "本人育休収入率が負数"),
        (1.1, "client_maternity_rate", "本人育休収入率が1超"),
        (-0.1, "spouse_maternity_rate", "配偶者育休収入率が負数"),
        (1.5, "spouse_maternity_rate", "配偶者育休収入率が1超"),
    ])
    def test_birth_maternity_rate_out_of_range_returns_422(
        self, client, minimal_request, rate, field, desc
    ):
        """育休収入率が範囲外なら 422"""
        request = dict(minimal_request)
        request["events"] = [{
            "type": "birth",
            "year": 2026,
            "child_count": 1,
            "client_maternity_rate": 1.0,
            "client_maternity_years": 0,
            "spouse_maternity_rate": 1.0,
            "spouse_maternity_years": 0,
            field: rate,
        }]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422, f"{desc} のとき 422 を期待"

    @pytest.mark.parametrize("years,field,desc", [
        (-1, "client_maternity_years", "本人育休期間が負数"),
        (-1, "spouse_maternity_years", "配偶者育休期間が負数"),
    ])
    def test_birth_maternity_years_negative_returns_422(
        self, client, minimal_request, years, field, desc
    ):
        """育休期間が負数なら 422"""
        request = dict(minimal_request)
        request["events"] = [{
            "type": "birth",
            "year": 2026,
            "child_count": 1,
            "client_maternity_rate": 1.0,
            "client_maternity_years": 0,
            "spouse_maternity_rate": 1.0,
            "spouse_maternity_years": 0,
            field: years,
        }]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422, f"{desc} のとき 422 を期待"


class TestSimulateUnknownEventType:
    def test_unknown_event_type_returns_422(self, client, minimal_request):
        """AC3: events に未知の type が来たら 422"""
        request = dict(minimal_request)
        request["events"] = [{"type": "unknown_type", "year": 2025}]
        response = client.post("/simulate", json=request)
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        """リクエストボディに必須フィールドが欠落していたら 422"""
        response = client.post("/simulate", json={"client": {"age": 35}})
        assert response.status_code == 422

    def test_empty_body_returns_422(self, client):
        """リクエストボディが空なら 422"""
        response = client.post("/simulate", json={})
        assert response.status_code == 422


class TestSimulateCORS:
    def test_cors_header_returned_for_allowed_origin(self, client, minimal_request):
        """AC6: localhost:3000 からのリクエストに CORS ヘッダーが付く"""
        response = client.post(
            "/simulate",
            json=minimal_request,
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    def test_cors_preflight_returns_200(self, client):
        """AC6: OPTIONS プリフライトリクエストに応答する"""
        response = client.options(
            "/simulate",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200
