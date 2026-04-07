from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IncomeModel(Enum):
    FLAT = "flat"                        # 収入一定
    RAISE_RATE = "raise_rate"            # 昇給率指定
    POST_RETIREMENT = "post_retirement"  # 定年後減額


class SchoolType(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass
class Client:
    age: int
    annual_income: int                   # 税引後年収（円）
    income_model: IncomeModel = IncomeModel.FLAT
    raise_rate: float = 0.0              # 昇給率（income_model=RAISE_RATEのとき使用）
    retirement_age: int = 65
    post_retirement_income: int = 0      # 定年後年収
    pension_start_age: int = 65
    pension_annual: int = 0              # FPが手入力（自動試算なし）


@dataclass
class MonthlyExpenses:
    living: int      # 月間生活費
    insurance: int   # 保険料
    other: int       # その他固定費


@dataclass
class LifeEvent:
    year: int        # 発生年（西暦）


@dataclass
class MarriageEvent(LifeEvent):
    cost: int = 0


@dataclass
class BirthEvent(LifeEvent):
    child_count: int = 1


@dataclass
class HousingEvent(LifeEvent):
    price: int = 0
    down_payment: int = 0
    loan_years: int = 35
    interest_rate: float = 0.02
    use_tax_deduction: bool = True


@dataclass
class EducationEvent(LifeEvent):
    child_birth_year: int = 0
    kindergarten: SchoolType = SchoolType.PUBLIC
    elementary: SchoolType = SchoolType.PUBLIC
    junior_high: SchoolType = SchoolType.PUBLIC
    high_school: SchoolType = SchoolType.PUBLIC
    university: SchoolType = SchoolType.PUBLIC


@dataclass
class CareEvent(LifeEvent):
    duration_years: int = 1
    monthly_cost: int = 0


@dataclass
class OtherExpenseEvent(LifeEvent):
    amount: int = 0
    name: str = ""


@dataclass
class Scenario:
    client: Client
    spouse: Optional[Client]
    savings_initial: int
    end_age: int
    monthly_expenses: MonthlyExpenses
    events: list[LifeEvent] = field(default_factory=list)
    start_year: int = 2025           # シミュレーション開始年


@dataclass
class CashFlowRow:
    year: int
    age_client: int
    age_spouse: Optional[int]
    income_total: int
    expense_total: int
    loan_deduction: int
    net: int          # 収入合計 - 支出合計 + 住宅ローン控除
    savings: int      # 前年末残高 + net
    events_label: str
