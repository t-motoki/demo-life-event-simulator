"""CLI（src/main.py）の出力先のテスト

既定の出力先は作業ディレクトリ基準の相対パスなので、作業ディレクトリを
tmp_path に移してから main() を呼ぶ。リポジトリ直下に data/ や xlsx を作らないため。
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

from src.main import main

# chdir の後は相対パスで見えないので、テストファイルの位置から辿る
SAMPLE_SCENARIO = Path(__file__).resolve().parent.parent / "scenario.yaml"


def _expected_output() -> Path:
    return Path("data") / "output" / f"cf_simulation_{datetime.now():%Y%m%d}.xlsx"


class TestMainOutput:
    def test_シナリオを渡すとdata_outputにExcelができる(self, tmp_path, monkeypatch, capsys):
        scenario = tmp_path / "data" / "scenarios" / "s.yaml"
        scenario.parent.mkdir(parents=True)
        shutil.copy(SAMPLE_SCENARIO, scenario)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["src.main", "data/scenarios/s.yaml"])

        main()

        expected = _expected_output()
        assert (tmp_path / expected).is_file()
        assert capsys.readouterr().out.strip() == f"Excelファイルを生成しました: {expected}"

    def test_入力の場所に関係なく出力先はdata_output(self, tmp_path, monkeypatch):
        shutil.copy(SAMPLE_SCENARIO, tmp_path / "scenario.yaml")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["src.main", "scenario.yaml"])

        main()

        assert (tmp_path / _expected_output()).is_file()
        assert list(tmp_path.glob("*.xlsx")) == []

    def test_読み込みに失敗したら出力フォルダを作らない(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["src.main", "missing.yaml"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        assert not (tmp_path / "data").exists()
