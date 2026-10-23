"""`.claude/hooks/` のフックのテスト共通フィクスチャ

`.claude/hooks/` はパッケージではない（フックは Claude Code から
`python3 <ファイル>` で単体起動される1ファイル完結のスクリプト）ので、
import ではなくファイルの場所から読み込む。
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def hook_script(name: str) -> Path:
    """フックのスクリプトのパス。無ければ理由の分かる形でテストを落とす

    スクリプトが無いときに収集エラーで全テストが巻き添えにならないよう、
    fixture の中（テストごと）で確かめる。
    """
    path = HOOKS_DIR / f"{name}.py"
    if not path.is_file():
        pytest.fail(f"フックのスクリプトが無い: .claude/hooks/{name}.py", pytrace=False)
    return path


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"hooks_{name}", hook_script(name))
    module = importlib.util.module_from_spec(spec)
    # sys.modules に登録しない: テスト間で monkeypatch した状態を他のモジュールから見せないため
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def post_hook() -> ModuleType:
    return _load("post_tool_run_tests")


@pytest.fixture(scope="module")
def fp_hook() -> ModuleType:
    return _load("pre_tool_fp_warning")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """`CLAUDE_PROJECT_DIR` として渡すプロジェクトのフォルダ（解決済み）

    tmp_path の直下ではなく1段下に作る。プロジェクトの外（兄弟フォルダ・
    前方一致だけ同じ `<P>-old`）のパスも tmp_path の中に作れるようにするため。
    フックはプロジェクトを resolve() して比べるので、期待値も解決済みのパスで作る
    （tmp_path 自体がシンボリックリンクの下にある環境でも落ちないように）。
    """
    path = tmp_path / "les"
    path.mkdir()
    return path.resolve()
