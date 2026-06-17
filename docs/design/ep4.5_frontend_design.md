# 設計: ep4.5 Phase 2 フロントエンド クライアント管理 UI

## 概要

バックエンド（Phase 1）で実装済みの `/clients` CRUD API を呼び出し、
クライアントデータの保存・呼び出し・更新・削除をフロントエンドから操作できるようにする。
クライアント選択時は key-based remount でフォーム全体を安全にリセットする。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 理由 |
| -------- | -------- | ---- |
| `frontend/src/api/types.ts` | 変更 | クライアント CRUD 用の型を追加 |
| `frontend/src/api/client.ts` | 変更 | クライアント CRUD 用の fetch 関数を追加 |
| `frontend/src/hooks/useClients.ts` | 新規 | クライアント一覧・選択・CRUD の状態管理 |
| `frontend/src/hooks/useScenario.ts` | 変更 | SET_ALL アクション追加（イベント一括復元用） |
| `frontend/src/components/ClientManager/ClientManager.tsx` | 新規 | クライアント選択・操作バー |
| `frontend/src/components/ClientManager/SaveDialog.tsx` | 新規 | 名前入力ダイアログ |
| `frontend/src/components/ClientSection/ClientSection.tsx` | 変更 | defaultValues prop 追加 |
| `frontend/src/components/ExpenseSection/ExpenseSection.tsx` | 変更 | defaultValues prop 追加 |
| `frontend/src/App.tsx` | 変更 | ClientManager 統合 + formKey による remount |

---

## データモデル

### API 型（`api/types.ts` に追加）

```typescript
// GET /clients の一覧要素
export interface ClientListItem {
  id: number;
  name: string;
  updated_at: string; // ISO 8601
}

// GET /clients/{id}, POST /clients, PUT /clients/{id} のレスポンス
export interface ClientResponse {
  id: number;
  name: string;
  scenario: SimulateRequestBody; // バックエンドでは dict だが、フロント側は型付きで扱う
  created_at: string;
  updated_at: string;
}

// POST /clients, PUT /clients/{id} のリクエストボディ
export interface ClientSaveRequest {
  name: string;
  scenario: SimulateRequestBody;
}

// クライアント CRUD 操作のエラー（既存の discriminated union パターンに合わせる）
export type ClientError =
  | { kind: 'network' }
  | { kind: 'timeout' }
  | { kind: 'not_found' }
  | { kind: 'validation'; detail: string }
  | { kind: 'server' };
```

### フォーム初期値の型（新規型は不要）

クライアント呼び出し時にフォームに渡す初期値は、既存の型をそのまま使う:
- `ClientFormData` (本人・配偶者)
- `ScenarioCommonData` (共通設定)
- `MonthlyExpensesRequest` (月間支出)
- `LifeEvent[]` (イベント一覧)

これらは `SimulateRequestBody` から分解して取り出す。

---

## インターフェース

### API 関数（`api/client.ts` に追加）

```typescript
export async function getClients(timeoutMs?: number): Promise<ClientListItem[]>;
export async function getClient(id: number, timeoutMs?: number): Promise<ClientResponse>;
export async function postClient(body: ClientSaveRequest, timeoutMs?: number): Promise<ClientResponse>;
export async function putClient(id: number, body: ClientSaveRequest, timeoutMs?: number): Promise<ClientResponse>;
export async function deleteClient(id: number, timeoutMs?: number): Promise<void>;
```

エラーハンドリングは既存の `postSimulate` と同じパターン:
- AbortController + setTimeout でタイムアウト制御
- 404 → `{ kind: 'not_found' }` として throw
- 422 → `{ kind: 'validation', detail }` として throw
- その他 → `{ kind: 'server' }` / `{ kind: 'network' }`

### useScenario の変更

```typescript
type EventAction =
  | { type: 'ADD'; event: LifeEvent }
  | { type: 'EDIT'; index: number; event: LifeEvent }
  | { type: 'DELETE'; index: number }
  | { type: 'SET_ALL'; events: LifeEvent[] };  // 追加
```

reducer に `SET_ALL` ケースを追加。`action.events` をそのまま返す。

### useClients hook

```typescript
interface UseClientsReturn {
  // 状態
  clients: ClientListItem[];
  selectedId: number | null;
  loading: boolean;
  error: ClientError | null;

  // 操作
  refresh: () => Promise<void>;           // 一覧を再取得
  load: (id: number) => Promise<ClientResponse>;  // 1件取得して selectedId を更新
  save: (name: string, scenario: SimulateRequestBody) => Promise<void>;  // 新規保存
  overwrite: (scenario: SimulateRequestBody) => Promise<void>;  // 上書き保存（selectedId 使用）
  remove: (id: number) => Promise<void>;  // 削除
  clearSelection: () => void;             // 選択解除（新規モードへ）
}

export function useClients(): UseClientsReturn;
```

**状態遷移:**

| 操作 | selectedId | clients | formKey |
| ---- | ---------- | ------- | ------- |
| ページ初期表示 | null | API から取得 | 0 |
| クライアント選択 | 選択した ID | 変化なし | +1 (remount) |
| 新規保存 | 新しい ID | 一覧に追加 | 変化なし |
| 上書き保存 | 変化なし | updated_at 更新 | 変化なし |
| 削除 | null | 一覧から除去 | +1 (remount) |
| 「新規作成」ボタン | null | 変化なし | +1 (remount) |

注意: `formKey` は `useClients` の中には持たない。`App.tsx` の `SimulatorPage` が管理する（後述）。

### ClientManager コンポーネント

```typescript
interface ClientManagerProps {
  clients: ClientListItem[];
  selectedId: number | null;
  loading: boolean;
  error: ClientError | null;
  onSelect: (id: number) => void;       // クライアント選択
  onNew: () => void;                     // 新規作成モード
  onSave: () => void;                    // 保存（名前入力ダイアログを開く）
  onOverwrite: () => void;               // 上書き保存
  onDelete: () => void;                  // 削除（確認ダイアログ付き）
}
```

**UI 構成:**

```
┌───────────────────────────────────────────────────────┐
│ [Autocomplete: クライアント選択]  [新規] [保存] [上書き] [削除] │
└───────────────────────────────────────────────────────┘
```

- **Autocomplete** (MUI): `ClientListItem[]` を options に、`name` を表示。`updated_at` をセカンダリテキストで表示
- **新規ボタン**: `selectedId !== null` のとき有効。フォームをリセットして新規入力モードへ
- **保存ボタン**: 常に有効。SaveDialog を開く
- **上書きボタン**: `selectedId !== null` のとき有効
- **削除ボタン**: `selectedId !== null` のとき有効。window.confirm で確認

### SaveDialog コンポーネント

```typescript
interface SaveDialogProps {
  open: boolean;
  defaultName: string;        // 編集中のクライアント名（上書き時のプリフィル）
  onSave: (name: string) => void;
  onCancel: () => void;
}
```

- MUI Dialog + TextField + Button (保存 / キャンセル)
- 名前が空の場合はボタン disabled
- Enter キーで保存

---

## App.tsx の変更: key-based remount

### 設計の要点

クライアント選択時に全フォームの値を復元する方法として **key-based remount** を採用する。

**仕組み:**
1. `SimulatorPage` が `formKey: number` state を持つ
2. クライアント選択・新規作成・削除時に `formKey` を increment する
3. `ClientSection`, `ExpenseSection`, `EventSection` を囲む要素に `key={formKey}` を設定
4. key が変わると React が子コンポーネントツリーを破棄して再生成する
5. 再生成時に各フォームが `defaultValues` prop で初期値を受け取る

**なぜ key-based remount か:**

| 方式 | メリット | デメリット |
| ---- | -------- | ---------- |
| react-hook-form の `reset()` を命令的に呼ぶ | 再マウント不要 | 全フォームの ref を親が管理する必要がある。SpouseToggle の表示/非表示も手動制御が必要 |
| **key-based remount** | 各フォームは props の defaultValues を受け取るだけ。子コンポーネントの変更が最小限 | フォーム再生成のコスト（軽微）|
| controlled component に全面変更 | 状態管理が明確 | 既存の useForm ベースの設計を大幅に変更する必要がある |

key-based remount は既存コードへの変更が最小で、各子コンポーネントの独立性を保てる。

### SimulatorPage の変更後の状態

```typescript
function SimulatorPage() {
  // 既存
  const { loading, result, error, simulate } = useSimulate();
  const { events, dispatch } = useScenario();

  // 新規: クライアント管理
  const {
    clients, selectedId, loading: clientLoading, error: clientError,
    refresh, load, save, overwrite, remove, clearSelection,
  } = useClients();

  // 新規: フォームの初期値（クライアント呼び出し時に更新）
  const [formKey, setFormKey] = useState(0);
  const [defaultClient, setDefaultClient] = useState<ClientFormData | undefined>(undefined);
  const [defaultSpouse, setDefaultSpouse] = useState<ClientFormData | null>(null);
  const [defaultCommon, setDefaultCommon] = useState<ScenarioCommonData | undefined>(undefined);
  const [defaultExpense, setDefaultExpense] = useState<MonthlyExpensesRequest | undefined>(undefined);

  // 既存（変更なし）
  const clientRef = useRef<ClientFormData>(...);
  const spouseRef = useRef<ClientFormData | null>(...);
  const commonRef = useRef<ScenarioCommonData>(...);
  const expenseRef = useRef<MonthlyExpensesRequest>(...);

  // クライアント選択ハンドラ
  const handleSelectClient = async (id: number) => {
    const response = await load(id);
    const scenario = response.scenario;
    // SimulateRequestBody から各フォームの初期値を分解
    setDefaultClient(scenario.client);
    setDefaultSpouse(scenario.spouse);
    setDefaultCommon({
      savings_initial: scenario.savings_initial,
      end_age: scenario.end_age,
      start_year: scenario.start_year,
    });
    setDefaultExpense(scenario.monthly_expenses);
    dispatch({ type: 'SET_ALL', events: scenario.events });
    setFormKey(prev => prev + 1); // remount
  };

  const handleNew = () => {
    clearSelection();
    setDefaultClient(undefined);
    setDefaultSpouse(null);
    setDefaultCommon(undefined);
    setDefaultExpense(undefined);
    dispatch({ type: 'SET_ALL', events: [] });
    setFormKey(prev => prev + 1); // remount
  };

  // 現在のフォーム値から SimulateRequestBody を組み立てる関数（simulate と共有）
  const buildScenarioBody = (): SimulateRequestBody => ({
    client: clientRef.current,
    spouse: spouseRef.current,
    savings_initial: commonRef.current.savings_initial,
    end_age: commonRef.current.end_age,
    start_year: commonRef.current.start_year,
    monthly_expenses: expenseRef.current,
    events: events,
  });

  // ...
}
```

### JSX の変更

```tsx
<Container maxWidth="lg" sx={{ py: 4 }}>
  <Typography variant="h4" component="h1" gutterBottom>
    ライフイベント家計シミュレーター
  </Typography>

  {/* 新規追加: クライアント管理バー */}
  <ClientManager
    clients={clients}
    selectedId={selectedId}
    loading={clientLoading}
    error={clientError}
    onSelect={handleSelectClient}
    onNew={handleNew}
    onSave={handleSave}
    onOverwrite={handleOverwrite}
    onDelete={handleDelete}
  />

  {/* key で囲んで remount する */}
  <Box key={formKey}>
    <ClientSection
      defaultClient={defaultClient}
      defaultSpouse={defaultSpouse}
      defaultCommon={defaultCommon}
      onClientChange={(data) => { clientRef.current = data; }}
      onSpouseChange={handleSpouseChange}
      onCommonChange={(data) => { commonRef.current = data; }}
    />

    <ExpenseSection
      defaultValues={defaultExpense}
      onExpenseChange={(data) => { expenseRef.current = data; }}
    />

    <EventSection events={events} dispatch={dispatch} />
  </Box>

  {/* 以下は既存のまま */}
  <SimulateButton ... />
  <ResultSection ... />
</Container>
```

---

## 子コンポーネントの変更

### ClientSection

```typescript
interface Props {
  defaultClient?: Partial<ClientFormData>;   // 追加
  defaultSpouse?: ClientFormData | null;     // 追加
  defaultCommon?: Partial<ScenarioCommonData>; // 追加
  onClientChange: (data: ClientFormData) => void;
  onSpouseChange: (data: ClientFormData | null) => void;
  onCommonChange: (data: ScenarioCommonData) => void;
}
```

変更点:
- `useForm<ScenarioCommonData>` の `defaultValues` に `props.defaultCommon` をマージ
- `<ClientForm>` に `defaultValues={props.defaultClient}` を渡す（既に対応済み）
- 配偶者: `defaultSpouse` が非 null なら初期状態で `spouseVisible = true` + `<ClientForm defaultValues={defaultSpouse}>` を渡す

### ExpenseSection

```typescript
interface Props {
  defaultValues?: Partial<MonthlyExpensesRequest>;  // 追加
  onExpenseChange: (data: MonthlyExpensesRequest) => void;
}
```

変更点:
- `useForm` の `defaultValues` に `props.defaultValues` をマージ

### ClientForm（変更不要）

既に `defaultValues?: Partial<ClientFormData>` prop を受け付けている。変更不要。

### EventSection（変更不要）

`events` は `useScenario` の `dispatch({ type: 'SET_ALL', events })` で更新される。
`EventSection` は `events` prop をそのまま表示するだけなので変更不要。

---

## 依存関係

```
App.tsx (SimulatorPage)
  ├── useClients (hook)
  │     └── api/client.ts (getClients, getClient, postClient, putClient, deleteClient)
  │           └── api/types.ts (ClientListItem, ClientResponse, ClientSaveRequest, ClientError)
  ├── useScenario (hook) ← SET_ALL 追加
  ├── ClientManager (component)
  │     └── SaveDialog (component)
  ├── ClientSection (component) ← defaultValues prop 追加
  │     └── ClientForm (component) ← 変更なし
  └── ExpenseSection (component) ← defaultValues prop 追加
```

依存の方向: UI コンポーネント → hooks → api 関数 → api 型。逆方向の依存はない。

---

## 設計判断の根拠

### 1. formKey による remount vs reset() の命令的呼び出し

**採用: formKey (key-based remount)**

理由:
- ClientForm は既に `defaultValues` prop を受け取る設計になっている
- SpouseToggle の表示/非表示状態も再マウントで自然にリセットされる
- 親が子の内部実装（useForm の ref）に依存しなくて済む
- フォームが増えても、key を囲む Box に入れるだけで対応できる

トレードオフ:
- 再マウントのコスト（DOM 再生成）はあるが、フォーム数個程度なので無視できる
- フォーム入力中の値がリセットされるが、クライアント切り替え操作なので意図通り

### 2. Autocomplete vs Select

**採用: Autocomplete**

理由:
- クライアント数が増えたときに検索できる
- MUI Autocomplete は freeSolo=false で Select と同じ操作感を提供できる
- クライアント名 + 更新日時をカスタムレンダリングで表示しやすい

### 3. useClients を独立 hook にする vs App.tsx に直書き

**採用: 独立 hook**

理由:
- API 呼び出し + 状態管理のロジックを App.tsx から分離する
- テスタビリティ（hook 単体でテスト可能）
- App.tsx が既に 100 行超で、これ以上ロジックを入れると見通しが悪くなる

### 4. ClientError を新設 vs 既存の SimulateError を共用

**採用: ClientError を新設**

理由:
- クライアント CRUD には `not_found` (404) が存在するが、SimulateError にはない
- 概念が異なる操作のエラーを同じ型で表現すると、switch 文で不要なケースを処理する必要が出る

### 5. scenario フィールドの型

バックエンドの `ClientSaveRequest.scenario` は `dict` (任意の JSON) だが、
フロントエンドでは `SimulateRequestBody` として型付きで扱う。

理由:
- フロントエンドが保存するデータは常に `SimulateRequestBody` の構造を持つ
- 型安全にすることで、呼び出し時のフィールド分解でコンパイル時チェックが効く
- バックエンドは dict として保存するので、構造変更時のマイグレーションはバックエンド側の責務

---

## 実装者へのノート

### 1. API 関数の共通化

`api/client.ts` に既に 4 つの関数があり、それぞれ同じ try/catch パターンを持つ。
新しい 5 関数を追加すると重複が目立つ。ただし、現時点では各関数のレスポンス型やエラー変換が微妙に異なるため、
**ヘルパー関数の抽出は2回目以降の重複が確認されてから行う**（設計原則4: 拡張より削除に強い設計）。
まず素直に個別関数を書く。

### 2. useClients の初回 fetch

`useEffect` で `refresh()` を呼ぶ。バックエンドが起動していない場合はエラーを state に保持するが、
フォーム操作はブロックしない（クライアント管理は付加機能であり、シミュレーション自体は従来通り使える必要がある）。

### 3. 保存時の scenario 組み立て

`buildScenarioBody()` は `clientRef.current` 等の ref から値を取る。
ref は onChange コールバックで常に最新値が入っているため、保存ボタン押下時点の値が正確に取れる。

### 4. 上書き保存のフロー

1. `putClient(selectedId, { name: currentName, scenario: buildScenarioBody() })` を呼ぶ
2. 成功したら `refresh()` で一覧を再取得（updated_at が変わるため）
3. formKey は変えない（フォームの値はそのまま）

### 5. 削除時の確認

`window.confirm` を使う。MUI の Dialog を使ってもよいが、
削除確認は単純な Yes/No なので、まずは最小限で実装する。

### 6. EventSection への events 受け渡し

formKey で remount すると `useScenario` の `events` state もリセットされてしまう問題がある。
`useScenario` は `SimulatorPage` で呼ばれているため remount 対象外。
`dispatch({ type: 'SET_ALL', events })` は `handleSelectClient` / `handleNew` の中で
`setFormKey` より前に呼ぶ。EventSection は `events` prop を受け取るだけなので、
remount されても新しい events が正しく渡される。

### 7. SpouseToggle の初期状態

`ClientSection` に `defaultSpouse` が渡された場合:
- `defaultSpouse` が非 null → `useState(true)` で配偶者フォームを初期表示
- `defaultSpouse` が null / undefined → `useState(false)` で非表示（従来通り）
