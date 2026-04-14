# API 振る舞い仕様 — ライフイベント家計シミュレーター FastAPI 層

作成日: 2026-04-14

---

## 目的

FP（ファイナンシャルプランナー）が Next.js フロントエンドからシミュレーションを実行できるようにする。
既存のドメインロジック（`simulate()` 関数）は変更せず、HTTP 経由で呼び出す REST API 層を追加する。

---

## 対象エンドポイント

| エンドポイント | メソッド | 目的 |
| -------------- | -------- | ---- |
| `POST /simulate` | POST | シナリオを受け取り、年次キャッシュフロー一覧を返す |
| `GET /health` | GET | サーバーが起動していることを確認する（フロントエンド疎通確認用） |

---

## エンドポイント詳細

### `POST /simulate`

#### 目的

FP がフォームに入力したシナリオ情報（クライアント情報・月間支出・ライフイベント）を受け取り、
年次キャッシュフロー一覧を返す。

受け取ったリクエストは既存の `validate()` でバリデーションしてから `simulate()` に渡す。
ドメインロジックの計算モデルはそのまま使う。新しい計算モデルをこの層に追加しない。

#### 入力の概要

リクエストボディ（JSON）で以下を受け取る。

**クライアント情報（本人・配偶者）**

| フィールド | 型 | 内容 |
| ---------- | -- | ---- |
| `age` | 整数 | 現在年齢 |
| `annual_income` | 整数 | 税引後年収（円） |
| `income_model` | 文字列 | `"flat"` / `"raise_rate"` / `"post_retirement"` |
| `raise_rate` | 小数 | 昇給率（income_model が raise_rate のときに使用） |
| `retirement_age` | 整数 | 定年年齢 |
| `post_retirement_income` | 整数 | 定年後年収（円） |
| `pension_start_age` | 整数 | 年金受給開始年齢 |
| `pension_annual` | 整数 | 年金額（円・FP手入力） |

配偶者は省略可能（`null`）。

**シナリオ全体**

| フィールド | 型 | 内容 |
| ---------- | -- | ---- |
| `client` | オブジェクト | 本人情報 |
| `spouse` | オブジェクト or null | 配偶者情報 |
| `savings_initial` | 整数 | 現在の貯蓄残高（円） |
| `end_age` | 整数 | シミュレーション終了年齢 |
| `start_year` | 整数 | シミュレーション開始年（西暦） |
| `monthly_expenses` | オブジェクト | 月間支出（生活費・保険・その他） |
| `events` | 配列 | ライフイベント一覧 |

**月間支出**

| フィールド | 型 | 内容 |
| ---------- | -- | ---- |
| `living` | 整数 | 月間生活費（円） |
| `insurance` | 整数 | 保険料（円） |
| `other` | 整数 | その他固定費（円） |

**ライフイベント**

各イベントは `type` フィールドでイベント種別を識別する。

| type 値 | 対応するドメインクラス | 追加フィールド |
| ------- | ---------------------- | -------------- |
| `marriage` | `MarriageEvent` | `year`, `cost` |
| `birth` | `BirthEvent` | `year`, `child_count`, `client_maternity_rate`, `client_maternity_years`, `spouse_maternity_rate`, `spouse_maternity_years` |
| `housing` | `HousingEvent` | `year`, `price`, `down_payment`, `loan_years`, `interest_rate`, `use_tax_deduction` |
| `education` | `EducationEvent` | `year`, `child_birth_year`, `kindergarten`, `elementary`, `junior_high`, `high_school`, `university` |
| `care` | `CareEvent` | `year`, `duration_years`, `monthly_cost` |
| `other_expense` | `OtherExpenseEvent` | `year`, `amount`, `name` |

#### 出力の概要

HTTP 200 のとき、年次キャッシュフロー一覧を JSON 配列で返す。
配列の各要素は `CashFlowRow` に対応する。

| フィールド | 型 | 内容 |
| ---------- | -- | ---- |
| `year` | 整数 | 西暦年 |
| `age_client` | 整数 | 本人年齢 |
| `age_spouse` | 整数 or null | 配偶者年齢 |
| `income_total` | 整数 | 収入合計（円） |
| `expense_total` | 整数 | 支出合計（円） |
| `loan_deduction` | 整数 | 住宅ローン控除額（円） |
| `net` | 整数 | 年間収支（円） |
| `savings` | 整数 | 貯蓄残高（円） |
| `events_label` | 文字列 | その年のイベント名（複数なら " / " 区切り） |

---

### `GET /health`

#### 目的

フロントエンドがバックエンドの起動を確認するための疎通エンドポイント。
シミュレーションとは無関係。認証なし・副作用なし。

#### 出力の概要

HTTP 200 で固定の JSON を返す。

```json
{"status": "ok"}
```

---

## アクセプタンス基準

以下の状態になれば「完成」と見なす。

1. **正常系**: 有効なシナリオを `POST /simulate` に送ると、既存のドメインロジックと同一のキャッシュフロー一覧が JSON で返ってくる
2. **バリデーション委譲**: `validator.py` が検出するすべてのエラー条件（年齢範囲外・貯蓄マイナス・頭金 >= 物件価格など）が HTTP 422 として返ってくる
3. **不正な type 値**: イベントの `type` に未知の値が来たら HTTP 422 が返ってくる
4. **疎通確認**: `GET /health` が常に HTTP 200 を返す
5. **既存テストへの無影響**: 既存の 89 件の pytest が変更前と同じ結果で通る（ドメインロジックを変更していないことの証明）
6. **CORS 許可**: Next.js のローカル開発サーバー（`http://localhost:3000`）からのリクエストが CORS エラーなく届く

---

## 境界値・異常系の仕様

### バリデーションエラー（HTTP 422）

以下の条件はすべて HTTP 422 Unprocessable Entity で返す。
エラーレスポンスには `detail` フィールドに人間が読めるメッセージを含める。

#### クライアント情報

| 条件 | エラー内容 |
| ---- | ---------- |
| `client.age` が 0〜100 の範囲外 | 本人の年齢が不正 |
| `spouse.age` が 0〜100 の範囲外 | 配偶者の年齢が不正 |
| `savings_initial` が負値 | 貯蓄初期残高が負 |
| `end_age` が `client.age` 以下 | 終了年齢が現在年齢以下 |

#### 住宅イベント

| 条件 | エラー内容 |
| ---- | ---------- |
| `down_payment >= price` | 頭金が物件価格以上 |
| `interest_rate` が 0〜1 の範囲外 | 金利が不正 |
| `loan_years` が 1〜50 の範囲外 | ローン年数が不正 |
| ローン完済年齢 >= `client.retirement_age` | 定年前に完済できない |

#### 育休イベント

| 条件 | エラー内容 |
| ---- | ---------- |
| `client_maternity_rate` が 0.0〜1.0 の範囲外 | 本人育休収入率が不正 |
| `spouse_maternity_rate` が 0.0〜1.0 の範囲外 | 配偶者育休収入率が不正 |
| `client_maternity_years` が負値 | 本人育休期間が負 |
| `spouse_maternity_years` が負値 | 配偶者育休期間が負 |

#### リクエスト構造エラー

| 条件 | エラー内容 |
| ---- | ---------- |
| `type` フィールドが未知の値 | 不明なイベント種別 |
| 必須フィールドが欠落 | フィールド欠落 |
| 型が不一致（文字列のところに整数など） | 型エラー |
| リクエストボディが空 | ボディ欠落 |

### サーバーエラー（HTTP 500）

ドメインロジック内で予期しない例外が発生した場合は HTTP 500 で返す。
`detail` にエラーメッセージを含める。エラーはサーバーログにも出力する。

### エラーレスポンスの形

すべてのエラーレスポンスは以下の形式に統一する。

```json
{
  "detail": "エラーの説明（日本語）"
}
```

バリデーションエラーが複数ある場合も、最初に検出したエラーを 1 件返す。
（`validator.py` が `ValueError` を 1 件ずつ raise する現在の仕様に合わせる）

---

## スコープ外（この仕様では定義しない）

- 認証・認可（ローカル完結のため不要）
- 複数シナリオの保存・比較
- Excel ダウンロードエンドポイント
- シナリオの CRUD（保存・取得・削除）
- レート制限
