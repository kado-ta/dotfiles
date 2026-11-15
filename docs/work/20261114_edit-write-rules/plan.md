---
status: in-progress
created: 2026-11-14
---

# Edit・Write ツールからの書き込みを塞ぐ（実装計画）

> [!NOTE]
> 実装は superpowers:executing-plans で、この会話のまま worktree で、タスクごとに進める（D3）。手順はチェックボックス（`- [ ]`）で追う。

- **目的:** sandbox の外で動く Edit・Write ツールから、後で sandbox の外で実行・読み込みされるファイルに書けないようにする。
- **方針:**
  - 作業ディレクトリの外は、`permissions.blockWritesOutsideWorkingDirectories` でまとめて止める。
  - 作業ディレクトリの中は、人間が操作しなくても動くもの（`.git` の hooks、mise の設定）だけに規則を足す。
  - worktree の `claude/` を、Edit ツールでも確認の対象にする（Bash の denyWrite と揃える）。
  - 規則が消されないように、`check-repo.py` の定数で検査する。
- **技術:** Claude Code の設定（JSON）、Python 3（`check-repo.py`）
- **根拠:** [research-edit-write.md](research-edit-write.md)

関連: PR #18、[20261113_sandbox-escape-hardening/plan.md](../20261113_sandbox-escape-hardening/plan.md)

<a name="decisions"></a>

## 決めていただきたいこと

| # | 内容 | 推奨 | 理由・トレードオフ | 決定 |
| --- | --- | --- | --- | --- |
| D1 | 2 の方式 | `blockWritesOutsideWorkingDirectories` をオンにする。作業ディレクトリの中向けの規則と、プロジェクト設定の `Edit(/claude/**)` を足す | 外への書き込みを、場所を並べずにまとめて止められる。代わりに、外に書くには `/add-dir` が要り、Claude は設定ファイルを編集できなくなり、EnterWorktree・ExitWorktree がなくなる（[research 2.5](research-edit-write.md#docs-write-block)） | 推奨のとおり（2026-11-14） |
| D2 | 3 の扱い | `CLAUDE.md`・`AGENTS.md` のための規則は足さずに閉じる | [research 7 章](research-edit-write.md#decisions) | 推奨のとおり（2026-11-14） |
| D3 | 作業の場所 | この会話のまま EnterWorktree で worktree に入り、出ずに最後まで進める | 会話の文脈を保てる。作業中の変更が、使っている設定に効かない。ExitWorktree の後に設定が古く残る件は、出なければ起きない | 推奨のとおり（2026-11-14） |
| D4 | mise の設定ファイルを、Bash からも守るか | **守る。** ユーザー設定の `sandbox.filesystem.denyWrite` に足す | Bash は作業ディレクトリの中の `mise.toml` に書ける。sf_hpf_metadata にも `mise.toml` があり、信頼はパスで決まる（[research 5 章](research-edit-write.md#mise)）。代わりに、Claude が `mise use` などで mise の設定を書き換える作業は、Edit ツール（確認あり）か人間が行う。`**/` の形が sandbox で効くかは未確認なので、Task 7 で確かめ、効かなければこの部分を戻す | 推奨のとおり（2026-11-14）。T6 で `**/` が効かなかったので、戻さずに `~/**/` の形に変えた（2026-11-16、[research 3.5](research-edit-write.md#probe-sandbox-anchor)） |
| D5 | Read の規則の整理 | **`*.key` は `~/**` に広げる。`*.pem` は広げない。`credentials` は Task 5 で測ってから決める** | `*.pem` を広げると、mise で入れた pip・Ruby・aws-cli の CA 証明書の束を sandbox から読めなくなる（[research 6 章](research-edit-write.md#read-rules)）。`*.key` で巻き込むのは、主に `~/.claude/sessions/*.key` と Keynote の書類 | 推奨のとおり（2026-11-14） |

<a name="constraints"></a>

## 守ること

- **既存の制限:** `permissions.deny`・`ask`、`sandbox.filesystem.denyRead`・`denyWrite` の項目は消さない。置き換えるときは、元の範囲を含める（`Read(~/Dev/**/*.key)` を `Read(~/**/*.key)` にする）。
- **sandbox の設定:** `sandbox.enabled`・`failIfUnavailable`・`allowUnsandboxedCommands` は変えない。
- **設定ファイルの編集:** `claude/settings.json` と `.claude/settings.json` は Edit ツールで変える（Bash からは書けない）。Task 2 の後は、`claude/` の編集のたびに確認の画面が出る見込み（このセッションがプロジェクト設定を読み直した場合）。
- **コミット:**
  - 1 コミットに 1 つの論理変更を入れる。Conventional Commits の形で、タイトルは英語、本文は日本語にする。
  - gstack が書き換える `claude/settings.json` のパスの差分は、コミットしない。
  - Python を変えたら、コミットの前に `grep -n -E " =[^= ]"` で、`=` の後の空白が落ちていないかを確かめる。
- **公開:** ユーザー名を含むパスを書かない。push の前に `check-repo.py` を実行する。
- **反映のタイミング:** ユーザー設定（`claude/settings.json`）は、マージして元のチェックアウトに pull した後に効く。マージの前は、Task 7 で `--settings` を使って確かめる。

<a name="review-focus"></a>

## 特に確かめること

1. **途中に `**` を置いた規則:** `Edit(**/.git/**/hooks/**)` が、`.git/hooks/x` と `.git/modules/m/hooks/x` の両方に当たるか。当たらなければ、`Edit(**/.git/hooks/**)` と `Edit(**/.git/modules/**/hooks/**)` の 2 つに分ける（Task 7 の T4）。
2. **書けるまま残るはずの場所:** scratchpad と plan のファイルに、普段どおり書けるか（T2）。書けないと、普段の作業が止まる。
3. **元のチェックアウトの `claude/settings.json`:** `blockWritesOutsideWorkingDirectories` が止めるか、確認の画面になるか（T9）。
4. **sandbox の `**/` の形（D4）:** 作業ディレクトリの中の `mise.toml` などへの Bash の書き込みを止めるか（T6）。
5. **`~/**/*.key`（D5）:** sandbox の中の `claude plugins list` が動くか（T7）。
6. **マージの後:** すべてのセッションから EnterWorktree・ExitWorktree がなくなる。マージの時点で EnterWorktree の worktree にいるセッション（このセッションを含む）は、終わるまで worktree から出られない。

<a name="task-0"></a>

## Task 0: 準備（済み）

- [x] 1. EnterWorktree で `.claude/worktrees/fix+edit-write-rules` を作り、ブランチ名を `fix/edit-write-rules` に変えた（[research 3.4](research-edit-write.md#branch-rename)）。
- [x] 2. `python3 -B .github/scripts/check-repo.py` と `python3 -B .github/scripts/test-check-repo.py` が、変更前に通ることを確かめた（8 項目 PASS、43 件 OK）。

<a name="task-1"></a>

## Task 1: research と plan をコミットする

/crit-review で plan が承認された後に行う。

- [x] 1. `status` を `in-progress` にする（D4・D5 の決定は、crit の 1 ラウンド目で表に書いた）。
- [x] 2. `check-repo.py` を実行して PASS を確かめる。
- [x] 3. コミットする: `docs: plan blocking Edit and Write writes that run outside the sandbox`

<a name="task-2"></a>

## Task 2: worktree の `claude/` を、Edit の確認の対象にする

**Files:**

- Modify: `.github/scripts/check-repo.py`（`PROJECT_ASK`）
- Modify: `.github/scripts/test-check-repo.py`（`PROJECT_ASK` とテスト）
- Modify: `.claude/settings.json`（`permissions.ask`）

- [ ] 1. `check-repo.py` の `PROJECT_ASK` の先頭に `"Edit(/claude/**)"` を足す。`PROJECT_DENY_WRITE` の `./claude` と同じ位置。
- [ ] 2. `test-check-repo.py` の `PROJECT_ASK` に同じものを足し、次のテストを足す。
  - `test_project_removed_claude_ask_fails`: `Edit(/claude/**)` を消すと、`FAIL project-permissions` と `Edit(/claude/**)` が出る。コメントに、worktree ではユーザー設定の `Edit(~/dotfiles/claude/**)` が当たらないことを書く。
- [ ] 3. `test-check-repo.py` が OK、`check-repo.py` が `FAIL project-permissions`（`.claude/settings.json: permissions.ask lacks Edit(/claude/**)`）になることを確かめる。
- [ ] 4. `.claude/settings.json` の `permissions.ask` の先頭に `"Edit(/claude/**)"` を足す。
- [ ] 5. `check-repo.py` が PASS になることを確かめる。
- [ ] 6. コミットする: `fix(claude): ask before Edit writes to claude/ in worktrees`

<a name="task-3"></a>

## Task 3: 作業ディレクトリの外への Edit・Write を止める

**Files:**

- Modify: `.github/scripts/check-repo.py`（定数と、新しい検査 `edit-permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions`）

**Interfaces:**

- Produces: `check_edit_permissions(root) -> list[str]`。`CHECKS` の `("push-permissions", …)` の次に `("edit-permissions", check_edit_permissions)` として登録する。Task 4 はこの関数に検査を足す。

- [ ] 1. `check-repo.py` に定数 `WRITE_BLOCK = "blockWritesOutsideWorkingDirectories"` を足す。コメントに、消すと作業ディレクトリの外（ほかのリポジトリの `.git/hooks`、`~/Library/LaunchAgents` など）に確認なしで書ける場合があることを書く。
- [ ] 2. `check_edit_permissions(root)` を足す。`permissions[WRITE_BLOCK]` が `True`（真偽値）でなければ、`{SETTINGS}: permissions.{WRITE_BLOCK} must be true` を返す。
- [ ] 3. `test-check-repo.py` の `settings()` の `permissions` に `"blockWritesOutsideWorkingDirectories": True` を足し、次のテストを足す。
  - `test_missing_write_block_fails`: キーを消すと、`FAIL edit-permissions` と `blockWritesOutsideWorkingDirectories` が出る。
  - `test_write_block_not_true_fails`: `False` と文字列の `"true"` のそれぞれで失敗する（`subTest`）。
- [ ] 4. `test-check-repo.py` が OK、`check-repo.py` が `FAIL edit-permissions` になることを確かめる。
- [ ] 5. `claude/settings.json` の `permissions` に `"blockWritesOutsideWorkingDirectories": true` を足す。
- [ ] 6. `check-repo.py` が PASS になることを確かめる。
- [ ] 7. コミットする: `fix(claude): block Edit and Write outside the working directories`

<a name="task-4"></a>

## Task 4: 作業ディレクトリの中の、自動で動くファイルを守る

**Files:**

- Modify: `.github/scripts/check-repo.py`（定数と `check_edit_permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions.deny`・`ask`、`sandbox.filesystem.denyWrite`）

**Interfaces:**

- Consumes: Task 3 の `check_edit_permissions(root)`

- [ ] 1. `check-repo.py` に定数を足す。
  - `EDIT_DENY = ("Edit(**/.git/**/hooks/**)",)`。コメント: hooks は、人間が git を使ったときに sandbox の外で動く。
  - `MISE_CONFIG`: mise が読む設定ファイルのパターン。次の 10 個。
    - `**/mise.toml`、`**/.mise.toml`、`**/mise.*.toml`、`**/.mise.*.toml`
    - `**/mise/config.toml`、`**/mise/config.*.toml`、`**/mise/conf.d/**`
    - `**/.mise/**`、`**/.config/mise/**`、`**/.tool-versions`
  - `MISE_ASK`: `MISE_CONFIG` のそれぞれを `Edit(…)` で包んだもの。コメント: 信頼済みのパスの hooks・`_.source`・`exec()` は、人間が `cd` したときに sandbox の外で動く。
  - `MISE_DENY_WRITE`（D4）: sandbox の `denyWrite` の形。末尾の `/**` を外したもの（`**/mise/conf.d`、`**/.mise`、`**/.config/mise`）と、残りのファイルのパターン。
- [ ] 2. `check_edit_permissions` に、`permissions.deny` が `EDIT_DENY` を、`permissions.ask` が `MISE_ASK` を、`sandbox.filesystem.denyWrite` が `MISE_DENY_WRITE` を含むかの検査を足す。メッセージは、既存の `lacks` の形に合わせる。
- [ ] 3. `test-check-repo.py` の `settings()` に、3 つの定数の内容を足し、次のテストを足す。
  - `test_missing_git_hooks_deny_fails`
  - `test_missing_mise_ask_fails`（`Edit(**/mise.toml)` を消す）
  - `test_missing_mise_deny_write_fails`（`**/mise.toml` を消す）
- [ ] 4. `test-check-repo.py` が OK、`check-repo.py` が `FAIL edit-permissions` になることを確かめる。
- [ ] 5. `claude/settings.json` に、`EDIT_DENY` を `permissions.deny` に、`MISE_ASK` を `permissions.ask` に、`MISE_DENY_WRITE` を `sandbox.filesystem.denyWrite`（新しいキー）に足す。
- [ ] 6. `check-repo.py` が PASS になることを確かめる。
- [ ] 7. コミットする: `fix(claude): guard git hooks and mise config inside the working directory`

<a name="task-5"></a>

## Task 5: Read の規則を整理する（D5）

**Files:**

- Modify: `claude/settings.json`（`permissions.deny`）

- [ ] 1. `credentials` を測る。
  1. 人間が自分の端末で、ダミーのファイルを作る: `mkdir -p ~/cc-probe/credentials && echo probe > ~/cc-probe/credentials/a.txt && echo probe > ~/cc-probe/b.key`
  2. このセッションで、Read ツールで `~/cc-probe/credentials/a.txt` を読む。拒否されれば、今の `Read(~/**/credentials)` で足りる。
  3. Bash で `head -c1 ~/cc-probe/credentials/a.txt >/dev/null; echo $?` を実行し、sandbox が止めるかを記録する。
- [ ] 2. 1 で Read ツールが拒否されなかった場合だけ、`Read(~/**/credentials/**)` を足す。sandbox が止めなかった場合は、bun のキャッシュの `@anthropic-ai/sdk` の `credentials` も読めなくなるので、research に書く。
- [ ] 3. `Read(~/Dev/**/*.key)` を `Read(~/**/*.key)` に置き換える。`Read(~/Dev/**/*.pem)` は変えない。
- [ ] 4. `check-repo.py` が PASS になることを確かめる。
- [ ] 5. コミットする: `fix(claude): deny reading key files anywhere under home`。本文に、`*.pem` を広げない理由を書く。

<a name="task-6"></a>

## Task 6: 文書を更新する

**Files:**

- Modify: `CLAUDE.md`（「Claude Code 設定（`claude/`）」の節）

- [ ] 1. 人間が、`claude -w` で作った worktree で `git branch -m <新しい名前>` が使えるかを確かめる（[research 3.4](research-edit-write.md#branch-rename) は EnterWorktree の worktree でだけ確かめた）。
- [ ] 2. `CLAUDE.md` に小節「Edit・Write ツールの書き込み」を足す。アンカーは `edit-write-rules`。書くことは次のとおり。
  - ユーザー設定で `blockWritesOutsideWorkingDirectories` をオンにしている。作業ディレクトリの外に書くには `/add-dir` を使う。Claude は設定ファイルを編集できないので、人間が編集する。
  - worktree は `claude -w <name>` で始める（EnterWorktree・ExitWorktree は使えない）。ブランチ名は 1 の結果に合わせて書く。
  - `.claude/settings.json` の ask に `Edit(/claude/**)` があるのは、worktree ではユーザー設定の `Edit(~/dotfiles/claude/**)` が当たらないため。
  - Read の `*.pem` を `~/**` に広げない（CA 証明書の束を sandbox から読めなくなる）。
- [ ] 3. `check-repo.py` が PASS になることを確かめる（アンカーとリンク）。
- [ ] 4. コミットする: `docs: describe the Edit and Write guards and the worktree workflow`

<a name="task-7"></a>

## Task 7: 人間のセッションで確かめ、test-report に書く

ユーザー設定の変更は、マージするまでこのセッションに効かない。人間が、変更後の規則を `--settings` で読ませたセッションを起動して確かめる。

- [ ] 1. 人間が、変更後の規則だけを取り出したファイルを作る。
  ```sh
  cd ~/dotfiles/.claude/worktrees/fix+edit-write-rules
  jq '{permissions: (.permissions | {blockWritesOutsideWorkingDirectories, deny, ask}), sandbox: {filesystem: .sandbox.filesystem}}' claude/settings.json > "$TMPDIR/edit-write-rules.json"
  ```
- [ ] 2. **worktree のセッション:** worktree で `claude --settings "$TMPDIR/edit-write-rules.json"` を起動し、下の表の T1〜T8 を試す。確認の画面には「No」と答える。
- [ ] 3. **元のチェックアウトのセッション:** `~/dotfiles` で同じ `--settings` を付けて起動し、下の表の T9 を試す。
- [ ] 4. 人間が `~/cc-probe` と、worktree に残った `tmp-probe` を消す。

| # | セッション | 試すこと | 期待する結果 |
| --- | --- | --- | --- |
| T1 | worktree | Write ツールで `~/block-test.txt` を作る | 拒否される |
| T2 | worktree | Write ツールで、そのセッションの scratchpad にファイルを作る | 作れる |
| T3 | worktree | Edit ツールで `claude/README.md` を変える | 確認の画面が出る（Task 2） |
| T4 | worktree | Write ツールで `tmp-probe/.git/hooks/pre-commit` と `tmp-probe/.git/modules/m/hooks/pre-commit` を作る | どちらも規則で拒否される |
| T5 | worktree | Write ツールで `tmp-probe/mise.toml`、`tmp-probe/.config/mise/config.toml`、`tmp-probe/.tool-versions` を作る | どれも確認の画面が出る |
| T6 | worktree | Bash で `mkdir -p tmp-probe/.config` の後、`touch tmp-probe/mise.toml`、`touch tmp-probe/.tool-versions`、`mkdir tmp-probe/.config/mise` | どれも Operation not permitted（D4） |
| T7 | worktree | Bash で `claude plugins list` | 普段どおり一覧が出る（D5） |
| T8 | worktree | Read ツールと Bash（`head -c1 … >/dev/null; echo $?`）で `~/cc-probe/b.key` を読む | どちらも拒否される |
| T9 | 元のチェックアウト | Edit ツールで `claude/settings.json` に空行を 1 つ足す | 拒否されるか、確認の画面が出る。どちらだったかを記録する |

- [ ] 5. 期待と違った項目は、原因を調べて直す。T4 は[特に確かめること](#review-focus)の 1 の分け方にする。T6 が効かなければ、D4 の部分（`MISE_DENY_WRITE` と設定）を戻し、research に書く。
- [ ] 6. `test-report.md` を書く。環境（Claude Code の版、コミット）、自動テストの結果、T1〜T9 の結果を書く。
- [ ] 7. コミットする: `docs: record the Edit and Write guard verification`

<a name="task-8"></a>

## Task 8: レビューと PR

- [ ] 1. 次を実行し、すべて通ることを確かめる。
  - `python3 -B .github/scripts/check-repo.py`
  - `python3 -B .github/scripts/test-check-repo.py`
  - `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`
  - `actionlint`
- [ ] 2. 権限の境界の変更なので、Codex のレビューを提案する。人間が `!` で実行し、指摘の採否と理由を test-report に書く。
- [ ] 3. `cc-safe-push` で push し、`cc-safe-pr create` で PR を作る。本文に、マージの後に人間が行うことを書く。
  - 元のチェックアウトで `git pull` し、Claude Code のセッションをすべて起動し直す。
  - 起動したセッションで、Write ツールで `~/block-test.txt` を作らせ、拒否されることを確かめる。
  - 以後、worktree は `claude -w` で始める。
- [ ] 4. `gh pr checks` で CI の結果を確かめる。
- [ ] 5. マージは人間が行う。

<a name="out-of-scope"></a>

## 範囲外

- **1（GitHub Actions）:** sf-hpf-metadata のデプロイの Actions の設計で扱う（2026-11-14 決定）。Workflow permissions は、人間が read にし、Actions による PR の作成と承認をオフにした。
- **`blockReadsOutsideWorkingDirectories`:** ほかのリポジトリを読む作業が多いので、採らない。
- **作業ディレクトリの中の、そのほかの保護パス（`.vscode`・`.mcp.json` など）:** auto mode の判定に任せる（[research 8 章](research-edit-write.md#residual-risks)）。
- **auto memory の `.md`:** 塞ぐ手段がないので、残るリスクとして research に書いた。
- **マージの後のメモリの更新:** 「worktree を出た後に denyWrite が古く残る」のメモリに、EnterWorktree が使えなくなったことを書き足す。
