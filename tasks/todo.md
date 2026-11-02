# タスク

---

## FP確認待ち

### 高優先度（実装ブロッカー）

- [x] **入力インターフェース**: 今バージョンはYAML設定ファイル（`scenario.yaml`）。FPが直接操作できる形式への対応は次バージョン以降（2026-04-07）

### 中優先度

- [ ] **住宅ローンの金利タイプ**: 固定 / 変動 / フラット35 のどれを想定するか
- [ ] **繰り上げ返済**: 考慮するか否か
- [ ] **定年後の再雇用収入**: 比率指定 / 固定額 / 無視 のどれにするか
- [ ] **教育費の標準単価の出典**: 文部科学省調査データ等、どれを使うか
- [ ] **大学院・留学・習い事**: 教育費の別項目として持つか否か
- [ ] **Excelの見た目**: 色・フォント・条件付き書式の仕様
- [ ] **税・社会保険**: 計算に含めるか（含める場合: 概算税率 / 正確計算）

### 低優先度

- [ ] 複数シナリオ対応の優先度（現バージョンのスコープ外）
- [ ] 遺族年金・死亡保険金シナリオを扱うか

---

## 確認済み（実装可）

| 項目 | 決定内容 | 確定日 |
|------|----------|--------|
| インフレ率 | 0%固定（生活費への加算なし） | 2026-04-04 |
| 運用利回り | 0%固定（貯蓄残高への運用益加算なし） | 2026-04-04 |
| 住宅ローン控除の計算方法 | 年末ローン残高の0.7%を年間収支に加算 | 2026-04-07 |
| 住宅ローン控除の期間 | 13年（14年目以降は控除額=0） | 2026-04-07 |
| 年金 | FPが手入力（自動試算なし） | 2026-04-07 |
| 教育費 | 幼稚園〜大学の公立/私立区分ごとの標準単価を使用 | 2026-04-07 |
| 育休中の収入減 | BirthEventに収入減額率（client/spouse）と育休期間（年数）を入力値として持つ。デフォルトは率=1.0・期間=0（取得しない）。育休取得年の収入 = 通常収入 × 減額率。年平均率を入力するため67%/50%の月次分割は不要。 | 2026-04-11 |

---

## 実装タスク

### フェーズ1: コア実装 【完了 2026-04-07】

- [x] src/domain/models.py（データモデル）
- [x] src/domain/loan.py（元利均等返済・住宅ローン控除）
- [x] src/domain/education.py（教育費標準単価・年次計算）
- [x] src/domain/cashflow.py（年次CF計算）
- [x] src/input/yaml_loader.py（YAML → Scenarioオブジェクト）
- [x] src/input/validator.py（入力バリデーション）
- [x] src/output/excel_writer.py（Excel出力・2シート）
- [x] src/main.py（エントリーポイント）
- [x] tests/ 63件全パス
- [x] scenario.yaml（サンプル）
- [x] requirements.txt

実行方法: `python -m src.main scenario.yaml`

### フェーズ4.3: FastAPI + React フロントエンド 【完了 2026-05-10】

- [x] FastAPI バックエンド（POST /simulate 等）
- [x] React + Vite フロントエンド（シミュレーション入力・結果表示）

### フェーズ4.4: 根拠付き出力（クライアントに渡せる形） 【完了 2026-05-10】

- [x] src/domain/cashflow_analysis.py（貯蓄最低値・赤字期間の分析）
- [x] src/output/excel_writer.py 拡張（「前提条件・注釈」第3シート）
- [x] src/output/comment_generator.py（Claude API によるFPコメント生成）
- [x] src/output/pdf_config.py（フォントパス設定）
- [x] src/output/pdf_writer.py（WeasyPrint によるPDF生成）
- [x] src/api/routes/comment.py（POST /generate-comment）
- [x] src/api/routes/pdf.py（POST /download-pdf）
- [x] src/api/schemas.py 拡張
- [x] src/api/main.py 拡張
- [x] フロントエンド PDFダウンロードボタン
- [x] tests/ 161件全パス（2スキップ）
- [ ] 実ブラウザでの AC-4-x 動作確認（未実施）
- [ ] WSL2 環境での WeasyPrint 動作確認（libpango インストール確認）
- [ ] ANTHROPIC_API_KEY 設定確認

### フェーズ4.5: クライアント永続化・管理UI・デスクトップアプリ化 【コミット済み 2026-06-17】

Phase 1: クライアントデータ永続化（8bf20f5）

- [x] src/db/models.py・client_repository.py・sqlite_repository.py（SQLAlchemy + Repository パターン）
- [x] src/api/routes/clients.py（CRUD: GET/POST/PUT/DELETE /clients）
- [x] src/api/dependencies.py・schemas.py 拡張
- [x] tests/db/・tests/api/test_clients.py
- [x] docs/design/ep4.5_client_persistence_design.md・_test_spec.md

Phase 2: クライアント管理 UI（3097602）

- [x] frontend ClientManager/SaveDialog コンポーネント・useClients hook
- [x] 選択ドロップダウン・保存・名前を付けて保存・削除（key-based remount でフォーム復元）
- [x] frontend テスト（ClientManager・useClients・clientCrud）
- [x] docs/design/ep4.5_frontend_design.md・_test_spec.md

Phase 3: Electron デスクトップアプリ化（bed2b87）

- [x] PyInstaller で FastAPI を実行ファイル化（api-server.spec）
- [x] electron/（main.js・preload.js・builder.config.js）— 空きポート自動確保・API 自動起動/停止
- [x] Windows NSIS インストーラー対応
- [x] docs/design/ep4.5_electron_design.md

- [ ] ep4.5 全テストのパス確認（テストコードは存在。実行確認は tasks 未記録）
- [x] WSL2 での実機ビルド確認（2026-06-20）。ビルド時に3つの実バグを修正：
      ① api-server.spec に exclude_binaries 欠落（onedir 衝突）
      ② main.py が凍結時も reload=True でプロセス無限増殖
      ③ electron/package.json で electron が dependencies（builder 停止）
      → api-server EXE は /health=200 を確認。AppImage(185MB)・snap(156MB) 生成、
        resources に api-server・frontend 同梱を確認
- [ ] Electron GUI の起動・操作確認（WSLg 対話セッションでユーザーが実施予定。
      起動: output/electron-dist/ライフイベント家計シミュレーター-1.0.0.AppImage）

---

## 実装計画: 開発基盤の安全設定（AI駆動開発設計思想 段階1 の移植）

作成日: 2026-10-18（planner）

### 目標

Claude Code が LES で動くとき、次の3つが仕組みで止まる状態にする。計算モデルには触れない（`src/` の変更は、顧客データの既定の置き場所を `data/` に移す2か所だけ＝タスク0.5）。

1. 秘密・顧客データ（`.env`・`clients.db` など）を Read ツールでも Bash（`cat`・`sqlite3`・`python -c` など）でも読まない
2. 安全設定そのもの（`.claude/settings*.json`・`.claude/hooks/**`）を人の承認なしに書き換えない
3. 取り返しのつかない git / rm（`git push -f`・`git reset --hard`・`rm -rf .` など）を止める

移植元: 別リポジトリで導入済みの guard フック（コミット 57cb314・b421b54。設計 `docs/design/guard_hook.md`・仕様 `docs/design/test_spec_guard_hook.md`）。

### 前提として分かっていること（2026-10-18 調査）

- `.claude/settings.json` に permissions（allow・ask・deny）が無い。`.claude/hooks/` も無い
- **既存の2フックは今も動いていない可能性が高い**。`$CLAUDE_TOOL_INPUT_FILE_PATH` を見ているが、Claude Code はフックの入力を環境変数ではなく標準入力の JSON（`tool_input.file_path`・絶対パス）で渡す。仮に値が入っても絶対パスなので `^src/` に一致しない。→ 「パスを `$CLAUDE_PROJECT_DIR` に直す」だけでは足りず、標準入力を読むスクリプトに作り直す（TDD 対象）
- pytest: `.venv/bin/python -m pytest`（Python 3.14.2・`pytest.ini` はマーカー `slow` の定義のみ・197件収集）。フックの `python3` は pyenv の 3.14
- `tests/` は層ごとのパッケージ（各ディレクトリに `__init__.py`）。guard のテストは `tests/hooks/` に置く
- `clients.db`: 開発時は `data/clients.db`（`LES_DB_PATH` の既定値。`src/data_paths.py`。タスク0.5 で既定値を直下から移した。直下に残る既存の `clients.db` は運営者が移す）、Electron 版は `app.getPath('userData')/clients.db`（リポジトリの外）。`data/`・`*.db`・`*.xlsx` は `.gitignore` 済み
- `cf_simulation_20260407.xlsx`・`cf_simulation_20260411.xlsx` がルートにある（`scenario.yaml` から作った出力の可能性が高いが未確認）
- `output/` の中身は Electron のビルド成果物だけ（顧客データは無い）
- `scenario.yaml` と `frontend/.env.development` は git 管理されている（リモートは公開リポジトリ demo-life-event-simulator）
- LES 用の個人メモリ（`~/.claude/projects/-home-<ユーザー>-pjt-life-event-simulator/memory/`）は**存在しない**。棚卸しは不要
- `.claude/settings.local.json`（348B・git 管理外）は中身を誰も開いていない

### タスク一覧

着手順は データの置き場所 → 設定 → フック → guard → 配線 → settings.local.json → 実機確認。

- [x] 0. 運営者に確認する（2026-10-20 回答済み。下の「運営者の決定」）
- [x] 0.5. **TDD 対象**: 顧客データを `data/` にまとめる（2026-10-20 完了・reviewer 済み。運営者が直下の `clients.db` と `cf_simulation_*.xlsx` を `data/` に移した＝2026-11-03 に直下に無いことを確認）（planner → tester → architect → engineer → reviewer）
  - 理由: 実データのシナリオの置き場を作るにあたり、顧客データが直下の `clients.db`・直下の `cf_simulation_*.xlsx`・新しいフォルダの3か所に散らばるのを避ける（`CLAUDE.md` コア原則「構成は直感的に」・`docs/rules/00_workflow.md`「配置の原則」）。`.gitignore`・deny・guard の対象を `data/` 1か所にする
  - 変えるもの: DB の既定パス → `data/clients.db`（既定値は1か所。`src/db/sqlite_repository.py` は既定値を持たない）、Excel の既定の出力先（`src/output/excel_writer.py` の `output_dir`）→ `data/output/`。DB・出力ともフォルダが無ければ作る。`src/main.py` は変更不要。詳細は設計書
  - 変えないもの: Electron 版（`LES_DB_PATH` を `userData` で明示しているので影響なし）・計算モデル・API の応答
  - `data/` を `.gitignore` に足す。`data/scenarios/` はコードでは作らず、README に `mkdir -p data/scenarios` と書く（決定④）
  - README に「データの置き場所」の節を足す（実データのシナリオは `data/scenarios/` に置き `python -m src.main data/scenarios/<名前>.yaml` で実行する／サンプルは直下の `scenario.yaml`／出力は `data/output/`）
  - 既存の直下の `clients.db` と `cf_simulation_*.xlsx` 2つは**運営者が自分で `data/` に移す**（AI は中身に触れない）
  - 振る舞い仕様（tester・2026-10-20）: `docs/design/test_spec_data_directory.md`（確認点6件は下の「運営者の決定」で回答済み・仕様に反映済み）
  - 運営者の決定（2026-10-20・仕様の確認点）: ①相対パスは作業ディレクトリ基準のまま ②`LES_DB_PATH` を明示したときも親フォルダが無ければ作る ③DB の既定値は1か所にまとめる（`sqlite_repository.py` の既定値をなくす） ④`data/scenarios/` は README に `mkdir -p data/scenarios` と書く ⑤空 DB の警告コードは足さない。マージ前に運営者が直下の `clients.db` と Excel を `data/` に移す ⑥`docs/guides/setup-windows.md` の Excel の出力先の記述はこのタスクで直す（同じ節の `python src/main.py` はバックログ）
  - 設計書（architect・2026-10-20）: `docs/design/data_directory.md`（既定値は新規 `src/data_paths.py` に置く提案＝決定③の置き場所の変更案）
- [x] 1. **設定のみ（TDD 対象外）**: `.claude/settings.json` に permissions を足す（Edit ツール・承認ダイアログで人が確認）（2026-10-20 完了。移植元の `Read(**/.env.development*)` は入れない＝deny は例外を書けず決定3の `frontend/.env.development` まで止まるため。`.env.development.local` は `.env.*.local` で止まる）
  - deny: 移植元と同じ `.env` 系・`*.pem`・`id_rsa*`・`~/claude-settings-backup/**` に加え、`Read(./data/**)`（顧客データ一式）・`Read(./.claude/settings.local.json)`・`Read(**/*.db)`・`Read(**/*.sqlite*)`・`Read(**/*.xlsx)`（0 の決定1）・`Read(~/.config/**/clients.db)`（Electron の保存先・決定4）。`frontend/.env.development` は例外（決定3）
  - ask: 移植元と同じ3件（`Edit(./.claude/settings.json)`・`Edit(./.claude/settings.local.json)`・`Edit(./.claude/hooks/**)`）
  - allow: 読むだけのコマンドに絞る（`git status/diff/log/show`・`.venv/bin/python -m pytest:*`）（決定6）
  - 再起動するまで効かない。確認は 6 でまとめて行う
- [x] 2. **TDD 対象**: 既存2フックを `.claude/hooks/` のスクリプトに作り直す（tester → architect → engineer → reviewer）（2026-10-24 完了・reviewer 四層○。仕様 `docs/design/test_spec_edit_hooks.md`・設計 `docs/design/edit_hooks.md`。tests/hooks 135件・全体 345 passed。配線はタスク4）
  - `post_tool_run_tests.py`: 標準入力の `tool_input.file_path` が `$CLAUDE_PROJECT_DIR/src/` 配下なら `"$CLAUDE_PROJECT_DIR"/.venv/bin/python -m pytest tests/ -q --tb=short` を実行（現状は `python`＝venv 外を使っている）。`-m "not slow"` を付ける（決定7）
  - `pre_tool_fp_warning.py`: `src/domain/` 配下の編集で `docs/spec/01_requirements.md` に `TODO: FPに確認` が残っていれば警告（止めない＝exit 0・additionalContext で返す）
  - 配線は `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/<名前>.py`。絶対パス `/home/<ユーザー>/...` を残さない
  - テスト: `tests/hooks/test_post_tool_run_tests.py`・`tests/hooks/test_pre_tool_fp_warning.py`（標準入力の JSON を与えて出力と終了コードを見る。pytest の実行そのものは差し替えて確かめる）
- [x] 3. **TDD 対象**: guard フックを持ち込む（tester → architect → engineer → reviewer）
  - 3a. tester: 移植元の仕様を LES 用に写し、`docs/design/test_spec_guard_hook.md` を作る。差分は「LES で足す秘密」（`data/` 配下・`*.db`・`*.sqlite*`・`*.xlsx`・`settings.local.json`。`frontend/.env.development` は例外）と「読む動詞に `sqlite3`・`unzip` を足す」の2点だけにする。テスト中のパス例はこのリポジトリ名・`$CLAUDE_PROJECT_DIR` に置き換える。設計書・テストに移植元のリポジトリ名は書かない（決定8。「移植元のコミット」とだけ書く）
    - 2026-10-29 完了: `docs/design/test_spec_guard_hook.md`（移植元コミット `d20ea9a` の誤検知の修正まで含めて写した。LES の差分は10節、運営者の決定9点は11節）
  - 3b. architect: `docs/design/guard_hook.md`（移植元の設計を参照し、差分と移植元コミットだけ書く）
    - 2026-10-29 完了: 移植元の関数・定数は変えず、LES の判定は【LES】ブロック1か所と `# 【LES】` の印を付けた接続点7行に閉じる（L4〜L6 は判定を足すので、定数だけでは済まない）
  - 3c. engineer（設計 `docs/design/guard_hook.md`）。`.claude/` には Write・Edit ツールだけで書く（承認あり）。Bash の cp・リダイレクト・patch や、/tmp の試作を写す手順は取らない
    - 3c-1 Red: `tests/hooks/conftest.py` の `_load` を `load_hook` に改名し、`tests/hooks/test_guard.py` を作る（移植元のテストを写し、仕様の【LES】の行を `# 【LES】` の印とクラス末尾の囲みで当てる）。`tests/fixtures/deny_probe/.env`（`DUMMY=1`・Write）と `.gitignore` の除外行も作る。guard のテストがテストごとに落ちることを確かめる
    - 3c-2: `.claude/hooks/guard.py` を移植元のコミット `d20ea9a` と一字一句同じに書き（Write）、`cmp` で一致を確かめる。【LES】のテストだけが落ちることを確かめる
    - 3c-3 Green: Edit ツールで【LES】ブロック・接続点7行・docstring を当てる
    - 3c-4: 性能テスト2件に `slow` を付け、`pytest.ini` の説明・README の1文（ファイル名に顧客の名前を使わない）・`docs/rules/00_workflow.md` の構成図（`tests/fixtures/`）を直す
  - 3d. `DENY_SAMPLES` を deny の16件にし、`test_every_read_deny_is_covered` に `project_dir` を渡す。`test_deny_exception_is_also_allowed_by_guard` を足す。`test_settings_wires_guard` は持ち込まない（タスク4）
  - 3e. reviewer（四層レビュー）。あわせて、移植元の `d20ea9a` と `diff` を取り差分が【LES】の印と【LES】ブロックに閉じていること（テストも同じ）、公開リポジトリに出せない語の grep が0件であることを確かめる
  - 2026-11-01 完了（3c〜3e）: reviewer 四層○。3e で見つかった `..` を挟んだ `data/` は決定11で塞いだ（再レビュー○）。H2〜H4・ヒアドキュメントの Python・here-string の xargs は記録だけ（仕様8節【LES】・決定12）。tests/hooks 1228 passed・2 xfailed、全体 1439 passed・2 skipped・2 xfailed。guard は配線前なのでまだ何も止めない（タスク4）
- [x] 4. **配線（設定。テストは 2・3 に含む）**（2026-11-03 完了・reviewer 四層○。差分は運営者が確認して承認。全体 1444 passed・2 skipped・2 xfailed。G4 の `== 180` は guard の `== 10` に揃えて数値のまま残す＝運営者の決定。承認ダイアログが出なかった原因は未解明）: `hooks.PreToolUse` に matcher `Bash` の guard（`"timeout": 10` 付き）、2 の2フックを差し替え。`test_settings_wires_guard` と G1〜G4 もこの工程で書く。**settings.json の書き換えは LES のセッションで** Edit ツールで行い、承認ダイアログで確認する（3c ではダイアログが出なかった・2026-11-01。原因は切り分け中なので、ダイアログが出ることを確かめてから書き、出なければ書く前の差分を人に見せて承認をもらう。テストの Red は別のセッションで進めてよい）。配線後は Bash で `.claude/` を書き換えられなくなる（以後の修正は Edit ツール）
- [x] 5. **設定のみ（運営者の作業が要る）**（2026-11-03 完了: 運営者が allow の8行をすべて消し `"allow": []` にした。秘密は入っていなかったので失効は不要。AI はファイルを開いていない）: `.claude/settings.local.json` の広い許可を削る。AI は中身を開かない。運営者に中身（秘密があれば伏せて）を見せてもらうか、運営者自身が `Bash(*)`・`Bash(python:*)`・`Bash(cat:*)`・`Read(//**)` のような広い許可を消す。秘密（トークン等）が入っていたら値の失効・再発行も検討
- [x] 6. **実機確認（Claude Code を再起動してから・人の立ち会いのもと・本物ではなくダミーで）**（2026-11-03 完了: 7項目すべて期待どおり。`src/domain/` の警告は要件書の TODO が0件のため出ないのが正しい。セッション開始時に `sed …; ls *.db` が止まった件は仕様 A1 の受け入れ済みの誤検知。結果は `docs/design/guard_hook.md`「実機確認の結果」）
  - `cat tests/fixtures/deny_probe/.env` → guard が止める（`PreToolUse:Bash hook error`・`DUMMY` が出ない）
  - `sqlite3 tests/fixtures/deny_probe/dummy.db .tables`・`cat tests/fixtures/deny_probe/cf_simulation_dummy.xlsx` → 止まる（ファイルは作らない。万一通っても「無い」と出るだけ）
  - Read ツールで `tests/fixtures/deny_probe/.env` → deny で拒否される（permissions は再起動後でないと効かない）
  - `head -3 .claude/settings.json`・`git status --short`・`.venv/bin/python -m pytest tests/hooks/ -q` → 通る
  - `src/` 配下を1行触って戻す → pytest フックが走る／`src/domain/` で警告が出る（2 の確認）
  - 書き換え・`rm -rf`・`git push -f` は実機で試さない（単体テストで担保）
  - 結果は `docs/design/guard_hook.md` 末尾に記録
- [x] 7. 個人メモリの棚卸し: 対象なし（2026-10-18 時点で LES 用メモリは存在しない）。完了扱い

### 着手順序の根拠

- 1（設定）は再起動まで効かないので先に入れておくと、6 の確認を1回の再起動で済ませられる。ただし deny の対象は 0 の回答で決まる
- 2 を 3 より先にする: 既存フックが動いていない疑いがあり、規模が小さい。標準入力の読み方・`$CLAUDE_PROJECT_DIR`・テストの置き場を先に固めると 3 の土台になる
- 3 の後に 4（配線）: 配線するとその場で Bash の `.claude/` 書き換えが止まるので、guard とテストが reviewer を通ってから
- 5 は運営者の作業が要るので 0 と同時に依頼し、6 の再起動前に終わらせる

### guard の持ち込み方（比較と推奨）

| 案 | 内容 | 評価 |
|---|---|---|
| **A. 複製して語彙表に LES 分を足す（推奨）** | `guard.py`・テストを LES に複製。差分は定数（秘密の判定・読む動詞）だけ | LES は独立したソフトウェア（CLAUDE.md）で公開リポジトリ。clone しただけで安全設定が揃う。guard は標準ライブラリだけの1ファイルで依存が無い。弱点は二重管理 → 移植元コミットを設計書に書き、差分を定数ブロックに閉じ込めて追従しやすくする |
| B. ユーザー設定（`~/.claude`）に1つ置いて共通化 | 全プロジェクトに効く | リポジトリの外に出るので LES を別の場所で開くと効かない。プロジェクトごとの秘密の表を持たせるには guard が設定ファイルを読む必要があり、移植元の「ファイルを開かない」設計に反する |
| C. 移植元を symlink・submodule で参照 | 1か所で管理 | 別リポジトリへの依存が公開リポジトリに入る。パスが変わると壊れる。`.claude/hooks/**` の保護対象がリポジトリ外を指す |
| D. 共通部分と LES 用設定ファイルに分ける | 拡張しやすい | 2プロジェクトでは過剰。guard が設定を読む点は B と同じ問題 |

推奨: **A**。定数の差分（`sqlite3`・`unzip` を読む動詞に足す等）は移植元にも害が無いので、移植元に戻すかは別途判断（移植元のバックログに書く）。

### LES で止める対象（2026-10-20 確定）

| 対象 | 扱い | 根拠 |
|---|---|---|
| `data/` 配下（実データのシナリオ・`clients.db`・出力の Excel） | 止める | 顧客データの置き場所（タスク0.5） |
| `.env` 系（移植元と同じ） | 止める | `ANTHROPIC_API_KEY` を使う |
| `frontend/.env.development` | 止めない（例外） | git 管理済み・公開済み（決定3） |
| `.claude/settings.local.json` | 止める（basename で判定） | 個人の許可設定 |
| `*.db` / `*.sqlite*` | 止める | 顧客 DB。`data/` の外に残った分と Electron の保存先も拾う |
| `*.xlsx` | 止める | 出力は顧客の家計が入る（決定1） |
| `scenario.yaml`（直下） | 止めない | git 管理のサンプル。実データは `data/scenarios/` |
| `output/`（直下） | 止めない | Electron のビルド成果物だけ（名前の整理はバックログ） |
| PDF 出力（`*.pdf`） | 止めない | ブラウザのダウンロードとして保存され、リポジトリに出力しない |

既知の穴（移植元と同じ）: スクリプトファイル経由（`python tools/x.py` の中で `clients.db` を開く）・API サーバーの応答経由は止まらない。guard はコマンド文字列だけを見る。

### 運営者の決定（2026-10-20）

1. 出力の Excel は `*.xlsx` 全般を止める
2. `scenario.yaml` は今後もサンプルだけ。ただし実データでも運用できるようにする → 実データは `data/scenarios/` に置く（タスク0.5）。顧客データは `data/` にまとめる（設計方針として `CLAUDE.md` コア原則と `docs/rules/00_workflow.md` に記載）
3. `frontend/.env.development` は guard・deny の例外にする（git 管理済み・公開済み）
4. Electron の保存先 `~/.config/…/clients.db` も Read の deny に書く
5. `settings.local.json` は運営者が自分で開いて広い許可を消す。秘密が入っていたら失効させる
6. allow は読むだけの git コマンドと `.venv/bin/python -m pytest:*` だけ
7. pytest フックは残し、`-m "not slow"` を付ける
8. 公開リポジトリの設計書・テストに移植元のリポジトリ名は書かない

### 運営者に確認が必要だった点（記録。回答は上）

1. `cf_simulation_*.xlsx` を止めるか。`*.xlsx` 全般まで広げるか。ルートの2ファイルは実データかサンプル出力か
2. `scenario.yaml` は今後もサンプルだけか（実データを入れる運用なら止める＋git 管理から外す必要がある）
3. `frontend/.env.development` を guard・deny の例外にするか（止まるままでもよいか）
4. Electron 版の保存先（`~/.config/…/clients.db`）も Read の deny に書くか（guard は basename で止めるので Bash 側は対応済みになる）
5. `.claude/settings.local.json` の中身の確認方法（運営者が見て広い許可を消す／伏せて AI に見せる）。秘密が入っていた場合の失効
6. allow に入れるコマンドの範囲（移植元相当の読むだけのもの＋ `.venv/bin/python -m pytest:*` でよいか）
7. src 編集ごとの pytest フックを残すか。残すなら `-m "not slow"`（WeasyPrint を除く）にするか
8. 設計書・テストに移植元リポジトリ名を書いてよいか（公開リポジトリのため。書かない場合は「移植元のコミット」だけ記す）

### FP確認待ち事項

なし。このタスクは開発基盤（`.claude/`・`tests/hooks/`・`docs/design/`）と、顧客データの既定の置き場所（タスク0.5・`src/` の既定値2か所）だけを変更し、計算モデルに触れない。

### バックログ（今回はやらない）

- guard は `rm -rf data`・`rm data/clients.db` など顧客データの削除を止めない（`.gitignore` 済みで取り戻せない。`git clean -fdx` は止まる）。止めるか・片付け（`rm data/output/x.xlsx`）も止めるかを決める（`docs/design/test_spec_guard_hook.md` 11節 決定5）
- `docs/diagrams/system.mmd` の excel_writer のノードが「2シート構成」のまま（今は3シート）
- `docs/guides/setup-windows.md` の `python src/main.py`（`-m` も引数も無い）は今の実装で動かない。手順を直す。同じ手引きの「4.」は `pip install openpyxl` だけで、CLI に要る PyYAML が入らない（`pip install -r requirements.txt` にするか、要るものだけにするかを決める）。`mkdir -p data/scenarios` に当たる Windows の手順（`mkdir data\scenarios`）も無い
- README の「ステータス」（要件定義完了 / 実装前）・「使い方」（実装後に追記）が今の実装と合っていない。「データの置き場所」の節と重ならないように書き直す（タスク0.5 の reviewer・2026-10-20）
- `LES_DB_PATH=""`（空文字）だとメモリ DB になり、再起動で保存したクライアントが消える（タスク0.5 の仕様 A6。今回は挙動を変えていない）。空文字をエラーにするか既定値扱いにするかを決める
- 直下の `output/` の中身は Electron のビルド成果物（`electron-dist`）だけで、名前から中身が分からない（Excel の出力先に見える）。`build/`・`dist/`（PyInstaller）と合わせて、ビルド成果物の置き場所を整理する（`CLAUDE.md` コア原則「構成は直感的に」）
- FP 未確認の警告フック（`.claude/hooks/pre_tool_fp_warning.py`・タスク2）は要件定義書の `TODO: FPに確認` だけを見るが、要件定義書には今マーカーが0件で発火しない（FP 未確定事項は § 8 の表、マーカーは `src/domain/education.py` などのコード側）。判定の対象を `src/` のコードの `TODO: FPに確認`（`/fp-check` の手順1と同じ情報源）に変えるかを決める。`src/` 全体を読むので要件定義書1つより重くなる点も含めて判断する（`docs/design/test_spec_edit_hooks.md`「運営者の決定」1・2026-10-22）
