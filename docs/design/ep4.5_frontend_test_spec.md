# テスト仕様: ep4.5 フロントエンド クライアント管理 UI

## 目的

FPが保存済みクライアントを選択してフォームにデータを復元し、シミュレーションを再実行できるようにする。また、現在の入力内容を名前付きで保存できるようにする。

### 成功した状態

- クライアント一覧から選択すると、フォーム全体にデータが復元される
- 現在の入力内容を名前付きで新規保存できる
- 選択中のクライアントに上書き保存できる
- 不要なクライアントを削除できる

### 失敗した状態

- 保存したはずのデータが復元されない
- API エラー時にユーザーに何もフィードバックがない
- クライアント未選択で上書き保存してデータが消える

---

## テスト対象 1: API client 関数

### テスト対象シグネチャ（新規追加）

```typescript
// api/client.ts に追加
getClients(): Promise<ClientSummary[]>
getClient(id: number): Promise<ClientDetail>
postClient(body: SaveClientBody): Promise<ClientDetail>
putClient(id: number, body: SaveClientBody): Promise<ClientDetail>
deleteClient(id: number): Promise<void>
```

### テストファイル

`frontend/src/__tests__/api/clientCrud.test.ts`

### テストクラス一覧

#### `describe('getClients')`

目的: クライアント一覧取得 API の呼び出しとエラーハンドリング

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `HTTP 200 のとき ClientSummary[] を返す` | fetch が `[{id:1, name:"田中", updated_at:"..."}]` を返す | 配列がそのまま返る | 正常系 |
| `HTTP 500 のとき server エラーを throw する` | fetch が status 500 を返す | `{ kind: 'server' }` が throw される | 異常系 |
| `fetch が throw するとき network エラーを throw する` | fetch が `Error('Failed to fetch')` を throw | `{ kind: 'network' }` が throw される | 異常系 |

#### `describe('getClient')`

目的: 単一クライアント詳細取得 API の呼び出しとエラーハンドリング

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `HTTP 200 のとき ClientDetail を返す` | fetch が `{id:1, name:"田中", scenario:{...}}` を返す | オブジェクトがそのまま返る | 正常系 |
| `HTTP 404 のとき not_found エラーを throw する` | fetch が status 404 を返す | `{ kind: 'not_found' }` が throw される | 異常系 |
| `HTTP 500 のとき server エラーを throw する` | fetch が status 500 を返す | `{ kind: 'server' }` が throw される | 異常系 |

#### `describe('postClient')`

目的: クライアント新規作成 API の呼び出しとエラーハンドリング

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `HTTP 201 のとき ClientDetail を返す` | fetch が status 201 + body を返す | 作成されたクライアントが返る | 正常系 |
| `リクエストボディに name と scenario が含まれる` | postClient 呼び出し時 | fetch の第2引数の body に name, scenario が JSON で入っている | 正常系 |
| `HTTP 422 のとき validation エラーを throw する` | fetch が status 422 + `{detail: "名前は必須です"}` を返す | `{ kind: 'validation', detail: '名前は必須です' }` が throw される | 異常系 |
| `HTTP 500 のとき server エラーを throw する` | fetch が status 500 を返す | `{ kind: 'server' }` が throw される | 異常系 |

#### `describe('putClient')`

目的: クライアント更新 API の呼び出しとエラーハンドリング

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `HTTP 200 のとき ClientDetail を返す` | fetch が status 200 + body を返す | 更新されたクライアントが返る | 正常系 |
| `URL に id が含まれる` | `putClient(42, body)` 呼び出し時 | fetch の第1引数が `/clients/42` で終わる | 正常系 |
| `HTTP 404 のとき not_found エラーを throw する` | fetch が status 404 を返す | `{ kind: 'not_found' }` が throw される | 異常系 |
| `HTTP 500 のとき server エラーを throw する` | fetch が status 500 を返す | `{ kind: 'server' }` が throw される | 異常系 |

#### `describe('deleteClient')`

目的: クライアント削除 API の呼び出しとエラーハンドリング

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `HTTP 204 のとき正常終了する` | fetch が status 204 を返す | 例外が throw されない | 正常系 |
| `HTTP 404 のとき not_found エラーを throw する` | fetch が status 404 を返す | `{ kind: 'not_found' }` が throw される | 異常系 |
| `HTTP 500 のとき server エラーを throw する` | fetch が status 500 を返す | `{ kind: 'server' }` が throw される | 異常系 |

### Fixture・前提条件

- `vi.stubGlobal('fetch', ...)` で fetch をモック（既存 `client.test.ts` と同じパターン）
- `afterEach(() => vi.unstubAllGlobals())` でクリーンアップ

### 実装者へのノート

- 既存の `postSimulate` のエラーハンドリングパターン（SimulateError discriminated union）に合わせる
- クライアント CRUD 用のエラー型 `ClientError` を `api/types.ts` に追加する: `{ kind: 'network' } | { kind: 'server' } | { kind: 'not_found' } | { kind: 'validation', detail: string }`
- `SaveClientBody` 型: `{ name: string; scenario: SimulateRequestBody }`
- `ClientSummary` 型: `{ id: number; name: string; updated_at: string }`
- `ClientDetail` 型: `{ id: number; name: string; scenario: SimulateRequestBody; created_at: string; updated_at: string }`

---

## テスト対象 2: useScenario hook（SET_ALL アクション追加）

### テスト対象シグネチャ（変更）

```typescript
// 既存の EventAction に追加
type EventAction =
  | { type: 'ADD'; event: LifeEvent }
  | { type: 'EDIT'; index: number; event: LifeEvent }
  | { type: 'DELETE'; index: number }
  | { type: 'SET_ALL'; events: LifeEvent[] };  // 新規追加
```

### テストファイル

`frontend/src/__tests__/hooks/useScenario.test.ts`

### テストクラス一覧

#### `describe('useScenario - SET_ALL')`

目的: クライアント読み込み時にイベント一覧を丸ごと差し替えできる

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `SET_ALL でイベント一覧が差し替わる` | 既存イベント2件 → SET_ALL で新しい3件を dispatch | events が新しい3件のみになる | 正常系 |
| `SET_ALL で空配列を渡すとイベントが全てクリアされる` | 既存イベント2件 → SET_ALL で `[]` を dispatch | events が空配列になる | 境界値 |
| `SET_ALL 後も ADD/EDIT/DELETE が正常に動作する` | SET_ALL → ADD → events の長さ確認 | SET_ALL の件数 + 1 になる | 正常系 |

### Fixture・前提条件

- `@testing-library/react` の `renderHook` を使用
- `act` でラップして dispatch を呼ぶ

### 実装者へのノート

- reducer の `SET_ALL` case は `return action.events` だけで良い（シンプルに差し替え）

---

## テスト対象 3: useClients hook

### テスト対象シグネチャ（新規）

```typescript
// hooks/useClients.ts
interface UseClientsReturn {
  clients: ClientSummary[];         // クライアント一覧
  selectedId: number | null;        // 選択中のクライアント ID
  loading: boolean;                 // API 通信中フラグ
  error: string | null;             // エラーメッセージ
  selectClient: (id: number) => Promise<ClientDetail>;  // 選択して詳細取得
  saveClient: (name: string, scenario: SimulateRequestBody) => Promise<void>;  // 新規保存
  overwriteClient: (scenario: SimulateRequestBody) => Promise<void>;  // 上書き保存
  deleteClient: (id: number) => Promise<void>;  // 削除
  refreshClients: () => Promise<void>;  // 一覧再取得
}
```

### テストファイル

`frontend/src/__tests__/hooks/useClients.test.ts`

### テストクラス一覧

#### `describe('useClients - 初期化')`

目的: hook マウント時にクライアント一覧を取得する

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `マウント時に getClients を呼んで一覧を取得する` | getClients が `[{id:1, name:"田中"}, {id:2, name:"佐藤"}]` を返す | clients が2件、loading が false | 正常系 |
| `マウント時に getClients が失敗したら error にメッセージが入る` | getClients が throw する | clients が空、error が非 null | 異常系 |
| `API 通信中は loading が true になる` | getClients が遅延する | 通信中は loading が true | 正常系 |

#### `describe('useClients - selectClient')`

目的: クライアント選択で詳細データを取得し selectedId を更新する

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `selectClient で selectedId が更新される` | selectClient(1) を呼ぶ | selectedId が 1 になる | 正常系 |
| `selectClient が ClientDetail を返す` | getClient が詳細データを返す | 戻り値に scenario が含まれる | 正常系 |
| `selectClient で getClient が失敗したら error にメッセージが入り selectedId は変わらない` | getClient が throw する | error が非 null、selectedId が変更前のまま | 異常系 |

#### `describe('useClients - saveClient')`

目的: 新規保存で一覧が更新され、保存したクライアントが選択される

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `saveClient で postClient を呼び、一覧が再取得される` | postClient 成功 | clients に新しいクライアントが含まれる | 正常系 |
| `saveClient 後に selectedId が新規クライアントの id になる` | postClient が `{id: 3}` を返す | selectedId が 3 | 正常系 |
| `saveClient で postClient が失敗したら error にメッセージが入る` | postClient が throw する | error が非 null | 異常系 |

#### `describe('useClients - overwriteClient')`

目的: 選択中のクライアントを上書き保存する

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `overwriteClient で putClient を selectedId で呼ぶ` | selectedId が 1 の状態で呼ぶ | putClient が id=1 で呼ばれる | 正常系 |
| `overwriteClient 後に一覧が再取得される` | putClient 成功 | refreshClients が呼ばれ clients が更新される | 正常系 |
| `selectedId が null のとき overwriteClient を呼ぶとエラーになる` | selectedId が null | error にメッセージが入る（API は呼ばれない） | 境界値 |

#### `describe('useClients - deleteClient')`

目的: クライアント削除で一覧が更新され、選択がクリアされる

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `deleteClient で一覧が再取得される` | deleteClient 成功 | clients から削除対象が消えている | 正常系 |
| `削除したクライアントが selectedId と一致する場合、selectedId が null になる` | selectedId=1 で deleteClient(1) | selectedId が null | 正常系 |
| `削除したクライアントが selectedId と一致しない場合、selectedId は変わらない` | selectedId=2 で deleteClient(1) | selectedId が 2 のまま | 正常系 |
| `deleteClient が失敗したら error にメッセージが入る` | deleteClient が throw する | error が非 null | 異常系 |

### Fixture・前提条件

- API client 関数（`getClients`, `getClient`, `postClient`, `putClient`, `deleteClient`）を `vi.mock('../../api/client')` でモック
- `renderHook` + `act` + `waitFor` を使用

### 実装者へのノート

- API エラーの `kind` をユーザー向けメッセージに変換するロジックは hook 内に持つ（`App.tsx` の `errorMessage` 変換と同じパターン）
- `refreshClients` は `saveClient` / `overwriteClient` / `deleteClient` の成功時に内部で呼ぶ

---

## テスト対象 4: ClientManager コンポーネント

### テスト対象シグネチャ（新規）

```typescript
// components/ClientManager/ClientManager.tsx
interface ClientManagerProps {
  onLoad: (scenario: SimulateRequestBody) => void;  // 読み込み時にフォーム復元を親に通知
  getCurrentScenario: () => SimulateRequestBody;     // 現在のフォーム値を取得
}
```

### テストファイル

`frontend/src/__tests__/components/ClientManager.test.tsx`

### テストクラス一覧

#### `describe('ClientManager - 初期表示')`

目的: コンポーネントの初期状態が正しいことを検証する

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `ドロップダウン・保存・名前を付けて保存・削除ボタンが表示される` | 初期表示 | 4つの UI 要素が存在する | 正常系 |
| `クライアント未選択のとき削除ボタンが無効化されている` | 初期表示（selectedId が null） | 削除ボタンが disabled | 正常系 |

#### `describe('ClientManager - クライアント選択')`

目的: ドロップダウンからクライアントを選択するとデータが復元される

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `ドロップダウンからクライアントを選択すると onLoad が呼ばれる` | ドロップダウンで "田中" を選択 | onLoad が scenario データで呼ばれる | 正常系 |
| `選択後にドロップダウンの値が選択したクライアント名になる` | "田中" を選択 | ドロップダウンの表示値が "田中" | 正常系 |

#### `describe('ClientManager - 保存')`

目的: 保存ボタンの動作が選択状態に応じて変わる

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `クライアント選択中に保存ボタンを押すと上書き保存される` | selectedId が 1 の状態で保存ボタン押下 | putClient が呼ばれる（SaveDialog は表示されない） | 正常系 |
| `クライアント未選択で保存ボタンを押すと SaveDialog が表示される` | selectedId が null の状態で保存ボタン押下 | 名前入力ダイアログが表示される | 正常系 |

#### `describe('ClientManager - 名前を付けて保存')`

目的: 名前入力ダイアログで新規保存できる

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `名前を付けて保存ボタンを押すと SaveDialog が表示される` | ボタン押下 | 名前入力ダイアログが表示される | 正常系 |
| `SaveDialog で名前を入力して保存するとクライアント一覧が更新される` | 名前 "山田" を入力 → 保存 | postClient が呼ばれ、ドロップダウンに "山田" が追加される | 正常系 |
| `SaveDialog で空文字のまま保存しようとすると保存されない` | 名前を空のまま保存ボタン | postClient が呼ばれない | 境界値 |
| `SaveDialog でキャンセルすると何も起きない` | キャンセルボタン押下 | postClient が呼ばれない、ダイアログが閉じる | 正常系 |

#### `describe('ClientManager - 削除')`

目的: 確認ダイアログを経て削除できる

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `削除ボタンを押すと確認ダイアログが表示される` | selectedId が 1 の状態で削除ボタン押下 | 確認ダイアログが表示される | 正常系 |
| `確認ダイアログで「はい」を押すと削除される` | 確認ダイアログで「はい」 | deleteClient が呼ばれ、ドロップダウンから消える | 正常系 |
| `確認ダイアログで「いいえ」を押すと削除されない` | 確認ダイアログで「いいえ」 | deleteClient が呼ばれない、ダイアログが閉じる | 正常系 |
| `クライアント未選択のとき削除ボタンが押せない` | selectedId が null | 削除ボタンが disabled | 境界値 |

#### `describe('ClientManager - エラー表示')`

目的: API エラー時にユーザーにフィードバックする

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `保存が失敗したらエラーメッセージが表示される` | postClient が throw | エラーメッセージが画面に表示される | 異常系 |
| `削除が失敗したらエラーメッセージが表示される` | deleteClient が throw | エラーメッセージが画面に表示される | 異常系 |
| `クライアント選択が失敗したらエラーメッセージが表示される` | getClient が throw | エラーメッセージが画面に表示される | 異常系 |

### Fixture・前提条件

- `useClients` hook を `vi.mock` するか、API 関数レベルでモックするかは実装者の判断（推奨: API 関数レベルでモック）
- `render(<ClientManager onLoad={vi.fn()} getCurrentScenario={vi.fn()} />)` で MUI の `ThemeProvider` が必要な場合はラッパーを用意
- `userEvent` で操作（click, type）
- MUI の `Select` コンポーネントは `role="combobox"` で取得できる

### 実装者へのノート

- MUI の `Dialog` はポータルにレンダリングされるため、`screen.getByRole('dialog')` で取得する
- MUI の `Select` のテストでは `userEvent.click` でドロップダウンを開いてから `screen.getByRole('option')` で選択する
- コンポーネントテストは統合寄りになるため、API モックの設定が複雑になる場合は hook のテストで振る舞いを担保し、コンポーネントテストは UI の表示・操作に集中する

---

## テストファイル配置まとめ

```
frontend/src/__tests__/
  api/
    client.test.ts          ← 既存（postSimulate）
    clientCrud.test.ts      ← 新規（getClients, getClient, postClient, putClient, deleteClient）
  hooks/
    useScenario.test.ts     ← 新規（SET_ALL アクション）
    useClients.test.ts      ← 新規（クライアント管理状態）
  components/
    ClientManager.test.tsx  ← 新規（クライアント管理 UI）
    SimulateButton.test.tsx ← 既存
    CashFlowTable.test.tsx  ← 既存
```

## 新規追加する型（api/types.ts）

```typescript
export type ClientError =
  | { kind: 'network' }
  | { kind: 'server' }
  | { kind: 'not_found' }
  | { kind: 'validation'; detail: string };

export interface ClientSummary {
  id: number;
  name: string;
  updated_at: string;
}

export interface ClientDetail {
  id: number;
  name: string;
  scenario: SimulateRequestBody;
  created_at: string;
  updated_at: string;
}

export interface SaveClientBody {
  name: string;
  scenario: SimulateRequestBody;
}
```
