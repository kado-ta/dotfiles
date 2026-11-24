---
status: in-progress
created: 2026-11-25
---

# 試験記録: PreCompact フックを消す

関連: [plan.md](plan.md)

<a name="changes"></a>

## 変えたもの

- **Claude:**
  - `claude/README.md` のフックの表から `precompact-context.sh` の行を消した。
  - `claude/SKILL_INVENTORY.md` の hooks の表から PreCompact の行を消した。
  - 削除をステージした。
- **人間（2026-11-25）:**
  - worktree の `claude/settings.json` から `"PreCompact"` の項目を消した。
  - 通常のターミナルで `claude/hooks/precompact-context.sh` を消した。
  - `jq empty` で JSON を確かめた（`OK`）。

`git diff -- claude/settings.json` は、`"PreCompact"` の 11 行の削除だけだった。

<a name="checks"></a>

## 検証（2026-11-25、Claude Code の sandbox の中）

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全 13 項目 PASS（`hook-scripts` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 93 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | exit 0 |
| `actionlint` | exit 0 |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | pass=131 fail=0 |
| `bash claude/hooks/tests/test-validate-command.sh` | pass=29 fail=0 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | pass=69 fail=0 |
| `bash claude/hooks/tests/test-ask-shared-tree-git.sh` | pass=111 fail=0 |
| `bash claude/hooks/tests/test-gh-read-token.sh` | pass=24 fail=0 |
| `bash claude/hooks/tests/test-guard-additional-dirs.sh` | pass=17 fail=0 |
| `bash claude/hooks/tests/test-guard-playwright-mcp.sh` | pass=51 fail=0 |
| `bash claude/hooks/tests/test-check-vault-note.sh` | pass=27 fail=0 skip=1（Seatbelt の部分。sandbox の中では飛ばされる） |

- フックの試験は、書き込める cwd（`$TMPDIR`）から絶対パスで実行した。
- 削除をステージする前は、`check-repo.py` の `local-paths` と shellcheck が、消したファイルを開けずに失敗した（どちらも `git ls-files` の一覧を使う）。ステージした後に、上の結果になった。
- `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh`（sandbox の外）は実行していない。`check-vault-note` は変えていない。CI がフックの試験一式を実行する。
- 新しい試験は作っていない。B では試験の対象のフックがなくなる（[plan の 6 章](plan.md#verification)）。

<a name="after-merge"></a>

## マージの後の確認（人間）

未実施。`~/dotfiles` で main を取り込んだ後、git のリポジトリで `/compact` を実行する。`PreCompact` の hook error が出ないことと、要約が作られることを確かめて、ここに記録する。
