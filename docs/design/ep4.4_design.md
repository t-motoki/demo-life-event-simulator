# 設計: ep4.4「根拠付き出力 — クライアントに渡せる形へ」

作成日: 2026-05-10

---

## 概要

既存のシミュレーション結果に「前提条件・注釈」シート（Excel）、FP コメント自動生成（Claude API）、PDF ダウンロード（WeasyPrint）の 3 機能を加える。フロントエンドにはダウンロードボタンを追加する。既存の `write_excel()` と `POST /simulate` には最小限の変更しか加えない。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 理由 |
| -------- | -------- | ---- |
| `src/domain/cashflow_analysis.py` | **新規** | 貯蓄最低値の特定・赤字期間の検出をドメイン計算として分離 |
| `src/output/excel_writer.py` | **変更** | `write_excel()` に `fp_comment`・`fp_name` 引数を追加し、3枚目シートを生成する内部関数 `_write_notes_sheet()` を追加 |
| `src/output/comment_generator.py` | **新規** | Claude API を呼び出して FP コメントを生成する。`anthropic` パッケージへの依存はこのファイルに閉じ込める |
| `src/output/pdf_writer.py` | **新規** | Scenario + CashFlowRow 一覧 + FP コメントを受け取り、WeasyPrint で PDF バイナリを生成する |
| `src/output/pdf_config.py` | **新規** | PDF 生成で参照するフォントパスなどの設定値を一箇所に集約する（ハードコードをここに限定する） |
| `src/api/schemas.py` | **変更** | `GenerateCommentRequest`・`GenerateCommentResponse`・`DownloadPdfRequest` スキーマを追加 |
| `src/api/routes/comment.py` | **新規** | `POST /generate-comment` エンドポイント |
| `src/api/routes/pdf.py` | **新規** | `POST /download-pdf` エンドポイント |
| `src/api/main.py` | **変更** | 新ルーターを `include_router` で追加する |
| `frontend/src/api/types.ts` | **変更** | `GenerateCommentRequest`・`GenerateCommentResponse`・PDF エラー型を追加 |
| `frontend/src/api/client.ts` | **変更** | `postGenerateComment()`・`postDownloadPdf()` 関数を追加 |
| `frontend/src/components/ResultSection/ResultSection.tsx` | **変更** | PDF ダウンロードボタンと状態管理を追加 |
| `requirements.txt` | **変更** | `weasyprint`・`anthropic` を追加 |
| `tests/domain/test_cashflow_analysis.py` | **新規** | `cashflow_analysis.py` のユニットテスト |
| `tests/output/test_excel_writer.py` | **変更** | AC-1-x に対応するテストを追加 |
| `tests/output/test_comment_generator.py` | **新規** | AC-2-x に対応するテスト（Claude API はモック） |
| `tests/output/test_pdf_writer.py` | **新規** | AC-3-1〜AC-3-9 に対応するテスト（WeasyPrint の実呼び出し） |
| `tests/api/test_comment.py` | **新規** | AC-2-6〜AC-2-8 に対応するエンドポイントテスト |
| `tests/api/test_pdf.py` | **新規** | AC-3-10・AC-3-11 に対応するエンドポイントテスト |

---

## データモデル

### 新規: `src/domain/cashflow_analysis.py` の値オブジェクト

```python
from dataclasses import dataclass
from typing import Optional

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
    end_year: int   # 単発の場合は start_year == end_year

@dataclass(frozen=True)
class CashFlowSummary:
    """Excel 第3シートおよび PDF の注目ポイント生成に使う分析結果"""
    savings_low: SavingsLow
    deficit_periods: list[DeficitPeriod]  # 空リスト = 赤字なし
```

---

## インターフェース定義

### 1. `src/domain/cashflow_analysis.py`

```python
def analyze(rows: list[CashFlowRow]) -> CashFlowSummary:
    """キャッシュフロー一覧を分析して貯蓄最低値と赤字期間を返す。
    rows が空の場合は ValueError を送出する。"""
```

実装ノート:
- 貯蓄最低値は `min(rows, key=lambda r: r.savings)` で特定する
- 赤字期間は `net < 0` の行を走査し、連続する年をひとつの `DeficitPeriod` にまとめる
- `age_client` が `None` になることはないため `int` として扱ってよい

---

### 2. `src/output/excel_writer.py` への追加

```python
def write_excel(
    scenario: Scenario,
    rows: list[CashFlowRow],
    output_dir: str | Path = ".",
    fp_comment: str = "",        # 追加（デフォルト空文字で後方互換）
    fp_name: str = "",           # 追加（デフォルト空文字で後方互換）
) -> Path:
    ...
```

内部関数（非公開）:

```python
def _write_notes_sheet(
    ws,
    scenario: Scenario,
    rows: list[CashFlowRow],
    fp_comment: str,
    fp_name: str,
) -> None:
    """「前提条件・注釈」シートに書き込む。
    analyze() を内部で呼び出して貯蓄最低値・赤字期間を取得する。"""
```

---

### 3. `src/output/comment_generator.py`

```python
def generate_comment(
    scenario: Scenario,
    rows: list[CashFlowRow],
    max_chars: int = 200,
) -> str:
    """Claude API を呼び出して FP コメントを生成する。
    返却文字列は max_chars 以内であることを呼び出し元に保証する。

    Raises:
        CommentGenerationError: Claude API が応答しないか例外を送出した場合
    """

class CommentGenerationError(Exception):
    """Claude API 呼び出し失敗を表す例外"""
```

実装ノート:
- `anthropic.Anthropic()` のインスタンス生成はこのモジュールのトップレベルに置く（関数呼び出しのたびに生成しない）
- API キーは環境変数 `ANTHROPIC_API_KEY` から自動的に読まれる（anthropic パッケージのデフォルト動作）
- 生成テキストが `max_chars` を超えた場合は末尾を切り捨てて返す。截断が発生した場合は `logger.warning` を出力する
- プロンプトには `analyze()` の結果を構造化テキストとして埋め込む（FP 向けのコンテキストを最小限に絞ること）

---

### 4. `src/output/pdf_config.py`

```python
# PDF 生成設定（フォントパスは WSL2 + Windows 前提）
KLEE_ONE_FONT_PATH = "/mnt/c/Windows/Fonts/KleeOne-Regular.ttf"
KLEE_ONE_FONT_FAMILY = "Klee One"
```

フォントパスをここに一元化する。`pdf_writer.py` はこの定数を参照する。テスト時にパスを差し替えたい場合は `pdf_config.py` の定数を monkeypatch する。

---

### 5. `src/output/pdf_writer.py`

```python
def generate_pdf(
    scenario: Scenario,
    rows: list[CashFlowRow],
    fp_comment: str = "",
) -> bytes:
    """HTML テンプレートを組み立て WeasyPrint で PDF バイナリを生成して返す。

    Returns:
        PDF バイナリ（%PDF- で始まる）

    Raises:
        PdfGenerationError: WeasyPrint が例外を送出した場合
    """

class PdfGenerationError(Exception):
    """PDF 生成失敗を表す例外"""
```

実装ノート:
- HTML テンプレートは文字列として `pdf_writer.py` 内に `_build_html()` として定義する。外部ファイル（Jinja2 テンプレート等）は導入しない（依存を増やさない）
- `@font-face` の `src: url(...)` には `pdf_config.KLEE_ONE_FONT_PATH` を参照させる
- `savings < 0` の行には CSS クラス `negative-savings` を付与し、赤背景を適用する（AC-3-9 対応）
- `spouse` が `None` のシナリオでは配偶者年齢列の `<th>/<td>` を HTML に含めない（AC-3-7・AC-3-8 対応）
- PDF の `Content-Disposition` ファイル名は `cf_simulation_YYYYMMDD.pdf`（実行日）

---

### 6. API スキーマ追加（`src/api/schemas.py`）

```python
class GenerateCommentRequest(BaseModel):
    scenario: SimulateRequest
    rows: list[CashFlowRowResponse]

class GenerateCommentResponse(BaseModel):
    comment: str

class DownloadPdfRequest(BaseModel):
    scenario: SimulateRequest
    rows: list[CashFlowRowResponse]
    fp_comment: str = ""
```

変換ノート:
- `GenerateCommentRequest` / `DownloadPdfRequest` の `scenario` フィールドは既存の `SimulateRequest` を再利用する。`to_domain_scenario()` で `Scenario` に変換できるため、新しい変換関数を書かない
- `rows` は既存の `CashFlowRowResponse` を再利用する。`CashFlowRow` へのドメイン逆変換関数 `to_domain_rows()` を `schemas.py` に追加する

```python
def to_domain_rows(rows: list[CashFlowRowResponse]) -> list[CashFlowRow]:
    """CashFlowRowResponse 一覧をドメインの CashFlowRow 一覧に変換する"""
```

---

### 7. `src/api/routes/comment.py`

```python
router = APIRouter()

@router.post("/generate-comment", response_model=GenerateCommentResponse)
def generate_comment_endpoint(request: GenerateCommentRequest) -> GenerateCommentResponse:
    ...
```

エラーハンドリング:
- `CommentGenerationError` → HTTP 503（Claude API 障害）
- それ以外の例外 → HTTP 500

---

### 8. `src/api/routes/pdf.py`

```python
router = APIRouter()

@router.post("/download-pdf")
def download_pdf_endpoint(request: DownloadPdfRequest) -> Response:
    ...
    # Response(content=pdf_bytes, media_type="application/pdf",
    #          headers={"Content-Disposition": f'attachment; filename="cf_simulation_{today}.pdf"'})
```

エラーハンドリング:
- `PdfGenerationError` → HTTP 500
- Pydantic ValidationError は FastAPI が自動で 422 に変換する（AC-3-10 対応）

---

### 9. フロントエンド型追加（`frontend/src/api/types.ts`）

```typescript
export interface DownloadPdfRequestBody {
  scenario: SimulateRequestBody;
  rows: CashFlowRowResponse[];
  fp_comment: string;
}

export interface GenerateCommentRequestBody {
  scenario: SimulateRequestBody;
  rows: CashFlowRowResponse[];
}

export interface GenerateCommentResponse {
  comment: string;
}

// SimulateError に 'pdf' kind を追加する
export type DownloadError =
  | { kind: 'network' }
  | { kind: 'timeout' }
  | { kind: 'server' };
```

---

### 10. フロントエンド API 関数（`frontend/src/api/client.ts`）

```typescript
export async function postDownloadPdf(
  body: DownloadPdfRequestBody,
  timeoutMs?: number,
): Promise<Blob>

export async function postGenerateComment(
  body: GenerateCommentRequestBody,
  timeoutMs?: number,
): Promise<GenerateCommentResponse>
```

---

## 依存関係

```
[domain/models.py]         ← 変更なし
[domain/cashflow_analysis.py]
  依存: domain/models.py のみ（外部ライブラリ依存なし）

[output/pdf_config.py]
  依存: なし（純粋な定数ファイル）

[output/excel_writer.py]
  依存（追加分): domain/cashflow_analysis.py

[output/comment_generator.py]
  依存: domain/models.py, domain/cashflow_analysis.py, anthropic

[output/pdf_writer.py]
  依存: domain/models.py, domain/cashflow_analysis.py, output/pdf_config.py, weasyprint

[api/schemas.py]
  依存（追加分): 既存 SimulateRequest, CashFlowRowResponse（自己参照）

[api/routes/comment.py]
  依存: api/schemas.py, output/comment_generator.py, domain/models.py

[api/routes/pdf.py]
  依存: api/schemas.py, output/pdf_writer.py, domain/models.py
```

禁止している依存:
- `api/routes/*.py` から `anthropic` を直接 import することは禁止
- `output/*.py` が `api/schemas.py` に依存することは禁止
- `domain/cashflow_analysis.py` が `output/` や `api/` に依存することは禁止

---

## requirements.txt への追加

```
weasyprint>=62.0
anthropic>=0.25
```

追加理由:
- `weasyprint`: HTML→PDF 変換。インストール時に `pango`・`cairo` が必要（WSL2 では `apt install python3-weasyprint` または `pip install weasyprint` で依存が解決される）
- `anthropic`: Claude API 公式 Python SDK。`ANTHROPIC_API_KEY` 環境変数を参照する

追加しないもの:
- Jinja2: HTML テンプレートを Python 文字列で組み立てることで依存を排除する
- pydantic-settings: 設定値は `pdf_config.py` の定数で十分。設定ファイル管理の複雑さを持ち込まない

---

## テスト設計（アクセプタンス基準との対応）

### `tests/domain/test_cashflow_analysis.py`（新規）

AC との直接対応はないが、後続の Excel・PDF テストが依存するドメイン計算のユニットテスト。

| テスト関数名 | 検証内容 |
| ------------ | -------- |
| `test_analyze_returns_savings_low_year` | 最小 savings の年・年齢・金額が正しく返る |
| `test_analyze_savings_low_monotonic_increase` | 全行 net >= 0 のとき最初の行が savings_low になる（AC-1-11 の計算根拠） |
| `test_analyze_no_deficit_when_all_net_positive` | `deficit_periods` が空リストになる |
| `test_analyze_detects_single_year_deficit` | net < 0 が 1 年の場合 start_year == end_year |
| `test_analyze_merges_consecutive_deficit_years` | 連続する赤字年がひとつの DeficitPeriod にまとまる |
| `test_analyze_raises_on_empty_rows` | rows が空のとき ValueError |

---

### `tests/output/test_excel_writer.py`（追加）

| テスト関数名 | 対応 AC |
| ------------ | ------- |
| `test_notes_sheet_exists_as_third_sheet` | AC-1-1 |
| `test_notes_sheet_creation_date` | AC-1-2 |
| `test_notes_sheet_fp_name_default_empty` | AC-1-3 |
| `test_notes_sheet_income_model_flat_text` | AC-1-4 |
| `test_notes_sheet_income_model_raise_rate_text` | AC-1-5 |
| `test_notes_sheet_income_model_post_retirement_text` | AC-1-6 |
| `test_notes_sheet_inflation_assumption_text` | AC-1-7 |
| `test_notes_sheet_housing_interest_rate_with_event` | AC-1-8 |
| `test_notes_sheet_no_housing_interest_rate_text` | AC-1-9 |
| `test_notes_sheet_savings_low_values` | AC-1-10 |
| `test_notes_sheet_savings_low_monotonic` | AC-1-11 |
| `test_notes_sheet_deficit_period_listed` | AC-1-12 |
| `test_notes_sheet_no_deficit_text_when_all_positive` | AC-1-13 |
| `test_notes_sheet_fp_comment_font_is_klee_one` | AC-1-14 |
| `test_notes_sheet_fp_comment_empty_is_blank` | AC-1-15 |

---

### `tests/output/test_comment_generator.py`（新規）

Claude API は `unittest.mock.patch` でモックする。実際の API 呼び出しは行わない。

| テスト関数名 | 対応 AC |
| ------------ | ------- |
| `test_generate_comment_returns_nonempty_string` | AC-2-1 |
| `test_generate_comment_within_200_chars` | AC-2-2 |
| `test_generate_comment_mentions_deficit_year` | AC-2-3 |
| `test_generate_comment_mentions_savings_low` | AC-2-4 |
| `test_generate_comment_no_negative_words_when_no_deficit` | AC-2-5 |
| `test_generate_comment_truncates_if_over_limit` | 200 字超えの返却値が切り捨てられること |
| `test_generate_comment_raises_on_api_error` | CommentGenerationError が送出されること |

AC-2-3〜AC-2-5 は Claude API の返却テキストを fixture で固定してテストする（非決定的な API 出力に依存しない）。

---

### `tests/api/test_comment.py`（新規）

| テスト関数名 | 対応 AC |
| ------------ | ------- |
| `test_generate_comment_returns_200_with_comment_field` | AC-2-6 |
| `test_generate_comment_response_shape` | AC-2-7 |
| `test_generate_comment_returns_503_on_api_failure` | AC-2-8 |

`comment_generator.generate_comment` を `pytest-mock` でパッチして Claude API を呼び出さずにテストする。

---

### `tests/output/test_pdf_writer.py`（新規）

WeasyPrint を実際に呼び出す（モックしない）。生成時間が長い場合は `@pytest.mark.slow` マーカーを付ける。PDF テキスト抽出には `pdfplumber` を使う（テスト専用依存として `requirements-dev.txt` に分離してもよい）。

| テスト関数名 | 対応 AC |
| ------------ | ------- |
| `test_pdf_starts_with_pdf_signature` | AC-3-2 |
| `test_pdf_contains_all_cashflow_years` | AC-3-3 |
| `test_pdf_contains_income_model_text` | AC-3-4 |
| `test_pdf_klee_one_in_css` | AC-3-5（生成 HTML に `font-family: "Klee One"` があることを検証） |
| `test_pdf_fp_comment_empty_label_present` | AC-3-6 |
| `test_pdf_no_spouse_column_when_no_spouse` | AC-3-7 |
| `test_pdf_spouse_column_present_when_spouse_set` | AC-3-8 |
| `test_pdf_negative_savings_row_has_css_class` | AC-3-9（生成 HTML に `.negative-savings` が付いていることを検証） |

AC-3-5 と AC-3-9 は WeasyPrint に渡す HTML 文字列（`_build_html()` の返却値）を直接テストする形でもよい。PDF テキスト抽出でフォントや CSS クラスを検証するのは困難なため、HTML 検証に切り替えることを推奨する。

---

### `tests/api/test_pdf.py`（新規）

| テスト関数名 | 対応 AC |
| ------------ | ------- |
| `test_download_pdf_returns_200_with_pdf_content_type` | AC-3-1 |
| `test_download_pdf_content_disposition_header` | AC-3-11 |
| `test_download_pdf_returns_422_on_invalid_body` | AC-3-10 |

`pdf_writer.generate_pdf` をモックして PDF バイナリ（`b"%PDF-1.4 mock"`）を返す。WeasyPrint の実行はこのテストでは不要。

---

### フロントエンドテスト（AC-4-x）

React Testing Library（または Playwright）を使う。本設計書ではファイル配置のみ示す。テストコードは frontend の engineer に委ねる。

| テストファイル | 対応 AC |
| -------------- | ------- |
| `frontend/src/components/ResultSection/ResultSection.test.tsx` | AC-4-1〜AC-4-6 |

---

## 設計判断の根拠

### 判断1: ドメイン計算の分離（`cashflow_analysis.py`）

「貯蓄最低値の特定」「赤字期間の検出」は純粋なビジネスルールであり、Excel・PDF どちらの出力にも共通して使われる。これを `excel_writer.py` 内に書いてしまうと `pdf_writer.py` が重複実装するか、`pdf_writer.py` が `excel_writer.py` に依存するという不健全な構造になる。独立したドメインモジュール `cashflow_analysis.py` として切り出すことで両者が同じ計算結果を参照できる。

選ばなかった選択肢: `pdf_writer.py` から直接計算する → Excel と PDF で計算が乖離するリスクがある。

---

### 判断2: フォントパスを `pdf_config.py` に集約

WeasyPrint に渡す `@font-face` の `src: url(...)` にハードコードした絶対パスを書くと、`pdf_writer.py` を読むだけでは設定場所がわからなくなる。`pdf_config.py` に定数として一元化することで、環境が変わった際に一箇所だけ変更すればよい状態を保つ。テストでの差し替えも `monkeypatch` で容易に行える。

選ばなかった選択肢: 環境変数から読む → 起動時の設定管理が複雑になる。今回の対象環境は WSL2 + Windows に固定されているため過剰。

---

### 判断3: HTML テンプレートを外部ファイルにしない

Jinja2 等のテンプレートエンジンを追加すると依存が増え、テンプレートファイルの配置パス管理が生まれる。現時点で PDF のレイアウトは 1 種類のみであり、Python 文字列での構築で十分読みやすい。2 種類以上の PDF テンプレートが必要になった段階でテンプレートエンジンの導入を検討する。

---

### 判断4: `rows` を API リクエストに含める（再計算しない）

`POST /download-pdf` と `POST /generate-comment` のリクエストに `rows` を含めることで、バックエンドは再度 `simulate()` を呼ぶ必要がない。フロントエンドがすでに保持している計算結果をそのまま渡す設計にする。これにより API の実装がシンプルになり、「フロントに表示された結果と PDF の内容が一致しない」バグを防ぐことができる。

選ばなかった選択肢: シナリオのみ送ってバックエンドで再計算する → API が二重に計算する。エラー時のデバッグが複雑になる。

---

### 判断5: `SimulateRequest` を再利用して `DownloadPdfRequest` の scenario フィールドに使う

`DownloadPdfRequest` のために別の scenario スキーマを定義すると、フィールド定義の重複とメンテナンスコストが生まれる。既存の `SimulateRequest` を型として再利用し、`to_domain_scenario()` でドメインオブジェクトに変換するパスをそのまま使う。

---

## 実装者へのノート

### `_write_notes_sheet()` の出力レイアウト

シートの行構成（行番号は目安）:

```
1行目: 作成日ラベル / 作成日値
2行目: FP名ラベル / FP名値
3行目: （空白）
4行目: 【前提条件】見出し
5行目: 収入モデルラベル / 説明テキスト
6行目: インフレ率ラベル / 「0%（固定）」
7行目: 運用利回りラベル / 「0%（固定）」
8行目: 住宅ローン金利ラベル / 金利値（HousingEvent あり時のみ）
9行目: （空白）
10行目: 【注目ポイント】見出し
11行目: 貯蓄最低値ラベル / 「YYYY年（XX歳）・X,XXX,XXX円」
12行目以降: 赤字期間ラベル / 「YYYY〜YYYY年」（各行）または空
N行目以降: FPコメント見出し
N+1行目: FPコメント本文（Klee One フォント）
```

AC-1-14 の検証対象は「FPコメント本文のセル」のフォント名。`openpyxl.styles.Font(name="Klee One")` で設定する。

### Claude API のプロンプト設計指針

プロンプトに含める情報:
- 貯蓄最低値（年・年齢・金額）
- 赤字期間（あれば）
- シミュレーション期間（開始年〜終了年）
- 収入モデル

含めない情報:
- 生の `rows` 全行データ（トークン節約）
- クライアントの個人情報

プロンプトは日本語で記述し、200 字以内の FP 向けコメントを 1 段落で返すよう指示する。

### `to_domain_rows()` の実装

`CashFlowRowResponse` → `CashFlowRow` の逆変換。`CashFlowRow` は dataclass であり、フィールドは 1:1 対応しているため、素直にマッピングすればよい。

### WeasyPrint の実行環境確認

WSL2 で WeasyPrint を動かすには `libpango-1.0-0` が必要。`requirements.txt` にコメントとして以下を残しておくこと:

```
# WeasyPrint を WSL2 で使う場合: sudo apt install -y libpango-1.0-0 libcairo2
```

### フロントエンド状態管理の方針

`ResultSection.tsx` に以下の状態を追加する:

```typescript
const [isDownloading, setIsDownloading] = useState(false);
const [downloadError, setDownloadError] = useState<string | null>(null);
```

ダウンロード成功時は `setDownloadError(null)` で前回のエラーをクリアする。シミュレーション再実行時（`result` が更新されたとき）も同様にクリアする（AC-4-6 対応）。
