"""ライフイベント家計シミュレーター エントリーポイント"""

import sys
from pathlib import Path

from src.domain.cashflow import simulate
from src.input.validator import validate
from src.input.yaml_loader import load_scenario
from src.output.excel_writer import write_excel


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方法: python -m src.main <scenario.yaml>", file=sys.stderr)
        sys.exit(1)

    yaml_path = Path(sys.argv[1])

    try:
        scenario = load_scenario(yaml_path)
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"YAMLの読み込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        validate(scenario)
    except ValueError as e:
        print(f"入力エラー: {e}", file=sys.stderr)
        sys.exit(1)

    rows = simulate(scenario)
    output_path = write_excel(scenario, rows)
    print(f"Excelファイルを生成しました: {output_path}")


if __name__ == "__main__":
    main()
