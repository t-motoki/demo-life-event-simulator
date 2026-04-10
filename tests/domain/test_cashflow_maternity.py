"""育休中の収入減機能のテスト"""

from src.domain.cashflow import _maternity_rate, simulate
from src.domain.models import (
    BirthEvent,
    CashFlowRow,
    Client,
    IncomeModel,
    LifeEvent,
    MonthlyExpenses,
    Scenario,
)


# --- _maternity_rate 単体テスト ---


def test_maternity_rate_no_birth_event():
    """BirthEventがなければ1.0を返す"""
    events: list[LifeEvent] = []
    assert _maternity_rate(events, "client", 2026) == 1.0
    assert _maternity_rate(events, "spouse", 2026) == 1.0


def test_maternity_rate_no_leave_taken():
    """育休フィールドがデフォルト値（rate=1.0, years=0）のとき1.0を返す"""
    events: list[LifeEvent] = [BirthEvent(year=2026, child_count=1)]
    assert _maternity_rate(events, "client", 2026) == 1.0
    assert _maternity_rate(events, "spouse", 2026) == 1.0


def test_maternity_rate_client_in_leave_period():
    """本人が育休中の年は指定率を返す"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2026,
            child_count=1,
            client_maternity_rate=0.5,
            client_maternity_years=1,
        )
    ]
    # 2026年: 育休中（2026 <= 2026 < 2026+1）
    assert _maternity_rate(events, "client", 2026) == 0.5


def test_maternity_rate_client_after_leave_period():
    """育休期間を過ぎた年は1.0を返す"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2026,
            child_count=1,
            client_maternity_rate=0.5,
            client_maternity_years=1,
        )
    ]
    # 2027年: 育休終了後（2026+1=2027 は範囲外）
    assert _maternity_rate(events, "client", 2027) == 1.0


def test_maternity_rate_spouse_in_leave_period():
    """配偶者が育休中の年は指定率を返す"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2026,
            child_count=1,
            spouse_maternity_rate=0.6,
            spouse_maternity_years=2,
        )
    ]
    # 2026年: 育休中（2026 <= 2026 < 2026+2）
    assert _maternity_rate(events, "spouse", 2026) == 0.6
    # 2027年: まだ育休中（2026 <= 2027 < 2028）
    assert _maternity_rate(events, "spouse", 2027) == 0.6


def test_maternity_rate_spouse_after_leave_period():
    """配偶者の育休期間を過ぎた年は1.0を返す"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2026,
            child_count=1,
            spouse_maternity_rate=0.6,
            spouse_maternity_years=2,
        )
    ]
    # 2028年: 育休終了後
    assert _maternity_rate(events, "spouse", 2028) == 1.0


def test_maternity_rate_multiple_birth_events_takes_minimum():
    """複数のBirthEventが同じ年に重なる場合は最小率を採用する"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2026,
            child_count=1,
            spouse_maternity_rate=0.6,
            spouse_maternity_years=1,
        ),
        BirthEvent(
            year=2026,
            child_count=1,
            spouse_maternity_rate=0.4,  # より低い率
            spouse_maternity_years=1,
        ),
    ]
    assert _maternity_rate(events, "spouse", 2026) == 0.4


def test_maternity_rate_rate_1_does_not_apply():
    """rate=1.0 のBirthEventは育休なしと同じ挙動（1.0を返す）"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2026,
            child_count=1,
            client_maternity_rate=1.0,
            client_maternity_years=1,
        )
    ]
    # m_rate < 1.0 の条件を満たさないため、1.0を返す
    assert _maternity_rate(events, "client", 2026) == 1.0


# --- simulate() 統合テスト ---


def _make_simple_scenario(
    events: list[LifeEvent],
    client_income: int = 1_000_000,
    spouse_income: int | None = None,
) -> Scenario:
    """テスト用シナリオを生成するヘルパー"""
    client = Client(
        age=30,
        annual_income=client_income,
        income_model=IncomeModel.FLAT,
        retirement_age=65,
        pension_start_age=65,
        pension_annual=0,
    )
    spouse = None
    if spouse_income is not None:
        spouse = Client(
            age=28,
            annual_income=spouse_income,
            income_model=IncomeModel.FLAT,
            retirement_age=65,
            pension_start_age=65,
            pension_annual=0,
        )
    return Scenario(
        client=client,
        spouse=spouse,
        savings_initial=0,
        end_age=32,  # 3年分だけ計算
        monthly_expenses=MonthlyExpenses(living=0, insurance=0, other=0),
        events=events,
        start_year=2025,
    )


def test_simulate_client_income_reduced_during_maternity():
    """育休中の年は本人収入が減額される"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2025,
            child_count=1,
            client_maternity_rate=0.5,
            client_maternity_years=1,
        )
    ]
    scenario = _make_simple_scenario(events, client_income=1_000_000)
    rows = simulate(scenario)

    # 2025年: 育休中 → 1,000,000 * 0.5 = 500,000
    row_2025 = next(r for r in rows if r.year == 2025)
    assert row_2025.income_total == 500_000

    # 2026年: 育休終了 → 1,000,000
    row_2026 = next(r for r in rows if r.year == 2026)
    assert row_2026.income_total == 1_000_000


def test_simulate_spouse_income_reduced_during_maternity():
    """育休中の年は配偶者収入が減額される"""
    events: list[LifeEvent] = [
        BirthEvent(
            year=2025,
            child_count=1,
            spouse_maternity_rate=0.6,
            spouse_maternity_years=1,
        )
    ]
    scenario = _make_simple_scenario(
        events, client_income=1_000_000, spouse_income=1_000_000
    )
    rows = simulate(scenario)

    # 2025年: 配偶者育休中 → client 1,000,000 + spouse 600,000 = 1,600,000
    row_2025 = next(r for r in rows if r.year == 2025)
    assert row_2025.income_total == 1_600_000

    # 2026年: 育休終了 → 2,000,000
    row_2026 = next(r for r in rows if r.year == 2026)
    assert row_2026.income_total == 2_000_000


def test_simulate_no_maternity_leave_unchanged():
    """育休フィールドがデフォルト値のとき収入は変わらない"""
    events: list[LifeEvent] = [BirthEvent(year=2025, child_count=1)]
    scenario = _make_simple_scenario(events, client_income=1_000_000)
    rows = simulate(scenario)

    row_2025 = next(r for r in rows if r.year == 2025)
    assert row_2025.income_total == 1_000_000
