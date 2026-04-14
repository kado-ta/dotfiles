# Skill Routing

ユーザーのリクエストが届いたら、まずシーンを判定してから起点スキルを呼ぶ。
直接回答・他ツール先行は禁止。スキルには専用ワークフローがあり、その場しのぎの回答より優れた結果を生む。

## シーン判定ルール

動詞で判断する:
- 新規追加系（作る・追加・実装・追加したい・作りたい）→ 新機能開発
- 修正系（直す・壊れた・エラー・動かない・失敗する・〜になっている）→ バグ修正
- どちらにも当てはまらない → 実装を始める前に確認する:
  「これは新機能の追加ですか、それとも既存の不具合修正ですか？」

## シーン判定表

| シーン | 日本語トリガー例 | 起点スキル | 連鎖先（完了後に提示） |
|---|---|---|---|
| 新機能開発 | 〜を作りたい / 〜を追加したい / 〜機能を実装 | `superpowers:brainstorming` | writing-plans → TDD → verification → /ship |
| バグ修正 | 壊れた / エラーになる / 動かない / 〜が失敗する | `superpowers:systematic-debugging` | /investigate（UI起因時）→ TDD → verification → /ship |
| UI/Design改善 | 見た目を直したい / デザインを変えたい / Figma通りに | `superpowers:writing-plans` | executing-plans → /design-review → /qa → verification → /ship |
| PRレビュー | レビューして / 差分を確認 / マージ前チェック | `superpowers:requesting-code-review` | /review → receiving-code-review（指摘あり時）|
| デプロイ・PR作成 | shipして / PRを出して / デプロイ | `superpowers:verification-before-completion` | /ship → /land-and-deploy |
| リファクタリング | リファクタ / 整理 / 責務分離 | `superpowers:brainstorming` | writing-plans → using-git-worktrees → executing-plans → verification |
| 定期品質チェック | retro / 振り返り / セキュリティ監査 | `/retro` or `/cso` | — |

## 次ステップ提示テンプレート

各スキル完了後、Claude は以下のフォーマットで次のステップを提示する:

> 「`{起点スキル}` が完了しました。
> 次のステップ: **{次のスキル名}** を使います。
> 進めてよいですか？」

詳細なフロー・プロンプト例は `.claude/docs/SKILL_ROUTING_README.md` を参照。
