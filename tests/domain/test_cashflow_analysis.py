"""キャッシュフロー分析モジュールのユニットテスト

TDD: 実装前にテストを書いて Red を確認する。
"""

import pytest

from src.domain.models import CashFlowRow


def _make_row(year: int, age_client: int, net: int, savings: int) -> CashFlowRow:
    """テスト用 CashFlowRow を簡易生成する"""
    return CashFlowRow(
        year=year,
        age_client=age_client,
        age_spouse=None,
        income_total=0,
        expense_total=0,
        loan_deduction=0,
        net=net,
        savings=savings,
        events_label="",
    )


class TestAnalyzeSavingsLow:
    def test_analyze_returns_savings_low_year(self):
        """最小 savings の年・年齢・金額が正しく返る"""
        from src.domain.cashflow_analysis import analyze

        rows = [
            _make_row(2026, 35, 100_000, 3_100_000),
            _make_row(2027, 36, -50_000, 3_050_000),
            _make_row(2028, 37, 200_000, 3_250_000),
        ]
        summary = analyze(rows)
        assert summary.savings_low.year == 2027
        assert summary.savings_low.age == 36
        assert summary.savings_low.amount == 3_050_000

    def test_analyze_savings_low_monotonic_increase(self):
        """全行 net >= 0 のとき最初の行が savings_low になる（単調増加シナリオ）"""
        from src.domain.cashflow_analysis import analyze

        rows = [
            _make_row(2026, 35, 100_000, 3_100_000),
            _make_row(2027, 36, 200_000, 3_300_000),
            _make_row(2028, 37, 300_000, 3_600_000),
        ]
        summary = analyze(rows)
        # 最初の行の savings が最小
        assert summary.savings_low.year == 2026
        assert summary.savings_low.age == 35
        assert summary.savings_low.amount == 3_100_000

    def test_analyze_raises_on_empty_rows(self):
        """rows が空のとき ValueError を送出する"""
        from src.domain.cashflow_analysis import analyze

        with pytest.raises(ValueError):
            analyze([])


class TestAnalyzeDeficitPeriods:
    def test_analyze_no_deficit_when_all_net_positive(self):
        """全行 net >= 0 のとき deficit_periods が空リストになる"""
        from src.domain.cashflow_analysis import analyze

        rows = [
            _make_row(2026, 35, 0, 3_000_000),
            _make_row(2027, 36, 100_000, 3_100_000),
        ]
        summary = analyze(rows)
        assert summary.deficit_periods == []

    def test_analyze_detects_single_year_deficit(self):
        """net < 0 が 1 年の場合 start_year == end_year"""
        from src.domain.cashflow_analysis import analyze

        rows = [
            _make_row(2026, 35, 100_000, 3_100_000),
            _make_row(2027, 36, -50_000, 3_050_000),
            _make_row(2028, 37, 200_000, 3_250_000),
        ]
        summary = analyze(rows)
        assert len(summary.deficit_periods) == 1
        assert summary.deficit_periods[0].start_year == 2027
        assert summary.deficit_periods[0].end_year == 2027

    def test_analyze_merges_consecutive_deficit_years(self):
        """連続する赤字年がひとつの DeficitPeriod にまとまる"""
        from src.domain.cashflow_analysis import analyze

        rows = [
            _make_row(2045, 54, 100_000, 3_000_000),
            _make_row(2046, 55, -100_000, 2_900_000),
            _make_row(2047, 56, -200_000, 2_700_000),
            _make_row(2048, 57, -150_000, 2_550_000),
            _make_row(2049, 58, 100_000, 2_650_000),
        ]
        summary = analyze(rows)
        assert len(summary.deficit_periods) == 1
        assert summary.deficit_periods[0].start_year == 2046
        assert summary.deficit_periods[0].end_year == 2048

    def test_analyze_detects_multiple_separate_deficit_periods(self):
        """離れた赤字年はそれぞれ別の DeficitPeriod になる"""
        from src.domain.cashflow_analysis import analyze

        rows = [
            _make_row(2026, 35, -10_000, 2_990_000),
            _make_row(2027, 36, 100_000, 3_090_000),
            _make_row(2028, 37, -20_000, 3_070_000),
        ]
        summary = analyze(rows)
        assert len(summary.deficit_periods) == 2
        assert summary.deficit_periods[0].start_year == 2026
        assert summary.deficit_periods[0].end_year == 2026
        assert summary.deficit_periods[1].start_year == 2028
        assert summary.deficit_periods[1].end_year == 2028
