"""テスト実行フック（.claude/hooks/post_tool_run_tests.py）のテスト

仕様: docs/design/test_spec_edit_hooks.md（A・B・C・E）
設計: docs/design/edit_hooks.md

本物の pytest は走らせない（時間がかかる上に、このテスト自身を再帰して走らせる）。
`main(run=...)` に偽の run を渡し、呼ばれたか・どの引数で呼ばれたかを記録する。
環境変数は monkeypatch.setenv ではなく `main(environ=...)` で渡す
（プロセス全体の環境を書き換えず、開発者の環境にも左右されないため）。
"""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.hooks.conftest import hook_script

# 仕様 C1 の並びを直に書く。定数 PYTEST_ARGS だけと比べると、定数ごと間違えたときに気づけない
EXPECTED_PYTEST_ARGS = ["-m", "pytest", "tests/", "-q", "--tb=short", "-m", "not slow"]


# --- 補助 ---------------------------------------------------------------


def payload(file_path, *, cwd: str | None = None) -> bytes:
    """Claude Code が標準入力に渡す JSON（Edit の PostToolUse）"""
    data = {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path},
        "hook_event_name": "PostToolUse",
    }
    if cwd is not None:
        data["cwd"] = cwd
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def fill(template: str, project: Path) -> str:
    """`{P}` をプロジェクト、`{T}` をプロジェクトの1つ上（プロジェクトの外）に置き換える"""
    return template.replace("{P}", str(project)).replace("{T}", str(project.parent))


class FakeRun:
    """subprocess.run の代わり。呼ばれた引数を記録し、決めた結果を返す（または例外を投げる）"""

    def __init__(self) -> None:
        self.calls: list[tuple[list, dict]] = []
        self.returncode = 0
        self.output = b"1 passed in 0.01s\n"
        self.exc: BaseException | None = None

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        if self.exc is not None:
            raise self.exc
        return subprocess.CompletedProcess(args, self.returncode, stdout=self.output)


class ExplodingStdin(io.BytesIO):
    """読んだ瞬間に想定外の例外を出す標準入力（B9）"""

    def read(self, *args, **kwargs):
        raise RuntimeError("想定外")


@pytest.fixture
def fake_run() -> FakeRun:
    return FakeRun()


@pytest.fixture
def venv_project(project: Path) -> Path:
    """`.venv/bin/python` を置いたプロジェクト。偽の run を渡すので中身は空でよい"""
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    return project


def call(hook, raw: bytes, environ: dict, run) -> tuple[int, bytes]:
    out = io.BytesIO()
    rc = hook.main(stdin=io.BytesIO(raw), stdout=out, environ=environ, run=run)
    return rc, out.getvalue()


def env_for(project: Path) -> dict:
    return {"CLAUDE_PROJECT_DIR": str(project)}


def context_of(out: bytes) -> str:
    """標準出力が JSON 1つだけで、PostToolUse の形であることを確かめて additionalContext を返す（E1・E2）"""
    # json.loads は前後に余計な文字（pytest の生の出力など）があると失敗する
    data = json.loads(out.decode("utf-8"))
    assert set(data) == {"hookSpecificOutput"}
    inner = data["hookSpecificOutput"]
    assert set(inner) == {"hookEventName", "additionalContext"}
    assert inner["hookEventName"] == "PostToolUse"
    assert isinstance(inner["additionalContext"], str)
    return inner["additionalContext"]


def run_with(post_hook, project: Path, fake_run: FakeRun) -> tuple[int, str]:
    """`src/main.py` の編集で発火させ、additionalContext を返す"""
    rc, out = call(post_hook, payload(str(project / "src" / "main.py")), env_for(project), fake_run)
    return rc, context_of(out)


# --- A. どのパスで発火するか ----------------------------------------------


class TestRunTestsPathMatching:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param("{P}/src/main.py", id="A1_src直下"),
            pytest.param("{P}/src/domain/education.py", id="A2_src_domain"),
            pytest.param("{P}/src/domain/sub/x.py", id="A3_src_domainの更に下"),
            pytest.param("{P}/src/output/excel_writer.py", id="A4_srcの別の層"),
            pytest.param("{P}/src/new_file.py", id="A5_まだ無いファイル"),
            pytest.param("{P}/src/README.md", id="A6_py以外"),
            pytest.param("{P}/src/domainx/a.py", id="A11_domainの前方一致"),
            pytest.param("src/domain/x.py", id="A16_相対パス"),
            pytest.param("{P}/tests/../src/x.py", id="A18_ドットドットでsrcに入る"),
            pytest.param("{P}/./src/./domain/x.py", id="A21_ドットを含む"),
        ],
    )
    def test_src配下のパスなら発火する(self, post_hook, venv_project, fake_run, template):
        rc, out = call(post_hook, payload(fill(template, venv_project)), env_for(venv_project), fake_run)

        assert rc == 0
        assert len(fake_run.calls) == 1
        context_of(out)

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param("{P}/tests/domain/test_x.py", id="A7_tests下"),
            pytest.param("{P}/docs/spec/01_requirements.md", id="A8_srcの外"),
            pytest.param("{P}/frontend/src/App.tsx", id="A9_frontend_src"),
            pytest.param("{P}/srcx/a.py", id="A10_srcx"),
            pytest.param("{P}/src_old/a.py", id="A10_src_old"),
            pytest.param("{P}/src", id="A12_srcそのもの"),
            pytest.param("{P}/.claude/worktrees/w1/src/main.py", id="A13_worktree"),
            pytest.param("{T}/other/repo/src/main.py", id="A14_プロジェクト外"),
            pytest.param("{P}-old/src/main.py", id="A15_プロジェクトの前方一致"),
            pytest.param("{P}/src/../tests/x.py", id="A19_ドットドットでsrcから出る"),
            pytest.param("src/../../other/src/x.py", id="A20_ドットドットでプロジェクト外"),
            pytest.param("{P}/SRC/x.py", id="A23_大文字"),
        ],
    )
    def test_src配下でないパスなら発火しない(self, post_hook, venv_project, fake_run, template):
        rc, out = call(post_hook, payload(fill(template, venv_project)), env_for(venv_project), fake_run)

        assert rc == 0
        assert out == b""
        assert fake_run.calls == []

    def test_相対パスは作業ディレクトリでなくプロジェクト基準で判定する(
        self, post_hook, venv_project, fake_run, monkeypatch
    ):
        # A17: 作業ディレクトリ基準で解決すると elsewhere/src/x.py になり発火しない
        elsewhere = venv_project.parent / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        rc, out = call(post_hook, payload("src/x.py"), env_for(venv_project), fake_run)

        assert rc == 0
        assert len(fake_run.calls) == 1

    @pytest.mark.parametrize(
        "env_side, path_side",
        [
            pytest.param("link", "real", id="環境変数はリンク_file_pathは実体"),
            pytest.param("real", "link", id="環境変数は実体_file_pathはリンク"),
        ],
    )
    def test_シンボリックリンク経由のプロジェクトでも判定できる(
        self, post_hook, tmp_path, fake_run, env_side, path_side
    ):
        # A22: 両方を解決して比べていれば、どちら側がリンクでも発火する
        real = tmp_path / "real"
        (real / ".venv" / "bin").mkdir(parents=True)
        (real / ".venv" / "bin" / "python").touch()
        link = tmp_path / "link"
        os.symlink(real, link)
        sides = {"real": real, "link": link}

        rc, out = call(
            post_hook,
            payload(str(sides[path_side] / "src" / "main.py")),
            {"CLAUDE_PROJECT_DIR": str(sides[env_side])},
            fake_run,
        )

        assert rc == 0
        assert len(fake_run.calls) == 1

    @pytest.mark.parametrize(
        "tool_input",
        [
            pytest.param({}, id="A24_file_pathキーが無い"),
            pytest.param({"file_path": ""}, id="A25_空文字"),
            pytest.param({"file_path": "   "}, id="A25_空白だけ"),
            pytest.param({"file_path": None}, id="A26_null"),
            pytest.param({"file_path": 1}, id="A26_数値"),
            pytest.param({"file_path": ["src/x.py"]}, id="A26_配列"),
        ],
    )
    def test_file_pathが無いか空か文字列でなければ何もしない(
        self, post_hook, venv_project, fake_run, tool_input
    ):
        # 空文字を Path にすると「.」＝プロジェクト自身になる。それを src 配下と取り違えないこと
        raw = json.dumps({"tool_name": "Edit", "tool_input": tool_input}).encode("utf-8")

        rc, out = call(post_hook, raw, env_for(venv_project), fake_run)

        assert rc == 0
        assert out == b""
        assert fake_run.calls == []


# --- B. 壊れた入力・環境（fail-open） -------------------------------------


class TestRunTestsFailOpen:
    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param(b"not json", id="B1_JSONでない"),
            pytest.param(b"", id="B2_空"),
            pytest.param(b"[]", id="B3_配列"),
            pytest.param(b'"x"', id="B3_文字列"),
            pytest.param(b"null", id="B3_null"),
            pytest.param(b'{"tool_name": "Edit"}', id="B4_tool_inputが無い"),
            pytest.param(b'{"tool_input": "src/x.py"}', id="B5_tool_inputが文字列"),
            pytest.param(b'{"tool_input": null}', id="B5_tool_inputがnull"),
        ],
    )
    def test_壊れた標準入力なら何もせずexit0(self, post_hook, venv_project, fake_run, raw, capsys):
        rc, out = call(post_hook, raw, env_for(venv_project), fake_run)

        assert rc == 0
        assert out == b""
        assert fake_run.calls == []
        assert "Traceback" not in capsys.readouterr().err

    @pytest.mark.parametrize(
        "make_environ, chdir_to_parent",
        [
            pytest.param(lambda p: {}, False, id="B6_無い"),
            pytest.param(lambda p: {"CLAUDE_PROJECT_DIR": ""}, False, id="B7_空文字"),
            # 作業ディレクトリ（プロジェクトの1つ上）基準で解決すればプロジェクトに届く
            # 相対パスにして、「相対パスを解決していない」ことまで確かめる
            pytest.param(lambda p: {"CLAUDE_PROJECT_DIR": p.name}, True, id="B7a_相対パス"),
        ],
    )
    def test_CLAUDE_PROJECT_DIRが無いか空か相対パスなら何もしない(
        self, post_hook, venv_project, fake_run, monkeypatch, make_environ, chdir_to_parent
    ):
        # JSON の cwd はプロジェクトを指し、作業ディレクトリも代用すれば発火する場所に置く。
        # 代用していれば発火してしまうので、代用していないことが確かめられる
        monkeypatch.chdir(venv_project.parent if chdir_to_parent else venv_project)
        raw = payload(str(venv_project / "src" / "main.py"), cwd=str(venv_project))

        rc, out = call(post_hook, raw, make_environ(venv_project), fake_run)

        assert rc == 0
        assert out == b""
        assert fake_run.calls == []

    def test_日本語のパスを判定できる(self, post_hook, venv_project, fake_run):
        # B8: 標準入力をロケール依存のテキストで読むと日本語のパスが化ける
        rc, out = call(
            post_hook, payload(str(venv_project / "src" / "domain" / "住宅.py")), env_for(venv_project), fake_run
        )

        assert rc == 0
        assert len(fake_run.calls) == 1

    def test_想定外の例外でもexit0_標準入力(self, post_hook, venv_project, fake_run, capsys):
        out = io.BytesIO()

        rc = post_hook.main(stdin=ExplodingStdin(), stdout=out, environ=env_for(venv_project), run=fake_run)

        assert rc == 0
        assert out.getvalue() == b""
        assert "Traceback" not in capsys.readouterr().err

    def test_想定外の例外でもexit0_pytestの起動(self, post_hook, venv_project, fake_run, capsys):
        # RuntimeError は OSError（C10）でも TimeoutExpired（C11）でもない、想定外の例外
        fake_run.exc = RuntimeError("想定外")

        rc, out = call(post_hook, payload(str(venv_project / "src" / "main.py")), env_for(venv_project), fake_run)

        assert rc == 0
        assert out == b""
        assert "Traceback" not in capsys.readouterr().err


# --- C・E. pytest の結果ごとに何を返すか -----------------------------------


class TestRunTestsResult:
    def test_venvのpythonで決めた引数とプロジェクトを作業ディレクトリにして実行する(
        self, post_hook, venv_project, fake_run
    ):
        run_with(post_hook, venv_project, fake_run)

        assert len(fake_run.calls) == 1
        args, kwargs = fake_run.calls[0]
        python = str(venv_project / ".venv" / "bin" / "python")
        assert args == [python, *EXPECTED_PYTEST_ARGS]
        assert args == [python, *post_hook.PYTEST_ARGS]
        assert Path(kwargs["cwd"]) == venv_project
        # C15: フックの標準入力を pytest に渡さない
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["timeout"] == post_hook.TIMEOUT_SECONDS
        # shell=True だと `not slow` が2語に割れる
        assert not kwargs.get("shell", False)

    def test_成功したら要約行をPostToolUseのadditionalContextで返す(self, post_hook, venv_project, fake_run):
        fake_run.output = b"..........\n...........  [100%]\n210 passed, 3 deselected in 6.41s\n"

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_PASSED)
        assert "210 passed, 3 deselected in 6.41s" in context
        # 成功時は全出力を入れない（文脈を無駄に使わない）
        assert "[100%]" not in context

    def test_失敗したら失敗したテスト名と要約行を返す(self, post_hook, venv_project, fake_run):
        fake_run.returncode = 1
        fake_run.output = (
            b"F.........\n"
            b"___ test_a ___\n"
            b"tests/domain/test_x.py:3: in test_a\n"
            b"    assert 1 == 2\n"
            b"E   assert 1 == 2\n"
            b"FAILED tests/domain/test_x.py::test_a - assert 1 == 2\n"
            b"1 failed, 209 passed in 6.00s\n"
        )

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_FAILED)
        assert "FAILED tests/domain/test_x.py::test_a" in context
        assert "1 failed, 209 passed" in context
        assert "E   assert 1 == 2" in context
        assert post_hook.HEADER_PASSED not in context

    def test_長い出力は末尾を残して上限以下に切る(self, post_hook):
        # C4: 組み立てた additionalContext（見出し＋改行＋出力）が上限+1 文字
        limit = post_hook.MAX_CONTEXT_CHARS
        header = "見出し"
        tail = "FAILED tests/x.py::t\n1 failed in 0.1s"
        body = "x" * (limit + 1 - len(header) - 1 - len(tail)) + tail
        assert len(header + "\n" + body) == limit + 1

        result = post_hook.fit_to_limit(header, body, limit)

        assert len(result) <= limit
        assert result.startswith(header)
        assert post_hook.TRUNCATION_NOTICE in result
        assert result.endswith(tail)

    def test_長い出力でもmain経由のadditionalContextは上限以下(self, post_hook, venv_project, fake_run):
        fake_run.returncode = 1
        fake_run.output = (
            b"E   noise\n" * post_hook.MAX_CONTEXT_CHARS
            + b"FAILED tests/domain/test_x.py::test_a\n1 failed, 209 passed in 6.00s\n"
        )

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert len(context) <= post_hook.MAX_CONTEXT_CHARS
        assert context.startswith(post_hook.HEADER_FAILED)
        assert post_hook.TRUNCATION_NOTICE in context
        assert "FAILED tests/domain/test_x.py::test_a" in context
        assert "1 failed, 209 passed in 6.00s" in context

    def test_上限ちょうどの出力は切らない(self, post_hook):
        # C5: 見出しの長さに左右されないよう、切る関数の単位で境界を作る
        limit = post_hook.MAX_CONTEXT_CHARS
        header = "見出し"
        body = "y" * (limit - len(header) - 1)
        assert len(header + "\n" + body) == limit

        result = post_hook.fit_to_limit(header, body, limit)

        assert result == header + "\n" + body
        assert post_hook.TRUNCATION_NOTICE not in result

    @pytest.mark.parametrize("shortfall", [0, 1], ids=["残りがちょうど0", "残りが負"])
    def test_見出しだけで上限に届いても上限を超えない(self, post_hook, shortfall):
        # body[-0:] は空でなく全体を返す。残す文字数が 0 以下の分岐が無いと上限を大きく超える
        header = "見出し"
        prefix = f"{header}\n{post_hook.TRUNCATION_NOTICE}\n"
        limit = len(prefix) - shortfall

        result = post_hook.fit_to_limit(header, "z" * 100, limit)

        assert len(result) <= limit
        assert "z" not in result

    def test_収集エラーは失敗として返す(self, post_hook, venv_project, fake_run):
        fake_run.returncode = 2
        fake_run.output = (
            b"ERROR collecting tests/domain/test_x.py\n"
            b"E   ModuleNotFoundError: No module named 'nope'\n"
            b"1 error in 0.20s\n"
        )

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_COLLECTION_ERROR)
        assert "ModuleNotFoundError: No module named 'nope'" in context
        assert "1 error in 0.20s" in context
        assert post_hook.HEADER_PASSED not in context

    def test_テストが集まらなければ成功扱いにしない(self, post_hook, venv_project, fake_run):
        fake_run.returncode = 5
        fake_run.output = b"no tests ran in 0.01s\n"

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_NO_TESTS)
        assert post_hook.HEADER_PASSED not in context

    @pytest.mark.parametrize("code", [3, 4])
    def test_その他の終了コードは異常終了として返す(self, post_hook, venv_project, fake_run, code):
        fake_run.returncode = code
        fake_run.output = b"INTERNALERROR> boom\n"

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_ABNORMAL.format(code=code))
        assert str(code) in context
        assert "INTERNALERROR> boom" in context
        assert post_hook.HEADER_PASSED not in context

    def test_venvが無ければ実行せず理由を返す(self, post_hook, project, fake_run):
        # C9: project には .venv を置いていない。venv 外の python に代えてもいけない
        rc, context = run_with(post_hook, project, fake_run)

        assert rc == 0
        assert fake_run.calls == []
        assert context.startswith(post_hook.HEADER_NO_VENV)
        assert ".venv/bin/python" in context

    def test_venvのpythonが起動できなければ理由を返す(self, post_hook, venv_project, fake_run):
        python = venv_project / ".venv" / "bin" / "python"
        fake_run.exc = PermissionError(13, "Permission denied", str(python))

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_CANNOT_START.split("{reason}")[0])
        assert post_hook.HEADER_PASSED not in context

    def test_時間切れなら成功扱いにせず時間切れと返す(self, post_hook, venv_project, fake_run):
        # 実際には待たない。subprocess.run と同じく、子プロセスを止めた後の例外を偽物が投げる
        fake_run.exc = subprocess.TimeoutExpired(cmd=["python"], timeout=post_hook.TIMEOUT_SECONDS)

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert context.startswith(post_hook.HEADER_TIMEOUT.format(seconds=post_hook.TIMEOUT_SECONDS))
        assert str(post_hook.TIMEOUT_SECONDS) in context
        assert post_hook.HEADER_PASSED not in context

    def test_日本語と不正なバイトを含む出力でも返せる(self, post_hook, venv_project, fake_run):
        fake_run.returncode = 1
        fake_run.output = (
            "FAILED tests/domain/test_x.py::test_住宅ローン控除は13年目で打ち切られる\n".encode("utf-8")
            + b"\xff\xfe broken\n"
            + b"1 failed in 0.10s\n"
        )

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert "test_住宅ローン控除は13年目で打ち切られる" in context
        # 不正なバイトは置換文字になる（例外にしない）
        assert "�" in context

    def test_標準エラーの出力も要約に含める(self, post_hook, venv_project, fake_run):
        # 標準エラーは標準出力に合流させる（今の 2>&1 と同じく出た順に並ぶ）。
        # 偽物は合流した後の1本の出力として両方の文字列を返す
        fake_run.returncode = 1
        fake_run.output = b"stderr: DeprecationWarning from plugin\nFAILED tests/x.py::t\n1 failed in 0.1s\n"

        rc, context = run_with(post_hook, venv_project, fake_run)

        _, kwargs = fake_run.calls[0]
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.STDOUT
        assert "stderr: DeprecationWarning from plugin" in context

    def test_引用符やバックスラッシュを含む出力もJSONとして読める(self, post_hook, venv_project, fake_run):
        # E3: 手で JSON を組み立てるとここで壊れる
        tricky = 'E   assert "a\\b" == \'c\'\t終わり'
        fake_run.returncode = 1
        fake_run.output = (tricky + "\nFAILED tests/x.py::t\n1 failed in 0.1s\n").encode("utf-8")

        rc, context = run_with(post_hook, venv_project, fake_run)

        assert rc == 0
        assert tricky in context

    @pytest.mark.parametrize(
        "scenario",
        ["passed", "failed", "no_venv", "cannot_start", "timeout"],
    )
    def test_返す文字列にユーザーのホームのパスを含めない(self, post_hook, project, fake_run, scenario):
        # E6: フックが作る文言だけを見る。偽の pytest の出力には絶対パスを入れない
        # （pytest 自身の出力の絶対パスは書き換えずに渡す決まりなので、混ぜると判定できない）
        if scenario != "no_venv":
            python = project / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.touch()
        if scenario == "failed":
            fake_run.returncode = 1
            fake_run.output = b"FAILED tests/x.py::t\n1 failed in 0.1s\n"
        elif scenario == "cannot_start":
            # str(e) にはファイル名の絶対パスが入る。それを文言に使っていないこと
            fake_run.exc = PermissionError(13, "Permission denied", str(python))
        elif scenario == "timeout":
            fake_run.exc = subprocess.TimeoutExpired(cmd=[str(python)], timeout=post_hook.TIMEOUT_SECONDS)

        rc, context = run_with(post_hook, project, fake_run)

        assert rc == 0
        assert str(project) not in context
        assert str(Path.home()) not in context


# --- Claude Code が呼ぶ形で端から端まで ------------------------------------

# 偽の `.venv/bin/python`。受け取った引数と作業ディレクトリを記録し、決めた要約行を出すだけ
FAKE_PYTHON = """\
#!{executable}
import json, os, sys
with open({record!r}, "w", encoding="utf-8") as f:
    json.dump({{"args": sys.argv[1:], "cwd": os.getcwd()}}, f)
print("1 passed in 0.01s")
sys.exit(0)
"""


class TestRunTestsEndToEnd:
    """`sys.executable -I -S` で起動して通れば、標準ライブラリだけで・同じフォルダの
    他のファイルに依存せずに動くことも確かめられる（G5）
    """

    @pytest.fixture
    def e2e(self, project: Path, tmp_path: Path):
        record = tmp_path / "fake_python_record.json"
        python = project / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text(FAKE_PYTHON.format(executable=sys.executable, record=str(record)), encoding="utf-8")
        python.chmod(0o755)
        # 作業ディレクトリはプロジェクト以外（フックが作業ディレクトリに頼っていないことを見る）
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        return project, record, elsewhere

    def _run(self, raw: bytes, project: Path, cwd: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        env["CLAUDE_PROJECT_DIR"] = str(project)
        return subprocess.run(
            [sys.executable, "-I", "-S", str(hook_script("post_tool_run_tests"))],
            input=raw,
            capture_output=True,
            env=env,
            cwd=cwd,
            timeout=60,
        )

    def test_src配下の編集で要約をJSONで返す(self, e2e):
        project, record, elsewhere = e2e

        result = self._run(payload(str(project / "src" / "main.py")), project, elsewhere)

        assert result.returncode == 0
        assert "1 passed in 0.01s" in context_of(result.stdout)
        recorded = json.loads(record.read_text(encoding="utf-8"))
        assert recorded["args"] == EXPECTED_PYTEST_ARGS
        assert Path(recorded["cwd"]).resolve() == project

    def test_JSONでない入力なら何も出さずexit0(self, e2e):
        project, record, elsewhere = e2e

        result = self._run(b"not json", project, elsewhere)

        assert result.returncode == 0
        assert result.stdout == b""
        assert b"Traceback" not in result.stderr
        assert not record.exists()

    def test_frontend_srcの編集ではpytestを呼ばない(self, e2e):
        project, record, elsewhere = e2e

        result = self._run(payload(str(project / "frontend" / "src" / "App.tsx")), project, elsewhere)

        assert result.returncode == 0
        assert result.stdout == b""
        assert not record.exists()
