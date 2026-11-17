---
status: done
created: 2026-11-17
---

# mise の paranoid と gstack の置き場所のフック（実装計画）

> [!NOTE]
> 実装は superpowers:executing-plans で、このセッションのままタスクごとに進める（推奨。人間の承認と `!` の操作が多く、Task 3〜5 が同じ設定と検査を続けて変えるため）。手順はチェックボックス（`- [ ]`）で追う。

- **目的:** プロジェクトの mise の設定を、パスではなく中身で信頼させ、mise の denyWrite を外す。`~/.gstack/projects` が symlink に差し替えられているあいだは、Edit・Write 系のツールを止める。
- **方針:** グローバルの mise 設定で paranoid を有効にし、ユーザー設定の denyWrite を、mise の 10 項目から paranoid の土台の 3 項目に替える。PreToolUse のフック `guard-additional-dirs.sh` を足す。どれも `check-repo.py` で検査する。
- **技術:** mise 2026.11.8、Claude Code の設定（JSON）、bash（macOS の `/bin/bash` 3.2）、Python 3（`check-repo.py`）
- **設計:** [design.md](design.md)（2026-11-17 に Crit で承認）。根拠は [research-path-gaps.md](research-path-gaps.md)。

<a name="constraints"></a>

## 守ること

- **値**（design の 6.1〜6.3 のとおり）:
  - `mise/mise_config.toml`: `[settings]` の `paranoid = ["config", "env_files"]`
  - `claude/settings.json` の `sandbox.filesystem.denyWrite`: mise の 10 項目（`~/**/mise.toml` など）を消し、`~/.config/mise`・`~/dotfiles/mise`・`~/.local/state/mise` を足す。ほかの項目は消さない。
  - `claude/settings.json` の `hooks.PreToolUse` の末尾に足す組: matcher `Edit|Write|MultiEdit|NotebookEdit`、command `/bin/bash ~/.claude/hooks/guard-additional-dirs.sh`、`timeout` 10、`onFailure` `block`
  - mise の Edit の ask（20 項目）と、`.claude/settings.json` の `./mise`・`./mise.toml` は残す。
- **フック:** stdin を読まない。jq を使わない。macOS の `/bin/bash` 3.2 で動く書き方にする。メッセージは英語にする。
- **mise trust:** Claude は実行しない。人間が中身を確かめてから実行する。
- **順番:** 設定は作業ツリーに書いた時点で効く（design の C1）。paranoid を有効にして人間が信頼を済ませるまで（Task 3）、denyWrite を外さない（Task 4）。
- **書き込みの手段:**
  - `claude/`・`mise/`・`CLAUDE.md`・`.claude/rules` は Edit・Write ツールで書く（確認の画面が出る。Bash からは書けない）。
  - `claude/settings.json` は Claude から書けない。作業ツリーへは、人間が `!` で写す（Task 4）。
- **コミット:**
  - 1 コミットに 1 つの論理変更。Conventional Commits の形で、タイトルは英語、本文は日本語にする。
  - `claude/settings.json` の無関係な差分（`switchModelsOnFlag` とキーの並べ替え）と、`biome/biome.jsonc` の差分（biome の postinstall が書いたもの）は、コミットしない。作業ツリーからも消さない。`git add` はファイルを名指しする。
  - docs とテストだけのコミットを除き、コミットの直前に `/verify` を実行する。
  - Python を変えたら、コミットの前に `grep -n -E " =[^= ]"` で、`=` の後の空白が落ちていないかを確かめる。
- **公開:** ユーザー名を含むパスを書かない。push の前に `check-repo.py` を実行する。
- **テストの実行:** フックのテストは、`$TMPDIR` をカレントディレクトリにして、絶対パスで実行する。

<a name="review-focus"></a>

## 特に確かめること

1. **`HOME` の途中の symlink:** `HOME` が symlink を含むパス（macOS の `$TMPDIR` は `/var` → `/private/var`）でも、実体の `~/.gstack/projects` なら通す。比べる相手は、`HOME` を `cd -P` で解決したパスに `/.gstack/projects` を付けたものにする（plan の判断。design の「`$HOME/.gstack/projects` と違えば」をそのまま比べると、ここで誤検知する）。Task 2 のテストで確かめる。
2. **先のない symlink と通常のファイル:** `~/.gstack/projects` がこのどちらかなら拒否する。「ない」と同じ扱いにしない。Task 2 のテストで確かめる。
3. **paranoid の値の形:** 文字列（`"config,env_files"`）や、`config` だけのリストを通さない。部分文字列で判定しない。Task 3 のテストで確かめる。
4. **信頼されていない設定のあるディレクトリの Bash:** paranoid では、端末のないコマンドが止まる。jq が mise の shim に解決されると、`validate-command.sh` などが fail closed になり、Bash がすべて止まる見込み（推測）。Task 3 の信頼の直後と、Task 6 の V1 で確かめる。止まるなら、CLAUDE.md の今の案内（`mise trust`）で戻せることを確かめ、test-report に書く。
5. **フックを登録した後の普段の書き込み:** 作業ディレクトリ・`~/.gstack/projects`・`.cc-crit-request.json` への Write が通る。Task 6 の V3 で確かめる。

<a name="task-0"></a>

## Task 0: 変更前の状態を記録する

- [x] 1. `python3 -B .github/scripts/check-repo.py`（9 項目 PASS）と `python3 -B .github/scripts/test-check-repo.py` の件数を記録する。
- [x] 2. フックのテスト 4 本が通ることを確かめる（`cd "$TMPDIR" && /bin/bash <dotfiles の絶対パス>/claude/hooks/tests/test-<名前>.sh`）。

<a name="task-1"></a>

## Task 1: `.gitignore` と作業文書をコミットする

plan が /crit-review で承認された後に行う。

**Files:**

- Modify: `.gitignore`（`tmp/`・`.tmp/`。作業ツリーで済んでいる）
- Modify: `docs/work/20261116_sandbox-path-gaps/research-path-gaps.md`、`design.md`、`plan.md`

- [x] 1. research に「5. 判断」の章（アンカー `decisions`）を足す。採った案（paranoid と denyWrite の替え方、フック、`.env` の受け入れ、git 経由の経路を次の作業にすること）を 1 行ずつ書き、design の該当する節にリンクする。status は `in-progress` のまま。
- [x] 2. design と plan の status を `in-progress` にする。
- [x] 3. `check-repo.py` が PASS になることを確かめる。
- [x] 4. `/verify` の後、`.gitignore` だけをコミットする: `chore: ignore tmp directories`
- [x] 5. 3 つの文書をコミットする: `docs: plan paranoid mise and the gstack directory guard`

<a name="task-2"></a>

## Task 2: `~/.gstack/projects` のフック

**Files:**

- Create: `claude/hooks/guard-additional-dirs.sh`（モード 100644。`/bin/bash` で起動するため）
- Create: `claude/hooks/tests/test-guard-additional-dirs.sh`

**Interfaces:**

- Produces: `claude/hooks/guard-additional-dirs.sh`。引数なし。終了コード 0 は通す、2 は拒否で、stderr に `Blocked:` で始まる理由を出す。Task 4 が `claude/settings.json` に登録し、`check-repo.py` は `hooks/guard-additional-dirs.sh` で終わる command を探す。

- [x] 1. テストを書く。形は `test-gh-read-token.sh` に合わせる（`$TMPDIR` を使う `mktemp -d`、`trap`、pass と fail の数、失敗があれば終了コード 1）。フックは `HOME=<ケースの HOME> "$BASH" "$HOOK" <"$T/input.json"` で起動する（入力は `{"tool_name":"Write"}` のファイル。`<<<` は使わない）。ケースごとに別の HOME を作る。

  | ケース | 準備 | 期待 |
  | --- | --- | --- |
  | 実体 | `$H/.gstack/projects` を mkdir | 0 |
  | ない | `$H` だけ | 0 |
  | 親だけある | `$H/.gstack` だけ mkdir | 0 |
  | `HOME` の途中に symlink | `$T/home-link` → `$T/home-real`、`home-real/.gstack/projects` は実体。`HOME=$T/home-link` | 0 |
  | symlink | `$H/.gstack/projects` → `$T/elsewhere`（実体） | 2 |
  | 先のない symlink | `$H/.gstack/projects` → `$T/none` | 2 |
  | 親が symlink | `$H/.gstack` → `$T/other`、`other/projects` は実体 | 2 |
  | 通常のファイル | `$H/.gstack/projects` を touch | 2 |
  | `HOME` が空 | `HOME=` | 2 |
  | `HOME` がない | `env -u HOME` | 2 |
  | メッセージ | symlink のケースの stderr | `Blocked:` で始まり、`.gstack/projects` を含む |

- [x] 2. テストを実行し、フックがないので失敗することを確かめる。
- [x] 3. フックを書く。判定の順番:
  1. `HOME` が未設定か空なら 2。
  2. `HOME` を `cd -P` で解決できなければ 2。
  3. `$HOME/.gstack/projects` が、存在せず（`-e`）symlink でもない（`-L`）なら 0。
  4. symlink なら 2。
  5. `cd -P` で解決できなければ 2（通常のファイルなど）。
  6. 解決したパスが「解決した `HOME` + `/.gstack/projects`」と違えば 2。それ以外は 0。

  先頭のコメントに、すべての呼び出しを止める理由（起動時に symlink が解決され、その先が作業ディレクトリとして扱われるので、対象のパスでは絞れない）と、戻されたときの迂回を受け入れていること（design の 7 章）を書く。拒否のメッセージには、パスと解決した先を入れ、人間に `~/.gstack/projects` を確かめて Claude Code を起動し直すよう書く。
- [x] 4. テストが全件 PASS になり、`shellcheck -S warning` が 2 つのファイルで何も出さないことを確かめる。
- [x] 5. `/verify` の後、2 つのファイルをコミットする: `feat(claude): stop Edit and Write while ~/.gstack/projects is redirected`

<a name="task-3"></a>

## Task 3: mise の paranoid

**Files:**

- Modify: `.github/scripts/check-repo.py`（定数、`check_mise_paranoid`、`CHECKS`）
- Modify: `.github/scripts/test-check-repo.py`（`setUp` とテスト）
- Modify: `mise/mise_config.toml`（末尾に `[settings]`）

**Interfaces:**

- Produces: `check_mise_paranoid(root) -> list[str]`。`CHECKS` の `("project-permissions", …)` の次に `("mise-paranoid", check_mise_paranoid)` として登録する。定数は `MISE_GLOBAL_CONFIG = "mise/mise_config.toml"` と `PARANOID_REQUIRED = ("config", "env_files")`。`settings.paranoid` が `True`、または `PARANOID_REQUIRED` をすべて含むリストなら通す。ファイルがなければ `mise/mise_config.toml: missing` を返す。TOML の誤りは例外のまま `main` に任せる（fail closed）。

- [x] 1. `test-check-repo.py` の `setUp` で、`mise/mise_config.toml` に `[settings]` と `paranoid = ["config", "env_files"]` を書く。次のテストを足す。
  - `test_missing_mise_global_config_fails`: ファイルを消して index からも外す → `FAIL mise-paranoid` と `mise/mise_config.toml`
  - `test_missing_paranoid_fails`: `[tools]` だけにする → `FAIL mise-paranoid` と `settings.paranoid`
  - `test_partial_paranoid_fails`: subTest で `["config"]`・`["env_files"]`・`false`・`"config,env_files"` → `FAIL mise-paranoid`
  - `test_paranoid_true_passes`: `true` → 通る
  - `test_paranoid_superset_passes`: `["config", "env_files", "plugins"]` → 通る
- [x] 2. `test-check-repo.py` を実行し、`fails` の 3 つが失敗することを確かめる。
- [x] 3. `check-repo.py` に定数と `check_mise_paranoid` を足し、`CHECKS` に登録する。定数のコメントに、paranoid はグローバルの設定でだけ効くことと、`config`・`env_files` が要る理由を 1 行ずつ書く。
- [x] 4. `test-check-repo.py` が OK になり、`check-repo.py` が `FAIL mise-paranoid` だけになることを確かめる。
- [x] 5. `mise/mise_config.toml` の末尾に `[settings]` と `paranoid = ["config", "env_files"]` を足す。コメントに、設定を中身で信頼させることと、`plugins`・`provenance` を入れない理由（このリスクと関係がなく、`npm:@salesforce/cli` のインストールを止める見込み）を書く。
- [x] 6. **Bash を使わずに**、6 つの設定（design の 4 章の手元の設定）の `mise trust` のコマンドをチャットで示す。人間が中身を確かめてから `!` で実行し、終わったと伝えるまで待つ。
- [x] 7. 次を確かめる。
  - `mise settings get paranoid` が `config` と `env_files` を返す。
  - dotfiles で `jq --version` が動く（[特に確かめること](#review-focus)の 4）。
  - dotfiles の `mise.toml` が信頼されている（`mise trust --show`）。
  - `check-repo.py` が全項目 PASS、`test-check-repo.py` が OK。
- [x] 8. `grep` で空白を確かめ、`/verify` の後、3 つのファイルをコミットする: `fix(mise): trust project configs by content with paranoid mode`

<a name="task-4"></a>

## Task 4: denyWrite の替え方とフックの登録

**Files:**

- Modify: `.github/scripts/check-repo.py`（`MISE_DENY_WRITE`、`GUARD_HOOK`・`GUARD_TOOLS`、`guard_hook_registered`、`check_edit_permissions`）
- Modify: `.github/scripts/test-check-repo.py`
- Modify: `claude/settings.json`（index は Claude、作業ツリーは人間）

**Interfaces:**

- Consumes: Task 2 の `claude/hooks/guard-additional-dirs.sh`。
- Produces:
  - `MISE_DENY_WRITE = ("~/.config/mise", "~/dotfiles/mise", "~/.local/state/mise")`。`MISE_CONFIG` からの導出をやめる。
  - `GUARD_HOOK = "hooks/guard-additional-dirs.sh"`、`GUARD_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")`
  - `guard_hook_registered(settings) -> bool`: `hooks.PreToolUse` のどれかの組で、matcher を `|` で分けたものが `GUARD_TOOLS` をすべて含み、その組の command が `GUARD_HOOK` で終わり、`onFailure` が `block` なら真。
  - `check_edit_permissions` は、偽のとき `claude/settings.json: hooks.PreToolUse lacks hooks/guard-additional-dirs.sh for Edit|Write|MultiEdit|NotebookEdit with onFailure block` を返す。

- [x] 1. `test-check-repo.py` の `MISE_DENY_WRITE` を 3 項目にし、`settings()` の `PreToolUse` にフックの組を足し、`setUp` で `claude/hooks/guard-additional-dirs.sh` を書く。テストを直し、足す。
  - `test_missing_mise_deny_write_fails`: subTest で 3 項目を 1 つずつ消す → `FAIL edit-permissions` と `denyWrite lacks <項目>`
  - `test_unprefixed_mise_deny_write_fails`: 期待を `denyWrite lacks ~/.config/mise` にする
  - `test_missing_guard_hook_fails`: 組を消す → `FAIL edit-permissions` と `guard-additional-dirs.sh`
  - `test_guard_hook_matcher_missing_tool_fails`: subTest で matcher から 1 つずつ消す → 同上
  - `test_guard_hook_without_block_fails`: `onFailure` を消す → 同上
- [x] 2. `test-check-repo.py` を実行し、足したテストが失敗することを確かめる。
- [x] 3. `check-repo.py` を直す。`MISE_DENY_WRITE` のコメントを、3 つを置く理由（グローバルの設定はパスで信頼される、その実体、信頼の記録。どこで起動しても sandbox から書かせない）に書き換える。
- [x] 4. `test-check-repo.py` が OK になり、`check-repo.py` が `FAIL edit-permissions` だけになることを確かめる。
- [x] 5. scratchpad に、jq で新しい `claude/settings.json` を 2 つ作る。変え方は、denyWrite から 10 項目を引いて 3 項目を足し、`PreToolUse` の末尾にフックの組を足す。
  - `settings-head.json`: `git show HEAD:claude/settings.json` から作る（コミット用）。
  - `settings-wt.json`: 作業ツリーのファイルから作る（作業ツリー用）。

  元のファイルとの `diff -u` が、どちらも同じ変更だけになることを確かめる（jq で書き直しても書式が変わらないことは、2026-11-17 に確かめた）。
- [x] 6. コミット用を index に入れる: `git update-index --cacheinfo 100644,"$(git hash-object -w <scratchpad>/settings-head.json)",claude/settings.json`。sandbox で失敗したら、同じコマンドを人間に `!` で頼む。
- [x] 7. 人間に、作業ツリー用を `!` で写してもらう: `cp <scratchpad の絶対パス>/settings-wt.json ~/dotfiles/claude/settings.json`
- [x] 8. 次を確かめる。
  - `git diff --cached claude/settings.json` が、この作業の変更だけ。
  - `git diff claude/settings.json` が、無関係な差分（`switchModelsOnFlag` と並べ替え）だけ。
  - `check-repo.py` が全項目 PASS、`test-check-repo.py` が OK。
- [x] 9. `grep` で空白を確かめ、`/verify` の後、`check-repo.py` と `test-check-repo.py` を名指しで `git add` して、index の `claude/settings.json` と一緒にコミットする: `fix(claude): replace the mise denyWrite and register the gstack guard`

<a name="task-5"></a>

## Task 5: 文書

**Files:**

- Modify: `CLAUDE.md`（54 行目、62 行目、Safety 相当の追記）
- Modify: `.claude/rules/CLAUDE_CONFIG.md`（53〜55 行目、57 行目、末尾の経緯）
- Modify: `claude/CLAUDE.md`（60 行目）
- Modify: `claude/README.md`（フックの表、テストの一覧）

- [x] 1. ルートの `CLAUDE.md`:
  - 54 行目を、外さないものに合わせて書き換える。mise の設定の Edit の ask、denyWrite の 3 項目、`guard-additional-dirs.sh` の登録（`edit-permissions` が失敗する）。`mise/mise_config.toml` の `paranoid` から `config`・`env_files` を外さない（`mise-paranoid` が失敗する）。
  - 62 行目のフックのテストの一覧に、`bash claude/hooks/tests/test-guard-additional-dirs.sh` を足す。
  - 「Edit・Write ツールの書き込み」の節に、dotfiles では sandbox の中の git が `claude/`・`mise/`・`mise.toml`・`CLAUDE.md` などで `unable to unlink` や `Operation not permitted` を出したら、続けずに `git status` を確かめて報告し、その状態でコミットしない、と足す（plan の判断。design の 6.5 は「ルートの CLAUDE.md の手順が引き続き当てはまる」としたが、ルートにこの手順はなかった。3 で消す `claude/CLAUDE.md` の行を、dotfiles 向けに移す）。
- [x] 2. `.claude/rules/CLAUDE_CONFIG.md`:
  - 53 行目の mise の文: paranoid で中身に信頼を結び付けることと、Edit の ask を残すこと。denyWrite は、ほかのリポジトリの git の操作を途中で止めるので外したこと。
  - 54 行目: denyWrite に 3 つを残す理由と、`~/` の接頭辞の説明（今の後半）。
  - 57 行目の `additionalDirectories`: フックの理由（起動時に symlink が解決され、その先が作業ディレクトリになる）と、戻されたときの迂回を受け入れていること。
  - 末尾の経緯に、[design.md](design.md) へのリンクを足す。
- [x] 3. `claude/CLAUDE.md`: 60 行目（mise の設定の `unable to unlink`）を消し、Safety に「mise が、設定を信頼していないという警告やエラーを出したら、自分で `mise trust` を実行しない。人間に、差分を確かめてから `mise trust` するよう頼む」を足す。
- [x] 4. `claude/README.md`: フックの表に `hooks/guard-additional-dirs.sh`（PreToolUse（Edit・Write・MultiEdit・NotebookEdit）、`~/.gstack/projects` が symlink に差し替えられているあいだ、Edit・Write 系のツールを止める）を足す。表の列の幅は今の表に合わせる。テストの一覧にも足す。
- [x] 5. `check-repo.py` が PASS（`markdown-links` を含む）になることを確かめ、4 つのファイルをコミットする: `docs: describe paranoid mise and the gstack guard`

<a name="task-6"></a>

## Task 6: 新しいセッションで確かめる

**Files:**

- Create: `docs/work/20261116_sandbox-path-gaps/test-report.md`

- [x] 1. 自動の検査を実行して記録する: `check-repo.py`、`test-check-repo.py`、フックのテスト 5 本（`/bin/bash` で）、`git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`、`actionlint`。
- [x] 2. 人間に、確かめるためのセッションを dotfiles で新しく起動してもらう。渡す依頼文をチャットで用意する（ダミー以外のファイルは編集しない、と書く）。
  - **V1（paranoid）:** ダミーは `tmp/paranoid-probe/mise.toml`（`[env]` に値を 1 つ）。
    - 人間のシェル: 信頼すると cd で値が入る。中身を変えると、cd で警告が出て読み飛ばされる。
    - 確かめるセッションの Bash: そのディレクトリで `mise env` が止まる。`jq --version` がどうなるかを記録する（[特に確かめること](#review-focus)の 4）。`mise trust` が失敗する。
  - **V2（denyWrite）:** 確かめるセッションの Bash で、`tmp/v2/mise.toml` を作れる。人間が `~/.config` で起動したセッションの Bash では、`~/.config/mise` の下に作れない。
  - **V3（フック）:** 確かめるセッションで、`tmp/` と `~/.gstack/projects` の下のダミーに Write・Edit が通る。本物の `~/.gstack/projects` は差し替えない。
- [x] 3. ダミーの後片付けのコマンドを人間に示す。
- [x] 4. test-report に、自動の検査、V1〜V3、[特に確かめること](#review-focus)の結果を書き、コミットする: `docs: record the paranoid and guard checks`

<a name="task-7"></a>

## Task 7: レビューと PR

- [x] 1. `/review` を実行する（範囲は人間と決める）。指摘への対応を決め、直したらコミットする。
- [x] 2. 権限の境界を変えるので、`/security-review` を実行する。
- [x] 3. 人間に Codex のレビューを頼む: `! codex review --base origin/main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false`。指摘ごとに採否と理由を整理し、test-report に記録する。
- [x] 4. research・design・plan・test-report の status を `done` にし、`check-repo.py` を実行してコミットする: `docs: close the sandbox path gap work documents`
- [ ] 5. `/crit-review` でブランチの差分を開く。開く前に、作業ツリーの無関係な差分（`claude/settings.json` の一部と `biome/biome.jsonc`）が表示されるが PR には入らない、と伝える。
- [ ] 6. 承認の後、`cc-safe-push` で push し、`.cc-pr-request.json` を書いて `cc-safe-pr create` で PR を作り、`gh pr checks` を確かめる。マージは人間が行う。
- [ ] 7. マージの後の手順（design の [6.10](design.md#design-after-merge)）を人間に伝える。git を経由する経路の設計を、次の作業として始めるかを確かめる。
