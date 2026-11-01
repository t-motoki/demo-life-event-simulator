# ライフイベント家計シミュレーター

[![GitHub](https://img.shields.io/badge/GitHub-t--motoki%2Fdemo--life--event--simulator-blue)](https://github.com/t-motoki/demo-life-event-simulator)
[![YouTube](https://img.shields.io/badge/YouTube-ゆる系エンジニアの手記-red)](https://www.youtube.com/channel/UCE1rHqZ5UvXkc0ZBLNiX6bA)
[![X](https://img.shields.io/badge/X-@yumussf-black)](https://x.com/yumussf)

FP（ファイナンシャルプランナー）がクライアントとの面談で使う業務ツール。

ライフイベント（住宅購入・出産・教育・老後など）のタイミングと収入情報を入力すると、年次キャッシュフロー一覧を Excel で出力する。

---

## ステータス

現在のフェーズ: 要件定義完了 / 実装前

- [x] 要件定義 (`docs/spec/01_requirements.md`)
- [ ] 実装
- [ ] テスト・動作確認

このプロジェクトは YouTube チャンネル「ゆる系エンジニアの手記」の ep4.x シリーズと並行して開発しています。制作の過程も動画で公開予定です。

---

## 使い方

（実装後に追記）

---

## データの置き場所

顧客データ（実データのシナリオ・顧客 DB・出力した Excel）は `data/` の下にだけ置きます。`data/` の下は git に入りません（`.gitignore`）。

| 置くもの | 場所 |
| --- | --- |
| 実データのシナリオ | `data/scenarios/`（自分で作る） |
| サンプルのシナリオ | リポジトリ直下の `scenario.yaml`（git 管理） |
| 出力した Excel | `data/output/cf_simulation_YYYYMMDD.xlsx`（無ければ自動で作る） |
| 顧客 DB（開発時の API サーバー） | `data/clients.db`（無ければ自動で作る。環境変数 `LES_DB_PATH` で変えられる） |
| 顧客 DB（デスクトップアプリ版） | アプリのデータフォルダ（Electron の `userData`）の `clients.db` |

`data/scenarios/` などに置くファイルの名前に、顧客の名前を使わないでください（ファイル名は `ls` などで会話や画面に出るため）。

コマンドは**リポジトリ直下で実行**します。相対パスは実行した場所（作業ディレクトリ）を基準にするためです。

```bash
# 実データのシナリオの置き場を作る（初回だけ）
mkdir -p data/scenarios

# 実データのシナリオから Excel を出力する
python -m src.main data/scenarios/<名前>.yaml

# サンプルで試す（出力先は同じ data/output/）
python -m src.main scenario.yaml
```

---

## セットアップ（Windows）

[docs/guides/setup-windows.md](docs/guides/setup-windows.md) を参照してください。

Python インストールからツールの起動まで、ターミナル未経験者向けに手順を説明しています。

---

## 要件

[docs/spec/01_requirements.md](docs/spec/01_requirements.md) を参照してください。

入力・計算・出力・Excel フォーマットの仕様、および FP との確認事項（計算モデルの前提）をまとめています。

---

## 技術スタック

- Python 3.10 以上
- `openpyxl`（Excel 出力）
- 外部 API 通信なし・スタンドアロン動作

---

## 開発方針

- 計算モデル（何を計算するか・何を除外するか）は FP 実務の判断に基づく
- 実装者が勝手に決めない。判断が必要な場面では必ず確認を取る
- クライアント情報を扱うためクラウド不使用・ローカル完結

---

## ライセンス

MIT
