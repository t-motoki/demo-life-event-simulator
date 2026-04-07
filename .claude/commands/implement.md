実装を開始します。

以下の手順で進めてください：

1. `docs/rules/00_workflow.md` を読む（実装フロー・エージェント定義を確認する）
2. `docs/spec/01_requirements.md` § 8 を読む（未確定事項を確認する）
   - 未確定事項が残っている場合は**実装を止めてユーザーに確認を求める**
3. `tasks/todo.md` を読む（対象タスクを確認する）

4. 以下の順でエージェントを呼ぶ：

   **planner** → タスクを分割し `tasks/todo.md` に計画を書く
   **tester** → 振る舞い仕様を記述する（テストコードは書かない）
   **architect** → 実装構造を設計する
   **engineer** → TDD で実装する（Red → Green → Refactor）

5. 実装完了後に `reviewer` を呼ぶ

---

**注意事項:**

- FP確認済みルールは `docs/spec/01_requirements.md` § 7 に従う。独断で変えない
- 計算モデルに関わる設計判断は `docs/` に記録する
- `src/` の変更には必ずテストを通す
