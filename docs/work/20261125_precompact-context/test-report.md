---
status: done
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

2026-11-25 に、[plan の 5.2](plan.md#plan-b-after-merge) のとおりに確かめた。`/compact` は人間が実行し、会話の記録と設定は Claude が sandbox の中で読んだ。

- [x] 通常のターミナルで main を取り込む
- [x] 新しいセッションの git のリポジトリで `/compact` を実行し、`PreCompact` の hook error が出ないことと、要約が作られることを確かめる

結果:

- **取り込み:** PR #111 は d61dccb でマージされた。そのとき `~/dotfiles` は別の作業のブランチ（`feat/atuin-ctrl-r`）だったので、PR #112 のマージの後に main へ切り替えて取り込んだ。取り込んだ後の状態は次のとおり。
  - `~/dotfiles` は main（7b14ea3。d61dccb を含む）で、変更はない。
  - `~/.claude/hooks/precompact-context.sh` はない。
  - `~/.claude/settings.json` に `PreCompact` のキーはない。
- **`/compact`:** `~/dotfiles` の新しいセッションで 2 回実行した。
  - 1 回目は `Not enough messages to compact.` と出て、圧縮されなかった。
  - 2 回目（手動）は圧縮が終わり、要約が作られた（78,415 → 18,669 トークン、26.6 秒）。Claude が見た出力は `Compacted (ctrl+o to see full summary)` だけだった。
- **会話の記録:** このセッションの記録（`~/.claude/projects/` の JSONL）にあるフックの結果は、SessionStart の `hook_success` と `hook_additional_context` の各 2 件だけだった。PreCompact の結果は、成功も失敗もなかった。
- **設定:** `~/.claude/settings.json`・`~/dotfiles/.claude/settings.json`・`~/dotfiles/.claude/settings.local.json` のどれにも `hooks.PreCompact` はなかった。
