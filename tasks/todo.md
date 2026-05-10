# タスク

---

## FP確認待ち

### 高優先度（実装ブロッカー）

- [x] **入力インターフェース**: 今バージョンはYAML設定ファイル（`scenario.yaml`）。FPが直接操作できる形式への対応は次バージョン以降（2026-04-07）

### 中優先度

- [ ] **住宅ローンの金利タイプ**: 固定 / 変動 / フラット35 のどれを想定するか
- [ ] **繰り上げ返済**: 考慮するか否か
- [ ] **定年後の再雇用収入**: 比率指定 / 固定額 / 無視 のどれにするか
- [ ] **教育費の標準単価の出典**: 文部科学省調査データ等、どれを使うか
- [ ] **大学院・留学・習い事**: 教育費の別項目として持つか否か
- [ ] **Excelの見た目**: 色・フォント・条件付き書式の仕様
- [ ] **税・社会保険**: 計算に含めるか（含める場合: 概算税率 / 正確計算）

### 低優先度

- [ ] 複数シナリオ対応の優先度（現バージョンのスコープ外）
- [ ] 遺族年金・死亡保険金シナリオを扱うか

---

## 確認済み（実装可）

| 項目 | 決定内容 | 確定日 |
|------|----------|--------|
| インフレ率 | 0%固定（生活費への加算なし） | 2026-04-04 |
| 運用利回り | 0%固定（貯蓄残高への運用益加算なし） | 2026-04-04 |
| 住宅ローン控除の計算方法 | 年末ローン残高の0.7%を年間収支に加算 | 2026-04-07 |
| 住宅ローン控除の期間 | 13年（14年目以降は控除額=0） | 2026-04-07 |
| 年金 | FPが手入力（自動試算なし） | 2026-04-07 |
| 教育費 | 幼稚園〜大学の公立/私立区分ごとの標準単価を使用 | 2026-04-07 |
| 育休中の収入減 | BirthEventに収入減額率（client/spouse）と育休期間（年数）を入力値として持つ。デフォルトは率=1.0・期間=0（取得しない）。育休取得年の収入 = 通常収入 × 減額率。年平均率を入力するため67%/50%の月次分割は不要。 | 2026-04-11 |

---

## 実装タスク

### フェーズ1: コア実装 【完了 2026-04-07】

- [x] src/domain/models.py（データモデル）
- [x] src/domain/loan.py（元利均等返済・住宅ローン控除）
- [x] src/domain/education.py（教育費標準単価・年次計算）
- [x] src/domain/cashflow.py（年次CF計算）
- [x] src/input/yaml_loader.py（YAML → Scenarioオブジェクト）
- [x] src/input/validator.py（入力バリデーション）
- [x] src/output/excel_writer.py（Excel出力・2シート）
- [x] src/main.py（エントリーポイント）
- [x] tests/ 63件全パス
- [x] scenario.yaml（サンプル）
- [x] requirements.txt

実行方法: `python -m src.main scenario.yaml`

### フェーズ4.3: FastAPI + React フロントエンド 【完了 2026-05-10】

- [x] FastAPI バックエンド（POST /simulate 等）
- [x] React + Vite フロントエンド（シミュレーション入力・結果表示）

### フェーズ4.4: 根拠付き出力（クライアントに渡せる形） 【完了 2026-05-10】

- [x] src/domain/cashflow_analysis.py（貯蓄最低値・赤字期間の分析）
- [x] src/output/excel_writer.py 拡張（「前提条件・注釈」第3シート）
- [x] src/output/comment_generator.py（Claude API によるFPコメント生成）
- [x] src/output/pdf_config.py（フォントパス設定）
- [x] src/output/pdf_writer.py（WeasyPrint によるPDF生成）
- [x] src/api/routes/comment.py（POST /generate-comment）
- [x] src/api/routes/pdf.py（POST /download-pdf）
- [x] src/api/schemas.py 拡張
- [x] src/api/main.py 拡張
- [x] フロントエンド PDFダウンロードボタン
- [x] tests/ 161件全パス（2スキップ）
- [ ] 実ブラウザでの AC-4-x 動作確認（未実施）
- [ ] WSL2 環境での WeasyPrint 動作確認（libpango インストール確認）
- [ ] ANTHROPIC_API_KEY 設定確認
