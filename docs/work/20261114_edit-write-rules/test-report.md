---
status: done
created: 2026-11-16
---

# Edit・Write ツールからの書き込みを塞ぐ（検証の記録）

[plan.md](plan.md) の Task 2〜7 を検証した記録。

<a name="environment"></a>

## 1. 環境

| 項目 | 版 |
| --- | --- |
| macOS | 26.7.1 |
| Claude Code | 2.1.325（[research 3.2](research-edit-write.md#trial-session) の試用は 2.1.323） |

人間の確かめ（[5 章](#human-sessions)）は 2 回に分けて行った。1 回目は `7dc56c9`（設定は `c38cee3` と同じ）、2 回目は `07e8bf8` の設定を使った。/review の後の確かめ（[5.1](#human-sessions-review)）は `7bc82dc`、2 回目の /review の後の確かめ（[5.2](#human-sessions-git)）は `aa618d0` の設定を使った。

<a name="automated"></a>

## 2. 自動テスト

Claude Code の Bash ツール（sandbox の中）で、worktree の `07e8bf8` で実行した。最後に `16b8677` で実行し、数字はその時点のもの。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 9 項目 PASS（変更前は 8 項目。`edit-permissions` を足した） |
| `python3 -B .github/scripts/test-check-repo.py` | 58 件 OK（変更前は 43 件） |
| shellcheck / actionlint | 指摘なし |

<a name="red-green"></a>

## 3. 先に失敗させたこと

| Task | 失敗させたテスト | 失敗の内容 |
| --- | --- | --- |
| 2 | `test_project_removed_claude_ask_fails` | プロジェクト設定の ask から `Edit(/claude/**)` を消しても、検査が通った |
| 3 | `test_missing_write_block_fails`、`test_write_block_not_true_fails` | `edit-permissions` の検査がなかった |
| 4 | `test_missing_git_hooks_deny_fails`、`test_missing_mise_ask_fails`、`test_missing_mise_deny_write_fails` | `.git` の hooks の deny と、mise の ask・denyWrite を検査していなかった |
| 7（T6 の修正） | `test_unprefixed_mise_deny_write_fails` と、テストの denyWrite の形 | `7dc56c9` の検査に変更後のテストを当てると、13 件が失敗した。理由はすべて、denyWrite の形が `**/` のままだったこと |
| 9 | `test_missing_root_anchored_hooks_deny_fails`、`test_missing_root_anchored_mise_ask_fails` | `//**/` の形を検査していなかった |
| 10 | `test_unprefixed_sandbox_path_fails`（4 つのリスト × 2 つのパスの 8 件） | mise の 10 項目のほかは、接頭辞を検査していなかった |
| 11 | `test_unexpected_additional_directory_fails` | `additionalDirectories` を検査していなかった |
| 14 | `test_missing_root_anchored_git_ask_fails`、`test_root_anchored_git_deny_fails`（各 2 件） | `.git` の `//**/` の規則が ask にあることと、deny にないことを検査していなかった。フィクスチャの deny から `//**/` の hooks を外したので、成功を期待するテストも失敗した |
| 15 | `test_additional_directory_without_allow_write_fails` | allowWrite を検査していなかった。同じ Task の `test_additional_directory_variants_fail` と `test_sandbox_path_prefix_boundaries` は、今の実装でも通った（境界を固定するテストとして残した） |

<a name="measurements"></a>

## 4. 実測

<a name="measure-credentials"></a>

### 4.1 `credentials` のディレクトリの中（Task 5）

人間がダミーのファイル `~/cc-probe/credentials/a.txt` を作り、このセッションから読んだ（2026-11-16）。

| 読み方 | 結果 |
| --- | --- |
| Read ツール | 拒否された（`File is in a directory that is denied by your permission settings.`） |
| sandbox の中の Bash（`head -c1`） | `Operation not permitted`（終了コード 1） |

今の `Read(~/**/credentials)` でディレクトリの中まで止まるので、`Read(~/**/credentials/**)` は足さなかった。

<a name="measure-branch-rename"></a>

### 4.2 `claude -w` の worktree のブランチ名（Task 6）

人間が `claude -w rename-check` で起動したセッションで、Claude に `git branch -m test/rename-check` を実行させた。

- ブランチ名は変わった（`git branch --show-current` は `test/rename-check`、元の `worktree-rename-check` は残っていない）。
- 次のエラーが出て、終了コードは 128 だった。sandbox が `.git/config` を守っているため。
  ```text
  error: could not lock config file /Users/<user>/dotfiles/.git/config
  fatal: branch is renamed, but update of config-file failed
  ```
- 元のブランチにも新しいブランチにも、`branch.*` の設定はなかった。

終了コードが 0 でないことは、CLAUDE.md の[「Edit・Write ツールの書き込み」](../../../CLAUDE.md#edit-write-rules)に書いた。

<a name="human-sessions"></a>

## 5. 人間のセッションでの確かめ（Task 7）

人間が、変更後の規則だけを取り出したファイルを `claude --settings` で読ませたセッションを起動し、Claude に操作させた（2026-11-16）。確認の画面には「No」と答えた。

| # | セッション | 試したこと | 結果 | 判定 |
| --- | --- | --- | --- | --- |
| T1 | worktree | Write ツールで `~/block-test.txt` を作る | 拒否された（`… is outside …; the permissions.blockWritesOutsideWorkingDirectories setting blocks writes outside the working directories. Ask the user to add the directory with /add-dir, or to remove that setting.`） | 期待どおり |
| T2 | worktree | Write ツールで、そのセッションの scratchpad に `probe.txt` を作る | 作れた | 期待どおり |
| T3 | worktree | Edit ツールで `claude/README.md` を変える | 確認の画面が出た | 期待どおり |
| T4 | worktree | Write ツールで `tmp-probe/.git/hooks/pre-commit` と `tmp-probe/.git/modules/m/hooks/pre-commit` を作る | 2 件とも規則で拒否された（`denied by your permission settings`） | 期待どおり |
| T5 | worktree | Write ツールで `tmp-probe/mise.toml`、`tmp-probe/.config/mise/config.toml`、`tmp-probe/.tool-versions` を作る | 3 件とも確認の画面が出た（人間が画面で確認） | 期待どおり |
| T6 | worktree | Bash で `touch tmp-probe/mise.toml`、`touch tmp-probe/.tool-versions`、`mkdir tmp-probe/.config/mise` | 1 回目（`**/` の形）は、すべて成功した。2 回目（`~/**/` の形）は止まった（下の説明） | 直して期待どおり |
| T7 | worktree | Bash で `claude plugins list` | 一覧が出た。`api.anthropic.com` などへの通信は sandbox のネットワークの設定で拒否されたが、一覧には影響しなかった | 期待どおり |
| T8 | worktree | Read ツールと Bash（`head -c1`）で `~/cc-probe/b.key` を読む | Read ツールは規則で拒否された。Bash は `Operation not permitted`（終了コード 1） | 期待どおり |
| T9 | 元のチェックアウト | Edit ツールで `claude/settings.json` に空行を 1 つ足す | 確認の画面は出ず、拒否された（下の文面） | 拒否された |
| T10 | worktree | Write ツールで `tmp-probe/x.json` を作る | 作れた（auto mode が許可） | T9 の文面の確認 |

- **T4:** [特に確かめること](plan.md#review-focus)の 1 のとおり、途中に `**` を置いた `Edit(**/.git/**/hooks/**)` は、どちらの深さにも当たった。規則は分けていない。
- **T5:** 1 回目は 3 件を並べて呼んだので、1 回の「No」で 3 件とも止まった。`mise.toml` は 1 回目のやり直しで、残りの 2 件は 2 回目に、1 件ずつ確かめた。
- **T6:** 1 回目の失敗の原因と対応は [research 3.5](research-edit-write.md#probe-sandbox-anchor) に書いた。ユーザー設定の `sandbox.filesystem` のパスは、接頭辞がないと `~/.claude` が基準になる。`07e8bf8` で `~/**/` の形に直し、2 回目は次のとおりだった。
  - `touch tmp-probe/mise.toml` と `touch tmp-probe/.tool-versions` は `Operation not permitted`。
  - `mkdir tmp-probe/.config/mise` は、1 回目に作ったディレクトリが残っていたので `File exists` になり、判定できなかった。代わりに、新しいパスで `touch fresh/mise.toml`、`touch fresh/.tool-versions`、`mkdir fresh/.config/mise` を試し、どれも `Operation not permitted` だった。
  - 残っていた `.config/mise/` の中の `touch config.toml` も `Operation not permitted` だった。ディレクトリの中にも効く。
  - 対照の `touch fresh/control.txt` は成功した。規則に当たるファイルだけが止まっている。
- **T9:** 表示された文面は次のとおり。sandbox ではなく `blockWritesOutsideWorkingDirectories` の判定で止まった。
  ```text
  /Users/<user>/dotfiles/claude/settings.json: Writes to Claude Code settings files are blocked while permissions.blockWritesOutsideWorkingDirectories is on, because a settings file can lift that block. While a managed settings folder cannot be resolved, any .json file counts as one.
  ```
- **T10:** T9 の文面の後半（managed settings のフォルダを解決できない間は、どの `.json` も設定ファイルとして扱う）が気になったので足した。この Mac には `/Library/Application Support/ClaudeCode` がないが、設定と関係のない `.json` は作れた。この文面は、今の環境には当てはまらなかったと考える（推測）。

<a name="human-sessions-review"></a>

### 5.1 /review の後の確かめ（Task 13）

`7bc82dc` の設定（`additionalDirectories` も含む）を `--settings` で読ませた worktree のセッションで、人間が `/add-dir ~/cc-probe2` を実行してから試した（2026-11-16）。

| # | 試したこと | 結果 | 判定 |
| --- | --- | --- | --- |
| T11 | Write ツールで `~/cc-probe2/mise.toml` を作る | 確認の画面が出て、No で止まった（`User rejected write`） | 期待どおり（D6） |
| T12 | Write ツールで `~/cc-probe2/.git/hooks/pre-commit` を作る | 確認の画面なしで、規則で拒否された（`File is in a directory that is denied by your permission settings.`） | 期待どおり（D6） |
| T13 | Write ツールで `~/.gstack/projects/cc-probe.txt` を作る | 作れた（`Allowed by auto mode`） | 期待どおり（D7） |
| T14 | Write ツールで `~/block-test.txt` を作る | 拒否された。文面の作業ディレクトリの一覧に `~/.gstack/projects` と `~/cc-probe2` が入っていた | 期待どおり |
| T15 | Write ツールで `tmp-probe/.tool-versions` を作る | 確認の画面が出て、No で止まった | 期待どおり |

- T11 と T12 は、接頭辞のない形と `//**/` の形の両方が読み込まれた状態で試したので、どちらの規則に当たったかは区別できていない。後の T19・T20（[5.2](#human-sessions-git)）で、接頭辞のない deny が `~/cc-probe2` にも当たったので、接頭辞のない形も `/add-dir` のディレクトリに効いていたと考える。
- T12 の `Edit(//**/.git/**/hooks/**)` は、この後の Task 14 で deny から ask に移した（sandbox の中の `git init`・`git clone` を壊す見込みのため）。今の設定での振る舞いは Task 17 の T19 で確かめる。
- T13 と T14 の文面から、`additionalDirectories` の `~/` の形は、ホームのディレクトリとして解決されている。
- 書き込みの後、ファイルは T13 の `cc-probe.txt` だけだった（確かめのセッションが `ls` で確認）。

<a name="human-sessions-git"></a>

### 5.2 2 回目の /review の後の確かめ（Task 17）

`aa618d0` の設定を `--settings` で読ませた worktree のセッションで、人間が `/add-dir ~/cc-probe2` を実行してから試した（2026-11-16）。

| # | 試したこと | 結果 | 判定 |
| --- | --- | --- | --- |
| T16 | Bash で `git init -q "$TMPDIR/git-probe"` | 成功（終了コード 0） | 期待どおり（D10） |
| T17 | Bash で `python3 -B .github/scripts/test-check-repo.py` | 58 件 OK（`setUp` で `git init` する） | 期待どおり（D10） |
| T18 | Bash で、`$TMPDIR` から `test-protect-main-branch.sh` | pass=94、fail=0 | 期待どおり（D10） |
| T19 | Write ツールで `~/cc-probe2/.git/hooks/pre-commit` を作る | 確認の画面なしで、規則で拒否された（`File is in a directory that is denied by your permission settings.`） | 期待（確認の画面）より強い |
| T20 | Write ツールで `~/cc-probe2/.git/config` を作る | T19 と同じ | 期待（確認の画面）より強い |
| T21 | Write ツールで `tmp-probe/.git/hooks/pre-commit` を作る | T19 と同じ | 期待どおり |

- T16〜T18 で、`//**/` の hooks の規則を ask に移した後は、sandbox の中の `git init` とこの repo のテストが通ることを確かめた。移す前の deny の形で失敗するかは、試していない（[research 8.1](research-edit-write.md#review-gaps) の推測のまま）。
- T19・T20 の文面は deny の規則に当たったときのもので、ask なら確認の画面になり、`blockWritesOutsideWorkingDirectories` なら別の文面になる（T14）。`~/cc-probe2` の `.git/hooks` と `.git/config` に当たる deny は、接頭辞のない `Edit(**/.git/**/hooks/**)` と `Edit(**/.git/config)` だけなので、**接頭辞のない形も `/add-dir` のディレクトリに当たる**と判断した。D6 の前提（当たらない）は外れていた。
- `//**/` の形は重複になるが、害はないので残した。文書は接頭辞のない形の起点をカレントディレクトリとしているので、`/cd` などで起点が変わったときの備えになる。

<a name="notes"></a>

## 6. 気づいたこと

- **worktree の `claude/CLAUDE.md`:** T3 で `claude/README.md` を読んだときに、`Loaded claude/CLAUDE.md` と出た。`.claude/settings.json` の `claudeMdExcludes` は `**/dotfiles/claude/CLAUDE.md` なので、worktree のパス（`…/worktrees/<name>/claude/CLAUDE.md`）に当たらない。worktree では、グローバルの指示と同じ内容が、プロジェクトの CLAUDE.md としても読み込まれる。守りは弱くならないが、コンテキストが増える。この作業の範囲外なので、直していない。
- **確かめのセッションによる編集:** T6 の 1 回目の失敗の後、確かめに使ったセッションが、同じ worktree の検査・テスト・設定・plan・research を書き換えた（人間の判断を受けたもの）。作業のセッションは編集を止め、人間がそのセッションを止めた後に、差分を読み、[3 章](#red-green)の失敗と成功を確かめて `07e8bf8` にまとめた。2 回目からは、確かめのセッションに「ファイルは編集しない」と伝えた。

<a name="not-verified"></a>

## 7. 確かめていないこと

- **権限の規則から変換された denyRead の `**/` の形:** `Read(**/.ssh)` などが sandbox の `denyRead` になったとき、作業ディレクトリの中に効くか。ダミーの `x.key` を作って sandbox の中から読む測定が、権限の判定で拒否された。`**/.env*`・`**/*.key` などには `~/**` の対があるので、ホームの下は守られている。対がないのは `**/.ssh` など。
- **ホームの外の mise の設定:** `~/**/` の形なので、`/tmp` に clone したものなどは、sandbox では守れない。Edit ツールの ask は `//**/` の形も置いたので、ホームの外と `/add-dir` のディレクトリにも効く（T11）。
- **plan のファイルへの書き込み:** [特に確かめること](plan.md#review-focus)の 2 のうち、scratchpad だけを試した（T2）。plan のファイルは、ドキュメントでは止めない場所に入っている。
- **マージの後:** 元のチェックアウトで `git pull` してセッションを起動し直した後、Write ツールで `~/block-test.txt` を作らせて拒否されることを、人間が確かめる（PR の本文に書く）。
- **/review で見つかった、規則の外の経路:** git の index 経由の mise の設定、ハードリンク・大文字小文字、submodule の config と hooks など。[research 8.1](research-edit-write.md#review-gaps) にまとめ、次の作業にする（D9）。

<a name="codex"></a>

## 8. レビュー

- **/review（2 回）:** 指摘への対応は、[plan](plan.md#decisions) の D6〜D13 に書いた。
- **Codex（1 回目、2026-11-16）:** `codex review --base origin/main`（読み取り専用）で、`16b8677` を受けた。
  - **結果:** 指摘なし。意図した制限の強化と、文書に書いた運用上の制約のほかに、直す必要のある新しい不具合はなかった。`check-repo.py` の 9 項目、shellcheck、actionlint は成功した。
  - **Codex が確かめていないこと:** 一時ファイルを作るテストと、Claude Code の上での権限の実際の動き。読み取り専用の環境のため。どちらも、2 章と 5 章で確かめた。
