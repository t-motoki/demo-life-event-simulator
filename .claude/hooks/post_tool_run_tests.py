"""テスト実行フック（PostToolUse・matcher `Edit|Write`）

Claude Code から `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/post_tool_run_tests.py` で呼ばれる。
`src/` 配下を編集した直後に `.venv` の pytest（slow を除く）を走らせ、結果の要約を
additionalContext で Claude に届ける。

fail-open である理由: このフックは「気づかせる」ためのもので、止める仕組みではない。
編集はもう済んでいるので、テストが落ちても・入力が壊れていても終了コードは 0 にする。

標準ライブラリだけで書き、同じフォルダの他のファイルを import しない
（配線は venv 外の python3 で起動し、import の失敗は try の外で起きて fail-open を破るため）。
仕様: docs/design/test_spec_edit_hooks.md　設計: docs/design/edit_hooks.md
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import BinaryIO

HOOK_EVENT = "PostToolUse"
TARGET_PARTS = ("src",)
VENV_PYTHON = Path(".venv") / "bin" / "python"  # プロジェクト基準
# `not slow` は1引数のまま渡す（shell を通さない）
PYTEST_ARGS = ("-m", "pytest", "tests/", "-q", "--tb=short", "-m", "not slow")
TIMEOUT_SECONDS = 120  # settings の timeout（180）より短くし、こちらが先に切れて理由を返せるようにする
MAX_CONTEXT_CHARS = 8_000
TRUNCATION_NOTICE = "（出力が長いため先頭を省略した）"

HEADER_PASSED = "pytest: テストは成功した"
HEADER_FAILED = "pytest: テストが失敗した"
HEADER_COLLECTION_ERROR = "pytest: テストの収集でエラーになった（import エラーなど）。失敗として扱う"
HEADER_NO_TESTS = "pytest: テストが見つからなかった（1件も走っていない）"
HEADER_ABNORMAL = "pytest が異常終了した（終了コード {code}）"
HEADER_TIMEOUT = "pytest: {seconds} 秒で時間切れになり、テストは最後まで走っていない"
HEADER_NO_VENV = (
    "pytest: .venv/bin/python が見つからないのでテストを実行していない"
    "（作り方: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt）"
)
HEADER_CANNOT_START = "pytest: .venv/bin/python を起動できなかったのでテストを実行していない（{reason}）"

Runner = Callable[..., "subprocess.CompletedProcess[bytes]"]


# --- 2つのフックで同じ関数（tests/hooks/test_hooks_in_sync.py で一致を確かめている） ---


def read_file_path(raw: bytes) -> str | None:
    """標準入力の JSON から `tool_input.file_path` を取り出す。使えなければ None

    もう一方のフックにも同じ関数がある（tests/hooks/test_hooks_in_sync.py で一致を確かめている）。
    バイト列を UTF-8 で解くのは、テキストで読むとロケール次第で日本語のパスが化けるため。
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    # 空文字を Path にすると「.」＝プロジェクト自身になるので、判定の前に弾く
    if not isinstance(file_path, str) or not file_path.strip():
        return None
    return file_path


def get_project_dir(environ: Mapping[str, str]) -> Path | None:
    """`CLAUDE_PROJECT_DIR` を解決したパス。無い・空・絶対パスでなければ None

    もう一方のフックにも同じ関数がある（tests/hooks/test_hooks_in_sync.py で一致を確かめている）。
    JSON の cwd や作業ディレクトリで代用しない。サブフォルダのことがあり、
    別の場所の src/ に反応したり別の場所で pytest を走らせたりするため。
    """
    value = environ.get("CLAUDE_PROJECT_DIR", "")
    if not value or not Path(value).is_absolute():
        return None
    return Path(value).resolve()


def is_under(file_path: str, project_dir: Path, parts: tuple[str, ...]) -> bool:
    """`file_path` が `<プロジェクト>/<parts>/` の下にあるか（要素単位で比べる）

    もう一方のフックにも同じ関数がある（tests/hooks/test_hooks_in_sync.py で一致を確かめている）。
    文字列の前方一致では `srcx/` や `<プロジェクト>-old/` を取り違えるので使わない。
    相対パスは作業ディレクトリでなくプロジェクト基準で解決する。
    """
    project = project_dir.resolve()
    path = Path(file_path)
    if not path.is_absolute():
        path = project / path
    try:
        relative = path.resolve().relative_to(project)
    except ValueError:
        return False
    # フォルダそのもの（`src` だけ）は配下に含めない
    return relative.parts[: len(parts)] == parts and len(relative.parts) > len(parts)


def emit(stdout: BinaryIO, event: str, context: str) -> None:
    """Claude に届く形（hookSpecificOutput.additionalContext）の JSON を1つだけ書く

    もう一方のフックにも同じ関数がある（tests/hooks/test_hooks_in_sync.py で一致を確かめている）。
    permissionDecision・decision・continue は入れない（許可の確認を飛ばしたり編集を止めたりするため）。
    """
    output = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}
    stdout.write(json.dumps(output, ensure_ascii=False).encode("utf-8"))
    stdout.flush()


# --- このフックだけの関数 ---


def fit_to_limit(header: str, body: str, limit: int) -> str:
    """見出し＋改行＋本文を、全体で `limit` 文字以下に収める

    切るときは本文の先頭側を落とす。pytest -q の出力は末尾に FAILED の一覧と要約行があり、
    そちらが Claude に要る情報のため。見出しは切らない。
    """
    full = f"{header}\n{body}" if body else header
    if len(full) <= limit:
        return full
    prefix = f"{header}\n{TRUNCATION_NOTICE}\n"
    keep = limit - len(prefix)
    # body[-0:] は空でなく全体を返すので、残す文字数が 0 以下の場合を分けて扱う
    if keep <= 0:
        return prefix[:limit]
    return prefix + body[-keep:]


def summarize(returncode: int, output: str) -> str:
    """pytest の終了コードと出力から、Claude に返す文言を作る"""
    lines = [line for line in output.rstrip().splitlines() if line.strip()]
    summary_line = lines[-1] if lines else ""
    if returncode == 0:
        # 成功時は要約行だけ。全出力を入れても文脈を無駄に使うだけなので
        return f"{HEADER_PASSED}\n{summary_line}" if summary_line else HEADER_PASSED
    if returncode == 1:
        header = HEADER_FAILED
    elif returncode == 2:
        header = HEADER_COLLECTION_ERROR
    elif returncode == 5:
        # 1件も走っていないのを成功と取り違えないよう、別の見出しにする
        header = HEADER_NO_TESTS
    else:
        header = HEADER_ABNORMAL.format(code=returncode)
    return fit_to_limit(header, output.rstrip(), MAX_CONTEXT_CHARS)


def run_pytest(project_dir: Path, run: Runner) -> str:
    """`.venv` の pytest を走らせ、返す additionalContext を作る（project_dir は解決済み）"""
    # resolve() しない。.venv/bin/python は venv 外の Python へのリンクで、
    # 解決して起動すると venv の外の Python になり依存が揃わない
    python = project_dir / VENV_PYTHON
    if not python.exists():
        # venv 外の python3 に代えない（依存が揃わず、誤った結果を返すため）
        return HEADER_NO_VENV
    try:
        result = run(
            [str(python), *PYTEST_ARGS],
            cwd=project_dir,
            # フックの標準入力を渡すと、pytest 側が標準入力を待って止まりうる
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            # 標準エラーも合流させる（出た順に並ぶ）
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run は子プロセスを kill してから例外を投げる
        return HEADER_TIMEOUT.format(seconds=TIMEOUT_SECONDS)
    except OSError as e:
        # str(e) はファイル名の絶対パスを含むので使わない（ホームのパスを返さない）
        return HEADER_CANNOT_START.format(reason=e.strerror or type(e).__name__)
    output = (result.stdout or b"").decode("utf-8", errors="replace")
    return summarize(result.returncode, output)


def build_context(raw: bytes, environ: Mapping[str, str], run: Runner) -> str | None:
    """返す additionalContext か、何も返さないなら None"""
    file_path = read_file_path(raw)
    if file_path is None:
        return None
    project_dir = get_project_dir(environ)
    if project_dir is None:
        return None
    # 対象外なら pytest を実行しない
    if not is_under(file_path, project_dir, TARGET_PARTS):
        return None
    return run_pytest(project_dir, run)


def main(
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    environ: Mapping[str, str] | None = None,
    run: Runner | None = None,
) -> int:
    try:
        # 本番の値の取り出しも try の内側で行う（標準入力が閉じている等でも exit 0 にするため）
        stdin = sys.stdin.buffer if stdin is None else stdin
        stdout = sys.stdout.buffer if stdout is None else stdout
        environ = os.environ if environ is None else environ
        run = subprocess.run if run is None else run
        context = build_context(stdin.read(), environ, run)
        if context is not None:
            emit(stdout, HOOK_EVENT, context)
    except Exception as e:
        # トレースバックは出さない。exit 0 の標準エラーは Claude に届かず作業も止めない
        try:
            sys.stderr.write(f"post_tool_run_tests: {type(e).__name__}\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
