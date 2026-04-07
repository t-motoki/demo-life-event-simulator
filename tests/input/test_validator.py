"""入力バリデーションのテスト"""

import pytest

from src.domain.models import (
    Client,
    HousingEvent,
    IncomeModel,
    MonthlyExpenses,
    Scenario,
)
from src.input.validator import validate


def _valid_scenario(**kwargs) -> Scenario:
    """バリデーション通過する基本シナリオを生成する"""
    defaults = dict(
        client=Client(
            age=35,
            annual_income=5_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        ),
        spouse=None,
        savings_initial=3_000_000,
        end_age=80,
        monthly_expenses=MonthlyExpenses(living=200_000, insurance=20_000, other=10_000),
        events=[],
        start_year=2025,
    )
    defaults.update(kwargs)
    return Scenario(**defaults)


class TestValidInput:
    def test_valid_scenario_passes(self):
        """正常な入力はエラーなし"""
        scenario = _valid_scenario()
        validate(scenario)  # 例外が発生しないこと


class TestClientAge:
    def test_age_zero_is_valid(self):
        """年齢0は有効"""
        client = Client(
            age=0,
            annual_income=0,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        )
        scenario = _valid_scenario(client=client, end_age=1)
        validate(scenario)

    def test_age_100_is_valid(self):
        """年齢100は有効"""
        client = Client(
            age=100,
            annual_income=0,
            income_model=IncomeModel.FLAT,
            retirement_age=100,
            post_retirement_income=0,
            pension_start_age=100,
            pension_annual=0,
        )
        scenario = _valid_scenario(client=client, end_age=101)
        validate(scenario)

    def test_negative_age_raises(self):
        """年齢が負数はエラー"""
        client = Client(
            age=-1,
            annual_income=0,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        )
        scenario = _valid_scenario(client=client)
        with pytest.raises(ValueError, match="年齢"):
            validate(scenario)

    def test_age_over_100_raises(self):
        """年齢が101以上はエラー"""
        client = Client(
            age=101,
            annual_income=0,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        )
        scenario = _valid_scenario(client=client)
        with pytest.raises(ValueError, match="年齢"):
            validate(scenario)


class TestEndAge:
    def test_end_age_equal_to_client_age_raises(self):
        """end_age == client.ageはエラー"""
        scenario = _valid_scenario(end_age=35)  # client.age=35と同じ
        with pytest.raises(ValueError, match="終了年齢"):
            validate(scenario)

    def test_end_age_less_than_client_age_raises(self):
        """end_age < client.ageはエラー"""
        scenario = _valid_scenario(end_age=30)  # client.age=35より小さい
        with pytest.raises(ValueError, match="終了年齢"):
            validate(scenario)

    def test_end_age_greater_than_client_age_passes(self):
        """end_age > client.ageは有効"""
        scenario = _valid_scenario(end_age=36)
        validate(scenario)


class TestSavingsInitial:
    def test_negative_savings_raises(self):
        """貯蓄初期残高が負数はエラー"""
        scenario = _valid_scenario(savings_initial=-1)
        with pytest.raises(ValueError, match="貯蓄"):
            validate(scenario)

    def test_zero_savings_passes(self):
        """貯蓄初期残高が0は有効"""
        scenario = _valid_scenario(savings_initial=0)
        validate(scenario)


class TestHousingEventValidation:
    def test_down_payment_equal_to_price_raises(self):
        """頭金 == 物件価格はエラー"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=30_000_000,
            loan_years=35,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        with pytest.raises(ValueError, match="頭金"):
            validate(scenario)

    def test_down_payment_greater_than_price_raises(self):
        """頭金 > 物件価格はエラー"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=35_000_000,
            loan_years=35,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        with pytest.raises(ValueError, match="頭金"):
            validate(scenario)

    def test_down_payment_less_than_price_passes(self):
        """頭金 < 物件価格は有効"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=35,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        validate(scenario)

    def test_negative_interest_rate_raises(self):
        """金利が負数はエラー"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=35,
            interest_rate=-0.01,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        with pytest.raises(ValueError, match="金利"):
            validate(scenario)

    def test_interest_rate_over_1_raises(self):
        """金利が1超はエラー"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=35,
            interest_rate=1.01,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        with pytest.raises(ValueError, match="金利"):
            validate(scenario)

    def test_loan_years_zero_raises(self):
        """借入期間が0年はエラー"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=0,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        with pytest.raises(ValueError, match="借入期間"):
            validate(scenario)

    def test_loan_years_over_50_raises(self):
        """借入期間が51年以上はエラー"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=51,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        with pytest.raises(ValueError, match="借入期間"):
            validate(scenario)

    def test_loan_years_50_passes(self):
        """借入期間50年は有効"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=50,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _valid_scenario(events=[housing])
        validate(scenario)


