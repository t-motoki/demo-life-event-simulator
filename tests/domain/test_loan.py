"""住宅ローン・住宅ローン控除計算のテスト"""

import pytest

from src.domain.loan import LOAN_DEDUCTION_YEARS, LoanSchedule


class TestMonthlyPayment:
    def test_zero_interest_rate(self):
        """金利0%のとき月返済額は元本/期間"""
        schedule = LoanSchedule(
            loan_amount=12_000_000,
            annual_rate=0.0,
            loan_years=10,
            start_year=2025,
        )
        expected = 12_000_000 / (10 * 12)
        assert schedule.monthly_payment() == pytest.approx(expected, rel=1e-6)

    def test_positive_interest_rate(self):
        """金利あり（1.5%）のとき月返済額が元本/期間より大きい"""
        schedule = LoanSchedule(
            loan_amount=40_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        # 元利均等返済の公式: P * r / (1 - (1+r)^-n)
        P = 40_000_000
        r = 0.015 / 12
        n = 35 * 12
        expected = P * r / (1 - (1 + r) ** (-n))
        assert schedule.monthly_payment() == pytest.approx(expected, rel=1e-6)

    def test_monthly_payment_positive(self):
        """月返済額は正の値"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.02,
            loan_years=30,
            start_year=2025,
        )
        assert schedule.monthly_payment() > 0


class TestYearEndBalance:
    def test_balance_decreases_over_time(self):
        """残高は年を経るごとに減少する"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        balance_year1 = schedule.year_end_balance(2025)
        balance_year5 = schedule.year_end_balance(2029)
        assert balance_year1 > balance_year5

    def test_balance_zero_after_loan_end(self):
        """返済期間終了後の残高は0"""
        schedule = LoanSchedule(
            loan_amount=10_000_000,
            annual_rate=0.01,
            loan_years=10,
            start_year=2025,
        )
        assert schedule.year_end_balance(2035) == 0
        assert schedule.year_end_balance(2036) == 0

    def test_balance_zero_before_start(self):
        """返済開始前は残高0"""
        schedule = LoanSchedule(
            loan_amount=10_000_000,
            annual_rate=0.01,
            loan_years=10,
            start_year=2025,
        )
        assert schedule.year_end_balance(2024) == 0

    def test_balance_zero_interest_rate(self):
        """金利0%のとき年末残高は元本から返済分を引いた値"""
        schedule = LoanSchedule(
            loan_amount=12_000_000,
            annual_rate=0.0,
            loan_years=10,
            start_year=2025,
        )
        # 1年後: 元本 - 1年分の返済
        annual_payment = 12_000_000 / 10
        expected = 12_000_000 - annual_payment
        assert schedule.year_end_balance(2025) == pytest.approx(expected, rel=1e-4)


class TestDeductionAmount:
    def test_deduction_within_13_years(self):
        """返済13年目まで控除額が発生する"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        deduction_year13 = schedule.deduction_amount(2025 + 13 - 1)  # 13年目
        assert deduction_year13 > 0

    def test_deduction_zero_at_year_14(self):
        """14年目以降は控除額が0"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        deduction_year14 = schedule.deduction_amount(2025 + 14 - 1)  # 14年目
        assert deduction_year14 == 0

    def test_deduction_zero_before_start(self):
        """返済開始前は控除額が0"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        assert schedule.deduction_amount(2024) == 0

    def test_deduction_rate_is_07_percent(self):
        """金利0%のとき控除額は残高 × 0.7%（整数切り捨て）"""
        # 金利0%だとバランス計算が単純になる
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.0,
            loan_years=30,
            start_year=2025,
        )
        balance = schedule.year_end_balance(2025)
        expected_deduction = int(balance * 0.007)
        assert schedule.deduction_amount(2025) == expected_deduction

    def test_deduction_decreases_over_years(self):
        """控除額は残高減少に伴い年々減少する"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        deduction_year1 = schedule.deduction_amount(2025)
        deduction_year5 = schedule.deduction_amount(2029)
        assert deduction_year1 > deduction_year5

    def test_deduction_years_constant(self):
        """控除期間定数が13年であることを確認"""
        assert LOAN_DEDUCTION_YEARS == 13


class TestAnnualPayment:
    def test_annual_payment_during_loan(self):
        """返済期間中の年間返済額は正の値"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        assert schedule.annual_payment(2025) > 0
        assert schedule.annual_payment(2059) > 0  # 最終年

    def test_annual_payment_after_loan(self):
        """返済期間終了後は0"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        assert schedule.annual_payment(2060) == 0

    def test_annual_payment_before_start(self):
        """返済開始前は0"""
        schedule = LoanSchedule(
            loan_amount=30_000_000,
            annual_rate=0.015,
            loan_years=35,
            start_year=2025,
        )
        assert schedule.annual_payment(2024) == 0
