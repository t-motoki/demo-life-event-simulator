# テスト仕様: 編集フック（テスト実行・FP 未確認の警告）を `.claude/hooks/` のスクリプトに作り直す

作成日: 2026-10-20（tester）
最終更新: 2026-10-24（設計書 `docs/design/edit_hooks.md` の確認点7件を「運営者の決定（設計の確認点）」として反映）
対象タスク: `tasks/todo.md`「実装計画: 開発基盤の安全設定」タスク2

---

## 目的

`src/` を編集したら自動でテストが走り、`src/domain/`（計算ロジック）を編集する前に FP 未確認事項が残っていることに気づける状態を、**実際に動く形で**取り戻す。

- **解決すること**: `.claude/settings.json` の2つのフックは、Claude Code が渡さない環境変数 `$CLAUDE_TOOL_INPUT_FILE_PATH` を見ており、仮に値が入っても絶対パスなので `^src/` に一致しない。つまり今は動いていない。さらに、ただの標準出力は Claude に届かないので、動いたとしても結果が伝わらない。リポジトリの絶対パスが直書きされ、pytest は venv 外の `python` を使っている
- **成功した状態**:
  - `src/` 配下のファイルを Edit / Write した直後に、`.venv` の pytest（`slow` を除く）が走り、結果が Claude に届く。失敗したときは、どのテストが落ちたかが分かる要約が届く
  - `src/domain/` 配下を Edit / Write する前に、要件定義書に `TODO: FPに確認` が残っていれば警告が Claude に届く。編集は止まらない
  - どんな入力・環境でも、フックが原因で作業が止まらない（fail-open）
  - 設定にリポジトリの絶対パスが残らない。別の場所に clone しても動く
- **失敗した状態**: 対象外のパス（`frontend/src/`・`tests/` など）で pytest が走る／対象のパスで走らない／結果が Claude に届かない／壊れた入力でフックが例外を出して編集が止まる・エラー表示になる／警告フックが編集を止める（exit 2 や `permissionDecision` を返す）／venv 外の Python で走る

## FP 確認事項

**無し。** 開発用のフックだけを変える。計算モデル・`src/`・要件定義書の中身には触れない。

---

## 今の振る舞い（実装を読んで確認した事実）

| 項目 | 今の設定（`.claude/settings.json`） | 問題 |
|---|---|---|
| PostToolUse（matcher `Edit\|Write`） | `$CLAUDE_TOOL_INPUT_FILE_PATH` が `^src/` に一致したら、リポジトリの絶対パスへ `cd` して `python -m pytest tests/ -q --tb=short 2>&1 \|\| true` | 環境変数は渡されない。値は絶対パス。`python` は venv 外。標準出力は Claude に届かない。`slow` を除いていない |
| PreToolUse（matcher `Edit\|Write`） | `^src/domain/` に一致し、`docs/spec/01_requirements.md` に `TODO: FPに確認` があれば警告文を echo | 上と同じく判定が効かない。echo は Claude に届かない |
| 終了コード | どちらも `\|\| true` で常に 0 | 残す（止めない） |

調べて分かった事実（2026-10-20）:

- Claude Code はフックの入力を**標準入力の JSON**で渡す（`{"tool_name": "Edit", "tool_input": {"file_path": "<絶対パス>", ...}, "cwd": ..., "hook_event_name": ...}`）。プロジェクトのルートは環境変数 `CLAUDE_PROJECT_DIR`
- Claude に届けるには、標準出力に `{"hookSpecificOutput": {"hookEventName": "<PostToolUse|PreToolUse>", "additionalContext": "..."}}` を1つだけ出して exit 0 する
- `.venv/bin/python -m pytest tests/ -q --tb=short -m "not slow"` は手元で **210 passed, 3 deselected・約8秒**
- **`docs/spec/01_requirements.md` には今 `TODO: FPに確認` が1つも無い**（FP 未確定事項は § 8 の表で管理されている。マーカーがあるのは `src/domain/education.py` などのコード側）。→ 警告フックは正しく作り直しても、今の要件定義書では発火しない（「運営者の決定」1）
- 警告文の `/fp-check` は LES に実在する（`.claude/skills/fp-check/SKILL.md`・git 管理）→ 警告文はそのまま残す
- `.claude/worktrees/` がリポジトリの中にある（worktree の `src/` はリポジトリの `src/` ではない）

---

## 振る舞い仕様

用語:

- **プロジェクト**: 環境変数 `CLAUDE_PROJECT_DIR` が指すフォルダ
- **パスの正規化**: `tool_input.file_path` が相対パスならプロジェクト基準で絶対パスにし、`..`・`.`・シンボリックリンクを解決する（プロセスの作業ディレクトリや JSON の `cwd` は使わない）。プロジェクトのパスも同じく解決してから比べる
- **配下**: 正規化したパスが `<プロジェクト>/src/` の下にある（フォルダ名の**要素単位**で比べる。文字列の前方一致ではない）。`<プロジェクト>/src` そのものは配下に含めない
- **何も返さない**: 標準出力が空で exit 0

### A. どのパスで発火するか（2フック共通の判定）

`post_tool_run_tests.py` は「`src/` 配下」、`pre_tool_fp_warning.py` は「`src/domain/` 配下」で発火する。発火しないときは何も返さない（pytest も実行しない・要件定義書も読まない）。

| # | `tool_input.file_path`（プロジェクト = `/p/les`） | テスト実行（`src/` 配下） | FP 警告（`src/domain/` 配下） | 分類 |
|---|---|---|---|---|
| A1 | `/p/les/src/main.py`（`src/` 直下） | 発火 | 発火しない | 正常系 |
| A2 | `/p/les/src/domain/education.py` | 発火 | 発火 | 正常系 |
| A3 | `/p/les/src/domain/sub/x.py`（`src/domain/` の更に下） | 発火 | 発火 | 境界値 |
| A4 | `/p/les/src/output/excel_writer.py`（`src/` の別の層） | 発火 | 発火しない | 正常系 |
| A5 | `/p/les/src/new_file.py`（まだ無いファイルを Write） | 発火 | — | 境界値 |
| A6 | `/p/les/src/README.md`（`.py` 以外） | 発火（拡張子では絞らない。今の振る舞いを残す。「運営者の決定」5） | — | 境界値 |
| A7 | `/p/les/tests/domain/test_x.py`（`tests/` 下） | 発火しない | 発火しない | 境界値 |
| A8 | `/p/les/docs/spec/01_requirements.md`（`src/` の外） | 発火しない | 発火しない | 正常系 |
| A9 | `/p/les/frontend/src/App.tsx`（名前に src を含む別フォルダ） | 発火しない | 発火しない | 境界値 |
| A10 | `/p/les/srcx/a.py`・`/p/les/src_old/a.py`（前方一致だけ同じ） | 発火しない | 発火しない | 境界値 |
| A11 | `/p/les/src/domainx/a.py`（`domain` の前方一致だけ同じ） | 発火 | 発火しない | 境界値 |
| A12 | `/p/les/src`（`src` フォルダそのもの） | 発火しない | 発火しない | 境界値 |
| A13 | `/p/les/.claude/worktrees/w1/src/main.py`（プロジェクト内の worktree） | 発火しない | 発火しない | 境界値 |
| A14 | `/other/repo/src/main.py`（プロジェクト外の絶対パス） | 発火しない | 発火しない | 異常系 |
| A15 | `/p/les-old/src/main.py`（プロジェクトのパスを前方一致で含む別フォルダ） | 発火しない | 発火しない | 境界値 |
| A16 | `src/domain/x.py`（相対パス） | 発火（プロジェクト基準で解決） | 発火 | 境界値 |
| A17 | 相対パス `src/x.py` で、プロセスの作業ディレクトリがプロジェクト以外 | 発火（作業ディレクトリに左右されない） | — | 境界値 |
| A18 | `/p/les/tests/../src/x.py`（`..` で `src/` に入る） | 発火 | — | 境界値 |
| A19 | `/p/les/src/../tests/x.py`（`..` で `src/` から出る） | 発火しない | 発火しない | 境界値 |
| A20 | `src/../../other/src/x.py`（`..` でプロジェクトの外へ出る） | 発火しない | 発火しない | 異常系 |
| A21 | `/p/les/./src/./domain/x.py`（`.` を含む） | 発火 | 発火 | 境界値 |
| A22 | プロジェクトがシンボリックリンク経由のパスで、`file_path` は実体側のパス（またはその逆） | 発火（両方を解決して比べる） | 発火（`src/domain/` のとき） | 境界値 |
| A23 | `/p/les/SRC/x.py`（大文字） | 発火しない（大文字小文字を区別する） | 発火しない | 境界値 |
| A24 | `file_path` キーが無い | 何も返さない | 何も返さない | 異常系 |
| A25 | `file_path` が空文字・空白だけ | 何も返さない（空文字をプロジェクト自身と解釈しない） | 何も返さない | 境界値 |
| A26 | `file_path` が文字列でない（`null`・数値・配列） | 何も返さない | 何も返さない | 異常系 |

判定は `tool_input.file_path` だけで行う。`tool_name` では絞らない（Edit / Write に絞るのは settings の matcher の役目。二重に持たない）。

### B. 壊れた入力・環境（fail-open）

基本は **fail-open**: 判定に必要なものが欠けていたら、何も返さず exit 0。標準エラーに1行の理由を書くのは可（exit 0 の標準エラーは Claude には届かず、作業も止めない）。

| # | 条件 | 期待される振る舞い（2フック共通） | 分類 |
|---|---|---|---|
| B1 | 標準入力が JSON でない（`not json`） | 何も返さない・exit 0・例外のトレースバックを出さない | 異常系 |
| B2 | 標準入力が空 | 同上 | 境界値 |
| B3 | JSON だがオブジェクトでない（`[]`・`"x"`・`null`） | 同上 | 異常系 |
| B4 | `tool_input` が無い | 同上 | 異常系 |
| B5 | `tool_input` がオブジェクトでない（文字列・`null`） | 同上 | 異常系 |
| B6 | 環境変数 `CLAUDE_PROJECT_DIR` が無い | 同上。**JSON の `cwd` やプロセスの作業ディレクトリで代用しない**（`cwd` はサブフォルダのことがあり、誤って別の場所の `src/` に反応する／別の場所で pytest を走らせるため） | 異常系 |
| B7 | `CLAUDE_PROJECT_DIR` が空文字 | 同上（B6 と同じ扱い） | 境界値 |
| B7a | `CLAUDE_PROJECT_DIR` が相対パス（例: プロジェクトのフォルダ名 `les` だけ。作業ディレクトリ基準で解決すればプロジェクトに当たる形） | 同上（B6 と同じ扱い。作業ディレクトリ基準で解決しない。「運営者の決定（設計の確認点）」3） | 境界値 |
| B8 | 標準入力の JSON に UTF-8 の日本語パスが入っている（`/p/les/src/domain/住宅.py`） | 正しく判定する（A2 と同じく発火） | 境界値 |
| B9 | フックの中で想定外の例外が起きた（どこで起きても） | 何も返さない・exit 0。exit 1 や 2 にしない | 異常系 |

**例外は無い。** 2フックはどちらも「気づかせる」ためのもので、守りの仕組み（止める仕組み）ではない。止める役目はタスク3の guard（こちらは止める側に倒す）と permissions が担う。ここで fail-closed にすると、壊れた入力1つで全ての編集が止まり、守るものが無いのに作業だけが止まる。

### C. テスト実行フック（`post_tool_run_tests.py`）

A で発火したときの振る舞い。

| # | 条件 | 期待される振る舞い | 分類 |
|---|---|---|---|
| C1 | 発火した | `<プロジェクト>/.venv/bin/python -m pytest tests/ -q --tb=short -m "not slow"` を、**作業ディレクトリ = プロジェクト**で1回だけ実行する（引数はこの並びのまま。`-m` の値は `not slow` の1引数） | 正常系 |
| C2 | pytest が成功（終了コード 0） | `hookEventName: "PostToolUse"` の additionalContext を返す。成功したことと、pytest の最後の要約行（例 `210 passed, 3 deselected in 6.41s`）を含む。短く保つ（全出力は入れない）。exit 0 | 正常系 |
| C3 | テストが失敗（終了コード 1） | additionalContext を返す。冒頭で失敗したと分かる。`FAILED <テストID>` の行と最後の要約行（例 `1 failed, 209 passed`）を含む。`--tb=short` のトレースバックも上限内で含む。exit 0（編集はもう済んでいるので止めない） | 正常系 |
| C4 | 組み立てた additionalContext（見出し＋改行＋pytest の出力）が上限（8,000 文字。定数で持つ。「運営者の決定」3）を超える | pytest の出力の末尾（要約行と `FAILED` の一覧がある側）を残し、先頭を切る。切ったことが分かる一文を入れる。**additionalContext 全体**の文字数が上限以下（上限は pytest の出力だけでなく全体に掛ける。「運営者の決定（設計の確認点）」2） | 境界値 |
| C5 | 組み立てた additionalContext 全体がちょうど上限 | 切らない（切ったという一文も入れない）。「運営者の決定（設計の確認点）」2 | 境界値 |
| C6 | 収集エラー（終了コード 2。import エラーなど） | 失敗として additionalContext を返す（エラーの末尾を含む）。exit 0 | 異常系 |
| C7 | テストが1件も集まらない（終了コード 5） | 「テストが見つからなかった」と分かる additionalContext を返す。成功扱いにしない。exit 0 | 境界値 |
| C8 | その他の終了コード（3・4 など） | 「pytest が異常終了した（終了コード N）」と出力の末尾を返す。exit 0 | 異常系 |
| C9 | `<プロジェクト>/.venv/bin/python` が無い | pytest を実行しない。「`.venv/bin/python` が見つからないのでテストを実行していない」と分かる additionalContext を返す（venv の作り方を一言添えてよい）。venv 外の `python`・`python3` に**代えない**。exit 0 | 異常系 |
| C10 | `.venv/bin/python` はあるが起動できない（実行権限が無い等で OSError） | 実行できなかったと分かる additionalContext を返す。exit 0 | 異常系 |
| C11 | pytest が時間切れ（フック側の時間制限。120 秒。定数で持つ。「運営者の決定」3） | pytest のプロセスを止め、「N 秒で時間切れになりテストは最後まで走っていない」と分かる additionalContext を返す。成功扱いにしない。exit 0 | 異常系 |
| C12 | pytest の出力に日本語（テスト名）や UTF-8 として不正なバイトが含まれる | 例外にせず、読める形（不正なバイトは置換）で返す | 境界値 |
| C13 | pytest が標準エラーにも出力した | 標準出力と標準エラーの両方を要約の材料にする（今の `2>&1` と同じ） | 正常系 |
| C14 | 発火しない（A の対象外・B の壊れた入力） | pytest を**実行しない**。何も返さない | 正常系 |
| C15 | pytest の実行中 | フックの標準入力を pytest に渡さない（pytest 側が標準入力を待って止まらない） | 境界値 |

### D. FP 未確認の警告フック（`pre_tool_fp_warning.py`）

A で発火したときの振る舞い。要件定義書は `<プロジェクト>/docs/spec/01_requirements.md`。

| # | 条件 | 期待される振る舞い | 分類 |
|---|---|---|---|
| D1 | 要件定義書に `TODO: FPに確認` が1つ以上ある | `hookEventName: "PreToolUse"` の additionalContext で警告文（E の文言）を返す。exit 0 | 正常系 |
| D2 | 要件定義書に `TODO: FPに確認（仮値）` の形で含まれる | D1 と同じ（部分一致で判定） | 境界値 |
| D3 | 複数ある | 警告は1つだけ返す | 境界値 |
| D4 | 要件定義書はあるが `TODO: FPに確認` が無い（**今の LES の状態**） | 何も返さない | 正常系 |
| D5 | 表記ゆれ（`TODO：FPに確認`（全角コロン）・`TODO: FP に確認`（空白入り）・`todo: FPに確認`） | 何も返さない（今の振る舞いと同じく、文字列 `TODO: FPに確認` の完全な部分一致だけを見る） | 境界値 |
| D6 | 要件定義書が無い | 何も返さない | 境界値 |
| D7 | 要件定義書が読めない（パスがフォルダ・権限が無い・UTF-8 として読めない） | 何も返さない・exit 0（fail-open）。テストはフォルダと UTF-8 でないバイト列の2通りで確かめる。権限が無い形は root で走ると再現できないのでテストにせず、同じ `OSError` の分岐を通ることを reviewer がコードで確かめる（「運営者の決定（設計の確認点）」6） | 異常系 |
| D8 | 要件定義書が空 | 何も返さない | 境界値 |
| D9 | 発火した・警告を返すとき | **編集を止めない**: exit 0。出力に `permissionDecision`・`decision`・`continue: false` を含めない（含めると許可の確認を飛ばしたり、編集を止めたりする） | 正常系 |
| D10 | 発火しない（A の対象外・B の壊れた入力） | 要件定義書を読まない。何も返さない | 正常系 |
| D11 | 編集中のファイル自体に `TODO: FPに確認` がある | 判定に使わない（見るのは要件定義書だけ。今の振る舞いを残す。「運営者の決定」1） | 境界値 |

### E. 出力の形（2フック共通）

| # | 条件 | 期待される振る舞い | 分類 |
|---|---|---|---|
| E1 | 何かを返すとき | 標準出力は JSON 1つだけ（前後に余計な文字・pytest の生の出力を出さない）。形は `{"hookSpecificOutput": {"hookEventName": "<PostToolUse か PreToolUse>", "additionalContext": "<文字列>"}}` | 正常系 |
| E2 | `hookEventName` | テスト実行フックは `"PostToolUse"`、警告フックは `"PreToolUse"` | 正常系 |
| E3 | additionalContext に日本語・改行・引用符・バックスラッシュが含まれる | JSON として正しく読める（`json.loads` で元の文字列に戻る） | 境界値 |
| E4 | 終了コード | どの場合も 0（A〜D の全行） | 正常系 |
| E5 | 警告文 | 今の文言をそのまま使う: `警告: docs/spec/01_requirements.md に FP未確認事項が残っています。/fp-check で確認してから実装を進めてください。` | 回帰防止 |
| E6 | フックが作る文言の中のパス | プロジェクト基準の相対パスで書く（`docs/spec/01_requirements.md`・`.venv/bin/python`）。ユーザーのホームのパスを入れない。**pytest 自身の出力（トレースバックの絶対パスなど）は書き換えずにそのまま渡す**（Claude がファイルを開くのに要る情報で、置換すると誤読を招く。「運営者の決定（設計の確認点）」5） | 正常系 |

### F. 今の振る舞いのうち、残すもの・変えるもの

| 項目 | 扱い | 理由 |
|---|---|---|
| 発火の対象（`src/` でテスト・`src/domain/` で警告）・matcher `Edit\|Write` | 残す | 目的は同じ。今は判定が効いていないだけ |
| pytest の引数 `tests/ -q --tb=short` | 残す | |
| `-m "not slow"` | 足す | 運営者の決定7（WeasyPrint を呼ぶ遅いテストを毎回は走らせない） |
| `python` → `<プロジェクト>/.venv/bin/python` | 変える | venv 外の Python では依存が揃わない |
| `.venv` が無いとき | 新しく決める（C9） | 今は venv 外で走るので、この場合が無かった |
| 時間切れ | 新しく決める（C11） | 今は時間制限が無い |
| 入力の受け取り（環境変数 → 標準入力の JSON） | 変える | 環境変数は渡されない |
| パスの判定（文字列の前方一致 → プロジェクト基準で正規化して要素単位） | 変える | 絶対パスが来る。`frontend/src/` などの誤発火を防ぐ |
| 結果の届け方（標準出力の生テキスト → additionalContext の JSON） | 変える | 生テキストは Claude に届かない |
| 成功時の出力（全出力 → 要約1行） | 変える | 文脈を無駄に使わない。成功時も要約1行は返す（「運営者の決定」2） |
| 終了コード常に 0（`\|\| true`） | 残す | 止めない |
| 警告文（`/fp-check` を含む） | 残す | `/fp-check` は `.claude/skills/fp-check/SKILL.md` として実在する |
| 要件定義書だけを見る | 残す（ただし今は発火しない。「運営者の決定」1） | 運営者の決定どおり |
| リポジトリの絶対パスの直書き | 無くす | 別の場所で動かない |

### G. 配線（`.claude/settings.json`。設定するのはタスク4・確かめる基準はここで決める）

G1〜G4 を確かめるテスト（`.claude/settings.json` を読むテスト）は**タスク2では書かない。タスク4で、タスク3d の「deny とテストの表を一致させる」テストとまとめて書く**（「運営者の決定」4。タスク2で書くと配線までずっと落ちる）。G5 はタスク2のスクリプトで満たす。

| # | 確認すること |
|---|---|
| G1 | `hooks.PostToolUse` の matcher `Edit\|Write` のコマンドが `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/post_tool_run_tests.py` |
| G2 | `hooks.PreToolUse` の matcher `Edit\|Write` のコマンドが `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/pre_tool_fp_warning.py` |
| G3 | `hooks` の中に `/home/` で始まる絶対パス・`CLAUDE_TOOL_INPUT_FILE_PATH` が残っていない |
| G4 | テスト実行フックに `timeout` を設定し、スクリプトの時間制限（C11）より長くする（180 秒。スクリプト側が先に切れて C11 のメッセージを返せるように。「運営者の決定」3） |
| G5 | スクリプトは標準ライブラリだけで動く（配線は venv 外の `python3` で起動するため） |

---

## テストファイル

| ファイル | 対象 | 振る舞い |
|---|---|---|
| `tests/hooks/__init__.py`（新規・空） | — | `tests/` は層ごとのパッケージなので必要。タスク2がタスク3より先なのでここで作る |
| `tests/hooks/test_post_tool_run_tests.py`（新規） | `.claude/hooks/post_tool_run_tests.py` | A（テスト実行の列）・B・C・E |
| `tests/hooks/test_pre_tool_fp_warning.py`（新規） | `.claude/hooks/pre_tool_fp_warning.py` | A（FP 警告の列）・B・D・E |
| `tests/hooks/test_hooks_in_sync.py`（新規） | 2フックに同じ形で持つ共通の関数（`read_file_path`・`get_project_dir`・`is_under`・`emit`） | 片方だけ直すずれを止める（H。「運営者の決定（設計の確認点）」1） |

`docs/rules/04_testing.md` の「ファイル命名」の表に `tests/hooks/` を足す（`.claude/hooks/` のテスト。`tests/` は `src/` を写すという原則の例外になる旨も書く）。

### テストクラス（tester の案。最終の割り当ては architect の設計書を正本とする）

#### `TestRunTestsPathMatching`（`test_post_tool_run_tests.py`）
目的: どのパスで pytest が走り、どのパスで走らないか（A）

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_src配下のパスなら発火する`（parametrize: A1〜A6・A11・A16・A18・A21） | 各 `file_path` | pytest が1回呼ばれる | 正常系/境界値 |
| `test_src配下でないパスなら発火しない`（parametrize: A7〜A10・A12〜A15・A19・A20・A23） | 各 `file_path` | pytest が呼ばれない・標準出力が空・exit 0 | 境界値/異常系 |
| `test_相対パスは作業ディレクトリでなくプロジェクト基準で判定する` | A17 | 発火する | 境界値 |
| `test_シンボリックリンク経由のプロジェクトでも判定できる` | A22 | 発火する | 境界値 |
| `test_file_pathが無いか空か文字列でなければ何もしない`（parametrize: A24〜A26） | 各入力 | pytest が呼ばれない・標準出力が空・exit 0 | 異常系 |

#### `TestRunTestsFailOpen`（`test_post_tool_run_tests.py`）
目的: 壊れた入力・環境でも作業を止めない（B）

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_壊れた標準入力なら何もせずexit0`（parametrize: B1〜B5） | 各入力 | pytest が呼ばれない・標準出力が空・exit 0 | 異常系 |
| `test_CLAUDE_PROJECT_DIRが無いか空か相対パスなら何もしない`（parametrize: B6・B7・B7a） | `environ` から外す／空にする／プロジェクトのフォルダ名（`project.name`）にする。JSON の `cwd` と作業ディレクトリは「代用すれば発火する場所」（`cwd` はプロジェクト、作業ディレクトリは `project.parent`）にしておく | pytest が呼ばれない（`cwd` や作業ディレクトリで代用しない） | 異常系 |
| `test_日本語のパスを判定できる` | B8 | 発火する | 境界値 |
| `test_想定外の例外でもexit0` | 内部の処理で例外を起こす | 標準出力が空・exit 0 | 異常系 |

#### `TestRunTestsResult`（`test_post_tool_run_tests.py`）
目的: pytest の結果ごとに Claude へ何を返すか（C・E）

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_venvのpythonで決めた引数とプロジェクトを作業ディレクトリにして実行する` | C1 | 実行したコマンドが `[<P>/.venv/bin/python, -m, pytest, tests/, -q, --tb=short, -m, not slow]`・作業ディレクトリ `<P>`・標準入力を渡していない | 正常系 |
| `test_成功したら要約行をPostToolUseのadditionalContextで返す` | C2 | JSON 1つ・`hookEventName == "PostToolUse"`・要約行を含む・exit 0 | 正常系 |
| `test_失敗したら失敗したテスト名と要約行を返す` | C3 | 冒頭で失敗と分かる・`FAILED tests/...` と `1 failed` を含む・exit 0 | 正常系 |
| `test_長い出力は末尾を残して上限以下に切る` | C4（組み立てた additionalContext が上限+1 文字以上） | additionalContext 全体の長さ ≤ 上限・要約行を含む・切った旨を含む | 境界値 |
| `test_上限ちょうどの出力は切らない` | C5（組み立てた additionalContext 全体がちょうど上限。境界は見出しの長さに左右されないよう、切る処理の関数の単位で作る） | 出力全体を含む・切った旨を含まない | 境界値 |
| `test_収集エラーは失敗として返す` | C6 | 失敗と分かる・exit 0 | 異常系 |
| `test_テストが集まらなければ成功扱いにしない` | C7 | 成功の文言を含まない・見つからなかった旨・exit 0 | 境界値 |
| `test_その他の終了コードは異常終了として返す` | C8 | 終了コードを含む・exit 0 | 異常系 |
| `test_venvが無ければ実行せず理由を返す` | C9 | pytest が呼ばれない・`.venv/bin/python` が無い旨・exit 0 | 異常系 |
| `test_venvのpythonが起動できなければ理由を返す` | C10 | 実行できなかった旨・exit 0 | 異常系 |
| `test_時間切れなら成功扱いにせず時間切れと返す` | C11 | 時間切れの旨と秒数・成功の文言を含まない・exit 0 | 異常系 |
| `test_日本語と不正なバイトを含む出力でも返せる` | C12 | 例外なし・JSON として読める | 境界値 |
| `test_標準エラーの出力も要約に含める` | C13 | 標準エラー側の文字列を含む | 正常系 |
| `test_返す文字列にユーザーのホームのパスを含めない` | E6（偽の pytest の出力には絶対パスを含めず、フックが作る文言だけを見る。C9 の `.venv` が無いときの文言も含む） | additionalContext に `<P>` の絶対パスが無い | 正常系 |

#### `TestFpWarningPathMatching`（`test_pre_tool_fp_warning.py`）
目的: どのパスで警告を出すか（A）

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_src_domain配下なら警告する`（parametrize: A2・A3・A16・A21） | 要件定義書にマーカーあり | 警告が返る | 正常系/境界値 |
| `test_src_domain配下でなければ警告しない`（parametrize: A1・A4・A7〜A15・A19・A20・A23） | 要件定義書にマーカーあり | 標準出力が空・exit 0 | 境界値/異常系 |
| `test_シンボリックリンク経由のプロジェクトでも判定できる` | A22 | 警告が返る | 境界値 |
| `test_file_pathが無いか空か文字列でなければ何もしない`（parametrize: A24〜A26） | 同上 | 標準出力が空・exit 0 | 異常系 |
| `test_対象外のパスでは要件定義書を読まない` | D10（要件定義書をフォルダにしておく等で読んだら分かる形にする） | 標準出力が空・exit 0 | 正常系 |

#### `TestFpWarningFailOpen`（`test_pre_tool_fp_warning.py`）
目的: 壊れた入力・環境でも編集を止めない（B）

`TestRunTestsFailOpen` と同じ行（B1〜B9・B7a）を警告フックに対して持つ。期待値は「標準出力が空・exit 0」。

#### `TestFpWarningMessage`（`test_pre_tool_fp_warning.py`）
目的: 要件定義書の状態ごとに何を返すか（D・E）

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_マーカーがあればPreToolUseのadditionalContextで警告する` | D1 | JSON 1つ・`hookEventName == "PreToolUse"`・additionalContext が E5 の文言と一致・exit 0 | 正常系 |
| `test_仮値つきのマーカーでも警告する` | D2 | 同上 | 境界値 |
| `test_マーカーが複数でも警告は1つ` | D3 | 警告文が1回だけ | 境界値 |
| `test_マーカーが無ければ何も返さない` | D4 | 標準出力が空・exit 0 | 正常系 |
| `test_表記ゆれはマーカーとみなさない`（parametrize: D5 の3つ） | 各表記 | 標準出力が空 | 境界値 |
| `test_要件定義書が無ければ何も返さない` | D6 | 標準出力が空・exit 0 | 境界値 |
| `test_要件定義書が読めなければ何も返さない`（parametrize: フォルダ・UTF-8 でないバイト列） | D7 | 標準出力が空・exit 0 | 異常系 |
| `test_要件定義書が空なら何も返さない` | D8 | 標準出力が空 | 境界値 |
| `test_警告しても編集を止めない` | D9 | exit 0・出力に `permissionDecision`・`decision`・`continue` のキーが無い | 正常系 |
| `test_編集中のファイルのマーカーは見ない` | D11（要件定義書にマーカー無し・`file_path` の中身にマーカーあり） | 標準出力が空 | 境界値 |

---

#### `TestRunTestsEndToEnd`（`test_post_tool_run_tests.py`。「運営者の決定（設計の確認点）」7）
目的: Claude Code が呼ぶ形（標準入力 → 標準出力・終了コード）を端から端まで確かめる。`[sys.executable, "-I", "-S", <スクリプト>]` で起動し、標準ライブラリだけで・同じフォルダの他のファイルに依存せずに動くこと（G5）も同時に確かめる。`.venv/bin/python` には引数と作業ディレクトリを記録して決めた要約行を出すだけの偽物を置く（本物の pytest は走らせない）。作業ディレクトリはプロジェクト以外

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_src配下の編集で要約をJSONで返す` | `file_path` = `<P>/src/main.py` | 標準出力が JSON 1つ・`hookEventName == "PostToolUse"`・偽物の要約行を含む・exit 0・偽物が記録した引数と作業ディレクトリが C1 どおり | 正常系 |
| `test_JSONでない入力なら何も出さずexit0` | 標準入力 `not json` | 標準出力が空・exit 0・標準エラーに `Traceback` が無い | 異常系 |
| `test_frontend_srcの編集ではpytestを呼ばない` | `file_path` = `<P>/frontend/src/App.tsx` | 偽物が呼ばれていない・標準出力が空・exit 0 | 境界値 |

#### `TestFpWarningEndToEnd`（`test_pre_tool_fp_warning.py`。「運営者の決定（設計の確認点）」7）
目的: 同上（警告フック）。`sys.executable -I -S` で起動する

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_マーカーがあればsrc_domainの編集で警告のJSONを返す` | 要件定義書にマーカーあり・`file_path` = `<P>/src/domain/x.py` | 標準出力が JSON 1つ・`hookEventName == "PreToolUse"`・E5 の文言・exit 0 | 正常系 |
| `test_JSONでない入力なら何も出さずexit0` | 標準入力 `not json` | 標準出力が空・exit 0 | 異常系 |
| `test_CLAUDE_PROJECT_DIRが無ければ何も出さずexit0` | `env` から `CLAUDE_PROJECT_DIR` を消す | 標準出力が空・exit 0 | 異常系 |

#### H. 共通の関数の一致（`tests/hooks/test_hooks_in_sync.py`。「運営者の決定（設計の確認点）」1）
目的: 2フックが同じ形で持つ共通の関数を、片方だけ直してずれる事故を止める（各フックは1ファイルで完結させるため、共有モジュールにしない。設計書 `docs/design/edit_hooks.md`「設計の要点2」）

| テストメソッド名 | 条件 | 期待値 | 分類 |
|---|---|---|---|
| `test_共通の関数は2つのフックで同じ`（parametrize: `read_file_path`・`get_project_dir`・`is_under`・`emit`） | 2つのスクリプトを読み込む | `inspect.getsource` で取った関数のソースが2ファイルで一致する | 正常系 |

## Fixture・前提条件

- **プロジェクトは一時フォルダ**: `CLAUDE_PROJECT_DIR`（`project` fixture）は `tmp_path` そのものではなく `(tmp_path / "les").resolve()` を指す（A14 のプロジェクトの外・A15 の `<P>-old`・A22 の `real/`・`link/` を `tmp_path` の中に作るため。「運営者の決定（設計の確認点）」8）。**`monkeypatch.setenv` ではなく `main(environ={...})` の引数で渡す**（プロセス全体の環境を書き換えず、他のテストへ漏れない。サブプロセスのテストだけ `os.environ` を写して `CLAUDE_PROJECT_DIR` を消してから明示的に入れた `env` を渡す。「運営者の決定（設計の確認点）」4）。本物のリポジトリの `docs/spec/01_requirements.md`・`.venv` に依存しない（今の要件定義書にはマーカーが無いので、本物を使うと D1 が書けない）
- **要件定義書**: `<project>/docs/spec/01_requirements.md` をテストごとに書く（マーカーあり・無し・表記ゆれ・空・フォルダ・不正なバイト列）
- **`.venv`**: C9 以外では `<project>/.venv/bin/python` を置く（実行の差し替え方によっては空ファイルでよい）。C9 では置かない
- **本物の pytest を走らせない**: テストの中からリポジトリの全テストを走らせると、時間がかかる上に再帰する。pytest の実行（サブプロセスの起動）は差し替えて、呼ばれたか・どの引数・どの作業ディレクトリで呼ばれたかを記録し、決めた終了コードと出力を返させる。時間切れ（C11）・起動できない（C10）も差し替えで起こす
- **作業ディレクトリ**: A17 では `monkeypatch.chdir` でプロジェクト以外へ移す。それ以外のテストも作業ディレクトリに依存しないこと
- **プロジェクトの外側のパス**: A14・A15（`tmp_path/les-old`）・A22（`tmp_path/real`・`tmp_path/link`。`os.symlink`）は、`project` の外かつ `tmp_path` の中に作る
- 環境変数 `CLAUDE_PROJECT_DIR` は開発者の環境に左右されないよう、全テストで明示的に渡す／外す（関数を呼ぶテストは `environ` の dict、サブプロセスのテストは `env`）

## engineer へのノート

- **スクリプトは標準ライブラリだけで書く**（G5）。配線は venv 外の `python3`（pyenv の 3.14）で起動する
- `.claude/hooks/` はパッケージではないので、テストからは `importlib.util.spec_from_file_location` でファイルから読み込むか、サブプロセスで起動する。設計書 `docs/design/edit_hooks.md` で、主は関数を読み込んで `main(stdin=…, stdout=…, environ=…, run=…)` を呼ぶ形、加えて各フック3件をサブプロセス（`sys.executable -I -S`）で起動する形（`TestRunTestsEndToEnd`・`TestFpWarningEndToEnd`）と決まった
- サブプロセスのテストでは、`<project>/.venv/bin/python` に「引数と作業ディレクトリを記録して決めた出力を返すだけの偽物」（先頭行が `#!<sys.executable>`・実行権限付き）を置く（本物の pytest を走らせずに C1・C2 を端から端まで確かめられる）
- パスの判定は `Path.resolve()` 後の `relative_to`（または `is_relative_to`）で要素単位に比べる。`str.startswith` は A10・A15 を誤発火させる
- 空文字の `file_path` を `Path("")` にすると `.`（＝プロジェクト自身）になる。A25 は判定の前に弾く
- pytest は `subprocess.run(..., cwd=<P>, stdin=subprocess.DEVNULL, capture_output=True, timeout=<定数>)` 相当。時間切れは `subprocess.TimeoutExpired`、起動できないのは `OSError`。出力は `errors="replace"` で文字列にする
- `-q` の最後の行が要約行（`N passed ...`／`N failed, M passed ...`）。要約は「最後の空でない行」で取れる
- 出力は `json.dumps(..., ensure_ascii=False)` 相当で1回だけ書く。pytest の生の出力を標準出力に流さない
- 警告フックの出力に `permissionDecision` を入れない（入れると許可の確認を飛ばしてしまう）
- `except Exception` で全体を包んで exit 0 にする（B9）。ただし判定の分岐は個別に書き、包み込みに頼って A・B を満たさない（どの行も意図して「何も返さない」にする）
- 完了時に `docs/rules/04_testing.md` に `tests/hooks/` を足す

---

## 運営者の決定（2026-10-22。tester が出した確認点5件への回答）

1. **警告フックは要件定義書のマーカーだけを見る**（確認点の案 (a)）
   - 事実: `docs/spec/01_requirements.md` に `TODO: FPに確認` は0件。FP 未確定事項は § 8 の表で管理されていて、マーカーはコード側（`src/domain/education.py` など）にある。作り直しても、今の要件定義書のままでは警告は出ない
   - タスク2の範囲は「既存の2フックを動く形に作り直す」まで。何を FP 未確認とみなすかは FP 確認プロトコルの判断になるので、ここでは変えない（D1〜D11）
   - 判定の対象を `src/` のコードにある `TODO: FPに確認` に変える案（`/fp-check` の手順1と同じ情報源）は、`tasks/todo.md`「実装計画: 開発基盤の安全設定」の「バックログ（今回はやらない）」に1項目として書いた。§ 8 の表に行が残っていれば警告する案は採らない
2. **pytest が成功したときも要約1行を返す**（C2）。返さないと「走って成功した」のか「発火しなかった」のか Claude が区別できない
3. **時間制限と文字数の上限**: スクリプトの時間制限 120 秒（C11）・settings の `timeout` 180 秒（G4）・additionalContext の上限 8,000 文字（C4・C5）。どれも定数で持ち、テストは定数を参照する（値そのものに依存しない）。今のテストは約8秒
4. **配線のテスト（G1〜G4）はタスク4で書く**。タスク3d の設定を読むテストとまとめる。タスク2では G を基準として決めるだけにする
5. **`src/` 配下の `.py` 以外でもテストを走らせる**（A6。今の振る舞いを残す。`src/` に置くデータファイル等の変更も計算結果に効きうる。約8秒なので負担は小さい）

## 運営者の決定（設計の確認点）（2026-10-24。設計書 `docs/design/edit_hooks.md`「確認点」7件への回答）

1. **`tests/hooks/test_hooks_in_sync.py` を足す**。共通の4関数（`read_file_path`・`get_project_dir`・`is_under`・`emit`）を各フックに同じ形で持つので、`inspect.getsource` で2ファイルの一致を確かめ、片方だけ直すずれを止める（H）
2. **C4・C5 の上限は additionalContext 全体（見出し＋改行＋pytest の出力）に掛ける**。pytest の出力だけに掛けると、見出しを足した時点で上限を超え、C4 と両立しない
3. **`CLAUDE_PROJECT_DIR` が相対パスなら B6 と同じく何も返さない**（B7a）。相対パスを解決すると作業ディレクトリ基準の解決になり、仕様で禁じている形になる
4. **テストの環境変数は `monkeypatch.setenv` ではなく `main(environ=…)` の引数で渡す**。サブプロセスのテストだけ `env` を組み立てて渡す（Fixture・前提条件）
5. **E6（絶対パスを出さない）はフックが作る文言だけに適用し、pytest 自身の出力は書き換えない**。E6 のテストは偽の出力に絶対パスを含めず、フックの文言だけを見る
6. **D7 の「権限が無い」はテストにしない**。フォルダと UTF-8 でないバイト列の2通りで確かめ、権限が無い場合も同じ `OSError` の分岐を通ることを reviewer がコードで確かめる
7. **`TestRunTestsEndToEnd`・`TestFpWarningEndToEnd` を足す**（各3件・`sys.executable -I -S` でサブプロセス起動）。G5（標準ライブラリだけ・他のファイルに依存しない）も同時に確かめる
8. **テスト中の `CLAUDE_PROJECT_DIR`（`project` fixture）は `(tmp_path / "les").resolve()` にする**（2026-10-24 追加）。A14・A15・A22 の外側のパスを `tmp_path` の中に作るため。B6・B7・B7a は、JSON の `cwd` と作業ディレクトリを「代用すれば発火する場所」にして確かめ、B7a の相対パスはプロジェクトのフォルダ名（`project.name`）を渡す
