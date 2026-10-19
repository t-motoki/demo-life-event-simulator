"""顧客 DB の既定の置き場所のテスト（src/api/dependencies.py）

既定値は作業ディレクトリ基準の相対パスなので、どのテストも作業ディレクトリを
tmp_path に移してから呼ぶ。リポジトリ直下に data/ や clients.db を作らないため。
"""

import pytest

from src.api.dependencies import _get_repository


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path, monkeypatch):
    """作業ディレクトリと Repository のキャッシュをテストごとに切り離す。

    _get_repository は lru_cache で1つを共有する。前で消さないと別のテストの
    Repository が返る。後ろでも消すのは、tmp_path を指す Repository が残ると、
    後で走る API のテストが差し替えなしで /clients を呼んだときに使われるため。
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LES_DB_PATH", raising=False)
    _get_repository.cache_clear()
    yield
    _get_repository.cache_clear()


class TestDefaultDbPath:
    def test_LES_DB_PATH未設定なら_data配下のclients_dbを使う(self, tmp_path):
        repo = _get_repository()
        assert repo.list_all() == []

        assert (tmp_path / "data" / "clients.db").is_file()
        assert not (tmp_path / "clients.db").exists()

    def test_dataフォルダが無くても作って起動できる(self, tmp_path):
        assert not (tmp_path / "data").exists()

        repo = _get_repository()
        repo.list_all()

        assert (tmp_path / "data").is_dir()

    def test_dataフォルダの既存ファイルを消さない(self, tmp_path):
        existing = tmp_path / "data" / "scenarios" / "x.yaml"
        existing.parent.mkdir(parents=True)
        existing.write_text("client: {}\n", encoding="utf-8")

        _get_repository().list_all()

        assert existing.read_text(encoding="utf-8") == "client: {}\n"
        assert (tmp_path / "data" / "clients.db").is_file()

    def test_LES_DB_PATHを明示したらその場所を使う(self, tmp_path, monkeypatch):
        db_path = tmp_path / "userdata" / "clients.db"
        db_path.parent.mkdir()
        monkeypatch.setenv("LES_DB_PATH", str(db_path))

        _get_repository().list_all()

        assert db_path.is_file()
        assert not (tmp_path / "data").exists()

    def test_LES_DB_PATHの親フォルダが無ければ作る(self, tmp_path, monkeypatch):
        db_path = tmp_path / "a" / "b" / "clients.db"
        monkeypatch.setenv("LES_DB_PATH", str(db_path))

        _get_repository().list_all()

        assert db_path.is_file()
        assert not (tmp_path / "data").exists()

    def test_LES_DB_PATHが空文字ならフォルダを作らない(self, tmp_path, monkeypatch):
        # 空文字は sqlite:/// （メモリ DB）になる。今回はこの挙動を変えない（回帰防止）
        monkeypatch.setenv("LES_DB_PATH", "")

        _get_repository().list_all()

        assert list(tmp_path.iterdir()) == []
