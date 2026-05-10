"""PDF生成モジュールのテスト

WeasyPrint を実際に呼び出す。
AC-3-5（フォント確認）と AC-3-9（CSS クラス確認）は
_build_html() の返却値を直接テストする形で行う。
"""

import pytest

from src.domain.models import (
    CashFlowRow,
    Client,
    IncomeModel,
    MonthlyExpenses,
    Scenario,
)


def _make_row(year: int, age_client: int, net: int, savings: int, age_spouse=None) -> CashFlowRow:
    return CashFlowRow(
        year=year,
        age_client=age_client,
        age_spouse=age_spouse,
        income_total=5_000_000,
        expense_total=4_000_000,
        loan_deduction=0,
        net=net,
        savings=savings,
        events_label="",
    )


def _base_scenario(with_spouse: bool = False) -> Scenario:
    spouse = Client(age=33, annual_income=3_000_000) if with_spouse else None
    return Scenario(
        client=Client(age=35, annual_income=5_000_000, income_model=IncomeModel.FLAT),
        spouse=spouse,
        savings_initial=3_000_000,
        end_age=70,
        monthly_expenses=MonthlyExpenses(living=200_000, insurance=20_000, other=10_000),
        start_year=2026,
    )


@pytest.fixture
def simple_rows():
    return [
        _make_row(2026, 35, 100_000, 3_100_000),
        _make_row(2027, 36, 200_000, 3_300_000),
        _make_row(2028, 37, 150_000, 3_450_000),
        _make_row(2029, 38, 100_000, 3_550_000),
        _make_row(2030, 39, 100_000, 3_650_000),
    ]


class TestBuildHtml:
    """_build_html() の返却 HTML を検証する"""

    def test_pdf_klee_one_in_css(self, simple_rows):
        """FP コメント欄に Klee One フォントが設定されている（AC-3-5）

        WeasyPrint に渡す HTML に font-family: "Klee One" が含まれることを検証する。
        """
        from src.output.pdf_writer import _build_html

        html = _build_html(_base_scenario(), simple_rows, fp_comment="テストコメント")
        assert 'font-family: "Klee One"' in html or "font-family: 'Klee One'" in html

    def test_pdf_klee_one_font_face_path(self, simple_rows):
        """@font-face に KleeOne-Regular.ttf のパスが含まれている（AC-3-5 の追加検証）"""
        from src.output.pdf_writer import _build_html

        html = _build_html(_base_scenario(), simple_rows, fp_comment="テストコメント")
        assert "KleeOne-Regular.ttf" in html

    def test_pdf_negative_savings_row_has_css_class(self):
        """savings < 0 の行に negative-savings CSS クラスが付与されている（AC-3-9）"""
        from src.output.pdf_writer import _build_html

        rows = [
            _make_row(2026, 35, 100_000, 3_100_000),
            _make_row(2027, 36, -200_000, -100_000),  # 貯蓄残高がマイナス
            _make_row(2028, 37, 200_000, 100_000),
        ]
        html = _build_html(_base_scenario(), rows, fp_comment="")
        assert "negative-savings" in html

    def test_pdf_no_negative_savings_class_when_positive(self, simple_rows):
        """全行 savings >= 0 のとき negative-savings クラスが行要素に付与されない"""
        from src.output.pdf_writer import _build_html

        html = _build_html(_base_scenario(), simple_rows, fp_comment="")
        # simple_rows はすべて正の savings なので、クラス属性として付与されない
        # CSS 定義側には "negative-savings" が存在するが、class= 属性には現れない
        assert 'class="negative-savings"' not in html

    def test_pdf_no_spouse_column_when_no_spouse(self, simple_rows):
        """配偶者なしシナリオでは配偶者年齢列が HTML に存在しない（AC-3-7）"""
        from src.output.pdf_writer import _build_html

        html = _build_html(_base_scenario(with_spouse=False), simple_rows, fp_comment="")
        assert "配偶者年齢" not in html

    def test_pdf_spouse_column_present_when_spouse_set(self):
        """配偶者ありシナリオでは配偶者年齢列が存在する（AC-3-8）"""
        from src.output.pdf_writer import _build_html

        rows = [
            _make_row(2026, 35, 100_000, 3_100_000, age_spouse=33),
            _make_row(2027, 36, 200_000, 3_300_000, age_spouse=34),
        ]
        html = _build_html(_base_scenario(with_spouse=True), rows, fp_comment="")
        assert "配偶者年齢" in html

    def test_pdf_fp_comment_empty_label_present(self, simple_rows):
        """FP コメントが空でもラベルが存在する（AC-3-6）"""
        from src.output.pdf_writer import _build_html

        html = _build_html(_base_scenario(), simple_rows, fp_comment="")
        # FP コメント欄の見出しラベルが存在する
        assert "FPコメント" in html or "FP コメント" in html

    def test_pdf_income_model_text_in_html(self, simple_rows):
        """収入モデルの説明テキストが HTML に含まれている（AC-3-4 の前段）"""
        from src.output.pdf_writer import _build_html

        html = _build_html(_base_scenario(), simple_rows, fp_comment="")
        # FLAT モデルのとき「収入一定」等が含まれる
        assert "収入一定" in html or "毎年同額" in html


class TestGeneratePdf:
    """generate_pdf() による PDF バイナリの検証"""

    @pytest.mark.slow
    def test_pdf_starts_with_pdf_signature(self, simple_rows):
        """生成された PDF が %PDF- で始まる（AC-3-2）"""
        from src.output.pdf_writer import generate_pdf

        pdf_bytes = generate_pdf(_base_scenario(), simple_rows)
        assert pdf_bytes[:5] == b"%PDF-"

    @pytest.mark.slow
    def test_pdf_contains_all_cashflow_years(self, simple_rows):
        """PDF に全キャッシュフロー年が含まれる（AC-3-3）

        pdfplumber でテキスト抽出して確認する。
        """
        pdfplumber = pytest.importorskip("pdfplumber")
        import io

        from src.output.pdf_writer import generate_pdf

        pdf_bytes = generate_pdf(_base_scenario(), simple_rows)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        for year in [2026, 2027, 2028, 2029, 2030]:
            assert str(year) in text, f"{year}年が PDF テキストに見つからない"

    @pytest.mark.slow
    def test_pdf_contains_income_model_text(self, simple_rows):
        """PDF に収入モデルの説明テキストが含まれる（AC-3-4）"""
        pdfplumber = pytest.importorskip("pdfplumber")
        import io

        from src.output.pdf_writer import generate_pdf

        pdf_bytes = generate_pdf(_base_scenario(), simple_rows)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        assert "収入一定" in text or "毎年同額" in text
