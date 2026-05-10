"""FP コメント自動生成モジュール（Claude API 使用）

anthropic パッケージへの依存はこのファイルに閉じ込める。
他のモジュールが直接 anthropic を import することは禁止。
"""

import logging

from src.domain.cashflow_analysis import analyze
from src.domain.models import CashFlowRow, IncomeModel, Scenario

logger = logging.getLogger(__name__)

# モジュールトップレベルでクライアントを生成する（関数呼び出しのたびに生成しない）
# ANTHROPIC_API_KEY が未設定の場合は None にして、テスト時にモックできるようにする
try:
    import anthropic as _anthropic_module
    _client = _anthropic_module.Anthropic()
except Exception:
    # API キー未設定やインポートエラー時は None にする（テスト時は mock で差し替える）
    _client = None  # type: ignore[assignment]


class CommentGenerationError(Exception):
    """Claude API 呼び出し失敗を表す例外"""


def _build_prompt(scenario: Scenario, rows: list[CashFlowRow]) -> str:
    """Claude API に送るプロンプトを組み立てる。

    生の rows 全行は含めない（トークン節約）。
    analyze() の結果を構造化テキストとして埋め込む。
    """
    summary = analyze(rows)
    start_year = rows[0].year
    end_year = rows[-1].year

    # 収入モデルの説明
    income_model_map = {
        IncomeModel.FLAT: "収入一定",
        IncomeModel.RAISE_RATE: f"昇給率 {scenario.client.raise_rate * 100:.1f}%",
        IncomeModel.POST_RETIREMENT: f"定年後減額（定年後年収: {scenario.client.post_retirement_income:,}円）",
    }
    income_desc = income_model_map.get(scenario.client.income_model, "収入一定")

    # 赤字期間の説明
    if summary.deficit_periods:
        deficit_lines = []
        for period in summary.deficit_periods:
            if period.start_year == period.end_year:
                deficit_lines.append(f"{period.start_year}年")
            else:
                deficit_lines.append(f"{period.start_year}〜{period.end_year}年")
        deficit_desc = "赤字期間: " + "、".join(deficit_lines)
    else:
        deficit_desc = "赤字期間: なし"

    prompt = f"""以下はライフイベント家計シミュレーションの分析結果です。
FP（ファイナンシャルプランナー）がクライアントに渡す資料向けに、200文字以内の日本語コメントを1段落で書いてください。

【シミュレーション概要】
- 期間: {start_year}年〜{end_year}年
- 収入モデル: {income_desc}

【注目ポイント】
- 貯蓄残高が最も低くなる時期: {summary.savings_low.year}年（{summary.savings_low.age}歳）、残高 {summary.savings_low.amount:,}円
- {deficit_desc}

コメントはFP向けの専門的な表現で、クライアントへの説明に使えるものにしてください。
200文字以内で1段落にまとめてください。それ以上書かないでください。"""

    return prompt


def generate_comment(
    scenario: Scenario,
    rows: list[CashFlowRow],
    max_chars: int = 200,
) -> str:
    """Claude API を呼び出して FP コメントを生成する。

    Args:
        scenario: シナリオ情報
        rows: キャッシュフロー一覧
        max_chars: 返却文字列の最大文字数（デフォルト 200）

    Returns:
        FP コメント文字列（max_chars 以内であることを保証）

    Raises:
        CommentGenerationError: Claude API が応答しないか例外を送出した場合
    """
    try:
        prompt = _build_prompt(scenario, rows)
        response = _client.messages.create(  # type: ignore[union-attr]
            model="claude-haiku-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        # text 属性を持つ最初のブロックを取得する（TextBlock 以外は除外）
        first_block = response.content[0]
        if not hasattr(first_block, "text"):
            raise CommentGenerationError("Claude API から予期しないレスポンス形式が返されました")
        text: str = first_block.text
    except CommentGenerationError:
        raise
    except Exception as e:
        raise CommentGenerationError(f"Claude API 呼び出しに失敗しました: {e}") from e

    # max_chars を超えた場合は末尾を切り捨てる
    if len(text) > max_chars:
        logger.warning(
            "生成コメントが %d 文字を超えたため切り捨てました（元の長さ: %d 文字）",
            max_chars,
            len(text),
        )
        text = text[:max_chars]

    return text
