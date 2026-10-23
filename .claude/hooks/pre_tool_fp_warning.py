"""FP 未確認の警告フック（PreToolUse・matcher `Edit|Write`）

Claude Code から `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/pre_tool_fp_warning.py` で呼ばれる。
`src/domain/`（計算ロジック）を編集する前に、要件定義書に `TODO: FPに確認` が残っていれば
additionalContext で警告を Claude に届ける。編集は止めない。

fail-open である理由: このフックは「気づかせる」ためのもので、止める仕組みではない。
壊れた入力1つで全ての編集が止まると、守るものが無いのに作業だけが止まる。
そのため、どんな入力・環境でも終了コードは 0 にする。

標準ライブラリだけで書き、同じフォルダの他のファイルを import しない
（配線は venv 外の python3 で起動し、import の失敗は try の外で起きて fail-open を破るため）。
仕様: docs/design/test_spec_edit_hooks.md　設計: docs/design/edit_hooks.md
"""

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import BinaryIO

HOOK_EVENT = "PreToolUse"
TARGET_PARTS = ("src", "domain")
REQUIREMENTS_PATH = Path("docs") / "spec" / "01_requirements.md"  # プロジェクト基準
MARKER = "TODO: FPに確認"
# 一字も変えない（回帰防止。テストが文字列そのものと比べている）
WARNING_MESSAGE = "警告: docs/spec/01_requirements.md に FP未確認事項が残っています。/fp-check で確認してから実装を進めてください。"


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


def read_requirements(project_dir: Path) -> str | None:
    """要件定義書の中身。無い・フォルダ・権限が無い・UTF-8 でなければ None（fail-open）"""
    try:
        return (project_dir / REQUIREMENTS_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def build_context(raw: bytes, environ: Mapping[str, str]) -> str | None:
    """返す警告文か、何も返さないなら None"""
    file_path = read_file_path(raw)
    if file_path is None:
        return None
    project_dir = get_project_dir(environ)
    if project_dir is None:
        return None
    # 対象外なら要件定義書を読まない
    if not is_under(file_path, project_dir, TARGET_PARTS):
        return None
    text = read_requirements(project_dir)
    if text is None or MARKER not in text:
        return None
    return WARNING_MESSAGE


def main(
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    try:
        # 本番の値の取り出しも try の内側で行う（標準入力が閉じている等でも exit 0 にするため）
        stdin = sys.stdin.buffer if stdin is None else stdin
        stdout = sys.stdout.buffer if stdout is None else stdout
        environ = os.environ if environ is None else environ
        context = build_context(stdin.read(), environ)
        if context is not None:
            emit(stdout, HOOK_EVENT, context)
    except Exception as e:
        # トレースバックは出さない。exit 0 の標準エラーは Claude に届かず作業も止めない
        try:
            sys.stderr.write(f"pre_tool_fp_warning: {type(e).__name__}\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
