# テスト仕様: シェル経由の危険操作を止める PreToolUse フック（guard）

作成日: 2026-10-28（tester）
最終更新: 2026-11-01（3e レビュー後の運営者の決定を反映: 途中に `..` を挟んだ `data/` を止める＝11節 決定11、既知の穴の記録＝決定12、9.4.1 の並びの形の数と 10.2 の表の追記）。2026-10-29: 11節の9点を運営者の決定として反映
対象タスク: `tasks/todo.md`「実装計画: 開発基盤の安全設定」タスク3（3a）
移植元: 別リポジトリで導入済みの guard フック。**移植元のコミット `d20ea9a`** の仕様を写す（`tasks/todo.md` が前提にした `57cb314`・`b421b54` の後に入った誤検知の修正＝9節を含む）
次工程: architect（3b `docs/design/guard_hook.md`）→ engineer（3c・3d）→ reviewer（3e）

> 本書は移植元の仕様を、節の番号をそろえて写したもの。**LES で変えた・足した箇所には【LES】を付けた**。【LES】の無い規則・テストは移植元と同じ（パスの例だけ LES 用に置き換えた）。LES の差分の受け入れ基準は 10節にまとめた。
> 移植元で運営者が決めたこと（「移植元で決定」と書いたもの）はそのまま引き継ぐ。

---

## 0. 目的

`.claude/settings.json` の `permissions.deny`（`Read(**/.env)`・`Read(./data/**)` など。タスク1）は Read ツールにしか効かず、Bash ツールのコマンド（`cat .env`・`sqlite3 data/clients.db` 等）は素通りする。移植元では、本物の `.env` の中身が会話に露出した。LES ではこれに加えて**顧客データ**（実データのシナリオ・顧客 DB・出力した Excel）が同じ経路で会話に出うる。

- **成功**: AI が Bash で ①秘密ファイル・顧客データの中身を読む ②保護対象（`.claude/settings*.json`・`.claude/hooks/**`）を書き換える・消す・動かす ③取り返しのつかない git / rm 操作をする、を**実行前に**止め、何がなぜ止まったか・代わりに何をすべきかを AI に返す。日常の作業（保護対象を読む・フックを実行する・pytest・CLI の実行・通常の git）は一切止めない
- **失敗**: 秘密・顧客データの中身が会話に出る／保護対象がシェル経由で書き換わる／日常のコマンドが止まって作業が進まない／guard 自身の故障で全 Bash が止まる（fail-closed になる）／guard がファイルを開いて秘密を読む

### 脅威モデル（守備範囲の前提）
- 対象は**善意の AI のうっかり**（「確認のために cat する」「DB を sqlite3 で覗く」「設定を sed -i で直す」「片付けで rm -rf」）。意図的な回避（変数に分割・エンコード・別名コピー経由など）は**完全には防がない**
- 判定は**コマンド文字列だけ**で行う。ファイルシステム・環境（cwd の中身）は見ない（例外: 「広い対象」と【LES】「顧客データの置き場所」の判定に `CLAUDE_PROJECT_DIR` を使う）
- **判定できないときは通す（fail-open）**。Bash が止まるとセッション全体が使えなくなるため。守りの最後の砦は人の承認（permission プロンプト）と deny ルールであり、guard はその手前の網

### 【LES】移植元からの差分（要約。詳細は 3.3・10節）

| # | 差分 | 根拠 |
| --- | --- | --- |
| 1 | 秘密に足す: `data/` 配下（プロジェクト直下の `data/`）・`*.db`・`*.sqlite*`・`*.xlsx` | `tasks/todo.md`「LES で止める対象」・決定1・タスク0.5 |
| 2 | `.env.development` を秘密から外す（basename がちょうど `.env.development` のときだけ。`.env.development.local` などは秘密のまま） | 決定3（`frontend/.env.development` は git 管理されたサンプル） |
| 3 | 読み取り動詞に `sqlite3`・`unzip` を足す | `tasks/todo.md` タスク3a |
| — | `.claude/settings.local.json` | **移植元で既に秘密**（basename で判定）。guard 側の変更は無い（deny 側はタスク1で足した） |
| — | 9節（誤検知の修正）との組み合わせ | 10.3。新しい秘密・動詞が `--exclude` の値・find の名前条件・一覧だけ・`/tmp` の除外とどう組み合わさるか |
| — | `TestRepositoryIntegration` の `DENY_SAMPLES` を LES の deny に合わせる | 3d。4節 |

## 1. テスト対象

本体: `.claude/hooks/guard.py`（標準ライブラリのみ・単体ファイル・外部コマンドを起動しない・ファイルを開かない）

テストが前提にする公開面（名前は architect が変えてよい。変えたら本書を直す）:

```python
def check_command(command: str, project_dir: str | None = None) -> str | None:
    """止めるなら理由（AI に返す文）を、通すなら None を返す。純粋関数。"""

def main(stdin=None, stderr=None, environ=None) -> int:
    """フックの入口。止めるなら理由を stderr に書いて 2、それ以外は必ず 0。"""
```

- `project_dir` 未指定時は `main` が `environ["CLAUDE_PROJECT_DIR"]` を渡す（無ければ None）
- 既定値を引数定義で `sys.stdin` などに束縛しない（テストで差し替えるため）

### Claude Code との入出力契約
- 入力: stdin に JSON。`tool_name`（`"Bash"`）と `tool_input.command`（文字列）を使う。他のキーは無視
- 止める: **exit 2**・stderr に理由（Claude Code が AI に返す）・stdout は空。**stderr への書き込みに失敗しても 2 を返す**（理由が届かなくても止める判定は守る）
- 通す: **exit 0**・stdout も stderr も空（JSON を出さない＝通常の承認フローに一切干渉しない）
- **exit 0 と 2 以外を返さない**（1 などは「フックのエラー」として人に表示されるだけで、止まりも通りもしない曖昧な状態になる）

## 2. テストファイル

`tests/hooks/test_guard.py`（`docs/rules/04_testing.md` の `tests/hooks/` の例外に当たる。`tests/hooks/__init__.py` はタスク2で作成済み）

- 【LES】読み込みは `tests/hooks/conftest.py`（タスク2）の「ファイルの場所から読み込む」方式にそろえる（スクリプトが無いときは収集エラーにせず、テストごとに理由の分かる形で落ちる）。fixture を conftest に足すか、テストモジュールの中に閉じるかは architect が決める
- テスト名は移植元と同じ英語の名前を使う（テストを移植元から複製し、差分を追いやすくするため。`docs/rules/04_testing.md` は日本語のテスト名を「OK」としており、必須ではない）

## 3. 判定の規則（振る舞いの定義）

### 3.1 前処理（全カテゴリ共通）
- コマンドは `;`・`&&`・`||`・`|`・`&`・改行・`( )`・`{ }` で区切った**全部の単純コマンド**を見る。区切り記号の前後に空白が無くても区切る（`cat .env;ls`）
- `$( … )`・`` ` … ` ``・プロセス置換 `<( … )`・`>( … )`・`bash -c` / `sh -c` / `zsh -c` / `eval` の引数文字列は、**中身もコマンドとして同じ規則で判定する**
- クォート・バックスラッシュは bash と同じく外してから判定する（`'.env'`・`".env"`・`.e""nv`・`\.env` はすべて `.env`）
- コマンド語の前の `VAR=値`、および包み込みコマンド `sudo`・`env`・`command`・`builtin`・`exec`・`nice`・`nohup`・`time`・`timeout <秒>`・`xargs [opts]`・`find … -exec`／`-execdir` の後ろは、**包まれた側をコマンド語として扱う**
- コマンド語は basename で判定する（`/usr/bin/cat`・`./venv/bin/python` → `cat`・`python`）
- **ヒアドキュメントの本文はデータとして扱い、判定しない**（`git commit -m "$(cat <<'EOF' … .env … EOF)"` のコミットメッセージで止めないため）。ヒアドキュメントを受けるコマンド行のリダイレクト先は判定する
- `eval eval … CMD` のように eval が続くときは、続く eval をまとめて剥がしてから1回だけ展開する（意味は同じ。1段ずつ展開すると段数ぶん解析し直して遅くなるため）
- `N>` の数字を fd 番号とみなすのは、数字が `>` に**空白なしで**続くときだけ（bash と同じ。`echo 2 > f` の `2` は引数）
- 全体がクォート不整合などで解析できないときは、**改行で区切った各行のうち解析できる行だけ判定**し、解析できない行は通す（bash は行ごとに実行するため、前の行は実際に走る）

### 3.2 パスの正規化
パス判定は、トークンから次を取り除いた形で行う:
- 先頭の `@`（`curl -d @.env`）、`名前=` / `名前=@`（`if=.env`・`file=@.env`・`--env-file=.env`）
- `./`・`../` の繰り返し、`~/…`・`$HOME/…`・`${HOME}/…`・`$CLAUDE_PROJECT_DIR/…`・`${CLAUDE_PROJECT_DIR}/…`・絶対パスの前置部分（判定は**パスの末尾側の構成要素**で行うので、前置部分の違いは結果に影響しない）
- 【LES】例外: 「顧客データの置き場所」（3.3 の `data/`）だけは**パスの先頭側**で判定する（プロジェクト直下の `data/` だけを指すため。`.gitignore` の `/data/` と同じ考え方）。前置部分の扱いは 3.3 の表に書く。先頭側で見るので、**途中の `..` を解いた形でも見る**（`src/../data/x` は `data/x`。3.3・10.1 L5・11節 決定11）

### 3.3 カテゴリA: 秘密ファイルを読む
**秘密パス**（basename または構成要素で判定。**大文字小文字を区別しない**: WSL の `/mnt/c` など区別しないファイルシステムでは `cat .ENV` でも `.env` が読めるため）:
| 種類 | 該当 | 該当しない |
| --- | --- | --- |
| `.env` | basename が `.env`（任意の階層） | `.envrc`・`environment.yml`・`my.env`・`.venv` |
| `.env.*` | basename が `.env.<x>…` で、`<x>` が `example`・`sample`・`template` **以外**。【LES】ただし basename が**ちょうど** `.env.development` のものは除く（決定3） | `.env.example`・`.env.sample`・`.env.template`・`.env.example.bak`・【LES】`.env.development`（`frontend/.env.development` など任意の階層） |
| ローカル設定 | basename が `settings.local.json`（任意の階層。`.claude/` 配下でなくても。`cd .claude && cat settings.local.json` を拾うため） | `settings.json` |
| 鍵 | basename が `*.pem`・`id_rsa*`・`id_ed25519*`・`id_ecdsa*`・`id_dsa*` | `pem.md` |
| 退避 | 構成要素に `claude-settings-backup` を含む | — |
| 【LES】顧客 DB | basename が `*.db`（`.db` で終わる）・`*.sqlite*`（`.sqlite` を含む）。任意の階層・前置部分を問わない（`/tmp/…`・`~/.config/…`（Electron の保存先）も） | `src/db/sqlite_repository.py`・`tests/db/`（構成要素 `db`・`sqlite_…` は `.db`・`.sqlite` ではない）・`sqlite3`（コマンド名） |
| 【LES】出力の Excel | basename が `*.xlsx`（`.xlsx` で終わる）。任意の階層 | `xlsx_notes.md` |
| 【LES】顧客データの置き場所 | 次のどれか（**プロジェクト直下の `data/` とその下すべて**。`data` そのものも含む）: ①相対パスで、`.`・`..` を除いた最初の構成要素が `data`（`data`・`data/`・`./data/x`・`../data/x`）②`$CLAUDE_PROJECT_DIR`・`${CLAUDE_PROJECT_DIR}` の直後の構成要素が `data` ③`project_dir` が与えられたとき、プロジェクトのフォルダ名（`project_dir` の basename）の構成要素の直後が `data`（`/work/proj/data/x`・`~/pjt/proj/data/x`・`../proj/data/x`）。**①〜③は「書いたままの形」と「`..` を解いた形」の2つに掛け、どちらかに当たれば秘密**（止める側にだけ倒す。11節 決定11）。「`..` を解いた形」は、前置部分（先頭の `/`・`~`・`$HOME`・`${HOME}`・`$CLAUDE_PROJECT_DIR`・`${CLAUDE_PROJECT_DIR}`）を残し、その後ろの `.` を捨て、`名前/..` を打ち消した形。前置部分より前には戻らず、相対パスの先頭に余った `..` は残す（①の「`.`・`..` を除いた最初」がそのまま掛かる）（`src/../data/x`→`data/x`・`$CLAUDE_PROJECT_DIR/src/../data/x`→`$CLAUDE_PROJECT_DIR/data/x`・`/work/proj/src/../data/x`→`/work/proj/data/x`・`src/../../data/x`→`../data/x`） | `tests/data/x`・`frontend/src/data/x`・`/tmp/x/data/y`・`/work/other/data/y`・`data_paths.py`・`data.json`・`metadata/x`・`docs/design/data_directory.md`・【11節 決定11】`data_x/../src/a.py`・`tests/../src/data_paths.py`・`src/../tests/data/x`・`/work/other/src/../data/y`（どちらの形でも当たらない） |
| glob | ドットで始まる basename の glob が `.env` に一致しうる（`.e*`・`.env*`・`.*`・`.en?`）／basename が `*.pem`・`id_rsa*` に一致。【LES】basename にリテラルの `.` があり、その `.` より後ろの glob が秘密の拡張子（`db`・`xlsx`・`sqlite…`）に一致しうる（`*.db`・`*.xls?`・`clients.d?`・`*.*`・`*.s*`） | `*`（bash はドットファイルを展開しない。【LES】顧客ファイルには一致しうるが通す＝8節）・`*.py`・【LES】`cf_*`（`.` が無い＝8節） |

【LES】**インタプリタのインラインコード（A3）では、「顧客データの置き場所」は `/` を含む語（`data/…`）だけを数える**。`data` だけの語は数えない（Python の変数名 `data` で止めないため。10.1 L5）。他の秘密（`.db`・`.xlsx` など）は A1 と同じに数える。

**読み取り動詞**: `cat tac nl less more most head tail grep egrep fgrep rg ag ack sed awk gawk cut sort uniq paste join diff comm od xxd hexdump strings base64 base32 cp scp rsync tar zip gzip bat batcat view vi vim nvim nano emacs jq yq curl wget dd source .`、【LES】`sqlite3 unzip`、および**インタプリタのインラインコード**（`python*`・`node`・`ruby`・`perl`・`php` の `-c` / `-e` の引数。**定義**: 最初の被演算子（スクリプト名など）より前にある、英字束に `c` か `e` を含むオプションの次の語。`python3 x.py -e foo` のスクリプト側引数は対象外）

**止める条件**（いずれか）:
- A1: コマンド全体のどこかに読み取り動詞があり、**同じコマンド全体のどこか**に秘密パスのトークンがある（`;`・`|` をまたいでも止める。`F=.env; cat $F`・`echo .env | xargs cat` を拾うため）
- A2: 入力リダイレクト `<` の対象が秘密パス（動詞を問わない。`while read l; do …; done < .env`）
- A3: インタプリタのインラインコード文字列の中に、秘密パスが語として現れる（`python3 -c "print(open('.env').read())"`。前後がクォート・空白・`/`・`(`・`=`・`,` などの区切りのときだけ一致とし、`dotenv`・`.envrc` には一致しない）

**止めない**: 秘密パスが出てきても読み取り動詞が無いもの（`ls -la .env`・`test -f .env`・`[ -f .env ]`・`find . -name .env`・`git add .env.example`・`ssh -i ~/.ssh/id_rsa host`・`docker run --env-file=.env`・【LES】`du -sh data`・`wc -c data/clients.db`・`mv clients.db data/`）。**除外の指定の値（9.3）と、「一覧だけ」のコマンドの名前（9.4）**。スクリプトを実行するだけのもの（`python3 scripts/x.py`・【LES】`.venv/bin/python -m src.main data/scenarios/a.yaml`。内部で顧客データを読んでも、会話に出るのはスクリプトの出力だけ）

### 3.4 カテゴリB: 保護対象を書き換える・消す・動かす
**保護パス**: 構成要素に `.claude` があり、その直後が `hooks`（それ自身とその下すべて）または basename が `settings*.json`（`settings.json`・`settings.local.json`）。`.claude` ディレクトリそのもの（`rm -rf .claude`・`mv .claude x`）も保護パス。前置部分は問わない（`~/.claude/settings.json` も対象）。**ただし `/tmp/`・`/var/tmp/` の下でプロジェクトの外にあるものは除く（9.5）**。**guard.py 自身も `.claude/hooks/` の下なので対象**

**止める条件**（単純コマンドごとに判定）:
| 操作 | 保護パスがどこにあると止めるか |
| --- | --- |
| 出力リダイレクト `>`・`>>`・`>|`・`&>`・`N>`（空白なし `>.claude/…` も）。**ただし `/dev/` で始まる先（`2>/dev/null`）と fd 複製（`2>&1`・`>&2`）は書き込みとして扱わない** | 書き込み先 |
| `tee [-a]` | どの引数でも |
| `sed -i` / `-i.bak` / `--in-place`、`perl -i`（`-pi -e` 等） | 対象ファイル |
| `cp`・`rsync`・`install`・`ln` | **書き込み先**（最後の引数、または `-t DIR`） |
| `dd` | `of=` |
| `mv`・`git mv` | どの引数でも（元を動かせば消えるのと同じ） |
| `rm`・`rmdir`・`git rm`・`unlink`・`truncate`・`touch`・`chmod`・`chown` | どの引数でも |
| `cd` で保護パス（`.claude` 以下）に入り、**その後に**上の書き込み操作をする | **相対パスの書き込み先**だけ（`cd .claude/hooks && rm guard.py`）。絶対パス・`~`・`/dev/` 宛て（`cd .claude && cp settings.json /tmp/bk.json`・`2>/dev/null`）は止めない。**cd は実行順に追う**: `cd ..`・`cd -`・`popd`・`cd /tmp`・引数なし `cd` で `.claude` から出た後の書き込みは止めない（`cd .claude && ls; cd ..; echo x > out.txt`）。`cd .claude/hooks; cd ..` はまだ `.claude` の中 |
| `find <場所> … -exec`／`-execdir` で上の書き込み操作を `{}` に対して行う、`find <場所> … -delete` | **探し始める場所**（`find .claude/hooks -name '*.py' -exec rm {} \;`）。`-exec cp {} /tmp/bk/` のように `{}` が書き込み先でなければ止めない |
| `xargs` 経由の書き込み操作で、書き込み先が標準入力から来るもの（`echo .claude/hooks/guard.py \| xargs rm`・`… \| xargs sed -i …`） | **コマンド全体のどこか**（A1 と同じ近似） |
| `git -C <dir> rm`／`mv` | `<dir>` とつないだパス（`git -C .claude/hooks rm guard.py` → `.claude/hooks/guard.py`） |

**止めない**: 読むだけ（`cat`・`sed -n`・`jq`・`grep`・`diff`・`git diff`・`git show`）、コピー元にするだけ（`cp .claude/settings.json /tmp/bk.json`）、実行するだけ（`python3 .claude/hooks/x.py`・`bash .claude/hooks/x.sh`・`echo '{}' | python3 .claude/hooks/guard.py`）、`git add`・`git commit`、`ls`

### 3.5 カテゴリC: 取り返しのつかない操作
- C1 `git push` の強制: `--force`・`-f`・`--force-with-lease[=…]`・短いオプションの束に `f` を含む（`-fu`）・refspec の先頭が `+`（`git push origin +main`）。オプションの位置は問わない（`git push origin main --force`）。`git -C <dir>` などサブコマンド前のグローバルオプションも越えて判定する
- C1b `git push` でリモートのブランチ（・タグ）を消す／丸ごと上書きする:
  - `--delete`・短いオプションの束に `d` を含む（`-d`・`-nd`。C1 の `f` と同じ読み方）
  - `--mirror`（リモートの ref をローカルと一致させる＝ローカルに無いブランチは消え、ずれたものは強制で上書きされる）
  - **コロンで始まり、コロンの右が空でない被演算子**（`:main`・`:refs/heads/x`・`:refs/tags/v1`）。コロンの左が空の refspec は「削除」の意味のため。**コロンの左が空でないもの（`HEAD:main`・`feature:feature`・`refs/heads/a:refs/heads/b`）は削除ではないので C1b では止めない**。コロン1文字だけの `:` は「同名のブランチをすべて push」（matching）の意味で削除ではないので止めない
  - オプション・被演算子の位置は問わない（`git push origin --delete feature`・`git push origin feature -d`）。`-n`／`--dry-run` が付いていても止める（C2b と同じく判定を単純に保つため）
  - `+` で始まる refspec は C1 で既に止まる（`+main`・`+HEAD:main`・`+:main`）。C1b はそれを変えない（`+` の扱いは C1 に揃える＝先頭が `+` なら中身を問わず止める）
- C2 `git reset --hard`（引数・位置を問わない）
- C2b `git clean` で、**強制（`-f`・`--force`）と無視ファイルの削除（`-x`・`-X`）を両方含む**もの。短いオプションの束・分割・順序を問わない（`-fdx`・`-fx`・`-xdf`・`-fX`・`-f -d -x`・`-d -x -f`・`--force -x`）。`-n`/`--dry-run` が付いていても、`-f` と `-x`/`-X` が揃えば止める（判定を単純に保つため。`-n` だけなら通る）。`.env` など無視されている秘密ファイルが消えて取り戻せないため（移植元で決定）。【LES】LES では `data/`・`*.db`・`*.xlsx` も `.gitignore` 済みなので、この規則が**顧客データの一括削除**も止める
- C2c 作業ツリー全体を捨てる `git checkout`: パス引数が `.` のもの（`git checkout -- .`・`git checkout .`・`git checkout HEAD -- .`）。`./`・`:/`（リポジトリ全体）も同じ扱い
- C2d ローカルの未コミットの変更を捨ててブランチを切り替える（`git reset --hard` 相当のため）:
  - `git checkout` に `--force`、または短いオプションの束に `f` を含む語（`-f`・`-fq`・`-fb`）がある。**ブランチ名・パスの有無を問わない**（`git checkout -f`・`git checkout -f main`・`git checkout -f -- file.py` も止める。判定を単純に保つため）
  - `git switch` に `--force`・`--discard-changes`、または短いオプションの束に `f` を含む語（`-f`）がある
  - **値を取る短いオプションの後ろは束として読まない**: `git checkout` の `-b`／`-B`、`git switch` の `-c`／`-C` は直後の文字列がブランチ名になる（`-bfix`＝ブランチ `fix` を作る）。束の中でこれらの文字より後ろの `f` は強制とみなさない（`git checkout -bfix/x`・`git switch -cfeature` は通す。`git checkout -fb x` は `f` が `b` より前なので止める）
  - 止めないもの: 普段の切り替え・作成（`git checkout <branch>`・`git checkout -b x`・`git checkout -`・`git switch <branch>`・`git switch -c x`・`git switch -`）、ファイル単位の取り消し（`git checkout -- <file>`）
  - **足さない（移植元で決定・記録だけ）**: `git checkout -B`・`git switch -C`／`--force-create`（既存ブランチの付け替え）。8節の「承認の外で、引き続き止めないもの」に置き、テストで「通る」ことを固定しない（将来足すときに既存テストが壊れないように）。強制の長いオプションは**完全一致**で見る（`--force-create` は `--force` ではない）
- **C の git 規則に共通の前提**（C1・C1b・C2・C2b・C2c・C2d すべて同じ）: サブコマンドの前のグローバルオプション（`-C <dir>`・`-c key=val`・`--git-dir <dir>`／`--git-dir=<dir>`・`--work-tree`・`--namespace`・`--no-pager` など）を越えてサブコマンドを見つける。`bash -c`・`sh -c`・`eval` の中、`$( … )` の中、`sudo`・`env` などの包み込みの後ろ、`;`・`&&`・`|` でつないだ後ろにあっても同じ規則で止める（3.1 の前処理による）。クォート（`'git' push "--delete"`）・絶対パス（`/usr/bin/git`）も同じ
- **C の範囲外として引き続き止めないもの**（移植元で決定）: `git restore`（`git restore .` を含む）・`git branch -D`
- C3 `rm` が**再帰**（`-r`・`-R`・`--recursive`、束 `-rf`・`-fr`・`-Rf`・`-rfv` を含む）で、対象のどれかが**広い対象**:
  - `/`・`/*`・`~`・`~/`・`~/*`・`$HOME`・`${HOME}`・`$HOME/`・`$HOME/*`・`*`・`.`・`./`・`./*`・`..`・`../`・`../*`・`.*`
  - `$CLAUDE_PROJECT_DIR`・`${CLAUDE_PROJECT_DIR}`（とその `/`・`/*`）
  - `project_dir` が与えられたとき: その絶対パス自身・その祖先（`/work` など）・それらの `/*`
  - **書き方の違いは正規化して見る**: `./.`・`../..`・`src/..`・`~/.`・`$HOME/..`・`$CLAUDE_PROJECT_DIR/.`・`$PWD`・`${PWD}/*`・`//`。相対パスは**作業ディレクトリ＝プロジェクト**とみなして `project_dir` と比べる（`rm -rf ../proj` を拾うため。cd 後は誤検知の側に倒れる）。`project_dir` が無いときは、起点そのものかそれより上（`..` だけ）を広いとみなす
  - 中身が分からない語は通す: 置換だけの語（`"$(mktemp -d)"`）・未知の変数（`"$tmp"/x`）
  - `-f` の有無は問わない（再帰が破壊の本体のため。7節-4）
  - 【LES】`rm -rf data` は広い対象ではないので止めない（8節。今回は直さず記録する＝11節 決定5）

### 3.6 止めたときの理由文（stderr）
- 1行目は `guard: ` で始まり、カテゴリ名（`秘密ファイルの読み取り`・`保護対象の書き換え`・`取り返しのつかない操作`）と、引っかかった対象（パスまたは操作）を含む
- 次にやることを含む: 回避を試みず人に判断を求めること。カテゴリA は「中身が必要なら人に確認する（Read/Grep ツールも deny ルールで止まる）」、B は「変更が必要なら Edit ツールで（承認が出る）行うか人に依頼する」、C は「人に実行してもらう」
- C で引っかかった対象は**操作ラベル**（サブコマンド＋該当した語）で示す。C1b・C2d の例: `git push --delete`・`git push -d`・`git push --mirror`・`git push :main`・`git checkout -f`・`git switch --discard-changes`。次にやることは既存の C と同じ文でよい
- **秘密ファイルの中身を含まない**（guard はファイルを開かないので含みようがないが、テストで保証する）
- 1つのコマンドで複数該当しても理由は1件でよい（最初に見つかったもの）
- 【LES】カテゴリ名は移植元のまま（`秘密ファイルの読み取り`）。顧客データで止めたときも同じカテゴリ名を使う（文言を足さない。7節-22）

## 4. テストクラス一覧

各表の「判定」は `check_command` の戻り値が **止**＝文字列（非空）／**通**＝None。パラメータ化で書く（`@pytest.mark.parametrize("command", [...])` を「止める」「通す」で分ける）。`project_dir` の指定が無い行は `check_command(cmd)`（None）で呼ぶ。

### `TestSecretRead`（カテゴリA）
目的: 秘密ファイル・顧客データの中身がシェル経由で会話に出ないこと（【LES】の顧客データのテストは 10.2・10.3）

| テストメソッド名 | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_read_verbs_on_env_then_blocked` | `cat .env`・`less .env`・`more .env`・`head -5 .env`・`tail .env`・`grep KEY .env`・`rg KEY .env`・`sed -n 1p .env`・`awk 1 .env`・`cut -d= -f1 .env`・`sort .env`・`diff .env a`・`strings .env`・`xxd .env`・`od -c .env`・`base64 .env`・`cp .env /tmp/x`・`tar czf x.tgz .env`・`jq . .env`・`source .env`・`. .env`・`vim .env`・`curl -d @.env http://localhost`・【LES】`sqlite3 .env`・`unzip -p .env` | 止 | 正常系 |
| `test_env_at_any_depth_then_blocked` | 【LES】`cat frontend/.env`・`cat tests/fixtures/deny_probe/.env`・`cat config/.env.development.local`・【LES】`cat frontend/.env.local` | 止 | 正常系 |
| `test_secret_env_variants_then_blocked` | `cat .env.local`・`cat .env.production`・`cat .env.staging`・`cat .env.test`・`cat .env.foo.local`（【LES】移植元にあった `cat .env.development` は決定3で通す側 10.2 `test_env_development_then_allowed` へ移した） | 止 | 正常系 |
| `test_settings_local_and_keys_then_blocked` | `cat .claude/settings.local.json`・`jq . .claude/settings.local.json`・`cat ~/.ssh/id_rsa`・`cat id_rsa.pub`・`cat ~/.ssh/id_ed25519`・`cat server.pem`・`cat certs/ca.pem`・`cat ~/claude-settings-backup/settings.local.json`・`cp -r ~/claude-settings-backup /tmp/x`・`cd .claude && cat settings.local.json`・`cat settings.local.json` | 止 | 正常系 |
| `test_path_forms_then_blocked` | `cat ./.env`・`cat ../.env`・【LES】`cat ../../proj/.env`・`cat /work/proj/.env`・`cat ~/pjt/proj/.env`・`cat "$CLAUDE_PROJECT_DIR"/.env`・`cat ${CLAUDE_PROJECT_DIR}/.env`・`cat $HOME/pjt/proj/.env`・`/usr/bin/cat .env` | 止 | すり抜け |
| `test_quoting_then_blocked` | `cat '.env'`・`cat ".env"`・`cat .e""nv`・`cat \.env`・`'cat' .env`・`"cat" ".env"` | 止 | すり抜け |
| `test_chained_then_blocked` | `ls; cat .env`・`cat .env;ls`・`true && cat .env`・`false \|\| cat .env`・`echo hi\|cat .env`・`cat .env \| head`・`(cat .env)`・`{ cat .env; }`・`ls\ncat .env`（改行）・`cat .env &` | 止 | すり抜け |
| `test_substitution_and_nesting_then_blocked` | `echo $(cat .env)`・`` echo `cat .env` ``・`cat $(echo .env)`・`bash -c "cat .env"`・`sh -c 'grep K .env'`・`eval "cat .env"`・`diff <(cat .env) x`・`paste <(grep K .env) y`・`echo x > >(cat .env)` | 止 | すり抜け |
| `test_split_across_commands_then_blocked` | `F=.env; cat $F`・`echo .env \| xargs cat`・`find . -name .env -exec cat {} \;`（移植元で以前ここにあった `ls .env && cat README.md` は 9節で「通」に変わり `test_name_only_commands_listing_only_then_allowed` に移した） | 止 | すり抜け |
| `test_wrappers_then_blocked` | `sudo cat .env`・`env cat .env`・`command cat .env`・`timeout 5 cat .env`・`nice cat .env`・`LANG=C cat .env`・`exec cat .env` | 止 | すり抜け |
| `test_input_redirect_then_blocked` | `while read l; do echo $l; done < .env`・`cat < .env`・`python3 < .env` | 止 | 正常系 |
| `test_interpreter_inline_code_then_blocked` | `python3 -c "print(open('.env').read())"`・`.venv/bin/python -c "import pathlib;print(pathlib.Path('.env').read_text())"`・`node -e "console.log(require('fs').readFileSync('.env','utf8'))"`・`python3 -I -c "print(open('.env').read())"`・`python3 -c "print(open('/x/.claude/settings.local.json').read())"` | 止 | 正常系 |
| `test_case_insensitive_names_then_blocked` | `cat .ENV`・`cat .Env.Local`・`cat ~/.ssh/ID_RSA`・`cat KEY.PEM`・`cat .CLAUDE/SETTINGS.LOCAL.JSON` | 止 | すり抜け |
| `test_case_insensitive_safe_names_then_allowed` | `cat .ENV.EXAMPLE`・`cat .Env.Sample`・`cat ENVIRONMENT.YML`・【LES】`cat FRONTEND/.ENV.DEVELOPMENT` | 通 | 境界値 |
| `test_glob_matching_dotenv_then_blocked` | `cat .env*`・`cat .e*`・`cat .*`・`cat .en?`・`cat *.pem`・`cat ~/.ssh/id_rsa*` | 止 | すり抜け |
| `test_non_secret_then_allowed` | `cat .env.example`・`cp .env.example .env.example.bak`・`cat .env.sample`・`cat .env.template`・`cat .envrc`・`cat environment.yml`・`cat src/env.py`・`grep -rn dotenv src/`・`cat *`・`cat *.py`・`cat docs/pem.md`・`cat .claude/settings.json` | 通 | 境界値 |
| `test_secret_mentioned_without_read_then_allowed` | `ls -la .env`・`test -f .env && echo ok`・`[ -f .env ] \|\| echo missing`・`find . -name ".env*"`・`git add .env.example`・`git status`・`ssh -i ~/.ssh/id_rsa host true`・`docker run --env-file=.env img` | 通 | 境界値 |
| `test_scripts_reading_env_internally_then_allowed` | 【LES】`.venv/bin/python -m src.main scenario.yaml`・`bash scripts/x.sh`・`python3 scripts/foo.py`・`source .venv/bin/activate && pytest` | 通 | 正常系 |
| `test_heredoc_body_is_not_scanned` | `git commit -m "$(cat <<'EOF'\n守る: .env を読まない\nEOF\n)"`・`cat <<'EOF' > notes.md\n.env は gitignore 済み\nEOF` | 通 | 境界値 |
| `test_blocked_reason_mentions_category_and_target` | `cat .env` | 理由が `guard: ` で始まり、`秘密ファイルの読み取り` と `.env` を含む | 正常系 |

### `TestProtectedWrite`（カテゴリB）
目的: 設定とフック（guard 自身を含む）がシェル経由で書き換わらないこと

| テストメソッド名 | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_redirect_into_protected_then_blocked` | `echo {} > .claude/settings.json`・`echo x >> .claude/settings.json`・`: > .claude/settings.local.json`・`echo x >.claude/hooks/guard.py`・`cat <<'EOF' > .claude/hooks/guard.py\nx\nEOF`・`printf x 2> .claude/hooks/a.py`・`echo x &> ~/.claude/settings.json` | 止 | 正常系/すり抜け |
| `test_tee_and_inplace_edit_then_blocked` | `echo x \| tee .claude/settings.json`・`echo x \| tee -a .claude/hooks/guard.py`・`sed -i 's/a/b/' .claude/settings.json`・`sed -i.bak 's/a/b/' .claude/hooks/guard.py`・`sed --in-place 's/a/b/' .claude/settings.json`・`perl -pi -e 's/a/b/' .claude/settings.json` | 止 | 正常系 |
| `test_copy_into_protected_then_blocked` | `cp /tmp/new.json .claude/settings.json`・`cp x.py .claude/hooks/`・`cp -t .claude/hooks x.py`・`rsync -a x/ .claude/hooks/`・`ln -sf /tmp/e.py .claude/hooks/guard.py`・`install -m 755 x .claude/hooks/x.py`・`dd if=/tmp/x of=.claude/settings.json` | 止 | 正常系 |
| `test_move_remove_chmod_protected_then_blocked` | `mv .claude/settings.json /tmp/`・`mv /tmp/s.json .claude/settings.json`・`mv .claude/hooks/guard.py /tmp/`・`rm .claude/hooks/guard.py`・`rm -f .claude/settings.json`・`rm -rf .claude/hooks`・`rm -rf .claude`・`git rm .claude/hooks/guard.py`・`git mv .claude/hooks/guard.py x.py`・`chmod -x .claude/hooks/guard.py`・`touch .claude/hooks/new.py`・`truncate -s0 .claude/settings.json` | 止 | 正常系 |
| `test_protected_path_forms_then_blocked` | `rm ./.claude/hooks/guard.py`・`rm "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py`・【LES】`rm /work/proj/.claude/settings.json`・`rm '.claude/hooks/guard.py'`・【LES】`rm ../proj/.claude/hooks/guard.py`・`ls && rm .claude/hooks/guard.py`・`bash -c "rm .claude/hooks/guard.py"`・`sudo rm .claude/settings.json` | 止 | すり抜け |
| `test_interpreter_script_args_not_inline_code` | `python3 scripts/x.py -e "open('.env')"`・`node app.js -c ".env"`・`python3 -m pytest -k env` | 通 | 境界値 |
| `test_process_substitution_writing_protected_then_blocked` | `echo x > >(tee .claude/settings.json)`・`diff <(echo a) <(rm .claude/hooks/guard.py)` | 止 | すり抜け |
| `test_cd_into_protected_then_write_blocked` | `cd .claude/hooks && rm guard.py`・`cd .claude; echo {} > settings.json`・`cd .claude/hooks && sed -i 's/a/b/' guard.py` | 止 | すり抜け |
| `test_read_or_execute_protected_then_allowed` | `cat .claude/settings.json`・`jq '.permissions.deny' .claude/settings.json`・`sed -n 1,20p .claude/hooks/guard.py`・`grep -n deny .claude/settings.json`・`diff .claude/settings.json /tmp/x`・`git diff .claude/settings.json`・`ls -la .claude/hooks`・`cp .claude/settings.json /tmp/bk.json`・【LES】`python3 .claude/hooks/pre_tool_fp_warning.py < /dev/null`・`echo '{}' \| python3 .claude/hooks/guard.py`・【LES】`bash .claude/hooks/x.sh`・`git add .claude/hooks/guard.py .claude/settings.json`・`cd .claude/hooks && ls` | 通 | 正常系 |
| `test_dev_null_and_fd_dup_then_allowed` | `cat .claude/settings.json 2>/dev/null`・`python3 .claude/hooks/guard.py < x.json 2>&1`・【LES】`cd .claude/hooks && python3 post_tool_run_tests.py 2>/dev/null`・`cd .claude/hooks && python3 x.py >&2`・`echo x > /dev/stderr` | 通 | 境界値 |
| `test_cd_into_protected_then_write_outside_allowed` | `cd .claude && cp settings.json /tmp/bk.json`・`cd .claude/hooks && cat guard.py > /tmp/guard_copy.py`・`cd .claude && echo x > ~/note.txt` | 通 | 境界値 |
| `test_writes_elsewhere_then_allowed` | `echo x > output/a.txt`・`sed -i 's/a/b/' src/x.py`・`cp a.json .claude-notes/settings.json`・`rm .claude_old/hooks.txt`・`echo x > docs/claude/settings.json` | 通 | 境界値 |
| `test_indirect_write_into_protected_then_blocked` | `find .claude/hooks -name '*.py' -exec rm {} \;`・`find .claude/hooks -name '*.pyc' -delete`・`find .claude -name settings.json -execdir sed -i 's/a/b/' {} +`・`echo .claude/hooks/guard.py \| xargs rm`・`ls .claude/hooks/*.py \| xargs sed -i 's/a/b/'`・`git -C .claude/hooks rm guard.py`・`git -C .claude mv settings.json /tmp/s.json` | 止 | すり抜け |
| `test_indirect_read_or_unrelated_write_then_allowed` | `find .claude -name settings.json -exec cat {} \;`・`find .claude/hooks -name '*.py' -exec cp {} /tmp/bk/ \;`・`ls .claude/hooks/*.py \| xargs grep foo`・`find . -name '*.pyc' -delete`・`find . -name '*.tmp' \| xargs rm -f`・`git -C sub rm old.py` | 通 | 境界値 |
| `test_cd_out_of_protected_then_write_allowed` | `cd .claude && ls; cd ..; echo x > out.txt`・`cd .claude/hooks; cd -; echo x > a.txt`・`cd .claude/hooks && cd /tmp && echo x > a.txt`・`pushd .claude/hooks && popd && echo x > a.txt`・`cd .claude && cd && echo x > a.txt` | 通 | 境界値 |
| `test_cd_moves_within_protected_then_write_blocked` | `cd .claude/hooks; cd ..; echo x > settings.json`・`cd .claude && cd hooks && rm guard.py`・`cd .claude && bash -c 'rm settings.json'; cd ..`・`cd /tmp; cd -; cd .claude/hooks && rm guard.py` | 止 | すり抜け |
| `test_blocked_reason_mentions_category_and_target` | `rm .claude/hooks/guard.py` | 理由が `保護対象の書き換え` と `.claude/hooks/guard.py` を含む | 正常系 |

注: `docs/claude/settings.json`・`.claude-notes/` は構成要素が `.claude` と完全一致しないので通す（部分一致にしない）。

### `TestIrreversibleOps`（カテゴリC）
目的: 取り返しのつかない git / rm を止め、日常の git / rm は止めないこと

| テストメソッド名 | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_force_push_then_blocked` | `git push --force`・`git push -f`・`git push origin main --force`・`git push --force-with-lease`・`git push --force-with-lease=main:abc`・`git push -fu origin main`・`git push origin +main`・`git -C /x push -f`・`'git' push "-f"`・`/usr/bin/git push --force` | 止 | 正常系/すり抜け |
| `test_reset_hard_then_blocked` | `git reset --hard`・`git reset --hard HEAD~1`・`git reset HEAD --hard`・`git -C x reset --hard`・`git status && git reset --hard` | 止 | 正常系 |
| `test_recursive_rm_broad_target_then_blocked` | `rm -rf /`・`rm -rf /*`・`rm -rf / --no-preserve-root`・`rm -rf ~`・`rm -rf ~/`・`rm -rf ~/*`・`rm -rf $HOME`・`rm -rf "$HOME"`・`rm -rf ${HOME}/*`・`rm -rf *`・`rm -rf .`・`rm -rf ./`・`rm -rf ./*`・`rm -rf ..`・`rm -rf ../*`・`rm -rf .*`・`rm -fr *`・`rm -r -f *`・`rm -R .`・`rm --recursive --force ~`・`rm -rfv *`・`rm -r *`・`sudo rm -rf /`・`cd /tmp && rm -rf *`・`rm -rf build *`（対象のどれかが広い） | 止 | 正常系/境界値 |
| `test_recursive_rm_project_root_then_blocked`（`project_dir="/work/proj"`） | `rm -rf /work/proj`・`rm -rf /work/proj/`・`rm -rf /work/proj/*`・`rm -rf /work`・`rm -rf "$CLAUDE_PROJECT_DIR"`・`rm -rf ${CLAUDE_PROJECT_DIR}/*` | 止 | 境界値 |
| `test_git_clean_force_with_ignored_then_blocked` | `git clean -fdx`・`git clean -fx`・`git clean -xdf`・`git clean -fX`・`git clean -f -d -x`・`git clean -d -x -f`・`git clean --force -x`・`git clean -ffdx`・`git -C x clean -fdx`・`git status && git clean -fdx`・`git clean -nfx` | 止 | 正常系/すり抜け |
| `test_git_clean_safe_forms_then_allowed` | `git clean -n`・`git clean -nd`・`git clean --dry-run -x`・`git clean -fd`・`git clean -f`・`git clean -f -d` | 通 | 境界値 |
| `test_git_checkout_whole_tree_then_blocked` | `git checkout -- .`・`git checkout .`・`git checkout HEAD -- .`・`git checkout -- ./`・`git checkout -- :/`・`git -C x checkout -- .` | 止 | 正常系 |
| `test_git_checkout_path_or_branch_then_allowed` | `git checkout -- path/file.py`・`git checkout -- src/x.py tests/y.py`・【LES】`git checkout main`・`git checkout -b feature/x`・`git checkout -`・`git restore .`・`git restore src/x.py`・`git branch -D old` | 通 | 境界値 |
| `test_everyday_git_then_allowed` | `git push`・【LES】`git push origin main`・`git push -u origin feature/x`・`git push --follow-tags`・`git push --no-force-with-lease`・`git reset`・`git reset --soft HEAD~1`・`git reset HEAD file.py`・`git log --oneline -5`・`git commit -m "force push を禁止"` | 通 | 境界値 |
| `test_recursive_rm_normalized_broad_then_blocked`（`project_dir="/work/proj"`） | `rm -rf ./.`・`rm -rf ../..`・`rm -rf src/..`・`rm -rf ~/.`・`rm -rf $HOME/..`・`rm -rf $CLAUDE_PROJECT_DIR/.`・`rm -rf "$PWD"`・`rm -rf ${PWD}/*`・`rm -rf ../proj`・`rm -rf //`・`rm -rf /work/./proj`・`rm -rf /work/proj/..` | 止 | すり抜け |
| `test_recursive_rm_normalized_broad_without_project_dir_then_blocked` | `rm -rf ./.`・`rm -rf ../..`・`rm -rf "$PWD"`・`rm -rf ~/.`・`rm -rf $CLAUDE_PROJECT_DIR/.` | 止 | すり抜け |
| `test_recursive_rm_narrow_or_unknown_then_allowed`（`project_dir="/work/proj"`） | `rm -rf "$(mktemp -d)"`・`rm -rf "$tmp"/x`・`rm -rf ../other/build`・`rm -rf ~/.cache/pip`・`rm -rf src/../build`・`rm -rf /work/proj/./output` | 通 | 境界値 |
| `test_everyday_rm_then_allowed`（`project_dir="/work/proj"`） | `rm -rf output/tmp`・`rm -rf ./build`・`rm -rf .pytest_cache __pycache__`・`rm -f *.pyc`・`rm *`（再帰なし）・`rm -rf /tmp/claude-1000/x`・`rm -rf /work/proj/output`・`rm -rf node_modules` | 通 | 境界値 |
| `test_push_delete_remote_ref_then_blocked`（C1b） | `git push origin :main`・`git push origin :refs/heads/feature/x`・`git push origin :refs/tags/v1.0`・`git push --delete origin feature`・`git push origin --delete feature`・`git push -d origin feature`・`git push origin feature -d`・`git push --dry-run --delete origin x`・`git push -nd origin x`・`git push --mirror`・`git push --mirror origin` | 止 | 正常系 |
| `test_push_delete_remote_ref_wrapped_then_blocked`（C1b） | `git -C /x push origin :main`・`git -c core.pager=cat push --delete origin x`・`git --git-dir=.git push --mirror`・`git --git-dir .git push origin :main`・`git --no-pager push -d origin x`・`'git' push "--delete" origin x`・`git push origin ':main'`・`/usr/bin/git push --mirror`・`bash -c "git push origin :main"`・`sh -c 'git push --delete origin x'`・`eval "git push --mirror"`・`sudo git push -d origin x`・`git status && git push origin :main`・`echo $(git push --delete origin x)` | 止 | すり抜け |
| `test_push_colon_refspec_not_delete_then_allowed`（C1b） | `git push origin HEAD:main`・`git push origin HEAD:refs/heads/feature/x`・`git push origin feature:feature`・`git push origin refs/heads/a:refs/heads/b`・`git push origin v1.0`・`git push origin refs/tags/v1.0:refs/tags/v1.0`・`git push --tags`・`git push origin :`（matching） | 通 | 境界値 |
| `test_push_plus_refspec_with_colon_then_blocked`（C1 との整合） | `git push origin +HEAD:main`・`git push origin +:main` | 止（C1 の `+` 規則で止まる。C1b を足しても変わらないこと） | 境界値 |
| `test_checkout_or_switch_discarding_changes_then_blocked`（C2d） | `git checkout -f main`・`git checkout -f`・`git checkout --force develop`・`git checkout main -f`・`git checkout -fq main`・`git checkout -fb x`・`git checkout -f -- file.py`・`git switch -f main`・`git switch --force main`・`git switch --discard-changes main`・`git switch main --discard-changes`・`git switch -f -c x` | 止 | 正常系 |
| `test_checkout_or_switch_discarding_changes_wrapped_then_blocked`（C2d） | `git -C /x checkout -f main`・`git -c advice.detachedHead=false checkout -f main`・`git --git-dir=.git --work-tree=. switch -f main`・`'git' checkout "-f" main`・`/usr/bin/git switch --discard-changes main`・`bash -c "git checkout -f main"`・`eval 'git switch -f main'`・`env GIT_TRACE=0 git checkout -f main`・`git fetch && git switch --discard-changes main`・`git stash; git checkout -f main` | 止 | すり抜け |
| `test_checkout_or_switch_everyday_then_allowed`（C2d） | `git checkout main`・`git checkout -b feature/fix`・`git checkout -bfix/x`（`-b` の値に `f` を含む）・`git checkout -t origin/feature`・`git checkout -`・`git checkout -- src/x.py`・`git checkout HEAD~1 -- file.py`・`git switch main`・`git switch -c feature/fix`・`git switch -cfeature`（`-c` の値に `f` を含む）・`git switch -`・`git switch --detach v1.0` | 通 | 境界値 |
| `test_restore_and_branch_delete_still_allowed` | `git restore .`・`git restore --staged .`・`git restore src/x.py`・`git branch -D old`・`git branch -d merged` | 通 | 境界値 |
| `test_blocked_reason_mentions_category` | `git push --force` | 理由が `取り返しのつかない操作` を含む | 正常系 |
| `test_blocked_reason_names_new_operations` | `git push origin :main`・`git push --delete origin x`・`git push --mirror`・`git checkout -f main`・`git switch --discard-changes main` | 理由が `取り返しのつかない操作` と、操作を示す語（それぞれ `:main`・`--delete`・`--mirror`・`-f`・`--discard-changes`）を含む | 正常系 |

### `TestEverydayCommandsAllowed`（全カテゴリ横断の回帰防止）
目的: このプロジェクトの日常コマンドが1つも止まらないこと（誤検知で作業が止まるのが最大のコスト）

| テストメソッド名 | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_project_daily_commands_then_allowed` | 【LES】`.venv/bin/python -m pytest tests/ -q -m "not slow"`・`.venv/bin/python -m pytest tests/hooks/test_guard.py -k env`・`.venv/bin/python -m src.main scenario.yaml`・`.venv/bin/python -m src.main data/scenarios/a.yaml`（README の手順。中身は読まない）・`cd frontend && npm run build`・`git status --porcelain`・`git diff --stat`・`git add -A && git commit -m "x"`・`ls -la`・`python3 -c "import json;print(json.load(open('.claude/settings.json'))['hooks'])"`・`grep -rn "Read(" .claude/settings.json`・`cat scenario.yaml`・`mkdir -p data/scenarios`（README の手順） | 通 | 正常系 |
| `test_project_daily_git_branch_and_push_then_allowed`（C1b／C2d の回帰防止） | 【LES】`git checkout main`・`git checkout main && git pull`・`git checkout -b feature/guard-git`・`git checkout -- tests/hooks/test_guard.py`・`git switch main`・`git switch -c fix/x`・`git push`・`git push origin main`・`git push -u origin feature/guard-git`・`git push origin HEAD:main`・`git push --follow-tags origin main`・`git commit -m "git push --delete と checkout -f を止める"`・`git log --oneline --diff-filter=D`（`D` を含むが push ではない）・`git diff --stat origin/main...HEAD` | 通 | 正常系 |
| `test_empty_or_whitespace_command_then_allowed` | `""`・`"   "`・`"\n"` | 通 | 境界値 |
| `test_unparseable_command_then_allowed` | `echo "unterminated`・`cat 'x` | 通 | 異常系 |
| `test_unparseable_tail_still_checks_earlier_lines` | `cat .env\necho "unterminated` | 止 | すり抜け |

### `TestMainContract`（入出力・fail-open）
目的: Claude Code との契約（exit 2＋stderr で止める／それ以外は exit 0 で黙る）を守り、guard の故障で Bash を止めないこと

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_block_exit2_reason_on_stderr` | stdin `{"tool_name":"Bash","tool_input":{"command":"cat .env"}}` | 戻り値 2・stderr が `check_command` の理由と一致（末尾改行は許容）・stdout 未使用 | 正常系 |
| `test_allow_exit0_silent` | 同 `"command":"ls"` | 0・stderr 空 | 正常系 |
| `test_invalid_input_fail_open`（parametrize） | stdin `""`・`"not json"`・`"[]"`・`"null"`・`{}`・`{"tool_name":"Bash"}`・`{"tool_name":"Bash","tool_input":{}}`・`{"tool_name":"Bash","tool_input":{"command":123}}`・`{"tool_name":"Bash","tool_input":"cat .env"}` | 0・stderr 空 | 異常系 |
| `test_non_bash_tool_ignored` | `{"tool_name":"Read","tool_input":{"command":"cat .env"}}` | 0 | 境界値 |
| `test_missing_tool_name_still_checked` | `{"tool_input":{"command":"cat .env"}}` | 2（tool_name 欠落は Bash とみなす。matcher が Bash なので欠落は想定外だが、止める側に倒しても誤検知の害がないため） | 境界値 |
| `test_internal_exception_fail_open` | `check_command` を例外を投げる関数に差し替え、stdin は `cat .env` | 0・stderr 空 | 異常系 |
| `test_project_dir_from_environ` | environ `{"CLAUDE_PROJECT_DIR":"/work/proj"}`、command `rm -rf /work/proj` | 2 | 正常系 |
| 【LES】`test_project_dir_from_environ_for_customer_data` | environ `{"CLAUDE_PROJECT_DIR":"/work/proj"}`、command `cat /work/proj/data/scenarios/a.yaml`（3.3 顧客データの置き場所の③。`project_dir` が無いと止まらない形） | 2 | 正常系 |
| `test_stderr_write_failure_still_blocks` | stdin `cat .env`、stderr を `write` で OSError を投げるものに差し替え | 2（理由が届かなくても止める判定は守る） | 異常系 |
| `test_never_opens_files` | `builtins.open`・`io.open`・`pathlib.Path.open`/`read_text`/`read_bytes` を「呼ばれたら AssertionError」に差し替え、`check_command("cat .env")` と `check_command("ls")`、【LES】`check_command("sqlite3 data/clients.db .tables", "/work/proj")` を呼ぶ | 例外なく 止／通 を返す | 副作用 |
| `test_no_subprocess` | `subprocess.run`・`subprocess.Popen`・`os.system` を「呼ばれたら AssertionError」に差し替えて `main` を呼ぶ | 例外なし | 副作用 |
| `test_long_command_finishes_quickly` | 9.7 の測り方（比で線形性を確かめる）。入力形 `many_cmds`・`quotes`・`nested_subst`・`many_xargs`・`long_cd`・`many_listing` | 9.7 の合格条件1・2 | 境界値 |
| `test_long_eval_chain_still_checked_quickly` | `"eval " * n + "cat .env"`（9.7） | 止・9.7 の合格条件1・2 | 境界値 |
| `test_subprocess_block` | `[sys.executable, HOOK_PATH]` を stdin `cat tests/fixtures/deny_probe/.env` の JSON で起動（env は `PATH` のみ＋`CLAUDE_PROJECT_DIR`=tmp_path） | returncode 2・stderr が `guard: ` で始まる・stdout 空・stderr に `DUMMY` を含まない | 統合 |
| `test_subprocess_allow` | 同 `ls` | returncode 0・stdout/stderr 空 | 統合 |
| `test_subprocess_garbage_stdin` | stdin `"\x00\xff not json"`（bytes） | returncode 0 | 異常系 |

### `TestRepositoryIntegration`
目的: settings.json の deny と guard の守備範囲がずれないこと／配線が正しいこと（【LES】タスク3d）

| テストメソッド名 | 条件 | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_every_read_deny_is_covered` | `.claude/settings.json` の `permissions.deny` のうち `Read(...)` の集合が、テスト内の対応表 `DENY_SAMPLES` のキー集合と**一致**し、各サンプルで `check_command(f"cat {sample}", project_dir=<プロジェクト>)` が止。【LES】`DENY_SAMPLES` は次の16件（タスク1の deny と同じ）: `"Read(./.env)": ".env"`・`"Read(**/.env)": "a/b/.env"`・`"Read(**/.env.local)": "x/.env.local"`・`"Read(**/.env.*.local)": ".env.dev.local"`・`"Read(**/.env.production*)": ".env.production"`・`"Read(**/.env.staging*)": ".env.staging"`・`"Read(**/.env.test*)": ".env.test"`・`"Read(**/*.pem)": "k.pem"`・`"Read(**/id_rsa*)": "id_rsa"`・`"Read(~/claude-settings-backup/**)": "~/claude-settings-backup/s.json"`・`"Read(./data/**)": "data/scenarios/a.yaml"`・`"Read(./.claude/settings.local.json)": ".claude/settings.local.json"`・`"Read(**/*.db)": "a/b/x.db"`・`"Read(**/*.sqlite*)": "x.sqlite3"`・`"Read(**/*.xlsx)": "out/x.xlsx"`・`"Read(~/.config/**/clients.db)": "~/.config/x/clients.db"`（移植元にあった `Read(**/.env.development*)` は LES の deny に無いので入れない＝決定3） | deny に新しい Read 規則が増えたら対応表を足すまで赤になる（guard の追従漏れを検出）。deny から消したら対応表も消すまで赤になる | 統合 |
| 【LES】`test_deny_exception_is_also_allowed_by_guard` | deny に `Read(**/.env.development*)` が**無い**こと、かつ `check_command("cat frontend/.env.development")` が通（決定3の例外が deny と guard でそろう） | 一致 | 統合 |
| `test_settings_wires_guard`（**配線の工程＝タスク4で書く**） | `settings["hooks"]["PreToolUse"]` に `matcher == "Bash"` のグループがあり、その `hooks` のどれかで `type == "command"` かつ `command == 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py'`、その hook の `timeout == 10`（**この3キーだけ比べる**。`statusMessage` などの追加キーは許す。辞書の完全一致にしない）。【LES】タスク2の `Edit\|Write` グループ（`pre_tool_fp_warning.py`・`post_tool_run_tests.py`）の確認（`docs/design/test_spec_edit_hooks.md` の G1〜G4）も同じ工程でまとめて書く | 一致 | 統合 |

- 【LES】`test_every_read_deny_is_covered` は `project_dir` を渡して呼ぶ（`Read(./data/**)` のサンプルは相対パスなので、`project_dir` が無くても止まる。渡すのは本番の `main` と同じ条件で確かめるため）。`<プロジェクト>` はテストのリポジトリのパス（`.claude/settings.json` を読むのと同じ場所）
- 【LES】サンプルのうち `data/scenarios/a.yaml` は顧客データの置き場所（3.3）でしか止まらない形にする（拡張子で止まる `data/clients.db` にしない。`data/` の規則が抜けたら赤になるように）

## 5. Fixture・前提条件
- 実ファイルは不要（`check_command` は文字列判定）。`tmp_path` は subprocess テストの `CLAUDE_PROJECT_DIR` にだけ使う
- **本物の `.env`・`.claude/settings.local.json`・【LES】`data/` 配下・`*.db`・`*.xlsx` を開くテストを書かない**。subprocess で `cat`・`sqlite3` を実際に走らせるテストも書かない（guard は判定だけで、コマンドは実行しない）
- 【LES】**`tests/fixtures/deny_probe/.env`**（3c で作る）:
  - 中身は `DUMMY=1` の1行だけ（本物の秘密を入れない）
  - `.gitignore` の `.env` 行（直下に限らず全階層の `.env` を除外する）に掛かるので、除外を打ち消す行 `!tests/fixtures/deny_probe/.env` を `.env` 行より**後ろ**に足す。受け入れ基準: `git check-ignore tests/fixtures/deny_probe/.env` が「無視されない」（終了コード 1）・`git ls-files` に載る（clone した人も実機確認＝タスク6 に使える）・他の `.env`（直下・`frontend/`）は引き続き無視される（`git check-ignore .env frontend/.env` が両方とも無視）
  - テストではパス文字列として使うだけ。stderr に `DUMMY` が出ないことの確認に使う（ファイルが無くても単体テストは通る。ファイルはタスク6の実機確認のため）
  - 作るときは Write ツールで書く（Bash の `echo DUMMY=1 > …/.env` は guard の対象外だが、Read の deny で中身を読み返せないので、書いた内容を確かめる手段がない。中身が `DUMMY=1` であることは `git diff --cached --stat` と、運営者の目視で確かめる）
  - 【LES】タスク6の `dummy.db`・`cf_simulation_dummy.xlsx` は**作らない**（文字列だけで確かめる。`.gitignore` の `*.db`・`*.xlsx` に掛かり、除外を打ち消す行を増やしたくない）
- ヘルパー（`run_main(stdin_text, environ)` → `(code, stderr)` など）はテストモジュール内に閉じるか `tests/hooks/conftest.py` に置く（2節。architect が決める）
- `TestRepositoryIntegration` は実リポジトリの `.claude/settings.json` を**読むだけ**
- 【LES】**性能テストの `slow`**（3c。11節 決定4）: 受け入れ基準は次の3つ
  - `TestMainContract.test_long_command_finishes_quickly`・`test_long_eval_chain_still_checked_quickly`（9.7 で名前を改めたときはその名前）に `@pytest.mark.slow` が付いている。guard のテストのうち、他のメソッドには付けない
  - `pytest.ini` の `slow` の説明が、WeasyPrint だけでなく guard の性能テストも含む形になっている（例: `slow: 時間のかかるテスト（WeasyPrint を実際に呼び出すテスト・guard の性能テスト）。通常の CI では -m "not slow" で除外可`）
  - `.venv/bin/python -m pytest tests/hooks/test_guard.py -q -m "not slow"` で性能テストが選ばれず（deselected に数えられる）、`-m slow` で性能テストだけが走る。テスト実行フック（タスク2。`-m "not slow"`）からは外れる
- 【LES】**README の「データの置き場所」**（3c。11節 決定6）: 節の中に「`data/scenarios/` などのファイル名に顧客の名前を使わない（ファイル名は `ls` などで会話・画面に出るため）」という1文が入っている。表・既存の文は変えない。出力の Excel（`cf_simulation_YYYYMMDD.xlsx`）と DB（`clients.db`）はコードが名前を決めるので対象外で、名前を付けるのは利用者が作る実データのシナリオ

## 6. 配線（タスク4。guard.py とテストが揃い reviewer を通った後）
- `.claude/settings.json` の `hooks.PreToolUse` に追加:
  ```json
  {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard.py", "timeout": 10}]}
  ```
- 配線後は guard 自身が「シェルで settings.json を書く」ことを止めるので、**配線は Edit ツール（承認あり）で行う**。以後の guard.py の修正も Edit ツール経由（Edit/Write は matcher `Bash` の対象外であり、承認プロンプトで人が見る）
- 配線後の実地確認（タスク6・人の立ち会いのもと）: `cat tests/fixtures/deny_probe/.env` が止まり理由が出ること、【LES】`sqlite3 tests/fixtures/deny_probe/dummy.db .tables`・`cat tests/fixtures/deny_probe/cf_simulation_dummy.xlsx` が止まること（ファイルは作らない）、`cat .claude/settings.json`・`git status --short`・`.venv/bin/python -m pytest tests/hooks/ -q` が通ること。**本物の `.env`・顧客データで試さない**

## 7. 判断した論点
1〜16 は移植元で決めたもの（引き継ぐ）。17 以降は【LES】。
1. **テスト置き場は `tests/hooks/`**（2節）
2. **秘密パスの読み取りは「コマンド全体での同居」で止める**（単純コマンド単位にしない）。`F=.env; cat $F`・`echo .env | xargs cat`・`cat $(echo .env)` を拾うため。代償は誤検知（`grep -rn ".env" docs/` も止まる）。除外の値・「一覧だけ」の名前は 9節で例外にした。止まっても Read/Grep ツールという逃げ道があるので許容
3. **`.env.*` は「example / sample / template 以外すべて秘密」**。deny 一覧より広い。未知の名前（`.env.prod2`）を通さない側に倒す。【LES】`.env.development` だけは決定3で外す（17）
4. **`rm -rf` を `rm -r` まで広げる**。破壊の本体は再帰で、`-f` は確認を省くだけのため
5. **鍵に `id_ed25519*`・`id_ecdsa*`・`id_dsa*` を加える**（現在の ssh 既定鍵は ed25519）。deny 一覧には無い
6. **ヒアドキュメント本文は判定しない**。コミットメッセージや文書作成で `.env` という語を書くたびに止まるのを避けるため。代償: `python3 - <<EOF … open('.env') … EOF` はすり抜ける
7. **`cp` は向きで扱いを変える**: 秘密パスはどちらの位置でも止め（元＝持ち出し、先＝上書き）、保護パスは書き込み先のときだけ止める（バックアップを取る `cp .claude/settings.json /tmp/` を通すため）
8. **インタプリタの `-c` は秘密の読み取りだけ見る**。保護対象の書き込み（`python3 -c "open('.claude/settings.json','w')"`）は見ない。設定を読む `python3 -c "json.load(open('.claude/settings.json'))"` が日常的で、文字列から読み書きを区別できないため
9. **`git clean` は `-f` と `-x`/`-X` が揃ったときだけ止める**／**`git checkout` はパス `.`（`./`・`:/`）のときだけ止める**。`git clean -fd` は無視ファイルを残すので通す。`git restore`・`git branch -D` は対象外
10. **`tool_name` 欠落は Bash とみなす**、`Bash` 以外の明示は通す
11. **guard はファイルを開かない・外部コマンドを起動しない**（テストで保証）。判定の材料はコマンド文字列と `CLAUDE_PROJECT_DIR` だけ
12. **リモートの削除・上書き（C1b）と、未コミット変更を捨てる切り替え（C2d）を C に加える**。止めるのは決まった形（`:<ref>`・`--delete`／`-d`・`--mirror`・`checkout -f`／`--force`・`switch -f`／`--force`／`--discard-changes`）に限り、広げない（`--prune`・`checkout -B`・`switch -C` は追加しない。8節）
13. **コロン refspec は「左が空で右が空でない」ときだけ削除とみなす**。`HEAD:main`・タグ・`a:b` は通常の push、`:` だけは matching push で、どちらもリモートを消さない。`+` で始まるものは C1 の規則をそのまま使う
14. **`git checkout -f` はブランチ名・パスの有無を問わず止める**。`-f` の後ろがブランチかパスかを文字列だけで区別できないため。`-f` を外せば通る逃げ道がある
15. **`-n`／`--dry-run` 付きでも C1b は止める**（C2b と同じ。判定を単純に保つ）
16. **束の読み方は C1（`f`）に揃える**（`d` も束のどこにあっても当たる）。例外は C2d の値を取る短いオプション（checkout の `b`/`B`・switch の `c`/`C`）。`git push -o <値>` の値をくっつけて書く形（`-odeploy`）は誤検知しうるが許容する
17. 【LES】**`.env.development` の例外は「basename がちょうど `.env.development`」に限る**（任意の階層）。`SAFE_ENV_SUFFIXES` に `development` を足す形にはしない: 移植元の規則は `.env.<x>` の `<x>` を最初の `.` までで読むので、足すと `.env.development.local`（Vite のローカルの秘密の置き場所）まで通ってしまう。`frontend/` に限らないのは、`cd frontend && cat .env.development` を止めないため（guard は cd 先でパスをつながない）と、deny 側も `.env.development` を階層を問わず読める形にしたため（タスク1）
18. 【LES】**`data/` はプロジェクト直下だけを指す**（先頭側で判定する。3.2・3.3）。`.gitignore` が `/data/` と先頭に `/` を付けた理由（`src/data/`・`frontend/src/data/` のようなソースのフォルダまで巻き込まない）と同じ。構成要素のどこかに `data` があれば止める形（移植元の `claude-settings-backup` と同じ形）は採らない。`electron/node_modules/…/data` などの無関係なフォルダや、`grep -rn "x/data/y"` のような語まで止まるため
19. 【LES】**`data` だけの語（`/` を含まない）も A1・A2 では数える**。`cd data && cat scenarios/a.yaml`・`grep -r KEY data`・`cp -r data /tmp/x`・`tar czf x.tgz data` を拾うため（cd の引数は 9.2.1 のとおり数える）。代償は `grep -rn data src/` のように、パターンが `data` だけの検索が止まること（9.6 の「grep のパターンの区別は先送り」と同じ種類の誤検知。Grep ツールが逃げ道）。**A3（インラインコード）では `data` だけの語は数えない**（Python の変数名 `data` が日常的で、`python3 -c "data = json.load(…)"` を止めると guard を避ける回り道を招くため）。代償は `python3 -c "from pathlib import Path; print([p.read_text() for p in Path('data').rglob('*')])"` のような形が通ること（8節）。11節 決定1で確定
20. 【LES】**顧客 DB・Excel の glob は「拡張子の側」で判定する**。`*.db`・`clients.d?`・`*.xls?`・`*.*` は止め、`*`・`cf_*` は通す。`*` まで止めると `cat *`・`grep x src/*` のような日常の形がすべて止まる。`*` は直下に顧客ファイルがあるときだけ危ないが、直下の `clients.db`・`cf_simulation_*.xlsx` は運営者が `data/` に移す（タスク0.5）ので、移した後は直下の `*` に顧客ファイルは当たらない
21. 【LES】**`sqlite3`・`unzip` は動詞として足すだけで、オプションを読み分けない**。`unzip -l x.xlsx`（名前の一覧だけ）・`unzip x.zip -x '*.db'`（除外の指定）も止まる（誤検知の側）。`--exclude` の値を割り引くコマンド（9.3）・一覧だけの許可リスト（9.4）に `sqlite3`・`unzip` を**足さない**（足すと 9.3・9.4 の「通すことで増える経路が無いことの確認」をやり直す必要がある。差分を2点に保つ）
22. 【LES】**カテゴリ名・理由文は移植元のまま**（3.6）。顧客データでも「秘密ファイルの読み取り」と出す。AI が取るべき行動（回避せず人に判断を求める）は同じで、文言を分けても行動は変わらないため
23. 【LES】**`..` を挟んだ `data/` は、書いたままの形と `..` を解いた形の両方で見る**（11節 決定11）。解いた形だけに置き換えない: 置き換えると、今止まっている `cat data/../src/a.py`（書いたままの最初の構成要素が `data`）・`cat /work/proj/../data/x`（書いたままの形で `proj` の直後が `data`）が通るようになり、止める側にだけ倒すという決定から外れる。**`..` でプロジェクトの外に出る形は止める**: `cat ../data/x`・`cat src/../../data/x`（相対パスの先頭に余る `..`）は、Bash の cwd がプロジェクトのどの階層か文字列から分からず（`cd src && cat ../data/x` はプロジェクト直下の `data/` を読む）、`cat $CLAUDE_PROJECT_DIR/../data/x`・`cat /work/proj/../data/x` は書いたままの形でプロジェクトの直後に `data` が並ぶ。どれも外の `data/` を読むこともあるが、止まっても書き直す手間だけで済み、通すと顧客データが出うるので止める側に置く。解いた形は前置部分（`~`・`$CLAUDE_PROJECT_DIR` など）より前に戻さない: `~/../data/x` を `data/x` と読むと、`~` の親の `data/` を「プロジェクト直下」と取り違えるため（どちらに転んでも顧客データは出ないので、テストでは固定しない）。シンボリックリンクは解かない（bash の `cat` は `src/..` を実際のリンク先の親として読むが、guard はファイルシステムを見ない。リンク経由の取り違えは止める側の誤差か、8節の既存の穴に入る）

## 8. 守備範囲外（止めない・既知の穴）
fail-open と「善意のうっかり」前提の割り切り。ここに書いたものは**テストで「通る」ことを固定しない**（将来塞いでも既存テストが壊れないように）。例外として、運営者が「誤検知として受け入れる」と決めた形は止める側のテストに置いたものがある（9.5・9.10・【LES】11節 決定11）。

**移植元から引き継ぐもの**:
- 読み取り動詞リストに無いコマンドでの読み取り（`python3 scripts/x.py .env` のような引数渡し、`awk` の別名など未知のツール）
- 名前を変えてからの読み取り（`mv .env x.txt; cat x.txt`）、変数の間接展開・エンコード（`cat $(printf '\x2eenv')`）
- `grep -r KEY .`・`rg --no-ignore KEY` のような、秘密パスを名指ししない再帰検索（`.env` を含むディレクトリ全体を読む）。※最も現実的な穴。【LES】`data/` も同じ（`grep -r KEY .` は `data/` の中まで読む）。対策（`grep -r` に `--exclude-dir=data` を必須にする等）は誤検知が大きいので別途判断
- `git show HEAD:.env`・`git diff --no-index .env x`・`git stash show -p` など git 経由の読み取り
- `.env` そのものへの書き込み・削除（`echo x > .env`・`rm .env`）、`git add -f .env`
- `git restore`（`git restore .` を含む）・`git branch -D`：対象外（移植元で決定）。テストでは日常操作として「通す」に含める
- `git clean -fd`（`-x`/`-X` なし。無視ファイル＝`.env`・【LES】`data/` は消えない。テストで「通す」に固定）
- `git stash drop/clear`・`find … -delete`
- `git checkout` のパス `.` 以外での広い指定（`git checkout -- *`・`git checkout -- src/`）
- `.envrc`・`*.env`・`credentials.json` など deny 一覧に無い秘密らしきファイル
- Edit / Write / Read / Grep ツール（matcher `Bash` の対象外。deny ルールと承認プロンプトの担当）
- 承認の外で、引き続き止めないもの: `git push --prune`、`git checkout -B`・`git switch -C`／`--force-create`（移植元で「足さない・記録だけ」と決定）
- git の長いオプションの省略形（`git push --delet`・`git switch --discard`・`git checkout --forc`）。完全一致でしか見ない
- `git --config-env <名前>=<環境変数> push …` のように、グローバルオプション表に無い値つきオプションの後ろのサブコマンド
- git の alias 経由（`git -c alias.nuke='push --delete' nuke origin main`・`git config alias.co 'checkout -f'` の後の `git co main`）。guard は git の設定を読まない
- git のサブコマンドを直接呼ぶ形（`/usr/lib/git-core/git-push origin :main`・`git-checkout -f`）
- （穴ではないことの確認）`git checkout -Bf x`・`git switch -Cf x` は「`-B`/`-C` にブランチ名 `f` を渡す」の意味で、強制ではない
- `ln -s .claude/hooks/guard.py g.py; echo x > g.py` など別名を作ってからの書き込み
- `rm -rf ~/pjt/proj` のように `~` 起点でプロジェクトを名指しするもの（HOME を判定材料にしていないため。`~` そのもの・`~/.`・`~/..` は止まる）
- `cat .claude/settings.local.json.bak` など秘密ファイルの別名コピー（basename 判定のため）
- 長いオプションの省略形（`grep --reg --exclude .env`）: 9.3.1 の表は完全一致でしか見ないので割り引いて通す
- 9.3.1 の表の漏れ: 表に無い値つきオプションが前にあると、J2 と同じ形で通る。見つかったら表に足す
- extglob（`shopt -s extglob` の後の `rm /tmp/@(…)/…/.claude/…`）: 意図的な回避
- **行継続をはさんだ置換 `$\<改行>(…)`**: bash は単一引用符の外の `\<改行>` を最初に取り除くが、guard の字句解析は外さず `(` で単純コマンドを切る。`rm /tmp/$\<改行>(echo ..)/work/proj/.claude/settings.json`・`rm $\<改行>(true).claude/hooks/guard.py` が通る。テストは strict な xfail（9.5 の c09）。直し方の案: 字句解析の前に、単一引用符の外の行継続を外す（ヒアドキュメント本文と単一引用符の中は外さない）
- 包み込み表に無いコマンド経由: `stdbuf -o0 BODY`・`setsid BODY`・`watch BODY`・`flock /tmp/l BODY`・`ionice BODY`・`doas BODY`・`strace BODY`・`unbuffer BODY`（BODY が `cat .env` でも通る）
- 誤検知側: `git ls-files .claude \| xargs -I{} cp {} /tmp/bk` が止まる（xargs の書き込み先を「コマンド全体」で近似するため）。サブシェル `(cd .claude && …); echo x > a` の後も `.claude` の中とみなす
- 誤検知側（受け入れ。9.5・9.10 決定1）: xargs で書き込むコマンドがあるとき、`/tmp` の下の `.claude` も保護パスとして数える。`echo /tmp/p/.claude/hooks/x.py \| xargs rm`（止めるテストに固定）・`find /tmp/p/.claude -name '*.pyc' -print0 \| xargs -0 rm`・`echo x \| xargs rm /tmp/p/.claude/hooks/x.py` が止まる（後ろ2つはテストで固定しない）。逃げ道: `find … -delete`・`find … -exec rm {} +`・`rm` を直接書く形
- `find … -exec xargs …`: find の `-exec` の中では xargs から来たことが落ち、9.5 の「xargs には当てない」が効かない。善意ではまず書かない形。テストで固定しない
- POSIXLY_CORRECT の見えない形: 名前を文字列に出さずに設定する形（`env $'POSIXLY\x5fCORRECT=1' grep …`・`source envfile; grep …`）と、Bash ツールのシェルが始めから `POSIXLY_CORRECT` を持っている場合（guard は自分の環境変数を判定材料にしない。7節-11）
- 9節の規則で新しく通るようになる形（範囲外・記録だけ）: `PATH=/tmp/x ls .env | cat`（許可リストの名前を別の実行ファイルに差し替える）／`git ls-files -X .env`・`git ls-files --exclude-from .env | cat`・`--exclude-per-directory .env`・`-x`・`--exclude`（`.env` を除外パターンとして読むだけで、中身は出力されない）
- `/tmp` の試作を丸ごとプロジェクトへコピーする形（`cp -r /tmp/p/. <プロジェクト>`・`rsync -a /tmp/p/ <プロジェクト>/`・`cp -r /tmp/p/.claude .`）。コピー元の下に `.claude` があるかは文字列だけでは分からない
- 既存の穴（9節と無関係）: `xargs -a .env`・`xargs --arg-file=.env`（xargs の既定コマンド `echo` が中身を出す）／`env -S 'cat .env'`／`git -c core.pager='cat .env' -p status`／`cat ${ find . -name .env; }`（bash 5.3 の置換）
- 9節で先送りにしたもの: grep のパターン（最初の被演算子）の区別、`diff -x`・`rsync --filter`・`zip -x`・`ag --ignore`
- 設計固有の既知の穴: `$( … )` 内の `case` パターンの `)` で置換が早く閉じる／全体の解析失敗時の行ごと判定でヒアドキュメント本文も判定される（誤検知側）／値を取るオプション（`python3 -W ignore -c …`）があるとインラインコードを見つけられない（`bash -o` のみ対応）／`cd .claude` の後は `.claude` 以下への相対パスの書き込みすべて（`skills/…` を含む）を止める（誤検知側）

**【LES】LES の差分で生じる穴・受け入れた止まりすぎ**（どれもテストで固定しない）:
- 穴: 拡張子の無い DB（`sqlite3 mydb .tables`）、SQLite の付随ファイル `clients.db-wal`・`clients.db-shm`・`clients.db-journal`（basename が `.db` で終わらない。`data/` の下なら置き場所の規則で止まる。Electron の保存先 `~/.config/…/` に出たものは止まらない。deny も同じ。記録だけ＝11節 決定7。足すときは deny と guard を同時に足す）
- 穴: `.xlsm`・`.xls`・`.csv` など `.xlsx` 以外の表計算の形式（LES の出力は `.xlsx` だけ）
- 穴: `.`の無い glob（`cat cf_*`・`cat *`・`grep KEY d*/scenarios/*`）。7節-20
- 穴: インラインコードの中の `data` だけの語（`Path('data').rglob('*')`）。7節-19
- 穴: `~` 起点やプロジェクト外の書き方で、プロジェクトのフォルダ名が途中に出ない `data/`（`cd ~/pjt && cat proj2/data/x` で `proj2` がプロジェクトのフォルダ名と違う場合など）。プロジェクトのフォルダ名と違う名前のシンボリックリンク経由も同じ
- 穴: `data/` の**ファイル名**が会話に出ること（`ls data/scenarios`・`find data -type f`・`git status` など）。ファイル名に顧客の名前を使うと個人情報になる。guard は読み取り動詞が無いコマンドを止めない。guard では扱わず、ファイル名に顧客の名前を使わない運用を README に書く（11節 決定6・5節）
- 穴: `rm -rf data`・`rm data/clients.db`（顧客データの削除）。広い対象ではないので C3 に当たらない。今回は直さず記録する（11節 決定5）。`git clean -fdx` は C2b で止まる
- 穴（移植元にもある・B）: `unzip -o x.zip -d .claude/hooks`・`tar xzf x.tgz -C .claude/hooks`（展開先として保護パスに書き込む）。B の書き込み操作の表に展開系が無い。記録だけ（11節 決定8。直すなら移植元と同時に）
- 止まりすぎ: パターンが顧客データの名前・拡張子に見える grep（`grep -rn clients.db src/`・`git ls-files | grep '\.db'`・`grep -rn data src/`・9.2.1 の実際の形の `\.sqlite`＝11節 決定9）。9.6 の「grep のパターンの区別は先送り」と同じ。逃げ道: Grep ツール／`'clients[.]db'`・`'\.db$'`・`'[.]sqlite'` のように書く
- 止まりすぎ: LES のパッケージ名 `src.db`（`grep -rn "src.db" src/`・`python3 -c "import src.db"`・`python3 -c "from src.db.sqlite_repository import SqliteRepository"`）。`src.db` は basename が `.db` で終わり、`src.db.sqlite_repository` は `.sqlite` を含む。逃げ道: テストに書く・Grep ツール。受け入れる（11節 決定3。実際の作業で何度も当たったら、`src.db`・`src.db.…` を外す例外を足す）
- 止まりすぎ: CLI・スクリプトの出力をフィルタに通す形（`.venv/bin/python -m src.main data/scenarios/a.yaml | tail -3`）。コマンド全体で「動詞＋秘密名」を見るため（7節-2）
- 止まりすぎ: find の探し始める場所が `data`（`find data -name '*.yaml' | sort`）。9.4 で割り引くのは名前条件の値だけ（cd の引数と同じく、場所は数える）。`find data -type f`（フィルタ無し）は通る
- 止まりすぎ: `unzip -l x.xlsx`・`unzip x.zip -x '*.db'`（7節-21）
- 穴（11節 決定12。2026-11-01 の 3e レビューで見つかったもの。記録だけ）:
  - H2: SQL 文字列の中で開く DB（`sqlite3 :memory: "ATTACH 'data/clients.db' AS c; …"`・`sqlite3 :memory: ".open 'data/clients.db'"`）。sqlite3 の引数の文字列の中の語はパスとして数えない（A1 はトークン単位、A3 はインタプリタの `-c`／`-e` だけ）。移植元の awk のプログラム（`awk 'BEGIN{while((getline l < ".env")>0) print l}'`）の穴と同じ種類で、プログラム・SQL の文字列の中身を読み分けない作りから来る
  - H3: ブレース展開（`cat *.{db,xlsx}`・`cat clients.{db,txt}`）。guard はブレースを展開せず、basename `*.{db,xlsx}`・`clients.{db,txt}` はどの秘密の規則にも当たらない。移植元にもある穴（`cat .{env,x}` など）で、移植元で直すときに LES の語彙（L1〜L4）の分も一緒に直す
  - H4: 3.2 の前置部分の表に無い変数で始まるパス（`cat $PWD/data/x`・`cat ${CLAUDE_PROJECT_DIR:-.}/data/x`）。①は相対パスだけ、②は `$CLAUDE_PROJECT_DIR`・`${CLAUDE_PROJECT_DIR}` そのものだけを見るので、`$PWD` と、既定値つきの展開 `${…:-…}` は当たらない
  - ヒアドキュメントで渡す Python（`python3 - <<'EOF' … sqlite3.connect('data/clients.db') … EOF`）: 移植元 7節-6 で受け入れた穴（ヒアドキュメントの本文は判定しない）。**LES では漏れるものが `.env` から顧客データ（DB・Excel・シナリオ）に広がる**
  - here-string で xargs に渡すパス（`xargs cat <<< .env`・`xargs cat <<< src/../data/x`）: A1 は `<<<` の右側をヒアドキュメントと同じく判定から外すが、xargs はその中身を引数にして `cat` を走らせる。移植元にもある穴（2026-11-01 の決定11のレビューで発見・運営者決定で記録だけ。直すなら移植元と同時に）
- 止まりすぎ（11節 決定11の代償。テストでは 10.2 で止める側に固定したもの以外は固定しない）: 書いたままの形で `data` が先に出る `cat data/../src/a.py`（止める側に固定）、プロジェクトの外の `data/` を `..` で指す `cat ../data/x`・`cat /work/proj/../data/x`（止める側に固定。7節-23）

## 実装者へのノート
- パラメータ化の `ids=` にコマンド文字列をそのまま使うと改行・記号で読みにくいので、短い id を付ける
- 「止」の判定は `assert check_command(cmd)`（非空文字列）、「通」は `assert check_command(cmd) is None`。失敗時に理由文が見えるよう `f"{cmd!r} -> {result!r}"` をメッセージに入れる
- 改行を含むコマンドは Python の文字列リテラルで `\n` を使う（表の `\n` は改行の意味）
- 時間のテストは `time.process_time()`（このプロセスの CPU 時間）で測る。測り方は 9.7
- 理由文の完全一致はテストしない（カテゴリ名と対象を含むことだけ）。文言の調整で赤にならないように
- 【LES】移植元のテストを複製してから、本書の【LES】の行（パスの置き換え・移したパラメータ・足したメソッド）を当てる。移植元のテストと本書がずれていたら本書を正とする
- 【LES】テストのパラメータにリポジトリの実パス（`/home/…`）を書かない。プロジェクトは `/work/proj`、他のプロジェクトは `/work/other`・`~/pjt/other`、ユーザー設定は `/home/user/.claude/…` で書く

## 9. 誤検知の修正（移植元で決定・引き継ぐ）

> 移植元のコミット `d20ea9a` で入った修正。移植元で運営者が決めたこと（9.8〜9.10）をそのまま引き継ぐ。**このうち2件目の誤検知（9.2.1）は LES での作業中に実際に起きた形**で、LES にこそ要る。

### 9.1 目的
- **成功**: 秘密の中身を読まない操作（秘密を検索から**外す**指定・名前の**一覧**）と、プロジェクトの外の使い捨て置き場への書き込みが止まらない。止まると AI が別名に置き直すなどの回り道をし、作業が遅れるうえ「guard を避ける」癖がつく
- **失敗**: 通すようにしたことで、秘密の中身が会話に出る経路・プロジェクト（またはユーザー設定）の `.claude/` を書き換える経路が**1つでも増える**。本節の「止め続ける」表はそのための回帰防止で、通す表と同じ重さで扱う

### 9.2 根本原因
3件とも「**コマンド文字列に秘密名・保護パスが出たら、それが何の役割の語かを見ずに止める**」ことから起きている。

| # | 実際の形 | 止める規則 | なぜ止まるか |
| --- | --- | --- | --- |
| 1 | `grep -r --exclude=.env* <パターン> .` | A1 | `grep` が読み取り動詞で、`--exclude=.env*` は `名前=` を外して `.env*`（glob）→ 秘密パスと判定。除外の値か読む対象かを区別しない |
| 2 | 下記 9.2.1 の形 | A1 | `find` の名前条件の値 `.env*`・`*.pem`・`id_rsa*` が秘密パスと判定され、`;` の後ろの `git ls-files \| grep -E …` の `grep`（読み取り動詞）と、A1 の「コマンド全体での同居」で組になる（7節-2） |
| 3 | `… > /tmp/claude-1000/…/scratchpad/proto/.claude/hooks/x.py` | B | 保護パスの判定は前置部分を問わない（3.4）。`.claude` の直後が `hooks` なら、どのディレクトリの下でも保護パス |

#### 9.2.1 2件目の実際の形（LES での作業中に起きた形。プロジェクトのパスは `/work/proj` に置き換えた）
```bash
cd /work/proj && find . -path ./node_modules -prune -o -path ./frontend/node_modules -prune -o -path ./.venv -prune -o -path ./.git -prune -o \( -name '.env*' -o -name '*.xlsx' -o -name '*.db' -o -name '*.sqlite*' -o -name '*.pem' -o -name 'id_rsa*' \) -print 2>/dev/null; echo ---; git ls-files | grep -E '(^|/)\.env|\.xlsx$|\.db$|\.sqlite'
```
- 移植元の語彙では、秘密パスと判定される語は `.env*`・`*.pem`・`id_rsa*` の3つで、すべて find の `-name` の値。grep のパターンは秘密パスと判定されず、9.4 だけで通る
- 【LES】**LES の語彙では `-name` の値 `*.xlsx`・`*.db`・`*.sqlite*` も秘密パスになる**（9.4 で割り引くので問題ない）が、**grep のパターン `(^|/)\.env|\.xlsx$|\.db$|\.sqlite` も秘密パスになる**（`/` で分けた最後の構成要素 `)\.env|\.xlsx$|\.db$|\.sqlite` が `.sqlite` を含む＝3.3 の `*.sqlite*`）。grep のパターンは 9.4 で割り引く語ではないので、**この形は LES では止まる**（9.6 の「grep のパターンの区別は先送り」に掛かる）。テストには、パターンを `(^|/)\.env|\.xlsx$|\.db$|[.]sqlite` に書き換えた形を「通」として置く（9.4 の表）。元の形は止まりすぎとして 8節に記録し、テストで固定しない（11節 決定9）
- 実行されるコマンドは `cd`・`find`・`echo`・`git ls-files`・`grep` で、すべて 9.4 の許可リストにある。置換は無く、`2>/dev/null` は書き込みとして扱わない（3.4）
- 先頭の `cd <プロジェクト>` の扱い: **A（秘密の読み取り）の判定には影響しない**。秘密パスはどのディレクトリにあっても秘密で、cd 先で判定を緩めも強めもしない。cd の引数は 9.4 で割り引く語に**含めない**ので、`cd ~/claude-settings-backup && ls | head`・【LES】`cd data/scenarios && ls | head` のように cd 先そのものが秘密なら従来どおり数える。B では cd を従来どおり追う

### 9.3 カテゴリA: 除外の指定（`--exclude` の値）

**規則（仕様）**: 次のコマンドの、次のオプションの**値**は、A1 の「秘密パスのトークン」として数えない。
- コマンド: `grep`・`egrep`・`fgrep`・`rsync`・`tar`・`diff`（【LES】`sqlite3`・`unzip` は足さない。7節-21）
- オプション: 長い形の `--exclude`・`--exclude-dir`。値の形はコマンドで違う:
  - `grep`・`egrep`・`fgrep`・`diff`: `--exclude=値` と `--exclude 値`（次の語）の両方。空白区切りは 9.3.1 の規則で前の語を見る
  - `rsync`・`tar`: **`--exclude=値` の形だけ**。空白区切りの `--exclude 値` は割り引かない（値を取るオプションが多く版ごとに増えるので、9.3.1 の表を作ると載せ忘れがそのまま穴になるため）。`--exclude=.env` と書けば通る
- **数え続けるもの**: `--include=値`（読む対象を秘密に絞る）、`--exclude-from=FILE`・`-f FILE`（FILE の中身を読む）、被演算子（`grep -r x .env`）、同じコマンドの他の語（`; cat .env`）。値を外すのは**その1語だけ**で、コマンド全体の判定は変えない
- **先送り**: 短い形・別の書き方の除外（`diff -x`・`rsync --filter`／`-f`・`zip -x`・`ag --ignore`）。今と同じく止まる（誤検知の側）。テストで「通る」「止まる」のどちらも固定しない
- **`POSIXLY_CORRECT` があれば割り引かない**: 環境変数 `POSIXLY_CORRECT` があると GNU の getopt はオプションを並べ替えず、最初の被演算子より後ろの `--exclude`・値をすべて被演算子（読む対象）にする（`POSIXLY_CORRECT=1 grep KEY --exclude .env` は `.env` を読む）。そこで、**コマンド文字列に `POSIXLY_CORRECT` という名前が現れたら、コマンド全体で本節（9.3・9.3.1）の割り引きを一切しない**（6コマンドすべて。止める側にだけ倒れる）。**bash の POSIX モードを指す語 `posix`**（単語境界で区切った `posix`。`set -o posix`・`set -ao posix`・`bash --posix`・`SHELLOPTS=posix:…`）も同じに扱う（POSIX モードは `POSIXLY_CORRECT=y` を設定し、`set -a` と組むと子の grep に渡る。`posixly_correct` は単語境界に当たらないので数えない）
  - 「現れる」の範囲（保守側）: **生のコマンド文字列のどこか**（単純コマンドの位置・代入か引数か・引用の中か・ヒアドキュメント本文か・別の単純コマンドかを問わない）に部分文字列 `POSIXLY_CORRECT` がある、**または**字句解析後の語（引用・`\` を外した後）のどれかに `POSIXLY_CORRECT` が含まれる。後者は `env "POSIXLY_"CORRECT=1 grep …`・`env POSIXLY_CORREC\T=1 grep …` のように、生の文字列では名前が切れているが env には `POSIXLY_CORRECT=1` が渡る形を拾うため
  - 位置を解析しない理由: 代入の前置き（`X=1 grep`）・`env`／`sudo`／`bash -c` の包み込み・`export`／`declare -x`／`set -a` の後の別コマンドなど、効く形が多く、どれが効くかを読み分けると漏れが穴になる。一方、名前そのものが書かれる場面は稀で、止まりすぎの害は小さい（`grep -r --exclude=.env KEY . \| grep POSIXLY_CORRECT` のように名前を検索するだけの形も止まるが、受け入れる）
  - 名前の大文字小文字は区別する（環境変数は区別されるので、`posixly_correct` は当たらない）。名前の一部（`POSIXLY`）だけでは当たらない
  - 割り引かないのは本節の割り引きだけ。9.4（一覧だけ）や B・C の判定は変えない（`POSIXLY_CORRECT=1 grep -r KEY src/` のように秘密名が無ければ従来どおり通る）

**通すことで増える経路が無いことの確認**: 除外の値を外した後に残る判定は「除外指定が無いのと同じコマンド」（`grep -r KEY .`・`rsync -a src/ dst/`）と同じになる。それらは既に通っている（8節の既知の穴）ので、除外を足した形を通しても読める範囲は広がらない（狭まる）。【LES】顧客データの値（`--exclude=*.db`・`--exclude-dir=data`）も同じ

| テストメソッド名（`TestSecretRead`） | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_exclude_option_values_then_allowed` | `grep -r --exclude=.env* PATTERN .`・`grep -r --exclude='.env*' PATTERN .`・`grep -rn --exclude=.env --exclude=.env.local KEY src/`・`grep -r --exclude .env PATTERN .`・`grep -r --exclude-dir=.env PATTERN .`・`egrep -r --exclude=.env x .`・`grep -rn dotenv --exclude=.env .`・`grep -r --exclude=settings.local.json --exclude='*.pem' x .` | 通 | 正常系 |
| `test_exclude_values_other_tools_then_allowed` | `rsync -a --exclude=.env --exclude='.env.*' src/ /tmp/bk/`・`tar --exclude=.env -czf /tmp/x.tgz src`・`diff -r --exclude=.env a b`・`diff -r --exclude .env a b` | 通 | 正常系 |
| `test_include_or_pattern_file_or_operand_then_blocked` | `grep --include=.env -r x .`・`grep -r --include='.env*' KEY .`・`grep -r x .env`・`grep -r --exclude=.env x . .env.local`・`grep -r --exclude-from=.env x .`・`grep -f .env x.txt`・`grep -r --exclude=.env KEY . ; cat .env`・`grep --exclude=.env -r x $(echo .env)`・`grep -r -- --exclude .env`（`--` の後ろは被演算子で、`--exclude` はパターン・`.env` は読む対象）・`rg -g .env x`・`rg --glob=.env x`・`rg --iglob .env x` | 止 | すり抜け |
| `test_include_values_other_tools_then_blocked` | `rsync -a --include=.env --exclude='*' src/ /tmp/x/`・`rsync -a --exclude-from=.env src/ dst/`・`tar --exclude=.env -czf x.tgz . .env`・`diff --exclude=.env .env x`・`rsync -a --exclude .env src/ /tmp/bk/`・`tar --exclude .env -czf /tmp/x.tgz src`（rsync・tar の空白区切りは割り引かない） | 止 | すり抜け |
| `test_negated_glob_then_allowed`（回帰防止） | `rg --glob '!.env' x`・`rg -g '!.env*' x` | 通 | 境界値 |
| `test_exclude_values_with_posixly_correct_then_blocked` | `POSIXLY_CORRECT=1 grep KEY --exclude .env`・`POSIXLY_CORRECT=1 grep -r KEY . --exclude=.env`・`POSIXLY_CORRECT= grep KEY --exclude .env`（空の値でも GNU は「ある」とみなす）・`env POSIXLY_CORRECT=1 grep -r KEY . --exclude=.env`・`sudo POSIXLY_CORRECT=1 grep -r KEY . --exclude=.env`・`export POSIXLY_CORRECT=1; grep -r KEY . --exclude=.env`・`export POSIXLY_CORRECT; grep KEY --exclude .env`・`bash -c 'POSIXLY_CORRECT=1 grep KEY --exclude .env'`・`env "POSIXLY_"CORRECT=1 grep KEY --exclude .env`（字句解析後の語で当たる）・`env POSIXLY_CORREC\T=1 grep KEY --exclude .env`（同）・`POSIXLY_CORRECT=1 grep -r --exclude=.env KEY .`（位置を解析しない＝保守側）・`POSIXLY_CORRECT=1 diff -r a b --exclude=.env`・`POSIXLY_CORRECT=1 tar -czf /tmp/x.tgz src --exclude=.env`・`grep -r --exclude=.env KEY . \| grep POSIXLY_CORRECT`（名前を検索するだけの形。誤検知の側として受け入れる）・`set -a; set -o posix; grep KEY --exclude .env .`・`set -ao posix; grep KEY --exclude .env .`・`bash --posix -a -c 'grep KEY --exclude .env .'`・`SHELLOPTS=posix:allexport bash -c 'grep KEY --exclude .env .'` | 止 | すり抜け |
| `test_exclude_values_without_posixly_correct_then_allowed`（回帰防止） | `grep -r KEY . --exclude=.env`（POSIXLY_CORRECT が無ければ被演算子の後ろでも除外の値）・`grep -r --exclude=.env KEY .`・`POSIXLY_CORRECT=1 grep -r KEY src/`（秘密名が無い）・`grep -rn POSIXLY --exclude=.env .`（名前の一部だけ）・`posixly_correct=1 grep -r KEY . --exclude=.env`（大文字小文字は区別する） | 通 | 境界値 |

#### 9.3.1 `--exclude` が前のオプションの値になっている形（J2）
`grep -v -e --exclude .env` は `-e` が `--exclude` をパターンとして取り、`.env` は**読む対象**になる。9.3 の規則が `--exclude` を語の形だけで見ると、`.env` を除外の値として割り引いて通してしまう（`grep -ve --exclude .env`・`grep -f --exclude .env`・`diff -L --exclude .env /dev/null`・`diff --label`／`-x`／`-I` も同じ）。

**規則（仕様）**:
- `--exclude`／`--exclude-dir` の語が**前のオプションの値**になっているときは、オプションではない。その語も次の語も割り引かない
- 「前のオプションの値になっている」＝直前の語が、そのコマンドの**値を取るオプション**で、値をくっつけていない形:
  - 長いオプション: 表にある名前と完全一致（`=` を含まない）
  - 短いオプションの束: 左から読み、値を取る文字が最初に現れた位置で決める（getopt と同じ）。その文字が束の**最後**なら次の語が値（`-e`・`-ve`・`-cf`）。後ろに文字が続けばそれが値で、次の語は値ではない（`-A3`・`-ev`）。実装が「束の最後の文字だけを見る」簡略化をとってもよい（`-ef` のような形で止める側にずれるだけ）
  - 直前の語自体がさらに前のオプションの値になっている場合は、それをオプションとして読まない（`grep -e -e --exclude .env` の2つ目の `-e` はパターン）。前から順に読めば自然にそうなる
- `--` より後ろは従来どおり読まない（9.3）
- `=` 形（`--exclude=.env`）も、その語自体が前のオプションの値になっているときは割り引かない（`grep -e --exclude=.env KEY .` は止める）。前のオプションの値になっていなければ、前の語に関係なく除外の値（`grep -e x --exclude=.env KEY .` は通す）

本節の規則が働くのは `grep`・`egrep`・`fgrep`・`diff` だけ（`rsync`・`tar` は空白区切りの `--exclude` をそもそも割り引かないので、前の語を見る必要がない）。

**値を取るオプションの表（コマンドごと。最低限の一覧。engineer が手元の man から写して足してよい）**:
| コマンド | 短い（値を取る文字） | 長い |
| --- | --- | --- |
| `grep`・`egrep`・`fgrep` | `e f m A B C d D` | `--regexp --file --max-count --after-context --before-context --context --directories --devices --label --binary-files --include --exclude --exclude-from --exclude-dir --group-separator` |
| `diff` | `x X I L F S D C U W` | `--exclude --exclude-from --ignore-matching-lines --label --show-function-line --starting-file --ifdef --width --tabsize --from-file --to-file --horizon-lines --palette --line-format --old-line-format --new-line-format --unchanged-line-format --old-group-format --new-group-format --changed-group-format --unchanged-group-format` |

値を省略できるオプション（`--color[=WHEN]`・`--context[=NUM]`・`--unified[=NUM]`・`tar --backup[=…]`）は `=` でしか値を取らないので表に入れない。

**表の漏れ**: 表に無い値つきオプションが前にあると、その形は J2 と同じく通る。grep・diff は値つきオプションが十数個で表が閉じるので、この2つに限って表で判定する。漏れが見つかったら表に足す。

| テストメソッド名（`TestSecretRead`） | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_exclude_word_as_previous_option_value_then_blocked`（J2） | `grep -v -e --exclude .env`・`grep -ve --exclude .env`・`grep -f --exclude .env`・`grep --regexp --exclude .env`・`grep -e --exclude=.env KEY .`・`diff -L --exclude .env /dev/null`・`diff --label --exclude .env /dev/null`・`diff -x --exclude .env /dev/null`・`diff -I --exclude .env /dev/null`・`tar -cf --exclude .env`・`rsync -e --exclude .env /tmp/x/`（rsync・tar は空白区切りを割り引かないので、表が無くても止まる） | 止 | すり抜け |
| `test_exclude_after_flag_or_attached_value_then_allowed`（J2） | `grep -e x --exclude=.env KEY .`・`grep -e x --exclude .env -r KEY .`・`grep -rv --exclude .env KEY .`・`grep -A3 --exclude .env -r KEY .`・`diff -r --exclude .env a b` | 通 | 境界値 |

### 9.4 カテゴリA: 名前の一覧（find の名前条件・名前だけを扱うコマンド）

**規則（仕様）**: 次の語は、コマンド全体が「**一覧だけ**」のときに限り、A1 の秘密パスのトークンとして数えない。
- `find` の**名前条件の値**（`-name`・`-iname`・`-path`・`-ipath`・`-wholename`・`-iwholename`・`-regex`・`-iregex` の次の語）
- **名前だけを扱うコマンドの被演算子**: `ls`・`stat`・`test`・`[`・`[[`、および `git` のサブコマンドが `check-ignore`・`ls-files`・`status` のときの被演算子（`git show HEAD:.env`・`git diff --no-index .env x` などは中身を出すので含めない）

「一覧だけ」＝ 見つけた・並べたパスが、中身を読むコマンドの対象になる経路が無いこと。次を**すべて**満たす:
1. どの `find` にも実行系のアクション（`-exec`・`-execdir`・`-ok`・`-okdir`）が無い
2. コマンド全体の実行されるコマンド（包み込み・`bash -c`・`eval` の中も含む）が、**許可リスト**のものだけ:
   - 名前を出すもの: `find`・`ls`・`stat`・`test`・`[`・`[[`・`git`（サブコマンドが `check-ignore`・`ls-files`・`status` のときだけ）
   - 名前を加工するだけのフィルタ: `sort`・`uniq`・`head`・`tail`・`grep`・`egrep`・`fgrep`・`wc`・`cut`・`tr`・`nl`・`column`・`cat`
   - 副作用の無いもの: `echo`・`printf`・`cd`・`pwd`・`true`・`false`・`:`
   - **それ以外（`xargs`・`read`・`sh`/`bash`・インタプリタ・`source`・`sed`・`awk`・`tar`・`rsync`・`zip`・`vim`・【LES】`sqlite3`・`unzip`、上記以外の git サブコマンドなど）が1つでもあれば割り引かない**
3. コマンド置換・プロセス置換（`$( )`・`` ` ` ``・`<( )`・`>( )`）がどこにも無い
4. `--files0-from`・`--files-from`（名前の一覧から中身を読む）を含む語が無い
5. **関数定義が無い**: `name ( )` の形（`(` の後に空白だけをはさんで `)` が続く）も、`function` という語も無い。**`function` は単純コマンドの先頭に限らず、どの位置にあっても関数定義とみなす**（`! function ls { cat "$@"; }; ls .env`・`if true; then function ls { cat "$@"; }; fi; ls .env`・`{ function ls { cat "$@"; }; }; ls .env`・`time function ls { cat "$@"; }; ls .env`）。許可リストは「名前で中身が決まる」ことが前提で、`ls() { cat "$@"; }` のような定義はその前提を崩すため。`find` の `\( … \)` は中に語があるので当たらない。止める側にだけ倒れる

割り引くのは上の語だけ。同じコマンドの他の語（`; cat .env` の `.env`・`F=.env` の代入・フィルタの被演算子・`cd` の引数・【LES】find の探し始める場所）は従来どおり数える。

**許可リスト方式にする理由**: 「読む経路」を禁止リストで並べると漏れが新しい穴になる（`sort --files0-from=-`・`tar -T -`・`rsync --files-from=-`・`sed 's/^/cat /' | sh`・`awk` の `getline`・`while read`）。許可リストなら、知らないコマンドが来たときは今と同じく止まる（誤検知の側に倒れる）。`sed`・`awk` はファイルを読む・実行する機能（GNU sed の `e`／`R`、awk の `getline`）があるので入れない。【LES】`sqlite3`・`unzip` も中身を出すので入れない

**通すことで増える経路が無いことの確認**: 許可リストのフィルタは標準入力の**文字列**（＝パス名）しか扱わず、名前からファイルを開く機能が無い（`sort`・`wc` の `--files0-from` は条件4で除く）。`find`・`ls`・`stat`・`test`・`git check-ignore`／`ls-files` は中身を出力しない（`find -printf` も中身は出せない）。`git status` は `-v`／`-vv` で**追跡しているファイルの差分**を出すが、git は読み取り動詞ではないので `git status -v` は 9.4 が無くても通っており、9.4 で経路は増えない（追跡されていない `.env`・【LES】`data/` の中身は出ない）。したがって通るのは「秘密のパス名・大きさ・時刻・存在」が会話に出るところまでで、中身は出ない（これらは単体で既に通っており、出る情報は変わらない）。【LES】顧客データでは**ファイル名そのもの**が顧客の情報になりうる点だけが違う（8節。11節 決定6で運用で防ぐ＝5節）

| テストメソッド名（`TestSecretRead`） | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_find_name_conditions_listing_only_then_allowed` | 【LES】**9.2.1 の形のパターンを `[.]sqlite` に書き換えたもの（1件）**: `cd /work/proj && find . -path ./node_modules -prune -o -path ./frontend/node_modules -prune -o -path ./.venv -prune -o -path ./.git -prune -o \( -name '.env*' -o -name '*.xlsx' -o -name '*.db' -o -name '*.sqlite*' -o -name '*.pem' -o -name 'id_rsa*' \) -print 2>/dev/null; echo ---; git ls-files \| grep -E '(^\|/)\.env\|\.xlsx$\|\.db$\|[.]sqlite'`・`find . -path ./node_modules -prune -o \( -name '.env*' -o -name '*.xlsx' \) -print`・`find . -name '.env*' -print \| sort`・`find . -name '.env*' 2>/dev/null \| head -20`・`find . -iname '.ENV*' \| grep -v example`・`find . -path '*/.env' -print \| wc -l`・`find . -wholename './config/.env.local' \| sort`・`find . -regex '.*/\.env.*' \| sort`・`find . -name '.env*' -o -name '*.pem' \| sort \| uniq`・`find . -name settings.local.json \| head`・`find . -name '.env*' -printf '%p %s\n' \| sort`・`cd sub && find . -name '.env*' \| sort` | 通 | 正常系 |
| `test_name_only_commands_listing_only_then_allowed` | `ls -la .env* \| head`・`test -f .env && grep -c KEY README.md`・`[ -e .env ] && echo ok \| cat`・`[[ -f .env.local ]] && echo yes`・`stat -c '%n %s' .env \| cat`・`git check-ignore -v .env .env.local \| cat`・`git ls-files .env.example .env \| sort`・`git status --short .env \| head`・`ls .env && cat README.md` | 通 | 正常系 |
| `test_find_name_conditions_feeding_reader_then_blocked` | `find . -name '.env*' -exec cat {} \;`・`find . -name '.env*' -execdir cat {} \;`・`find . -name '.env*' -ok cat {} \;`・`find . -name '.env*' -okdir cat {} \;`・`find . -name '.env*' -exec grep KEY {} +`・`find . -name '.env*' \| xargs cat`・`find . -name '.env*' -print0 \| xargs -0 grep KEY`・`cat $(find . -name '.env*')`・`` cat `find . -name .env` ``・`find . -name '.env*' \| while read f; do cat "$f"; done`・`for f in $(find . -name '.env*'); do cat "$f"; done`・`while read f; do cat "$f"; done < <(find . -name '.env*')`・`find . -name '.env*' -print0 \| sort --files0-from=-`・`find . -name '.env*' -print0 \| tar --null -T - -czf /tmp/x.tgz`・`find . -name '.env*' \| rsync -a --files-from=- . /tmp/x/`・`find . -name '.env*' \| sed 's/^/cat /' \| sh`・`find . -name .env \| awk '{while((getline l < $0)>0) print l}'`・`vim $(find . -name .env)`・`bash -c "find . -name .env \| xargs cat"`・`find . -name .env; cat .env`・【LES】`cd /work/other && find . -name '.env*' \| xargs cat`（cd が前にあっても同じ） | 止 | すり抜け |
| `test_name_only_commands_feeding_reader_then_blocked` | `ls .env \| xargs cat`・`cat $(ls .env*)`・`ls .env* \| while read f; do cat "$f"; done`・`test -f .env && source .env`・`git ls-files -z .env \| xargs -0 cat`・`stat .env && cat .env`・`ls() { cat "$@"; }; ls .env`・`function ls() { cat "$@"; }; ls .env`・`function ls { cat "$@"; }; ls .env` | 止 | すり抜け |

注:
- 表の中の `\|` は Markdown の表のための書き方で、コマンドでは `|`
- `find . -name '.env*' -delete`・`-fprint FILE`・`-fls FILE` は A では止まらない（読み取り動詞が無い。中身は読まない）。A のテストでは「通る」「止まる」のどちらも固定しない。`-fprint` 系の**書き込み先**は 9.5.1 で B に加える
- **関数定義の3件（条件5）**: `function ls { cat "$@"; }; ls .env`（括弧なしの `function` 形）は、9.4.1（本体を判定に掛ける）と条件5の両方が揃って初めて止まる
- `git show HEAD:.env | cat` は、`HEAD:.env` が秘密パスと判定されず通る（8節の git 経由の既知の穴）。git を許可リストに入れるのは `check-ignore`・`ls-files`・`status` だけなので、本節でこの穴が広がることはない。テストには入れない

### 9.4.1 関数定義・coproc・複合コマンドの本体

**目的**: 本体の中のコマンドが、A・B・C の判定から**見えなくならない**こと。原因は「名前を取る予約語（`function NAME`・`coproc NAME`）の後ろの名前を、コマンド名と取り違える」こと。

**規則（仕様）**:
- `function NAME { BODY; }`（入れ子 `function f { function g { BODY; }; }` を含む）の BODY を、単独で書いたときと同じ規則で A・B・C に掛ける。**呼ばれない関数の本体も判定する**（定義だけで止まる。`if false; then cat .env; fi` を止めているのと同じく止める側に倒す）
- `coproc BODY`（`coproc cat .env`）と `coproc NAME { BODY; }` の BODY も同じ。`coproc NAME` の後ろが `{` のほか `if`・`while`・`until`・`for`・`case`・`select` のときも NAME ごと剥がし、その後ろを本体として判定する（`coproc N if cat .env; then :; fi`・`coproc N while cat .env; do :; done` など）。それ以外の語が2つ目に来る形（`coproc cat .env`）は従来どおり1つ目がコマンド名
- 本体に危険な語が無ければ従来どおり通す（`function f { echo hi; }; f`・`coproc sleep 1`）
- 複合コマンドの形（下の「複合コマンドの並び」）は止まり続ける（回帰防止）

**形の並び（テストで共有する。`BODY` を差し替えて使う）**:
- **関数定義・coproc の並び（移植元の7形）**: `function f { BODY; }`・`function f { function g { BODY; }; }`・`coproc BODY`・`coproc NAME { BODY; }`・`coproc NAME if BODY; then :; fi`・`coproc NAME while BODY; do :; done`・`coproc NAME until BODY; do :; done`（後ろ3つは上の規則の「`coproc NAME` の後ろが `{` 以外の複合コマンド」の形。2026-11-01 に移植元のテストの並びに合わせて形の数を直した）
- **複合コマンドの並び（27形）**: `{ BODY; }`・`{ { BODY; }; }`・`! { BODY; }`・`if true; then { BODY; }; fi`・`( BODY )`・`f() ( BODY )`・`if true; then BODY; fi`・`if BODY; then :; fi`・`if false; then :; elif true; then BODY; fi`・`if false; then :; else BODY; fi`・`while true; do BODY; done`・`until false; do BODY; done`・`for f in x; do BODY; done`・`for ((i=0;i<1;i++)); do BODY; done`・`select f in x; do BODY; done`・`case x in x) BODY;; esac`・`case x in (x) BODY;; esac`・`! BODY`・`time BODY`・`time -p BODY`・`x=1 BODY`・`[[ -n x ]] && BODY`・`f() { BODY; }`・`f () { BODY; }`・`function f() { BODY; }`・`function f ( ) { BODY; }`・`coproc NAME ( BODY )`
- 本体（BODY）: A `cat .env`／B `rm .claude/hooks/guard.py`／C `git push --force`（【LES】A に `sqlite3 data/clients.db .tables` を足すかは 10.2 の `test_function_and_coproc_bodies_customer_data_then_blocked` で別に持つ。ここは移植元のまま）

| テストクラス.メソッド | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `TestSecretRead.test_function_and_coproc_bodies_then_blocked` | 関数定義・coproc の並び（7形）× BODY=`cat .env` | 止 | すり抜け |
| `TestProtectedWrite.test_function_and_coproc_bodies_then_blocked` | 同（7形）× BODY=`rm .claude/hooks/guard.py` | 止 | すり抜け |
| `TestIrreversibleOps.test_function_and_coproc_bodies_then_blocked` | 同（7形）× BODY=`git push --force` | 止 | すり抜け |
| `TestSecretRead.test_compound_command_bodies_then_blocked` | 複合コマンドの並び（27形）× BODY=`cat .env` | 止 | 回帰防止 |
| `TestProtectedWrite.test_compound_command_bodies_then_blocked` | 同（27形）× BODY=`rm .claude/hooks/guard.py` | 止 | 回帰防止 |
| `TestIrreversibleOps.test_compound_command_bodies_then_blocked` | 同（27形）× BODY=`git push --force` | 止 | 回帰防止 |
| `TestEverydayCommandsAllowed.test_function_and_coproc_harmless_bodies_then_allowed` | `function f { echo hi; }; f`・`function f { function g { ls; }; }; f`・`coproc sleep 1`・`coproc W { sleep 1; }` | 通 | 境界値 |

実装者へのノート:
- 2つの並びはテストモジュールの定数（例 `FUNCTION_AND_COPROC_FORMS`・`COMPOUND_FORMS`）に置き、各メソッドで `form.replace("BODY", body)` して parametrize する。3クラスで同じ並びを使うことで、どの群だけが黙って通るようになったかが分かる
- 9.4 の `test_name_only_commands_feeding_reader_then_blocked` の `function ls { cat "$@"; }; ls .env` は、本節の変更と 9.4 条件5の両方が揃って初めて止まる。本節のテストとは別に置いたままにする
- 8節の「包み込み表に無いコマンド」（`stdbuf`・`setsid`・`watch` など8コマンド）は同じ症状だが原因が違い、範囲外。本節の並びに入れない

### 9.5 カテゴリB: プロジェクトの外の `.claude/`

**これまでの扱い**: 保護パスの判定は構成要素に `.claude` があれば前置部分を問わない。そのため次は**すべて保護パス**だった:
- プロジェクト自身: `.claude/…`・`./.claude/…`・`../proj/.claude/…`・`"$CLAUDE_PROJECT_DIR"/.claude/…`・`/work/proj/.claude/…`・`~/pjt/proj/.claude/…`
- ユーザー設定: `~/.claude/settings.json`・`~/.claude/hooks/…`・`$HOME/.claude/…`・`/home/user/.claude/settings.json`・`~/.claude`（ディレクトリそのもの）。保護されるのは `hooks/**`・`settings*.json`（`.claude` 直下のときだけ）・`.claude` 自身で、`~/.claude/CLAUDE.md`・`~/.claude/skills/…` は保護対象外（本節で変えない）
- 他のプロジェクト（`~/pjt/other/.claude/settings.json`）・一時ディレクトリ（`/tmp/x/.claude/hooks/…`）も同じく保護パス
- guard は HOME を見ない（3.5 C3 と同じ方針）ので、絶対パス `/home/user/.claude/…` がユーザー設定かどうかを「HOME と比べて」決めることはできない

**規則（仕様）**: 保護パスの判定から、次を**すべて**満たすパスだけを外す。それ以外（プロジェクト自身・ユーザー設定・他のプロジェクト）は保護パスのまま。
1. 正規化（`.`・`..`・連続する `/` を解決）した後の絶対パスが `/tmp/` または `/var/tmp/` の下にある
2. **行き先が文字列だけで決まる**。次のどれかに当たる語は外さない（保護パスのまま）:
   - `$` を含む（`/tmp/$X/…`・`$TMPDIR/…`・`/tmp/${X:-..}/…`）
   - `{` を含む（ブレース展開。`/tmp/{a,../<P>}/.claude/hooks/guard.py` は展開後の行き先が文字列の正規化と違う）
   - `.` で始まり `*`・`?`・`[` を含む構成要素がある（`/tmp/.?/…`・`/tmp/.[.]/…` は `..` に当たりうる）。`.` で始まらない構成要素のグロブは `..` に当たらないので外してよい（`rm /tmp/p/.claude/hooks/*.pyc` は通す）
   - **語の組み立てに置換が入っていた**（J1）: コマンド置換 `$( … )`・バッククォート・算術展開 `$(( … ))`・プロセス置換 `<( … )`／`>( … )` のどれかが、その語の一部だった。字句解析は置換の中身を語から取り除く（`/tmp/$(echo ..)/<P>/…` は `/tmp//<P>/…` になり、正規化すると `/tmp` の下に見える）ので、取り除いた後の文字列では決めない。`${ … }` は `$` が語に残るので上の `$` の規則で外さない
   - **`$'…'`（ANSI-C 引用）が語の一部だった**: 字句解析はエスケープを「次の1文字」に簡略化して読む（`$'\x2e\x2e'` を `x2ex2e` と読む）ので、文字列が実際の行き先と違う。置換と同じく外さない
   - 判定は**書き込み先の語ごと**に行う。コマンド文字列のどこかに置換があることでは決めない（ヒアドキュメント本文の `$(date)`・`echo "$(date)" > /tmp/p/.claude/hooks/log.txt` の echo 側の置換は、書き込み先の語に入っていないので通す）
   - **粒度**: 出力リダイレクトの対象は**語ごと**に見る。`cp`・`rm`・`dd of=`・`git -C` などの書き込み先・`find` の探し始める場所・`cd` の行き先は**単純コマンドごと**に見る（その単純コマンドの語のどれかに置換・`$'…'` が入っていれば、書き込み先が `/tmp` の下でも外さない）。代わりに、書き込み先以外の引数に置換がある形（`cp "$(ls a.py)" /tmp/p/.claude/hooks/`）は止まる（誤検知の側として許容）。**この形はテストで「通る」「止まる」のどちらにも固定しない**
3. `project_dir` が与えられているとき、そのパスが `project_dir` の下に**ない**（プロジェクトが `/tmp` の下にある場合＝テストの `tmp_path` を守るため）

この除外は、**コマンド文字列に書いた語がそのまま行き先になる書き込み先**に効く: 出力リダイレクト・`cp`・`mv`・`rm`・`sed -i` など・`cd` の追跡（`cd /tmp/p/.claude/hooks && echo x > a.py`）・`git -C`・`find <場所> -delete`／`-exec rm {}`・9.5.1 の `find -fprint` 系。

**xargs には当てない（9.10 決定1）**: xargs が走らせる書き込みコマンドの書き込み先は、`/tmp/…`・`/var/tmp/…` に見えても、本節の除外を当てずに保護パスとして判定する。対象は次のすべて:
- **標準入力から渡る語の近似**（コマンド全体の語。`echo … | xargs rm`・`xargs -a FILE rm`）: 語は xargs に届くまでにパイプの途中（`sed`・`tr`・`cut`・`printf` の書式・`echo -e` のエスケープなど）で加工されうるので、コマンド文字列に見える `/tmp/…` が実際の行き先だとは文字列から決められない
- **xargs の後ろに直接書いた書き込み先**（`xargs rm /tmp/…`・`xargs -I X rm /tmp/X/…`）: `-I`／`-i`／`--replace` の置き換え文字列は任意の文字（`X` など）を選べ、標準入力の語（`..` など）がはめ込まれるので、同じく文字列から決められない。`-I` の有無で分けず、xargs の後ろの書き込み先はすべて当てない
- **xargs が走らせる `sh -c`／`bash -c` の中身**: 中身のすべての書き込み先（出力リダイレクト・cd の追跡を含む）に除外を当てない。除外を外すだけで構造の判定（`.claude/hooks/**`・`settings*.json`・`.claude` 自身）は変えないので、`.claude` を含まない `/tmp` への書き込み（`xargs -I X sh -c 'rm /tmp/X.log'`）は従来どおり通る
- **xargs が走らせる find の `-exec` の中・`-delete`・`-fls`**（`echo .. | xargs -I X find . -maxdepth 0 -exec rm /tmp/X/work/proj/.claude/settings.json \;` など）
- `find -exec rm {} +`・`find … -delete`（xargs を経ないもの）は従来どおり除外する（見つかるパスは探し始める場所の下に限られ、行き先が文字列で決まる）。`find /tmp/p/.claude … -print0 \| xargs -0 rm` は xargs 経由なので止まる（誤検知の側。`-delete`・`-exec rm {} +` に書き換えれば通る）

**他のプロジェクトの `.claude/` を書き換えたいとき**は、そのプロジェクトのセッションで Edit ツール（承認あり）を使う（LES に guard を持ち込む作業もこの形）。

**秘密パス（A）は変えない**: `/tmp/p/.env`・`/tmp/p/.claude/settings.local.json`・【LES】`/tmp/p/clients.db`・`/tmp/p/x.xlsx` を読むのは従来どおり止める（どこにあっても中身は秘密になりうる）。

**通すことで増える経路が無いことの確認**:
- 正規化してから判定するので、`/tmp/../work/proj/.claude/…` や `cd /tmp/p/.claude && cd ../../../work/proj/.claude/hooks` でプロジェクトに戻る形は止まる
- `/tmp` の下に**プロジェクトの `.claude` を指すシンボリックリンク**を作って書く形（`ln -s ~/pjt/proj/.claude /tmp/p/.claude; echo x > /tmp/p/.claude/hooks/guard.py`）は通るようになる。ただし同じことは名前に `.claude` を含まないリンク（`ln -s … /tmp/l; echo x > /tmp/l/hooks/guard.py`）で既に通る（8節「`ln -s` で別名を作ってからの書き込み」）。新しい種類の穴ではない
- `/tmp` の下の `.claude` を丸ごとプロジェクトへ持ち込む形（`cp -r /tmp/p/.claude .`）は、書き込み先が `.` なので既に通る（既存の穴）。`cp -rT /tmp/p/.claude .claude`・`rsync -a /tmp/p/.claude/ .claude/` は書き込み先が保護パスなので止まり続ける

| テストメソッド名（`TestProtectedWrite`） | 条件（command）／`project_dir` | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_write_under_tmp_outside_project_then_allowed`（`project_dir="/work/proj"` と `None` の両方） | `echo x > /tmp/claude-1000/x/scratchpad/proto/.claude/hooks/x.py`・`mkdir -p /tmp/p/.claude/hooks && cp a.py /tmp/p/.claude/hooks/`・`cat <<'EOF' > /tmp/p/.claude/settings.json\n{}\nEOF`・`sed -i 's/a/b/' /tmp/p/.claude/settings.json`・`rm -rf /tmp/p/.claude`・`cd /tmp/p/.claude/hooks && echo x > a.py`・`git -C /tmp/p/.claude/hooks rm x.py`・`find /tmp/p/.claude/hooks -name '*.pyc' -delete`・`find /tmp/p/.claude -name '*.pyc' -exec rm {} +`・`find . -fls /tmp/p/.claude/hooks/l.txt`・`echo x > /var/tmp/p/.claude/settings.json` | 通 | 正常系 |
| `test_project_claude_dir_then_still_blocked`（`project_dir="/work/proj"`） | `echo x > .claude/hooks/a.py`・`echo x > ./.claude/settings.json`・`rm /work/proj/.claude/hooks/guard.py`・`rm "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py`・`rm ${CLAUDE_PROJECT_DIR}/.claude/settings.json`・`rm ../proj/.claude/hooks/guard.py`・【LES】`echo x > ~/pjt/proj/.claude/settings.json`・`echo x > $HOME/pjt/proj/.claude/hooks/a.py` | 止 | 回帰防止 |
| `test_user_claude_dir_then_still_blocked` | `echo x > ~/.claude/settings.json`・`echo x > $HOME/.claude/hooks/x.py`・`echo x > ${HOME}/.claude/settings.json`・【LES】`echo x > /home/user/.claude/settings.json`・`rm -rf ~/.claude`・`sed -i 's/a/b/' ~/.claude/settings.json` | 止 | 回帰防止 |
| `test_other_project_claude_dir_then_still_blocked` | 【LES】`echo x > ~/pjt/other/.claude/settings.json`・`rm /work/other/.claude/hooks/guard.py`・`cd /work/other && rm .claude/hooks/guard.py` | 止 | 回帰防止 |
| `test_tmp_path_escaping_back_then_blocked`（`project_dir="/work/proj"`） | `echo x > /tmp/../work/proj/.claude/settings.json`・`rm /tmp/./p/../../work/proj/.claude/hooks/guard.py`・`echo x > //tmp/../work/proj/.claude/settings.json`・`echo x > /tmpx/.claude/settings.json`（`/tmp/` の下ではない）・`echo x > /tmp/$X/.claude/hooks/a.py`・`echo x > $TMPDIR/p/.claude/hooks/a.py`・`cd /tmp/p/.claude && cd ../../../work/proj/.claude/hooks && rm guard.py`・`cd /tmp && cd /work/proj/.claude && rm settings.json`・`cd /tmp/p/.claude/hooks && cd - && rm .claude/hooks/guard.py`（`cd -` で戻った先の相対パスは保護パス）・`rm /tmp/{a,../work/proj}/.claude/hooks/guard.py`・`rm /tmp/.[.]/work/proj/.claude/settings.json`・`rm /tmp/.?/work/proj/.claude/settings.json`・`cd /tmp/.?/work/proj/.claude && rm settings.json` | 止 | すり抜け |
| `test_tmp_path_built_with_substitution_then_blocked`（J1。`project_dir="/work/proj"`） | `rm /tmp/$(echo ..)/work/proj/.claude/settings.json`・`` rm /tmp/`echo ..`/work/proj/.claude/settings.json ``・`cd /tmp/$(echo ..)/work/proj/.claude/hooks && rm guard.py`・`echo x > "/tmp/$(echo ..)/work/proj/.claude/hooks/a.py"`・`cp a.py /tmp/$(echo ..)/work/proj/.claude/hooks/`・`echo x > /tmp/p$((1+1))/.claude/hooks/a.py`（算術展開も同じ扱い）・`echo x > /tmp/p-$(date +%s)/.claude/hooks/a.py`（行き先は `/tmp` の下だが、置換入りの語は外さない。誤検知の側として許容）・`rm /tmp/$'\x2e\x2e'/work/proj/.claude/settings.json`・`echo x > /tmp/$'p'/.claude/hooks/a.py`（`$'…'` 入りの語は外さない。後者は誤検知の側）。加えて strict な xfail（c09）: `rm /tmp/$\<改行>(echo ..)/work/proj/.claude/settings.json`（8節の既知の穴。直したら XPASS で失敗し、外し忘れに気づける） | 止 | すり抜け |
| `test_substitution_outside_target_word_under_tmp_then_allowed`（J1） | `cat > /tmp/p/.claude/hooks/x.sh <<'EOF'\necho $(date)\nEOF`・`cat > /tmp/p/.claude/hooks/x.sh <<EOF\necho $(date)\nEOF`（ヒアドキュメント本文の置換）・`echo "$(date)" > /tmp/p/.claude/hooks/log.txt`・`rm /tmp/p/.claude/hooks/*.pyc` | 通 | 境界値 |
| `test_tmp_path_through_xargs_then_blocked`（9.10 決定1。`project_dir="/work/proj"` と `None` の両方） | パイプ途中の加工: `printf '/tmp/%s/work/proj/.claude/settings.json' .. \| xargs rm`・`echo /tmp/x/work/proj/.claude/settings.json \| sed s/x/../ \| xargs rm`・`echo /tmp/x/work/proj/.claude/settings.json \| tr x . \| xargs rm`・`echo -e '/tmp/\x2e\x2e/work/proj/.claude/settings.json' \| xargs rm`・`echo /tmp/a/work/proj/.claude/settings.json \| cut -d/ -f1,4- \| xargs rm`。置き換え文字列: `echo .. \| xargs -I X rm /tmp/X/work/proj/.claude/settings.json`・`echo .. \| xargs -IX rm /tmp/X/work/proj/.claude/settings.json`・`echo .. \| xargs --replace=X rm /tmp/X/work/proj/.claude/settings.json`・`echo .. \| xargs -I X cp a.py /tmp/X/work/proj/.claude/hooks/`。ファイルから渡す: `echo /tmp/p/.claude/hooks/x.py > /tmp/list; xargs -a /tmp/list rm`。加工の無い形（誤検知として受け入れる）: `echo /tmp/p/.claude/hooks/x.py \| xargs rm`。xargs が走らせるシェルの中身: `echo .. \| xargs -I X sh -c 'rm /tmp/X/work/proj/.claude/settings.json'`・`echo .. \| xargs -I X bash -c 'rm /tmp/X/work/proj/.claude/settings.json'`・`echo .. \| xargs -I X bash -c 'echo y > /tmp/X/work/proj/.claude/settings.json'`。xargs が走らせる find: `echo .. \| xargs -I X find . -maxdepth 0 -exec rm /tmp/X/work/proj/.claude/settings.json \;`・`echo .. \| xargs -I X find . -maxdepth 0 -exec sh -c 'rm /tmp/X/work/proj/.claude/settings.json' \;`・`echo .. \| xargs -I X find /tmp/X/work/proj/.claude/hooks -delete`・`echo .. \| xargs -I X find /tmp/X/work/proj/.claude/hooks -exec rm {} +`・`echo .. \| xargs -I X find . -fls /tmp/X/work/proj/.claude/settings.json` | 止 | すり抜け |
| `test_tmp_path_through_xargs_without_claude_then_allowed`（回帰防止） | `echo x \| xargs rm /tmp/a.txt`・`echo a.py \| xargs -I{} cp {} /tmp/bk/`・`find /tmp/p -name '*.log' \| xargs rm`・`echo a \| xargs -I X sh -c 'rm /tmp/X.log'`・`echo a \| xargs -I X bash -c 'echo y > /tmp/X.txt'` | 通 | 境界値 |
| `test_project_dir_under_tmp_then_still_blocked`（`project_dir="/tmp/proj"`） | `echo x > /tmp/proj/.claude/settings.json`・`rm /tmp/proj/.claude/hooks/guard.py`・`rm .claude/hooks/guard.py`・`cd /tmp/proj/.claude/hooks && rm guard.py`・`rm /tmp/x/../proj/.claude/hooks/guard.py` | 止 | 境界値 |
| `test_secret_under_tmp_then_still_blocked` | `cat /tmp/p/.env`・`cat /tmp/p/.claude/settings.local.json`（【LES】顧客データは 10.3 `test_customer_files_under_tmp_still_blocked`） | 止 | 回帰防止 |

#### 9.5.1 `find -fprint` 系の書き込み先
`find . -fprint .claude/settings.json` が通るすり抜けを塞ぐ。

**規則（仕様）**: `find` の `-fprint FILE`・`-fprint0 FILE`・`-fls FILE`・`-fprintf FILE FORMAT` の **FILE** を、B の書き込み先として扱う（`cp` の書き込み先と同じ判定。cd の追跡・9.5 の一時ディレクトリの除外も同じく効く）。A の扱いは変えない（名前を書くだけで中身は読まない）。

| テストメソッド名（`TestProtectedWrite`） | 条件（command） | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_find_fprint_into_protected_then_blocked` | `find . -fprint .claude/settings.json`・`find . -name x -fls .claude/hooks/a.py`・`find . -fprint0 ~/.claude/settings.json`・`find . -fprintf .claude/hooks/x.py '%p\n'`・`cd .claude/hooks && find . -fprint list.txt` | 止 | すり抜け |
| `test_find_fprint_elsewhere_then_allowed` | `find . -name x -fprint /tmp/list.txt`・`find . -fprintf out/list.txt '%p\n'`・`find .claude/hooks -name '*.py' -fprint /tmp/hooks_list.txt`（保護パスは探し始める場所で、書き込み先ではない） | 通 | 境界値 |

### 9.6 同じ原因から生じる他の誤検知（洗い出しと決定）

| 形 | 結果 | 原因 | 決定 |
| --- | --- | --- | --- |
| `git ls-files \| grep env` | 通 | （`env` は秘密名ではない） | 対応不要 |
| `ls -la .env*`・`stat .env`・`test -f .env`・`[ -e .env ]`・`git check-ignore .env`・`echo .env` | 通（単体） | 読み取り動詞が無い | 対応不要 |
| `ls -la .env* \| head`・`test -f .env && grep -c KEY README.md`・`git check-ignore -v .env .env.local \| cat`・`ls .env && cat README.md` | 通 | 9.4 | 直した（9.4） |
| `cat .gitignore \| grep .env`・`git ls-files \| grep -v .env`・`grep -n '.env' .gitignore`・`grep -rn ".env" docs/`・【LES】`grep -rn clients.db src/`・`git ls-files \| grep '\.db'`・`grep -rn data src/`・`grep -rn "src.db" src/` | 止 | grep の**パターン**（最初の被演算子）を読む対象と区別しない | **先送り**。パターンかファイルかは `-e`・`-eKEY`・`--regexp=`・`-f`・`-A 3` などの読み方に依存し、読み違えると `grep -eKEY .env` が通る新しい穴になる。回り道: `'\.env'`・`'[.]env'`・`'(^\|/)\.env'`・【LES】`'clients[.]db'`・`'\.db$'`・`'[.]sqlite'` のようにパターンを書けば通る。テストで「通る」「止まる」のどちらも固定しない |
| `rsync -a --exclude=.env src/ dst/`・`tar --exclude=.env -czf x.tgz .`・`diff -r --exclude=.env a b` | 通 | 9.3 | 直した（9.3）。`diff -x`・`rsync --filter`・`zip -x`・`ag --ignore` は先送り |
| `rg --glob '!.env' x`・`rg -g '!.env*' x` | 通 | 値が `!` で始まり basename が `.env` にならない | 対応不要（回帰防止のテストだけ） |
| `find . -name .env -print 2>/dev/null \| head -20` | 通 | 9.4 | 直した（9.4） |

**類似の調査で見つかったすり抜け（誤検知ではない）**:
- `find . -fprint .claude/settings.json` 系 → 9.5.1 で塞いだ
- `cp -r /tmp/p/.claude .`・`rsync -a /tmp/p/.claude .` → 先送り（8節）

### 9.7 性能テストの測り方
- 絶対時間の上限ではなく、「**線形であって二乗でない**」ことを比で確かめる（絶対時間は負荷で揺れるが、同じ負荷の下で続けて測った2つの時間の比は揺れにくい）
- **対象**: `TestMainContract.test_long_command_finishes_quickly` の6件（`many_cmds`・`quotes`・`nested_subst`・`many_xargs`・`long_cd`・`many_listing`）と `test_long_eval_chain_still_checked_quickly`（`eval_chain`）。各入力形を**繰り返し回数 n の関数**として書き、基準の n を定数で持つ:

  | id | 入力形（n の関数） | 基準の n |
  | --- | --- | --- |
  | `many_cmds` | `"echo a; " * n + "ls"` | 20000 |
  | `quotes` | `"'" * n` | 300000 |
  | `nested_subst` | `("$(" * 20 + "\n") * n`（1行ごとに上限 `MAX_DEPTH` を越える入れ子を置き、上限を越える入れ子で再帰が膨らまない・例外にならないことを確かめる） | 5000 |
  | `many_xargs` | `"echo .claude/x \| xargs rm; " * n` | 5000 |
  | `long_cd` | `"cd .claude/" + "a/" * n + "; " + "cd ../; " * (n // 2)` | 20000（下げない。長い cd 先のつなぎ直しの退行を比で捕まえられるのはこの大きさ） |
  | `many_listing` | `"find . -name .env -print \| sort; " * n` | 5000 |
  | `eval_chain` | `"eval " * n + "cat .env"` | 30000 |

- **合格条件1（比）**: `t(2n) < 3 × t(n)`。線形なら比は約2、二乗なら約4なので、3 で分かれる
- **合格条件2（緩い絶対上限）**: `t(2n) < 5秒`。比だけでは「線形だが桁違いに遅い」退行を見逃すので残す
- **測り方**: `t(n)` は `time.process_time()` で測った `check_command` 1回の CPU 時間の、**3回の最小値**。測る前に同じ形の小さい入力（例 n=10）で1回呼んで温めておく。n と 2n は同じテストの中で**交互に**測る
- **短すぎる入力の扱い**: `t(n)` が数ミリ秒以下だと比が時計の粒度で決まり不安定になる。engineer は普段の `t(n)` が **50ミリ秒以上**になるよう、短い形の基準の n を引き上げてよい（入力形は変えない。引き上げた n はテストの定数に書く）
- `eval_chain` は「止まる」ことの確認（`assert check_command(...)`）も両方の n で残す
- テスト名は振る舞いを表す名前に改めてよい（例 `test_long_command_scales_linearly`）。id は上の表のものを使う
- 【LES】**所要時間**: 上の7件は1回測るごとに合計で約4〜5秒（移植元の guard で 2026-10-28 に測った CPU 時間。n と 2n の合計）で、3回の最小値と温めを入れると十数秒かかる。タスク2のテスト実行フック（`src/` を編集するたびに `-m "not slow"` で全テストを走らせる・今は約8秒）に毎回この時間が足されるのを避けるため、**性能テストの2メソッド（`test_long_command_finishes_quickly`・`test_long_eval_chain_still_checked_quickly`）に `@pytest.mark.slow` を付ける**（11節 決定4）。受け入れ基準は 5節

### 9.8〜9.10 移植元での運営者の決定（引き継ぐ）
1. 除外の値を外すコマンドは `grep`・`egrep`・`fgrep`・`rsync`・`tar`・`diff` の長い `--exclude`／`--exclude-dir`。rsync・tar は `=` 形だけ（9.3）
2. 名前だけを扱うコマンドも「一覧だけ」に含める: `ls`・`stat`・`test`・`[`・`[[`・`git check-ignore`・`git ls-files`・`git status`（9.4）
3. `/tmp/`・`/var/tmp/` の下（プロジェクトの下を除く）だけを保護パスから外す。他のプロジェクト・ユーザー設定は保護パスのまま。HOME は判定材料にしない（9.5）
4. grep のパターン（最初の被演算子）の区別は先送り（9.6）
5. `find -fprint`・`-fprint0`・`-fprintf`・`-fls` の書き込み先を B に加える（9.5.1）
6. 関数定義があれば「一覧だけ」にしない（9.4 条件5）。括弧なしの関数定義・coproc の本体を判定に掛ける（9.4.1）。複合コマンドの回帰テストを A・B・C に1メソッドずつ足す
7. `=` 形の `--exclude=.env` が前のオプションの値になっている形は止める（9.3.1）
8. `$'…'` を含む語も J1 と同じ扱いで、`/tmp` の下でも外さない。`echo x > /tmp/p-$(date +%s)/.claude/hooks/a.py` のような J1 の誤検知は許容する（9.5）
9. 行継続をはさんだ `$\<改行>(…)` は直さず、既知の穴にする（strict な xfail で残す）
10. xargs の書き込み先（標準入力の語・直接書いた書き込み先・xargs が走らせる `sh -c`／`bash -c`／find の中身）には 9.5 の /tmp 除外を当てない
11. POSIXLY_CORRECT（と bash の POSIX モード）があれば 9.3 の割り引きをしない
12. 性能テストは比で測る（9.7）
13. 包み込み表に無い8コマンドは記録だけ（8節）

---

## 10. 【LES】足した秘密・動詞の受け入れ基準

### 10.1 規則（3.3 の【LES】の行をまとめたもの）

| # | 規則 | 例（止） | 例（通） |
| --- | --- | --- | --- |
| L1 | basename が `.db` で終わる（大文字小文字を区別しない・任意の階層・前置部分を問わない） | `cat data/clients.db`・`cat /tmp/x/clients.db`・`cat ~/.config/x/clients.db`・`cat X.DB` | `cat src/db/sqlite_repository.py` |
| L2 | basename が `.sqlite` を含む | `cat x.sqlite`・`cat x.sqlite3`・`cat x.sqlite-journal` | `cat tests/db/test_sqlite_repository.py` |
| L3 | basename が `.xlsx` で終わる | `cat cf_simulation_20260407.xlsx`・`cat data/output/x.xlsx`・`cat Book.XLSX` | — |
| L4 | glob: basename にリテラルの `.` があり、その後ろの glob が `db`・`xlsx`・`sqlite…` に一致しうる | `cat *.db`・`cat *.xlsx`・`cat *.xls?`・`cat clients.d?`・`cat *.*`・`cat *.sqlite*` | `cat *`・`cat *.py`・`cat *.yaml`・`cat cf_*` |
| L5 | 顧客データの置き場所（プロジェクト直下の `data/`）。①相対パスの最初の構成要素（`.`・`..` を除く）が `data` ②`$CLAUDE_PROJECT_DIR`・`${CLAUDE_PROJECT_DIR}` の直後が `data` ③`project_dir` があるとき、プロジェクトのフォルダ名の直後が `data`。大文字小文字を区別しない。**A3（インラインコード）では `/` を含む語だけ**。**①〜③を書いたままの形と `..` を解いた形（3.3）の両方に掛け、どちらかに当たれば止める**（11節 決定11） | `cat data/scenarios/a.yaml`・`grep -r KEY data`・`cd data && cat scenarios/a.yaml`・`cat /work/proj/data/a.yaml`・`cat src/../data/scenarios/a.yaml`・`cat $CLAUDE_PROJECT_DIR/src/../data/x`・`cat /work/proj/src/../data/x`・`cat ../data/x` | `cat tests/data/x.json`・`cat /tmp/x/data/a.yaml`・`cat src/data_paths.py`・`python3 -c "data = 1; print(data)"`・`cat data_x/../src/a.py`・`cat tests/../src/data_paths.py`・`cat src/../tests/data/x.json` |
| L6 | basename がちょうど `.env.development` なら秘密でない | — | `cat frontend/.env.development` |
| L6' | `.env.development` 以外の `.env.development…` は従来どおり秘密 | `cat frontend/.env.development.local`・`cat frontend/.env.development.bak`・`cat frontend/.env.d*` | — |
| V | 読み取り動詞に `sqlite3`・`unzip` | `sqlite3 data/clients.db .tables`・`unzip -p data/output/x.xlsx xl/sharedStrings.xml` | `sqlite3 --version`・`unzip -o release.zip -d build/` |

- `.claude/settings.local.json` は移植元で既に秘密（3.3「ローカル設定」）。guard の変更は無い
- **L5 と `..`（11節 決定11）**: 3.3 の文言「`.`・`..` を除いた最初の構成要素」は、途中の `..` を捨てたうえで最初の構成要素を見るので、`src/../data/x` の最初は `src` になり通っていた（2026-11-01 の 3e レビューの H1。「プロジェクト直下の `data/`」という意図から外れる）。`..` を解いた形でも①〜③を見る。書いたままの形での判定は残す（解いた形に置き換えない。7節-23）。`..` を解くのは L5 だけで、basename で見る規則（L1〜L4・L6・移植元の `.env` など）と構成要素で見る規則（退避フォルダ・B の `.claude`）は変えない（`..` を解くと構成要素は打ち消されて減るだけで、新しい名前は現れない。どこかの構成要素を見る規則は書いたままの形で既に当たっている。basename が変わるのは末尾が `..` の形だけで、`x/.env/y/..` のようにファイルの下を指す、実在しないパスになる）
- **L5 の③と `project_dir`**: `check_command(cmd)`（`project_dir=None`）では③が働かない。`main` は `CLAUDE_PROJECT_DIR` を渡すので、本番では常に働く（`TestMainContract.test_project_dir_from_environ_for_customer_data`）
- 【architect へ】移植元の判定は「秘密パスの判定は `project_dir` を受け取らない」作りなので、L5 ③・L6 は語彙表（定数）を足すだけでは書けない（L1〜L3・V は定数の追加で済む見込み。L4 は glob の判定の追加、L5 は先頭側で見る判定と A3 での扱いの分岐、L6 は `SAFE_ENV_SUFFIXES` とは別の例外）。`tasks/todo.md` 3c の「語彙表（定数）だけに LES の差分を足す」は、この4点については成り立たない。差分をどこに閉じ込めるかは architect が決める（11節「architect に委ねる点」）

### 10.2 テスト（`TestSecretRead` に足す）

| テストメソッド名 | 条件（command）／`project_dir` | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_customer_db_and_excel_then_blocked` | `cat data/clients.db`・`cat clients.db`・`cat /tmp/x/clients.db`・`cat ~/.config/x/clients.db`・`head -c 300 Thumbs.db`・`cat x.sqlite`・`cat x.sqlite3`・`cat x.sqlite-journal`・`cat cf_simulation_20260407.xlsx`・`cat data/output/x.xlsx`・`cp clients.db /tmp/x`・`cp clients.db data/`・`strings data/clients.db`・`xxd clients.db \| head`・`cat X.DB`・`cat Book.XLSX`・`cat X.SQLITE3` | 止 | 正常系 |
| `test_customer_data_dir_then_blocked`（`project_dir="/work/proj"`） | `cat data/scenarios/a.yaml`・`cat ./data/scenarios/a.yaml`・`cat "$CLAUDE_PROJECT_DIR"/data/scenarios/a.yaml`・`cat ${CLAUDE_PROJECT_DIR}/data/scenarios/a.yaml`・`cat /work/proj/data/scenarios/a.yaml`・`cat ~/pjt/proj/data/scenarios/a.yaml`・`cat ../proj/data/scenarios/a.yaml`・`cat DATA/scenarios/a.yaml`・`grep -r KEY data`・`grep -r KEY data/`・`cp -r data /tmp/bk`・`tar czf /tmp/x.tgz data`・`zip -r /tmp/x.zip data`・`rsync -a data/ /tmp/bk/`・`cd data && cat scenarios/a.yaml`・`cd data/scenarios && ls \| head`・`ls data/ \| while read f; do cat "data/$f"; done` | 止 | 正常系/すり抜け |
| `test_customer_data_dir_without_project_dir_then_blocked`（`project_dir=None`） | `cat data/scenarios/a.yaml`・`cat "$CLAUDE_PROJECT_DIR"/data/scenarios/a.yaml`・`grep -r KEY data`・`cd data && cat scenarios/a.yaml`・【決定11】`cat src/../data/scenarios/a.yaml`・`cat $CLAUDE_PROJECT_DIR/src/../data/x` | 止 | 境界値 |
| `test_customer_data_dir_through_dotdot_then_blocked`（決定11。`project_dir="/work/proj"`） | `cat src/../data/scenarios/a.yaml`・`cat $CLAUDE_PROJECT_DIR/src/../data/x`・`cat /work/proj/src/../data/x`（以上3つが 3e レビューの H1）・`cat ./src/../data/x`・`cat src/./../data/x`・`cat src/sub/../../data/x`・`cat src/../../data/x`（解いた形 `../data/x` の先頭に `..` が余る＝プロジェクトの外に出うる。7節-23）・`cat "${CLAUDE_PROJECT_DIR}/src/../data/x"`・`cat ~/pjt/proj/src/../data/x`・`cat SRC/../DATA/x`・`cat src/../data`・`grep -r KEY src/../data`・`cp -r src/../data /tmp/bk`・`cd src/../data && cat scenarios/a.yaml`・`dd if=src/../data/scenarios/a.yaml`・`cat < src/../data/scenarios/a.yaml`（A2）・`python3 -c "print(open('src/../data/scenarios/a.yaml').read())"`（A3。`/` を含む語） | 止 | すり抜け |
| `test_customer_data_dir_written_form_still_blocked`（決定11。`project_dir="/work/proj"`。書いたままの形での判定を残すことの回帰防止） | `cat data/../src/a.py`（書いたままの最初の構成要素が `data`）・`cat ../data/x`・`cat ../../data/x`・`cat $CLAUDE_PROJECT_DIR/../data/x`・`cat /work/proj/../data/x`・`cat /work/other/../proj/data/x`（`..` でプロジェクトの外に出る形。7節-23） | 止 | 境界値 |
| `test_dotdot_not_resolving_to_customer_data_then_allowed`（決定11。`project_dir="/work/proj"` と `None` の両方） | `cat data_x/../src/a.py`・`cat tests/../src/data_paths.py`・`cat src/../tests/data/x.json`・`cat src/data/../a.py`・`cat tests/data/../x.json`・`cat frontend/../frontend/src/data/x.ts`・`cat /work/proj/src/../tests/data/x.json`・`cat $CLAUDE_PROJECT_DIR/src/../src/data_paths.py`・`cat /work/other/src/../data/x`・`cat /tmp/x/../data/y` | 通 | 境界値 |
| `test_other_data_dirs_and_similar_names_then_allowed`（`project_dir="/work/proj"`） | `cat tests/data/x.json`・`cat frontend/src/data/x.ts`・`cat /tmp/x/data/a.yaml`・`cat /work/other/data/a.yaml`・`cat src/data_paths.py`・`cat docs/design/data_directory.md`・`cat metadata/x.txt`・`cat data.json`・`cat scenario.yaml`・`cat src/db/sqlite_repository.py`・`cat tests/db/test_sqlite_repository.py`・`jq .data package.json`・`grep -rn "data =" src/` | 通 | 境界値 |
| `test_sqlite3_and_unzip_reading_secrets_then_blocked` | `sqlite3 data/clients.db .tables`・`sqlite3 data/clients.db "select * from clients"`・`sqlite3 -readonly ~/.config/x/clients.db .dump`・`echo .tables \| sqlite3 data/clients.db`・`sqlite3 data/clients.db .dump > /tmp/x.sql`・`sqlite3 x.sqlite3 .schema`・`sqlite3 tests/fixtures/deny_probe/dummy.db .tables`（タスク6の実機確認と同じ形）・`sqlite3 :memory: < data/q.sql`（A2）・`unzip -p data/output/x.xlsx xl/sharedStrings.xml`・`unzip -p cf_simulation_20260407.xlsx`・`unzip -o data/output/x.xlsx -d /tmp/x`・`unzip -l cf_simulation_20260407.xlsx`（一覧だけでも止まる＝7節-21）・`unzip -p secrets.zip .env` | 止 | 正常系 |
| `test_sqlite3_and_unzip_without_secret_then_allowed` | `sqlite3 --version`・`sqlite3 :memory: "select 1"`・`unzip -o release.zip -d build/`・`unzip -l dist.zip` | 通 | 境界値 |
| `test_interpreter_inline_code_customer_data_then_blocked`（`project_dir="/work/proj"`） | `python3 -c "import sqlite3; print(sqlite3.connect('data/clients.db').execute('select * from clients').fetchall())"`・`python3 -c "import openpyxl; wb=openpyxl.load_workbook('cf_simulation_20260407.xlsx')"`・`.venv/bin/python -c "import pandas as pd;print(pd.read_excel('data/output/x.xlsx'))"`・`python3 -c "print(open('data/scenarios/a.yaml').read())"`・`node -e "console.log(require('fs').readFileSync('data/clients.db'))"` | 止 | 正常系 |
| `test_interpreter_inline_code_data_identifier_then_allowed` | `python3 -c "data = {'a': 1}; print(data)"`・`python3 -c "import json; data=json.load(open('package.json')); print(data['name'])"` | 通 | 境界値 |
| `test_glob_matching_customer_files_then_blocked` | `cat *.db`・`cat *.xlsx`・`cat *.xls?`・`cat clients.d?`・`cat *.*`・`cat *.sqlite*`・`cat */clients.db`・`cat data/*` | 止 | すり抜け |
| `test_glob_not_matching_customer_files_then_allowed` | `cat *.py`・`cat *.yaml`・`cat tests/*.py`・`head -5 src/*.py` | 通 | 境界値 |
| `test_env_development_then_allowed`（決定3） | `cat frontend/.env.development`・`cat .env.development`・`cd frontend && cat .env.development`・`grep VITE_ frontend/.env.development`・`diff frontend/.env.development /tmp/x`・`cat FRONTEND/.ENV.DEVELOPMENT` | 通 | 正常系 |
| `test_env_development_in_backup_dir_still_blocked`（決定10。reviewer が 3e で足した） | `cat ~/claude-settings-backup/.env.development`・`cat ~/claude-settings-backup/frontend/.env.development` | 止 | 境界値 |
| `test_env_development_variants_still_blocked`（決定3の範囲の外） | `cat frontend/.env.development.local`・`cat .env.development.local`・`cat frontend/.env.development.bak`・`cat frontend/.env.d*`・`cat frontend/.env*`・`cat frontend/.env`・`cat frontend/.env.local`・`cat frontend/.env.production` | 止 | 境界値 |
| `test_function_and_coproc_bodies_customer_data_then_blocked` | 9.4.1 の並び（移植元の7形）× BODY=`sqlite3 data/clients.db .tables` | 止 | すり抜け |
| `test_blocked_reason_mentions_customer_target` | `sqlite3 data/clients.db .tables`（`project_dir="/work/proj"`） | 理由が `guard: ` で始まり、`秘密ファイルの読み取り` と `data/clients.db` を含む（顧客データでも移植元と同じカテゴリ名＝7節-22） | 正常系 |

### 10.3 9節（誤検知の修正）との組み合わせ（`TestSecretRead` に足す）

| テストメソッド名 | 条件（command）／`project_dir` | 期待値 | 分類 |
| --- | --- | --- | --- |
| `test_exclude_customer_values_then_allowed`（9.3） | `grep -r --exclude=*.db KEY .`・`grep -r --exclude='*.xlsx' --exclude-dir=data KEY .`・`grep -rn --exclude-dir=data --exclude=*.xlsx --exclude=*.db --exclude='*.sqlite*' KEY .`・`grep -r --exclude-dir data KEY .`・`rsync -a --exclude=data --exclude='*.db' ./ /tmp/bk/`・`tar --exclude=data --exclude='*.xlsx' -czf /tmp/x.tgz src`・`diff -r --exclude=data a b` | 通 | 正常系 |
| `test_customer_values_not_as_exclusion_then_blocked`（9.3・9.3.1） | `grep -r --include=*.db KEY .`・`grep -r --exclude=*.db KEY data`（除外の値は外れるが、被演算子 `data` は数える）・`grep -r --exclude-from=data/ex.txt KEY .`・`rsync -a --exclude data ./ /tmp/bk/`（rsync の空白区切りは割り引かない）・`tar --exclude data -czf /tmp/x.tgz .`・`grep -e --exclude=*.db KEY .`（9.3.1）・`grep -r -- --exclude *.db`・`POSIXLY_CORRECT=1 grep -r KEY . --exclude=*.db`・`POSIXLY_CORRECT=1 grep -r KEY . --exclude-dir=data` | 止 | すり抜け |
| `test_listing_customer_names_then_allowed`（9.4。`project_dir="/work/proj"`） | `ls data/`・`ls -la data/output \| head`・`ls data/ && cat README.md`・`find . -name '*.xlsx' -print`・`find . -name '*.xlsx' -o -name '*.db' -o -name '*.sqlite*' \| sort`・`find . -iname '*.XLSX' \| wc -l`・`ls *.db \| head`・`stat -c '%n %s' data/clients.db \| cat`・`git check-ignore -v data/clients.db x.xlsx \| cat`・`test -f data/clients.db && echo ok`・`git ls-files \| grep -E '\.db$'`（パターンが `$` で終わり `.db` で終わらない） | 通 | 正常系 |
| `test_listing_customer_names_feeding_reader_then_blocked`（9.4） | `find . -name '*.db' \| xargs sqlite3`・`find . -name '*.xlsx' -exec unzip -p {} \;`・`find . -name '*.db' -exec sqlite3 {} .dump \;`・`ls data/scenarios/*.yaml \| xargs cat`・`cat $(find . -name '*.xlsx')`・`find . -name '*.db'; sqlite3 data/clients.db .tables`・`ls *.db && sqlite3 clients.db .tables`（sqlite3 は許可リストに無い） | 止 | すり抜け |
| `test_customer_files_under_tmp_still_blocked`（9.5。`project_dir="/work/proj"` と `None` の両方） | `cat /tmp/x/clients.db`・`unzip -p /tmp/x/report.xlsx`・`sqlite3 /tmp/p/x.sqlite3 .tables`・`cp /tmp/p/clients.db /tmp/q/` | 止 | 回帰防止 |
| `test_customer_daily_commands_then_allowed`（`TestEverydayCommandsAllowed` に置く。`project_dir="/work/proj"`） | `mkdir -p data/scenarios`・`mkdir -p data && mv clients.db cf_simulation_20260407.xlsx data/`（運営者が直下の顧客データを移す手順。`mv` は読み取り動詞ではない）・`.venv/bin/python -m src.main data/scenarios/a.yaml`・`LES_DB_PATH=data/clients.db .venv/bin/python -m uvicorn src.api.app:app`・`du -sh data`・`wc -c data/clients.db`・`file data/output/x.xlsx`・`.venv/bin/python -m pytest tests/db/test_sqlite_repository.py -q`・`cat scenario.yaml` | 通 | 正常系 |

10.2・10.3 の「通」の行は、移植元の guard に LES の語彙を仮に当てて、2026-10-28 に tester が `check_command(…, "/work/proj")` で確かめた（L4 の `clients.d?`・L5 ③の `../proj/data/…` は仮の当て方が仕様と違ったので、仕様の側を正とする）。

2026-11-01（決定11）に、3e 時点の LES の guard（決定11の前）へ `check_command(…, "/work/proj")` と `check_command(…)` で当てて確かめた: `test_customer_data_dir_through_dotdot_then_blocked` の行はすべて**通ってしまう**（Red になる）。`test_customer_data_dir_written_form_still_blocked` の行は `project_dir="/work/proj"` ですべて止まる（回帰防止）。`test_dotdot_not_resolving_to_customer_data_then_allowed` の行は両方の `project_dir` ですべて通る。

---

## 11. 【LES】運営者の決定（2026-10-29・2026-11-01）

1〜9: tester が出した9点に、運営者がすべて推奨どおりに答えた（2026-10-29）。10: 2026-10-30 追加。11・12: 3e（reviewer）のレビューの後に運営者が決めた（2026-11-01）。本文・テスト一覧は決定に合わせて確定させた。

1. **`data` だけの語（`/` 無し）は、A1・A2 では数え、A3（インラインコード）では数えない**（3.3・7節-19・10.1 L5）。どこでも数えると AI がよく書く一行の Python（変数名 `data`）を止め、guard を避ける回り道を招く。どこでも数えないと `grep -r KEY data` で顧客データがそのまま会話に出る。テスト: 10.2 `test_customer_data_dir_then_blocked`・`test_interpreter_inline_code_data_identifier_then_allowed`
2. **`.env.development` の例外は、basename がちょうど `.env.development` のときだけ。階層は問わない**（3.3・7節-17・10.1 L6）。deny も階層を問わず読める形。`frontend/` に限ると `cd frontend && cat .env.development` が止まり、guard は cd 先でパスをつながないので直せない。テスト: 10.2 `test_env_development_then_allowed`・`test_env_development_variants_still_blocked`
3. **LES のパッケージ名 `src.db` で止まるのは受け入れ、既知の止まりすぎとして記録する**（8節）。差分を2点に保つ。逃げ道（テストに書く・Grep ツール）がある。実際の作業で何度も当たったら、`src.db`・`src.db.…` を秘密の判定から外す例外を足す（移植元の 9節と同じく、起きた誤検知から直す）。テストで「通る」「止まる」のどちらも固定しない
4. **性能テストに `slow` を付け、`pytest.ini` の `slow` の説明を直す**（9.7・5節の受け入れ基準）。性能テストが捕まえるのは guard.py の変更による退行で、`src/` の編集のたびに走らせる意味が無い（テスト実行フックは `-m "not slow"` なので外れる。フックは `.claude/hooks/` の編集では走らない）。コミット前の全体実行で走る
5. **`rm -rf data`・`rm data/clients.db`（顧客データの削除）は今回は直さず記録する**（3.5 C3・8節）。今回の差分（秘密の追加・動詞の追加）の外で、規則の形（`rm data/output/x.xlsx` の片付けも止めるか等）を別に決める必要がある。一括削除の `git clean -fdx` は C2b で既に止まる。**記録先**: `tasks/todo.md`「実装計画: 開発基盤の安全設定」の「バックログ（今回はやらない）」に1項目として書く（LES のバックログはそこにまとめている。書くのは `tasks/todo.md` を更新する人（3a の完了を記録するとき）で、tester は書かない）。書く内容の案: 「guard は `rm -rf data`・`rm data/clients.db` など顧客データの削除を止めない（`.gitignore` 済みで取り戻せない。`git clean -fdx` は止まる）。止めるか・片付け（`rm data/output/x.xlsx`）も止めるかを決める（`docs/design/test_spec_guard_hook.md` 11節 決定5）」
6. **`data/` のファイル名は guard では扱わず、README の「データの置き場所」に「`data/scenarios/` などのファイル名に顧客の名前を使わない」と書く**（8節・9.4）。3c の engineer の作業で、受け入れ基準は 5節。guard は読み取り動詞の無いコマンドを止めない作りで、一覧を止めるのは新しい規則になる
7. **SQLite の付随ファイル（`clients.db-wal`・`-shm`・`-journal`）・拡張子の無い DB は記録だけ**（8節）。`data/` の下なら置き場所の規則で止まる。Electron の保存先の付随ファイルも止めるときは、**deny と guard を同時に足す**（片方だけ足すと 3d の `test_every_read_deny_is_covered` がずれる）
8. **展開先として保護パスに書き込む形（`unzip -d .claude/hooks`・`tar -C .claude/hooks`）は記録だけ**（8節）。今回の差分の外。移植元にも同じ穴があり、移植元の記録は移植元の側で行う。直すなら移植元と同時に
9. **9.2.1 の実際の形が grep のパターン `\.sqlite` で止まるのは受け入れる**（9.2.1・8節）。パターンを `[.]sqlite` と書けば通る。grep のパターンの区別は移植元で「読み違えると新しい穴になる」として先送りした変更で、LES だけで先に入れると移植元との差分が大きくなる。元の形はテストで固定しない
10. **退避フォルダの中の `.env.development`（`~/claude-settings-backup/.env.development`）は止める**（2026-10-30 追加。3.3 の退避フォルダの行と L6 の例外の両方に当たる。L6 は basename の規則だけを外し、退避フォルダの規則は残す。設計 `docs/design/guard_hook.md`）。テスト: 10.2 `test_env_development_in_backup_dir_still_blocked`（3e で reviewer が足した）
11. **途中に `..` を挟んだ `data/` を止める**（2026-11-01。3e レビューの H1）。`cat src/../data/scenarios/a.yaml`・`cat $CLAUDE_PROJECT_DIR/src/../data/x`・`cat /work/proj/src/../data/x` が、3.3 ①の「`.`・`..` を除いた最初の構成要素」の文言どおりに通っていた。文言どおりではあるが「プロジェクト直下の `data/`」という意図から外れる。L5 の①〜③を、書いたままの形と `..` を解いた形の両方に掛け、どちらかに当たれば止める（止める側にだけ倒す）。`..` でプロジェクトの外に出る形（`cat ../data/x`・`cat src/../../data/x`・`cat $CLAUDE_PROJECT_DIR/../data/x`・`cat /work/proj/../data/x`）も止める（7節-23）。規則: 3.2・3.3・10.1 L5。テスト: 10.2 `test_customer_data_dir_through_dotdot_then_blocked`・`test_customer_data_dir_written_form_still_blocked`・`test_dotdot_not_resolving_to_customer_data_then_allowed`、`test_customer_data_dir_without_project_dir_then_blocked` に2行
12. **3e レビューの H2・H3・H4 と、ヒアドキュメントで渡す Python は記録だけ**（2026-11-01。8節の【LES】）。H2（SQL 文字列の中の DB）・H3（ブレース展開）は、移植元にも同じ種類の穴があり（awk のプログラム・`cat .{env,x}`）、LES だけで先に直すと移植元との差分が大きくなる。H3 は移植元で直すときに LES の語彙の分も一緒に直す。H4（`$PWD`・`${…:-…}`）は前置部分の表に足す変更で、移植元の 3.2 の扱いと合わせて決める。ヒアドキュメントは移植元 7節-6 で受け入れた穴で、LES では漏れるものが顧客データに広がることを記録する。テストで「通る」ことを固定しない

### architect に委ねる点
- L4・L5・L6 の判定を guard.py のどこに置くか（10.1 の【architect へ】）。移植元との差分を「定数のブロック＋最小限の判定」に閉じ込め、移植元への追従をしやすくする形（`tasks/todo.md`「guard の持ち込み方」案A の弱点＝二重管理への手当て）
- L5 ③のために、秘密パスの判定へ `project_dir` をどう渡すか（関数の引数を増やすか、呼び出し側で判定するか）。`check_command` の公開面（1節）は変えない
- A3 でだけ `data` だけの語を数えない分岐の置き場所
- 【決定11】`..` を解いた形の作り方と置き場所（L5 の判定の中で2つの形を作って①〜③に掛けるか、正規化を別の関数に分けるか）。`posixpath.normpath` をそのまま使うと `~/../data/x` が `data/x` になり前置部分を越えて戻るので、前置部分を残す手当てが要る（3.3。この形はテストで固定しないので、手当ての有無は設計で決めてよい）。書いたままの形での判定（今の `path_components`）を置き換えないこと（7節-23）
- テストの読み込みを `tests/hooks/conftest.py` にそろえるか（2節）、ヘルパーをどこに置くか（5節）
- 移植元のテストを複製したうえで、本書の【LES】の行をどう当てるか（パラメータの置き換え・移動・足すメソッドの置き場所）
