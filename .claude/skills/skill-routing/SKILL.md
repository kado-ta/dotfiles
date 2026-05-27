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

各シーンで Codex Offload Rules（`~/.claude/CLAUDE.md` の同名セクション）を参照し委譲する。  
完了後は「`{起点スキル}` 完了 → 次は **{次のスキル}** を使います。進めてよいですか？」のフォーマットで次ステップを提示する。

---

## 各シーン詳細フロー

### 1. 新機能開発

> アイデア → 設計 → 実装計画 → 実装 → QA → デプロイ

#### Step 1: 設計

- **起点スキル:** `superpowers:brainstorming` 🔁 writing-plans
- **渡す情報:** 機能の目的・ユーザーストーリー・既存システムとの関係・制約条件
- **プロンプト例:**
  ```
  [機能名]を設計してください。
  目的: [〇〇をできるようにする]
  制約: [既存の[関連機能名]との整合性を保つこと]
  ```
- **注意点:** 設計承認前にコードを書き始めない。brainstorming の終端で自動的に writing-plans へ連携される。

#### Step 2: 実装計画確認

- **スキル:** `superpowers:writing-plans`（Step 1 から自動起動）
- **出力:** `docs/plans/YYYY-MM-DD-<feature>.md`
- **注意点:** 計画ファイルのタスク粒度・依存関係を確認してから次へ進む。

#### Step 3: 実装

- **スキル:** `superpowers:test-driven-development` → `superpowers:executing-plans`
- **渡す情報:** 計画ファイルのパス
- **プロンプト例:**
  ```
  docs/plans/[plan-file].md の Step N を実装してください。
  ```
- **注意点:** 独立したタスクが多い場合は `superpowers:dispatching-parallel-agents` で並列実行を検討。

#### Step 4: 動作確認

- **スキル:** `/qa`
- **渡す情報:** 確認対象 URL・操作フロー・期待する動作
- **プロンプト例:**
  ```
  /qa [URL] で [操作手順] を実行し、[期待する動作] を確認してください。
  ```
- **注意点:** `/qa` はバグを発見した場合その場で修正まで行う。レポートのみなら `/qa-only`。

#### Step 5: 完了確認・PR 作成

- **スキル:** `superpowers:verification-before-completion` → `/ship`
- **注意点:** verification 後に `/ship` を実行。`/ship` はバージョンバンプ・CHANGELOG 更新・PR 作成まで行う。

#### Step 6: デプロイ後確認

- **スキル:** `/land-and-deploy`
- **注意点:** CI 待機 → デプロイ → canary 確認まで自動化。

---

### 2. バグ修正

> バグ報告 → 原因調査 → 修正 → 回帰テスト → デプロイ

起点スキルは**バグの発生層**で分岐する:

| 分岐 | 適用条件 | 起点スキル |
|---|---|---|
| 2a 非UI | サーバーエラー / API 失敗 / CLI が動かない / ロジック・データ層の不具合 | `superpowers:systematic-debugging` |
| 2b UI/ブラウザ起因 | 画面表示崩れ / クリック不可 / フォーム送信失敗 / レンダリング異常 | `/investigate` |

判別がつかない場合は症状を見直し、ブラウザを開かないと再現できないなら 2b、コンソール/ログで完結するなら 2a。

#### Step 1: 原因調査

- **起点スキル:** 上表に従って `superpowers:systematic-debugging` または `/investigate`
- **プロンプト例（2a 非UI）:**
  ```
  以下のバグを調査してください。
  症状: [〇〇をすると〇〇になる]
  再現手順: [手順]
  関連ファイル: [ファイルパス]
  ```
- **プロンプト例（2b UI/ブラウザ起因）:**
  ```
  /investigate [URL] で [操作] を行い、コンソールエラー・ネットワークエラー・
  レンダリング状態を収集してください。
  ```
- **注意点:** 原因を仮定して修正を始めない。根本原因を特定するまで実装に進まない。

#### Step 2: 回帰テストを先に書く

- **スキル:** `superpowers:test-driven-development`
- **プロンプト例:**
  ```
  [バグの内容]が再発しないよう、先に回帰テストを書いてから修正してください。
  ```
- **注意点:** テストが Red になることを確認してから修正コードを書く。修正後に Green になることを確認。

#### Step 3: 完了確認・PR 作成・デプロイ

- **スキル:** `superpowers:verification-before-completion` → `/ship` → `/land-and-deploy`
- **注意点:** 修正が他の機能に影響していないか（デグレ）を必ず確認。

---

### 3. UI/Design 改善（Figma 起点）

> Figma デザイン確定 → 実装計画 → 実装 → ビジュアル QA → 動作 QA → デプロイ

#### Step 1: 実装計画

- **起点スキル:** `superpowers:writing-plans`（直接呼ぶ）
- **渡す情報:** Figma の URL or スクリーンショットのパス・変更対象コンポーネント・デザイントークン
- **プロンプト例:**
  ```
  以下の Figma デザインを実装する計画を作成してください。
  Figma: [URL or スクリーンショットのパス]
  対象: [コンポーネント名 / ページ名]
  変更点: [レイアウト、カラー、フォントなど]
  ```
- **注意点:** デザインは Figma で確定済みなので `brainstorming` は不要。

#### Step 2: 実装

- **スキル:** `superpowers:executing-plans`
- **注意点:** CSS の数値（px・rem）は Figma の値をそのまま使う。

#### Step 3: ビジュアル QA

- **スキル:** `/design-review`
- **注意点:** ビジュアルの不整合・スペーシング問題を検出し、その場で修正まで行う。

#### Step 4: インタラクション・動作確認

- **スキル:** `/qa`
- **注意点:** `/design-review` が見た目、`/qa` が動作担当。両方実行が基本。

#### Step 5: 完了確認・PR 作成・デプロイ

- **スキル:** `superpowers:verification-before-completion` → `/ship` → `/land-and-deploy`

---

### 4. PR コードレビュー

> PR 作成前チェック → 差分レビュー → 指摘対応 → マージ → デプロイ確認

#### Step 1: PR 作成前セルフレビュー

- **起点スキル:** `superpowers:requesting-code-review`
- **プロンプト例:**
  ```
  [機能名]の実装をレビューしてください。
  変更内容: [概要]
  変更の意図: [なぜこのアプローチを選んだか]
  テスト済み: [確認した内容]
  ```

#### Step 2: 差分レビュー

- **スキル:** `/review`
- **注意点:** SQL 安全性・LLM トラスト境界違反・条件分岐漏れ・テスト不足を重点チェック。

#### Step 3: レビュー指摘への対応

- **スキル:** `superpowers:receiving-code-review`
- **注意点:** 全指摘を機械的に受け入れない。疑問があればこのスキルが判断を助ける。

#### Step 4: マージ・デプロイ

- **スキル:** `/land-and-deploy`
- **注意点:** CI が通っていることを確認してから実行。

---

### 5. デプロイ・PR 作成

#### Step 1: 完了確認

- **起点スキル:** `superpowers:verification-before-completion`
- **注意点:** 実装が完了しているかの証拠（テスト結果・確認コマンド出力）を確認してから主張する。

#### Step 2: PR 作成

- **スキル:** `/ship`
- **注意点:** バージョンバンプ・CHANGELOG 更新・PR 作成まで自動で行う。

#### Step 3: マージ・デプロイ

- **スキル:** `/land-and-deploy`

---

### 6. リファクタリング

> スコープ設計 → 実装計画 → ブランチ分離 → 実装 → 回帰確認 → デプロイ

#### Step 1: スコープ・方針の設計

- **起点スキル:** `superpowers:brainstorming` 🔁 writing-plans
- **プロンプト例:**
  ```
  以下のリファクタリング方針を設計してください。
  対象: [ファイル名 / モジュール名]
  問題: [責務が混在している / 命名が不明瞭 / など]
  制約: [外部 API の仕様は変えない / DB スキーマは変えない]
  ```
- **注意点:** 解決する問題を明確にしてから始める。スコープが広い場合は brainstorming で分割を提案させる。

#### Step 2: ブランチ分離

- **スキル:** `superpowers:using-git-worktrees`
- **注意点:** 進行中の機能開発ブランチと混在させない。

#### Step 3: 実装

- **スキル:** `superpowers:executing-plans`
- **注意点:** 各ステップ後に既存テストが通ることを確認しながら進める。

#### Step 4: 回帰確認・PR 作成

- **スキル:** `superpowers:verification-before-completion` → `superpowers:requesting-code-review` → `/ship`
- **注意点:** PR タイトルに `refactor:` プレフィックスを明記。

---

### 7. 定期的な品質チェック

振り返り（7a）とセキュリティ監査（7b）は独立したルーチン。トリガー語で分岐する。

#### 7a. 振り返り（週次・スプリント単位）

- **起点スキル:** `/retro`
- **トリガー語:** retro / 振り返り / 週次まとめ / 何を出荷したか
- **注意点:** コミット履歴・作業パターン・コード品質メトリクスを分析。週次での実行が推奨。

#### 7b. セキュリティ監査

- **起点スキル:** `/cso`
- **トリガー語:** セキュリティ監査 / 脆弱性チェック / 攻撃面確認 / OWASP
- **注意点:** OWASP Top 10・STRIDE・シークレット漏洩・依存関係サプライチェーンを横断検査。月次または大きな変更後に実行。

#### 補助スキル

- `/benchmark` — パフォーマンス計測（初回でベースライン確立、以降は回帰検出）
- `/qa-only` — QA レポートのみ（`/qa` と違い修正は行わない）
- `/learn` — プロジェクト固有の知見を永続化
