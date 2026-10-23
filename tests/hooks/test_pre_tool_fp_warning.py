"""FP 未確認の警告フック（.claude/hooks/pre_tool_fp_warning.py）のテスト

仕様: docs/design/test_spec_edit_hooks.md（A・B・D・E）
設計: docs/design/edit_hooks.md

要件定義書はテストごとに一時フォルダのプロジェクトへ書く。本物の
docs/spec/01_requirements.md には今マーカーが無いので、本物を使うと警告の場合が書けない。
環境変数は monkeypatch.setenv ではなく `main(environ=...)` で渡す。
"""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.hooks.conftest import hook_script

# 回帰防止のため、定数を参照せず文字列そのものと比べる（E5。一字も変えない）
WARNING_MESSAGE = (
    "警告: docs/spec/01_requirements.md に FP未確認事項が残っています。"
    "/fp-check で確認してから実装を進めてください。"
)
MARKER_TEXT = "# 要件定義\n\n| 項目 | 状態 |\n|---|---|\n| 育休 | TODO: FPに確認 |\n"


# --- 補助 ---------------------------------------------------------------


def payload(file_path, *, cwd: str | None = None) -> bytes:
    """Claude Code が標準入力に渡す JSON（Edit の PreToolUse）"""
    data = {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path},
        "hook_event_name": "PreToolUse",
    }
    if cwd is not None:
        data["cwd"] = cwd
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def fill(template: str, project: Path) -> str:
    """`{P}` をプロジェクト、`{T}` をプロジェクトの1つ上（プロジェクトの外）に置き換える"""
    return template.replace("{P}", str(project)).replace("{T}", str(project.parent))


def write_requirements(project: Path, content: str | bytes) -> Path:
    path = project / "docs" / "spec" / "01_requirements.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


class ExplodingStdin(io.BytesIO):
    """読んだ瞬間に想定外の例外を出す標準入力（B9）"""

    def read(self, *args, **kwargs):
        raise RuntimeError("想定外")


def call(hook, raw: bytes, environ: dict) -> tuple[int, bytes]:
    out = io.BytesIO()
    rc = hook.main(stdin=io.BytesIO(raw), stdout=out, environ=environ)
    return rc, out.getvalue()


def env_for(project: Path) -> dict:
    return {"CLAUDE_PROJECT_DIR": str(project)}


def context_of(out: bytes) -> str:
    """標準出力が JSON 1つだけで、PreToolUse の形であることを確かめて additionalContext を返す（E1・E2）"""
    data = json.loads(out.decode("utf-8"))
    assert set(data) == {"hookSpecificOutput"}
    inner = data["hookSpecificOutput"]
    assert set(inner) == {"hookEventName", "additionalContext"}
    assert inner["hookEventName"] == "PreToolUse"
    return inner["additionalContext"]


@pytest.fixture
def marked_project(project: Path) -> Path:
    """要件定義書にマーカーがあるプロジェクト（警告が出る状態）"""
    write_requirements(project, MARKER_TEXT)
    return project


def domain_edit(project: Path) -> bytes:
    return payload(str(project / "src" / "domain" / "x.py"))


# --- A. どのパスで警告するか ----------------------------------------------


class TestFpWarningPathMatching:
    @pytest.mark.parametrize(
        "template",
        [
            pytest.param("{P}/src/domain/education.py", id="A2_src_domain"),
            pytest.param("{P}/src/domain/sub/x.py", id="A3_src_domainの更に下"),
            pytest.param("src/domain/x.py", id="A16_相対パス"),
            pytest.param("{P}/./src/./domain/x.py", id="A21_ドットを含む"),
        ],
    )
    def test_src_domain配下なら警告する(self, fp_hook, marked_project, template):
        rc, out = call(fp_hook, payload(fill(template, marked_project)), env_for(marked_project))

        assert rc == 0
        assert context_of(out) == WARNING_MESSAGE

    @pytest.mark.parametrize(
        "template",
        [
            pytest.param("{P}/src/main.py", id="A1_src直下"),
            pytest.param("{P}/src/output/excel_writer.py", id="A4_srcの別の層"),
            pytest.param("{P}/tests/domain/test_x.py", id="A7_tests下"),
            pytest.param("{P}/docs/spec/01_requirements.md", id="A8_srcの外"),
            pytest.param("{P}/frontend/src/App.tsx", id="A9_frontend_src"),
            pytest.param("{P}/srcx/a.py", id="A10_srcx"),
            pytest.param("{P}/src_old/a.py", id="A10_src_old"),
            pytest.param("{P}/src/domainx/a.py", id="A11_domainの前方一致"),
            pytest.param("{P}/src", id="A12_srcそのもの"),
            pytest.param("{P}/src/domain", id="A12相当_src_domainそのもの"),
            pytest.param("{P}/.claude/worktrees/w1/src/domain/x.py", id="A13_worktree"),
            pytest.param("{T}/other/repo/src/domain/x.py", id="A14_プロジェクト外"),
            pytest.param("{P}-old/src/domain/x.py", id="A15_プロジェクトの前方一致"),
            pytest.param("{P}/src/domain/../../tests/x.py", id="A19_ドットドットでsrcから出る"),
            pytest.param("src/../../other/src/domain/x.py", id="A20_ドットドットでプロジェクト外"),
            pytest.param("{P}/SRC/domain/x.py", id="A23_大文字"),
        ],
    )
    def test_src_domain配下でなければ警告しない(self, fp_hook, marked_project, template):
        rc, out = call(fp_hook, payload(fill(template, marked_project)), env_for(marked_project))

        assert rc == 0
        assert out == b""

    @pytest.mark.parametrize(
        "env_side, path_side",
        [
            pytest.param("link", "real", id="環境変数はリンク_file_pathは実体"),
            pytest.param("real", "link", id="環境変数は実体_file_pathはリンク"),
        ],
    )
    def test_シンボリックリンク経由のプロジェクトでも判定できる(self, fp_hook, tmp_path, env_side, path_side):
        # A22: 両方を解決して比べていれば、どちら側がリンクでも警告する
        real = tmp_path / "real"
        real.mkdir()
        write_requirements(real, MARKER_TEXT)
        link = tmp_path / "link"
        os.symlink(real, link)
        sides = {"real": real, "link": link}

        rc, out = call(
            fp_hook,
            payload(str(sides[path_side] / "src" / "domain" / "x.py")),
            {"CLAUDE_PROJECT_DIR": str(sides[env_side])},
        )

        assert rc == 0
        assert context_of(out) == WARNING_MESSAGE

    @pytest.mark.parametrize(
        "tool_input",
        [
            pytest.param({}, id="A24_file_pathキーが無い"),
            pytest.param({"file_path": ""}, id="A25_空文字"),
            pytest.param({"file_path": "   "}, id="A25_空白だけ"),
            pytest.param({"file_path": None}, id="A26_null"),
            pytest.param({"file_path": 1}, id="A26_数値"),
            pytest.param({"file_path": ["src/domain/x.py"]}, id="A26_配列"),
        ],
    )
    def test_file_pathが無いか空か文字列でなければ何もしない(self, fp_hook, marked_project, tool_input):
        raw = json.dumps({"tool_name": "Edit", "tool_input": tool_input}).encode("utf-8")

        rc, out = call(fp_hook, raw, env_for(marked_project))

        assert rc == 0
        assert out == b""

    def test_対象外のパスでは要件定義書を読まない(self, fp_hook, marked_project, monkeypatch):
        # D10: build_context は read_requirements を呼び出しの時点でモジュールから引くので差し替えが効く
        calls = []
        monkeypatch.setattr(fp_hook, "read_requirements", lambda project_dir: calls.append(project_dir))

        rc, out = call(fp_hook, payload(str(marked_project / "src" / "main.py")), env_for(marked_project))

        assert rc == 0
        assert out == b""
        assert calls == []


# --- B. 壊れた入力・環境（fail-open） -------------------------------------


class TestFpWarningFailOpen:
    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param(b"not json", id="B1_JSONでない"),
            pytest.param(b"", id="B2_空"),
            pytest.param(b"[]", id="B3_配列"),
            pytest.param(b'"x"', id="B3_文字列"),
            pytest.param(b"null", id="B3_null"),
            pytest.param(b'{"tool_name": "Edit"}', id="B4_tool_inputが無い"),
            pytest.param(b'{"tool_input": "src/domain/x.py"}', id="B5_tool_inputが文字列"),
            pytest.param(b'{"tool_input": null}', id="B5_tool_inputがnull"),
        ],
    )
    def test_壊れた標準入力なら何もせずexit0(self, fp_hook, marked_project, raw, capsys):
        rc, out = call(fp_hook, raw, env_for(marked_project))

        assert rc == 0
        assert out == b""
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
        self, fp_hook, marked_project, monkeypatch, make_environ, chdir_to_parent
    ):
        # JSON の cwd はプロジェクトを指し、作業ディレクトリも代用すれば警告する場所に置く
        monkeypatch.chdir(marked_project.parent if chdir_to_parent else marked_project)
        raw = payload(str(marked_project / "src" / "domain" / "x.py"), cwd=str(marked_project))

        rc, out = call(fp_hook, raw, make_environ(marked_project))

        assert rc == 0
        assert out == b""

    def test_日本語のパスを判定できる(self, fp_hook, marked_project):
        # B8: 標準入力をロケール依存のテキストで読むと日本語のパスが化ける
        rc, out = call(
            fp_hook, payload(str(marked_project / "src" / "domain" / "住宅.py")), env_for(marked_project)
        )

        assert rc == 0
        assert context_of(out) == WARNING_MESSAGE

    def test_想定外の例外でもexit0_標準入力(self, fp_hook, marked_project, capsys):
        out = io.BytesIO()

        rc = fp_hook.main(stdin=ExplodingStdin(), stdout=out, environ=env_for(marked_project))

        assert rc == 0
        assert out.getvalue() == b""
        assert "Traceback" not in capsys.readouterr().err

    def test_想定外の例外でもexit0_要件定義書の読み取り(self, fp_hook, marked_project, monkeypatch, capsys):
        def explode(project_dir):
            raise RuntimeError("想定外")

        monkeypatch.setattr(fp_hook, "read_requirements", explode)

        rc, out = call(fp_hook, domain_edit(marked_project), env_for(marked_project))

        assert rc == 0
        assert out == b""
        assert "Traceback" not in capsys.readouterr().err


# --- D・E. 要件定義書の状態ごとに何を返すか ---------------------------------


class TestFpWarningMessage:
    def test_マーカーがあればPreToolUseのadditionalContextで警告する(self, fp_hook, marked_project):
        rc, out = call(fp_hook, domain_edit(marked_project), env_for(marked_project))

        assert rc == 0
        assert context_of(out) == WARNING_MESSAGE

    def test_警告文は定数と一致する(self, fp_hook):
        assert fp_hook.WARNING_MESSAGE == WARNING_MESSAGE

    def test_仮値つきのマーカーでも警告する(self, fp_hook, project):
        write_requirements(project, "育休中の収入減率 # TODO: FPに確認（仮値）\n")

        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        assert context_of(out) == WARNING_MESSAGE

    def test_マーカーが複数でも警告は1つ(self, fp_hook, project):
        write_requirements(project, "TODO: FPに確認\nTODO: FPに確認\nTODO: FPに確認（仮値）\n")

        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        context = context_of(out)
        assert context == WARNING_MESSAGE
        assert out.decode("utf-8").count("警告:") == 1

    def test_マーカーが無ければ何も返さない(self, fp_hook, project):
        # D4: 今の LES の状態（未確定事項は § 8 の表で管理され、マーカーは無い）
        write_requirements(project, "# 要件定義\n\n## 8. 未確定事項\n\n| 項目 | 状態 |\n|---|---|\n| 育休 | 未確定 |\n")

        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        assert out == b""

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("TODO：FPに確認\n", id="全角コロン"),
            pytest.param("TODO: FP に確認\n", id="空白入り"),
            pytest.param("todo: FPに確認\n", id="小文字"),
        ],
    )
    def test_表記ゆれはマーカーとみなさない(self, fp_hook, project, text):
        write_requirements(project, text)

        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        assert out == b""

    def test_要件定義書が無ければ何も返さない(self, fp_hook, project):
        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        assert out == b""

    @pytest.mark.parametrize("kind", ["フォルダ", "UTF8でないバイト列"])
    def test_要件定義書が読めなければ何も返さない(self, fp_hook, project, kind, capsys):
        # D7: 権限が無い形は root で走ると再現しないのでテストにしない（同じ OSError の分岐）
        path = project / "docs" / "spec" / "01_requirements.md"
        if kind == "フォルダ":
            path.mkdir(parents=True)
        else:
            # マーカーの前後を UTF-8 として不正なバイトで挟む。読めたことにしてしまうと警告が出る
            write_requirements(project, b"\xff\xfe" + "TODO: FPに確認".encode("utf-8") + b"\x80")

        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        assert out == b""
        assert "Traceback" not in capsys.readouterr().err

    def test_要件定義書が空なら何も返さない(self, fp_hook, project):
        write_requirements(project, "")

        rc, out = call(fp_hook, domain_edit(project), env_for(project))

        assert rc == 0
        assert out == b""

    def test_警告しても編集を止めない(self, fp_hook, marked_project):
        # D9: permissionDecision を返すと許可の確認を飛ばし、decision・continue は編集を止めうる
        rc, out = call(fp_hook, domain_edit(marked_project), env_for(marked_project))

        assert rc == 0
        data = json.loads(out.decode("utf-8"))
        for forbidden in ("permissionDecision", "decision", "continue"):
            assert forbidden not in data
            assert forbidden not in data["hookSpecificOutput"]

    def test_編集中のファイルのマーカーは見ない(self, fp_hook, project):
        # D11: 見るのは要件定義書だけ
        write_requirements(project, "# 要件定義\n")
        target = project / "src" / "domain" / "education.py"
        target.parent.mkdir(parents=True)
        target.write_text("RATE = 0.5  # TODO: FPに確認（仮値）\n", encoding="utf-8")

        rc, out = call(fp_hook, payload(str(target)), env_for(project))

        assert rc == 0
        assert out == b""


# --- Claude Code が呼ぶ形で端から端まで ------------------------------------


class TestFpWarningEndToEnd:
    """`sys.executable -I -S` で起動して通れば、標準ライブラリだけで・同じフォルダの
    他のファイルに依存せずに動くことも確かめられる（G5）
    """

    def _run(self, raw: bytes, project: Path | None, cwd: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project)
        return subprocess.run(
            [sys.executable, "-I", "-S", str(hook_script("pre_tool_fp_warning"))],
            input=raw,
            capture_output=True,
            env=env,
            cwd=cwd,
            timeout=60,
        )

    @pytest.fixture
    def elsewhere(self, tmp_path: Path) -> Path:
        # 作業ディレクトリはプロジェクト以外（フックが作業ディレクトリに頼っていないことを見る）
        path = tmp_path / "elsewhere"
        path.mkdir()
        return path

    def test_マーカーがあればsrc_domainの編集で警告のJSONを返す(self, marked_project, elsewhere):
        result = self._run(domain_edit(marked_project), marked_project, elsewhere)

        assert result.returncode == 0
        assert context_of(result.stdout) == WARNING_MESSAGE

    def test_JSONでない入力なら何も出さずexit0(self, marked_project, elsewhere):
        result = self._run(b"not json", marked_project, elsewhere)

        assert result.returncode == 0
        assert result.stdout == b""
        assert b"Traceback" not in result.stderr

    def test_CLAUDE_PROJECT_DIRが無ければ何も出さずexit0(self, marked_project):
        # 作業ディレクトリをプロジェクトにしておき、代用していないことまで確かめる
        result = self._run(domain_edit(marked_project), None, marked_project)

        assert result.returncode == 0
        assert result.stdout == b""
