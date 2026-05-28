# Karpathy Coding Discipline 追加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.claude/CLAUDE.md` に Karpathy 由来の `Coding Discipline` セクションを追加し、`Working Principles` から重複行を削除する。

**Architecture:** 単一ファイル編集のみ。`Working Principles` 直後に新セクションを挿入し、`Working Principles` の重複行を削除する。シンボリックリンク経由で `~/.claude/CLAUDE.md` に自動反映される。

**Tech Stack:** Markdown のみ。ビルド/テストなし。

**Spec:** `docs/superpowers/specs/2026-05-22-claude-md-karpathy-design.md`

---

## File Structure

- **Modify:** `/Users/kado/dotfiles/.claude/CLAUDE.md`
  - `Working Principles` から重複行を 1 行削除
  - `Working Principles` と `Safety Rules` の間に `## Coding Discipline` セクションを挿入

他ファイルは触らない (`Surgical Changes` 原則)。

---

## Task 1: Working Principles から重複行を削除

**Files:**
- Modify: `/Users/kado/dotfiles/.claude/CLAUDE.md` (12 行目付近)

- [ ] **Step 1: 現状の Working Principles を確認**

Run:
```bash
sed -n '8,14p' /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected output:
```
## Working Principles
- 思考は英語で行い、最終的な出力は日本語とする。
  - ユーザーへの確認・質問・結果表示は、必ず日本語を使用すること。
- 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。
- 要件が曖昧な場合は推測で確定せず、質問・前提・方針・代替案を提示すること。

---
```

- [ ] **Step 2: 重複行を削除する Edit を適用**

Edit `/Users/kado/dotfiles/.claude/CLAUDE.md`:

- **old_string:**
  ```
  - 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。
  - 要件が曖昧な場合は推測で確定せず、質問・前提・方針・代替案を提示すること。
  ```
- **new_string:**
  ```
  - 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。
  ```

- [ ] **Step 3: 削除結果を検証**

Run:
```bash
sed -n '8,13p' /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected output:
```
## Working Principles
- 思考は英語で行い、最終的な出力は日本語とする。
  - ユーザーへの確認・質問・結果表示は、必ず日本語を使用すること。
- 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。

---
```

`要件が曖昧な場合は推測で確定せず...` の行が消えていること。

---

## Task 2: Coding Discipline セクションを挿入

**Files:**
- Modify: `/Users/kado/dotfiles/.claude/CLAUDE.md` (Working Principles と Safety Rules の間)

- [ ] **Step 1: 挿入位置のマーカー (区切り `---`) を確認**

Run:
```bash
grep -n '^---$' /Users/kado/dotfiles/.claude/CLAUDE.md | head -3
```

Expected: Task 1 完了後、最初の `---` は 12〜13 行目付近。次の `---` (Safety Rules の後ろ) との間に挿入する。

- [ ] **Step 2: Coding Discipline セクションを挿入する Edit を適用**

Task 1 を適用した直後のファイル状態では、Working Principles 末尾と Safety Rules の間が以下の通り:

```
- 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。

---

## Safety Rules
```

Edit `/Users/kado/dotfiles/.claude/CLAUDE.md`:

- **old_string:**
  ```
  - 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。

  ---

  ## Safety Rules
  ```
- **new_string:**
  ```
  - 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。

  ---

  ## Coding Discipline

  Karpathy の LLM コーディング原則 (<https://github.com/multica-ai/andrej-karpathy-skills>) をベースに、このリポジトリで遵守するコーディング行動を定義する。

  **Tradeoff**: これらの指針は速度よりも慎重さに寄せている。trivial なタスクでは判断で省略してよい。

  ### 1. Think Before Coding (実装前に考える)
  **推測しない。迷いを隠さない。トレードオフを明示する。**
  - 前提を明示して進める。不確かなら質問する。
  - 解釈が複数あるなら、黙って選ばず並べて示す。
  - よりシンプルな代替案があれば提示する。必要なら押し返す。
  - 不明点があれば手を止め、何が不明か言語化して質問する。

  ### 2. Simplicity First (シンプルさを優先)
  **問題を解く最小限のコード。推測は不要。**
  - 依頼されていない機能は作らない。
  - 一回しか使わないコードを抽象化しない。
  - 要求されていない `flexibility` / `configurability` を追加しない。
  - 起こりえないシナリオのエラーハンドリングは不要。
  - 200 行で書いたものが 50 行で済むなら書き直す。
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
  ```

- [ ] **Step 3: 挿入結果を検証**

Run:
```bash
grep -n '^## ' /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected output:
```
3:## Purpose
8:## Working Principles
15:## Coding Discipline
55:## Safety Rules
63:## Testing Policy
70:## Output Format for Changes
80:## Git / GitHub Rules
91:## Preferred Decision Order
94:## Compaction policy
101:## gstack
106:## Codex Offload Rules
124:## Skill Routing
```

(行番号は近似値。重要なのは `Coding Discipline` が `Working Principles` の直後・`Safety Rules` の直前に入っていること)

---

## Task 3: 全体検証

**Files:**
- Read-only: `/Users/kado/dotfiles/.claude/CLAUDE.md`, `~/.claude/CLAUDE.md`

- [ ] **Step 1: シンボリックリンクの実体確認**

Run:
```bash
ls -l ~/.claude/CLAUDE.md
```

Expected: `~/.claude/CLAUDE.md -> /Users/kado/dotfiles/.claude/CLAUDE.md` (シンボリックリンクであること)

もしシンボリックリンクでない場合は `.claude/setup.sh` が未実行の可能性。その場合は変更が反映されないので報告して停止する。

- [ ] **Step 2: シンボリックリンク先の内容一致を確認**

Run:
```bash
diff /Users/kado/dotfiles/.claude/CLAUDE.md ~/.claude/CLAUDE.md && echo OK
```

Expected: `OK` (差分なし)

- [ ] **Step 3: 他セクションが無変更であることを確認**

Run:
```bash
git -C /Users/kado/dotfiles diff main -- .claude/CLAUDE.md | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)' | head -80
```

Expected: 削除行 1 行 (`- 要件が曖昧な場合は推測で確定せず...`) + `## Coding Discipline` セクションの追加行のみ。Safety Rules / Testing Policy / Git / Codex / Skill Routing / gstack 由来の行が `+`/`-` に現れていないこと。

- [ ] **Step 4: Markdown 構造の健全性確認**

Run:
```bash
awk '/^```/{c++} END{print "fences:", c, "(should be even)"}' /Users/kado/dotfiles/.claude/CLAUDE.md
grep -c '^## ' /Users/kado/dotfiles/.claude/CLAUDE.md
```

Expected: コードフェンスの数が偶数 (開閉が対応)。`## ` 見出しが 12 個 (Purpose / Working Principles / Coding Discipline / Safety Rules / Testing Policy / Output Format for Changes / Git / GitHub Rules / Preferred Decision Order / Compaction policy / gstack / Codex Offload Rules / Skill Routing)。

---

## Task 4: コミット

**Files:**
- Stage only: `.claude/CLAUDE.md`
- (`.codex/config.toml` の既存変更は無関係なのでステージしない)

- [ ] **Step 1: ブランチ確認**

Run:
```bash
git -C /Users/kado/dotfiles branch --show-current
```

Expected: `docs/claude-md-karpathy-discipline` (main / master / staging でないこと)

- [ ] **Step 2: ステージ対象の限定**

Run:
```bash
git -C /Users/kado/dotfiles add .claude/CLAUDE.md
git -C /Users/kado/dotfiles status
```

Expected: `Changes to be committed:` に `.claude/CLAUDE.md` のみ。`.codex/config.toml` は `Changes not staged for commit:` に残る。

- [ ] **Step 3: コミット**

Run:
```bash
git -C /Users/kado/dotfiles commit -m "$(cat <<'EOF'
docs(claude): add Karpathy-inspired Coding Discipline section

Adds a new "Coding Discipline" section based on
multica-ai/andrej-karpathy-skills, covering Think Before Coding,
Simplicity First, Surgical Changes, and Goal-Driven Execution.
Removes the duplicate "ambiguous requirements" line from
Working Principles (now covered by Think Before Coding).
EOF
)"
```

Expected: コミット成功。pre-commit フック (`protect-main-branch.sh`) は feature ブランチなので通る。

- [ ] **Step 4: コミット内容確認**

Run:
```bash
git -C /Users/kado/dotfiles log --oneline -3
git -C /Users/kado/dotfiles show --stat HEAD
```

Expected: 最新コミットが `docs(claude): add Karpathy-inspired Coding Discipline section`。変更ファイルは `.claude/CLAUDE.md` のみ。

---

## やらないこと (Out of Scope, 再掲)

- 他セクション (Safety / Testing / Git / Codex / Skill Routing / gstack) の改稿
- プロジェクト側 `/Users/kado/dotfiles/CLAUDE.md` の変更
- `.claude/docs/CODEX_OFFLOAD.md` / `SKILL_ROUTING.md` への手入れ
- `.codex/config.toml` の既存変更へのコミット (本タスクと無関係)
- 新スキル追加・PR 作成 (PR 作成はユーザー指示後)
