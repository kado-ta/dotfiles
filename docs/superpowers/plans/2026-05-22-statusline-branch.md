# Statusline Branch Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.claude/scripts/statusline.sh` に「カレントディレクトリの git ブランチ名」セグメントを追加し、通常ブランチ／detached HEAD／非 git ディレクトリの3状態を仕様どおりに表示する。

**Architecture:** JSON にブランチ情報がないため、`workspace.current_dir` を CWD として `git symbolic-ref` と `git rev-parse --git-dir` を呼び、シェル変数 `GIT_BRANCH` に格納する。既存の `parts=("${CYAN}${SHORT_DIR}${RESET}")` 初期化のみを差し替えて、cwd と branch を1セグメントに連結し ` ⎇ ` で区切る。既存ロジック（jq パイプライン、`parts+=(...)`、`SEP` ループ）はそのまま流用する。

**Tech Stack:** bash, jq（既存）, git CLI（新規依存だがシステム標準）, ANSI エスケープシーケンス。

**Spec:** `docs/superpowers/specs/2026-05-22-statusline-branch-design.md`

---

## File Structure

| ファイル | 操作 | 役割 |
|---|---|---|
| `.claude/scripts/statusline.sh` | 編集 | ブランチ取得ロジック追加（`SHORT_DIR` ブロック直後）、`parts` 初期化の差し替え、ヘッダコメント更新 |

新規ファイルなし。テストはエフェメラル（インラインコマンドで実行、リポジトリにテストファイルは置かない — dotfiles リポジトリには既存テストスイートが無いため、新規導入はスコープ外）。

---

## Task 1: Implement branch segment with TDD-style smoke tests

**Files:**
- Modify: `.claude/scripts/statusline.sh:1-3`（ヘッダコメント）
- Modify: `.claude/scripts/statusline.sh:28-39`（`SHORT_DIR` ブロックと `parts` 初期化）

- [ ] **Step 1: Write the 3 smoke test cases as a single shell snippet**

下記スニペットを保存先未確定のまま一旦コピペして実行できる状態にしておく（リポジトリには置かない）。各ケースは独立して `pass`/`fail` を判定する:

```bash
# Test A: normal branch (dotfiles 自体を使う)
echo '{"workspace":{"current_dir":"'"$PWD"'"},"context_window":{"used_percentage":10}}' \
  | bash .claude/scripts/statusline.sh \
  | grep -F ' ⎇ ' >/dev/null && echo "A: PASS" || echo "A: FAIL (expected ⎇ separator)"

# Test B: non-git directory
echo '{"workspace":{"current_dir":"/tmp"},"context_window":{"used_percentage":10}}' \
  | bash .claude/scripts/statusline.sh \
  | grep -F ' ⎇ ' >/dev/null && echo "B: FAIL (no ⎇ expected)" || echo "B: PASS"

# Test C: detached HEAD (ephemeral repo)
TMPGIT=$(mktemp -d)
git -C "$TMPGIT" init -q
git -C "$TMPGIT" commit --allow-empty -m init -q
SHA=$(git -C "$TMPGIT" rev-parse HEAD)
git -C "$TMPGIT" -c advice.detachedHead=false checkout -q "$SHA"
echo '{"workspace":{"current_dir":"'"$TMPGIT"'"},"context_window":{"used_percentage":10}}' \
  | bash .claude/scripts/statusline.sh \
  | grep -F '(detached)' >/dev/null && echo "C: PASS" || echo "C: FAIL (expected '(detached)')"
rm -rf "$TMPGIT"
```

- [ ] **Step 2: Run all 3 smoke tests before any change to confirm they fail**

上記スニペットを実行する。
Expected:
```
A: FAIL (expected ⎇ separator)
B: PASS                                # まだ ⎇ を出していないので「Bが先に通る」のが正しい
C: FAIL (expected '(detached)')
```

`A` と `C` が FAIL することで「未実装」が確認できる。`B` が PASS なのは正しい（非 git で出力しない仕様は既に満たしている）。

- [ ] **Step 3: Add branch-extraction block right after the `SHORT_DIR` fallback**

`.claude/scripts/statusline.sh` の現在の line 28-29:

```bash
SHORT_DIR="${DIR/#$HOME/~}"
[ -z "$SHORT_DIR" ] && SHORT_DIR="-"
```

の直後（line 30 が空行、line 31 が `pick_color` 関数の前）に以下を挿入する:

```bash

GIT_BRANCH=""
if [ -n "$DIR" ]; then
    GIT_BRANCH=$(git -C "$DIR" symbolic-ref --short HEAD 2>/dev/null)
    if [ -z "$GIT_BRANCH" ] && git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1; then
        GIT_BRANCH="(detached)"
    fi
fi
```

実装メモ:
- `symbolic-ref --short HEAD` は通常ブランチで `refs/heads/` を取り除いた名前を返す。detached や非 git なら非ゼロ終了 + 標準エラー。
- 2段目の `rev-parse --git-dir` で git 管理下判定を行い、detached と非 git を区別する。
- `2>/dev/null` で `not a git repository` 等のエラーログを抑止する。

- [ ] **Step 4: Replace the `parts` initialization to inline the branch with a ⎇ separator**

`.claude/scripts/statusline.sh` の現在の line 38-39（既存 `parts=(...)` 初期化部分）:

```bash
SEP=" │ "
parts=("${CYAN}${SHORT_DIR}${RESET}")
```

を以下に置き換える:

```bash
SEP=" │ "
if [ -n "$GIT_BRANCH" ]; then
    parts=("${CYAN}${SHORT_DIR} ⎇ ${GIT_BRANCH}${RESET}")
else
    parts=("${CYAN}${SHORT_DIR}${RESET}")
fi
```

`SEP` の宣言位置は変えない。以降の `parts+=(...)` ロジックには手を入れない。

- [ ] **Step 5: Update the header comment to reflect new output**

`.claude/scripts/statusline.sh` の line 1-3 を:

```bash
#!/bin/bash
# Status line displaying: cwd | ctx% | 5h% | 7d% | model | effort
# Percent segments (ctx / 5h / 7d) use threshold colors;
# cwd / model / effort use fixed colors.
```

から以下に書き換える:

```bash
#!/bin/bash
# Status line displaying: cwd ⎇ branch | ctx% | 5h% | 7d% | model | effort
# Percent segments (ctx / 5h / 7d) use threshold colors;
# cwd / branch / model / effort use fixed colors.
# Branch is shown only when the current directory is inside a git repository.
```

- [ ] **Step 6: Re-run the 3 smoke tests; expect all PASS**

Step 1 のスニペットを再実行。

Expected:
```
A: PASS
B: PASS
C: PASS
```

いずれかが FAIL した場合、`statusline.sh` の編集を見直して再試行。

- [ ] **Step 7: Run the 3 PR #65 regression fixtures; expect no behavior change other than the added branch segment**

```bash
# Regression A: full input (now should also contain ⎇ + a branch name since $PWD is dotfiles)
echo '{"workspace":{"current_dir":"'"$PWD"'"},"context_window":{"used_percentage":32.4},"rate_limits":{"five_hour":{"used_percentage":12},"seven_day":{"used_percentage":45.7}},"model":{"display_name":"Opus 4.7 (1M)"},"effort":{"level":"xhigh"}}' \
  | bash .claude/scripts/statusline.sh

# Regression B: rate_limits / effort missing
echo '{"workspace":{"current_dir":"'"$PWD"'"},"context_window":{"used_percentage":85},"model":{"display_name":"Sonnet 4.6"}}' \
  | bash .claude/scripts/statusline.sh

# Regression C: empty object
echo '{}' | bash .claude/scripts/statusline.sh
```

Expected:
- A: `~/dotfiles ⎇ <現在のブランチ> │ ctx 32% │ 5h 12% │ 7d 45% │ Opus 4.7 (1M) │ xhigh` （色付き）
- B: `~/dotfiles ⎇ <現在のブランチ> │ ctx 85% │ Sonnet 4.6` （85% は YELLOW）
- C: `- │ ctx -` （`DIR` 空のため git 呼び出しスキップ、既存挙動と同一）

A と B でブランチセグメントが追加され、それ以外のセグメント順・色は PR #65 のレビュー時と同一であることを目視確認する。C は完全に同一出力（`-` のみ、`⎇` 無し）であることを確認。

- [ ] **Step 8: Stage and commit only the statusline.sh change**

`.claude/settings.json` や `.codex/config.toml` が未ステージで残っていることがあるが、それらは PR #65 のスコープ外なので **明示的にファイル名指定で stage する**:

```bash
git add .claude/scripts/statusline.sh
git status -sb
git commit -m "$(cat <<'EOF'
feat(claude): show current git branch on statusline

Add a branch segment that appears immediately after cwd, separated by
` ⎇ `. Source the branch via `git -C "$DIR" symbolic-ref --short HEAD`
with a `rev-parse --git-dir` fallback to distinguish detached HEAD
(rendered as `(detached)`) from non-git directories (segment omitted).

Spec: docs/superpowers/specs/2026-05-22-statusline-branch-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

コミット後の確認:

```bash
git log -1 --stat
```

Expected: `.claude/scripts/statusline.sh` が1ファイルだけ変更されていること。

---

## Self-Review Checklist

実装完了後に以下を1分で確認する:

1. **Spec coverage:**
   - 通常ブランチ表示 → Step 3-4 + Step 6 Test A
   - `(detached)` 表示 → Step 3 + Step 6 Test C
   - 非 git 省略 → Step 3 + Step 6 Test B
   - 位置（cwd 直後） → Step 4
   - 色（CYAN、cwd と同色）→ Step 4
   - ` ⎇ ` 区切り → Step 4 + Step 5
   - ヘッダコメント更新 → Step 5
   - エラー処理（`2>/dev/null`）→ Step 3
   - 既存3パターンの退行なし → Step 7

2. **No placeholders:** すべてのステップに具体的なコマンド／コード／期待出力が書かれていること。

3. **Type consistency:** `GIT_BRANCH` という変数名が Step 3, 4, ヘッダコメントで一貫している。`⎇` という記号も同じ U+2387 を使っている。
