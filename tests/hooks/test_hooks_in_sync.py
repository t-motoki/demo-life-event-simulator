"""2つのフックに同じ形で持つ共通の関数が、一字一句同じであることのテスト

各フックは1ファイルで完結させる（共有モジュールを import すると、それが壊れたとき
2フックとも exit 1 で落ち、fail-open を守れない）。代わりに同じ関数を2か所に持つので、
片方だけ直すずれをここで止める。設計: docs/design/edit_hooks.md「設計の要点2」
"""

import inspect

import pytest

SHARED_FUNCTIONS = ["read_file_path", "get_project_dir", "is_under", "emit"]


@pytest.mark.parametrize("name", SHARED_FUNCTIONS)
def test_共通の関数は2つのフックで同じ(post_hook, fp_hook, name):
    assert inspect.getsource(getattr(post_hook, name)) == inspect.getsource(getattr(fp_hook, name))
