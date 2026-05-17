# Claude Code × Codex 協調ワークフロー設計

- 日付: 2026-05-17
- 対象リポジトリ: `~/dotfiles`（macOS dotfiles 管理）
- 目的: Claude Code のコンテキスト使用量を削減しつつ、プロダクト開発の精度を維持する

## 背景

Claude Code は対話・判断・編集に優れる一方、大量読み込み（巨大ファイル・ログ・横断検索）でコンテキストを消費しやすい。
OpenAI の `codex` CLI を「コンテキスト軽量化エンジン」「セカンドオピニオン」として組み合わせることで、Claude Code の判断品質を保ちながらコンテキスト消費を抑える。

gstack 経由で `/codex` スキル（review / challenge / consult の 3 モード）は導入済み。本設計はその上にトリガー条件と運用ルールを定義する。

## 役割分担

```
                ┌─────────────────────────────────┐
                │       Claude Code (主)          │
                │  ・対話・判断・編集・統合           │
                │  ・plan / spec 作成              │
                │  ・最終 commit / PR              │
                └──────────┬──────────────────────┘
                           │
       ┌───────────┬───────┴────────┬──────────────┐
       ▼           ▼                ▼              ▼
   [A] 読込委譲  [B] 限定実装    [C] レビュー   [D] 相談
   /codex       codex exec      /codex review  /codex consult
   consult      (限定)
```

- **Claude Code**: 判断・統合・対話の中枢。Codex の出力を吟味して最終決定。
- **Codex [A]**: 読み込みオフロード（コンテキスト節約の主役）
- **Codex [B]**: 限定的な並列実装（スコープ完全独立の機械的タスクのみ）
- **Codex [C]**: レビュー（品質ゲート）
- **Codex [D]**: 相談（判断のセカンドオピニオン）

## トリガー条件

### [A] 読込委譲 → `/codex consult`

以下のいずれかで発動し、要約のみを Claude Code に返す:

- 単一ファイル > 1000 行
- 横断検索の結果が > 5 ファイル かつ 合計 > 2000 行見込み
- ログ解析（行数問わず）
- 「アーキテクチャ全体把握」系の依頼

NOT 発動:
- 数百行以下の通常ファイル
- 特定の関数定義を 1 箇所探すだけのケース

Codex への依頼フォーマット:
> 「以下を読み、{目的}に関して 200 行以内で要約してください。参照箇所は file:line 形式で記載してください。」

### [B] 限定実装委譲 → `codex exec`（Bash 経由）

機械的かつ独立スコープに限定:
- 型エラー > 10 箇所の一括修正
- import 整理・リネーム・format 系の大量修正
- 既存実装に対する単純なユニットテスト追加

絶対 NOT 発動:
- 設計判断を含む実装
- デバッグ（→ `/investigate`）
- 仕様が曖昧なもの（→ `superpowers:brainstorming` に戻す）

委譲後は **必ず `/codex review` または `/review` でゲート**してから commit。

### [C] レビュー → `/codex review`

必須:
- `/ship` 前
- 差分 > 200 行
- auth / 認証 / トークン / migration / schema 変更
- ユーザーからレビュー依頼

### [D] 相談 → `/codex consult`

Claude Code が判断に迷ったら自発的に提案:
- 実装アプローチが 2 つ以上で迷う
- デバッグ仮説が 3 つ以上に分岐
- 既存コードの設計意図が不明
- ユーザーから「どう思う？」と問われた

相談時のフォーマット:
> 「以下の選択肢で迷っています。{制約}を踏まえて推奨を教えてください:
> - 案 A: ...
> - 案 B: ...」

### 呼び出し方法の対応

| 用途 | コマンド | 理由 |
|---|---|---|
| A 読込 / D 相談 | `/codex consult` | セッション継続性あり・対話可能 |
| B 限定実装 | `codex exec "..."` (Bash 経由) | 非対話・diff 返却に向く |
| C レビュー | `/codex review` | gstack 既存ワークフロー完成 |

## CLAUDE.md への統合

`~/.claude/CLAUDE.md`（dotfiles symlink 経由）に新規セクション `## Codex Offload Rules` を `## gstack` の直下に追加する。Skill Routing 表からは参照リンクで連携。

追加内容は本設計書「トリガー条件」セクションを CLAUDE.md 向けに簡潔化したもの。詳細は実装計画フェーズで確定する。

追加しないもの（YAGNI）:
- フック自動化（フックはブロック用途であり委譲ロジックには不向き）
- 新規スキル作成（既存 `/codex` で足りる）
- `settings.json` への permission 追加（動作確認後に必要なら後追い）

## 前提条件・セットアップ

### 必要なもの

| 項目 | 状態 | 対応 |
|---|---|---|
| `codex` CLI 本体 | 未インストール | `.Brewfile` に追加 |
| 認証 | 未設定 | 初回 `codex login`（ChatGPT Business 契約を使用） |
| gstack `/codex` スキル | 導入済み | 追加作業なし |
| CLAUDE.md ルール | 未記載 | 本設計で追加 |

### dotfiles への変更点

| ファイル | 変更内容 |
|---|---|
| `.Brewfile` | `brew "codex"` 1 行追加 |
| `.claude/CLAUDE.md` | `## Codex Offload Rules` セクション追加 |
| `~/.claude/CLAUDE.md` への symlink | 既存 `.claude/setup.sh` が処理済 |

### セットアップ手順（ユーザー実行）

```sh
brew bundle --file=$HOME/.Brewfile  # codex CLI 取得
codex login                          # ChatGPT Business で認証
codex --version                      # 動作確認
```

## 失敗ケース・運用ルール

### 失敗モードと対処

| 失敗モード | 対処 |
|---|---|
| Codex 要約が不正確 / 重要箇所欠落 (A) | コード変更直前に該当 file:line を Claude が直接 Read で再確認 |
| Codex 実装に bug (B) | `/codex review` or `/review` を必ず通し、fail なら Claude が修正 |
| Codex の意見が間違い (C/D) | あくまで「意見」として扱い、Claude が判断主体 |
| codex CLI 起動失敗 / 認証切れ | exit code ≠ 0 で Claude 直接実行へフォールバック、ユーザーに報告 |
| Codex 応答が遅い / タイムアウト | 60 秒目安で切り上げ、Claude 直接実行へ切替 |

### 信頼境界

**Codex の出力をそのままコミットしない。Claude が必ず吟味する。**

| 種別 | 信頼レベル | 確認義務 |
|---|---|---|
| A 要約 | 中 | コード変更前に該当箇所を直接 Read |
| B 実装 diff | 低 | `/codex review` 必須、テスト実行必須 |
| C レビュー指摘 | 中 | Claude が妥当性判定して採否決定 |
| D 相談意見 | 中 | Claude 案と並列提示、ユーザーが選択 |

### ループ防止

- 1 タスクで `/codex consult` は最大 2 回まで。3 回目は人間判断を仰ぐ。
- 「Codex に聞いた結果さらに Codex に聞きたくなる」連鎖は禁止。

### ユーザー可視化

Codex 委譲時は必ず 1 行で報告:

```
[Codex委譲A] xxxxx.log (3200 行) を要約依頼します
[Codex委譲C] PR 差分 (450 行) を /codex review に出します
[Codex相談D] アプローチ A/B で迷っているため /codex consult で意見取得
```

### Skill Routing との整合

既存 `## Skill Routing` の各シーンと Codex Offload Rules は並列適用:

| シーン | Codex 委譲が発動しうるフェーズ |
|---|---|
| 新機能開発 | brainstorming(D) → writing-plans(A 大規模時) → TDD → 完了前(C) |
| バグ修正 | systematic-debugging(D 仮説分岐時) → ログ解析(A) → 完了前(C) |
| PR レビュー | `/review` と並列で `/codex review` (C) |
| デプロイ | `/ship` 内で `/codex review` 必須 (C) |

## 効果測定

1 ヶ月運用後の retro で以下を確認:
- Codex 委譲回数 / Claude 直接実行回数 の比率
- コンテキスト消費の体感変化
- 委譲後の手戻り（Codex 出力の不正確さに起因する修正）の有無
- トリガー閾値（1000 行 / 5 ファイル / 2000 行 / 200 行）の妥当性

数値が想定とズレた場合、CLAUDE.md の閾値を調整する。

## 非ゴール

- Claude Code を Codex に置き換えること
- Codex を「実装の主力」にすること（B は限定用途）
- 全自動委譲（人間または Claude の判断を介する）
- 他言語モデル（Gemini など）の併用

## 次ステップ

1. 本設計書のユーザーレビュー
2. `superpowers:writing-plans` で実装計画を作成
3. 計画に従って `.Brewfile` と `.claude/CLAUDE.md` を更新
4. ユーザー側で `brew bundle` と `codex login` を実行
5. 動作確認後、運用開始
