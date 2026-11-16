---
status: done
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
| D6 | 新しい Edit の規則の起点 | **接頭辞のない形を残したまま、`//**/` の形を併記する**（`.git` の hooks の deny と、mise の ask） | 接頭辞のない形は、起動したディレクトリが起点になる。CLAUDE.md が勧める `/add-dir` のディレクトリには当たらない（/review の security と adversarial が指摘）。今の形を残すので、新しい形が効かなくても後退しない | 推奨のとおり（2026-11-16、/review の D1） |
| D7 | 全リポジトリ向けの運用 | **グローバルの `claude/CLAUDE.md` に運用の説明を足し、`permissions.additionalDirectories` に `~/.gstack/projects` を入れる** | 設定は全リポジトリに効くのに、説明は dotfiles の CLAUDE.md にしかない。gstack の `/office-hours`・`/context-save` などは、Write ツールで `~/.gstack/projects` に書く。そこは sandbox の allowWrite に入っていて、Bash はもともと書けるので、書ける範囲は広がらない。`~/` の形が使えるかは文書にないので、Task 13 で確かめる | 推奨のとおり（2026-11-16、/review の D2） |
| D8 | sandbox のパスの接頭辞の検査 | **ユーザー設定の `sandbox.filesystem` の 4 つのリストの全項目が、`~/` か `/` で始まることを検査する** | 接頭辞のないパスは `~/.claude` が起点になり、黙って効かない（T6）。今は mise の 10 項目しか検査していない（/review の testing が指摘） | 推奨のとおり（2026-11-16、/review の D3） |
| D9 | この PR の規則の外にある経路 | **直さずに、research の残るリスクと test-report に記録し、次の作業にする** | git の index 経由の mise の設定、ハードリンク・大文字小文字、submodule の config と hooks など（/review の adversarial と red team が指摘）。どれもこの PR が持ち込んだものではない。次の作業の第一候補は、mise の paranoid と、ハードリンク・大文字小文字のダミーでの確認 | 推奨のとおり（2026-11-16、/review の D4） |
| D10 | `//` の hooks の deny の副作用 | **`Edit(//**/.git/**/hooks/**)` を deny から ask に移し、`Edit(//**/.git/config)` の ask を足す。接頭辞のない deny は残す** | Edit の deny の規則は sandbox の denyWrite にもなる（ask はならない）。`//` の形の deny は全体の denyWrite になり、sandbox の中の `git init`・`git clone`（hooks のサンプルを写す）と、`$TMPDIR` で `git init` するこの repo のテストを壊す見込み（2 回目の /review の security・adversarial が指摘。未実測）。代わりに、`/add-dir` のディレクトリでは拒否ではなく確認の画面になる | 推奨のとおり（2026-11-16、2 回目の /review の D1） |
| D11 | `~/.gstack/projects` の symlink | **D7 は残し、research 8.1 に優先度の高い次の作業として書く** | sandbox から `~/.gstack/projects` を `~/Library/LaunchAgents` への symlink に差し替えると、次のセッションで Edit・Write と sandbox の書ける範囲が移るおそれ（未確認）。sandbox の allowWrite はこの PR の前からある | 推奨のとおり（2026-11-16、2 回目の /review の D2） |
| D12 | 文書と検査 | **すべて直す** | グローバルの CLAUDE.md（`/add-dir` の副作用、サブエージェントの `isolation: worktree` とバックグラウンドのセッション、`~/Dev` で起動したときの sandbox の範囲）、「接頭辞のない形は `/add-dir` に当たらない」を推測と書く、接頭辞のない hooks の deny の副作用、`additionalDirectories` ⊆ allowWrite の検査、境界のテスト | 推奨のとおり（2026-11-16、2 回目の /review の D3） |
| D13 | 直した後の進め方 | **人間の実測 → Codex → Crit。3 回目の /review はしない** | 一番大事なのは D10 の実測。別のモデルの目は Codex が入れる | 推奨のとおり（2026-11-16、2 回目の /review の D4） |

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
7. **`//**/` の形（D6）:** `/add-dir` で足したディレクトリの `mise.toml` で確認の画面が出るか、`.git/hooks` が拒否されるか（Task 13 の T11・T12）。出なければ、接頭辞のない形は残っているので後退はしない。原因を調べて research に書く。
8. **`additionalDirectories` の `~/`（D7）:** `~/.gstack/projects` に Write ツールで書けるか（T13）。書けなければ、`additionalDirectories` と検査の定数を戻し、グローバルの CLAUDE.md に「gstack の置き場所には Bash で書く」と書く。
9. **sandbox の中の git（D10）:** 新しい規則で、sandbox の中の `git init` とこの repo のテストが通るか（Task 17 の T16〜T18）。通らなければ、接頭辞のない hooks の deny も含めて原因を調べ、ask か PreToolUse のフックに替える案を、人間に諮る。

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

- [x] 1. `check-repo.py` の `PROJECT_ASK` の先頭に `"Edit(/claude/**)"` を足す。`PROJECT_DENY_WRITE` の `./claude` と同じ位置。
- [x] 2. `test-check-repo.py` の `PROJECT_ASK` に同じものを足し、次のテストを足す。
  - `test_project_removed_claude_ask_fails`: `Edit(/claude/**)` を消すと、`FAIL project-permissions` と `Edit(/claude/**)` が出る。コメントに、worktree ではユーザー設定の `Edit(~/dotfiles/claude/**)` が当たらないことを書く。
- [x] 3. `test-check-repo.py` が OK、`check-repo.py` が `FAIL project-permissions`（`.claude/settings.json: permissions.ask lacks Edit(/claude/**)`）になることを確かめる。
- [x] 4. `.claude/settings.json` の `permissions.ask` の先頭に `"Edit(/claude/**)"` を足す。
- [x] 5. `check-repo.py` が PASS になることを確かめる。
- [x] 6. コミットする: `fix(claude): ask before Edit writes to claude/ in worktrees`

<a name="task-3"></a>

## Task 3: 作業ディレクトリの外への Edit・Write を止める

**Files:**

- Modify: `.github/scripts/check-repo.py`（定数と、新しい検査 `edit-permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions`）

**Interfaces:**

- Produces: `check_edit_permissions(root) -> list[str]`。`CHECKS` の `("push-permissions", …)` の次に `("edit-permissions", check_edit_permissions)` として登録する。Task 4 はこの関数に検査を足す。

- [x] 1. `check-repo.py` に定数 `WRITE_BLOCK = "blockWritesOutsideWorkingDirectories"` を足す。コメントに、消すと作業ディレクトリの外（ほかのリポジトリの `.git/hooks`、`~/Library/LaunchAgents` など）に確認なしで書ける場合があることを書く。
- [x] 2. `check_edit_permissions(root)` を足す。`permissions[WRITE_BLOCK]` が `True`（真偽値）でなければ、`{SETTINGS}: permissions.{WRITE_BLOCK} must be true` を返す。
- [x] 3. `test-check-repo.py` の `settings()` の `permissions` に `"blockWritesOutsideWorkingDirectories": True` を足し、次のテストを足す。
  - `test_missing_write_block_fails`: キーを消すと、`FAIL edit-permissions` と `blockWritesOutsideWorkingDirectories` が出る。
  - `test_write_block_not_true_fails`: `False` と文字列の `"true"` のそれぞれで失敗する（`subTest`）。
- [x] 4. `test-check-repo.py` が OK、`check-repo.py` が `FAIL edit-permissions` になることを確かめる。
- [x] 5. `claude/settings.json` の `permissions` に `"blockWritesOutsideWorkingDirectories": true` を足す。
- [x] 6. `check-repo.py` が PASS になることを確かめる。
- [x] 7. コミットする: `fix(claude): block Edit and Write outside the working directories`

<a name="task-4"></a>

## Task 4: 作業ディレクトリの中の、自動で動くファイルを守る

**Files:**

- Modify: `.github/scripts/check-repo.py`（定数と `check_edit_permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions.deny`・`ask`、`sandbox.filesystem.denyWrite`）

**Interfaces:**

- Consumes: Task 3 の `check_edit_permissions(root)`

- [x] 1. `check-repo.py` に定数を足す。
  - `EDIT_DENY = ("Edit(**/.git/**/hooks/**)",)`。コメント: hooks は、人間が git を使ったときに sandbox の外で動く。
  - `MISE_CONFIG`: mise が読む設定ファイルのパターン。次の 10 個。
    - `**/mise.toml`、`**/.mise.toml`、`**/mise.*.toml`、`**/.mise.*.toml`
    - `**/mise/config.toml`、`**/mise/config.*.toml`、`**/mise/conf.d/**`
    - `**/.mise/**`、`**/.config/mise/**`、`**/.tool-versions`
  - `MISE_ASK`: `MISE_CONFIG` のそれぞれを `Edit(…)` で包んだもの。コメント: 信頼済みのパスの hooks・`_.source`・`exec()` は、人間が `cd` したときに sandbox の外で動く。
  - `MISE_DENY_WRITE`（D4）: sandbox の `denyWrite` の形。末尾の `/**` を外したもの（`**/mise/conf.d`、`**/.mise`、`**/.config/mise`）と、残りのファイルのパターン。
- [x] 2. `check_edit_permissions` に、`permissions.deny` が `EDIT_DENY` を、`permissions.ask` が `MISE_ASK` を、`sandbox.filesystem.denyWrite` が `MISE_DENY_WRITE` を含むかの検査を足す。メッセージは、既存の `lacks` の形に合わせる。
- [x] 3. `test-check-repo.py` の `settings()` に、3 つの定数の内容を足し、次のテストを足す。
  - `test_missing_git_hooks_deny_fails`
  - `test_missing_mise_ask_fails`（`Edit(**/mise.toml)` を消す）
  - `test_missing_mise_deny_write_fails`（`**/mise.toml` を消す）
- [x] 4. `test-check-repo.py` が OK、`check-repo.py` が `FAIL edit-permissions` になることを確かめる。
- [x] 5. `claude/settings.json` に、`EDIT_DENY` を `permissions.deny` に、`MISE_ASK` を `permissions.ask` に、`MISE_DENY_WRITE` を `sandbox.filesystem.denyWrite`（新しいキー）に足す。
- [x] 6. `check-repo.py` が PASS になることを確かめる。
- [x] 7. コミットする: `fix(claude): guard git hooks and mise config inside the working directory`

> [!NOTE]
> Task 7 の T6 で `**/` の形が効かなかったので、`MISE_DENY_WRITE` と設定は `~/**/` の形に変えた（`07e8bf8`、D4）。テストで消す項目も `~/**/mise.toml` になった。

<a name="task-5"></a>

## Task 5: Read の規則を整理する（D5）

**Files:**

- Modify: `claude/settings.json`（`permissions.deny`）

- [x] 1. `credentials` を測る。
  1. 人間が自分の端末で、ダミーのファイルを作る: `mkdir -p ~/cc-probe/credentials && echo probe > ~/cc-probe/credentials/a.txt && echo probe > ~/cc-probe/b.key`
  2. このセッションで、Read ツールで `~/cc-probe/credentials/a.txt` を読む。拒否されれば、今の `Read(~/**/credentials)` で足りる。
  3. Bash で `head -c1 ~/cc-probe/credentials/a.txt >/dev/null; echo $?` を実行し、sandbox が止めるかを記録する。
- [x] 2. 1 で Read ツールが拒否されなかった場合だけ、`Read(~/**/credentials/**)` を足す。sandbox が止めなかった場合は、bun のキャッシュの `@anthropic-ai/sdk` の `credentials` も読めなくなるので、research に書く。
- [x] 3. `Read(~/Dev/**/*.key)` を `Read(~/**/*.key)` に置き換える。`Read(~/Dev/**/*.pem)` は変えない。
- [x] 4. `check-repo.py` が PASS になることを確かめる。
- [x] 5. コミットする: `fix(claude): deny reading key files anywhere under home`。本文に、`*.pem` を広げない理由を書く。

<a name="task-6"></a>

## Task 6: 文書を更新する

**Files:**

- Modify: `CLAUDE.md`（「Claude Code 設定（`claude/`）」の節）

- [x] 1. 人間が、`claude -w` で作った worktree で `git branch -m <新しい名前>` が使えるかを確かめる（[research 3.4](research-edit-write.md#branch-rename) は EnterWorktree の worktree でだけ確かめた）。
- [x] 2. `CLAUDE.md` に小節「Edit・Write ツールの書き込み」を足す。アンカーは `edit-write-rules`。書くことは次のとおり。
  - ユーザー設定で `blockWritesOutsideWorkingDirectories` をオンにしている。作業ディレクトリの外に書くには `/add-dir` を使う。Claude は設定ファイルを編集できないので、人間が編集する。
  - worktree は `claude -w <name>` で始める（EnterWorktree・ExitWorktree は使えない）。ブランチ名は 1 の結果に合わせて書く。
  - `.claude/settings.json` の ask に `Edit(/claude/**)` があるのは、worktree ではユーザー設定の `Edit(~/dotfiles/claude/**)` が当たらないため。
  - Read の `*.pem` を `~/**` に広げない（CA 証明書の束を sandbox から読めなくなる）。
- [x] 3. `check-repo.py` が PASS になることを確かめる（アンカーとリンク）。
- [x] 4. コミットする: `docs: describe the Edit and Write guards and the worktree workflow`

> [!NOTE]
> main を取り込んだ後（`5edd643`）、main の構成に合わせて、規則の理由は `.claude/rules/CLAUDE_CONFIG.md` に移した。`CLAUDE.md` には使い方と禁止事項を残した（`01b8e2b`）。

<a name="task-7"></a>

## Task 7: 人間のセッションで確かめ、test-report に書く

ユーザー設定の変更は、マージするまでこのセッションに効かない。人間が、変更後の規則を `--settings` で読ませたセッションを起動して確かめる。

- [x] 1. 人間が、変更後の規則だけを取り出したファイルを作る。
  ```sh
  cd ~/dotfiles/.claude/worktrees/fix+edit-write-rules
  jq '{permissions: (.permissions | {blockWritesOutsideWorkingDirectories, deny, ask}), sandbox: {filesystem: .sandbox.filesystem}}' claude/settings.json > "$TMPDIR/edit-write-rules.json"
  ```
- [x] 2. **worktree のセッション:** worktree で `claude --settings "$TMPDIR/edit-write-rules.json"` を起動し、下の表の T1〜T8 を試す。確認の画面には「No」と答える。
- [x] 3. **元のチェックアウトのセッション:** `~/dotfiles` で同じ `--settings` を付けて起動し、下の表の T9 を試す。
- [x] 4. 人間が `~/cc-probe` と、worktree に残った `tmp-probe` を消す。

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

- [x] 5. 期待と違った項目は、原因を調べて直す。T4 は[特に確かめること](#review-focus)の 1 の分け方にする。T6 が効かなければ、D4 の部分（`MISE_DENY_WRITE` と設定）を戻し、research に書く。
- [x] 6. `test-report.md` を書く。環境（Claude Code の版、コミット）、自動テストの結果、T1〜T9 の結果を書く。
- [x] 7. コミットする: `docs: record the Edit and Write guard verification`

> [!NOTE]
> T6 は、人間の判断で D4 を戻さずに `~/**/` の形に直した。T9 の文面を確かめるために T10（設定と関係のない `.json` を作る）を足した。結果は [test-report](test-report.md#human-sessions) にある。

<a name="task-9"></a>

## Task 9: 新しい Edit の規則に、`//**/` の形を併記する（D6）

/review の後に追記した Task（9〜13）。Task 8 の 1 の検査は、/review の中で一度通した。2〜5 は Task 13 の後に行う。

**Files:**

- Modify: `.github/scripts/check-repo.py`（`EDIT_DENY`・`MISE_ASK`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions.deny`・`ask`）

- [x] 1. `test-check-repo.py` の `EDIT_DENY` に `"Edit(//**/.git/**/hooks/**)"` を足し、`MISE_ASK` を、接頭辞のない形と `//` を付けた形の両方にする。次のテストを足す。
  - `test_missing_root_anchored_hooks_deny_fails`: `Edit(//**/.git/**/hooks/**)` を消すと、`FAIL edit-permissions` とその規則が出る。
  - `test_missing_root_anchored_mise_ask_fails`: `Edit(//**/mise.toml)` を消すと、`FAIL edit-permissions` とその規則が出る。
- [x] 2. 2 件が失敗し、ほかのテストが通ることを確かめる。
- [x] 3. `check-repo.py` の `EDIT_DENY` に同じ規則を足し、`MISE_ASK` に `Edit(//{p})` の形を足す。コメントに、接頭辞のない形は起動したディレクトリが起点で、`/add-dir` のディレクトリに当たらないことを書く。
- [x] 4. テストが通り、`check-repo.py` が `FAIL edit-permissions` になることを確かめる。
- [x] 5. `claude/settings.json` の deny の `Edit(**/.git/**/hooks/**)` の次と、ask の mise の 10 件の次に、`//` の形を足す。
- [x] 6. `check-repo.py` が PASS になることを確かめる。`grep -n -E " =[^= ]"` で空白の落ちを確かめる。
- [x] 7. コミットする: `fix(claude): anchor the new Edit rules at the filesystem root as well`

<a name="task-10"></a>

## Task 10: sandbox のパスの接頭辞を検査する（D8）

**Files:**

- Modify: `.github/scripts/check-repo.py`（`check_edit_permissions`）
- Modify: `.github/scripts/test-check-repo.py`

- [x] 1. テストを足す。`test_unprefixed_sandbox_path_fails`: `denyRead`・`denyWrite`・`allowWrite`・`allowRead` のそれぞれに、`**/.ssh` と `./secrets` を足すと、`FAIL edit-permissions` とそのパスが出る（`subTest`）。
- [x] 2. 失敗することを確かめる。
- [x] 3. `check-repo.py` に定数 `SANDBOX_PATH_LISTS = ("denyRead", "denyWrite", "allowWrite", "allowRead")` を足す。`check_edit_permissions` で、ユーザー設定の各リストの項目が `~/` でも `/` でも始まらなければ、`{SETTINGS}: sandbox.filesystem.{key} has an unprefixed path {path}` を返す。
- [x] 4. テストが通り、`check-repo.py` が PASS になることを確かめる（今の設定は、すべて `~/` で始まる）。
- [x] 5. コミットする: `test(claude): reject unprefixed sandbox paths in user settings`

<a name="task-11"></a>

## Task 11: gstack の置き場所を Edit・Write ツールの書ける範囲に入れる（D7 の設定）

**Files:**

- Modify: `.github/scripts/check-repo.py`（定数と `check_edit_permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions.additionalDirectories`）

- [x] 1. `test-check-repo.py` の `settings()` に `"additionalDirectories": ["~/.gstack/projects"]` を足し、次のテストを足す。
  - `test_unexpected_additional_directory_fails`: `~/Dev` を足すと、`FAIL edit-permissions` と `~/Dev` が出る。作業ディレクトリとして数えられ、`blockWritesOutsideWorkingDirectories` が効かなくなるため。
- [x] 2. 失敗することを確かめる。
- [x] 3. `check-repo.py` に定数 `ADDITIONAL_DIRECTORIES = ("~/.gstack/projects",)` を足す。`permissions.additionalDirectories` にこれ以外があれば、`{SETTINGS}: permissions.additionalDirectories must not list {path}` を返す。コメントに、sandbox の allowWrite にも入っていて、Bash はもともと書けることを書く。
- [x] 4. テストが通ることを確かめる。
- [x] 5. `claude/settings.json` の `permissions` に `"additionalDirectories": ["~/.gstack/projects"]` を足す。
- [x] 6. `check-repo.py` が PASS になることを確かめる。
- [x] 7. コミットする: `fix(claude): let Edit and Write reach the gstack project directory`

<a name="task-12"></a>

## Task 12: 文書を更新する（D7 の説明と D9 の記録）

**Files:**

- Modify: `claude/CLAUDE.md`（グローバルの指示。「Safety」の節）
- Modify: `CLAUDE.md`、`.claude/rules/CLAUDE_CONFIG.md`
- Modify: `docs/work/20261114_edit-write-rules/research-edit-write.md`（8 章）、`test-report.md`（7 章）

- [x] 1. `claude/CLAUDE.md` の「Safety」に、次の 4 つを 1 行ずつ足す。
  - Edit・Write ツールは、作業ディレクトリの外と Claude Code の設定ファイルに書けない。外に書く必要があるときは人間に `/add-dir` を頼み、この設定を外すことは提案しない。
  - worktree は人間に `claude -w <name>` で作ってもらう（EnterWorktree は使えず、sandbox の中の `git worktree add` は途中で失敗する）。
  - sandbox の中の git が、mise の設定（`mise.toml`・`.tool-versions` など）で `unable to unlink` や `Operation not permitted` を出したら、続けずに `git status` を確かめて報告する。その状態の作業ツリーをコミットしない。
  - 起動したディレクトリが `~` や `~/Dev` のように複数のリポジトリを含むときは、作業ディレクトリの外を止める設定が効かないので、最初に人間に伝える。
- [x] 2. `CLAUDE.md` の「Edit・Write ツールの書き込み」に `~/.gstack/projects` を書き、禁止事項に `additionalDirectories` に足さないことを書く。接頭辞の禁止事項に、`edit-permissions` が失敗することを書き足す。
- [x] 3. `.claude/rules/CLAUDE_CONFIG.md` に、`//**/` を併記する理由（D6）、`additionalDirectories` の理由（D7）、接頭辞の検査（D8）を書く。
- [x] 4. research の 8 章に、D9 の経路を書く。次の作業の候補と順番（1. mise の paranoid、2. ハードリンク・大文字小文字のダミーでの確認、3. 権限の規則から変換された denyRead・denyWrite の `**/` の確認（env-zsh の `.env` を含む）、4. submodule の config と hooks・`.git` ファイル・core.hooksPath、5. 元のチェックアウトから worktree の `claude/`、6. `*.pem` の範囲）も書く。test-report の 7 章からリンクする。
- [x] 5. `check-repo.py` が PASS になることを確かめる。
- [x] 6. コミットする: `docs: describe the Edit and Write rules for every repository`

<a name="task-13"></a>

## Task 13: 人間のセッションで確かめる（D6・D7）

- [x] 1. 人間が、規則のファイルを作り直す。`additionalDirectories` も取り出す。
  ```sh
  cd ~/dotfiles/.claude/worktrees/fix+edit-write-rules
  jq '{permissions: (.permissions | {blockWritesOutsideWorkingDirectories, additionalDirectories, deny, ask}), sandbox: {filesystem: .sandbox.filesystem}}' claude/settings.json > "$TMPDIR/edit-write-rules.json"
  mkdir -p ~/cc-probe2
  ```
- [x] 2. worktree で `claude --settings "$TMPDIR/edit-write-rules.json"` を起動し、`/add-dir ~/cc-probe2` を実行してから、下の表を試す。確認の画面には「No」と答える。
- [x] 3. 人間が `~/cc-probe2`、`~/.gstack/projects/cc-probe.txt`、worktree の `tmp-probe` を消す。
- [x] 4. 期待と違った項目は、[特に確かめること](#review-focus)の 7・8 のとおりにする。
- [x] 5. test-report に T11〜T15 の結果を足し、コミットする: `docs: record the root-anchored rule and gstack directory checks`

| # | 試すこと | 期待する結果 |
| --- | --- | --- |
| T11 | Write ツールで `~/cc-probe2/mise.toml` を作る | 確認の画面が出る（D6） |
| T12 | Write ツールで `~/cc-probe2/.git/hooks/pre-commit` を作る | 規則で拒否される（D6） |
| T13 | Write ツールで `~/.gstack/projects/cc-probe.txt` を作る | 作れる（D7） |
| T14 | Write ツールで `~/block-test.txt` を作る | 拒否される（T1 と同じ） |
| T15 | Write ツールで `tmp-probe/.tool-versions` を作る | 確認の画面が出る（T5 と同じ） |

<a name="task-14"></a>

## Task 14: `.git` の `//` の規則を ask にする（D10）

2 回目の /review の後に追記した Task（14〜17）。

**Files:**

- Modify: `.github/scripts/check-repo.py`（`EDIT_DENY`、新しい `EDIT_ASK`、`check_edit_permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（`permissions.deny`・`ask`）

- [x] 1. テストを変える。`EDIT_DENY` を `["Edit(**/.git/**/hooks/**)"]` に戻し、`EDIT_ASK = ["Edit(//**/.git/**/hooks/**)", "Edit(//**/.git/config)"]` を足して `settings()` の ask に入れる。`test_missing_root_anchored_hooks_deny_fails` を、次の 2 つに置き換える。
  - `test_missing_root_anchored_git_ask_fails`: `EDIT_ASK` のそれぞれを ask から消すと、`FAIL edit-permissions` とその規則が出る（`subTest`）。
  - `test_root_anchored_git_deny_fails`: `EDIT_ASK` のそれぞれを deny に足すと、`FAIL edit-permissions` と `must not be a deny rule` が出る（`subTest`）。deny は sandbox の denyWrite にもなり、`git init`・`git clone` を壊すため。
- [x] 2. 失敗することを確かめる。
- [x] 3. `check-repo.py` に `EDIT_ASK` を足し、`EDIT_DENY` を戻す。`check_edit_permissions` で、`EDIT_ASK` が ask にあること、deny にないことを検査する。コメントに理由を書く。
- [x] 4. テストが通り、`check-repo.py` が `FAIL edit-permissions` になることを確かめる。
- [x] 5. `claude/settings.json` の deny から `Edit(//**/.git/**/hooks/**)` を外し、ask の `Edit(~/dotfiles/claude/**)` の次に `EDIT_ASK` の 2 つを足す。
- [x] 6. `check-repo.py` が PASS になることを確かめる。`grep -n -E " =[^= ]"` で空白の落ちを確かめる。
- [x] 7. コミットする: `fix(claude): ask instead of deny for root-anchored git rules`

<a name="task-15"></a>

## Task 15: `additionalDirectories` と接頭辞の検査を強める（D12）

**Files:**

- Modify: `.github/scripts/check-repo.py`、`.github/scripts/test-check-repo.py`

- [x] 1. テストを足す。`settings()` の filesystem に `"allowWrite": ["~/.gstack/projects"]` を足す。
  - `test_additional_directory_without_allow_write_fails`: allowWrite を空にすると、`FAIL edit-permissions` と `~/.gstack/projects` が出る。
  - `test_additional_directory_variants_fail`: `~/.gstack/projects/../security`・`~/.gstack`・`~/.gstack/projects/` のそれぞれで失敗する（`subTest`）。
  - `test_sandbox_path_prefix_boundaries`: denyRead に `/Library/Keychains` を足すと通り、`~.ssh` を足すと `unprefixed path ~.ssh` で失敗する。
- [x] 2. 新しいテストのうち、allowWrite の検査のものが失敗することを確かめる（ほかは今の実装でも通る見込み。通ったものは、境界を固定するテストとして残す）。
- [x] 3. `check_edit_permissions` に、`ADDITIONAL_DIRECTORIES` の各項目が `sandbox.filesystem.allowWrite` にあることの検査を足す（メッセージ: `sandbox.filesystem.allowWrite lacks {path} (listed in permissions.additionalDirectories)`）。
- [x] 4. テストと `check-repo.py` が通ることを確かめる。
- [x] 5. コミットする: `test(claude): pin the additional directory and sandbox path checks`

<a name="task-16"></a>

## Task 16: 文書を直す（D11・D12）

**Files:**

- Modify: `claude/CLAUDE.md`、`CLAUDE.md`、`.claude/rules/CLAUDE_CONFIG.md`
- Modify: `docs/work/20261114_edit-write-rules/research-edit-write.md`（8.1・8.2）、`test-report.md`

- [x] 1. `claude/CLAUDE.md` の「Safety」を直す。
  - `/add-dir` の行に、そのディレクトリの `.claude/skills`・`commands`・`agents` も読み込まれるので、書き込み先の最小のディレクトリだけを頼み、信頼していないリポジトリと sandbox から書ける場所（`$TMPDIR` など）は頼まないことを足す。
  - サブエージェントに `isolation: "worktree"` を使わない（編集が拒否される）。バックグラウンドのセッションは、人間に `claude --bg --worktree` で始めてもらう。
  - `~` や `~/Dev` で起動した行を、sandbox の書き込み範囲も広がるので、作業の前にリポジトリで起動し直すよう人間に頼む形にする。
- [x] 2. `CLAUDE.md`・`CLAUDE_CONFIG.md` を直す。`.git` の `//` の規則は ask で、deny にしない理由（sandbox の denyWrite になる）。接頭辞のない hooks の deny の、起動したディレクトリの中での副作用（入れ子のリポジトリの `git init`・`git clone`、`hooks` という名前の階層を含む refs）。「接頭辞のない形は `/add-dir` のディレクトリに当たらない」は、文書の「起点はカレントディレクトリ」からの推測と書く。`additionalDirectories` は sandbox の書き込み範囲にもなることと、allowWrite にもあることを検査していること。
- [x] 3. research の 8.1 に、`~/.gstack/projects` の symlink の経路を足し、8.2 の候補の 1 番目の次に入れる（D11）。
- [x] 4. test-report の 5.1 の、T11・T12 を `//**/` の形によるものとした判断を、推測と書き直す（接頭辞のない形だけの対照は試していない）。
- [x] 5. `check-repo.py` が PASS になることを確かめる。
- [x] 6. コミットする: `docs: correct the Edit and Write guidance after the second review`

<a name="task-17"></a>

## Task 17: 人間のセッションで確かめる（D10）

- [x] 1. 人間が、規則のファイルを作り直し、ダミーのディレクトリを作る。
  ```sh
  cd ~/dotfiles/.claude/worktrees/fix+edit-write-rules
  jq '{permissions: (.permissions | {blockWritesOutsideWorkingDirectories, additionalDirectories, deny, ask}), sandbox: {filesystem: .sandbox.filesystem}}' claude/settings.json > "$TMPDIR/edit-write-rules.json"
  mkdir -p ~/cc-probe2
  ```
- [x] 2. worktree で `claude --settings "$TMPDIR/edit-write-rules.json"` を起動し、`/add-dir ~/cc-probe2` を実行してから、下の表を試す。確認の画面には「No」と答える。
- [x] 3. 人間が `~/cc-probe2` と、worktree の `tmp-probe` を消す。
- [x] 4. 期待と違った項目は、[特に確かめること](#review-focus)の 9 のとおりにする。
- [x] 5. test-report に T16〜T21 の結果を足し、コミットする: `docs: record the sandboxed git checks`

| # | 試すこと | 期待する結果 |
| --- | --- | --- |
| T16 | Bash で `git init -q "$TMPDIR/git-probe"` | 成功する（D10） |
| T17 | Bash で `python3 -B .github/scripts/test-check-repo.py` | 通る（`setUp` で `git init` する） |
| T18 | Bash で、`$TMPDIR` から `bash <worktree>/claude/hooks/tests/test-protect-main-branch.sh` | fail=0 |
| T19 | Write ツールで `~/cc-probe2/.git/hooks/pre-commit` を作る | 確認の画面が出る（D10。前は拒否） |
| T20 | Write ツールで `~/cc-probe2/.git/config` を作る | 確認の画面が出る（D10） |
| T21 | Write ツールで `tmp-probe/.git/hooks/pre-commit` を作る | 拒否される（接頭辞のない deny。T4 と同じ） |

> [!NOTE]
> T16〜T18 と T21 は期待どおりだった。T19・T20 は、確認の画面ではなく、接頭辞のない deny で拒否された。接頭辞のない形も `/add-dir` のディレクトリに当たるので、D6 の前提は外れていた。`//**/` の形は重複になるが、害はないので残した（[test-report 5.2](test-report.md#human-sessions-git)）。

<a name="task-8"></a>

## Task 8: レビューと PR

Task 17 の後に行う。1 の検査を実行し直してから 2 に進む（D13 により、3 回目の /review はしない）。

- [x] 1. 次を実行し、すべて通ることを確かめる。
  - `python3 -B .github/scripts/check-repo.py`
  - `python3 -B .github/scripts/test-check-repo.py`
  - `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`
  - `actionlint`
- [x] 2. 権限の境界の変更なので、Codex のレビューを提案する。人間が `!` で実行し、指摘の採否と理由を test-report に書く。
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
- **/review で見つかった、この PR の規則の外にある経路（D9）:** git の index 経由の mise の設定、ハードリンク・大文字小文字、submodule の config と hooks、`.git` ファイル、core.hooksPath、`.claude/hooks` や mise の設定から呼ぶスクリプト、元のチェックアウトから worktree の `claude/`、env-zsh の `.env`、`*.pem` の範囲。Task 12 で research の 8 章に書き、次の作業にする。
- **マージの後のメモリの更新:** 「worktree を出た後に denyWrite が古く残る」のメモリに、EnterWorktree が使えなくなったことを書き足す。
