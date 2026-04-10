"""年次キャッシュフロー計算モジュール"""

import sys
from typing import Optional

from src.domain.education import get_education_cost
from src.domain.loan import LoanSchedule
from src.domain.models import (
    BirthEvent,
    CareEvent,
    CashFlowRow,
    Client,
    EducationEvent,
    HousingEvent,
    IncomeModel,
    LifeEvent,
    MarriageEvent,
    OtherExpenseEvent,
    Scenario,
)


def _calc_income(client: Client, year: int, start_year: int) -> int:
    """指定年の給与収入を計算する（年金を除く）

    Args:
        client: クライアント情報
        year: 西暦年
        start_year: シミュレーション開始年

    Returns:
        給与収入（円）
    """
    client_age_this_year = client.age + (year - start_year)

    if client_age_this_year >= client.retirement_age:
        # 定年後
        return client.post_retirement_income

    match client.income_model:
        case IncomeModel.FLAT:
            return client.annual_income
        case IncomeModel.RAISE_RATE:
            years_elapsed = year - start_year
            income = client.annual_income * (1 + client.raise_rate) ** years_elapsed
            return int(income)
        case IncomeModel.POST_RETIREMENT:
            return client.annual_income
        case _:
            return client.annual_income


def _calc_pension(client: Client, year: int, start_year: int) -> int:
    """指定年の年金収入を計算する

    Args:
        client: クライアント情報
        year: 西暦年
        start_year: シミュレーション開始年

    Returns:
        年金収入（円）
    """
    client_age_this_year = client.age + (year - start_year)
    if client_age_this_year >= client.pension_start_age:
        return client.pension_annual
    return 0


def _maternity_rate(events: list[LifeEvent], target: str, year: int) -> float:
    """指定年に有効な育休減額率を返す。複数の BirthEvent がある場合は最小値を使う。

    Args:
        events: イベント一覧
        target: "client" または "spouse"
        year: 西暦年

    Returns:
        収入率（0.0〜1.0）。育休なしなら 1.0
    """
    rate = 1.0
    for event in events:
        if not isinstance(event, BirthEvent):
            continue
        if target == "client":
            m_rate = event.client_maternity_rate
            m_years = event.client_maternity_years
        else:
            m_rate = event.spouse_maternity_rate
            m_years = event.spouse_maternity_years
        # m_rate < 1.0 かつ育休期間内のとき、より小さい率を採用する
        if m_rate < 1.0 and event.year <= year < event.year + m_years:
            rate = min(rate, m_rate)
    return rate


def _build_loan_schedule(events: list[LifeEvent]) -> Optional[LoanSchedule]:
    """住宅イベントからローンスケジュールを構築する"""
    for event in events:
        if isinstance(event, HousingEvent):
            loan_amount = event.price - event.down_payment
            if loan_amount > 0:
                return LoanSchedule(
                    loan_amount=loan_amount,
                    annual_rate=event.interest_rate,
                    loan_years=event.loan_years,
                    start_year=event.year,
                )
    return None


def _event_labels(events: list[LifeEvent], year: int) -> str:
    """指定年に発生するイベントのラベル文字列を返す"""
    labels = []
    for event in events:
        if isinstance(event, MarriageEvent) and event.year == year:
            labels.append("結婚")
        elif isinstance(event, BirthEvent) and event.year == year:
            labels.append(f"出産×{event.child_count}")
        elif isinstance(event, HousingEvent) and event.year == year:
            labels.append("住宅購入")
        elif isinstance(event, CareEvent):
            if event.year <= year < event.year + event.duration_years:
                labels.append("介護")
        elif isinstance(event, OtherExpenseEvent) and event.year == year:
            labels.append(event.name if event.name else "その他支出")
    return " / ".join(labels)


def simulate(scenario: Scenario) -> list[CashFlowRow]:
    """シナリオ全体のキャッシュフローを計算する

    Args:
        scenario: シナリオ情報

    Returns:
        年次キャッシュフロー一覧
    """
    rows: list[CashFlowRow] = []
    savings = scenario.savings_initial
    loan_schedule = _build_loan_schedule(scenario.events)

    # シミュレーション終了年の計算
    end_year = scenario.start_year + (scenario.end_age - scenario.client.age)

    for year in range(scenario.start_year, end_year + 1):
        client_age = scenario.client.age + (year - scenario.start_year)
        spouse_age: Optional[int] = None
        if scenario.spouse is not None:
            spouse_age = scenario.spouse.age + (year - scenario.start_year)

        # --- 収入計算 ---
        # 育休中は給与収入に減額率を乗算する（年金収入には適用しない）
        client_rate = _maternity_rate(scenario.events, "client", year)
        income = int(_calc_income(scenario.client, year, scenario.start_year) * client_rate)
        income += _calc_pension(scenario.client, year, scenario.start_year)

        if scenario.spouse is not None:
            spouse_rate = _maternity_rate(scenario.events, "spouse", year)
            income += int(_calc_income(scenario.spouse, year, scenario.start_year) * spouse_rate)
            income += _calc_pension(scenario.spouse, year, scenario.start_year)

        # --- 支出計算 ---
        # 月間固定費
        monthly = scenario.monthly_expenses
        expense = (monthly.living + monthly.insurance + monthly.other) * 12

        # 住宅ローン返済額
        loan_payment = 0
        if loan_schedule is not None:
            loan_payment = loan_schedule.annual_payment(year)
        expense += loan_payment

        # イベント費用
        for event in scenario.events:
            if isinstance(event, MarriageEvent) and event.year == year:
                expense += event.cost
            elif isinstance(event, BirthEvent) and event.year == year:
                pass  # 出産費用は現バージョンでは別途OtherExpenseEventで管理
            elif isinstance(event, HousingEvent) and event.year == year:
                expense += event.down_payment  # 頭金
            elif isinstance(event, CareEvent):
                if event.year <= year < event.year + event.duration_years:
                    expense += event.monthly_cost * 12
            elif isinstance(event, OtherExpenseEvent) and event.year == year:
                expense += event.amount

        # 教育費
        for event in scenario.events:
            if isinstance(event, EducationEvent):
                expense += get_education_cost(event, year)

        # --- 住宅ローン控除 ---
        loan_deduction = 0
        if loan_schedule is not None:
            housing_event = next(
                (e for e in scenario.events if isinstance(e, HousingEvent)), None
            )
            if housing_event and housing_event.use_tax_deduction:
                loan_deduction = loan_schedule.deduction_amount(year)

        # --- 年間収支・貯蓄残高 ---
        net = income - expense + loan_deduction
        prev_savings = savings
        savings = savings + net
        if savings < 0 and prev_savings >= 0:
            print(
                f"警告: {year}年（本人{client_age}歳）に貯蓄残高がマイナスになりました"
                f"（{savings:,}円）",
                file=sys.stderr,
            )

        row = CashFlowRow(
            year=year,
            age_client=client_age,
            age_spouse=spouse_age,
            income_total=income,
            expense_total=expense,
            loan_deduction=loan_deduction,
            net=net,
            savings=savings,
            events_label=_event_labels(scenario.events, year),
        )
        rows.append(row)

    return rows
