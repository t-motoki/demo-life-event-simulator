"""YAML → Scenarioオブジェクト変換モジュール"""

from pathlib import Path
from typing import Any

import yaml

from src.domain.models import (
    BirthEvent,
    CareEvent,
    Client,
    EducationEvent,
    HousingEvent,
    IncomeModel,
    LifeEvent,
    MarriageEvent,
    MonthlyExpenses,
    OtherExpenseEvent,
    Scenario,
    SchoolType,
)


def _parse_client(data: dict[str, Any]) -> Client:
    """クライアントデータをClientオブジェクトに変換する"""
    return Client(
        age=data["age"],
        annual_income=data["annual_income"],
        income_model=IncomeModel(data.get("income_model", "flat")),
        raise_rate=data.get("raise_rate", 0.0),
        retirement_age=data.get("retirement_age", 65),
        post_retirement_income=data.get("post_retirement_income", 0),
        pension_start_age=data.get("pension_start_age", 65),
        pension_annual=data.get("pension_annual", 0),
    )


def _parse_monthly_expenses(data: dict[str, Any]) -> MonthlyExpenses:
    """月間支出データをMonthlyExpensesオブジェクトに変換する"""
    return MonthlyExpenses(
        living=data["living"],
        insurance=data["insurance"],
        other=data["other"],
    )


def _parse_event(data: dict[str, Any]) -> LifeEvent:
    """イベントデータをLifeEventサブクラスに変換する"""
    event_type = data["type"]
    year = data["year"]

    match event_type:
        case "marriage":
            return MarriageEvent(
                year=year,
                cost=data.get("cost", 0),
            )
        case "birth":
            return BirthEvent(
                year=year,
                child_count=data.get("child_count", 1),
            )
        case "housing":
            return HousingEvent(
                year=year,
                price=data.get("price", 0),
                down_payment=data.get("down_payment", 0),
                loan_years=data.get("loan_years", 35),
                interest_rate=data.get("interest_rate", 0.02),
                use_tax_deduction=data.get("use_tax_deduction", True),
            )
        case "education":
            return EducationEvent(
                year=year,
                child_birth_year=data.get("child_birth_year", year),
                kindergarten=SchoolType(data.get("kindergarten", "public")),
                elementary=SchoolType(data.get("elementary", "public")),
                junior_high=SchoolType(data.get("junior_high", "public")),
                high_school=SchoolType(data.get("high_school", "public")),
                university=SchoolType(data.get("university", "public")),
            )
        case "care":
            return CareEvent(
                year=year,
                duration_years=data.get("duration_years", 1),
                monthly_cost=data.get("monthly_cost", 0),
            )
        case "other_expense":
            return OtherExpenseEvent(
                year=year,
                amount=data.get("amount", 0),
                name=data.get("name", ""),
            )
        case _:
            raise ValueError(f"未知のイベントタイプです: {event_type}")


def load_scenario(path: str | Path) -> Scenario:
    """YAMLファイルからScenarioオブジェクトを構築する

    Args:
        path: YAMLファイルのパス

    Returns:
        Scenarioオブジェクト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: YAMLの内容が不正な場合
    """
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"シナリオファイルが見つかりません: {path}")

    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    client = _parse_client(data["client"])

    spouse = None
    if "spouse" in data and data["spouse"] is not None:
        spouse = _parse_client(data["spouse"])

    monthly_expenses = _parse_monthly_expenses(data["monthly_expenses"])

    events: list[LifeEvent] = []
    for event_data in data.get("events", []):
        events.append(_parse_event(event_data))

    return Scenario(
        client=client,
        spouse=spouse,
        savings_initial=data["savings_initial"],
        end_age=data["end_age"],
        monthly_expenses=monthly_expenses,
        events=events,
        start_year=data.get("start_year", 2025),
    )
