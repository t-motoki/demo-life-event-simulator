"""住宅ローン・住宅ローン控除計算モジュール"""

from dataclasses import dataclass


# 住宅ローン控除の適用期間（年数）
LOAN_DEDUCTION_YEARS = 13

# 住宅ローン控除率
LOAN_DEDUCTION_RATE = 0.007  # 0.7%


@dataclass
class LoanSchedule:
    """住宅ローン返済スケジュール"""
    loan_amount: int
    annual_rate: float
    loan_years: int
    start_year: int  # 返済開始年（住宅購入年）

    def monthly_payment(self) -> float:
        """元利均等返済の月返済額を計算する"""
        principal = self.loan_amount
        monthly_rate = self.annual_rate / 12
        n_payments = self.loan_years * 12

        if monthly_rate == 0:
            return principal / n_payments

        payment = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-n_payments))
        return payment

    def year_end_balance(self, year: int) -> int:
        """指定年の年末ローン残高を返す（円・切り捨て）

        Args:
            year: 西暦年

        Returns:
            年末時点のローン残高。返済開始前や完済後は0。
        """
        elapsed_years = year - self.start_year + 1
        if elapsed_years <= 0:
            # 返済開始前
            return 0
        elif elapsed_years > self.loan_years:
            # 完済済み
            return 0
        else:
            n_paid = elapsed_years * 12

        principal = self.loan_amount
        monthly_rate = self.annual_rate / 12
        n_total = self.loan_years * 12

        if monthly_rate == 0:
            remaining_payments = n_total - n_paid
            balance = principal * remaining_payments / n_total
        else:
            monthly_pmt = self.monthly_payment()
            balance = principal * (1 + monthly_rate) ** n_paid - monthly_pmt * ((1 + monthly_rate) ** n_paid - 1) / monthly_rate

        return max(0, int(balance))

    def annual_payment(self, year: int) -> int:
        """指定年の年間返済額を返す（円・切り捨て）

        Args:
            year: 西暦年

        Returns:
            年間返済額。返済期間外は0。
        """
        elapsed_years = year - self.start_year + 1
        if elapsed_years <= 0 or elapsed_years > self.loan_years:
            return 0

        return int(self.monthly_payment() * 12)

    def deduction_amount(self, year: int) -> int:
        """指定年の住宅ローン控除額を返す（円・切り捨て）

        返済開始年から13年間のみ適用。
        控除額 = 年末ローン残高 × 0.7%

        Args:
            year: 西暦年

        Returns:
            控除額（円）。適用外の年は0。
        """
        elapsed_years = year - self.start_year + 1
        if elapsed_years <= 0 or elapsed_years > LOAN_DEDUCTION_YEARS:
            return 0

        balance = self.year_end_balance(year)
        deduction = int(balance * LOAN_DEDUCTION_RATE)
        return deduction
