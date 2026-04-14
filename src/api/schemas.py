"""API リクエスト／レスポンス Pydantic スキーマ定義

ドメインの dataclass とは別クラスとして定義する。
ドメイン層を外部ライブラリ（Pydantic）に依存させないための設計上の判断。
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

# ドメインの Enum をそのまま型ヒントに使う（Pydantic v2 が文字列と自動マッピングする）
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
    MonthlyExpenses,
    OtherExpenseEvent,
    Scenario,
    SchoolType,
)


# ---------------------------------------------------------------------------
# クライアント情報
# ---------------------------------------------------------------------------

class ClientRequest(BaseModel):
    age: int
    annual_income: int
    income_model: IncomeModel = IncomeModel.FLAT
    raise_rate: float = 0.0
    retirement_age: int = 65
    post_retirement_income: int = 0
    pension_start_age: int = 65
    pension_annual: int = 0


# ---------------------------------------------------------------------------
# 月間支出
# ---------------------------------------------------------------------------

class MonthlyExpensesRequest(BaseModel):
    living: int
    insurance: int
    other: int


# ---------------------------------------------------------------------------
# ライフイベント（discriminated union）
#
# type フィールドの値で Pydantic が構造を自動的に分岐する。
# 未知の type 値が来た場合は Pydantic が ValidationError を送出し、
# FastAPI が HTTP 422 に変換する。
# ---------------------------------------------------------------------------

class MarriageEventRequest(BaseModel):
    type: Literal["marriage"]
    year: int
    cost: int = 0


class BirthEventRequest(BaseModel):
    type: Literal["birth"]
    year: int
    child_count: int = 1
    client_maternity_rate: float = 1.0
    client_maternity_years: int = 0
    spouse_maternity_rate: float = 1.0
    spouse_maternity_years: int = 0


class HousingEventRequest(BaseModel):
    type: Literal["housing"]
    year: int
    price: int = 0
    down_payment: int = 0
    loan_years: int = 35
    interest_rate: float = 0.02
    use_tax_deduction: bool = True


class EducationEventRequest(BaseModel):
    type: Literal["education"]
    year: int
    child_birth_year: int = 0
    kindergarten: SchoolType = SchoolType.PUBLIC
    elementary: SchoolType = SchoolType.PUBLIC
    junior_high: SchoolType = SchoolType.PUBLIC
    high_school: SchoolType = SchoolType.PUBLIC
    university: SchoolType = SchoolType.PUBLIC


class CareEventRequest(BaseModel):
    type: Literal["care"]
    year: int
    duration_years: int = 1
    monthly_cost: int = 0


class OtherExpenseEventRequest(BaseModel):
    type: Literal["other_expense"]
    year: int
    amount: int = 0
    name: str = ""


# discriminated union: type フィールドで分岐する
EventRequest = Annotated[
    Union[
        MarriageEventRequest,
        BirthEventRequest,
        HousingEventRequest,
        EducationEventRequest,
        CareEventRequest,
        OtherExpenseEventRequest,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# シナリオ全体リクエスト
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    client: ClientRequest
    spouse: Optional[ClientRequest] = None
    savings_initial: int
    end_age: int
    start_year: int = 2025
    monthly_expenses: MonthlyExpensesRequest
    events: list[EventRequest] = []


# ---------------------------------------------------------------------------
# レスポンス
# ---------------------------------------------------------------------------

class CashFlowRowResponse(BaseModel):
    year: int
    age_client: int
    age_spouse: Optional[int]
    income_total: int
    expense_total: int
    loan_deduction: int
    net: int
    savings: int
    events_label: str


# ---------------------------------------------------------------------------
# 変換関数: Pydantic スキーマ → ドメイン dataclass
#
# yaml_loader.py の _parse_event とは別実装にする。
# yaml_loader は dict を受け取る設計で、ここでは型検証済みの Pydantic オブジェクトを受け取る。
# ---------------------------------------------------------------------------

def _to_domain_client(req: ClientRequest) -> Client:
    return Client(
        age=req.age,
        annual_income=req.annual_income,
        income_model=req.income_model,
        raise_rate=req.raise_rate,
        retirement_age=req.retirement_age,
        post_retirement_income=req.post_retirement_income,
        pension_start_age=req.pension_start_age,
        pension_annual=req.pension_annual,
    )


def _to_domain_event(req: EventRequest) -> LifeEvent:
    """Pydantic イベントスキーマをドメインイベント dataclass に変換する"""
    if isinstance(req, MarriageEventRequest):
        return MarriageEvent(year=req.year, cost=req.cost)

    if isinstance(req, BirthEventRequest):
        return BirthEvent(
            year=req.year,
            child_count=req.child_count,
            client_maternity_rate=req.client_maternity_rate,
            client_maternity_years=req.client_maternity_years,
            spouse_maternity_rate=req.spouse_maternity_rate,
            spouse_maternity_years=req.spouse_maternity_years,
        )

    if isinstance(req, HousingEventRequest):
        return HousingEvent(
            year=req.year,
            price=req.price,
            down_payment=req.down_payment,
            loan_years=req.loan_years,
            interest_rate=req.interest_rate,
            use_tax_deduction=req.use_tax_deduction,
        )

    if isinstance(req, EducationEventRequest):
        return EducationEvent(
            year=req.year,
            child_birth_year=req.child_birth_year,
            kindergarten=req.kindergarten,
            elementary=req.elementary,
            junior_high=req.junior_high,
            high_school=req.high_school,
            university=req.university,
        )

    if isinstance(req, CareEventRequest):
        return CareEvent(
            year=req.year,
            duration_years=req.duration_years,
            monthly_cost=req.monthly_cost,
        )

    if isinstance(req, OtherExpenseEventRequest):
        return OtherExpenseEvent(
            year=req.year,
            amount=req.amount,
            name=req.name,
        )

    # ここに到達することは Pydantic の discriminated union が防ぐが、念のため
    raise ValueError(f"不明なイベント種別: {req}")


def to_domain_scenario(req: SimulateRequest) -> Scenario:
    """SimulateRequest をドメイン Scenario に変換する"""
    return Scenario(
        client=_to_domain_client(req.client),
        spouse=_to_domain_client(req.spouse) if req.spouse is not None else None,
        savings_initial=req.savings_initial,
        end_age=req.end_age,
        start_year=req.start_year,
        monthly_expenses=MonthlyExpenses(
            living=req.monthly_expenses.living,
            insurance=req.monthly_expenses.insurance,
            other=req.monthly_expenses.other,
        ),
        events=[_to_domain_event(e) for e in req.events],
    )


def to_response(rows: list[CashFlowRow]) -> list[CashFlowRowResponse]:
    """ドメインの CashFlowRow 一覧をレスポンス形式に変換する"""
    return [
        CashFlowRowResponse(
            year=row.year,
            age_client=row.age_client,
            age_spouse=row.age_spouse,
            income_total=row.income_total,
            expense_total=row.expense_total,
            loan_deduction=row.loan_deduction,
            net=row.net,
            savings=row.savings,
            events_label=row.events_label,
        )
        for row in rows
    ]
