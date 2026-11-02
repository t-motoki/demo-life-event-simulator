# 作業状態

最終更新: 2026-11-03

---

## 取り組み中のフェーズ

開発基盤の安全設定（AI駆動開発設計思想 段階1 の移植）— タスク0.5〜5 完了。残りはタスク6（実機確認）

## 直前までやっていたこと

- タスク4（配線）: guard と編集フック2本を `.claude/settings.json` に配線し、配線のテスト（`test_settings_wires_guard`・G1〜G4）を足した。reviewer 四層○・全体 1444 passed・2 skipped・2 xfailed（c730ab8・1663305・f59f772）
- タスク5: 運営者が `.claude/settings.local.json` の allow を8行すべて消した（`"allow": []`・秘密なし）（f1a830f）
- このあと Claude Code を再起動する。再起動後から guard・deny・settings.local.json の変更が効く

## ブロッカー・未決事項

- タスク6（実機確認）は再起動後に運営者の立ち会いで行う。手順は `tasks/todo.md` タスク6、結果は `docs/design/guard_hook.md` 末尾に記録
- 3c で settings.json の書き換えに承認ダイアログが出なかった原因は未解明（タスク4 は差分を運営者に見せて承認をもらって進めた）
- 運営者の作業待ち: 直下の `clients.db` と `cf_simulation_*.xlsx` を `data/` に移す（タスク0.5 の残り）
- FP確認待ち（住宅ローンの金利タイプ・税と社会保険など）は `tasks/todo.md`「FP確認待ち」。今のフェーズは計算モデルに触れないので影響なし
- ep4.4 時点の未検証3項目（実機での AC-4-x・WSL2 の WeasyPrint・ANTHROPIC_API_KEY）は未消化のまま

## 次回必要なファイル

- `tasks/todo.md`（安全設定の移植のタスク6）
- `docs/design/guard_hook.md`
- `tests/fixtures/deny_probe/`
