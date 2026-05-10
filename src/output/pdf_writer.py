"""PDF 生成モジュール（WeasyPrint 使用）

Scenario + CashFlowRow 一覧 + FP コメントを受け取り、
WeasyPrint で PDF バイナリを生成して返す。
HTML テンプレートは外部ファイルに依存せず、文字列として組み立てる。
"""

import logging

from src.domain.cashflow_analysis import analyze
from src.domain.models import CashFlowRow, HousingEvent, IncomeModel, Scenario
from src.output import pdf_config

logger = logging.getLogger(__name__)


class PdfGenerationError(Exception):
    """PDF 生成失敗を表す例外"""


def _income_model_description(scenario: Scenario) -> str:
    """収入モデルの説明テキストを返す"""
    model = scenario.client.income_model
    if model == IncomeModel.FLAT:
        return "収入一定（毎年同額の収入）"
    elif model == IncomeModel.RAISE_RATE:
        rate_pct = scenario.client.raise_rate * 100
        return f"昇給率 {rate_pct:.1f}%（毎年昇給）"
    elif model == IncomeModel.POST_RETIREMENT:
        return f"定年後減額（定年後年収: {scenario.client.post_retirement_income:,}円）"
    return "収入一定"


def _build_html(
    scenario: Scenario,
    rows: list[CashFlowRow],
    fp_comment: str = "",
) -> str:
    """HTML テンプレートを組み立てて返す（WeasyPrint への入力）。

    テストから直接呼び出してフォント・CSS クラスを検証できるよう、
    モジュールレベルの関数として定義する。
    """
    summary = analyze(rows)
    has_spouse = scenario.spouse is not None
    income_desc = _income_model_description(scenario)

    # 赤字期間の説明テキスト
    if summary.deficit_periods:
        deficit_parts = []
        for p in summary.deficit_periods:
            if p.start_year == p.end_year:
                deficit_parts.append(f"{p.start_year}年")
            else:
                deficit_parts.append(f"{p.start_year}〜{p.end_year}年")
        deficit_text = "、".join(deficit_parts)
    else:
        deficit_text = ""

    # キャッシュフローテーブルの行 HTML を組み立てる
    table_rows_html = ""
    for row in rows:
        css_class = "negative-savings" if row.savings < 0 else ""
        class_attr = f' class="{css_class}"' if css_class else ""

        spouse_td = f"<td>{row.age_spouse}</td>" if has_spouse else ""

        net_class = "negative" if row.net < 0 else ""
        savings_class = "negative" if row.savings < 0 else ""

        table_rows_html += f"""
        <tr{class_attr}>
          <td>{row.year}</td>
          <td>{row.age_client}</td>
          {spouse_td}
          <td class="amount">{row.income_total:,}</td>
          <td class="amount">{row.expense_total:,}</td>
          <td class="amount">{row.loan_deduction:,}</td>
          <td class="amount {net_class}">{row.net:,}</td>
          <td class="amount {savings_class}">{row.savings:,}</td>
          <td>{row.events_label}</td>
        </tr>"""

    # 配偶者列ヘッダー
    spouse_th = "<th>配偶者年齢</th>" if has_spouse else ""

    # 住宅ローン金利の記載（HousingEvent がある場合のみ）
    housing_row_html = ""
    for event in scenario.events:
        if isinstance(event, HousingEvent):
            rate_pct = event.interest_rate * 100
            housing_row_html = f"""
        <tr>
          <td>住宅ローン金利</td>
          <td>{rate_pct:.1f}%</td>
        </tr>"""
            break

    # 赤字期間行（あれば）
    deficit_row_html = ""
    if deficit_text:
        deficit_row_html = f"""
        <tr>
          <td>赤字期間</td>
          <td>{deficit_text}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <style>
    @font-face {{
      font-family: "Klee One";
      src: url("{pdf_config.KLEE_ONE_FONT_PATH}");
    }}
    body {{
      font-family: "Hiragino Kaku Gothic Pro", "Meiryo", sans-serif;
      font-size: 10px;
      margin: 20px;
    }}
    h1 {{
      font-size: 16px;
      margin-bottom: 10px;
    }}
    h2 {{
      font-size: 13px;
      margin-top: 20px;
      margin-bottom: 6px;
      border-bottom: 1px solid #333;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 16px;
    }}
    th, td {{
      border: 1px solid #ccc;
      padding: 4px 6px;
      text-align: left;
    }}
    th {{
      background-color: #f0f0f0;
      font-weight: bold;
    }}
    td.amount {{
      text-align: right;
    }}
    td.negative {{
      color: #cc0000;
    }}
    tr.negative-savings {{
      background-color: #ffcccc;
    }}
    .fp-comment {{
      font-family: "{pdf_config.KLEE_ONE_FONT_FAMILY}";
      font-size: 11px;
      border: 1px solid #999;
      padding: 8px;
      min-height: 40px;
      margin-top: 4px;
    }}
    .premises-table td:first-child {{
      width: 160px;
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <h1>ライフイベント家計シミュレーション結果</h1>

  <h2>前提条件・注釈</h2>
  <table class="premises-table">
    <tr>
      <td>収入モデル</td>
      <td>{income_desc}</td>
    </tr>
    <tr>
      <td>インフレ率</td>
      <td>0%（固定）</td>
    </tr>
    <tr>
      <td>運用利回り</td>
      <td>0%（固定）</td>
    </tr>
    {housing_row_html}
  </table>

  <h2>注目ポイント</h2>
  <table class="premises-table">
    <tr>
      <td>貯蓄残高最低時期</td>
      <td>{summary.savings_low.year}年（{summary.savings_low.age}歳）・{summary.savings_low.amount:,}円</td>
    </tr>
    {deficit_row_html}
  </table>

  <h2>キャッシュフロー一覧</h2>
  <table>
    <thead>
      <tr>
        <th>年（西暦）</th>
        <th>本人年齢</th>
        {spouse_th}
        <th>収入合計</th>
        <th>支出合計</th>
        <th>住宅ローン控除</th>
        <th>年間収支</th>
        <th>貯蓄残高</th>
        <th>イベント</th>
      </tr>
    </thead>
    <tbody>
      {table_rows_html}
    </tbody>
  </table>

  <h2>FPコメント</h2>
  <div class="fp-comment">{fp_comment}</div>

</body>
</html>"""

    return html


def generate_pdf(
    scenario: Scenario,
    rows: list[CashFlowRow],
    fp_comment: str = "",
) -> bytes:
    """HTML テンプレートを組み立て WeasyPrint で PDF バイナリを生成して返す。

    Args:
        scenario: シナリオ情報
        rows: キャッシュフロー一覧
        fp_comment: FP コメント文字列（省略可）

    Returns:
        PDF バイナリ（%PDF- で始まる）

    Raises:
        PdfGenerationError: WeasyPrint が例外を送出した場合
    """
    try:
        from weasyprint import HTML

        html_str = _build_html(scenario, rows, fp_comment)
        pdf_bytes: bytes = HTML(string=html_str).write_pdf()
        return pdf_bytes
    except Exception as e:
        logger.error("PDF 生成中にエラーが発生しました: %s", e, exc_info=True)
        raise PdfGenerationError(f"PDF 生成に失敗しました: {e}") from e
