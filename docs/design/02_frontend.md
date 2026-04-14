# 設計: React + Vite フロントエンド層

作成日: 2026-04-14

---

## 概要

FP が 1 画面でシナリオを入力し、`POST /simulate` を呼び出して年次キャッシュフロー一覧を確認するシングルページアプリケーションを `frontend/` ディレクトリに構築する。
ep4.4 での Electron デスクトップアプリ化を前提に設計し、`HashRouter`・環境変数 API URL・Node.js API 非使用を設計の根幹に組み込む。

---

## Electron 互換制約（設計の根幹）

| 制約 | 理由 | 実現方法 |
|------|------|----------|
| `HashRouter` を使う | `file://` プロトコルでは `BrowserRouter` のパス解決が機能しない | `react-router-dom` の `HashRouter` を採用。`BrowserRouter` は使わない |
| API ベース URL を環境変数化 | Electron では別プロセスで起動するバックエンドの URL が変わりうる | `import.meta.env.VITE_API_URL`（デフォルト `http://localhost:8000`）で全 `fetch` のベース URL を統一 |
| Node.js 固有 API を React コンポーネントに混入しない | Electron renderer プロセスはデフォルトで Node.js API を使えない | `fs`・`path`・`process` 等を直接呼ばない。Electron との IPC は `preload.ts` 経由とし、それは ep4.4 のスコープ |

---

## プロジェクト構成

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── package.json
├── .env.development          # VITE_API_URL=http://localhost:8000
├── .env.production           # 本番用（Electron ビルド時に上書き）
│
└── src/
    ├── main.tsx              # ReactDOM.createRoot エントリポイント
    ├── App.tsx               # HashRouter + ルーティング（現時点では / のみ）
    │
    ├── api/
    │   ├── client.ts         # fetch ラッパー（VITE_API_URL 参照・タイムアウト・エラー変換）
    │   └── types.ts          # API リクエスト・レスポンスの TypeScript 型定義
    │
    ├── components/
    │   ├── ClientSection/
    │   │   ├── ClientSection.tsx     # 本人・配偶者フォームをまとめるセクション
    │   │   ├── ClientForm.tsx        # 本人または配偶者 1 人分のフォーム
    │   │   └── SpouseToggle.tsx      # 「配偶者を追加 / 削除」トグルボタン
    │   │
    │   ├── ExpenseSection/
    │   │   └── ExpenseSection.tsx    # 月間支出フォーム（合計参考値表示を含む）
    │   │
    │   ├── EventSection/
    │   │   ├── EventSection.tsx      # イベント一覧 + 追加ボタン
    │   │   ├── EventCard.tsx         # 各イベントのカード表示（編集・削除ボタン付き）
    │   │   ├── EventDialog.tsx       # 追加・編集用モーダルダイアログ（種別選択 → フォーム切り替え）
    │   │   └── event-forms/
    │   │       ├── CommonEventFields.tsx   # 発生年（全種別共通）
    │   │       ├── MarriageForm.tsx
    │   │       ├── BirthForm.tsx
    │   │       ├── HousingForm.tsx
    │   │       ├── EducationForm.tsx
    │   │       ├── CareForm.tsx
    │   │       └── OtherExpenseForm.tsx
    │   │
    │   ├── SimulateButton.tsx        # 実行ボタン（ローディング状態・無効化制御）
    │   │
    │   └── ResultSection/
    │       ├── ResultSection.tsx     # テーブル全体のラッパー（非表示制御）
    │       └── CashFlowTable.tsx     # 年次キャッシュフロー表示テーブル
    │
    ├── hooks/
    │   ├── useSimulate.ts    # POST /simulate の呼び出し・状態管理（loading/result/error）
    │   └── useScenario.ts    # シナリオ全体の状態（ライフイベントリスト）を useReducer で管理
    │
    ├── types/
    │   └── scenario.ts       # フロントエンド内部のドメイン型（ScenarioFormData・LifeEvent 等）
    │
    └── utils/
        └── formatCurrency.ts # 円表示フォーマット（将来的な表示変更を 1 箇所に集約）
```

---

## コンポーネント設計

### 設計方針

- `App.tsx` がページ全体を縦積みで表示する唯一のページコンポーネント
- フォームの入力値は React Hook Form が管理し、フォームコンポーネント内に閉じる
- ライフイベントのリスト（追加・削除・編集）はフォームではなくアプリ状態なので `useReducer`（`useScenario`）で管理する
- `useSimulate` フックが API 呼び出しの副作用と結果状態を持つ
- コンポーネントは表示・入力のみ担当し、API 呼び出しを直接行わない

### コンポーネント責務一覧

| コンポーネント | 責務 | props の方向 |
|---------------|------|-------------|
| `App.tsx` | セクションの縦積みレイアウト。`useScenario` と `useSimulate` を呼び出し、子コンポーネントへ渡す | 各セクションへ渡す |
| `ClientSection` | 本人フォーム + 配偶者トグル + 配偶者フォームの制御 | `onClientChange`, `onSpouseChange` を受け取る |
| `ClientForm` | 1 人分の入力フォーム（React Hook Form の `useForm` を内部で持つ）。収入モデルに応じたフィールドの活性・非活性切り替えを担当 | `defaultValues`, `onChange` を受け取る |
| `SpouseToggle` | 「配偶者を追加」ボタン。配偶者フォームの表示/非表示を切り替えるだけ | `shown`, `onToggle` を受け取る |
| `ExpenseSection` | 月間支出フォーム。入力値から合計参考値を計算してリアルタイム表示する | `onExpenseChange` を受け取る |
| `EventSection` | イベントカード一覧 + 追加ボタン。`EventDialog` の開閉を制御 | `events`, `onAdd`, `onEdit`, `onDelete` を受け取る |
| `EventCard` | 種別・年・主要パラメータのサマリーを 1 件表示。編集・削除ボタンを持つ | `event`, `onEdit`, `onDelete` を受け取る |
| `EventDialog` | 追加・編集のモーダル。種別選択ドロップダウンと種別フォームを含む。バリデーションは React Hook Form で担当 | `open`, `initialValue`, `onSubmit`, `onClose` を受け取る |
| `*Form`（各種別フォーム） | 種別固有のフィールドを表示。`CommonEventFields`（発生年）を必ず含む | React Hook Form の `register`, `control`, `errors` を受け取る |
| `SimulateButton` | ローディング中は無効化。クリックで `App.tsx` のコールバックを呼ぶ | `loading`, `onClick` を受け取る |
| `ResultSection` | `result` が null のときは何も表示しない。結果があれば `CashFlowTable` をレンダーし `scrollIntoView` を呼ぶ | `result`, `hasSpouse` を受け取る |
| `CashFlowTable` | 年次キャッシュフローをテーブルで表示。`net < 0` の行は文字色を赤、`savings < 0` の行は背景色を薄い赤にする。`hasSpouse` が false なら配偶者年齢列を表示しない | `rows`, `hasSpouse` を受け取る |

### イベントフォームのモーダル設計

種別選択と入力を同一ダイアログ内に収める。ステップは以下の通り。

1. ダイアログが開く（追加: 種別未選択・編集: 既存種別が選択済み）
2. 種別ドロップダウンで選択すると、対応する `*Form` コンポーネントに切り替わる
3. React Hook Form の `handleSubmit` でバリデーション実行
4. バリデーション通過で `onSubmit` コールバックを呼び、ダイアログを閉じる

**モーダルを選んだ理由**: インライン展開では、複数イベントを追加するたびに画面が伸びてイベントカード一覧の視認性が下がる。面談中の操作性を優先してモーダルとする。

---

## 状態管理設計

### 状態の分類と管理場所

| 状態 | 管理場所 | 理由 |
|------|---------|------|
| 本人・配偶者フォームの入力値 | `ClientForm` 内の `useForm`（React Hook Form） | フォームのバリデーション・ダーティ検出が必要 |
| 支出フォームの入力値 | `ExpenseSection` 内の `useForm`（React Hook Form） | 同上 |
| 配偶者フォームの表示状態 | `App.tsx` の `useState<boolean>` | `ClientSection` と `useSimulate` の両方が参照する（`spouse: null` の決定に使う） |
| ライフイベントリスト | `useScenario` フック内の `useReducer` | 追加・編集・削除の操作が明確なので `reducer` が適切 |
| イベントダイアログの開閉・編集対象 | `EventSection` 内の `useState` | `EventSection` 内で完結する |
| API 呼び出し状態（loading/result/error） | `useSimulate` フック | 副作用と状態を 1 箇所に集める |

### `useScenario` フックの設計

```typescript
// アクションの型
type EventAction =
  | { type: "ADD"; event: LifeEvent }
  | { type: "EDIT"; index: number; event: LifeEvent }
  | { type: "DELETE"; index: number }

// 返す値
interface UseScenarioReturn {
  events: LifeEvent[]
  dispatch: Dispatch<EventAction>
}
```

`LifeEvent` はユニオン型で種別を表現する（後述の型設計を参照）。

### `useSimulate` フックの設計

```typescript
// エラーの種別
type SimulateError =
  | { kind: "network" }           // fetch が throw（接続なし）
  | { kind: "timeout" }           // AbortController でキャンセル
  | { kind: "validation"; detail: string }  // HTTP 422
  | { kind: "server" }            // HTTP 500 以上

// 返す値
interface UseSimulateReturn {
  loading: boolean
  result: CashFlowRowResponse[] | null
  error: SimulateError | null
  simulate: (scenario: SimulateRequestBody) => Promise<void>
}
```

`simulate` 関数は `App.tsx` の「シミュレーション実行」ボタン押下時に呼ばれる。
呼び出しのたびに `result` と `error` をリセットしてから `fetch` を開始する。

---

## API クライアント設計

### `src/api/client.ts`

すべての `fetch` 呼び出しはこのファイルに集約する。コンポーネントや hooks が直接 `fetch` しない。

```typescript
// エクスポートする関数
async function postSimulate(body: SimulateRequestBody): Promise<CashFlowRowResponse[]>
async function getHealth(): Promise<void>
```

### 設計の詳細

**ベース URL の解決**

```typescript
const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
```

`VITE_API_URL` が設定されていない場合は `http://localhost:8000` にフォールバックする。
Vite は `import.meta.env` を静的に置換するため、Electron ビルド時の `.env.production` で上書きできる。

**タイムアウト制御**

`AbortController` と `setTimeout` を組み合わせる。追加ライブラリは使わない。

| エンドポイント | タイムアウト |
|---------------|------------|
| `GET /health` | 5 秒 |
| `POST /simulate` | 30 秒 |

タイムアウト発生時は `AbortController.abort()` を呼び、`fetch` が throw する `AbortError` を捕捉して `{ kind: "timeout" }` に変換する。

**エラー変換ルール**

| fetch の結果 | 変換後の `SimulateError` |
|-------------|------------------------|
| `fetch` が throw（接続失敗） | `{ kind: "network" }` |
| `AbortError`（タイムアウト） | `{ kind: "timeout" }` |
| HTTP 422（`detail` 文字列） | `{ kind: "validation", detail: response.detail }` |
| HTTP 422（`detail` 配列 / Pydantic 形式） | `{ kind: "validation", detail: "入力内容に誤りがあります" }` にフォールバック |
| HTTP 500 以上 | `{ kind: "server" }` |

**HTTP 422 の `detail` 形式について**

バックエンド設計（`docs/design/01_api-layer.md`）に記載の通り、`validator.py` 由来のエラーは `detail` が文字列、Pydantic 由来のエラーは `detail` が配列になる。
フロントエンドは `typeof response.detail === "string"` で分岐し、配列の場合は汎用メッセージにフォールバックする。

---

## TypeScript 型設計

### `src/api/types.ts`（API の入出力型）

バックエンドの `src/api/schemas.py` と 1:1 で対応する。
実際の型定義は engineer が `schemas.py` を参照して作成すること。主要な型の概要を示す。

```typescript
// リクエスト
interface ClientRequest { ... }           // schemas.py の ClientRequest と同フィールド
interface MonthlyExpensesRequest { ... }  // schemas.py の MonthlyExpensesRequest と同フィールド

// ライフイベントのユニオン型（discriminated union）
type EventRequest =
  | MarriageEventRequest    // type: "marriage"
  | BirthEventRequest       // type: "birth"
  | HousingEventRequest     // type: "housing"
  | EducationEventRequest   // type: "education"
  | CareEventRequest        // type: "care"
  | OtherExpenseEventRequest  // type: "other_expense"

interface SimulateRequestBody {
  client: ClientRequest
  spouse: ClientRequest | null
  savings_initial: number
  end_age: number
  start_year: number
  monthly_expenses: MonthlyExpensesRequest
  events: EventRequest[]
}

// レスポンス
interface CashFlowRowResponse {
  year: number
  age_client: number
  age_spouse: number | null
  income_total: number
  expense_total: number
  loan_deduction: number
  net: number
  savings: number
  events_label: string
}
```

### `src/types/scenario.ts`（フロントエンド内部型）

React Hook Form が扱うフォームの内部表現。API 型と完全には一致しない（例: `income_model` は選択肢の文字列リテラル型で持つ）。

```typescript
// 収入モデルの選択肢
type IncomeModel = "flat" | "raise_rate" | "post_retirement"

// 学校種別
type SchoolType = "public" | "private"

// フォームで使うクライアント情報型
interface ClientFormData {
  age: number
  annual_income: number
  income_model: IncomeModel
  raise_rate: number
  retirement_age: number
  post_retirement_income: number
  pension_start_age: number
  pension_annual: number
}

// ライフイベントの内部表現（リストで管理する単位）
type LifeEvent = MarriageEvent | BirthEvent | HousingEvent | EducationEvent | CareEvent | OtherExpenseEvent
// 各型は type フィールドを持つ discriminated union
```

`LifeEvent` の各型フィールドは API の `EventRequest` と同じにする。変換コストをゼロにするため、内部型と API 型を揃える。

---

## テスト設計

テストツール: Vitest + React Testing Library。

### テストファイル配置

```
frontend/
└── src/
    └── __tests__/
        ├── api/
        │   └── client.test.ts          # API クライアントのユニットテスト
        ├── hooks/
        │   ├── useSimulate.test.ts
        │   └── useScenario.test.ts
        └── components/
            ├── ClientForm.test.tsx
            ├── ExpenseSection.test.tsx
            ├── EventDialog.test.tsx
            ├── EventCard.test.tsx
            ├── CashFlowTable.test.tsx
            └── App.integration.test.tsx  # 全体の結合テスト
```

### `client.test.ts`（API クライアント）

`fetch` を `vi.stubGlobal` でモックして各ケースをテストする。

| テストケース | 検証内容 |
|------------|---------|
| 正常系: HTTP 200 | レスポンス JSON が `CashFlowRowResponse[]` として返る |
| タイムアウト | `AbortController` が 30 秒後に `abort()` を呼ぶことを確認 |
| HTTP 422（detail 文字列） | `{ kind: "validation", detail: "..." }` が throw される |
| HTTP 422（detail 配列） | `{ kind: "validation", detail: "入力内容に誤りがあります" }` が throw される |
| HTTP 500 | `{ kind: "server" }` が throw される |
| fetch が throw | `{ kind: "network" }` が throw される |

### `useSimulate.test.ts`

`renderHook` でフックを呼び出し、`client.ts` をモックして状態遷移を検証する。

| テストケース | 検証内容 |
|------------|---------|
| 実行前 | `loading: false`, `result: null`, `error: null` |
| 実行中 | `loading: true`, ボタンの無効化が前提 |
| 成功後 | `loading: false`, `result` に行データが入る |
| エラー後 | `loading: false`, `error` に対応する種別が入る |
| 2 回目実行 | 前回の `result` と `error` がリセットされてから fetch が始まる |

### `useScenario.test.ts`

reducer の動作をテストする（UI 不要）。

| テストケース | 検証内容 |
|------------|---------|
| ADD | events の末尾に追加される |
| EDIT | 指定 index のイベントが置き換わる |
| DELETE | 指定 index のイベントが消える |
| 同一種別の複数追加 | 重複なくリストに並ぶ |

### `ClientForm.test.tsx`

仕様のアクセプタンス基準・境界値を網羅する。

| テストケース | 検証内容 |
|------------|---------|
| 収入モデル「昇給率指定」選択 | 昇給率フィールドがアクティブになる |
| 収入モデル「定年後減額」選択 | 定年後年収フィールドがアクティブになる |
| 収入モデル「一定」選択 | 昇給率・定年後年収がアクティブでない |
| 年齢に 0 入力 | エラーメッセージが表示される |
| 年齢に 101 入力 | エラーメッセージが表示される |
| 昇給率に 101% 入力 | エラーメッセージが表示される |
| 貯蓄残高に負数入力 | エラーメッセージが表示される |

### `EventDialog.test.tsx`

| テストケース | 検証内容 |
|------------|---------|
| 住宅購入: 頭金 >= 物件価格 | エラーメッセージが表示され、`onSubmit` が呼ばれない |
| 住宅購入: 金利が 0 未満 | エラーメッセージが表示される |
| 住宅購入: ローン年数 51 | エラーメッセージが表示される |
| 出産: 育休中収入率が 0 未満 | エラーメッセージが表示される |
| 出産: 育休期間が負数 | エラーメッセージが表示される |
| 発生年が未入力で追加 | エラーメッセージが表示される |
| 正常追加 | `onSubmit` が正しいデータで呼ばれる |
| 編集モード | フォームに既存値が初期表示される |

### `CashFlowTable.test.tsx`

| テストケース | 検証内容 |
|------------|---------|
| `net < 0` の行 | 年間収支セルが赤色表示（`color: red` 相当のクラス or スタイル） |
| `savings < 0` の行 | 行の背景が薄い赤（クラス or スタイルで確認） |
| `hasSpouse: false` | 配偶者年齢列が DOM に存在しない |
| `hasSpouse: true` | 配偶者年齢列が表示される |
| 同一年に複数イベント | " / " 区切りで 1 セルに表示される |

### `App.integration.test.tsx`（結合テスト）

`fetch` をモックした状態で画面全体を `render` し、ユーザー操作の流れをテストする。
アクセプタンス基準の E2E 相当をここで担保する。

| テストケース | 操作手順 | 検証内容 |
|------------|---------|---------|
| 正常シミュレーション実行 | 必須項目を入力 → 実行ボタン押下 → API が 200 を返す | 結果テーブルが表示される |
| 必須項目未入力でブロック | 年収を未入力のまま実行ボタン押下 | リクエストが送信されない（`fetch` が呼ばれない） |
| ネットワークエラー | fetch が throw するようにモック → 実行 | 「サーバーに接続できません」が表示される |
| HTTP 422 エラー | fetch が 422 + detail 文字列を返すようにモック → 実行 | detail のメッセージが表示される |
| HTTP 500 エラー | fetch が 500 を返すようにモック → 実行 | 「サーバーでエラーが発生しました」が表示される |
| 配偶者なしで実行 | 配偶者フォームを非表示にして実行 | リクエストの `spouse` が null（`fetch` の引数で確認） |
| 2 回目実行で上書き | 1 回目実行後に入力を変えて 2 回目実行 | テーブルが新しい結果で更新される |
| 送信中の二重送信防止 | 実行ボタン押下後にすぐ再押下 | `fetch` が 1 回しか呼ばれない |

---

## 依存関係

```
App.tsx
  ├── useScenario (hooks/useScenario.ts)
  ├── useSimulate (hooks/useSimulate.ts)
  │     └── api/client.ts
  │           └── api/types.ts
  ├── ClientSection/ClientSection.tsx
  │     ├── ClientForm.tsx            (react-hook-form)
  │     └── SpouseToggle.tsx
  ├── ExpenseSection/ExpenseSection.tsx  (react-hook-form)
  ├── EventSection/EventSection.tsx
  │     ├── EventCard.tsx
  │     └── EventDialog.tsx
  │           ├── CommonEventFields.tsx
  │           └── event-forms/*.tsx   (react-hook-form)
  ├── SimulateButton.tsx
  └── ResultSection/ResultSection.tsx
        └── CashFlowTable.tsx
```

**循環依存なし**: すべての依存は末端（`api/types.ts`, `types/scenario.ts`）に向かって一方向に流れる。

---

## 設計判断の根拠

### `HashRouter` を最初から採用する

`BrowserRouter` を `HashRouter` に後から変更する場合、ルーティングに依存したリンクやリダイレクト処理をすべて確認し直す必要がある。現時点でルートは 1 つだが、ep4.4 で Electron 化するとき変更コストがゼロになるよう最初から `HashRouter` にする。

### フォーム値を React Hook Form に任せ、イベントリストだけ `useReducer` にする

フォームの入力値はリアルタイムバリデーション・ダーティ検出・リセットが必要であり、React Hook Form がこれを提供する。
一方、ライフイベントのリストは「追加・編集・削除」という明確な操作セットを持ち、操作の意図を reducer のアクション型で表現する方が可読性が高い。
両者を混在させると責務が不明確になるため、分離する。

### `EventDialog` をモーダルにする

インライン展開では、3〜4 件のイベントを追加した後にさらに追加しようとすると、各イベントのフォームが縦に並んで画面が伸び、既存のイベントカード一覧が見えなくなる。
FP は面談中にクライアントと画面を共有するため、既存イベントの確認と新規追加を行き来しやすいモーダルを選ぶ。

### `src/api/client.ts` にすべての `fetch` を集約する

コンポーネントやフックが直接 `fetch` を呼ぶと、ベース URL の変更・タイムアウト追加・エラー変換ロジックが散在する。
Electron ビルド時に `VITE_API_URL` を変更する箇所が `client.ts` の 1 行だけになることが確認できる。

### `LifeEvent` の内部型と API 型を揃える

フロントエンドが独自の「内部型」を持ち、送信時に API 型へ変換するパターンもある。
しかし、今回のライフイベントのフィールドはフロントエンド固有の加工を必要としない（表示用に整形した値を別途持つ必要がない）。
変換コードを書かずにそのまま `SimulateRequestBody.events` に渡せるため、内部型と API 型を同一にする。

### 選ばなかった選択肢

| 選択肢 | 不採用理由 |
|--------|-----------|
| `BrowserRouter` | Electron の `file://` プロトコルで動作しない |
| Zustand / Jotai などのグローバル状態管理 | フォームは React Hook Form・イベントは `useReducer` で十分。外部ライブラリを追加する複雑さの方がコストが高い |
| axios | fetch API で要件（タイムアウト・エラーハンドリング）を満たせる。追加依存は不要 |
| ライフイベントフォームをインライン展開 | 面談中の操作性・画面の視認性を損なう |
| `LifeEvent` の内部型を API 型と分ける | 変換コードが増えるだけで利点がない（フロントエンド固有の表現が不要なため） |

---

## 実装者へのノート

1. **`VITE_API_URL` の未定義時の挙動**: Vite は `.env` ファイルが存在しない場合 `import.meta.env.VITE_API_URL` が `undefined` になる。`?? "http://localhost:8000"` でフォールバックを必ず書く。`||` は空文字列を `false` 扱いするため使わない。

2. **React Hook Form の `useForm` を複数インスタンス使う**: 本人フォーム・配偶者フォーム・支出フォーム・各イベントフォームは独立した `useForm` を持つ。`App.tsx` で単一の `useForm` にまとめようとすると、ネストした配列フィールドの扱いが複雑になる。分割を維持すること。

3. **配偶者フォームの「非表示時にリセット」**: 配偶者フォームが非表示になったとき、`useForm` の `reset()` を呼ぶか、コンポーネントを DOM からアンマウントしてフォーム状態を破棄するかを選ぶ。アンマウントの方がシンプル。`spouseVisible` が false のとき `<ClientForm />` をレンダーしないだけでよい。

4. **`EventDialog` の編集モードの初期値**: React Hook Form の `defaultValues` に既存イベントの値を渡す。ダイアログを開くたびに `useForm` を再マウントするか、`reset(editTarget)` を呼ぶかを選ぶ。ダイアログのモーダル開閉と合わせて、ダイアログが閉じたら DOM からアンマウントする（MUI の `keepMounted={false}` 相当）方が初期値の管理がシンプル。

5. **`CashFlowTable` のスクロール**: `ResultSection` がマウント（または `result` が非 null になった）タイミングで `ref.current.scrollIntoView({ behavior: "smooth" })` を呼ぶ。`useEffect` で `result` の変化を監視する。

6. **`EventCard` のサマリー表示**: 種別ごとにサマリーのフォーマットが異なる。`switch (event.type)` で分岐する純粋関数 `formatEventSummary(event: LifeEvent): string` を `utils/` に置く。テスト可能な純粋関数として分離しておくと、種別追加時の変更が 1 箇所に集まる。

7. **Vitest の `fetch` モック**: `vi.stubGlobal("fetch", mockFetch)` で置き換える。テスト終了後は `vi.unstubAllGlobals()` でリストアする。`afterEach` に書いておくと安全。

8. **`App.integration.test.tsx` の `fetch` 呼び出し確認**: `expect(mockFetch).toHaveBeenCalledWith(...)` でリクエストボディを検証する。`spouse: null` になっているかのテストはここで行う。
