# gstack × Superpowers スキルルーティング ガイド

Claude への日本語指示から、Superpowers・gstack の適切なスキルが自動起動・連鎖提示される仕組みのガイドです。

自動スキル選択のロジックは `.claude/CLAUDE.md` が担います。
このドキュメントは各シーンの詳細フロー・プロンプト例の人間向けリファレンスです。

**凡例:**
- `superpowers:xxx` → Superpowers スキル（`Skill` ツールで起動）
- `/xxx` → gstack スキルコマンド
- 🔁 → 完了後に Claude が次スキルを提示して確認を取る

---

## シーン一覧

| # | シーン | 起点スキル | 連鎖フロー |
|---|---|---|---|
| 1 | [新機能開発](#1-新機能開発) | `superpowers:brainstorming` | → writing-plans → TDD → verification → /ship |
| 2 | [バグ修正](#2-バグ修正) | `superpowers:systematic-debugging` | → /investigate → TDD → verification → /ship |
| 3 | [UI/Design改善](#3-uidesign改善figma起点) | `superpowers:writing-plans` | → executing-plans → /design-review → /qa → verification → /ship |
| 4 | [PRコードレビュー](#4-prコードレビュー) | `superpowers:requesting-code-review` | → /review → receiving-code-review |
| 5 | [デプロイ・PR作成](#5-デプロイpr作成) | `superpowers:verification-before-completion` | → /ship → /land-and-deploy |
| 6 | [リファクタリング](#6-リファクタリング) | `superpowers:brainstorming` | → writing-plans → using-git-worktrees → executing-plans → verification |
| 7 | [定期品質チェック](#7-定期的な品質チェック) | `/retro` or `/cso` | — |

---

## 1. 新機能開発

> アイデア → 設計 → 実装計画 → 実装 → QA → デプロイ

### Step 1: 設計

- **起点スキル:** `superpowers:brainstorming` 🔁 writing-plans
- **渡す情報:** 機能の目的・ユーザーストーリー・既存システムとの関係・制約条件
- **プロンプト例:**
  ```
  [機能名]を設計してください。
  目的: [〇〇をできるようにする]
  制約: [既存の[関連機能名]との整合性を保つこと]
  ```
- **注意点:** 設計承認前にコードを書き始めない。brainstorming の終端で自動的に writing-plans へ連携される。

### Step 2: 実装計画確認

- **スキル:** `superpowers:writing-plans`（Step 1から自動起動）
- **出力:** `docs/plans/YYYY-MM-DD-<feature>.md`
- **注意点:** 計画ファイルのタスク粒度・依存関係を確認してから次へ進む。

### Step 3: 実装

- **スキル:** `superpowers:test-driven-development` → `superpowers:executing-plans`
- **渡す情報:** 計画ファイルのパス
- **プロンプト例:**
  ```
  docs/plans/[plan-file].md の Step N を実装してください。
  ```
- **注意点:** 独立したタスクが多い場合は `superpowers:dispatching-parallel-agents` で並列実行を検討。

### Step 4: 動作確認

- **スキル:** `/qa`
- **渡す情報:** 確認対象URL・操作フロー・期待する動作
- **プロンプト例:**
  ```
  /qa [URL] で [操作手順] を実行し、[期待する動作] を確認してください。
  ```
- **注意点:** `/qa` はバグを発見した場合その場で修正まで行う。レポートのみなら `/qa-only`。

### Step 5: 完了確認・PR作成

- **スキル:** `superpowers:verification-before-completion` → `/ship`
- **プロンプト例:**
  ```
  [機能名]の実装が完了したか確認してください。
  ```
- **注意点:** verification 後に `/ship` を実行。`/ship` はバージョンバンプ・CHANGELOG更新・PR作成まで行う。

### Step 6: デプロイ後確認

- **スキル:** `/land-and-deploy`
- **注意点:** CI待機 → デプロイ → canary確認まで自動化。

---

## 2. バグ修正

> バグ報告 → 原因調査 → 修正 → 回帰テスト → デプロイ

### Step 1: 原因調査

- **起点スキル:** `superpowers:systematic-debugging`
- **渡す情報:** バグの症状・再現手順・発生環境・関連ファイル
- **プロンプト例:**
  ```
  以下のバグを調査してください。
  症状: [〇〇をすると〇〇になる]
  再現手順: [手順]
  関連ファイル: [ファイルパス]
  ```
- **注意点:** 原因を仮定して修正を始めない。根本原因を特定するまで実装に進まない。

### Step 2: ブラウザ上での動作確認（UI起因の場合）

- **スキル:** `/investigate`
- **渡す情報:** バグが発生するURL・操作手順
- **プロンプト例:**
  ```
  /investigate [URL] で [操作] を行い、コンソールエラー・ネットワークエラーを収集してください。
  ```
- **注意点:** サーバーサイド起因のバグには不要。UIやAPIレスポンスに関わるバグで有効。

### Step 3: 回帰テストを先に書く

- **スキル:** `superpowers:test-driven-development`
- **プロンプト例:**
  ```
  [バグの内容]が再発しないよう、先に回帰テストを書いてから修正してください。
  ```
- **注意点:** テストがRedになることを確認してから修正コードを書く。修正後にGreenになることを確認。

### Step 4: 完了確認・PR作成・デプロイ

- **スキル:** `superpowers:verification-before-completion` → `/ship` → `/land-and-deploy`
- **注意点:** 修正が他の機能に影響していないか（デグレ）を必ず確認。

---

## 3. UI/Design改善（Figma起点）

> Figmaデザイン確定 → 実装計画 → 実装 → ビジュアルQA → 動作QA → デプロイ

### Step 1: 実装計画

- **起点スキル:** `superpowers:writing-plans`（直接呼ぶ）
- **渡す情報:** FigmaのURL or スクリーンショットのパス・変更対象コンポーネント・デザイントークン
- **プロンプト例:**
  ```
  以下のFigmaデザインを実装する計画を作成してください。
  Figma: [URL or スクリーンショットのパス]
  対象: [コンポーネント名 / ページ名]
  変更点: [レイアウト、カラー、フォントなど]
  ```
- **注意点:** デザインはFigmaで確定済みなので `brainstorming` は不要。

### Step 2: 実装

- **スキル:** `superpowers:executing-plans`
- **注意点:** CSSの数値（px・rem）はFigmaの値をそのまま使う。

### Step 3: ビジュアルQA

- **スキル:** `/design-review`
- **渡す情報:** 確認対象URL・Figmaスクリーンショットのパス（比較用）
- **注意点:** ビジュアルの不整合・スペーシング問題を検出し、その場で修正まで行う。

### Step 4: インタラクション・動作確認

- **スキル:** `/qa`
- **注意点:** `/design-review` が見た目、`/qa` が動作担当。両方実行が基本。

### Step 5: 完了確認・PR作成・デプロイ

- **スキル:** `superpowers:verification-before-completion` → `/ship` → `/land-and-deploy`

---

## 4. PRコードレビュー

> PR作成前チェック → 差分レビュー → 指摘対応 → マージ → デプロイ確認

### Step 1: PR作成前セルフレビュー

- **起点スキル:** `superpowers:requesting-code-review`
- **渡す情報:** 実装した機能の概要・変更の意図・テスト済みの内容
- **プロンプト例:**
  ```
  [機能名]の実装をレビューしてください。
  変更内容: [概要]
  変更の意図: [なぜこのアプローチを選んだか]
  テスト済み: [確認した内容]
  ```

### Step 2: 差分レビュー

- **スキル:** `/review`
- **注意点:** SQL安全性・LLMトラスト境界違反・条件分岐漏れ・テスト不足を重点チェック。

### Step 3: レビュー指摘への対応

- **スキル:** `superpowers:receiving-code-review`
- **渡す情報:** レビューコメント（GitHubのURLまたはテキスト）
- **注意点:** 全指摘を機械的に受け入れない。疑問があればこのスキルが判断を助ける。

### Step 4: マージ・デプロイ

- **スキル:** `/land-and-deploy`
- **注意点:** CIが通っていることを確認してから実行。

---

## 5. デプロイ・PR作成

### Step 1: 完了確認

- **起点スキル:** `superpowers:verification-before-completion`
- **注意点:** 実装が完了しているかの証拠（テスト結果・確認コマンド出力）を確認してから主張する。

### Step 2: PR作成

- **スキル:** `/ship`
- **注意点:** バージョンバンプ・CHANGELOG更新・PR作成まで自動で行う。

### Step 3: マージ・デプロイ

- **スキル:** `/land-and-deploy`

---

## 6. リファクタリング

> スコープ設計 → 実装計画 → ブランチ分離 → 実装 → 回帰確認 → デプロイ

### Step 1: スコープ・方針の設計

- **起点スキル:** `superpowers:brainstorming` 🔁 writing-plans
- **渡す情報:** リファクタリング対象・現状の問題点・変えてはいけない外部仕様
- **プロンプト例:**
  ```
  以下のリファクタリング方針を設計してください。
  対象: [ファイル名 / モジュール名]
  問題: [責務が混在している / 命名が不明瞭 / など]
  制約: [外部APIの仕様は変えない / DBスキーマは変えない]
  ```
- **注意点:** 解決する問題を明確にしてから始める。スコープが広い場合は brainstorming で分割を提案させる。

### Step 2: ブランチ分離

- **スキル:** `superpowers:using-git-worktrees`
- **注意点:** 進行中の機能開発ブランチと混在させない。

### Step 3: 実装

- **スキル:** `superpowers:executing-plans`
- **注意点:** 各ステップ後に既存テストが通ることを確認しながら進める。

### Step 4: 回帰確認・PR作成

- **スキル:** `superpowers:verification-before-completion` → `superpowers:requesting-code-review` → `/ship`
- **注意点:** PRタイトルに `refactor:` プレフィックスを明記。

---

## 7. 定期的な品質チェック

> 振り返り → セキュリティ監査 → パフォーマンス計測 → QAレポート → 学習記録

### Step 1: 振り返り（週次・スプリント単位）

- **起点スキル:** `/retro`
- **注意点:** コミット履歴・作業パターン・コード品質メトリクスを分析。週次での実行が推奨。

### Step 2: セキュリティ監査

- **スキル:** `/cso`
- **注意点:** OWASP Top 10・STRIDE・シークレット漏洩・依存関係サプライチェーンを横断検査。月次または大きな変更後に実行。

### Step 3: パフォーマンス計測

- **スキル:** `/benchmark`
- **渡す情報:** 計測対象URL・比較基準
- **注意点:** 初回実行でベースラインを確立し、以降はそのベースラインと比較して回帰を検出。

### Step 4: QAレポート

- **スキル:** `/qa-only`
- **注意点:** `/qa`（バグ修正まで実行）と違い、発見のみ。品質の現状把握や修正を別セッションに持ち越したい場合に使う。

### Step 5: 学習の記録

- **スキル:** `/learn`
- **注意点:** プロジェクト固有の知見を永続化。次回以降のQA・設計判断に自動参照される。
