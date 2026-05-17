# Claude Code × Codex 協調ワークフロー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code のコンテキスト使用量を削減しつつ精度を維持するため、`codex` CLI と gstack `/codex` スキルを協調動作させるルールを dotfiles に組み込む。

**Architecture:** 設定ファイルへの最小差分のみ。`.bin/.Brewfile` に `codex` パッケージ 1 行追加、`.claude/CLAUDE.md` に `## Codex Offload Rules` セクション追加、Skill Routing セクションから参照リンクを追加。フック・新規スキル・permission 変更は行わない。

**Tech Stack:** Homebrew (codex CLI 配布), Markdown (CLAUDE.md), gstack `/codex` スキル（既存）

**Spec:** [`docs/superpowers/specs/2026-05-17-claude-codex-workflow-design.md`](../specs/2026-05-17-claude-codex-workflow-design.md)

---

## File Structure

このプランで触るファイル：

| ファイル | 役割 | 変更種別 |
|---|---|---|
| `.bin/.Brewfile` | Homebrew パッケージ管理（symlink で `~/.Brewfile`） | Modify: 1 行追加 |
| `.claude/CLAUDE.md` | Claude Code グローバル設定（symlink で `~/.claude/CLAUDE.md`） | Modify: 新規セクション + 参照リンク |

変更しないもの：
- `.claude/settings.json`（permissions は動作確認後に必要なら追加）
- `.claude/hooks/`（フックは委譲には不向き）
- `.claude/setup.sh`（既存 symlink 機構で十分）
- `mise/`（codex はバイナリ、ランタイム管理外）

---

## Task 1: `.bin/.Brewfile` に codex を追加

**Files:**
- Modify: `/Users/kado/dotfiles/.bin/.Brewfile:8`

**Context:** Brewfile は `.bin/link.sh` 経由で `~/.Brewfile` に symlink される。`.bin/.Brewfile` の `brew` セクションはおおむねアルファベット順。`codex` は `circleci` (line 8) と `coreutils` (line 9) の間に挿入。

- [ ] **Step 1: ブランチを作成**

```bash
cd /Users/kado/dotfiles
git checkout feat/codex-workflow-design || git checkout -b feat/codex-workflow-design
git branch --show-current
```

Expected: `feat/codex-workflow-design`

- [ ] **Step 2: `.Brewfile` を編集**

`/Users/kado/dotfiles/.bin/.Brewfile` の line 8 (`brew "circleci"`) の直後に以下を追加：

```ruby
brew "codex"             # OpenAI Codex CLI (Claude Code との協調動作用)
```

期待される行（Edit ツールを使用）:

old_string:
```
brew "circleci"          # CircleCI コマンド
brew "coreutils"         # mise や Ruby の bundle install でも必要とするライブラリを含む。
```

new_string:
```
brew "circleci"          # CircleCI コマンド
brew "codex"             # OpenAI Codex CLI (Claude Code との協調動作用)
brew "coreutils"         # mise や Ruby の bundle install でも必要とするライブラリを含む。
```

- [ ] **Step 3: 変更を確認**

```bash
grep -n "codex" /Users/kado/dotfiles/.bin/.Brewfile
```

Expected:
```
9:brew "codex"             # OpenAI Codex CLI (Claude Code との協調動作用)
```

- [ ] **Step 4: コミット**

```bash
cd /Users/kado/dotfiles
git add .bin/.Brewfile
git commit -m "$(cat <<'EOF'
chore(brew): add codex CLI for Claude Code coordination

Adds OpenAI Codex CLI to .Brewfile so it can be managed alongside other
development tools. Required by the Codex Offload Rules in CLAUDE.md.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -1
```

Expected: `chore(brew): add codex CLI for Claude Code coordination`

---

## Task 2: `.claude/CLAUDE.md` に `## Codex Offload Rules` セクションを追加

**Files:**
- Modify: `/Users/kado/dotfiles/.claude/CLAUDE.md` (between `## gstack` and `## Skill Routing`)

**Context:** 既存セクション順序は `## gstack` (line 67) → `## Skill Routing` (line 73)。新セクションはこの間（line 72 と 73 の間）に挿入する。

- [ ] **Step 1: 挿入位置を確認**

```bash
grep -n "^## " /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected: `## gstack` と `## Skill Routing` が連続している（間に他のセクションなし）。

- [ ] **Step 2: CLAUDE.md を編集**

`/Users/kado/dotfiles/.claude/CLAUDE.md` の `## gstack` セクションと `## Skill Routing` セクションの間に以下を挿入する。

old_string:
```
## gstack
- すべてのウェブブラウジングに gstack の `/browse` スキルを使用すること。
- `mcp__claude-in-chrome__*` ツールは絶対に使用しないこと.

---

## Skill Routing
```

new_string:
```
## gstack
- すべてのウェブブラウジングに gstack の `/browse` スキルを使用すること。
- `mcp__claude-in-chrome__*` ツールは絶対に使用しないこと.

---

## Codex Offload Rules

Claude Code のコンテキストを節約しつつ精度を保つため、以下の条件で gstack の `/codex` スキル（または `codex exec`）へ委譲する。判断時は本セクションを必ず参照すること。

### [A] 読込委譲 → `/codex consult`
以下のいずれかに該当する読み込みは Codex に依頼し、要約のみ受け取る:
- 単一ファイル > 1000 行
- 横断検索の結果が > 5 ファイル かつ 合計 > 2000 行見込み
- ログ解析（行数問わず）
- 「アーキテクチャ全体を把握」系の依頼

Codex への依頼フォーマット:
> 「以下を読み、{目的}に関して 200 行以内で要約してください。参照箇所は file:line 形式で記載してください。」

NOT 発動:
- 数百行以下の通常ファイル（直接 Read のほうが正確）
- 特定の関数定義を 1 箇所探すだけ（grep で十分）

### [B] 限定実装委譲 → `codex exec`（Bash 経由）
**機械的かつ独立スコープ**の場合のみ:
- 型エラー > 10 箇所の一括修正
- import 整理・リネーム・format 系の大量修正
- 既存実装に対する単純なユニットテスト追加

絶対 NOT:
- 設計判断を含む実装
- デバッグ（→ `/investigate`）
- 仕様が曖昧なもの（→ `superpowers:brainstorming`）

委譲後は **必ず `/codex review` または `/review` でゲート**してから commit。

### [C] レビュー → `/codex review`
以下では **必須**:
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

### 運用ルール
- **信頼境界**: Codex 出力はそのままコミットしない。要約は該当 file:line を直接 Read で再確認、実装 diff は `/codex review` 必須。
- **ループ防止**: 1 タスクで `/codex consult` は最大 2 回。3 回目は人間判断を仰ぐ。
- **フォールバック**: `codex` CLI が exit code ≠ 0、または 60 秒以内に応答が無い場合は Claude 直接実行へ切り替え、原因をユーザーへ報告。
- **可視化**: Codex 委譲時は 1 行で報告（例: `[Codex委譲A] xxx.log (3200 行) を要約依頼します`）。

---

## Skill Routing
```

- [ ] **Step 3: Skill Routing 表に Codex 参照を追記**

`### シーン判定表` の下、表の直後に注記を追加する。

old_string:
```
| 定期品質チェック | retro / 振り返り / セキュリティ監査 | `/retro` or `/cso` | — |

### 次ステップ提示テンプレート
```

new_string:
```
| 定期品質チェック | retro / 振り返り / セキュリティ監査 | `/retro` or `/cso` | — |

> **Codex 連携**: 各シーンで [Codex Offload Rules](#codex-offload-rules) を参照し、読込 (A) / 限定実装 (B) / レビュー (C) / 相談 (D) を適切に委譲すること。

### 次ステップ提示テンプレート
```

- [ ] **Step 4: 変更を確認**

```bash
grep -n "^## \|^### " /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected: `## Codex Offload Rules` が `## gstack` と `## Skill Routing` の間に存在。

```bash
grep -c "Codex Offload Rules" /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected: `2`（セクションヘッダ 1 + Skill Routing からの参照 1）

- [ ] **Step 5: コミット**

```bash
cd /Users/kado/dotfiles
git add .claude/CLAUDE.md
git commit -m "$(cat <<'EOF'
feat(claude): add Codex Offload Rules section

Defines when and how to delegate to the codex CLI (read offload, limited
impl, review, consult) to reduce Claude Code context usage while
maintaining development precision. Cross-referenced from Skill Routing.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git log --oneline -1
```

Expected: `feat(claude): add Codex Offload Rules section`

---

## Task 3: symlink と CLAUDE.md 反映を検証

**Files:** (read-only verification)

**Context:** `.claude/setup.sh` が `~/.claude/CLAUDE.md` への symlink を作成済みのはず。再実行は不要、symlink が壊れていないかだけ確認。

- [ ] **Step 1: symlink を確認**

```bash
ls -la ~/.claude/CLAUDE.md
```

Expected: `/Users/kado/dotfiles/.claude/CLAUDE.md` への symlink になっている。

- [ ] **Step 2: 反映を確認**

```bash
grep -n "Codex Offload Rules" ~/.claude/CLAUDE.md
```

Expected: 2 行ヒット（セクション + 参照リンク）。

- [ ] **Step 3: Brewfile symlink 確認**

```bash
ls -la ~/.Brewfile
grep -n "codex" ~/.Brewfile
```

Expected: `/Users/kado/dotfiles/.bin/.Brewfile` への symlink、`brew "codex"` 行が存在。

> symlink が壊れている場合は `cd /Users/kado/dotfiles && sh .bin/link.sh && sh .claude/setup.sh` を再実行。

---

## Task 4: PR を作成

**Files:** (no file changes)

**Context:** `feat/codex-workflow-design` ブランチには既に spec のコミット (`c1b08c6`) と本プランの commit 2 件が積まれている状態。

- [ ] **Step 1: ブランチ状態を確認**

```bash
cd /Users/kado/dotfiles
git status
git log main..HEAD --oneline
```

Expected: 3 つの commit (spec 追加、Brewfile 追加、CLAUDE.md 追加)、working tree clean。

- [ ] **Step 2: push**

```bash
git push -u origin feat/codex-workflow-design
```

Expected: push 成功。

- [ ] **Step 3: PR を作成**

```bash
gh pr create --title "feat: Claude Code × Codex 協調ワークフロー" --body "$(cat <<'EOF'
## Summary
- Claude Code のコンテキスト節約 × 精度維持を目的に、`codex` CLI と gstack `/codex` スキルを協調動作させるルールを追加
- `.bin/.Brewfile` に `codex` パッケージを追加
- `.claude/CLAUDE.md` に `## Codex Offload Rules` セクションを新設（読込委譲 A / 限定実装 B / レビュー C / 相談 D の 4 パターン）
- Skill Routing 表から新セクションへの参照リンクを追加

## 設計書
`docs/superpowers/specs/2026-05-17-claude-codex-workflow-design.md`

## Test plan
- [ ] `brew bundle --file=$HOME/.Brewfile` で `codex` がインストールされる
- [ ] `codex login` で ChatGPT Business 認証が通る
- [ ] `codex --version` が成功する
- [ ] `~/.claude/CLAUDE.md` に新セクションが反映されている
- [ ] 新規 Claude Code セッションで `/codex consult` などの委譲が CLAUDE.md の閾値に従って提案される

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL が返る。

- [ ] **Step 4: CI ステータス確認**

```bash
gh pr checks
```

Expected: CI が無い場合は "no checks reported"。CI がある場合は pass を待つ。

---

## Task 5: ユーザー側セットアップ手順を提示

**Files:** (no file changes — instructions only)

**Context:** PR マージ後、ユーザーは codex CLI のインストールと認証を手動実行する。

- [ ] **Step 1: ユーザーに以下手順を伝える**

PR マージ後、以下を実行してください:

```bash
# 1. Homebrew 反映
brew bundle --file=$HOME/.Brewfile

# 2. ChatGPT Business で認証（ブラウザが開く）
codex login

# 3. 動作確認
codex --version
codex exec "echo hello world" 2>&1 | head -5
```

期待結果:
- `codex` バージョンが表示される
- `codex exec` が成功し、ストリーミング応答が返る

問題が出た場合:
- `codex login` がブラウザを開かない → `codex login --help` で代替手順確認
- `brew install codex` が失敗 → `brew search codex` で formula 名確認、必要なら Brewfile を修正

---

## Self-Review

仕様カバレッジ:
- ✅ 役割分担 4 パターン (A/B/C/D) → Task 2 の CLAUDE.md セクションでカバー
- ✅ トリガー条件・閾値 → Task 2 でカバー
- ✅ CLAUDE.md 統合（gstack 直下） → Task 2 で挿入位置明示
- ✅ Skill Routing 連携 → Task 2 Step 3 で参照リンク追加
- ✅ `.Brewfile` への codex 追加 → Task 1
- ✅ 認証方針（ChatGPT Business） → Task 5
- ✅ symlink 検証 → Task 3
- ✅ 信頼境界・ループ防止・フォールバック・可視化 → Task 2 の運用ルール subsection
- ✅ 非ゴール（フック・新規スキル・permission） → File Structure で除外明記

プレースホルダー: 無し（全 step に具体的なコマンド・期待値・コード）

型/命名の一貫性:
- `Codex Offload Rules` セクション名は spec と plan で一致
- 4 パターン A/B/C/D の名称も spec と一致
- ファイルパスは絶対パスで統一
