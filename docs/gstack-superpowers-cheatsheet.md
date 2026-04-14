# gstack × superpowers チートシート

> このドキュメントは `.claude/SKILL_ROUTING.md` と連動しています。
> Claude の自動スキル選択は `SKILL_ROUTING.md` が担い、このドキュメントは各シーンの詳細フロー・プロンプト例の人間向けリファレンスです。

各シーンでどのスキル/コマンドを使い、何を渡すかの個人参照用リファレンス。

**凡例:**
- `superpowers xxx` → `superpowers xxx スキルを使って〜してください` と入力
- `/xxx` → gstack スキルコマンド（例: `/qa`, `/ship`）
- 🔁 → 自動的に次のスキルへ連携される

---

## シーン一覧

| # | シーン | superpowers | gstack |
|---|---|---|---|
| 1 | [新機能開発](#1-新機能開発) | brainstorming → writing-plans → TDD → verification | qa, canary |
| 2 | [バグ修正](#2-バグ修正) | systematic-debugging → TDD → verification | investigate, qa |
| 3 | [UI/Design改善](#3-uidesign改善figma起点) | writing-plans → verification | design-review, qa |
| 4 | [PRコードレビュー](#4-prコードレビュー) | requesting-code-review → receiving-code-review | review, land-and-deploy, canary |
| 5 | [定期品質チェック](#5-定期的な品質チェック) | — | retro, cso, benchmark, qa-only, learn |
| 6 | [リファクタリング](#6-リファクタリング) | brainstorming → writing-plans → executing-plans → verification | qa |

---

## 1. 新機能開発

> アイデア → 設計 → 実装計画 → 実装 → QA → デプロイ

### Step 1: 設計

- **スキル:** `superpowers brainstorming` 🔁 writing-plans
- **渡す情報:** 機能の目的・ユーザーストーリー・既存システムとの関係・制約条件
- **プロンプト例:**
  ```
  superpowers brainstorming スキルを使って、[機能名]を設計してください。
  目的: [〇〇をできるようにする]
  制約: [既存の[関連機能名]との整合性を保つこと]
  ```
- **注意点:** 設計承認前にコードを書き始めない。brainstorming の終端で自動的に writing-plans へ連携される。

### Step 2: 実装計画確認

- **スキル:** `superpowers writing-plans`（Step 1から自動起動）
- **渡す情報:** —（Step 1 の出力から自動引き継ぎ）
- **出力:** `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`
- **プロンプト例:** —（自動起動のため不要）
- **注意点:** 計画ファイルのタスク粒度・依存関係（ブロッカーになるタスクが明示されているか）を確認してから次へ進む。

### Step 3: 実装

- **スキル:** `superpowers test-driven-development` → `superpowers executing-plans`
- **渡す情報:** 計画ファイルのパス
- **プロンプト例:**
  ```
  superpowers test-driven-development スキルを使って、
  docs/superpowers/plans/[plan-file].md の Step N を実装してください。
  ```
- **注意点:** 独立したタスクが多い場合は `superpowers dispatching-parallel-agents` で並列実行を検討。

### Step 4: 動作確認

- **スキル:** `/qa`
- **渡す情報:** 確認対象URL・操作フロー・期待する動作
- **プロンプト例:**
  ```
  /qa [URL] で [操作手順] を実行し、[期待する動作] を確認してください。
  ```
- **注意点:** `/qa` はバグを発見した場合その場で修正まで行う。レポートのみ欲しい場合は `/qa-only`。

### Step 5: 完了確認・PR作成

- **スキル:** `superpowers verification-before-completion` → `/ship`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  superpowers verification-before-completion スキルを使って、
  [機能名]の実装が完了したか確認してください。
  ```
- **注意点:** verification 後に `/ship` を実行。`/ship` はバージョンバンプ・CHANGELOG更新・PR作成まで行う。

### Step 6: デプロイ後確認

- **スキル:** `/land-and-deploy`（または `/canary` 単独）
- **渡す情報:** 本番URL
- **プロンプト例:**
  ```
  /land-and-deploy でマージ・デプロイ・本番確認まで実行してください。
  ```
- **注意点:** `/land-and-deploy` はCI待機 → デプロイ → canary確認まで自動化。`/ship` でPR作成後に使う。

---

## 2. バグ修正

> バグ報告 → 原因調査 → 修正 → 回帰テスト → デプロイ

### Step 1: 原因調査

- **スキル:** `superpowers systematic-debugging`
- **渡す情報:** バグの症状・再現手順・発生環境・関連ファイル
- **プロンプト例:**
  ```
  superpowers systematic-debugging スキルを使って、以下のバグを調査してください。
  症状: [〇〇をすると〇〇になる]
  再現手順: [手順]
  関連ファイル: [ファイルパス]
  ```
- **注意点:** 原因を仮定して修正を始めない。このスキルが根本原因を特定するまで実装に進まない。

### Step 2: ブラウザ上での動作確認（UI起因の場合）

- **スキル:** `/investigate`
- **渡す情報:** バグが発生するURL・操作手順
- **プロンプト例:**
  ```
  /investigate [URL] で [操作] を行い、コンソールエラー・ネットワークエラーを収集してください。
  ```
- **注意点:** サーバーサイド起因のバグには不要。UIやAPIレスポンスに関わるバグで有効。

### Step 3: 回帰テストを先に書く

- **スキル:** `superpowers test-driven-development`
- **渡す情報:** バグの原因・期待する正しい動作
- **プロンプト例:**
  ```
  superpowers test-driven-development スキルを使って、
  [バグの内容]が再発しないよう、先に回帰テストを書いてから修正してください。
  ```
- **注意点:** テストがRedになることを確認してから修正コードを書く。修正後にGreenになることを確認。

### Step 4: 完了確認・PR作成

- **スキル:** `superpowers verification-before-completion` → `/ship`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  superpowers verification-before-completion スキルを使って、
  [バグ名]の修正が完了したか確認してください。
  ```
- **注意点:** 修正が他の機能に影響していないか（デグレ）を必ず確認してから `/ship`。

### Step 5: デプロイ後確認

- **スキル:** `/land-and-deploy`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  /land-and-deploy でマージからデプロイまで実行してください。
  ```
- **注意点:** バグ修正は影響範囲が限定的なことが多いが、`/canary` でエラーレートの変化を確認する。

---

## 3. UI/Design改善（Figma起点）

> Figmaデザイン確定 → 実装計画 → 実装 → ビジュアルQA → 動作QA → デプロイ

### Step 1: 実装計画

- **スキル:** `superpowers writing-plans`（直接呼ぶ）
- **渡す情報:** FigmaのURL or スクリーンショットのパス・変更対象コンポーネント・デザイントークン（色・余白など）
- **プロンプト例:**
  ```
  superpowers writing-plans スキルを使って、以下のFigmaデザインを実装する計画を作成してください。
  Figma: [URL or スクリーンショットのパス]
  対象: [コンポーネント名 / ページ名]
  変更点: [レイアウト、カラー、フォントなど]
  ```
- **注意点:** デザインはFigmaで確定済みなので `brainstorming` は不要。直接 `writing-plans` を呼ぶ。

### Step 2: 実装

- **スキル:** `superpowers executing-plans`
- **渡す情報:** 計画ファイルのパス
- **プロンプト例:**
  ```
  superpowers executing-plans スキルを使って、
  docs/superpowers/plans/[plan-file].md を実行してください。
  ```
- **注意点:** CSSの数値（px・rem）はFigmaの値をそのまま使う。マジックナンバーを避け、デザイントークンや定数に落とす。

### Step 3: ビジュアルQA

- **スキル:** `/design-review`
- **渡す情報:** 確認対象URL・Figmaスクリーンショットのパス（比較用）
- **プロンプト例:**
  ```
  /design-review [URL] を確認してください。
  Figmaデザイン: [スクリーンショットのパス]
  確認ポイント: [余白、フォントサイズ、カラー、レスポンシブ]
  ```
- **注意点:** ビジュアルの不整合・スペーシング問題・AIスロップパターンを検出し、その場で修正まで行う。レポートのみなら `/qa-only`。

### Step 4: インタラクション・動作確認

- **スキル:** `/qa`
- **渡す情報:** 確認対象のユーザー操作フロー
- **プロンプト例:**
  ```
  /qa [URL] でフォーム送信・ホバー・レスポンシブ（SP/PC）の動作を確認してください。
  ```
- **注意点:** `/design-review` が見た目、`/qa` が動作担当。両方を実行するのが基本。

### Step 5: 完了確認・PR作成・デプロイ

- **スキル:** `superpowers verification-before-completion` → `/ship` → `/land-and-deploy`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  superpowers verification-before-completion スキルを使って、
  [デザイン変更名]の実装が完了したか確認してください。
  ```
- **注意点:** デプロイ後も `/canary` で本番表示を確認。ローカルと本番でフォントやCDNの差異が出ることがある。

---

## 4. PR・コードレビュー

> PR作成前チェック → 差分レビュー → 指摘対応 → マージ → デプロイ確認

### Step 1: PR作成前セルフレビュー

- **スキル:** `superpowers requesting-code-review`
- **渡す情報:** 実装した機能の概要・変更の意図・テスト済みの内容
- **プロンプト例:**
  ```
  superpowers requesting-code-review スキルを使って、
  [機能名]の実装をレビューしてください。
  変更内容: [概要]
  変更の意図: [なぜこのアプローチを選んだか]
  テスト済み: [確認した内容]
  ```
- **注意点:** `verification-before-completion` とは別物。verification は「完成しているか」、requesting-code-review は「マージして問題ないか」を確認する。

### Step 2: 差分レビュー

- **スキル:** `/review`
- **渡す情報:** —（差分は自動取得）
- **プロンプト例:**
  ```
  /review でこのPRの差分をレビューしてください。
  ```
- **注意点:** SQL安全性・LLMトラスト境界違反・条件分岐漏れ・テスト不足を重点的にチェックする。指摘があれば修正してから次へ進む。

### Step 3: レビュー指摘への対応

- **スキル:** `superpowers receiving-code-review`
- **渡す情報:** レビューコメント（GitHubのURLまたはテキスト）
- **プロンプト例:**
  ```
  superpowers receiving-code-review スキルを使って、
  以下のレビューコメントに対応してください。
  [レビューコメントのURL or テキスト]
  ```
- **注意点:** 指摘に疑問がある場合はこのスキルが「議論すべきか・受け入れるべきか」の判断を助ける。全指摘を機械的に受け入れない。

### Step 4: マージ・デプロイ

- **スキル:** `/land-and-deploy`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  /land-and-deploy でマージからデプロイまで実行してください。
  ```
- **注意点:** CIが通っていることを確認してから実行。マージ → CI完了待機 → デプロイ → canary確認まで自動で行う。

### Step 5: デプロイ後確認

- **スキル:** `/canary`
- **渡す情報:** 本番URL
- **プロンプト例:**
  ```
  /canary [本番URL] でデプロイ後の動作・エラーレートを監視してください。
  ```
- **注意点:** `/land-and-deploy` に canary 確認が含まれる場合は不要。手動デプロイ後に単独で実行する場合に使う。

---

## 5. 定期的な品質チェック

> 振り返り → セキュリティ監査 → パフォーマンス計測 → QAレポート → 学習記録

### Step 1: 振り返り（週次・スプリント単位）

- **スキル:** `/retro`
- **渡す情報:** 対象期間（任意）
- **プロンプト例:**
  ```
  /retro で直近のコミット履歴・作業パターン・コード品質を分析してください。
  ```
- **注意点:** コミット履歴・作業パターン・コード品質メトリクスを分析し、改善ポイントを提示する。週次での実行が推奨。

### Step 2: セキュリティ監査

- **スキル:** `/cso`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  /cso でこのリポジトリのセキュリティ監査を実行してください。
  ```
- **注意点:** OWASP Top 10・STRIDE・シークレット漏洩・依存関係サプライチェーンを横断的に検査する。月次または大きな変更後に実行。

### Step 3: パフォーマンス計測

- **スキル:** `/benchmark`
- **渡す情報:** 計測対象URL・比較基準
- **プロンプト例:**
  ```
  /benchmark [URL] でページロード時間・Core Web Vitalsのベースラインを計測してください。
  ```
- **注意点:** 初回実行でベースラインを確立し、以降はそのベースラインと比較して回帰を検出する。新機能リリース前後での比較が特に有効。

### Step 4: QAレポート

- **スキル:** `/qa-only`
- **渡す情報:** 確認対象URL・テストシナリオ
- **プロンプト例:**
  ```
  /qa-only [URL] で主要ユーザーフローを一通り確認し、レポートを作成してください。
  ```
- **注意点:** `/qa`（バグ修正まで実行）と違い、`/qa-only` は発見のみでコードを変更しない。品質の現状把握や、修正を別セッションに持ち越したい場合に使う。

### Step 5: 学習の記録

- **スキル:** `/learn`
- **渡す情報:** 今回の品質チェックで得た知見・判断
- **プロンプト例:**
  ```
  /learn で今回の品質チェックで得た知見を記録してください。
  発見した問題: [内容]
  対応方針: [内容]
  次回への改善点: [内容]
  ```
- **注意点:** プロジェクト固有の知見をgstackのlearningsとして永続化する。次回以降のQA・設計判断に自動参照される。

---

## 6. リファクタリング

> スコープ設計 → 実装計画 → ブランチ分離 → 実装 → 回帰確認 → デプロイ

### Step 1: スコープ・方針の設計

- **スキル:** `superpowers brainstorming` 🔁 writing-plans
- **渡す情報:** リファクタリング対象・現状の問題点・変えてはいけない外部仕様
- **プロンプト例:**
  ```
  superpowers brainstorming スキルを使って、以下のリファクタリング方針を設計してください。
  対象: [ファイル名 / モジュール名]
  問題: [責務が混在している / 命名が不明瞭 / など]
  制約: [外部APIの仕様は変えない / DBスキーマは変えない]
  ```
- **注意点:** 「なんとなく綺麗にする」ではなく、解決する問題を明確にしてから始める。スコープが広い場合は brainstorming で分割を提案させる。

### Step 2: 実装計画確認

- **スキル:** `superpowers writing-plans`（Step 1から自動起動）
- **渡す情報:** —（Step 1 の出力から自動引き継ぎ）
- **プロンプト例:** —（自動起動のため不要）
- **注意点:** 計画ファイルに「何を変えないか」を明記させる（ブロッカーになるタスクが明示されているか確認）。機能追加ゼロ・動作変更ゼロが原則。

### Step 3: ブランチ分離

- **スキル:** `superpowers using-git-worktrees`
- **渡す情報:** フィーチャーブランチ名
- **プロンプト例:**
  ```
  superpowers using-git-worktrees スキルを使って、
  refactor/[対象名] ブランチで作業できる環境を用意してください。
  ```
- **注意点:** 進行中の機能開発ブランチと混在させない。worktreeで独立させることでレビュー時の差分が明確になる。

### Step 4: 実装（既存テストをガードレールに）

- **スキル:** `superpowers executing-plans`
- **渡す情報:** 計画ファイルのパス
- **プロンプト例:**
  ```
  superpowers executing-plans スキルを使って、
  docs/superpowers/plans/[plan-file].md を実行してください。
  各ステップ後に既存テストが通ることを確認しながら進めてください。
  ```
- **注意点:** リファクタリング中に新しいテストを書く必要はほぼない。既存テストが壊れたら即座に止まること。

### Step 5: 回帰確認

- **スキル:** `superpowers verification-before-completion` → `/qa`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  superpowers verification-before-completion スキルを使って、
  リファクタリング前後で動作が変わっていないことを確認してください。
  ```
- **注意点:** UIを持つ場合は `/qa` でユーザーフローも確認する。「コードは綺麗になったが画面が壊れた」を防ぐ。

### Step 6: PR作成・デプロイ

- **スキル:** `superpowers requesting-code-review` → `/ship` → `/land-and-deploy`
- **渡す情報:** —（特になし）
- **プロンプト例:**
  ```
  superpowers requesting-code-review スキルを使って、
  リファクタリングの内容をレビューしてください。
  変更内容: [何をリファクタリングしたか]
  変更の意図: [解決した問題]
  テスト済み: [確認した内容]
  ```
- **注意点:** PRタイトルに `refactor:` プレフィックスを明記。PR本文に「変えたこと・変えていないこと」を両方記載する。
