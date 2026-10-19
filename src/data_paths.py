"""顧客データの既定の置き場所。

顧客データ（DB・出力した Excel・実データのシナリオ）は data/ の下にだけ置く。
.gitignore で data/ を除外しているので、git に入れない対象をここ1か所にまとめられる。

相対パスはプロセスの作業ディレクトリ基準（コマンドはリポジトリ直下で実行する前提）。
DB と出力の既定値を同じファイルに置くのは、出力層が API 層を import せずに済むようにするため。
"""

from pathlib import Path

DATA_DIR = Path("data")
DEFAULT_DB_PATH = DATA_DIR / "clients.db"
DEFAULT_OUTPUT_DIR = DATA_DIR / "output"
