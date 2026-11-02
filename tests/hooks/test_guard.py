"""
シェル経由の危険操作を止める PreToolUse フック（.claude/hooks/guard.py）のテスト

仕様: docs/design/test_spec_guard_hook.md
設計: docs/design/guard_hook.md

.claude はパッケージとして import できないため、ファイルパスから読み込む。
秘密ファイルについての注意: このテストは本物の .env を一切開かない。
guard はコマンド文字列だけを判定するので、パスは「文字列」として渡すだけで足りる。
subprocess のテストで使う tests/fixtures/deny_probe/.env（中身 DUMMY=1）も、
パス文字列として JSON に入れるだけで、実際に cat は走らせない。
【LES】移植元のコミット d20ea9a のテストを複製し、仕様の【LES】の行を `# 【LES】` の印とクラス末尾の囲みで当てた。
【LES】顧客データ（data/ 配下・*.db・*.xlsx）も本物を開かない。パスは文字列として渡すだけ。
"""

import builtins
import functools  # 【LES】
import io
import json
import os
import pathlib
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.hooks.conftest import hook_script, load_hook  # 【LES】

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
EXPECTED_COMMAND = 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py'
PROBE_ENV = "tests/fixtures/deny_probe/.env"

CATEGORY_SECRET = "秘密ファイルの読み取り"
CATEGORY_PROTECTED = "保護対象の書き換え"
CATEGORY_IRREVERSIBLE = "取り返しのつかない操作"


# 【LES】HOOK_PATH・_load_hook・hook は持ち込まない（読み込みは conftest の load_hook。下の _hook）


# ---------------------------------------------------------------------------
# ヘルパー（このモジュール内に閉じる。conftest を汚さない）
# ---------------------------------------------------------------------------

@functools.cache  # 【LES】
def _hook():  # 【LES】無ければ hook_script が pytest.fail（テストごと）。例外は cache されない
    return load_hook("guard")  # 【LES】


def assert_blocked(command, project_dir=None):
    result = _hook().check_command(command, project_dir)
    assert isinstance(result, str) and result, f"{command!r} -> {result!r}"
    return result


def assert_allowed(command, project_dir=None):
    result = _hook().check_command(command, project_dir)
    assert result is None, f"{command!r} -> {result!r}"


def ids(commands):
    """パラメータの id を短くする（改行・記号でテスト名が読みにくくならないように）"""
    return [f"c{i:02d}" for i in range(len(commands))]


def params(commands):
    return pytest.mark.parametrize("command", commands, ids=ids(commands))


# 本体（BODY）を差し替えて A・B・C の3クラスで共有する形の並び（仕様 9.4.1）。
# 同じ並びを3群に掛けることで、どの群だけが黙って通るようになったかが分かる
# 名前を取る予約語（function NAME・coproc NAME）の後ろの本体。現行は3群とも通ってしまう
FUNCTION_AND_COPROC_FORMS = [
    "function f { BODY; }",
    "function f { function g { BODY; }; }",
    "coproc BODY",
    "coproc NAME { BODY; }",
    # coproc NAME の後ろは { 以外の複合コマンドも取れる（bash の文法）。条件の部分が NAME の引数に埋もれないこと
    "coproc NAME if BODY; then :; fi",
    "coproc NAME while BODY; do :; done",
    "coproc NAME until BODY; do :; done",
]
# 現行で既に止まっている複合コマンドの形。字句解析・予約語の扱いを変えたときに黙って通るようにならないこと
COMPOUND_FORMS = [
    "{ BODY; }", "{ { BODY; }; }", "! { BODY; }", "if true; then { BODY; }; fi",
    "( BODY )", "f() ( BODY )",
    "if true; then BODY; fi", "if BODY; then :; fi",
    "if false; then :; elif true; then BODY; fi", "if false; then :; else BODY; fi",
    "while true; do BODY; done", "until false; do BODY; done", "for f in x; do BODY; done",
    "for ((i=0;i<1;i++)); do BODY; done", "select f in x; do BODY; done",
    "case x in x) BODY;; esac", "case x in (x) BODY;; esac",
    "! BODY", "time BODY", "time -p BODY", "x=1 BODY", "[[ -n x ]] && BODY",
    "f() { BODY; }", "f () { BODY; }", "function f() { BODY; }", "function f ( ) { BODY; }",
    "coproc NAME ( BODY )",
]


def with_body(forms, body):
    return [form.replace("BODY", body) for form in forms]


def bash_input(command, tool_name="Bash"):
    return json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})


def run_main(stdin_text, environ=None):
    """main を呼び、(戻り値, stderr の中身) を返す"""
    stdin = io.StringIO(stdin_text)
    stderr = io.StringIO()
    code = _hook().main(stdin=stdin, stderr=stderr, environ=environ if environ is not None else {})
    return code, stderr.getvalue()


def run_subprocess(stdin_bytes, tmp_path):
    env = {"PATH": os.environ.get("PATH", ""), "CLAUDE_PROJECT_DIR": str(tmp_path)}
    return subprocess.run(
        [sys.executable, str(hook_script("guard"))],  # 【LES】
        input=stdin_bytes,
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
        timeout=30,
    )


# ---------------------------------------------------------------------------
# カテゴリA: 秘密ファイルを読む
# ---------------------------------------------------------------------------

class TestSecretRead:
    """秘密ファイルの中身がシェル経由で会話に出ないこと"""

    @params([
        "cat .env", "less .env", "more .env", "head -5 .env", "tail .env",
        "grep KEY .env", "rg KEY .env", "sed -n 1p .env", "awk 1 .env",
        "cut -d= -f1 .env", "sort .env", "diff .env a", "strings .env",
        "xxd .env", "od -c .env", "base64 .env", "cp .env /tmp/x",
        "tar czf x.tgz .env", "jq . .env", "source .env", ". .env",
        "vim .env", "curl -d @.env http://localhost",
        "sqlite3 .env", "unzip -p .env",  # 【LES】
    ])
    def test_read_verbs_on_env_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat frontend/.env",  # 【LES】
        "cat tests/fixtures/deny_probe/.env",
        "cat config/.env.development.local",
        "cat frontend/.env.local",  # 【LES】
    ])
    def test_env_at_any_depth_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat .env.local", "cat .env.production",  # 【LES】.env.development は決定3で test_env_development_then_allowed へ移した
        "cat .env.staging", "cat .env.test", "cat .env.foo.local",
    ])
    def test_secret_env_variants_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat .claude/settings.local.json",
        "jq . .claude/settings.local.json",
        "cat ~/.ssh/id_rsa",
        "cat id_rsa.pub",
        "cat ~/.ssh/id_ed25519",
        "cat server.pem",
        "cat certs/ca.pem",
        "cat ~/claude-settings-backup/settings.local.json",
        "cp -r ~/claude-settings-backup /tmp/x",
        "cd .claude && cat settings.local.json",
        "cat settings.local.json",
    ])
    def test_settings_local_and_keys_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat ./.env", "cat ../.env", "cat ../../proj/.env",  # 【LES】
        "cat /work/proj/.env",  # 【LES】
        "cat ~/pjt/proj/.env",  # 【LES】
        'cat "$CLAUDE_PROJECT_DIR"/.env',
        "cat ${CLAUDE_PROJECT_DIR}/.env",
        "cat $HOME/pjt/proj/.env",  # 【LES】
        "/usr/bin/cat .env",
    ])
    def test_path_forms_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat '.env'", 'cat ".env"', 'cat .e""nv', "cat \\.env",
        "'cat' .env", '"cat" ".env"',
    ])
    def test_quoting_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "ls; cat .env", "cat .env;ls", "true && cat .env", "false || cat .env",
        "echo hi|cat .env", "cat .env | head", "(cat .env)", "{ cat .env; }",
        "ls\ncat .env", "cat .env &",
    ])
    def test_chained_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "echo $(cat .env)", "echo `cat .env`", "cat $(echo .env)",
        'bash -c "cat .env"', "sh -c 'grep K .env'", 'eval "cat .env"',
        "diff <(cat .env) x", "paste <(grep K .env) y", "echo x > >(cat .env)",
    ])
    def test_substitution_and_nesting_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "F=.env; cat $F",
        "echo .env | xargs cat",
        "find . -name .env -exec cat {} \\;",
        # "ls .env && cat README.md" は仕様 9.4（名前の一覧）で「通」に変わったので
        # test_name_only_commands_listing_only_then_allowed へ移した（仕様 9.7）
    ])
    def test_split_across_commands_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "sudo cat .env", "env cat .env", "command cat .env",
        "timeout 5 cat .env", "nice cat .env", "LANG=C cat .env",
        "exec cat .env",
    ])
    def test_wrappers_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "while read l; do echo $l; done < .env", "cat < .env", "python3 < .env",
    ])
    def test_input_redirect_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "python3 -c \"print(open('.env').read())\"",
        ".venv/bin/python -c \"import pathlib;print(pathlib.Path('.env').read_text())\"",
        "node -e \"console.log(require('fs').readFileSync('.env','utf8'))\"",
        "python3 -I -c \"print(open('.env').read())\"",
        "python3 -c \"print(open('/x/.claude/settings.local.json').read())\"",
    ])
    def test_interpreter_inline_code_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat .env*", "cat .e*", "cat .*", "cat .en?", "cat *.pem", "cat ~/.ssh/id_rsa*",
    ])
    def test_glob_matching_dotenv_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat .env.example", "cp .env.example .env.example.bak", "cat .env.sample",
        "cat .env.template", "cat .envrc", "cat environment.yml", "cat src/env.py",
        "grep -rn dotenv src/", "cat *", "cat *.py", "cat docs/pem.md",
        "cat .claude/settings.json",
    ])
    def test_non_secret_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "ls -la .env", "test -f .env && echo ok", "[ -f .env ] || echo missing",
        'find . -name ".env*"', "git add .env.example", "git status",
        "ssh -i ~/.ssh/id_rsa host true", "docker run --env-file=.env img",
    ])
    def test_secret_mentioned_without_read_then_allowed(self, command):
        assert_allowed(command)

    @params([
        ".venv/bin/python -m src.main scenario.yaml",  # 【LES】
        "bash scripts/x.sh",  # 【LES】
        "python3 scripts/foo.py",
        "source .venv/bin/activate && pytest",
    ])
    def test_scripts_reading_env_internally_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "git commit -m \"$(cat <<'EOF'\n守る: .env を読まない\nEOF\n)\"",
        "cat <<'EOF' > notes.md\n.env は gitignore 済み\nEOF",
    ])
    def test_heredoc_body_is_not_scanned(self, command):
        assert_allowed(command)

    # 大文字小文字を区別しないファイルシステム（WSL の /mnt/c など）では同じファイルが読める
    @params(["cat .ENV", "cat .Env.Local", "cat ~/.ssh/ID_RSA", "cat KEY.PEM", "cat .CLAUDE/SETTINGS.LOCAL.JSON"])
    def test_case_insensitive_names_then_blocked(self, command):
        assert_blocked(command)

    @params(["cat .ENV.EXAMPLE", "cat .Env.Sample", "cat ENVIRONMENT.YML", "cat FRONTEND/.ENV.DEVELOPMENT"])  # 【LES】
    def test_case_insensitive_safe_names_then_allowed(self, command):
        assert_allowed(command)

    def test_blocked_reason_mentions_category_and_target(self):
        reason = assert_blocked("cat .env")
        assert reason.startswith("guard: ")
        assert CATEGORY_SECRET in reason
        assert ".env" in reason

    # --- 仕様 9.3: 除外の指定（--exclude の値）は読む対象ではない ---

    @params([
        "grep -r --exclude=.env* PATTERN .",
        "grep -r --exclude='.env*' PATTERN .",
        "grep -rn --exclude=.env --exclude=.env.local KEY src/",
        "grep -r --exclude .env PATTERN .",
        "grep -r --exclude-dir=.env PATTERN .",
        "egrep -r --exclude=.env x .",
        "grep -rn dotenv --exclude=.env .",
        "grep -r --exclude=settings.local.json --exclude='*.pem' x .",
    ])
    def test_exclude_option_values_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "rsync -a --exclude=.env --exclude='.env.*' src/ /tmp/bk/",
        # "rsync -a --exclude .env src/ /tmp/bk/" は rsync・tar の空白区切りを割り引かなくなったので
        # test_include_values_other_tools_then_blocked へ移した（仕様 9.9 決定2）
        "tar --exclude=.env -czf /tmp/x.tgz src",
        "diff -r --exclude=.env a b",
        "diff -r --exclude .env a b",  # diff は値を取るオプションの表があるので空白区切りも割り引く（9.3.1）
    ])
    def test_exclude_values_other_tools_then_allowed(self, command):
        assert_allowed(command)

    # 外すのは --exclude の値の1語だけ。読む対象を絞る・中身を読む・被演算子・別のコマンドは数え続ける
    @params([
        "grep --include=.env -r x .",
        "grep -r --include='.env*' KEY .",
        "grep -r x .env",
        "grep -r --exclude=.env x . .env.local",
        "grep -r --exclude-from=.env x .",
        "grep -f .env x.txt",
        "grep -r --exclude=.env KEY . ; cat .env",
        "grep --exclude=.env -r x $(echo .env)",
        # `--` の後ろは被演算子。--exclude はパターン、.env は読む対象（設計 12.9-3）
        "grep -r -- --exclude .env",
        # rg の -g/--glob/--iglob は除外ではなく対象の指定（9.3 の対象外）
        "rg -g .env x",
        "rg --glob=.env x",
        "rg --iglob .env x",
    ])
    def test_include_or_pattern_file_or_operand_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "rsync -a --include=.env --exclude='*' src/ /tmp/x/",
        "rsync -a --exclude-from=.env src/ dst/",
        "tar --exclude=.env -czf x.tgz . .env",
        "diff --exclude=.env .env x",
        # rsync・tar は値を取るオプションが多く版ごとに増えるので、空白区切りの値は割り引かない（仕様 9.9 決定2）。
        # 通す側から移した。--exclude=.env と書けば通る
        "rsync -a --exclude .env src/ /tmp/bk/",
        "tar --exclude .env -czf /tmp/x.tgz src",
    ])
    def test_include_values_other_tools_then_blocked(self, command):
        assert_blocked(command)

    # --- 仕様 9.3.1（J2）: --exclude が前のオプションの値になっているときはオプションではない ---

    @params([
        "grep -v -e --exclude .env",
        "grep -ve --exclude .env",
        "grep -f --exclude .env",
        "grep --regexp --exclude .env",
        # = 形でも前のオプションの値なら割り引かない（9.9 決定1。規則を1つで済ませる）
        "grep -e --exclude=.env KEY .",
        "diff -L --exclude .env /dev/null",
        "diff --label --exclude .env /dev/null",
        "diff -x --exclude .env /dev/null",
        "diff -I --exclude .env /dev/null",
        # rsync・tar は空白区切りを割り引かないので、表が無くても止まる
        "tar -cf --exclude .env",
        "rsync -e --exclude .env /tmp/x/",
    ])
    def test_exclude_word_as_previous_option_value_then_blocked(self, command):
        assert_blocked(command)

    # 値を読み飛ばした後・値を取らない束・値をくっつけた束の後ろの --exclude はオプション
    @params([
        "grep -e x --exclude=.env KEY .",
        "grep -e x --exclude .env -r KEY .",
        "grep -rv --exclude .env KEY .",
        "grep -A3 --exclude .env -r KEY .",
        "diff -r --exclude .env a b",
    ])
    def test_exclude_after_flag_or_attached_value_then_allowed(self, command):
        assert_allowed(command)

    # 現行でも通る（値が ! で始まり basename が .env にならない）。回帰防止
    @params(["rg --glob '!.env' x", "rg -g '!.env*' x"])
    def test_negated_glob_then_allowed(self, command):
        assert_allowed(command)

    # POSIXLY_CORRECT があると GNU の getopt はオプションを並べ替えず、被演算子の後ろの --exclude と値は
    # 読む対象になる。効く位置は解析せず、名前が現れたらコマンド全体で除外の値を割り引かない（仕様 9.3・9.10 決定2）
    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        "POSIXLY_CORRECT=1 grep KEY --exclude .env",
        "POSIXLY_CORRECT=1 grep -r KEY . --exclude=.env",
        "POSIXLY_CORRECT= grep KEY --exclude .env",  # 空の値でも GNU は「ある」とみなす
        "env POSIXLY_CORRECT=1 grep -r KEY . --exclude=.env",
        "sudo POSIXLY_CORRECT=1 grep -r KEY . --exclude=.env",
        "export POSIXLY_CORRECT=1; grep -r KEY . --exclude=.env",
        "export POSIXLY_CORRECT; grep KEY --exclude .env",
        "bash -c 'POSIXLY_CORRECT=1 grep KEY --exclude .env'",
        # 生の文字列では名前が切れているが、字句解析後の語で当たる
        'env "POSIXLY_"CORRECT=1 grep KEY --exclude .env',
        "env POSIXLY_CORREC\\T=1 grep KEY --exclude .env",
        # 被演算子より前の --exclude は実際には除外として読まれるが、位置を解析しない（保守側）
        "POSIXLY_CORRECT=1 grep -r --exclude=.env KEY .",
        "POSIXLY_CORRECT=1 diff -r a b --exclude=.env",
        "POSIXLY_CORRECT=1 tar -czf /tmp/x.tgz src --exclude=.env",
        # 名前を検索するだけの形も止まる（誤検知の側として受け入れる）
        "grep -r --exclude=.env KEY . | grep POSIXLY_CORRECT",
        # bash の POSIX モードは POSIXLY_CORRECT=y を設定し、allexport と組むと grep に渡る（名前が文字列に出ない）
        "set -a; set -o posix; grep KEY --exclude .env .",
        "set -ao posix; grep -r KEY . --exclude=.env",
        "bash --posix -a -c 'grep KEY --exclude .env .'",
        "SHELLOPTS=posix:allexport bash -c 'grep KEY --exclude .env .'",
    ])
    def test_exclude_values_with_posixly_correct_then_blocked(self, command, project_dir):
        assert_blocked(command, project_dir=project_dir)

    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        "grep -r KEY . --exclude=.env",  # POSIXLY_CORRECT が無ければ被演算子の後ろでも除外の値
        "grep -r --exclude=.env KEY .",
        "POSIXLY_CORRECT=1 grep -r KEY src/",  # 秘密名が無ければ割り引きの有無に関係なく通る
        "grep -rn POSIXLY --exclude=.env .",  # 名前の一部だけ
        "posixly_correct=1 grep -r KEY . --exclude=.env",  # 大文字小文字は区別する
    ])
    def test_exclude_values_without_posixly_correct_then_allowed(self, command, project_dir):
        assert_allowed(command, project_dir=project_dir)

    # --- 仕様 9.4: 名前の一覧だけなら、名前条件・名前だけを扱うコマンドの語を数えない ---

    @params([
        # 【LES】9.2.1 の実際の形。プロジェクトのパスを /work/proj に、grep のパターンの \.sqlite を [.]sqlite に替えた
        # 【LES】（\.sqlite のままだと LES では秘密名に見えて止まる。止まりすぎとして受け入れた＝仕様 11節 決定9）
        r"cd /work/proj && find . -path ./node_modules -prune"  # 【LES】
        r" -o -path ./frontend/node_modules -prune -o -path ./.venv -prune -o -path ./.git -prune"
        r" -o \( -name '.env*' -o -name '*.xlsx' -o -name '*.db' -o -name '*.sqlite*' -o -name '*.pem'"
        r" -o -name 'id_rsa*' \) -print 2>/dev/null; echo ---;"
        r" git ls-files | grep -E '(^|/)\.env|\.xlsx$|\.db$|[.]sqlite'",  # 【LES】
        r"find . -path ./node_modules -prune -o \( -name '.env*' -o -name '*.xlsx' \) -print",
        "find . -name '.env*' -print | sort",
        "find . -name '.env*' 2>/dev/null | head -20",
        "find . -iname '.ENV*' | grep -v example",
        "find . -path '*/.env' -print | wc -l",
        "find . -wholename './config/.env.local' | sort",
        r"find . -regex '.*/\.env.*' | sort",
        "find . -name '.env*' -o -name '*.pem' | sort | uniq",
        "find . -name settings.local.json | head",
        r"find . -name '.env*' -printf '%p %s\n' | sort",
        "cd sub && find . -name '.env*' | sort",
    ])
    def test_find_name_conditions_listing_only_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "ls -la .env* | head",
        "test -f .env && grep -c KEY README.md",
        "[ -e .env ] && echo ok | cat",
        "[[ -f .env.local ]] && echo yes",
        "stat -c '%n %s' .env | cat",
        "git check-ignore -v .env .env.local | cat",
        "git ls-files .env.example .env | sort",
        "git status --short .env | head",
        # test_split_across_commands_then_blocked から移した（仕様 9.7）
        "ls .env && cat README.md",
    ])
    def test_name_only_commands_listing_only_then_allowed(self, command):
        assert_allowed(command)

    # 見つけた名前が中身を読むコマンドに渡る経路が1つでもあれば「一覧だけ」ではない
    @params([
        "find . -name '.env*' -exec cat {} \\;",
        "find . -name '.env*' -execdir cat {} \\;",
        "find . -name '.env*' -ok cat {} \\;",
        "find . -name '.env*' -okdir cat {} \\;",
        "find . -name '.env*' -exec grep KEY {} +",
        "find . -name '.env*' | xargs cat",
        "find . -name '.env*' -print0 | xargs -0 grep KEY",
        "cat $(find . -name '.env*')",
        "cat `find . -name .env`",
        "find . -name '.env*' | while read f; do cat \"$f\"; done",
        "for f in $(find . -name '.env*'); do cat \"$f\"; done",
        "while read f; do cat \"$f\"; done < <(find . -name '.env*')",
        "find . -name '.env*' -print0 | sort --files0-from=-",
        "find . -name '.env*' -print0 | tar --null -T - -czf /tmp/x.tgz",
        "find . -name '.env*' | rsync -a --files-from=- . /tmp/x/",
        "find . -name '.env*' | sed 's/^/cat /' | sh",
        "find . -name .env | awk '{while((getline l < $0)>0) print l}'",
        "vim $(find . -name .env)",
        'bash -c "find . -name .env | xargs cat"',
        "find . -name .env; cat .env",
        # cd が前にあっても同じ
        "cd /work/other && find . -name '.env*' | xargs cat",  # 【LES】
    ])
    def test_find_name_conditions_feeding_reader_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "ls .env | xargs cat",
        "cat $(ls .env*)",
        "ls .env* | while read f; do cat \"$f\"; done",
        "test -f .env && source .env",
        "git ls-files -z .env | xargs -0 cat",
        "stat .env && cat .env",
        # 許可リストの名前で関数を定義すると「名前で中身が決まる」前提が崩れる（9.4 条件5）
        'ls() { cat "$@"; }; ls .env',
        'function ls() { cat "$@"; }; ls .env',
        # 括弧なしの function 形は、本体が見える（9.4.1）と条件5 が揃って初めて止まる
        'function ls { cat "$@"; }; ls .env',
        # function が単純コマンドの先頭の語でなくても関数定義（予約語・time の後ろ）。条件5 は位置を問わない
        '! function ls { cat "$@"; }; ls .env',
        'if true; then function ls { cat "$@"; }; fi; ls .env',
        '{ function ls { cat "$@"; }; }; ls .env',
        'time function ls { cat "$@"; }; ls .env',
    ])
    def test_name_only_commands_feeding_reader_then_blocked(self, command):
        assert_blocked(command)

    # --- 仕様 9.4.1: 関数定義・coproc・複合コマンドの本体も判定に掛かる ---

    @params(with_body(FUNCTION_AND_COPROC_FORMS, "cat .env"))
    def test_function_and_coproc_bodies_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    @params(with_body(COMPOUND_FORMS, "cat .env"))
    def test_compound_command_bodies_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # --- 【LES】ここから（仕様 10.2・10.3）---

    # 10.2 L1〜L3: 顧客 DB・出力の Excel は、階層・前置部分・大文字小文字を問わず秘密
    @params([
        "cat data/clients.db", "cat clients.db", "cat /tmp/x/clients.db", "cat ~/.config/x/clients.db",
        "head -c 300 Thumbs.db", "cat x.sqlite", "cat x.sqlite3", "cat x.sqlite-journal",
        "cat cf_simulation_20260407.xlsx", "cat data/output/x.xlsx", "cp clients.db /tmp/x",
        "cp clients.db data/", "strings data/clients.db", "xxd clients.db | head",
        "cat X.DB", "cat Book.XLSX", "cat X.SQLITE3",
    ])
    def test_customer_db_and_excel_then_blocked(self, command):
        assert_blocked(command)

    # 10.2 L5: 顧客データの置き場所（プロジェクト直下の data/）。先頭側で判定する
    @params([
        "cat data/scenarios/a.yaml",
        "cat ./data/scenarios/a.yaml",
        'cat "$CLAUDE_PROJECT_DIR"/data/scenarios/a.yaml',
        "cat ${CLAUDE_PROJECT_DIR}/data/scenarios/a.yaml",
        "cat /work/proj/data/scenarios/a.yaml",
        "cat ~/pjt/proj/data/scenarios/a.yaml",
        "cat ../proj/data/scenarios/a.yaml",
        "cat DATA/scenarios/a.yaml",
        "grep -r KEY data",
        "grep -r KEY data/",
        "cp -r data /tmp/bk",
        "tar czf /tmp/x.tgz data",
        "zip -r /tmp/x.zip data",
        "rsync -a data/ /tmp/bk/",
        "cd data && cat scenarios/a.yaml",
        "cd data/scenarios && ls | head",
        'ls data/ | while read f; do cat "data/$f"; done',
    ])
    def test_customer_data_dir_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # 10.2 L5 の①②は project_dir が無くても働く（③だけが project_dir を要る）
    @params([
        "cat data/scenarios/a.yaml",
        'cat "$CLAUDE_PROJECT_DIR"/data/scenarios/a.yaml',
        "grep -r KEY data",
        "cd data && cat scenarios/a.yaml",
        "cat src/../data/scenarios/a.yaml",  # 決定11
        "cat $CLAUDE_PROJECT_DIR/src/../data/x",  # 決定11
    ])
    def test_customer_data_dir_without_project_dir_then_blocked(self, command):
        assert_blocked(command)

    # 10.2 L5（11節 決定11）: 途中に `..` を挟んでも、解いた形がプロジェクト直下の data/ なら止める
    @params([
        "cat src/../data/scenarios/a.yaml",
        "cat $CLAUDE_PROJECT_DIR/src/../data/x",
        "cat /work/proj/src/../data/x",
        "cat ./src/../data/x",
        "cat src/./../data/x",
        "cat src/sub/../../data/x",
        "cat src/../../data/x",  # 解いた形 ../data/x の先頭に .. が余る＝プロジェクトの外に出うる（7節-23）
        'cat "${CLAUDE_PROJECT_DIR}/src/../data/x"',
        "cat ~/pjt/proj/src/../data/x",
        "cat SRC/../DATA/x",
        "cat src/../data",
        "grep -r KEY src/../data",
        "cp -r src/../data /tmp/bk",
        "cd src/../data && cat scenarios/a.yaml",
        "dd if=src/../data/scenarios/a.yaml",
        "cat < src/../data/scenarios/a.yaml",  # A2
        "python3 -c \"print(open('src/../data/scenarios/a.yaml').read())\"",  # A3（/ を含む語）
    ])
    def test_customer_data_dir_through_dotdot_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # 10.2 L5（11節 決定11）: 書いたままの形での判定も残す（解いた形に置き換えない。7節-23）
    @params([
        "cat data/../src/a.py",  # 書いたままの最初の構成要素が data
        "cat ../data/x",
        "cat ../../data/x",
        "cat $CLAUDE_PROJECT_DIR/../data/x",
        "cat /work/proj/../data/x",
        "cat /work/other/../proj/data/x",
    ])
    def test_customer_data_dir_written_form_still_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # 10.2 L5（11節 決定11）: `..` を解いてもプロジェクト直下の data/ にならない形は通す
    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        "cat data_x/../src/a.py",
        "cat tests/../src/data_paths.py",
        "cat src/../tests/data/x.json",
        "cat src/data/../a.py",
        "cat tests/data/../x.json",
        "cat frontend/../frontend/src/data/x.ts",
        "cat /work/proj/src/../tests/data/x.json",
        "cat $CLAUDE_PROJECT_DIR/src/../src/data_paths.py",
        "cat /work/other/src/../data/x",
        "cat /tmp/x/../data/y",
    ])
    def test_dotdot_not_resolving_to_customer_data_then_allowed(self, command, project_dir):
        assert_allowed(command, project_dir=project_dir)

    # 10.2 L5: プロジェクト直下でない data/・data に似た名前・src/db などのソースは秘密ではない
    @params([
        "cat tests/data/x.json",
        "cat frontend/src/data/x.ts",
        "cat /tmp/x/data/a.yaml",
        "cat /work/other/data/a.yaml",
        "cat src/data_paths.py",
        "cat docs/design/data_directory.md",
        "cat metadata/x.txt",
        "cat data.json",
        "cat scenario.yaml",
        "cat src/db/sqlite_repository.py",
        "cat tests/db/test_sqlite_repository.py",
        "jq .data package.json",
        'grep -rn "data =" src/',
    ])
    def test_other_data_dirs_and_similar_names_then_allowed(self, command):
        assert_allowed(command, project_dir="/work/proj")

    # 10.2 V: 読み取り動詞に sqlite3・unzip（オプションは読み分けない。一覧だけの unzip -l も止まる＝7節-21）
    @params([
        "sqlite3 data/clients.db .tables",
        'sqlite3 data/clients.db "select * from clients"',
        "sqlite3 -readonly ~/.config/x/clients.db .dump",
        "echo .tables | sqlite3 data/clients.db",
        "sqlite3 data/clients.db .dump > /tmp/x.sql",
        "sqlite3 x.sqlite3 .schema",
        "sqlite3 tests/fixtures/deny_probe/dummy.db .tables",  # タスク6の実機確認と同じ形
        "sqlite3 :memory: < data/q.sql",  # A2
        "unzip -p data/output/x.xlsx xl/sharedStrings.xml",
        "unzip -p cf_simulation_20260407.xlsx",
        "unzip -o data/output/x.xlsx -d /tmp/x",
        "unzip -l cf_simulation_20260407.xlsx",
        "unzip -p secrets.zip .env",
    ])
    def test_sqlite3_and_unzip_reading_secrets_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "sqlite3 --version",
        'sqlite3 :memory: "select 1"',
        "unzip -o release.zip -d build/",
        "unzip -l dist.zip",
    ])
    def test_sqlite3_and_unzip_without_secret_then_allowed(self, command):
        assert_allowed(command)

    # 10.2 決定1: インラインコード（A3）でも顧客 DB・Excel と、/ を含む data/… は数える
    @params([
        "python3 -c \"import sqlite3; print(sqlite3.connect('data/clients.db')"
        ".execute('select * from clients').fetchall())\"",
        "python3 -c \"import openpyxl; wb=openpyxl.load_workbook('cf_simulation_20260407.xlsx')\"",
        ".venv/bin/python -c \"import pandas as pd;print(pd.read_excel('data/output/x.xlsx'))\"",
        "python3 -c \"print(open('data/scenarios/a.yaml').read())\"",
        "node -e \"console.log(require('fs').readFileSync('data/clients.db'))\"",
    ])
    def test_interpreter_inline_code_customer_data_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # 10.2 決定1: インラインコードの中の data だけの語（Python の変数名）は数えない
    @params([
        "python3 -c \"data = {'a': 1}; print(data)\"",
        "python3 -c \"import json; data=json.load(open('package.json')); print(data['name'])\"",
    ])
    def test_interpreter_inline_code_data_identifier_then_allowed(self, command):
        assert_allowed(command)

    # 10.2 L4: glob は「最後の . より後ろ」が秘密の拡張子に一致しうれば止める
    @params([
        "cat *.db", "cat *.xlsx", "cat *.xls?", "cat clients.d?", "cat *.*", "cat *.sqlite*",
        "cat */clients.db", "cat data/*",
    ])
    def test_glob_matching_customer_files_then_blocked(self, command):
        assert_blocked(command)

    @params(["cat *.py", "cat *.yaml", "cat tests/*.py", "head -5 src/*.py"])
    def test_glob_not_matching_customer_files_then_allowed(self, command):
        assert_allowed(command)

    # 10.2 L6（決定3）: basename がちょうど .env.development なら秘密ではない（階層は問わない）
    @params([
        "cat frontend/.env.development",
        "cat .env.development",
        "cd frontend && cat .env.development",
        "grep VITE_ frontend/.env.development",
        "diff frontend/.env.development /tmp/x",
        "cat FRONTEND/.ENV.DEVELOPMENT",
    ])
    def test_env_development_then_allowed(self, command):
        assert_allowed(command)

    # 10.2 L6'（決定3の範囲の外）: .env.development 以外の .env.development… や他の .env は秘密のまま
    @params([
        "cat frontend/.env.development.local",
        "cat .env.development.local",
        "cat frontend/.env.development.bak",
        "cat frontend/.env.d*",
        "cat frontend/.env*",
        "cat frontend/.env",
        "cat frontend/.env.local",
        "cat frontend/.env.production",
    ])
    def test_env_development_variants_still_blocked(self, command):
        assert_blocked(command)

    # 11節 決定10: 退避フォルダの中の .env.development は止める（L6 は basename の規則だけを外す）
    @params([
        "cat ~/claude-settings-backup/.env.development",
        "cat ~/claude-settings-backup/frontend/.env.development",
    ])
    def test_env_development_in_backup_dir_still_blocked(self, command):
        assert_blocked(command)

    @params(with_body(FUNCTION_AND_COPROC_FORMS, "sqlite3 data/clients.db .tables"))
    def test_function_and_coproc_bodies_customer_data_then_blocked(self, command):
        assert_blocked(command)

    def test_blocked_reason_mentions_customer_target(self):
        # 顧客データでも移植元と同じカテゴリ名（7節-22）
        reason = assert_blocked("sqlite3 data/clients.db .tables", project_dir="/work/proj")
        assert reason.startswith("guard: ")
        assert CATEGORY_SECRET in reason
        assert "data/clients.db" in reason

    # 10.3 9.3: 顧客データの除外の値も読む対象ではない
    @params([
        "grep -r --exclude=*.db KEY .",
        "grep -r --exclude='*.xlsx' --exclude-dir=data KEY .",
        "grep -rn --exclude-dir=data --exclude=*.xlsx --exclude=*.db --exclude='*.sqlite*' KEY .",
        "grep -r --exclude-dir data KEY .",
        "rsync -a --exclude=data --exclude='*.db' ./ /tmp/bk/",
        "tar --exclude=data --exclude='*.xlsx' -czf /tmp/x.tgz src",
        "diff -r --exclude=data a b",
    ])
    def test_exclude_customer_values_then_allowed(self, command):
        assert_allowed(command)

    # 10.3 9.3・9.3.1: 除外の値でないもの（対象の指定・中身を読む・被演算子・POSIXLY_CORRECT）は数え続ける
    @params([
        "grep -r --include=*.db KEY .",
        "grep -r --exclude=*.db KEY data",  # 除外の値は外れるが、被演算子 data は数える
        "grep -r --exclude-from=data/ex.txt KEY .",
        "rsync -a --exclude data ./ /tmp/bk/",  # rsync の空白区切りは割り引かない
        "tar --exclude data -czf /tmp/x.tgz .",
        "grep -e --exclude=*.db KEY .",  # 9.3.1
        "grep -r -- --exclude *.db",
        "POSIXLY_CORRECT=1 grep -r KEY . --exclude=*.db",
        "POSIXLY_CORRECT=1 grep -r KEY . --exclude-dir=data",
    ])
    def test_customer_values_not_as_exclusion_then_blocked(self, command):
        assert_blocked(command)

    # 10.3 9.4: 顧客データの名前の一覧だけなら通す（ファイル名の扱いは README の運用＝決定6）
    @params([
        "ls data/",
        "ls -la data/output | head",
        "ls data/ && cat README.md",
        "find . -name '*.xlsx' -print",
        "find . -name '*.xlsx' -o -name '*.db' -o -name '*.sqlite*' | sort",
        "find . -iname '*.XLSX' | wc -l",
        "ls *.db | head",
        "stat -c '%n %s' data/clients.db | cat",
        "git check-ignore -v data/clients.db x.xlsx | cat",
        "test -f data/clients.db && echo ok",
        "git ls-files | grep -E '\\.db$'",  # パターンが $ で終わり .db で終わらない
    ])
    def test_listing_customer_names_then_allowed(self, command):
        assert_allowed(command, project_dir="/work/proj")

    @params([
        "find . -name '*.db' | xargs sqlite3",
        "find . -name '*.xlsx' -exec unzip -p {} \\;",
        "find . -name '*.db' -exec sqlite3 {} .dump \\;",
        "ls data/scenarios/*.yaml | xargs cat",
        "cat $(find . -name '*.xlsx')",
        "find . -name '*.db'; sqlite3 data/clients.db .tables",
        "ls *.db && sqlite3 clients.db .tables",  # sqlite3 は許可リストに無い
    ])
    def test_listing_customer_names_feeding_reader_then_blocked(self, command):
        assert_blocked(command)

    # 10.3 9.5: /tmp の下の除外は B だけに効く。顧客データは /tmp の下でも秘密
    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        "cat /tmp/x/clients.db",
        "unzip -p /tmp/x/report.xlsx",
        "sqlite3 /tmp/p/x.sqlite3 .tables",
        "cp /tmp/p/clients.db /tmp/q/",
    ])
    def test_customer_files_under_tmp_still_blocked(self, command, project_dir):
        assert_blocked(command, project_dir=project_dir)

    # --- 【LES】ここまで ---


# ---------------------------------------------------------------------------
# カテゴリB: 保護対象を書き換える・消す・動かす
# ---------------------------------------------------------------------------

class TestProtectedWrite:
    """設定とフック（guard 自身を含む）がシェル経由で書き換わらないこと"""

    @params([
        "echo {} > .claude/settings.json",
        "echo x >> .claude/settings.json",
        ": > .claude/settings.local.json",
        "echo x >.claude/hooks/guard.py",
        "cat <<'EOF' > .claude/hooks/guard.py\nx\nEOF",
        "printf x 2> .claude/hooks/a.py",
        "echo x &> ~/.claude/settings.json",
    ])
    def test_redirect_into_protected_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "echo x | tee .claude/settings.json",
        "echo x | tee -a .claude/hooks/guard.py",
        "sed -i 's/a/b/' .claude/settings.json",
        "sed -i.bak 's/a/b/' .claude/hooks/guard.py",
        "sed --in-place 's/a/b/' .claude/settings.json",
        "perl -pi -e 's/a/b/' .claude/settings.json",
    ])
    def test_tee_and_inplace_edit_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cp /tmp/new.json .claude/settings.json",
        "cp x.py .claude/hooks/",
        "cp -t .claude/hooks x.py",
        "rsync -a x/ .claude/hooks/",
        "ln -sf /tmp/e.py .claude/hooks/guard.py",
        "install -m 755 x .claude/hooks/x.py",
        "dd if=/tmp/x of=.claude/settings.json",
    ])
    def test_copy_into_protected_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "mv .claude/settings.json /tmp/",
        "mv /tmp/s.json .claude/settings.json",
        "mv .claude/hooks/guard.py /tmp/",
        "rm .claude/hooks/guard.py",
        "rm -f .claude/settings.json",
        "rm -rf .claude/hooks",
        "rm -rf .claude",
        "git rm .claude/hooks/guard.py",
        "git mv .claude/hooks/guard.py x.py",
        "chmod -x .claude/hooks/guard.py",
        "touch .claude/hooks/new.py",
        "truncate -s0 .claude/settings.json",
    ])
    def test_move_remove_chmod_protected_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "rm ./.claude/hooks/guard.py",
        'rm "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py',
        "rm /work/proj/.claude/settings.json",  # 【LES】
        "rm '.claude/hooks/guard.py'",
        "rm ../proj/.claude/hooks/guard.py",  # 【LES】
        "ls && rm .claude/hooks/guard.py",
        'bash -c "rm .claude/hooks/guard.py"',
        "sudo rm .claude/settings.json",
    ])
    def test_protected_path_forms_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "python3 scripts/x.py -e \"open('.env')\"",
        'node app.js -c ".env"',
        "python3 -m pytest -k env",
    ])
    def test_interpreter_script_args_not_inline_code(self, command):
        assert_allowed(command)

    @params([
        "echo x > >(tee .claude/settings.json)",
        "diff <(echo a) <(rm .claude/hooks/guard.py)",
    ])
    def test_process_substitution_writing_protected_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "cd .claude/hooks && rm guard.py",
        "cd .claude; echo {} > settings.json",
        "cd .claude/hooks && sed -i 's/a/b/' guard.py",
    ])
    def test_cd_into_protected_then_write_blocked(self, command):
        assert_blocked(command)

    @params([
        "cat .claude/settings.json",
        "jq '.permissions.deny' .claude/settings.json",
        "sed -n 1,20p .claude/hooks/guard.py",
        "grep -n deny .claude/settings.json",
        "diff .claude/settings.json /tmp/x",
        "git diff .claude/settings.json",
        "ls -la .claude/hooks",
        "cp .claude/settings.json /tmp/bk.json",
        "python3 .claude/hooks/pre_tool_fp_warning.py < /dev/null",  # 【LES】
        "echo '{}' | python3 .claude/hooks/guard.py",
        "bash .claude/hooks/x.sh",  # 【LES】
        "git add .claude/hooks/guard.py .claude/settings.json",
        "cd .claude/hooks && ls",
    ])
    def test_read_or_execute_protected_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "cat .claude/settings.json 2>/dev/null",
        "python3 .claude/hooks/guard.py < x.json 2>&1",
        "cd .claude/hooks && python3 post_tool_run_tests.py 2>/dev/null",  # 【LES】
        "cd .claude/hooks && python3 x.py >&2",
        "echo x > /dev/stderr",
    ])
    def test_dev_null_and_fd_dup_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "cd .claude && cp settings.json /tmp/bk.json",
        "cd .claude/hooks && cat guard.py > /tmp/guard_copy.py",
        "cd .claude && echo x > ~/note.txt",
    ])
    def test_cd_into_protected_then_write_outside_allowed(self, command):
        assert_allowed(command)

    @params([
        "echo x > output/a.txt",
        "sed -i 's/a/b/' src/x.py",
        "cp a.json .claude-notes/settings.json",
        "rm .claude_old/hooks.txt",
        "echo x > docs/claude/settings.json",
    ])
    def test_writes_elsewhere_then_allowed(self, command):
        assert_allowed(command)

    # 書き込み先が find の探し始める場所や標準入力から渡される形
    @params([
        "find .claude/hooks -name '*.py' -exec rm {} \\;",
        "find .claude/hooks -name '*.pyc' -delete",
        "find .claude -name settings.json -execdir sed -i 's/a/b/' {} +",
        "echo .claude/hooks/guard.py | xargs rm",
        "ls .claude/hooks/*.py | xargs sed -i 's/a/b/'",
        "git -C .claude/hooks rm guard.py",
        "git -C .claude mv settings.json /tmp/s.json",
    ])
    def test_indirect_write_into_protected_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "find .claude -name settings.json -exec cat {} \\;",
        "find .claude/hooks -name '*.py' -exec cp {} /tmp/bk/ \\;",
        "ls .claude/hooks/*.py | xargs grep foo",
        "find . -name '*.pyc' -delete",
        "find . -name '*.tmp' | xargs rm -f",
        "git -C sub rm old.py",
    ])
    def test_indirect_read_or_unrelated_write_then_allowed(self, command):
        assert_allowed(command)

    # cd は実行順に追う。.claude から出た後の書き込みは止めない
    @params([
        "cd .claude && ls; cd ..; echo x > out.txt",
        "cd .claude/hooks; cd -; echo x > a.txt",
        "cd .claude/hooks && cd /tmp && echo x > a.txt",
        "pushd .claude/hooks && popd && echo x > a.txt",
        "cd .claude && cd && echo x > a.txt",
    ])
    def test_cd_out_of_protected_then_write_allowed(self, command):
        assert_allowed(command)

    @params([
        "cd .claude/hooks; cd ..; echo x > settings.json",
        "cd .claude && cd hooks && rm guard.py",
        "cd .claude && bash -c 'rm settings.json'; cd ..",
        "cd /tmp; cd -; cd .claude/hooks && rm guard.py",
    ])
    def test_cd_moves_within_protected_then_write_blocked(self, command):
        assert_blocked(command)

    def test_blocked_reason_mentions_category_and_target(self):
        reason = assert_blocked("rm .claude/hooks/guard.py")
        assert CATEGORY_PROTECTED in reason
        assert ".claude/hooks/guard.py" in reason

    # --- 仕様 9.5: プロジェクトの外の使い捨て置き場（/tmp・/var/tmp）の .claude は保護しない ---

    # 除外は語の文字列がそのまま行き先になる書き込み先（リダイレクト・cp・sed -i・rm・cd の追跡・git -C・
    # find -delete／-exec・find -fprint 系）に効く。xargs の書き込み先には当てない（仕様 9.10 決定1）。
    # main は常に CLAUDE_PROJECT_DIR を渡すが、無いときも同じに通ること
    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        "echo x > /tmp/claude-1000/x/scratchpad/proto/.claude/hooks/x.py",
        "mkdir -p /tmp/p/.claude/hooks && cp a.py /tmp/p/.claude/hooks/",
        "cat <<'EOF' > /tmp/p/.claude/settings.json\n{}\nEOF",
        "sed -i 's/a/b/' /tmp/p/.claude/settings.json",
        "rm -rf /tmp/p/.claude",
        "cd /tmp/p/.claude/hooks && echo x > a.py",
        "git -C /tmp/p/.claude/hooks rm x.py",
        # "echo /tmp/p/.claude/hooks/x.py | xargs rm" は xargs の書き込み先に除外を当てなくなったので
        # test_tmp_path_through_xargs_then_blocked へ移した（仕様 9.10 決定1）
        "find /tmp/p/.claude/hooks -name '*.pyc' -delete",
        "find /tmp/p/.claude -name '*.pyc' -exec rm {} +",  # find は xargs ではないので除外が効く
        "find . -fls /tmp/p/.claude/hooks/l.txt",
        "echo x > /var/tmp/p/.claude/settings.json",
        "rm /tmp/p/.claude/hooks/*.pyc",  # . で始まらないグロブは .. に当たらない
    ])
    def test_write_under_tmp_outside_project_then_allowed(self, command, project_dir):
        assert_allowed(command, project_dir=project_dir)

    # 相対・$ 起点・~ 起点・/tmp の外の絶対パスは、プロジェクト自身の .claude として保護し続ける
    @params([
        "echo x > .claude/hooks/a.py",
        "echo x > ./.claude/settings.json",
        "rm /work/proj/.claude/hooks/guard.py",
        'rm "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard.py',
        "rm ${CLAUDE_PROJECT_DIR}/.claude/settings.json",
        "rm ../proj/.claude/hooks/guard.py",
        "echo x > ~/pjt/proj/.claude/settings.json",  # 【LES】
        "echo x > $HOME/pjt/proj/.claude/hooks/a.py",  # 【LES】
        # 【LES】移植元のホームの絶対パスの行は、上の /work/proj の絶対パスの行と同じ形なので持ち込まない
    ])
    def test_project_claude_dir_then_still_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # guard は HOME を見ないので、ユーザー設定は書き方を問わず保護パスのまま
    @params([
        "echo x > ~/.claude/settings.json",
        "echo x > $HOME/.claude/hooks/x.py",
        "echo x > ${HOME}/.claude/settings.json",
        "echo x > /home/user/.claude/settings.json",  # 【LES】
        "rm -rf ~/.claude",
        "sed -i 's/a/b/' ~/.claude/settings.json",
    ])
    def test_user_claude_dir_then_still_blocked(self, command):
        assert_blocked(command)

    # 案A の固定: 他のプロジェクトの .claude はそのプロジェクトのセッションで Edit ツールで書く
    @params([
        "echo x > ~/pjt/other/.claude/settings.json",  # 【LES】
        "rm /work/other/.claude/hooks/guard.py",  # 【LES】
        "cd /work/other && rm .claude/hooks/guard.py",  # 【LES】
    ])
    def test_other_project_claude_dir_then_still_blocked(self, command):
        assert_blocked(command)

    # 正規化してから比べるので、/tmp を経由してプロジェクトへ戻る形は止まる
    @params([
        "echo x > /tmp/../work/proj/.claude/settings.json",
        "rm /tmp/./p/../../work/proj/.claude/hooks/guard.py",
        "echo x > //tmp/../work/proj/.claude/settings.json",
        "echo x > /tmpx/.claude/settings.json",  # /tmp/ の下ではない
        "echo x > /tmp/$X/.claude/hooks/a.py",
        "echo x > $TMPDIR/p/.claude/hooks/a.py",
        "cd /tmp/p/.claude && cd ../../../work/proj/.claude/hooks && rm guard.py",
        "cd /tmp && cd /work/proj/.claude && rm settings.json",
        # cd - で戻った先の相対パスは保護パス
        "cd /tmp/p/.claude/hooks && cd - && rm .claude/hooks/guard.py",
        # ブレース展開・. で始まるグロブは、文字列の正規化と展開後の行き先が違いうる（$ と同じく中身が分からない）
        "rm /tmp/{a,../work/proj}/.claude/hooks/guard.py",
        "rm /tmp/{x/..,..}/work/proj/.claude/settings.json",
        "rm /tmp/.[.]/work/proj/.claude/settings.json",
        "rm /tmp/.?/work/proj/.claude/settings.json",
        "rm /tmp/.*/work/proj/.claude/settings.json",
        "cd /tmp/.?/work/proj/.claude && rm settings.json",
    ])
    def test_tmp_path_escaping_back_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # J1: 字句解析は置換の中身を語から取り除き、$'…' のエスケープを簡略化して読むので、
    # そうして組み立てた語の文字列は実際の行き先ではない。/tmp の下に見えても外さない
    @params([
        "rm /tmp/$(echo ..)/work/proj/.claude/settings.json",
        "rm /tmp/`echo ..`/work/proj/.claude/settings.json",
        "cd /tmp/$(echo ..)/work/proj/.claude/hooks && rm guard.py",
        'echo x > "/tmp/$(echo ..)/work/proj/.claude/hooks/a.py"',
        "cp a.py /tmp/$(echo ..)/work/proj/.claude/hooks/",
        "echo x > /tmp/p$((1+1))/.claude/hooks/a.py",  # 算術展開も同じ扱い
        # 行き先は /tmp の下だが、置換入りの語は外さない（誤検知の側として許容。9.9 決定4）
        "echo x > /tmp/p-$(date +%s)/.claude/hooks/a.py",
        "rm /tmp/$'\\x2e\\x2e'/work/proj/.claude/settings.json",
        "echo x > /tmp/$'p'/.claude/hooks/a.py",  # $'…' 入りの語は外さない（9.9 決定3。誤検知の側）
    ])
    def test_tmp_path_built_with_substitution_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # 既知の穴（移植元で決定。今回は直さない）: 行継続をはさんだ `$\<改行>(` を字句解析は置換と読まず、  # 【LES】
    # `(` で単純コマンドを切るので、後ろのパスが別のコマンド名になり書き込み先として見えない（/tmp に関係なく通る）。
    # strict にしておき、直ったときに赤になって気づけるようにする
    @pytest.mark.xfail(strict=True, reason="既知の穴: 字句解析が行継続を外さず ( で単純コマンドを切る。仕様8節")
    @params([
        "rm /tmp/$\\\n(echo ..)/work/proj/.claude/settings.json",
        "rm $\\\n(true).claude/hooks/guard.py",
    ])
    def test_line_continued_substitution_known_hole_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    # 判定は書き込み先の語ごと。ヒアドキュメント本文や別の語の置換では外すのをやめない
    @params([
        "cat > /tmp/p/.claude/hooks/x.sh <<'EOF'\necho $(date)\nEOF",
        "cat > /tmp/p/.claude/hooks/x.sh <<EOF\necho $(date)\nEOF",
        'echo "$(date)" > /tmp/p/.claude/hooks/log.txt',
        "rm /tmp/p/.claude/hooks/*.pyc",
    ])
    def test_substitution_outside_target_word_under_tmp_then_allowed(self, command):
        assert_allowed(command)

    # xargs の書き込み先は、標準入力の語（パイプの途中で加工されうる）か、-I の置き換え文字列に標準入力の語を
    # はめ込んだもので、文字列から行き先を決められない。/tmp の下に見えても外さない（仕様 9.5・9.10 決定1）
    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        # パイプの途中の加工
        "printf '/tmp/%s/work/proj/.claude/settings.json' .. | xargs rm",
        "echo /tmp/x/work/proj/.claude/settings.json | sed s/x/../ | xargs rm",
        "echo /tmp/x/work/proj/.claude/settings.json | tr x . | xargs rm",
        "echo -e '/tmp/\\x2e\\x2e/work/proj/.claude/settings.json' | xargs rm",
        "echo /tmp/a/work/proj/.claude/settings.json | cut -d/ -f1,4- | xargs rm",
        # 置き換え文字列
        "echo .. | xargs -I X rm /tmp/X/work/proj/.claude/settings.json",
        "echo .. | xargs -IX rm /tmp/X/work/proj/.claude/settings.json",
        "echo .. | xargs --replace=X rm /tmp/X/work/proj/.claude/settings.json",
        "echo .. | xargs -I X cp a.py /tmp/X/work/proj/.claude/hooks/",
        # ファイルから渡す
        "echo /tmp/p/.claude/hooks/x.py > /tmp/list; xargs -a /tmp/list rm",
        # 加工の無い形（誤検知として受け入れる。通す側から移した）
        "echo /tmp/p/.claude/hooks/x.py | xargs rm",
        # xargs が走らせるシェルの中身（置き換え文字列が sh -c の文字列に入る）
        "echo .. | xargs -I X sh -c 'rm /tmp/X/work/proj/.claude/settings.json'",
        "echo .. | xargs -I X bash -c 'rm /tmp/X/work/proj/.claude/settings.json'",
        "echo .. | xargs -I X bash -c 'echo y > /tmp/X/work/proj/.claude/settings.json'",
        # xargs が走らせる find（探し始める場所・-fprint 系・-exec の中の書き込み先と sh -c の中身）
        "echo .. | xargs -I X find /tmp/X/work/proj/.claude -delete",
        "echo .. | xargs -I X find /tmp/X/work/proj/.claude -exec rm {} +",
        "echo .. | xargs -I X find . -fls /tmp/X/work/proj/.claude/settings.json",
        "echo .. | xargs -I X find . -maxdepth 0 -exec rm /tmp/X/work/proj/.claude/settings.json \\;",
        "echo .. | xargs -I X find . -maxdepth 0 -exec sh -c 'rm /tmp/X/work/proj/.claude/settings.json' \\;",
    ])
    def test_tmp_path_through_xargs_then_blocked(self, command, project_dir):
        assert_blocked(command, project_dir=project_dir)

    # 除外を外すだけで構造の判定は変えないので、.claude を含まない書き込みは xargs でも通る
    @pytest.mark.parametrize("project_dir", ["/work/proj", None], ids=["proj", "noproj"])
    @params([
        "echo x | xargs rm /tmp/a.txt",
        "echo a.py | xargs -I{} cp {} /tmp/bk/",
        "find /tmp/p -name '*.log' | xargs rm",
        "echo a | xargs -I X sh -c 'rm /tmp/X.log'",
        "echo a | xargs -I X bash -c 'echo y > /tmp/X.txt'",
    ])
    def test_tmp_path_through_xargs_without_claude_then_allowed(self, command, project_dir):
        assert_allowed(command, project_dir=project_dir)

    # プロジェクトが /tmp の下にある（テストの tmp_path など）ときは、プロジェクトの .claude を守る
    @params([
        "echo x > /tmp/proj/.claude/settings.json",
        "rm /tmp/proj/.claude/hooks/guard.py",
        "rm .claude/hooks/guard.py",
        "cd /tmp/proj/.claude/hooks && rm guard.py",
        "rm /tmp/x/../proj/.claude/hooks/guard.py",
    ])
    def test_project_dir_under_tmp_then_still_blocked(self, command):
        assert_blocked(command, project_dir="/tmp/proj")

    # 秘密パス（A）は場所を問わない。9.5 の除外は B だけに効く
    @params(["cat /tmp/p/.env", "cat /tmp/p/.claude/settings.local.json"])
    def test_secret_under_tmp_then_still_blocked(self, command):
        assert_blocked(command)

    # --- 仕様 9.5.1: find -fprint 系の FILE は書き込み先 ---

    @params([
        "find . -fprint .claude/settings.json",
        "find . -name x -fls .claude/hooks/a.py",
        "find . -fprint0 ~/.claude/settings.json",
        "find . -fprintf .claude/hooks/x.py '%p\\n'",
        "cd .claude/hooks && find . -fprint list.txt",
    ])
    def test_find_fprint_into_protected_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "find . -name x -fprint /tmp/list.txt",
        "find . -fprintf out/list.txt '%p\\n'",
        # 保護パスは探し始める場所で、書き込み先ではない
        "find .claude/hooks -name '*.py' -fprint /tmp/hooks_list.txt",
        # /tmp の下の -fls は 9.5 の test_write_under_tmp_outside_project_then_allowed で見る
    ])
    def test_find_fprint_elsewhere_then_allowed(self, command):
        assert_allowed(command)

    # --- 仕様 9.4.1: 関数定義・coproc・複合コマンドの本体も判定に掛かる ---

    @params(with_body(FUNCTION_AND_COPROC_FORMS, "rm .claude/hooks/guard.py"))
    def test_function_and_coproc_bodies_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    @params(with_body(COMPOUND_FORMS, "rm .claude/hooks/guard.py"))
    def test_compound_command_bodies_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")


# ---------------------------------------------------------------------------
# カテゴリC: 取り返しのつかない操作
# ---------------------------------------------------------------------------

class TestIrreversibleOps:
    """取り返しのつかない git / rm を止め、日常の git / rm は止めないこと"""

    @params([
        "git push --force", "git push -f", "git push origin main --force",
        "git push --force-with-lease", "git push --force-with-lease=main:abc",
        "git push -fu origin main", "git push origin +main", "git -C /x push -f",
        "'git' push \"-f\"", "/usr/bin/git push --force",
    ])
    def test_force_push_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "git reset --hard", "git reset --hard HEAD~1", "git reset HEAD --hard",
        "git -C x reset --hard", "git status && git reset --hard",
    ])
    def test_reset_hard_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "rm -rf /", "rm -rf /*", "rm -rf / --no-preserve-root", "rm -rf ~",
        "rm -rf ~/", "rm -rf ~/*", "rm -rf $HOME", 'rm -rf "$HOME"',
        "rm -rf ${HOME}/*", "rm -rf *", "rm -rf .", "rm -rf ./", "rm -rf ./*",
        "rm -rf ..", "rm -rf ../*", "rm -rf .*", "rm -fr *", "rm -r -f *",
        "rm -R .", "rm --recursive --force ~", "rm -rfv *", "rm -r *",
        "sudo rm -rf /", "cd /tmp && rm -rf *",
        "rm -rf build *",  # 対象のどれかが広い
    ])
    def test_recursive_rm_broad_target_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "rm -rf /work/proj", "rm -rf /work/proj/", "rm -rf /work/proj/*",
        "rm -rf /work", 'rm -rf "$CLAUDE_PROJECT_DIR"', "rm -rf ${CLAUDE_PROJECT_DIR}/*",
    ])
    def test_recursive_rm_project_root_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    @params([
        "git clean -fdx", "git clean -fx", "git clean -xdf", "git clean -fX",
        "git clean -f -d -x", "git clean -d -x -f", "git clean --force -x",
        "git clean -ffdx", "git -C x clean -fdx", "git status && git clean -fdx",
        "git clean -nfx",
    ])
    def test_git_clean_force_with_ignored_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "git clean -n", "git clean -nd", "git clean --dry-run -x", "git clean -fd",
        "git clean -f", "git clean -f -d",
    ])
    def test_git_clean_safe_forms_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "git checkout -- .", "git checkout .", "git checkout HEAD -- .",
        "git checkout -- ./", "git checkout -- :/", "git -C x checkout -- .",
    ])
    def test_git_checkout_whole_tree_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "git checkout -- path/file.py", "git checkout -- src/x.py tests/y.py",
        "git checkout main", "git checkout -b feature/x", "git checkout -",  # 【LES】
        "git restore .", "git restore src/x.py", "git branch -D old",
    ])
    def test_git_checkout_path_or_branch_then_allowed(self, command):
        assert_allowed(command)

    @params([
        "git push", "git push origin main", "git push -u origin feature/x",  # 【LES】
        "git push --follow-tags", "git push --no-force-with-lease", "git reset",
        "git reset --soft HEAD~1", "git reset HEAD file.py", "git log --oneline -5",
        'git commit -m "force push を禁止"',
    ])
    def test_everyday_git_then_allowed(self, command):
        assert_allowed(command)

    # 書き方の違い（`./.`・`~/.`・`$PWD`）を正規化しても広い対象。相対パスは作業ディレクトリ＝プロジェクトとみなす
    @params([
        "rm -rf ./.", "rm -rf ../..", "rm -rf src/..", "rm -rf ~/.", "rm -rf $HOME/..",
        "rm -rf $CLAUDE_PROJECT_DIR/.", 'rm -rf "$PWD"', "rm -rf ${PWD}/*", "rm -rf ../proj",
        "rm -rf //", "rm -rf /work/./proj", "rm -rf /work/proj/..",
    ])
    def test_recursive_rm_normalized_broad_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    @params(["rm -rf ./.", "rm -rf ../..", 'rm -rf "$PWD"', "rm -rf ~/.", "rm -rf $CLAUDE_PROJECT_DIR/."])
    def test_recursive_rm_normalized_broad_without_project_dir_then_blocked(self, command):
        assert_blocked(command)

    @params([
        'rm -rf "$(mktemp -d)"', 'rm -rf "$tmp"/x', "rm -rf ../other/build", "rm -rf ~/.cache/pip",
        "rm -rf src/../build", "rm -rf /work/proj/./output",
    ])
    def test_recursive_rm_narrow_or_unknown_then_allowed(self, command):
        assert_allowed(command, project_dir="/work/proj")

    @params([
        "rm -rf output/tmp", "rm -rf ./build", "rm -rf .pytest_cache __pycache__",
        "rm -f *.pyc", "rm *", "rm -rf /tmp/claude-1000/x", "rm -rf /work/proj/output",
        "rm -rf node_modules",
    ])
    def test_everyday_rm_then_allowed(self, command):
        assert_allowed(command, project_dir="/work/proj")

    def test_blocked_reason_mentions_category(self):
        reason = assert_blocked("git push --force")
        assert CATEGORY_IRREVERSIBLE in reason

    # C1b（移植元で追加）: リモートのブランチ・タグを消す／丸ごと一致させる push  # 【LES】
    @params([
        "git push origin :main", "git push origin :refs/heads/feature/x",
        "git push origin :refs/tags/v1.0", "git push --delete origin feature",
        "git push origin --delete feature", "git push -d origin feature",
        "git push origin feature -d", "git push --dry-run --delete origin x",
        "git push -nd origin x", "git push --mirror", "git push --mirror origin",
    ])
    def test_push_delete_remote_ref_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "git -C /x push origin :main", "git -c core.pager=cat push --delete origin x",
        "git --git-dir=.git push --mirror", "git --git-dir .git push origin :main",
        "git --no-pager push -d origin x", "'git' push \"--delete\" origin x",
        "git push origin ':main'", "/usr/bin/git push --mirror",
        'bash -c "git push origin :main"', "sh -c 'git push --delete origin x'",
        'eval "git push --mirror"', "sudo git push -d origin x",
        "git status && git push origin :main", "echo $(git push --delete origin x)",
    ])
    def test_push_delete_remote_ref_wrapped_then_blocked(self, command):
        assert_blocked(command)

    # コロンの左が空でない refspec は削除ではない。`:` だけは matching push
    @params([
        "git push origin HEAD:main", "git push origin HEAD:refs/heads/feature/x",
        "git push origin feature:feature", "git push origin refs/heads/a:refs/heads/b",
        "git push origin v1.0", "git push origin refs/tags/v1.0:refs/tags/v1.0",
        "git push --tags", "git push origin :",
    ])
    def test_push_colon_refspec_not_delete_then_allowed(self, command):
        assert_allowed(command)

    # `+` で始まる refspec は C1 で止まる。C1b を足しても変わらないこと
    @params(["git push origin +HEAD:main", "git push origin +:main"])
    def test_push_plus_refspec_with_colon_then_blocked(self, command):
        assert_blocked(command)

    # C2d（移植元で追加）: 未コミットの変更を捨てて切り替える  # 【LES】
    @params([
        "git checkout -f main", "git checkout -f", "git checkout --force develop",
        "git checkout main -f", "git checkout -fq main", "git checkout -fb x",
        "git checkout -f -- file.py", "git switch -f main", "git switch --force main",
        "git switch --discard-changes main", "git switch main --discard-changes",
        "git switch -f -c x",
    ])
    def test_checkout_or_switch_discarding_changes_then_blocked(self, command):
        assert_blocked(command)

    @params([
        "git -C /x checkout -f main", "git -c advice.detachedHead=false checkout -f main",
        "git --git-dir=.git --work-tree=. switch -f main", "'git' checkout \"-f\" main",
        "/usr/bin/git switch --discard-changes main", 'bash -c "git checkout -f main"',
        "eval 'git switch -f main'", "env GIT_TRACE=0 git checkout -f main",
        "git fetch && git switch --discard-changes main", "git stash; git checkout -f main",
    ])
    def test_checkout_or_switch_discarding_changes_wrapped_then_blocked(self, command):
        assert_blocked(command)

    # `-b`/`-c` の直後はブランチ名なので、その中の `f` は強制ではない
    @params([
        "git checkout main", "git checkout -b feature/fix", "git checkout -bfix/x",
        "git checkout -t origin/feature", "git checkout -", "git checkout -- src/x.py",
        "git checkout HEAD~1 -- file.py", "git switch main", "git switch -c feature/fix",
        "git switch -cfeature", "git switch -", "git switch --detach v1.0",
    ])
    def test_checkout_or_switch_everyday_then_allowed(self, command):
        assert_allowed(command)

    # 移植元で決定した判断（restore・branch -D は対象外）を、移植元で再確認したもの  # 【LES】
    @params([
        "git restore .", "git restore --staged .", "git restore src/x.py",
        "git branch -D old", "git branch -d merged",
    ])
    def test_restore_and_branch_delete_still_allowed(self, command):
        assert_allowed(command)

    @pytest.mark.parametrize(
        ("command", "operation"),
        [
            ("git push origin :main", ":main"),
            ("git push --delete origin x", "--delete"),
            ("git push --mirror", "--mirror"),
            ("git checkout -f main", "-f"),
            ("git switch --discard-changes main", "--discard-changes"),
        ],
        ids=["push-colon", "push-delete", "push-mirror", "checkout-f", "switch-discard"],
    )
    def test_blocked_reason_names_new_operations(self, command, operation):
        reason = assert_blocked(command)
        assert CATEGORY_IRREVERSIBLE in reason, reason
        assert operation in reason, reason

    # --- 仕様 9.4.1: 関数定義・coproc・複合コマンドの本体も判定に掛かる ---

    @params(with_body(FUNCTION_AND_COPROC_FORMS, "git push --force"))
    def test_function_and_coproc_bodies_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")

    @params(with_body(COMPOUND_FORMS, "git push --force"))
    def test_compound_command_bodies_then_blocked(self, command):
        assert_blocked(command, project_dir="/work/proj")


# ---------------------------------------------------------------------------
# 全カテゴリ横断の回帰防止
# ---------------------------------------------------------------------------

class TestEverydayCommandsAllowed:
    """このプロジェクトの日常コマンドが1つも止まらないこと"""

    @params([
        '.venv/bin/python -m pytest tests/ -q -m "not slow"',  # 【LES】
        ".venv/bin/python -m pytest tests/hooks/test_guard.py -k env",  # 【LES】
        ".venv/bin/python -m src.main scenario.yaml",  # 【LES】
        ".venv/bin/python -m src.main data/scenarios/a.yaml",  # 【LES】README の手順。中身は読まない
        "git status --porcelain",
        "git diff --stat",
        'git add -A && git commit -m "x"',
        "ls -la",
        "python3 -c \"import json;print(json.load(open('.claude/settings.json'))['hooks'])\"",
        "cd frontend && npm run build",  # 【LES】
        'grep -rn "Read(" .claude/settings.json',
        "cat scenario.yaml",  # 【LES】
        "mkdir -p data/scenarios",  # 【LES】README の手順
    ])
    def test_project_daily_commands_then_allowed(self, command):
        assert_allowed(command)

    # C1b・C2d（移植元で追加）を足しても日常のブランチ操作・push が止まらないこと  # 【LES】
    @params([
        "git checkout main",  # 【LES】
        "git checkout main && git pull",  # 【LES】
        "git checkout -b feature/guard-git",
        "git checkout -- tests/hooks/test_guard.py",
        "git switch main",  # 【LES】
        "git switch -c fix/x",
        "git push",
        "git push origin main",  # 【LES】
        "git push -u origin feature/guard-git",
        "git push origin HEAD:main",  # 【LES】
        "git push --follow-tags origin main",  # 【LES】
        'git commit -m "git push --delete と checkout -f を止める"',
        "git log --oneline --diff-filter=D",  # D を含むが push ではない
        "git diff --stat origin/main...HEAD",  # 【LES】
    ])
    def test_project_daily_git_branch_and_push_then_allowed(self, command):
        assert_allowed(command)

    @params(["", "   ", "\n"])
    def test_empty_or_whitespace_command_then_allowed(self, command):
        assert_allowed(command)

    @params(['echo "unterminated', "cat 'x"])
    def test_unparseable_command_then_allowed(self, command):
        assert_allowed(command)

    def test_unparseable_tail_still_checks_earlier_lines(self):
        assert_blocked('cat .env\necho "unterminated')

    # 本体を判定に掛けるようにしても（仕様 9.4.1）、本体に危険な語が無ければ従来どおり通る
    @params([
        "function f { echo hi; }; f",
        "function f { function g { ls; }; }; f",
        "coproc sleep 1",
        "coproc W { sleep 1; }",
        "coproc W while sleep 1; do :; done",
    ])
    def test_function_and_coproc_harmless_bodies_then_allowed(self, command):
        assert_allowed(command)

    # --- 【LES】ここから（仕様 10.3）---

    # 顧客データの置き場所を作る・移す・使う日常の操作は止めない（読み取り動詞が無い・スクリプトを実行するだけ）
    @params([
        "mkdir -p data/scenarios",
        "mkdir -p data && mv clients.db cf_simulation_20260407.xlsx data/",  # 運営者が直下の顧客データを移す手順
        ".venv/bin/python -m src.main data/scenarios/a.yaml",
        "LES_DB_PATH=data/clients.db .venv/bin/python -m uvicorn src.api.app:app",
        "du -sh data",
        "wc -c data/clients.db",
        "file data/output/x.xlsx",
        ".venv/bin/python -m pytest tests/db/test_sqlite_repository.py -q",
        "cat scenario.yaml",
    ])
    def test_customer_daily_commands_then_allowed(self, command):
        assert_allowed(command, project_dir="/work/proj")

    # --- 【LES】ここまで ---


# ---------------------------------------------------------------------------
# 入出力・fail-open
# ---------------------------------------------------------------------------

class TestMainContract:
    """exit 2＋stderr で止める／それ以外は exit 0 で黙る。guard の故障で Bash を止めない"""

    def test_block_exit2_reason_on_stderr(self):
        code, err = run_main(bash_input("cat .env"))
        assert code == 2
        assert err.rstrip("\n") == _hook().check_command("cat .env", None)

    def test_allow_exit0_silent(self):
        code, err = run_main(bash_input("ls"))
        assert code == 0
        assert err == ""

    INVALID_INPUTS = [
        "", "not json", "[]", "null", "{}",
        '{"tool_name":"Bash"}',
        '{"tool_name":"Bash","tool_input":{}}',
        '{"tool_name":"Bash","tool_input":{"command":123}}',
        '{"tool_name":"Bash","tool_input":"cat .env"}',
    ]

    @pytest.mark.parametrize("stdin_text", INVALID_INPUTS, ids=ids(INVALID_INPUTS))
    def test_invalid_input_fail_open(self, stdin_text):
        code, err = run_main(stdin_text)
        assert code == 0
        assert err == ""

    def test_non_bash_tool_ignored(self):
        code, _ = run_main(bash_input("cat .env", tool_name="Read"))
        assert code == 0

    def test_missing_tool_name_still_checked(self):
        code, _ = run_main(json.dumps({"tool_input": {"command": "cat .env"}}))
        assert code == 2

    def test_internal_exception_fail_open(self, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("壊れた")

        monkeypatch.setattr(_hook(), "check_command", boom)
        code, err = run_main(bash_input("cat .env"))
        assert code == 0
        assert err == ""

    def test_project_dir_from_environ(self):
        code, _ = run_main(bash_input("rm -rf /work/proj"), environ={"CLAUDE_PROJECT_DIR": "/work/proj"})
        assert code == 2

    def test_stderr_write_failure_still_blocks(self):
        class BrokenStream:
            def write(self, _):
                raise OSError("書けない")

        code = _hook().main(stdin=io.StringIO(bash_input("cat .env")), stderr=BrokenStream(), environ={})
        assert code == 2

    def test_never_opens_files(self, monkeypatch):
        def forbidden(*args, **kwargs):
            raise AssertionError("guard がファイルを開こうとしました")

        mod = _hook()
        monkeypatch.setattr(builtins, "open", forbidden)
        monkeypatch.setattr(io, "open", forbidden)
        monkeypatch.setattr(pathlib.Path, "open", forbidden)
        monkeypatch.setattr(pathlib.Path, "read_text", forbidden)
        monkeypatch.setattr(pathlib.Path, "read_bytes", forbidden)
        assert mod.check_command("cat .env")
        assert mod.check_command("ls") is None
        assert mod.check_command("sqlite3 data/clients.db .tables", "/work/proj")  # 【LES】

    def test_no_subprocess(self, monkeypatch):
        def forbidden(*args, **kwargs):
            raise AssertionError("guard が外部コマンドを起動しようとしました")

        monkeypatch.setattr(subprocess, "run", forbidden)
        monkeypatch.setattr(subprocess, "Popen", forbidden)
        monkeypatch.setattr(os, "system", forbidden)
        code, _ = run_main(bash_input("cat .env"))
        assert code == 2
        code, _ = run_main(bash_input("ls"))
        assert code == 0

    # 絶対時間は負荷で揺れるので、交互に測った n と 2n の CPU 時間の比で「線形であって二乗でない」ことを
    # 確かめる（仕様 9.7・9.10 決定3）。線形なら比は約2、二乗なら約4なので 3 で分かれる。
    # 入力形は繰り返し回数 n の関数。基準の n は普段の t(n) が 50ms 以上になる大きさ（短いと比が時計の粒度で決まる）
    LONG_COMMANDS = {
        "many_cmds": (lambda n: "echo a; " * n + "ls", 20000),
        "quotes": (lambda n: "'" * n, 300000),
        # 1行ごとに上限（MAX_DEPTH）を越える入れ子を置く。1行だけだと上限で打ち切られて仕事量が n によらず一定になり、
        # 比の検証にならない（設計 12.12 (4)）
        "nested_subst": (lambda n: ("$(" * 20 + "\n") * n, 5000),
        # xargs のたびにコマンド全体を走査し直さない
        "many_xargs": (lambda n: "echo .claude/x | xargs rm; " * n, 5000),
        # 長い cd 先を毎回つなぎ直さない。n を下げると MAX_PATH_CHARS を外した退行を比で捕まえられない（設計 12.12 (4)）
        "long_cd": (lambda n: "cd .claude/" + "a/" * n + "; " + "cd ../; " * (n // 2), 20000),
        # 「一覧だけ」の判定を単純コマンドごとにやり直さない
        "many_listing": (lambda n: "find . -name .env -print | sort; " * n, 5000),
    }
    # 比だけでは「線形だが桁違いに遅い」退行を見逃すので、緩い絶対上限も見る（普段の 2n は1秒前後）
    MAX_SECONDS = 5.0

    @staticmethod
    def _min_times(commands, repeat=3):
        """commands それぞれの check_command 1回の CPU 時間の、repeat 回の最小値（最小値は負荷の山を拾いにくい）

        経過時間ではなくこのプロセスの CPU 時間で測る。経過時間は他のプロセスに CPU を取られた分も入り、
        n と 2n の片方だけがそれに当たって比が揺れる（CPU を2倍に取り合わせた負荷下で 4.3 になった）。
        n と 2n は交互に測る（キャッシュなど残る揺れも両方に同じように乗せる）
        """
        mod = _hook()
        times: list[list[float]] = [[] for _ in commands]
        for _ in range(repeat):
            for k, command in enumerate(commands):
                start = time.process_time()
                mod.check_command(command)
                times[k].append(time.process_time() - start)
        return [min(ts) for ts in times]

    def _assert_scales_linearly(self, make, n):
        # 温め: 初回のモジュール読み込み・正規表現のコンパイルを t(n) に入れない
        _hook().check_command(make(10))
        t1, t2 = self._min_times([make(n), make(2 * n)])
        assert t2 < 3 * t1, f"二乗に近い伸び: t(n)={t1:.3f}s t(2n)={t2:.3f}s 比={t2 / t1:.2f}"
        assert t2 < self.MAX_SECONDS, f"遅すぎる: t(2n)={t2:.3f}s"

    @pytest.mark.slow  # 【LES】
    @pytest.mark.parametrize("case", list(LONG_COMMANDS), ids=list(LONG_COMMANDS))
    def test_long_command_scales_linearly(self, case):
        make, n = self.LONG_COMMANDS[case]
        self._assert_scales_linearly(make, n)

    @pytest.mark.slow  # 【LES】
    def test_long_eval_chain_scales_linearly_and_still_checked(self):
        # eval eval … は続く eval をまとめて剥がす（1段ずつ剥がすと MAX_DEPTH で打ち切られ cat .env まで届かない）
        def make(n):
            return "eval " * n + "cat .env"
        n = 30000
        assert _hook().check_command(make(n))
        assert _hook().check_command(make(2 * n))
        self._assert_scales_linearly(make, n)

    def test_subprocess_block(self, tmp_path):
        hook_script("guard")  # 【LES】無ければテストごとに pytest.fail（移植元の HOOK_PATH の確認の代わり）
        result = run_subprocess(bash_input(f"cat {PROBE_ENV}").encode(), tmp_path)
        stderr = result.stderr.decode("utf-8", errors="replace")
        assert result.returncode == 2
        assert stderr.startswith("guard: ")
        assert result.stdout == b""
        assert "DUMMY" not in stderr

    def test_subprocess_allow(self, tmp_path):
        hook_script("guard")  # 【LES】無ければテストごとに pytest.fail（移植元の HOOK_PATH の確認の代わり）
        result = run_subprocess(bash_input("ls").encode(), tmp_path)
        assert result.returncode == 0
        assert result.stdout == b""
        assert result.stderr == b""

    def test_subprocess_garbage_stdin(self, tmp_path):
        hook_script("guard")  # 【LES】無ければテストごとに pytest.fail（移植元の HOOK_PATH の確認の代わり）
        result = run_subprocess(b"\x00\xff not json", tmp_path)
        assert result.returncode == 0

    # --- 【LES】ここから（仕様 4節）---

    def test_project_dir_from_environ_for_customer_data(self):
        # 顧客データの置き場所の③（プロジェクトのフォルダ名の直後の data）は project_dir が無いと働かない形
        code, _ = run_main(bash_input("cat /work/proj/data/scenarios/a.yaml"),
                           environ={"CLAUDE_PROJECT_DIR": "/work/proj"})
        assert code == 2

    # --- 【LES】ここまで ---


# ---------------------------------------------------------------------------
# settings.json との整合
# ---------------------------------------------------------------------------

# deny の Read 規則 → その規則が守るパスの代表例。
# deny に新しい Read 規則が増えたら、ここに足すまで赤になる（guard の追従漏れを検出する）
DENY_SAMPLES = {
    "Read(./.env)": ".env",
    "Read(**/.env)": "a/b/.env",
    "Read(**/.env.local)": "x/.env.local",
    "Read(**/.env.*.local)": ".env.dev.local",
    "Read(**/.env.production*)": ".env.production",
    # 【LES】Read(**/.env.development*) は LES の deny に無い（決定3。test_deny_exception_is_also_allowed_by_guard）
    "Read(**/.env.staging*)": ".env.staging",
    "Read(**/.env.test*)": ".env.test",
    "Read(**/*.pem)": "k.pem",
    "Read(**/id_rsa*)": "id_rsa",
    "Read(~/claude-settings-backup/**)": "~/claude-settings-backup/s.json",
    # 【LES】data/ のサンプルは置き場所の規則でしか止まらない形（拡張子で止まる data/clients.db にしない）
    "Read(./data/**)": "data/scenarios/a.yaml",  # 【LES】
    "Read(./.claude/settings.local.json)": ".claude/settings.local.json",  # 【LES】
    "Read(**/*.db)": "a/b/x.db",  # 【LES】
    "Read(**/*.sqlite*)": "x.sqlite3",  # 【LES】
    "Read(**/*.xlsx)": "out/x.xlsx",  # 【LES】
    "Read(~/.config/**/clients.db)": "~/.config/x/clients.db",  # 【LES】
}


class TestRepositoryIntegration:
    """settings.json の deny と guard の守備範囲がずれないこと"""

    def test_every_read_deny_is_covered(self):
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        read_denies = {rule for rule in settings["permissions"]["deny"] if rule.startswith("Read(")}
        assert read_denies == set(DENY_SAMPLES), "deny の Read 規則と DENY_SAMPLES がずれています"
        for rule, sample in DENY_SAMPLES.items():
            result = _hook().check_command(f"cat {sample}", str(REPO_ROOT))  # 【LES】本番の main と同じく project_dir を渡す
            assert result, f"{rule} の代表例 {sample!r} を guard が止めません"

    def test_settings_wires_guard(self):
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        groups = settings["hooks"]["PreToolUse"]
        bash_hooks = [h for g in groups if g.get("matcher") == "Bash" for h in g["hooks"]]
        # 辞書の完全一致にしない: 将来 statusMessage などが足されても配線の意味は変わらないため
        guard_hooks = [h for h in bash_hooks if h.get("type") == "command" and h.get("command") == EXPECTED_COMMAND]
        assert guard_hooks, "PreToolUse の matcher Bash に guard.py が配線されていません"
        # 判定は文字列処理だけで速い。長すぎる待ちは止まったときに作業を固めるので 10 秒に揃える
        assert all(h.get("timeout") == 10 for h in guard_hooks)
        # guard の追加で既存の Edit|Write のフック（FP 未確認の警告）を消していないこと  # 【LES】
        edit_write = [g for g in groups if g.get("matcher") == "Edit|Write"]
        assert edit_write, "既存の Edit|Write グループが消えています"
        assert any("pre_tool_fp_warning.py" in h["command"] for g in edit_write for h in g["hooks"])  # 【LES】

    # --- 【LES】ここから（仕様 4節）---

    def test_deny_exception_is_also_allowed_by_guard(self):
        # 決定3の例外（frontend/.env.development を読んでよい）が deny と guard でそろっていること
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        assert "Read(**/.env.development*)" not in settings["permissions"]["deny"]
        assert _hook().check_command("cat frontend/.env.development") is None

    # --- 【LES】ここまで ---

    # --- 【LES】ここから（編集フックの配線。docs/design/test_spec_edit_hooks.md の G1〜G4）---
    # 仕様が「deny とテストの表を一致させるテストとまとめて書く」と決めているので、
    # settings.json を読むテストはこのクラスに集める（フックごとのファイルに散らさない）

    RUN_TESTS_COMMAND = 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/post_tool_run_tests.py'
    FP_WARNING_COMMAND = 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/pre_tool_fp_warning.py'

    @staticmethod
    def _command_hooks(event, matcher, command):
        """settings の hooks.<event> のうち、matcher が一致するグループで command が一致する hook の一覧"""
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        groups = settings["hooks"].get(event, [])
        return [
            h
            for g in groups
            if g.get("matcher") == matcher
            for h in g["hooks"]
            # 辞書の完全一致にしない（test_settings_wires_guard と同じ理由）
            if h.get("type") == "command" and h.get("command") == command
        ]

    def test_settings_wires_run_tests_hook(self):
        # G1
        command = self.RUN_TESTS_COMMAND
        assert self._command_hooks("PostToolUse", "Edit|Write", command), (
            "PostToolUse の matcher Edit|Write に post_tool_run_tests.py が配線されていません"
        )

    def test_settings_wires_fp_warning_hook(self):
        # G2
        command = self.FP_WARNING_COMMAND
        assert self._command_hooks("PreToolUse", "Edit|Write", command), (
            "PreToolUse の matcher Edit|Write に pre_tool_fp_warning.py が配線されていません"
        )

    def test_settings_hooks_have_no_absolute_path_or_unset_env(self):
        # G3: 絶対パスは別の場所に clone すると動かない。CLAUDE_TOOL_INPUT_FILE_PATH は Claude Code が渡さない
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        hooks_text = json.dumps(settings["hooks"], ensure_ascii=False)
        assert "/home/" not in hooks_text, "hooks に絶対パス /home/… が残っています"
        assert "CLAUDE_TOOL_INPUT_FILE_PATH" not in hooks_text, "hooks に渡されない環境変数 CLAUDE_TOOL_INPUT_FILE_PATH が残っています"

    def test_settings_run_tests_hook_timeout_outlasts_script(self):
        # G4: スクリプト側の時間制限が先に切れ、理由（C11）を返せるようにする
        command = self.RUN_TESTS_COMMAND
        run_tests_hooks = self._command_hooks("PostToolUse", "Edit|Write", command)
        assert run_tests_hooks, "PostToolUse の matcher Edit|Write に post_tool_run_tests.py が配線されていません"
        script_timeout = load_hook("post_tool_run_tests").TIMEOUT_SECONDS
        for h in run_tests_hooks:
            assert isinstance(h.get("timeout"), (int, float)), "テスト実行フックに timeout が設定されていません"
            assert h["timeout"] > script_timeout, (
                f"テスト実行フックの timeout（{h['timeout']}）がスクリプトの時間制限（{script_timeout}）以下です"
            )
            assert h["timeout"] == 180  # 運営者の決定3（docs/design/test_spec_edit_hooks.md）

    # --- 【LES】ここまで ---
