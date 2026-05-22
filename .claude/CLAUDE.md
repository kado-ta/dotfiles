# ~/.claude/CLAUDE.md

## Purpose
このファイルは、Claude Code がどのリポジトリでも共通して守る作業原則を定義する。

---

## Working Principles
- 思考は英語で行い、最終的な出力は日本語とする。
  - ユーザーへの確認・質問・結果表示は、必ず日本語を使用すること。
- 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。

---

## Coding Discipline

Karpathy の LLM コーディング原則 (<https://github.com/multica-ai/andrej-karpathy-skills>) をベースに、このリポジトリで遵守するコーディング行動を定義する。

**Tradeoff**: これらの指針は速度よりも慎重さに寄せている。trivial なタスクでは判断で省略してよい。

### 1. Think Before Coding (実装前に考える)
**推測しない。迷いを隠さない。トレードオフを明示する。**
- 解釈が複数あるなら、黙って選ばず並べて示す。
- よりシンプルな代替案があれば提示する。必要なら押し返す。
- 不明点があれば手を止め、何が不明か言語化して質問する。

### 2. Simplicity First (シンプルさを優先)
**問題を解く最小限のコード。推測は不要。**
- 依頼されていない機能は作らない。
- 一回しか使わないコードを抽象化しない。
- 要求されていない `flexibility` / `configurability` を追加しない。
- 起こりえないシナリオのエラーハンドリングは不要。
- 「Senior engineer が複雑すぎると言うか?」と自問し、Yes なら簡素化する。

### 3. Surgical Changes (外科手術的な変更)
**必要な部分だけに触れる。自分が出したゴミだけ片付ける。**
- 隣接コード・コメント・フォーマットを「改善」しない。
- 壊れていないものをリファクタしない。
- 既存スタイルに合わせる (自分の好みと違っても)。
- 無関係なデッドコードに気づいたら、勝手に消さず報告する。
- 自分の変更で発生した未使用 import / 変数 / 関数のみ除去する。既存のデッドコードは依頼がない限り残す。
- 変更された全行がユーザー依頼に直接トレースできること。

### 4. Goal-Driven Execution (ゴール駆動の実行)
**成功基準を定義し、検証ループを回す。**
- `validation を追加` → `不正入力のテストを書き pass させる`
- `バグ修正` → `再現テストを書いてから修正する`
- `リファクタ` → `前後でテストが pass することを保証`
- マルチステップ作業では `[step → verify: check]` 形式で計画を明示する。
- 「動くようにする」のような曖昧なゴールでは進めず、明確な判定基準を先に定義する。

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
以下のいずれかに該当する変更時は **What changed** / **Why** / **Impact** / **Validation** の 4 項目で要約する:
- 設計判断を含む変更
- 複数ファイル（2 ファイル以上）にまたがる変更
- 公開 API・スキーマ・設定ファイルの変更
- セキュリティ・認証・破壊的操作を含む変更

軽微な変更（typo 修正、1 ファイル内のリネーム、コメント追記など）は 1〜2 行で簡潔に報告すれば足りる。

---

## Git / GitHub Rules
- **CRITICAL**: main / master / staging への直接コミット禁止。コミット前にブランチを必ず確認する。
- コミットメッセージは英語・[Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) 形式（`feat:` `fix:` `refactor:` `test:` `docs:` `chore:`）。
- 大きな変更は論理単位で分ける。自動生成ファイルの変更は理由を明記する。
- GitHub 操作はすべて `gh` コマンドを使用（MCP 経由禁止）。
- PR 本文の言語はプロジェクトの慣習に合わせる:
  - 社内・個人リポジトリ: 日本語をデフォルトとする。
  - OSS・対外プロジェクト: 既存 PR の言語に合わせる（不明な場合は英語）。
- CI/CD がある場合、PR 作成後に `gh pr checks` でステータスを確認して完了とする。

---

## Preferred Decision Order
判断順: セキュリティ > 正確性 > 既存仕様整合 > 運用容易性 > 実装速度

---

## Compaction policy
コンテキスト圧縮時、Claude 自身が要約に必ず保持する情報:
- 実行したテスト・lint・型チェックコマンドとその結果
- 未完了の TODO と次のアクション
- 直前にユーザーから受けた判断・指示（推測ではなく確定情報）

---

## gstack
- 対話型ブラウジング（クリック・フォーム入力・スクリーンショット・QA・ログイン後の状態確認）には gstack の `/browse` スキルを使用する。
- 静的なドキュメント参照（公式ドキュメント・MDN・GitHub README など、URL を開いて読むだけ）は `WebFetch` を使ってよい。`settings.json` の allow リストに登録されたドメインに限る。
- `mcp__claude-in-chrome__*` ツールは絶対に使用しないこと。

---

## Codex Offload Rules

コンテキスト節約とレビュー精度のため、以下は Codex に委譲する。
詳細・タイムアウト・依頼フォーマットは `.claude/docs/CODEX_OFFLOAD.md` を参照。

| ケース | コマンド | 主なトリガー |
|---|---|---|
| 読込委譲 | `/codex consult` | 単一ファイル > 1000 行 / 横断検索 > 5 ファイル & 2000 行 / ログ解析 / 全体把握 |
| 限定実装 | `codex exec` | 機械的な一括修正のみ（型エラー、import 整理、format、単純テスト追加） |
| レビュー | `/codex review` | `/ship` 前 / 差分 > 200 行 / auth・token・migration・schema 変更 |
| 相談 | `/codex consult` | 実装案 2 つ以上で迷う / デバッグ仮説 3 つ以上 / ユーザーから「どう思う？」 |

- 信頼境界: Codex 出力はそのままコミットしない。実装 diff は `/codex review` でゲート。
- ループ防止: 1 タスクで `/codex consult` は最大 2 回。
- CLI が失敗・タイムアウトの場合は Claude 直接実行に切り替え、原因を報告。

---

## Skill Routing
ユーザーのリクエストはまずシーンを判定し、該当する起点スキルを呼ぶ。詳細フロー・プロンプト例は `.claude/docs/SKILL_ROUTING.md` を参照。

直接回答可（スキル起動不要）:
- シーン判定表のどの行にも該当しない単発の質問（例: 「このファイルの何行目に X がある？」「この変数の型は？」）
- 既存ファイルの確認・閲覧のみで完結する依頼
- ユーザーが明示的にスキル起動を不要と指示した場合

### シーン判定ルール
衝突時の優先順位: **(1) UI/Design 関連語 > (2) レビュー・デプロイ系 > (3) 動詞判断（新規=brainstorming / 修正=systematic-debugging、UI 起因のみ /investigate）**。判定不能なら実装前に「新機能 or 不具合修正？」を確認。

### シーン判定表

| シーン | 日本語トリガー例 | 起点スキル | 連鎖先（完了後に提示） |
|---|---|---|---|
| 新機能開発 | 〜を作りたい / 〜を追加したい / 〜機能を実装 | `superpowers:brainstorming` | writing-plans → TDD → **code-style** → verification → /ship |
| バグ修正（非UI） | サーバーエラー / API が失敗する / CLI が動かない / ロジックが壊れた | `superpowers:systematic-debugging` | TDD → **code-style** → verification → /ship |
| バグ修正（UI/ブラウザ起因） | 画面表示が崩れる / クリックできない / フォーム送信失敗 / レンダリングが壊れた | `/investigate` | TDD → **code-style** → verification → /ship |
| UI/Design改善 | 見た目を直したい / デザインを変えたい / Figma通りに | `superpowers:writing-plans` | executing-plans → /design-review → /qa → verification → /ship |
| PRレビュー | レビューして / 差分を確認 / マージ前チェック | `superpowers:requesting-code-review` | /review → receiving-code-review（指摘あり時）|
| デプロイ・PR作成 | shipして / PRを出して / デプロイ | `superpowers:verification-before-completion` | /ship → /land-and-deploy |
| リファクタリング | リファクタ / 整理 / 責務分離 | `superpowers:brainstorming` | writing-plans → using-git-worktrees → executing-plans → verification |
| 振り返り | retro / 振り返り / 週次まとめ / 何を出荷したか | `/retro` | — |
| セキュリティ監査 | セキュリティ監査 / 脆弱性チェック / 攻撃面確認 / OWASP | `/cso` | — |

各シーンで [Codex Offload Rules](#codex-offload-rules) を参照し委譲する。完了後は「`{起点スキル}` 完了 → 次は **{次のスキル}** を使います。進めてよいですか？」のフォーマットで次ステップを提示する。
