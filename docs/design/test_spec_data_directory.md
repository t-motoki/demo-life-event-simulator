# テスト仕様: 顧客データの置き場所を `data/` にまとめる

作成日: 2026-10-20（tester）
対象タスク: `tasks/todo.md`「実装計画: 開発基盤の安全設定」タスク0.5

---

## 目的

顧客データ（顧客 DB・出力した Excel・実データのシナリオ）の既定の置き場所を `data/` の下にまとめる。

- **解決すること**: 今は顧客 DB と出力の Excel がリポジトリ直下に散らばっている。実データのシナリオの置き場を足すと3か所になる。`.gitignore`・Read の deny・guard の対象を `data/` 1か所にし、置き場所を名前で分かるようにする（`CLAUDE.md` コア原則「構成は直感的に」・`docs/rules/00_workflow.md`「配置の原則」）
- **成功した状態**: 何も指定せずに API サーバーを起動したり CLI で Excel を出力したりすると、顧客データは `data/clients.db`・`data/output/` に置かれる。フォルダが無くても失敗しない。`data/` の下は何も git に入らない
- **失敗した状態**: 既定の動作でリポジトリ直下に `clients.db` や `cf_simulation_*.xlsx` ができる／`data/` が無いと起動や出力でエラーになる／Electron 版の DB の場所が変わる／計算結果・API の応答が変わる

## FP 確認事項

**無し。** このタスクはファイルの置き場所だけを変える。計算モデル（`src/domain/`）・API の応答の中身・Excel の中身（シート構成・列・値）・ファイル名（`cf_simulation_YYYYMMDD.xlsx`）には触れない。

---

## 今の振る舞い（実装を読んで確認した事実）

| 項目 | 今の実装 | 場所 |
|---|---|---|
| DB の既定パス | `LES_DB_PATH` が無ければ `clients.db` | `src/api/dependencies.py` `_get_repository()` |
| Repository の既定 URL | `sqlite:///clients.db` | `src/db/sqlite_repository.py` `SqliteClientRepository.__init__` |
| Excel の既定の出力先 | `output_dir="."` | `src/output/excel_writer.py` `write_excel()` |
| CLI からの呼び出し | `write_excel(scenario, rows)`（`output_dir` を渡さない＝既定の `.`） | `src/main.py` |
| 出力先フォルダが無いとき | 作らない（`wb.save` が `FileNotFoundError`） | `write_excel()` |
| DB の親フォルダが無いとき | 作らない（SQLite が `unable to open database file` で失敗。`create_all` は `__init__` の中なので、Repository を作った時点で失敗する） | `SqliteClientRepository.__init__` |
| 相対パスの基準 | **作業ディレクトリ**（SQLite の相対 URL も `Path(".")` も、プロセスの作業ディレクトリから解決される） | — |
| Electron 版 | `LES_DB_PATH` を `app.getPath('userData')/clients.db`（絶対パス）で明示。開発モードの `cwd` はリポジトリ直下 | `electron/main.js` |

補足: 入口は `python -m src.main <yaml>`（CLI）と `uvicorn src.api.main:app`（API）。どちらも `src` パッケージを解決するために、作業ディレクトリがリポジトリ直下であることを前提にしている。

---

## 振る舞い仕様

以下、「相対パス」は作業ディレクトリ基準とする（今の振る舞いを変えない。「運営者の決定」1）。

### A. 顧客 DB の場所（`src/api/dependencies.py`）

| # | 条件 | 操作 | 期待される振る舞い | 分類 |
|---|---|---|---|---|
| A1 | `LES_DB_PATH` が未設定 | Repository を取得する | `data/clients.db` を使う（作業ディレクトリ基準）。直下に `clients.db` はできない | 正常系 |
| A2 | `LES_DB_PATH` が未設定・`data/` が無い | Repository を取得する | `data/` を作り、`data/clients.db` ができる。エラーにならない | 境界値 |
| A3 | `LES_DB_PATH` が未設定・`data/` が既にある（中に別のファイルがある） | Repository を取得する | 既存のファイルを消さない・変えない。`data/clients.db` を使う | 境界値 |
| A4 | `LES_DB_PATH` に絶対パスを明示（Electron 版） | Repository を取得する | その値をそのまま使う。`data/` は作らない | 正常系（回帰防止） |
| A5 | `LES_DB_PATH` に親フォルダが無いパスを明示 | Repository を取得する | 親フォルダを作り、そのパスの DB を使う。`data/` は作らない（「運営者の決定」2） | 境界値 |
| A6 | `LES_DB_PATH` が空文字 | Repository を取得する | 今は `sqlite:///`（＝メモリ DB 扱い）になる。この挙動は今回変えない。フォルダも作らない（範囲外。気づいた点として記録） | 異常系（回帰防止） |

### B. Repository の既定 URL（`src/db/sqlite_repository.py`）

| # | 条件 | 操作 | 期待される振る舞い | 分類 |
|---|---|---|---|---|
| B1 | `db_url` を渡さない | `SqliteClientRepository()` | `TypeError` になる。Repository は既定値を持たない（既定値は A の1か所だけ。既定値が2か所でずれない） | 異常系 |
| B2 | `db_url="sqlite:///:memory:"` | 生成する | 今どおりメモリ DB（StaticPool）。ファイルもフォルダも作らない | 回帰防止 |
| B3 | `db_url` にファイルの URL を明示 | 生成する | その URL を使う | 回帰防止 |

既定値は1か所にまとめ、Repository は `db_url` 必須にする（「運営者の決定」3）。外から見た既定（`data/clients.db`）は A1 で確かめる。

### C. Excel の出力先（`src/output/excel_writer.py`・`src/main.py`）

| # | 条件 | 操作 | 期待される振る舞い | 分類 |
|---|---|---|---|---|
| C1 | `output_dir` を渡さない | `write_excel(scenario, rows)` | `data/output/cf_simulation_YYYYMMDD.xlsx` に書き、そのパスを返す。直下に xlsx はできない | 正常系 |
| C2 | `output_dir` を渡さない・`data/output/` が無い（`data/` も無い） | `write_excel` | `data/output/` を親ごと作って書く。エラーにならない | 境界値 |
| C3 | `output_dir` に既存のフォルダを明示（既存テストの `tmp_path`） | `write_excel` | 今どおりそのフォルダに書く。`data/` は作らない | 回帰防止 |
| C4 | `output_dir` に存在しないフォルダを明示 | `write_excel` | そのフォルダを親ごと作って書く（C2 と同じ扱い） | 境界値 |
| C5 | `output_dir` に既存の**ファイル**を明示 | `write_excel` | エラーになる（黙って別の場所に書かない）。メッセージの文言は問わない | 異常系 |
| C6 | 同じ日に2回出力 | `write_excel` ×2 | 今どおり同じファイル名で上書き（ファイル名の規則は変えない） | 回帰防止 |
| C7 | 正しいシナリオ YAML | `python -m src.main data/scenarios/<名前>.yaml` | `data/output/cf_simulation_YYYYMMDD.xlsx` ができ、標準出力に「Excelファイルを生成しました: data/output/cf_simulation_YYYYMMDD.xlsx」と出る。終了コード 0 | 正常系 |
| C8 | サンプルの `scenario.yaml` | `python -m src.main scenario.yaml` | 出力先は C7 と同じ `data/output/`（入力の場所で出力先は変わらない） | 正常系 |
| C9 | 存在しない YAML | `python -m src.main` | 今どおりエラー終了。`data/output/` を作らない（入力の読み込み・検証に失敗したら出力フォルダも作らない） | 異常系 |

### D. 変えないこと（回帰防止）

| # | 確認すること |
|---|---|
| D1 | Excel の中身（3シート・列・値）は変わらない → 既存の `tests/output/test_excel_writer.py` がそのまま通る |
| D2 | API の応答（`/simulate`・`/clients`・`/pdf`・`/comment`・`/health`）は変わらない → 既存の `tests/api/` がそのまま通る |
| D3 | PDF はダウンロードとして返すだけでファイルに書かない（`data/output/` にも書かない） |
| D4 | 計算モデル（`src/domain/`）に差分が無い |
| D5 | 全テスト（`.venv/bin/python -m pytest`）が通り、実行後にリポジトリ直下に `clients.db`・`*.xlsx`・`data/` が**新しく**できていない |

### E. git の扱い（`.gitignore`）

`.gitignore` には既に `*.db`・`*.xlsx` がある。それでも `data/` を足すのは、**拡張子で拾えない実データのシナリオ（`data/scenarios/*.yaml`）を守るため**。YAML は git に入れる対象（直下のサンプル `scenario.yaml`）と同じ拡張子なので、拡張子では区別できない。置き場所で区別する。

| # | 条件 | 確認 | 期待 |
|---|---|---|---|
| E1 | `data/scenarios/x.yaml` を置く | `git check-ignore -v data/scenarios/x.yaml` | `.gitignore` の `data/` の行で無視される |
| E2 | `data/clients.db`・`data/output/x.xlsx` | 同上 | 無視される（`data/` の行でも `*.db`・`*.xlsx` の行でもよい） |
| E3 | 直下の `scenario.yaml` | `git ls-files scenario.yaml` | 今どおり git 管理のまま |
| E4 | `git ls-files data/` | — | 何も出ない |

E は `.gitignore` の確認なので pytest にしなくてよい（engineer が実行して結果を reviewer に見せる）。pytest にする場合は `git` が無い環境で skip する。

### F. README

| # | 確認すること |
|---|---|
| F1 | 「データの置き場所」の節がある |
| F2 | 実データのシナリオは `data/scenarios/` に置き、`python -m src.main data/scenarios/<名前>.yaml` で実行すると書いてある |
| F3 | サンプルは直下の `scenario.yaml` と書いてある |
| F4 | 出力は `data/output/`、開発時の顧客 DB は `data/clients.db`、デスクトップアプリ版はアプリのデータフォルダ（`userData`）と書いてある |
| F5 | `data/` の下は git に入らないと書いてある |
| F6 | コマンドはリポジトリ直下で実行する前提だと書いてある（相対パスは作業ディレクトリ基準。「運営者の決定」1） |
| F7 | `data/scenarios/` は `mkdir -p data/scenarios` で自分で作ると書いてある（コードでは作らない。「運営者の決定」4） |

### G. 手引き（`docs/guides/setup-windows.md`）

| # | 確認すること |
|---|---|
| G1 | 「5. ツールの実行」の手順3が、Excel の出力先を `data\output` フォルダと書いている（「運営者の決定」6。手順2の `python src/main.py` はバックログで、このタスクでは直さない） |

---

## 既存のテストへの影響（grep の結果）

`grep -rn "write_excel|LES_DB_PATH|clients.db|SqliteClientRepository(|get_client_repository|output_dir|chdir|cf_simulation" tests/` で洗い出した。

| テスト | 既定値への依存 | 影響 |
|---|---|---|
| `tests/output/test_excel_writer.py` | 全呼び出しが `output_dir=tmp_path` を明示 | 無し（C3 の回帰防止として働く） |
| `tests/db/test_sqlite_repository.py` | `db_url="sqlite:///:memory:"` を明示 | 無し（B2） |
| `tests/api/test_clients.py` | `dependency_overrides` でメモリ DB に差し替え | 無し |
| `tests/api/conftest.py`・`test_pdf.py`・`test_comment.py`・`test_simulate.py`・`test_health.py` | `TestClient(app)` を差し替え無しで使うが、`/clients` を呼ばない。`_get_repository()` は最初に `/clients` を呼んだときに作られる（`lru_cache`）ので DB は作られない | 無し |
| `tests/api/test_pdf.py` の `cf_simulation_\d{8}\.pdf` | ファイル名だけの確認（PDF はファイルに書かない） | 無し |
| `src/main.py` のテスト | **存在しない** | 新規に必要（C7〜C9） |
| `src/api/dependencies.py` のテスト | **存在しない** | 新規に必要（A1〜A5） |

- 既定のパス・出力先に依存している既存テストは**無い**
- 既存テストがリポジトリ直下に `clients.db` や xlsx を作る経路は**無い**（xlsx は全部 `tmp_path`、DB は全部メモリ）。直下の `clients.db`（最終更新 2026-06-18）と `cf_simulation_*.xlsx`（2026-04-07・2026-04-11）は、開発時に API サーバーや CLI を手で動かしてできたものと見られる（中身は開いていない）
- `pytest.ini` に `testpaths`・`rootdir` 指定は無い。pytest はリポジトリ直下で実行される前提

---

## テストファイル

最終の割り当て（テストメソッドの一覧を含む）は設計書 `docs/design/data_directory.md`「テスト設計」が正本。

| ファイル | 対象 | 振る舞い |
|---|---|---|
| `tests/api/test_dependencies.py`（新規） | `_get_repository()` | A1〜A6 |
| `tests/db/test_sqlite_repository.py`（追記） | `SqliteClientRepository` の `db_url` | B1・B3（B2 は既存で担保） |
| `tests/output/test_excel_writer.py`（追記） | `write_excel()` の出力先 | C1〜C6（C3 は既存で担保） |
| `tests/test_main.py`（新規） | `src.main.main()` | C7〜C9。`tests/` は `src/` の構成を写すので直下に置き、`docs/rules/04_testing.md` に足す |

テストクラス（tester の案。設計書で A5・A6・B1・C6・C8 のテストを足している）:

#### `TestDefaultDbPath`（`tests/api/test_dependencies.py`）
目的: DB の既定の置き場所と、明示したときの優先

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_LES_DB_PATH未設定なら_data配下のclients_dbを使う` | 作業ディレクトリ＝`tmp_path`・`LES_DB_PATH` を消す | `tmp_path/data/clients.db` ができ、`tmp_path/clients.db` は無い | 正常系 |
| `test_dataフォルダが無くても作って起動できる` | 同上・`data/` 無し | 例外なし・`data/` ができる | 境界値 |
| `test_dataフォルダの既存ファイルを消さない` | `data/scenarios/x.yaml` を先に置く | 実行後も残っている | 境界値 |
| `test_LES_DB_PATHを明示したらその場所を使う` | `LES_DB_PATH=tmp_path/userdata/clients.db` | そのファイルができ、`data/` はできない | 正常系 |

#### `TestDefaultOutputDir`（`tests/output/test_excel_writer.py`）
目的: Excel の既定の出力先とフォルダの作成

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_出力先を渡さなければdata_outputに書く` | 作業ディレクトリ＝`tmp_path` | 返り値が `data/output/cf_simulation_YYYYMMDD.xlsx`、ファイルがある、直下に xlsx が無い | 正常系 |
| `test_出力先フォルダが無ければ親ごと作る` | `data/` 無し | 例外なし・ファイルがある | 境界値 |
| `test_存在しない出力先を明示したら作って書く` | `output_dir=tmp_path/a/b` | `a/b/` ができファイルがある | 境界値 |
| `test_出力先にファイルを渡したらエラー` | `output_dir` に既存ファイル | 例外 | 異常系 |

#### `TestMainOutput`（CLI）
目的: CLI の出力先

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_シナリオを渡すとdata_outputにExcelができる` | `sys.argv` にシナリオ（`tmp_path` にサンプルを写したもの） | `data/output/` にファイル・標準出力にそのパス | 正常系 |
| `test_読み込みに失敗したら出力フォルダを作らない` | 存在しない YAML | `SystemExit(1)`・`data/output/` が無い | 異常系 |

## Fixture・前提条件

- **リポジトリ直下を汚さない**: 既定値のテストはすべて `monkeypatch.chdir(tmp_path)` で作業ディレクトリを一時フォルダに移してから行う。実行後にリポジトリ直下に `data/`・`clients.db`・xlsx が新しくできていないこと（D5）
- `LES_DB_PATH` は `monkeypatch.delenv("LES_DB_PATH", raising=False)` / `monkeypatch.setenv` で制御する。開発者の環境変数に左右されないようにする
- 実データ・既存の `clients.db`・xlsx をテストに使わない。シナリオは直下のサンプル `scenario.yaml` を `tmp_path` に写すか、テスト内で組み立てる
- 日付を含むファイル名は `datetime.now().strftime("%Y%m%d")` で期待値を作るか、固定する（日付またぎで落ちないように）

## engineer へのノート

- **`_get_repository()` は `lru_cache` で1つを共有している**。テストの前後で `_get_repository.cache_clear()` を呼ばないと、先に作られた Repository（別の作業ディレクトリ・別の `LES_DB_PATH`）が残り、テスト同士が干渉する。fixture で前後に必ず呼ぶ
- SQLite は親フォルダが無いと `unable to open database file` で失敗する。`todo.md` は「出力先のフォルダが無ければ作る」とだけ書いているが、**DB の `data/` も作らないと A2 が満たせない**（`data/` は git に入らないので、clone 直後は必ず無い）
- フォルダの作成は `Path.mkdir(parents=True, exist_ok=True)` 相当。既存のフォルダ・ファイルは変えない
- C9: フォルダの作成は出力の直前（`write_excel` の中）で行い、読み込み・検証の前には作らない
- 既定値（`data/clients.db`・`data/output`）は `src/data_paths.py` 1か所に定義する。`sqlite_repository.py` は既定値を持たない（設計書 `docs/design/data_directory.md`）
- 既存の直下の `clients.db`・`cf_simulation_*.xlsx` は**開かない・動かさない**（運営者が自分で `data/` に移す）。テストでも参照しない
- 完了時に古い記述を直す: `docs/rules/00_workflow.md`「配置の原則」の「移行中」の行を消す、`tasks/todo.md` の「前提として分かっていること」の `clients.db` の行、`docs/guides/setup-windows.md` の Excel の出力先（G1）。過去の設計書（`docs/design/ep4.4_design.md`・`ep4.5_client_persistence_design.md`）は当時の記録なので直さない

---

## 運営者の決定（2026-10-20・仕様の確認点への回答）

1. **相対パスの基準**: 作業ディレクトリ基準のまま（今の振る舞い）。CLI（`python -m src.main`）も API（`uvicorn src.api.main:app`）も作業ディレクトリがリポジトリ直下でないと `src` を解決できないので、実際の運用では同じ場所になる。README に「リポジトリ直下で実行する」と書く（F6）
2. **`LES_DB_PATH` を明示したときも、親フォルダが無ければ作る**（A5）。既定値と同じ扱い。Electron の `userData` はアプリ起動時に既にあるので Electron 版は変わらない
3. **DB の既定値は1か所にまとめる**。`src/db/sqlite_repository.py` の既定値をなくし、Repository は `db_url` 必須にする（B1）。既定値の置き場所は設計書 `docs/design/data_directory.md`（`src/data_paths.py` を提案）
4. **`data/scenarios/` は README に `mkdir -p data/scenarios` と書く**。コードでは作らない（入力の置き場なのでツールが勝手に作る理由が無い。`.gitkeep` は使わない）（F7）
5. **空 DB の警告コードは足さない**。マージ前に運営者が直下の `clients.db` と `cf_simulation_*.xlsx` を `data/` に移す（新しいコードで先に API サーバーを起動すると、空の `data/clients.db` ができて登録済みのクライアントが見えなくなったように見えるため）
6. **`docs/guides/setup-windows.md` の Excel の出力先の記述はこのタスクで直す**（G1）。同じ節の `python src/main.py`（引数無し・`-m` 無し。今の実装でも動かない）はバックログ

## 気づいた点（範囲外・記録のみ）

- A6: `LES_DB_PATH=""` でメモリ DB になり、再起動で保存したクライアントが消える。今回は変えない
- README の「ステータス」「使い方（実装後に追記）」が実装済みの現状と合っていない。「データの置き場所」の節を足すときに、使い方との重複に注意する
