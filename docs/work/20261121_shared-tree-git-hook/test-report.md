---
status: in-progress
created: 2026-11-21
---

# 同じ作業ツリーの別セッションを知らせるフック 試験記録

関連: [design.md](design.md)、[plan.md](plan.md)

<a name="automated"></a>

## 1. 自動のテストと検査

Claude Code の sandbox の中で、worktree（`feat/shared-tree-git-hook`）で実行した。フックのテストは、書き込める cwd（`$TMPDIR`）から絶対パスで実行した。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | Ran 83 tests、OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 出力なし、終了コード 0 |
| `actionlint` | 出力なし、終了コード 0 |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | pass=94 fail=0 |
| `bash claude/hooks/tests/test-validate-command.sh` | pass=29 fail=0 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | pass=66 fail=0 |
| `bash claude/hooks/tests/test-ask-shared-tree-git.sh` | pass=91 fail=0（`SKIP real ps`） |
| `bash claude/hooks/tests/test-gh-read-token.sh` | pass=24 fail=0 |
| `bash claude/hooks/tests/test-guard-additional-dirs.sh` | pass=17 fail=0 |
| `bash claude/hooks/tests/test-guard-playwright-mcp.sh` | pass=49 fail=0 |

人間が普段の端末（sandbox の外）で `bash claude/hooks/tests/test-ask-shared-tree-git.sh` を実行した結果は pass=94 fail=0 で、`SKIP` は出なかった。実物の ps・kill を使う 3 件（生きているセッション、テストのシェル＝フックの祖先、終了したセッション）も通った。記録 60 件のテストは 0 秒だった。

テストが変更を検出できることは、フックの写しに変異を入れて確かめた（対象の照合・ツリーの比較・`TZ=UTC`・空白の正規化・祖先の除外・`sessionId` の除外・5 件の上限のそれぞれを外すと FAIL になり、`exit 0` を `exit 2` にすると全件 FAIL になる）。

<a name="speed"></a>

## 2. 速さ

sandbox の中で、`/bin/kill`・`/bin/ps` を偽物に置き換えたフックを 20 回ずつ動かした。

| 入力 | 1 回あたり |
| --- | --- |
| `git status`（対象外） | 18.5 ms |
| `git switch main`（対象。同じツリーの記録 60 件、うち生きているのは 1 件） | 703.5 ms |

- 対象のコマンドは、同じツリーの記録ごとに `tree_root` のサブシェルと `kill` の起動がかかる。sandbox の中はプロセスの起動が遅めに出る。普段の端末のテストでは、記録 60 件の場合が 0 秒（秒の単位）だった。
- 2026-11-21 の `~/.claude/sessions` の記録は 23〜26 件で、最古は 11/16 だった。終了したセッションの記録が際限なく増える様子はない。

<a name="manual"></a>

## 3. 手動の確認（design 5.9）

worktree の `.claude/settings.local.json` にだけフックを登録し、worktree で起動したセッションで確かめた。確認はどれも拒否し、ブランチは動かしていない。

| 項目 | CLI | VS Code（拡張機能のパネル） | desktop app |
| --- | --- | --- | --- |
| 1. 記録の `procStart` と `TZ=UTC LC_ALL=C /bin/ps -o lstart=` の一致 | 21 件すべて一致 | 3 件すべて一致 | 2 件すべて一致 |
| 2. 自分を別のセッションとして数えない | OK | OK | OK |
| 3. `/clear` の後・`--resume`（開き直し）の後も数えない | OK | OK | OK |
| 4. 別のセッションがあると確認が出て、文面に載る | OK | OK | OK |
| 5. auto mode で、allow の `Bash(git checkout *)` に当たる `git checkout -b` でも確認が出る | OK | OK | OK |

- 1 は、生きているすべてのセッション（起動元とディレクトリを問わず 26 件）を、普段の端末で比べた。空白の正規化の後で、すべて一致した。
- 2〜5 は、このとき worktree にいた別の CLI のセッション（実装を進めたセッション）を「別のセッション」として使い、文面にそのセッションだけが載り、確認したセッション自身が載らないことを見た。
- `--resume` の後の CLI のセッションで `git switch -c tmp/hook-check` を実行したときの文面:

  ```text
  同じ作業ツリー（~/dotfiles/.claude/worktrees/shared-tree-git-hook）で、別の Claude セッションが動いています: CLI（idle、11/21 16:00 開始）、VS Code（waiting、11/21 16:15 開始）、desktop app（waiting、11/21 16:19 開始）。このコマンドは、そのセッションのブランチや未コミットの変更に影響します。そのセッションが作業中なら、終わるのを待つか、別の作業ツリーで作業してください。
  ```

  同じ worktree の VS Code と desktop app のセッションが見え、確認したセッション自身（16:09 開始の CLI）は載っていない。`~/dotfiles` で動いていたセッション（CLI・desktop app）は載っておらず、`claude -w` の worktree が別の作業ツリーとして扱われている（5.9 の 4 の後半）。
- 2・3 で、どちらの仕組み（`sessionId` の一致か、祖先の pid か）で除外されたかは区別していない。

<a name="observations"></a>

## 4. 気づいたこと

- **再開しても `sessionId` は変わらなかった。** 実装を進めた CLI のセッションは、途中で再開されて pid が変わった（74325 → 64014）が、記録の `sessionId` は再開の前と同じだった。
- **閉じたセッションの記録は消えていた。** 確認に使った VS Code のセッションを閉じた後、その記録は `~/.claude/sessions` になかった。design の C3 は「終了したセッションの記録も残る」としているが、少なくともこの終わり方では消えた。残る記録がどの終わり方のものかは確かめていない。どちらでも、フックは生死を `kill -0` と `procStart` で確かめるので、判定は変わらない。
