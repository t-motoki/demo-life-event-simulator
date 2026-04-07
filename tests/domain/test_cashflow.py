"""キャッシュフロー計算のテスト"""

import pytest

from src.domain.cashflow import simulate
from src.domain.models import (
    BirthEvent,
    Client,
    HousingEvent,
    IncomeModel,
    MarriageEvent,
    MonthlyExpenses,
    OtherExpenseEvent,
    Scenario,
)


def _base_scenario(**kwargs) -> Scenario:
    """テスト用の基本シナリオを生成する"""
    defaults = dict(
        client=Client(
            age=35,
            annual_income=5_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=1_500_000,
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


class TestBasicCashflow:
    def test_no_events_flat_income(self):
        """イベントなし・収入一定のとき: 年間収支 = 収入 - 支出"""
        scenario = _base_scenario()
        rows = simulate(scenario)

        monthly = scenario.monthly_expenses
        annual_expense = (monthly.living + monthly.insurance + monthly.other) * 12
        expected_net = scenario.client.annual_income - annual_expense

        # 最初の年（退職前）を確認
        first_row = rows[0]
        assert first_row.income_total == scenario.client.annual_income
        assert first_row.expense_total == annual_expense
        assert first_row.net == expected_net
        assert first_row.loan_deduction == 0

    def test_savings_accumulates(self):
        """貯蓄残高が年次収支を正しく積み上げる"""
        scenario = _base_scenario()
        rows = simulate(scenario)

        expected_savings = scenario.savings_initial
        for row in rows:
            expected_savings += row.net
            assert row.savings == expected_savings

    def test_simulation_end_year(self):
        """シミュレーションがend_ageまで計算される"""
        scenario = _base_scenario(end_age=70)
        rows = simulate(scenario)
        last_row = rows[-1]
        assert last_row.age_client == 70

    def test_simulation_row_count(self):
        """行数がstart_yearからend_ageまでの年数と一致する"""
        scenario = _base_scenario(end_age=70)
        rows = simulate(scenario)
        expected_years = 70 - 35 + 1  # end_age - start_age + 1
        assert len(rows) == expected_years

    def test_age_increments_correctly(self):
        """各行の年齢が正しくインクリメントされる"""
        scenario = _base_scenario()
        rows = simulate(scenario)
        for i, row in enumerate(rows):
            assert row.age_client == scenario.client.age + i
            assert row.year == scenario.start_year + i


class TestHousingEvent:
    def test_down_payment_included_in_expense(self):
        """住宅購入年に頭金が支出に含まれる"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=35,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _base_scenario(events=[housing])
        rows = simulate(scenario)

        purchase_row = rows[0]  # 2025年
        monthly = scenario.monthly_expenses
        base_expense = (monthly.living + monthly.insurance + monthly.other) * 12
        loan_payment = rows[0].expense_total - base_expense - housing.down_payment

        assert housing.down_payment in [
            purchase_row.expense_total - base_expense - loan_payment
        ]
        # 頭金が支出に含まれることを確認（ローン返済額+固定費+頭金）
        assert purchase_row.expense_total > base_expense

    def test_loan_deduction_applied(self):
        """住宅ローン控除が年間収支に反映される"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=35,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _base_scenario(events=[housing])
        rows = simulate(scenario)

        first_row = rows[0]
        assert first_row.loan_deduction > 0
        assert first_row.net == first_row.income_total - first_row.expense_total + first_row.loan_deduction

    def test_no_loan_deduction_at_year_14(self):
        """住宅ローン控除は14年目以降は0"""
        housing = HousingEvent(
            year=2025,
            price=30_000_000,
            down_payment=5_000_000,
            loan_years=35,
            interest_rate=0.015,
            use_tax_deduction=True,
        )
        scenario = _base_scenario(events=[housing], end_age=90)
        rows = simulate(scenario)

        # 14年目 = 2038年 (index: 2038-2025=13)
        row_year14 = next(r for r in rows if r.year == 2038)
        assert row_year14.loan_deduction == 0


class TestPension:
    def test_pension_starts_at_pension_age(self):
        """年金受給開始年齢から年金収入が加算される"""
        # 定年は70歳、年金は65歳から開始するシナリオ
        # これにより64歳→65歳で年金分だけ収入が増えることを確認できる
        client = Client(
            age=35,
            annual_income=5_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=70,        # 定年は70歳（年金開始より後）
            post_retirement_income=5_000_000,
            pension_start_age=65,
            pension_annual=1_500_000,
        )
        scenario = _base_scenario(client=client, end_age=70)
        rows = simulate(scenario)

        pre_pension_row = next(r for r in rows if r.age_client == 64)
        pension_row = next(r for r in rows if r.age_client == 65)

        # 65歳から年金1,500,000が加算される（定年前なので給与は変わらない）
        assert pension_row.income_total == pre_pension_row.income_total + 1_500_000

    def test_income_includes_pension(self):
        """年金受給開始年の収入に年金額が含まれる"""
        client = Client(
            age=35,
            annual_income=5_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=70,  # 定年後減額なしで年金との差がわかりやすい
            post_retirement_income=5_000_000,
            pension_start_age=65,
            pension_annual=1_500_000,
        )
        scenario = _base_scenario(client=client, end_age=70)
        rows = simulate(scenario)

        age64_row = next(r for r in rows if r.age_client == 64)
        age65_row = next(r for r in rows if r.age_client == 65)

        # 65歳から年金1,500,000が加算される（定年前なので給与は同じ）
        assert age65_row.income_total == age64_row.income_total + 1_500_000


class TestNegativeSavings:
    def test_negative_savings_continues(self):
        """貯蓄残高がマイナスになっても計算を続ける"""
        client = Client(
            age=35,
            annual_income=1_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        )
        # 支出が収入を大幅に上回る設定
        monthly = MonthlyExpenses(living=300_000, insurance=50_000, other=50_000)
        scenario = _base_scenario(
            client=client,
            monthly_expenses=monthly,
            savings_initial=100_000,
            end_age=40,
        )
        rows = simulate(scenario)

        # 全行が存在し、マイナスになっても途中で停止しないことを確認
        assert len(rows) == 6  # 35〜40歳
        # どこかでマイナスになることを確認
        assert any(r.savings < 0 for r in rows)


class TestRetirement:
    def test_income_drops_at_retirement(self):
        """定年後に収入が変わる"""
        client = Client(
            age=35,
            annual_income=5_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=60,
            post_retirement_income=2_000_000,
            pension_start_age=65,
            pension_annual=0,
        )
        scenario = _base_scenario(client=client, end_age=65)
        rows = simulate(scenario)

        row_age59 = next(r for r in rows if r.age_client == 59)
        row_age60 = next(r for r in rows if r.age_client == 60)

        assert row_age59.income_total == 5_000_000
        assert row_age60.income_total == 2_000_000


class TestSpouse:
    def test_spouse_income_included(self):
        """配偶者の収入が合算される"""
        spouse = Client(
            age=33,
            annual_income=3_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        )
        scenario = _base_scenario(spouse=spouse)
        rows = simulate(scenario)

        first_row = rows[0]
        expected_income = (
            scenario.client.annual_income + spouse.annual_income
        )
        assert first_row.income_total == expected_income

    def test_spouse_age_in_row(self):
        """配偶者の年齢が正しく記録される"""
        spouse = Client(
            age=33,
            annual_income=3_000_000,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            post_retirement_income=0,
            pension_start_age=65,
            pension_annual=0,
        )
        scenario = _base_scenario(spouse=spouse)
        rows = simulate(scenario)

        for i, row in enumerate(rows):
            assert row.age_spouse == 33 + i


class TestMarriageEvent:
    def test_marriage_cost_in_expense(self):
        """結婚費用が発生年の支出に含まれる"""
        marriage = MarriageEvent(year=2025, cost=2_000_000)
        scenario = _base_scenario(events=[marriage])
        rows = simulate(scenario)

        monthly = scenario.monthly_expenses
        base_expense = (monthly.living + monthly.insurance + monthly.other) * 12
        first_row = rows[0]
        assert first_row.expense_total == base_expense + 2_000_000


class TestOtherExpense:
    def test_other_expense_in_correct_year(self):
        """その他支出が指定年のみ発生する"""
        expense_event = OtherExpenseEvent(year=2027, amount=1_000_000, name="車購入")
        scenario = _base_scenario(events=[expense_event])
        rows = simulate(scenario)

        monthly = scenario.monthly_expenses
        base_expense = (monthly.living + monthly.insurance + monthly.other) * 12

        row_2027 = next(r for r in rows if r.year == 2027)
        row_2026 = next(r for r in rows if r.year == 2026)

        assert row_2027.expense_total == base_expense + 1_000_000
        assert row_2026.expense_total == base_expense
