# テスト仕様: クライアントデータ永続化（ep4.5）

作成日: 2026-06-17

---

## 目的

FPがクライアントごとにシミュレーションの入力内容（SimulateRequest の JSON）を保存・呼び出し・更新・削除できるようにする。これにより、面談のたびにデータを再入力する必要がなくなる。

### 成功した状態

- FPがクライアントを名前付きで保存し、後日呼び出してシミュレーションを再実行できる
- 保存データの一覧から目的のクライアントを素早く見つけられる
- 不要になったクライアントデータを削除できる

### 失敗した状態

- 保存したはずのデータが呼び出せない
- 存在しないクライアントへの操作がサイレントに無視される（エラーが返らない）
- 名前なしのクライアントが作成されてしまい、一覧で識別できない

---

## 1. Repository レイヤー

### テスト対象

```python
# src/db/client_repository.py（抽象クラス）
class ClientRepository(ABC):
    def create(self, name: str, scenario: dict) -> ClientRecord
    def list_all(self) -> list[ClientSummary]
    def get(self, client_id: str) -> ClientRecord | None
    def update(self, client_id: str, name: str, scenario: dict) -> ClientRecord
    def delete(self, client_id: str) -> None

# src/db/sqlite_repository.py（実装）
class SqliteClientRepository(ClientRepository): ...
```

> `ClientRecord`: id, name, scenario (dict), created_at, updated_at を持つデータクラス
> `ClientSummary`: id, name, updated_at を持つデータクラス（一覧表示用）

### テストファイル

`tests/db/test_sqlite_repository.py`

### Fixture・前提条件

- `repository` fixture: `:memory:` SQLite で `SqliteClientRepository` を生成する。テストごとにインスタンスを新規作成して独立性を保証する
- `sample_scenario` fixture: `tests/api/conftest.py` の `minimal_request` と同等の dict を返す

---

### テストクラス一覧

#### `TestCreate`

目的: クライアントの新規作成が正しく動作すること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_create_when_valid_name_and_scenario_then_returns_record` | name="田中太郎", scenario=sample_scenario | ClientRecord が返る。id が非空文字列。name, scenario が入力と一致 | 正常系 |
| `test_create_when_valid_then_sets_timestamps` | name="田中太郎", scenario=sample_scenario | created_at と updated_at が datetime 型でセットされる。created_at == updated_at | 正常系 |
| `test_create_when_called_twice_then_ids_are_unique` | 同じ name/scenario で2回作成 | 2つの異なる id が返る | 正常系 |
| `test_create_when_name_is_empty_then_raises_error` | name="", scenario=sample_scenario | ValueError を送出 | 異常系 |
| `test_create_when_name_is_whitespace_only_then_raises_error` | name="   ", scenario=sample_scenario | ValueError を送出 | 異常系 |

#### `TestListAll`

目的: クライアント一覧の取得が正しく動作すること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_list_all_when_empty_then_returns_empty_list` | データなし | 空リスト [] が返る | 境界値 |
| `test_list_all_when_two_clients_then_returns_two_summaries` | 2件作成済み | ClientSummary が2件返る。各 summary に id, name, updated_at が含まれる。scenario は含まれない | 正常系 |
| `test_list_all_returns_ordered_by_updated_at_desc` | 3件を時間差で作成 | updated_at の降順で返る（最近更新したものが先頭） | 正常系 |

#### `TestGet`

目的: 単体クライアントの取得が正しく動作すること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_get_when_existing_id_then_returns_record_with_scenario` | 作成済みの id | ClientRecord が返る。scenario が保存時の dict と一致 | 正常系 |
| `test_get_when_nonexistent_id_then_returns_none` | 存在しない UUID 文字列 | None が返る | 異常系 |

#### `TestUpdate`

目的: クライアントデータの更新が正しく動作すること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_update_when_existing_id_then_name_and_scenario_are_updated` | 作成済みの id で name と scenario を変更 | get で取得した結果が新しい name と scenario を持つ | 正常系 |
| `test_update_when_existing_id_then_updated_at_changes` | 作成済みの id で更新 | updated_at が created_at より後になる。created_at は変わらない | 正常系 |
| `test_update_when_nonexistent_id_then_raises_error` | 存在しない UUID 文字列 | ValueError (or KeyError) を送出 | 異常系 |
| `test_update_when_name_is_empty_then_raises_error` | name="" | ValueError を送出 | 異常系 |

#### `TestDelete`

目的: クライアントデータの削除が正しく動作すること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_delete_when_existing_id_then_get_returns_none` | 作成済みの id を削除後に get | None が返る | 正常系 |
| `test_delete_when_existing_id_then_list_all_excludes_it` | 2件中1件を削除 | list_all が1件だけ返す | 正常系 |
| `test_delete_when_nonexistent_id_then_raises_error` | 存在しない UUID 文字列 | ValueError (or KeyError) を送出 | 異常系 |

### 実装者へのノート

- テストは `:memory:` SQLite を使い、ファイルI/Oに依存しない
- `created_at` / `updated_at` の検証で時間差を確実に作りたい場合は `time.sleep(0.01)` を使うか、datetime を mock する
- scenario は dict として保存・復元されることを検証する（JSON 文字列ではなく dict で返ること）
- UUID の形式チェックは不要（id が非空で一意であることだけ検証すれば十分）

---

## 2. API レイヤー

### テスト対象

```python
# src/api/routes/clients.py
GET    /clients         → クライアント一覧（id, name, updated_at のみ）
GET    /clients/{id}    → 単体取得（scenario 含む）
POST   /clients         → 新規作成（name + scenario）
PUT    /clients/{id}    → 更新（name + scenario）
DELETE /clients/{id}    → 削除
```

### テストファイル

`tests/api/test_clients.py`

### Fixture・前提条件

- 既存の `client` fixture（`tests/api/conftest.py` の TestClient）を使う
- `minimal_request` fixture を scenario の値として使い回す
- Repository は DI で注入される前提。API テストでは `:memory:` SQLite の実リポジトリを使う（mock しない）

---

### テストクラス一覧

#### `TestPostClients`

目的: POST /clients でクライアントが新規作成できること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_post_clients_when_valid_then_returns_201` | `{"name": "田中太郎", "scenario": minimal_request}` | HTTP 201。レスポンスに id, name, created_at, updated_at が含まれる | 正常系 |
| `test_post_clients_when_valid_then_scenario_is_persisted` | 作成後に GET /clients/{id} | scenario の内容が POST 時と一致 | 正常系 |
| `test_post_clients_when_name_missing_then_returns_422` | `{"scenario": minimal_request}`（name なし） | HTTP 422 | 異常系 |
| `test_post_clients_when_name_empty_then_returns_422` | `{"name": "", "scenario": minimal_request}` | HTTP 422 | 異常系 |
| `test_post_clients_when_scenario_missing_then_returns_422` | `{"name": "田中太郎"}`（scenario なし） | HTTP 422 | 異常系 |

#### `TestGetClientsList`

目的: GET /clients でクライアント一覧が取得できること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_get_clients_when_empty_then_returns_200_with_empty_list` | データなし | HTTP 200。空リスト `[]` | 境界値 |
| `test_get_clients_when_two_exist_then_returns_summaries` | 2件作成済み | HTTP 200。2件の配列。各要素に id, name, updated_at のみ含まれる。scenario は含まれない | 正常系 |

#### `TestGetClientDetail`

目的: GET /clients/{id} で単体クライアントが取得できること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_get_client_when_existing_id_then_returns_200_with_scenario` | 作成済みの id | HTTP 200。レスポンスに id, name, scenario, created_at, updated_at が含まれる | 正常系 |
| `test_get_client_when_nonexistent_id_then_returns_404` | 存在しない UUID | HTTP 404 | 異常系 |

#### `TestPutClients`

目的: PUT /clients/{id} でクライアントデータが更新できること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_put_client_when_existing_id_then_returns_200` | 作成済みの id で name と scenario を変更 | HTTP 200。レスポンスの name, scenario が更新後の値 | 正常系 |
| `test_put_client_when_existing_id_then_updated_at_changes` | 更新前後で比較 | updated_at が更新前より後の値 | 正常系 |
| `test_put_client_when_nonexistent_id_then_returns_404` | 存在しない UUID | HTTP 404 | 異常系 |
| `test_put_client_when_name_empty_then_returns_422` | `{"name": "", "scenario": ...}` | HTTP 422 | 異常系 |

#### `TestDeleteClients`

目的: DELETE /clients/{id} でクライアントデータが削除できること

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_delete_client_when_existing_id_then_returns_204` | 作成済みの id | HTTP 204（No Content） | 正常系 |
| `test_delete_client_when_existing_id_then_get_returns_404` | 削除後に GET /clients/{id} | HTTP 404 | 正常系 |
| `test_delete_client_when_nonexistent_id_then_returns_404` | 存在しない UUID | HTTP 404 | 異常系 |

#### `TestClientsCORS`

目的: /clients エンドポイントに CORS ヘッダーが正しく付くこと

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_cors_header_on_get_clients` | Origin: http://localhost:3000 で GET /clients | access-control-allow-origin ヘッダーが付く | 正常系 |

### 実装者へのノート

- 既存の `tests/api/conftest.py` の `client` fixture と `minimal_request` fixture を使う
- API テストでは Repository を mock せず、`:memory:` SQLite の実リポジトリを DI で注入する。FastAPI の `app.dependency_overrides` を使って fixture でセットアップする
- POST のレスポンスステータスは 201 (Created)、DELETE は 204 (No Content) を期待する
- 404 のレスポンスボディには `{"detail": "..."}` 形式のエラーメッセージが含まれることを検証する
- `main.py` に `clients` ルーターの `include_router` 追加と、`allow_methods` への `PUT`, `DELETE` 追加が必要になる

---

## アクセプタンス基準（まとめ）

| # | 基準 | 検証レイヤー |
| --- | --- | --- |
| AC1 | クライアントを名前 + シナリオで新規作成できる | Repository + API |
| AC2 | クライアント一覧を取得できる（scenario を含まない軽量レスポンス） | Repository + API |
| AC3 | ID 指定で単体クライアントを取得できる（scenario 含む） | Repository + API |
| AC4 | ID 指定でクライアントの name と scenario を更新できる | Repository + API |
| AC5 | ID 指定でクライアントを削除できる | Repository + API |
| AC6 | 存在しない ID への get/update/delete が適切なエラーを返す（サイレント無視しない） | Repository + API |
| AC7 | name が空文字・空白のみの場合は作成・更新を拒否する | Repository + API |
| AC8 | created_at は作成時に設定され、更新しても変わらない。updated_at は更新のたびに変わる | Repository |
| AC9 | CORS ヘッダーが /clients エンドポイントにも付く | API |
