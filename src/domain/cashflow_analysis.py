"""キャッシュフロー分析モジュール

貯蓄最低値の特定・赤字期間の検出を純粋なドメイン計算として分離する。
Excel・PDF どちらの出力にも共通して使われるため、output/ や api/ に依存しない。
"""

from dataclasses import dataclass

from src.domain.models import CashFlowRow


@dataclass(frozen=True)
class SavingsLow:
    """貯蓄残高が最も低くなる年の情報"""

    year: int
    age: int
    amount: int  # 円


@dataclass(frozen=True)
class DeficitPeriod:
    """net < 0 が連続または単発で発生する期間"""

    start_year: int
    end_year: int  # 単発の場合は start_year == end_year


@dataclass(frozen=True)
class CashFlowSummary:
    """Excel 第3シートおよび PDF の注目ポイント生成に使う分析結果"""

    savings_low: SavingsLow
    deficit_periods: list[DeficitPeriod]  # 空リスト = 赤字なし


def analyze(rows: list[CashFlowRow]) -> CashFlowSummary:
    """キャッシュフロー一覧を分析して貯蓄最低値と赤字期間を返す。

    Args:
        rows: キャッシュフロー一覧（1行以上必須）

    Returns:
        CashFlowSummary: 貯蓄最低値と赤字期間のまとめ

    Raises:
        ValueError: rows が空の場合
    """
    if not rows:
        raise ValueError("キャッシュフロー一覧が空です。分析対象の行が必要です。")

    # 貯蓄最低値: savings が最小の行を特定する
    min_row = min(rows, key=lambda r: r.savings)
    savings_low = SavingsLow(
        year=min_row.year,
        age=min_row.age_client,
        amount=min_row.savings,
    )

    # 赤字期間: net < 0 の行を走査し、連続する年をひとつの DeficitPeriod にまとめる
    deficit_periods: list[DeficitPeriod] = []
    period_start: int | None = None
    period_end: int | None = None

    for row in rows:
        if row.net < 0:
            if period_start is None:
                # 新しい赤字期間の開始
                period_start = row.year
                period_end = row.year
            elif row.year == period_end + 1:  # type: ignore[operator]
                # 連続する赤字期間の延長
                period_end = row.year
            else:
                # 連続していない → 前の期間を確定し、新しい期間を開始
                deficit_periods.append(
                    DeficitPeriod(start_year=period_start, end_year=period_end)  # type: ignore[arg-type]
                )
                period_start = row.year
                period_end = row.year
        else:
            if period_start is not None:
                # 赤字期間が終了 → 確定
                deficit_periods.append(
                    DeficitPeriod(start_year=period_start, end_year=period_end)  # type: ignore[arg-type]
                )
                period_start = None
                period_end = None

    # ループ終了後に未確定の赤字期間が残っている場合
    if period_start is not None:
        deficit_periods.append(
            DeficitPeriod(start_year=period_start, end_year=period_end)  # type: ignore[arg-type]
        )

    return CashFlowSummary(
        savings_low=savings_low,
        deficit_periods=deficit_periods,
    )
