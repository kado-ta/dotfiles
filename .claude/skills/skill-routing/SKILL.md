---
name: skill-routing
description: Use when starting any task — determines which skill to invoke by detecting the scene type (new feature, bug fix, UI/design, code review, deploy, refactor, etc.) and routes to the correct starting skill. Also defines when direct answers are allowed without invoking a skill.
---

# Skill Routing

ユーザーのリクエストのシーンを判定し、起動すべき起点スキルを決定する。

## 直接回答可（スキル起動不要）

以下に該当する場合はスキルを起動せず直接回答してよい:
- シーン判定表のどの行にも該当しない単発の質問（例: 「このファイルの何行目に X がある？」「この変数の型は？」）
- 既存ファイルの確認・閲覧のみで完結する依頼
- ユーザーが明示的にスキル起動を不要と指示した場合

## シーン判定ルール

衝突時の優先順位: **(1) UI/Design 関連語 > (2) レビュー・デプロイ系 > (3) 動詞判断（新規=brainstorming / 修正=systematic-debugging、UI 起因のみ /investigate）**。判定不能なら実装前に「新機能 or 不具合修正？」を確認。

## シーン判定表

| シーン | 日本語トリガー例 | 起点スキル | 連鎖先（完了後に提示） |
|---|---|---|---|
| 新機能開発 | 〜を作りたい / 〜を追加したい / 〜できるようにしたい / 〜機能を実装 | `superpowers:brainstorming` | writing-plans → TDD → **code-style** → verification → /ship |
| バグ修正（非UI） | サーバーエラー / API が失敗する / CLI が動かない / ロジックが壊れた | `superpowers:systematic-debugging` | TDD → **code-style** → verification → /ship |
| バグ修正（UI/ブラウザ起因） | 画面表示が崩れる / クリックできない / フォーム送信失敗 / レンダリングが壊れた | `/investigate` | TDD → **code-style** → verification → /ship |
| UI/Design改善 | 見た目を直したい / デザインを変えたい / Figma通りに | `superpowers:writing-plans` | executing-plans → /design-review → /qa → verification → /ship |
| PRレビュー | レビューして / 差分を確認 / マージ前チェック | `superpowers:requesting-code-review` | /review → receiving-code-review（指摘あり時）|
| デプロイ・PR作成 | shipして / PRを出して / デプロイ | `superpowers:verification-before-completion` | /ship → /land-and-deploy |
| リファクタリング | リファクタ / 整理 / 責務分離 | `superpowers:brainstorming` | writing-plans → using-git-worktrees → executing-plans → verification |
| 振り返り | retro / 振り返り / 週次まとめ / 何を出荷したか | `/retro` | — |
| セキュリティ監査 | セキュリティ監査 / 脆弱性チェック / 攻撃面確認 / OWASP | `/cso` | — |

各シーンで Codex Offload Rules（`.claude/docs/CODEX_OFFLOAD.md` 参照）に従い委譲する。  
完了後は「`{起点スキル}` 完了 → 次は **{次のスキル}** を使います。進めてよいですか？」のフォーマットで次ステップを提示する。
