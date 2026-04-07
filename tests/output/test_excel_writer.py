"""Excel出力のテスト"""

import openpyxl
import pytest

from src.domain.cashflow import simulate
from src.domain.models import (
    Client,
    HousingEvent,
    IncomeModel,
    MonthlyExpenses,
    Scenario,
)
from src.output.excel_writer import write_excel


def _base_scenario(**kwargs) -> Scenario:
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
        end_age=70,
        monthly_expenses=MonthlyExpenses(living=200_000, insurance=20_000, other=10_000),
        events=[],
        start_year=2025,
    )
    defaults.update(kwargs)
    return Scenario(**defaults)


def _read_input_sheet(tmp_path, scenario):
    """入力内容確認シートの内容を {ラベル: 値} で返す"""
    rows = simulate(scenario)
    path = write_excel(scenario, rows, output_dir=tmp_path)
    wb = openpyxl.load_workbook(path)
    ws = wb["入力内容確認"]
    return {row[0].value: row[1].value for row in ws.iter_rows() if row[0].value}


class TestInputSummaryHousingLoan:
    def test_payoff_age_present_in_sheet(self, tmp_path):
        """住宅ローンがある場合、完済年齢が入力確認シートに出力される"""
        housing = HousingEvent(
            year=2027,  # 借入時 client 年齢: 35 + (2027-2025) = 37歳
            price=40_000_000,
            down_payment=8_000_000,
            loan_years=25,  # 完済年齢: 37 + 25 = 62歳
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _base_scenario(events=[housing])
        data = _read_input_sheet(tmp_path, scenario)
        assert "完済年齢" in data
        assert data["完済年齢"] == 62

    def test_payoff_age_calculation(self, tmp_path):
        """完済年齢 = 借入時年齢 + loan_years で計算される"""
        # client 35歳 / start_year=2025 / housing year=2025 → 借入時35歳
        # loan_years=20 → 完済年齢=55
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=20,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _base_scenario(events=[housing])
        data = _read_input_sheet(tmp_path, scenario)
        assert data["完済年齢"] == 55

    def test_no_housing_event_no_payoff_age(self, tmp_path):
        """住宅イベントがない場合、完済年齢は出力されない"""
        scenario = _base_scenario()
        data = _read_input_sheet(tmp_path, scenario)
        assert "完済年齢" not in data
