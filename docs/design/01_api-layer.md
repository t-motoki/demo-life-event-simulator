# 設計: FastAPI バックエンド層

作成日: 2026-04-14

---

## 目的

FP が React + Vite フロントエンドから HTTP 経由でシミュレーションを実行できるようにする。
既存の `simulate()` および `validate()` をそのまま呼び出す薄いアダプター層として `src/api/` を追加する。
ドメイン層（`src/domain/`）および入力層（`src/input/`）は一切変更しない。

---

## CUI の共存（設計方針）

**CUI（`src/main.py`）は削除しない。Web UI と並行して動き続ける状態を維持する。**

### 理由

「同じドメインロジックに、複数の UI を付け替えられること」を設計で証明する。

```
src/main.py   ← CUI エントリポイント（YAML 入力 → Excel 出力）  ※ 変更しない
src/api/      ← Web API エントリポイント（JSON 入力 → JSON 出力）  ※ 今回追加
     ↓              ↓
     └──── src/domain/ （cashflow / loan / education）────┘
                ↑
           ここは一切触らない
```

どちらのエントリポイントも同じ `simulate()` を呼ぶ。UI が変わっても計算結果は同一。

### CUI が動き続けることの検証

既存の 89 件の pytest（ドメインロジック + CUI パス）が変更前と同じ結果で全通過することが証明になる。
`src/main.py` 自体のテストを追加する必要はない（既存テストが代替する）。

---

## 対象ファイル（層ごと）

### 新規作成（`src/api/` 配下）

| ファイル | 役割 |
| -------- | ---- |
| `src/api/__init__.py` | パッケージ宣言（空ファイル） |
| `src/api/main.py` | FastAPI アプリ生成・CORS 設定・ルーター登録・`uvicorn` エントリポイント |
| `src/api/schemas.py` | Pydantic v2 によるリクエスト／レスポンス定義（全スキーマ） |
| `src/api/routes/simulate.py` | `POST /simulate` ハンドラー |
| `src/api/routes/health.py` | `GET /health` ハンドラー |
| `src/api/routes/__init__.py` | パッケージ宣言（空ファイル） |

### 新規作成（テスト）

| ファイル | 役割 |
| -------- | ---- |
| `tests/api/__init__.py` | パッケージ宣言（空ファイル） |
| `tests/api/test_simulate.py` | `POST /simulate` のアクセプタンステスト |
| `tests/api/test_health.py` | `GET /health` のテスト |

### 変更（既存ファイル）

| ファイル | 変更内容 |
| -------- | -------- |
| `requirements.txt` | `fastapi>=0.111`・`uvicorn[standard]>=0.29`・`httpx>=0.27`（テスト用）を追記 |

---

## 依存関係

```
src/api/main.py
    └── src/api/routes/simulate.py
    └── src/api/routes/health.py

src/api/routes/simulate.py
    ├── src/api/schemas.py          # リクエスト→ドメイン変換
    ├── src/domain/models.py        # 変換先の dataclass
    ├── src/input/validator.py      # validate()
    └── src/domain/cashflow.py     # simulate()

src/api/schemas.py
    └── src/domain/models.py        # SchoolType / IncomeModel enum の再利用
```

`domain/` から `api/` への依存は作らない。

---

## Pydantic スキーマ設計（`src/api/schemas.py`）

### 基本方針

- Pydantic v2 の `BaseModel` を使う
- ドメインの dataclass と 1:1 で対応するが、**別クラスとして定義する**（ドメインに Pydantic を混入させない）
- `IncomeModel` / `SchoolType` は `str` ではなく、ドメインの `Enum` をそのまま型ヒントに使う（Pydantic v2 は Enum を自動的に文字列とマッピングする）
- 全フィールドの alias は設けない（JSON キー名 = Python 属性名で統一）

### イベントの discriminated union

`events` 配列の各要素は `type` フィールドの値によって構造が異なる。
Pydantic v2 の `Annotated` + `Literal` + `discriminator` を使って型安全に分岐する。

```
EventRequest = Annotated[
    MarriageEventRequest
    | BirthEventRequest
    | HousingEventRequest
    | EducationEventRequest
    | CareEventRequest
    | OtherExpenseEventRequest,
    Field(discriminator="type")
]
```

各イベントスキーマは `type: Literal["marriage"]` のように固定値 `Literal` で宣言する。
未知の `type` 値が来た場合、Pydantic が自動的に `ValidationError` を送出し、FastAPI が HTTP 422 に変換する。

### クライアント情報

```python
class ClientRequest(BaseModel):
    age: int
    annual_income: int
    income_model: IncomeModel = IncomeModel.FLAT
    raise_rate: float = 0.0
    retirement_age: int = 65
    post_retirement_income: int = 0
    pension_start_age: int = 65
    pension_annual: int = 0
```

### 月間支出

```python
class MonthlyExpensesRequest(BaseModel):
    living: int
    insurance: int
    other: int
```

### シナリオ全体

```python
class SimulateRequest(BaseModel):
    client: ClientRequest
    spouse: ClientRequest | None = None
    savings_initial: int
    end_age: int
    start_year: int = 2025
    monthly_expenses: MonthlyExpensesRequest
    events: list[EventRequest] = []
```

### レスポンス

```python
class CashFlowRowResponse(BaseModel):
    year: int
    age_client: int
    age_spouse: int | None
    income_total: int
    expense_total: int
    loan_deduction: int
    net: int
    savings: int
    events_label: str

# POST /simulate のレスポンス型
SimulateResponse = list[CashFlowRowResponse]
```

### ドメインへの変換

`schemas.py` に変換関数を定義する（ハンドラーの肥大化を防ぐため）。

```python
def to_domain_scenario(req: SimulateRequest) -> Scenario:
    ...

def to_response(rows: list[CashFlowRow]) -> list[CashFlowRowResponse]:
    ...
```

`to_domain_scenario` の内部実装は `yaml_loader.py` の `_parse_client` / `_parse_event` と同じマッピングロジックを踏襲する。ただし yaml_loader の関数を直接呼ばない（インプット形式が異なるため）。

`EducationEvent` の `kindergarten` 等のフィールドは `SchoolType` enum を直接受け取る。Pydantic v2 が `"public"` / `"private"` を自動変換する。

---

## エンドポイント設計

### `POST /simulate`（`src/api/routes/simulate.py`）

```python
@router.post("/simulate", response_model=list[CashFlowRowResponse])
def simulate_endpoint(request: SimulateRequest) -> list[CashFlowRowResponse]:
    scenario = to_domain_scenario(request)
    validate(scenario)          # ValueError → 422 に変換する（下記参照）
    rows = simulate(scenario)
    return to_response(rows)
```

### `GET /health`（`src/api/routes/health.py`）

```python
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

---

## エラーハンドリング設計

### バリデーションエラー（HTTP 422）のルート

| エラー発生源 | 発生タイミング | HTTP ステータス | 変換方法 |
| ------------ | -------------- | --------------- | -------- |
| Pydantic `ValidationError` | リクエスト解析時（型不一致・必須欠落・不明 type） | 422 | FastAPI が自動変換（`detail` は Pydantic 標準形式） |
| `validator.py` の `ValueError` | `validate()` 呼び出し時 | 422 | `HTTPException(status_code=422, detail=str(e))` に変換 |
| ドメインロジック内の予期しない例外 | `simulate()` 呼び出し時 | 500 | `HTTPException(status_code=500, detail=str(e))` に変換 |

`validate()` からの `ValueError` は、ハンドラー内で `try/except ValueError` で捕捉し `HTTPException(422)` を送出する。

Pydantic 由来のエラーと `validator.py` 由来のエラーは `detail` フォーマットが異なる。
仕様書では「すべてのエラーを `{"detail": "..."}`」に統一するとある。
Pydantic 標準の 422 レスポンスは `detail` が配列形式（FastAPI デフォルト）になる。
この差異については以下の判断とする。

**判断**: Pydantic 由来（構造エラー）はそのまま FastAPI のデフォルト形式（`detail` が配列）で返す。`validator.py` 由来のビジネスルールエラーのみ `{"detail": "文字列"}` で返す。
フロントエンドは両形式を受け取れる必要がある。仕様に揺れがある場合は実装開始前にユーザーに確認すること。

---

## CORS 設定（`src/api/main.py`）

`CORSMiddleware` を FastAPI アプリに追加する。

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

将来的に別オリジンを追加する場合は `allow_origins` にリストで追記する。
環境変数で制御する仕組みは今回のスコープ外。

---

## テスト設計

テストは `pytest` + `httpx` の `TestClient`（FastAPI 標準）で実施する。
ドメインオブジェクトを直接生成して期待値を計算し、HTTP レスポンスと突き合わせる。

### `tests/api/test_health.py`

| アクセプタンス基準 | テストケース |
| ------------------ | ------------ |
| AC4: `GET /health` が常に HTTP 200 を返す | `GET /health` → status 200・body `{"status": "ok"}` |

### `tests/api/test_simulate.py`

| アクセプタンス基準 | テストケース | テスト方針 |
| ------------------ | ------------ | ---------- |
| AC1: 正常系でドメインロジックと同一結果 | 最小シナリオ（配偶者なし・イベントなし）を送信し、`simulate()` を直接呼んだ結果と各行を比較 | `simulate()` を直接呼び出した `list[CashFlowRow]` と HTTP レスポンスの JSON 配列を全フィールド比較 |
| AC1: 全イベント種別の正常系 | `marriage` / `birth` / `housing` / `education` / `care` / `other_expense` を各1件含むシナリオで 200 を確認 | フィールド数・type が正しく変換されていることを確認（計算値の詳細は AC1 最小シナリオに委ねる） |
| AC2: validator.py のエラーが 422 になる | 各バリデーション条件（age < 0・savings_initial < 0・down_payment >= price・interest_rate 範囲外・loan_years 範囲外・完済年齢超過・育休率範囲外・育休期間負値）を個別にリクエスト → 422 を確認 | 各条件を独立したパラメータ化テスト（`pytest.mark.parametrize`）で網羅 |
| AC3: 不明な type 値が 422 になる | `events` に `"type": "unknown_type"` を含むリクエスト → 422 | Pydantic discriminated union の自動エラーを確認 |
| AC4: ヘルスチェック | `test_health.py` で担当 | — |
| AC5: 既存テスト無影響 | CI でドメイン側の 89 件と API テストを同時実行し全通過 | テストファイルを追加するだけで既存テストは触らない |
| AC6: CORS 許可 | `Origin: http://localhost:3000` ヘッダー付きで `POST /simulate` → `Access-Control-Allow-Origin` ヘッダーが返ることを確認 | `TestClient` でカスタム Origin ヘッダーを送り、レスポンスヘッダーを検証 |

### 共通テストフィクスチャ

`tests/api/conftest.py`（新規）に以下を定義する。

```python
@pytest.fixture
def client() -> TestClient:
    from src.api.main import app
    return TestClient(app)

@pytest.fixture
def minimal_request() -> dict:
    """バリデーション通過・イベントなしの最小シナリオ JSON"""
    ...
```

最小シナリオは `tests/input/test_validator.py` の `_valid_scenario()` と同じ値を JSON 形式で定義する（コードの重複だが、テスト層の独立性を優先する）。

---

## 設計判断の根拠

### `schemas.py` にドメインモデルと別のクラスを定義する理由

`domain/models.py` の dataclass に `BaseModel` を継承させる方法もあるが、それはドメインを Pydantic に依存させる。
ドメイン層は外部ライブラリに依存しないという原則に反するため採用しない。
変換関数（`to_domain_scenario`）のコストは受け入れ可能。

### `yaml_loader.py` の `_parse_event` を再利用しない理由

`yaml_loader.py` の `_parse_event` は `dict[str, Any]` を受け取る設計で、Pydantic スキーマを前提としていない。
API 層では Pydantic によって型検証済みのオブジェクトを受け取るため、`dict` 経由の変換を経由する必要がない。
直接 Pydantic スキーマ → ドメイン dataclass に変換することでコードが明確になる。

### `routes/` をサブディレクトリに分ける理由

今回は 2 エンドポイントのみだが、将来 Excel ダウンロードや保存系エンドポイントが追加された場合に `main.py` が肥大化するのを防ぐ。
エンドポイントごとにファイルを分けておく構造は、追加コストがほぼゼロで拡張耐性を持つ。

### 選ばなかった選択肢

| 選択肢 | 不採用理由 |
| ------ | ---------- |
| `domain/models.py` を Pydantic BaseModel に変更 | ドメインを Pydantic に依存させる。既存の 89 件のテストに影響する可能性がある |
| `yaml_loader.py` を API 層でも流用 | dict 経由の変換は型安全でない。API 層と YAML 入力で変換ロジックが混在する |
| FastAPI の `response_model` に dataclass を直接使う | FastAPI は dataclass を直接 response_model に使えるが、`Optional` / `None` の扱いで意図しないシリアライズが起きる可能性がある。Pydantic モデルで明示的に定義する方が安全 |
| エラー形式を完全統一（Pydantic 由来も文字列 detail に変換） | `exception_handler` を追加すれば可能だが、Pydantic の詳細なフィールドエラー情報が消える。フロントエンドへの影響を確認してから判断する |

---

## 実装者へのノート

1. **Pydantic v2 と v1 の API 差異に注意**: `Field(discriminator="type")` の書き方は v2 での記法。`requirements.txt` に `fastapi>=0.111` を追加すれば Pydantic v2 が依存として入る。

2. **`EducationEvent` の `SchoolType` フィールド**: JSON では `"public"` / `"private"` の文字列が来る。Pydantic v2 は Enum の value で自動変換するので追加実装不要。

3. **`to_domain_scenario` での `IncomeModel` 変換**: Pydantic スキーマが `IncomeModel` enum を受け取るので、変換時は `req.client.income_model`（すでに `IncomeModel` 型）を dataclass にそのまま渡せる。

4. **`simulate()` の戻り値の `int` 変換**: `CashFlowRow` の数値フィールドは `int` だが、`simulate()` 内部で `int()` キャストしているので API 層での追加変換は不要。

5. **テストの `TestClient` と CORS**: FastAPI の `TestClient` は `httpx` ベース。CORS ヘッダーの検証は `response.headers["access-control-allow-origin"]` で確認する。preflight（OPTIONS）の確認も AC6 のテストに含めることを推奨する。

6. **`validate()` は `ValueError` を 1 件だけ raise する**: 複数エラーを一括返却しない設計。エラーレスポンスも単一 `detail` 文字列で問題ない。

7. **起動コマンド**: `uvicorn src.api.main:app --reload`。`src/` を Python パッケージのルートとして扱うため、プロジェクトルート（`life-event-simulator/`）で実行する。

8. **Pydantic discriminated union の未知 type**: 仕様では `type` が未知なら HTTP 422。Pydantic の `discriminator` が機能する前提だが、`Annotated` + `Field(discriminator=...)` を正しく設定しないとランタイムエラーになる。実装後に `"type": "invalid"` を含むリクエストで動作確認すること。
