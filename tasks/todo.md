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

### フェーズ4.5: クライアント永続化・管理UI・デスクトップアプリ化 【コミット済み 2026-06-17】

Phase 1: クライアントデータ永続化（8bf20f5）

- [x] src/db/models.py・client_repository.py・sqlite_repository.py（SQLAlchemy + Repository パターン）
- [x] src/api/routes/clients.py（CRUD: GET/POST/PUT/DELETE /clients）
- [x] src/api/dependencies.py・schemas.py 拡張
- [x] tests/db/・tests/api/test_clients.py
- [x] docs/design/ep4.5_client_persistence_design.md・_test_spec.md

Phase 2: クライアント管理 UI（3097602）

- [x] frontend ClientManager/SaveDialog コンポーネント・useClients hook
- [x] 選択ドロップダウン・保存・名前を付けて保存・削除（key-based remount でフォーム復元）
- [x] frontend テスト（ClientManager・useClients・clientCrud）
- [x] docs/design/ep4.5_frontend_design.md・_test_spec.md

Phase 3: Electron デスクトップアプリ化（bed2b87）

- [x] PyInstaller で FastAPI を実行ファイル化（api-server.spec）
- [x] electron/（main.js・preload.js・builder.config.js）— 空きポート自動確保・API 自動起動/停止
- [x] Windows NSIS インストーラー対応
- [x] docs/design/ep4.5_electron_design.md

- [ ] ep4.5 全テストのパス確認（テストコードは存在。実行確認は tasks 未記録）
- [x] WSL2 での実機ビルド確認（2026-06-20）。ビルド時に3つの実バグを修正：
      ① api-server.spec に exclude_binaries 欠落（onedir 衝突）
      ② main.py が凍結時も reload=True でプロセス無限増殖
      ③ electron/package.json で electron が dependencies（builder 停止）
      → api-server EXE は /health=200 を確認。AppImage(185MB)・snap(156MB) 生成、
        resources に api-server・frontend 同梱を確認
- [ ] Electron GUI の起動・操作確認（WSLg 対話セッションでユーザーが実施予定。
      起動: output/electron-dist/ライフイベント家計シミュレーター-1.0.0.AppImage）
