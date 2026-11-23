---
status: done
created: 2026-11-21
---

# 同じ作業ツリーの別セッションを知らせるフック 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude が作業ツリーの状態を動かす git 操作を実行する直前に、同じ作業ツリーで生きている別の Claude セッションがあれば、人間の確認（`permissionDecision: "ask"`）に回す PreToolUse（Bash）のフックを作る。

**Architecture:** `claude/hooks/ask-shared-tree-git.sh` 1 本。入力のコマンドを正規化して対象の操作かを照合し、対象なら `~/.claude/sessions/*.json` を読んで、同じ作業ツリーで生きている別のセッションを探す。見つかれば ask の JSON を出し、それ以外とすべての失敗では何も出さずに 0 で終わる（fail open）。

**Tech Stack:** macOS の `/bin/bash`（3.2）、jq、`/bin/ps`、`/bin/kill`、grep。

**Spec:** [design.md](design.md)

**Execution:** Native（superpowers:executing-plans。2026-11-21 に人間が選んだ）

関連: [design.md](design.md)

## Global Constraints

- フックのパスは `claude/hooks/ask-shared-tree-git.sh`、テストは `claude/hooks/tests/test-ask-shared-tree-git.sh`。
- `/bin/bash` 3.2 で動くこと（連想配列・`mapfile`・`${var,,}` を使わない）。コードのコメントは日本語、テストの説明文は英語（既存のテストに合わせる）。
- セッションの記録は `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/*.json` だけを読む。`*.key` は読まない。記録は改行のない 1 行の JSON（2026-11-21 に 23 件で確認）。
- 生死の確認は `/bin/kill -0 <pid>` と `TZ=UTC LC_ALL=C /bin/ps -o lstart= -p <pid>`、祖先は `/bin/ps -o ppid= -p <pid>`。この 3 つの文字列をそのまま使う（テストが置き換える）。PATH の `ps`・`kill` を使わない。
- git を実行しない。コマンドの文字列を実行・評価しない。
- 失敗したときは、標準出力に何も出さずに終了コード 0 で終える。終了コード 2 を使わない。ask の JSON は、すべての判定が済んでから 1 回だけ出す。
- 出力: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": <文面>}}`（jq の `--arg` で組み立てる）。
- 文面: `同じ作業ツリー（<ルート>）で、別の Claude セッションが動いています: <一覧>。このコマンドは、そのセッションのブランチや未コミットの変更に影響します。そのセッションが作業中なら、終わるのを待つか、別の作業ツリーで作業してください。`
  - `<一覧>` の 1 件は `<起動元>（<status>、<MM/DD HH:MM> 開始）`、区切りは `、`。6 件以上なら 5 件と `、ほか N 件`。
  - 起動元: `cli` → `CLI`、`claude-vscode` → `VS Code`、`claude-desktop` → `desktop app`、それ以外はそのまま。
  - 時刻は `startedAt`（ミリ秒）を手元のタイムゾーンで。パスは先頭の `$HOME` を `~` にする。
- 対象の操作は design の [5.2 の表](design.md#design-targets) がすべて。

## Review Focus

- **起動元ごとのプロセスの親子関係。** desktop app や VS Code が、フックを Claude のプロセスの子孫として起動しないと、自分を数えて対象の操作のたびに確認が出る。`sessionId` の除外が保険になる。→ Task 3 の手動の確認 2・3。
- **symlink を通った `cwd`。** 記録の `cwd` やフックの `cwd` が symlink を含んでも、同じツリーと判定されるべき。→ Task 1 のテスト `symlinked cwd`。
- **1 桁の日の `procStart`。** `Sun Nov  1` と `Sun Nov 1` の違いで生きているセッションを外さない。→ Task 2 のテスト `single-digit day`。
- **記録が多いとき。** 終了したセッションの記録が数十件あっても、タイムアウト（10 秒）に遠く及ばない。→ Task 2 のテスト `many records`。
- **記録の `cwd` が消えたディレクトリ。** ルートを求められない記録は飛ばし、他の記録の判定を続ける。→ Task 1 のテスト `deleted cwd`。

---

### Task 0: 作業場所を用意する

この作業は `claude -w` の worktree で行う。`~/dotfiles` には別の作業の未コミットの変更がある。

- [ ] **Step 1:** 人間に、普段のターミナルで `cd ~/dotfiles && claude -w shared-tree-git-hook` を実行してもらう。以降はそのセッションで行う。
- [ ] **Step 2:** ブランチ名を変える: `git branch -m worktree-shared-tree-git-hook feat/shared-tree-git-hook`。`could not lock config file` と出て終了コード 128 で終わるが、名前は変わる。`git branch --show-current` が `feat/shared-tree-git-hook` を返すことを、別の Bash 呼び出しで確かめる。
- [ ] **Step 3:** `~/dotfiles/docs/work/20261121_shared-tree-git-hook/` の `design.md` と `plan.md` を、worktree の同じ場所に写す（Read と Write）。
- [ ] **Step 4:** コミットする。

```bash
git add docs/work/20261121_shared-tree-git-hook/
git commit -m "docs: add the design and plan for the shared-tree git hook"
```

### Task 1: 対象の照合・同じツリーの判定・失敗の扱い

**Files:**
- Create: `claude/hooks/ask-shared-tree-git.sh`
- Test: `claude/hooks/tests/test-ask-shared-tree-git.sh`

`claude/hooks` には sandbox の Bash から書けないので、Write・Edit ツールで作る。

**Interfaces:**
- Produces（フックの中の関数。Task 2 が使う）:
  - `tree_root <dir>`: 物理パスにしたディレクトリから親へたどり、`.git`（ディレクトリかファイル）がある最初のディレクトリを物理パスで出す。なければ終了コード 1。
  - `is_target`: 正規化済みの `$COMMAND` が design 5.2 の対象なら 0、対象外なら 1。照合に失敗したら 2 以上（呼び出し側で fail open）。
  - `read_sessions <dir>`: 各記録を 1 行の TSV で出す。列は `pid sessionId cwd status entrypoint startedAt procStart`。読めない記録と、`pid` が整数でないか `cwd` がない記録は飛ばし、残りの記録は出し続ける。
  - `is_alive <pid> <procStart>`: Task 1 では `/bin/kill -0 <pid>` だけで判定する。
- Produces（テストの補助。Task 2 が使う）:
  - `record <pid> <cwd> [status] [entrypoint] [sessionId] [procStart|-] [startedAt]`: `$CFG/sessions/<pid>.json` を jq で書く。`-` は `procStart` を省く。既定は `idle`・`cli`・`other-<pid>`・`-`・`1795237132160`。
  - `alive <pid> [epoch]`: 偽の kill に生きている pid として登録し、偽の ps の開始時刻（UNIX 秒）を登録する。
  - `check <ask|none> <command> [cwd] [description]`: `cwd` の既定は `$T/repo`。入力 `{"session_id": "self-id", "cwd": <cwd>, "tool_input": {"command": <command>}}` で、フックの差し替え版を `CLAUDE_CONFIG_DIR=$CFG TZ=Asia/Tokyo` で動かす。`none` は「終了コード 0 で出力なし」、`ask` は「終了コード 0 で `"permissionDecision": "ask"` を含む」。それ以外の終了コードは常に失敗にする。
  - 差し替え版: フックの中の `/bin/ps` と `/bin/kill` を、`$T/bin/ps`・`$T/bin/kill` に置き換えた写し。置き換わらなかったら FAIL にする（`test-ask-gh-pr-write.sh` の 132〜140 行と同じ方法）。
  - 偽の kill: `-0 <pid>` で、`$T/alive/<pid>` があれば 0、なければ 1。
  - 偽の ps: `-o lstart= -p <pid>` で `date -r "$(cat "$T/start/<pid>")" '+%a %b %e %H:%M:%S %Y'` を出す（呼び出し側の `TZ` に従うので、実物の ps と同じくタイムゾーンの影響を受ける）。`-o ppid= -p <pid>` で `$T/ppid/<pid>` の中身、なければ `$T/ppid/default` の中身、それもなければ `1` を出す。知らない pid の lstart は終了コード 1。
  - fixture: `$T/repo/.git/`（ディレクトリ）と `$T/repo/sub/`、`$T/repo/.claude/worktrees/wt/.git`（ファイル）、`$T/other/.git/`、`$T/link` → `$T/repo` の symlink。

- [ ] **Step 1: 失敗するテストを書く**

既定の状態: 生きている別のセッション `record 5001 "$T/repo"` と `alive 5001`。

```bash
# Targets ask when another live session shares the tree
for cmd in 'git switch main' 'git switch -c feat/x' 'git checkout main' 'git checkout -b x' \
  'git checkout -- f' 'git rebase main' 'git merge x' 'git pull' 'git reset --hard' 'git reset HEAD~1' \
  'git bisect start' 'git stash' 'git stash push -m x' 'git stash pop' 'git restore f' 'git clean -fd' \
  'git add -A' 'git add --all' 'git add -u' 'git add --update' 'git add .' 'git add :/' \
  'git commit -a -m x' 'git commit -am x' 'git commit --all -m x' 'gh pr checkout 12' \
  'git -C sub -c core.x=y switch main' '"git" switch main' $'git \\\nswitch main' 'cd sub && git switch main'; do
  check ask "$cmd"
done
# Not targets
for cmd in 'git commit -m x' 'git add f' 'git add src/' 'git stash list' 'git stash show' 'git status' \
  'git log' 'git diff' 'git fetch' 'git branch -a' 'git cherry-pick abc' 'git revert abc' 'git push' \
  'git worktree list' 'git rm f' 'git mv a b' 'gh pr view 1' 'echo hi' ''; do
  check none "$cmd"
done
# Tree
check ask 'git switch main' "$T/repo/sub" 'subdirectory of the same tree'
check ask 'git switch main' "$T/link" 'symlinked cwd'
check none 'git switch main' "$T/other" 'another tree'
check none 'git switch main' "$T/repo/.claude/worktrees/wt" 'worktree inside the tree'
check none 'git switch main' "$T" 'outside any repository'
# (separate cases, each resetting the records)
#   no records at all -> none
#   only a record in $T/other -> none
#   only a record in the worktree -> none
#   only a record whose cwd is $T/link -> ask ('symlinked record cwd')
#   only a dead record (record 5002 without alive) -> none
#   a record whose cwd no longer exists, plus the live 5001 -> ask ('deleted cwd')
#   a malformed file 0000.json before 5001.json -> ask ('malformed record skipped')
#   a record without pid or with a string pid -> skipped
# Fail open: every failure exits 0 with no output
#   PATH without jq; PATH with a jq that exits 1; sessions dir missing; input 'not json';
#   command null / 1 / missing -> none (exit 0)
```

- [ ] **Step 2: 失敗を確かめる**

Run: `cd "$TMPDIR" && bash <worktree の絶対パス>/claude/hooks/tests/test-ask-shared-tree-git.sh`
Expected: フックがないので FAIL が並び、最後が `pass=0 fail=N`、終了コード 1。

- [ ] **Step 3: フックを実装する**

- 流れ: 入力を読む → `.tool_input.command` を `ask-gh-pr-write.sh` と同じ jq で正規化（行継続と引用符を除く）→ `is_target` → `tree_root`（入力の `.cwd`、なければ `CLAUDE_PROJECT_DIR`）→ `read_sessions` → 各記録で `tree_root` が一致し `is_alive` のもの → 1 件以上なら ask。
- 正規表現の形は任せる（design 8 章）。`ask-gh-pr-write.sh` の `OPT` と同じく、`git` とサブコマンドの間のオプションを許す。
- fail open の形: 本体をサブシェルで動かして出力を変数に受け、成功したときだけ出力する。どの経路でも `exit 0`。
- この Task の文面は、Global Constraints の文面のうち `<一覧>` を起動元だけにしたものでよい（Task 2 で仕上げる）。

- [ ] **Step 4: テストが通ることを確かめる**

Run: Step 2 と同じ。
Expected: `fail=0`、終了コード 0。

- [ ] **Step 5: shellcheck を通す**

Run: `shellcheck -S warning claude/hooks/ask-shared-tree-git.sh claude/hooks/tests/test-ask-shared-tree-git.sh`
Expected: 出力なし、終了コード 0。

- [ ] **Step 6: コミットする**

```bash
git add claude/hooks/ask-shared-tree-git.sh claude/hooks/tests/test-ask-shared-tree-git.sh
git commit -m "feat(claude): ask before tree-changing git commands when another session shares the tree"
```

### Task 2: 生死の確認・自分の除外・文面

**Files:**
- Modify: `claude/hooks/ask-shared-tree-git.sh`
- Test: `claude/hooks/tests/test-ask-shared-tree-git.sh`

**Interfaces:**
- Consumes: Task 1 の `read_sessions`・`tree_root`・`is_alive`、テストの `record`・`alive`・`check`、偽の ps・kill。
- Produces:
  - `is_alive <pid> <procStart>`: `/bin/kill -0` が成功し、`procStart` が `^[A-Z][a-z]{2} [A-Z][a-z]{2} +[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}$` に合うなら、`TZ=UTC LC_ALL=C /bin/ps -o lstart= -p <pid>` と、連続する空白を 1 つにし前後を除いてから比べる。`procStart` が空か形に合わなければ `kill -0` だけで判定する。
  - `ancestor_pids`: フック自身の `$$` から `/bin/ps -o ppid= -p` で 1 までたどった pid の一覧（最大 32 段）。`ps` が失敗したら、そこまでの一覧を返す。
  - `label <entrypoint>`、`format_reason <root> <件数> <一覧の各行>`: Global Constraints の文面を作る。

- [ ] **Step 1: 失敗するテストを書く**

```bash
EPOCH=1795237131   # 2026-11-21 04:58:51 UTC
proc() { TZ=UTC date -r "$1" '+%a %b %e %H:%M:%S %Y'; }   # the record side, as Claude Code writes it
# procStart (fake ps honors TZ; the hook runs with TZ=Asia/Tokyo)
#   record 5001 "$T/repo" idle cli other-5001 "$(proc $EPOCH)"; alive 5001 $EPOCH     -> ask ('procStart matches in UTC')
#   same record, alive 5001 $((EPOCH + 60))                                            -> none ('pid reused')
#   record procStart 'garbage'; alive 5001 $((EPOCH + 60))                             -> ask ('unknown procStart format falls back to kill -0')
#   EPOCH1=1793491200 (Sun Nov  1 00:00:00 UTC): record procStart 'Sun Nov 1 00:00:00 2026'; alive 5001 $EPOCH1
#                                                                                      -> ask ('single-digit day')
# Self
#   record 5001 ... sessionId self-id; alive 5001                                      -> none ('same sessionId')
#   echo 4242 >"$T/ppid/default"; echo 1 >"$T/ppid/4242"; record 4242 ...; alive 4242 -> none ('ancestor pid')
#   ancestor 4242 plus another live 5001                                               -> ask, and the reason lists 1 session
# Reason text (capture permissionDecisionReason with jq)
#   records: cli busy, claude-vscode idle, claude-desktop waiting, 'cursor' idle
#   -> contains 'CLI（busy、', 'VS Code（idle、', 'desktop app（waiting、', 'cursor（idle、'
#   -> run with HOME="$T": contains '同じ作業ツリー（~/repo）'
#      (like the other tests that change HOME, this needs a jq that is not a mise shim; see CLAUDE.md)
#   -> run with the normal HOME: contains the physical absolute path of $T/repo
#   -> start time: record startedAt 1795237132160, TZ=Asia/Tokyo -> contains '11/21 13:58 開始'
#   7 live sessions -> exactly 5 items and 'ほか 2 件'
#   a record whose cwd is a directory named 'a"b' inside the repo -> output parses with jq -e
# many records: 60 dead records plus 1 live in the same tree -> ask in under 2 seconds
# Real ps (skip in the sandbox: if ! /bin/ps -p $$ >/dev/null 2>&1; then echo "SKIP real ps"; fi)
#   sleep 60 & pid=$!; record $pid "$T/repo" idle cli x "$(TZ=UTC LC_ALL=C /bin/ps -o lstart= -p $pid)"
#   run the real hook (not the substituted copy) with TZ=Asia/Tokyo                   -> ask
#   record $$ (the test shell, an ancestor of the hook) with its real procStart        -> none
#   kill the sleep                                                                      -> none
```

- [ ] **Step 2: 失敗を確かめる**

Run: `cd "$TMPDIR" && bash <worktree の絶対パス>/claude/hooks/tests/test-ask-shared-tree-git.sh`
Expected: `pid reused`・`same sessionId`・`ancestor pid`・文面の各テストが FAIL。Task 1 のテストは PASS のまま。

- [ ] **Step 3: `is_alive`・`ancestor_pids`・自分の除外・`format_reason` を実装する**

自分の除外は、記録の `sessionId` が入力の `.session_id` と同じか、`pid` が `ancestor_pids` に含まれるもの。

- [ ] **Step 4: テストが通ることを確かめる**

Run: Step 2 と同じ。
Expected: `fail=0`、終了コード 0。sandbox の中では `SKIP real ps` が出る。

- [ ] **Step 5: 普段のターミナルでの実行を頼む**

人間に、普段のターミナルで `cd ~/dotfiles/.claude/worktrees/shared-tree-git-hook && bash claude/hooks/tests/test-ask-shared-tree-git.sh` を実行してもらう。
Expected: `SKIP` が出ず、`fail=0`。

- [ ] **Step 6: shellcheck を通してコミットする**

Run: `shellcheck -S warning claude/hooks/ask-shared-tree-git.sh claude/hooks/tests/test-ask-shared-tree-git.sh`
Expected: 出力なし。

```bash
git add claude/hooks/ask-shared-tree-git.sh claude/hooks/tests/test-ask-shared-tree-git.sh
git commit -m "feat(claude): exclude reused pids and the calling session, and list the sessions in the prompt"
```

### Task 3: 登録・文書・手動の確認

**Files:**
- Modify: `claude/settings.json`（`PreToolUse` の `ask-gh-pr-write.sh` の項目の次）
- Modify: `claude/README.md:32-41`（フックの表）、`claude/README.md:49-58`（テストのコマンド）
- Modify: `claude/SKILL_INVENTORY.md:259`
- Modify: `CLAUDE.md:66`（フックのテストの一覧）
- Create: `docs/work/20261121_shared-tree-git-hook/test-report.md`

**Interfaces:**
- Consumes: Task 2 の完成したフック。

- [ ] **Step 1: 登録を足す**

design の [5.1](design.md#design-files) の JSON を、`claude/settings.json` の `ask-gh-pr-write.sh` の項目の次に足す。Edit ツールで試し、拒否されたら差分を示して人間に当ててもらう（C1）。

- [ ] **Step 2: 文書を直す**

- `claude/README.md` の表: `| \`hooks/ask-shared-tree-git.sh\` | PreToolUse（Bash） | ブランチの切り替えなど作業ツリーの状態を動かす git 操作の前に、同じ作業ツリーで別の Claude セッションが動いていれば人間の承認に回す。検査できないときは何もしない |`
- `claude/README.md` のテストの一覧と `CLAUDE.md` の一覧: `bash claude/hooks/tests/test-ask-shared-tree-git.sh` を `test-ask-gh-pr-write.sh` の次に足す。
- `claude/SKILL_INVENTORY.md` の 259 行: `ask-gh-pr-write.sh` の後に `、\`ask-shared-tree-git.sh\`（同じ作業ツリーの別セッション）` を足す。

- [ ] **Step 3: リポジトリの検査を通す**

Run（それぞれ別に、新しいシェルで）:
- `python3 -B .github/scripts/check-repo.py` → 失敗なし
- `python3 -B .github/scripts/test-check-repo.py` → 失敗なし
- `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning` → 出力なし
- `actionlint` → 出力なし
- 既存のフックのテスト 6 本と新しいテスト（`$TMPDIR` から絶対パスで）→ すべて `fail=0`

- [ ] **Step 4: 速さを測る**

差し替え版のフックで、`git status`（対象外）と `git switch main`（対象、記録 60 件）をそれぞれ 20 回動かし、1 回あたりの時間を測る。

- [ ] **Step 5: 手動の確認の準備を頼む**

人間に、worktree の `.claude/settings.local.json` に次を書いてもらう（Claude は書けない）。worktree で起動したセッションだけに、このフックが効く。

```json
{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "/bin/bash <worktree の絶対パス>/claude/hooks/ask-shared-tree-git.sh", "timeout": 10}]}]}}
```

- [ ] **Step 6: 手動の確認をする**

design の [5.9](design.md#design-manual) の 1〜5 を、worktree で起動した CLI・VS Code・desktop app のセッションで確かめる。worktree の中のブランチの切り替えは、`git switch -c tmp/hook-check` のあと `git switch feat/shared-tree-git-hook` で戻すなど、作業に影響しない形にする。失敗したときの進め方は design 5.9 の末尾に従う。終わったら、人間に `.claude/settings.local.json` を消してもらう。

- [ ] **Step 7: 試験の記録を書く**

`test-report.md` に、Step 3 のコマンドと結果、Step 4 の時間、Step 6 の各項目の結果（起動元ごと）を書く。

- [ ] **Step 8: コミットする**

```bash
git add claude/settings.json claude/README.md claude/SKILL_INVENTORY.md CLAUDE.md docs/work/20261121_shared-tree-git-hook/test-report.md
git commit -m "feat(claude): register ask-shared-tree-git and document it"
```

`claude/settings.json` を人間が当てた場合も、同じコミットに含める。

### Task 4: レビューと PR

- [ ] **Step 1:** `/review` でブランチの差分をレビューし、指摘を直す。
- [ ] **Step 2:** 共通の基盤（すべてのセッションのフック）なので、普段のターミナルでの Codex のレビューを提案する: `cd <worktree> && codex review --base main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false`。
- [ ] **Step 3:** `/crit-review` でブランチの差分を開き、`approved: true` が返るまで push しない。
- [ ] **Step 4:** design と plan の `status` を `done` にし、コミットする。
- [ ] **Step 5:** `git branch --show-current` を別の呼び出しで確かめてから、`/usr/local/libexec/claude-push/cc-safe-push` を単独で実行する。
- [ ] **Step 6:** `.cc-pr-request.json` を書き、`/usr/local/libexec/claude-push/cc-safe-pr create` を単独で実行する。PR の本文は日本語で、design へのリンクと手動の確認の結果を含める。
- [ ] **Step 7:** `gh pr checks` で CI を確かめる（macOS の runner は待ちが長いことがある）。マージは人間に任せる。
- [ ] **Step 8:** マージの後、人間に `~/dotfiles/docs/work/20261121_shared-tree-git-hook/`（写す前の未追跡のファイル）を消してもらい、自動メモリ shared-worktree-branch-switch にこのフックのことを書く。
