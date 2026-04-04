# ライフイベント家計シミュレーター

[![GitHub](https://img.shields.io/badge/GitHub-t--motoki%2Fdemo--life--event--simulator-blue)](https://github.com/t-motoki/demo-life-event-simulator)

FP（ファイナンシャルプランナー）がクライアントとの面談で使う業務ツール。

ライフイベント（住宅購入・出産・教育・老後など）のタイミングと収入情報を入力すると、年次キャッシュフロー一覧を Excel で出力する。

---

## ステータス

現在のフェーズ: 要件定義完了 / 実装前

- [x] 要件定義 (`docs/spec/requirements.md`)
- [ ] 実装
- [ ] テスト・動作確認

このプロジェクトは YouTube チャンネル「ゆる系エンジニアの手記」の ep4.x シリーズと並行して開発しています。制作の過程も動画で公開予定です。

---

## 使い方

（実装後に追記）

---

## セットアップ（Windows）

[docs/guides/setup-windows.md](docs/guides/setup-windows.md) を参照してください。

Python インストールからツールの起動まで、ターミナル未経験者向けに手順を説明しています。

---

## 要件

[docs/spec/requirements.md](docs/spec/requirements.md) を参照してください。

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
