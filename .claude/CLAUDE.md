# ~/.claude/CLAUDE.md

## Purpose
このファイルは、Claude Code がどのリポジトリでも共通して守る作業原則を定義する。
不明点がある場合は、推測で実装を進めず、影響範囲・前提・代替案を明示すること。

---

## Working Principles
- 思考は英語で行い、最終的な出力は日本語とする。
  - ユーザーへの確認・質問・結果表示は、必ず日本語を使用すること。
- 既存の設計・命名・責務分割を優先して踏襲する。
- 変更は最小差分を基本とする。関連箇所以外には不要に触れない。
- 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。
- 新規実装より、まず既存拡張を検討する。
- コメント追加は「理由がないと理解できない箇所」に限定する。
- 要件が曖昧な場合は推測で確定せず、質問・前提・方針・代替案を提示すること。
- 仕様衝突・影響範囲が広い・自動修正が難しい場合は明示的に報告すること。

---

## Safety Rules
- 秘密情報（APIキー、秘密鍵、認証情報）を生成・ハードコード・ログ出力しない。
- `.env` や認証情報ファイルを新規作成・変更する場合は明示的理由を書く。
- 破壊的操作（大量削除、スキーマ変更、本番向け設定変更）は、影響範囲を明記する。
- 外部依存追加時は、必要性・代替不可理由・影響を示す。
- セキュリティ関連の変更では、攻撃面の変化を簡潔に記載する。

---

## Testing Policy
バグ修正時は再発防止のため原則テストを追加する。テスト不能な変更はその理由を明示する。

### Before finishing
作業完了前にテスト・lint・format・型チェック（必要なら）を実施すること。実行できない場合は理由を明記する。

---

## Output Format for Changes
変更時: **What changed** / **Why** / **Impact** / **Validation** の4項目で要約すること。

---

## Git / GitHub Rules
- **CRITICAL**: main / master / staging への直接コミット禁止。コミット前に `git branch --show-current` 確認必須。
- コミットメッセージは英語・[Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) 形式（`feat:` `fix:` `refactor:` `test:` `docs:` `chore:`）。
- 大きな変更は論理単位で分ける。自動生成ファイルの変更は理由を明記する。
- GitHub 操作はすべて `gh` コマンドを使用（MCP 経由禁止）。
- PR 作成前にテスト・lint を実施すること。PR 本文は日本語で書く。
- CI/CD がある場合、PR 作成後に `gh pr checks` でステータスを確認して完了とする。

---

## Preferred Decision Order
判断順: セキュリティ > 正確性 > 既存仕様整合 > 運用容易性 > 実装速度

---

## Compaction policy
コンテキスト圧縮時は、下記を必ず保持:
- 変更したファイルの一覧
- 実行したテストコマンドとその結果
- 未完了の TODO

---

## gstack
- すべてのウェブブラウジングに gstack の `/browse` スキルを使用すること。
- `mcp__claude-in-chrome__*` ツールは絶対に使用しないこと.

---

## Skill Routing
ユーザーのリクエストが届いたら、まずシーンを判定してから起点スキルを呼ぶ。
直接回答・他ツール先行は禁止。スキルには専用ワークフローがあり、その場しのぎの回答より優れた結果を生む。

### シーン判定ルール
動詞で判断する:
- 新規追加系（作る・追加・実装・追加したい・作りたい）→ 新機能開発
- 修正系（直す・修正する・壊れた・エラー・動かない・失敗する・〜になっている）→ バグ修正
- どちらにも当てはまらない → 実装を始める前に確認する:
  「これは新機能の追加ですか、それとも既存の不具合修正ですか？」

### シーン判定表

| シーン | 日本語トリガー例 | 起点スキル | 連鎖先（完了後に提示） |
|---|---|---|---|
| 新機能開発 | 〜を作りたい / 〜を追加したい / 〜機能を実装 | `superpowers:brainstorming` | writing-plans → TDD → **code-style** → verification → /ship |
| バグ修正 | 壊れた / エラーになる / 動かない / 〜が失敗する | `superpowers:systematic-debugging` | /investigate（UI起因時）→ TDD → **code-style** → verification → /ship |
| UI/Design改善 | 見た目を直したい / デザインを変えたい / Figma通りに | `superpowers:writing-plans` | executing-plans → /design-review → /qa → verification → /ship |
| PRレビュー | レビューして / 差分を確認 / マージ前チェック | `superpowers:requesting-code-review` | /review → receiving-code-review（指摘あり時）|
| デプロイ・PR作成 | shipして / PRを出して / デプロイ | `superpowers:verification-before-completion` | /ship → /land-and-deploy |
| リファクタリング | リファクタ / 整理 / 責務分離 | `superpowers:brainstorming` | writing-plans → using-git-worktrees → executing-plans → verification |
| 定期品質チェック | retro / 振り返り / セキュリティ監査 | `/retro` or `/cso` | — |

### 次ステップ提示テンプレート
各スキル完了後、Claude は以下のフォーマットで次のステップを提示する:

> 「`{起点スキル}` が完了しました。
> 次のステップ: **{次のスキル名}** を使います。
> 進めてよいですか？」
