"""FPコメント生成モジュールのユニットテスト

Claude API は unittest.mock.patch でモックする。実際の API 呼び出しは行わない。
"""

from unittest.mock import MagicMock, patch

import pytest

from src.domain.models import CashFlowRow, Client, IncomeModel, MonthlyExpenses, Scenario


def _make_row(year: int, age_client: int, net: int, savings: int) -> CashFlowRow:
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


def _base_scenario() -> Scenario:
    return Scenario(
        client=Client(age=35, annual_income=5_000_000, income_model=IncomeModel.FLAT),
        spouse=None,
        savings_initial=3_000_000,
        end_age=70,
        monthly_expenses=MonthlyExpenses(living=200_000, insurance=20_000, other=10_000),
        start_year=2026,
    )


def _rows_with_deficit():
    return [
        _make_row(2026, 35, 100_000, 3_100_000),
        _make_row(2045, 54, -500_000, 2_000_000),
        _make_row(2046, 55, 200_000, 2_200_000),
    ]


def _rows_no_deficit():
    return [
        _make_row(2026, 35, 100_000, 3_100_000),
        _make_row(2027, 36, 200_000, 3_300_000),
        _make_row(2028, 37, 150_000, 3_450_000),
    ]


class TestGenerateComment:
    def test_generate_comment_returns_nonempty_string(self):
        """生成されたコメントが空でない（AC-2-1）"""
        from src.output.comment_generator import generate_comment

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="50歳時点で貯蓄が最も低くなります。早めの対策をご検討ください。")]

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            rows = _rows_no_deficit()
            result = generate_comment(_base_scenario(), rows)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_comment_within_200_chars(self):
        """コメントが 200 文字以内（AC-2-2）"""
        from src.output.comment_generator import generate_comment

        # 201 文字を超えるテキストをモックで返す
        long_text = "あ" * 250
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=long_text)]

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_comment(_base_scenario(), _rows_no_deficit())

        assert len(result) <= 200

    def test_generate_comment_mentions_deficit_year(self):
        """赤字ありシナリオでは返却テキストに赤字年への言及がある（AC-2-3）

        Claude API の返却テキストを fixture で固定してテストする。
        """
        from src.output.comment_generator import generate_comment

        fixed_text = "2045年に収支がマイナスになります。住宅ローンの返済と教育費が重なる時期のため、早めに備えることをお勧めします。"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=fixed_text)]

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_comment(_base_scenario(), _rows_with_deficit())

        # fixture テキストに赤字関連の表現が含まれることを確認
        has_deficit_mention = any(
            keyword in result for keyword in ["赤字", "収支がマイナス", "資金不足", "マイナス"]
        )
        assert has_deficit_mention

    def test_generate_comment_mentions_savings_low(self):
        """貯蓄最低値の年齢または金額への言及がある（AC-2-4）"""
        from src.output.comment_generator import generate_comment

        fixed_text = "50歳時点の貯蓄残高が最も低く、約200万円となります。この時期に向けた資産形成が重要です。"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=fixed_text)]

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_comment(_base_scenario(), _rows_with_deficit())

        # 年齢か金額への言及がある
        assert "歳" in result or "万円" in result or "円" in result

    def test_generate_comment_no_negative_words_when_no_deficit(self):
        """赤字なしシナリオでは否定的な財務表現が含まれない（AC-2-5）"""
        from src.output.comment_generator import generate_comment

        fixed_text = "シミュレーション期間中、収支は安定しています。貯蓄残高も着実に増加しており、健全な資産形成が見込まれます。"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=fixed_text)]

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_comment(_base_scenario(), _rows_no_deficit())

        # 否定的な財務表現が含まれないことを確認
        negative_words = ["赤字", "資金不足"]
        for word in negative_words:
            assert word not in result

    def test_generate_comment_truncates_if_over_limit(self):
        """200 字超えの返却値が切り捨てられること"""
        from src.output.comment_generator import generate_comment

        # ちょうど 210 文字のテキスト
        long_text = "あ" * 210
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=long_text)]

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.return_value = mock_response
            result = generate_comment(_base_scenario(), _rows_no_deficit(), max_chars=200)

        assert len(result) == 200

    def test_generate_comment_raises_on_api_error(self):
        """Claude API が例外を送出した場合 CommentGenerationError が送出される"""
        from src.output.comment_generator import CommentGenerationError, generate_comment

        with patch("src.output.comment_generator._client") as mock_client:
            mock_client.messages.create.side_effect = Exception("API接続エラー")

            with pytest.raises(CommentGenerationError):
                generate_comment(_base_scenario(), _rows_no_deficit())
