---
status: in-progress
created: 2026-11-26
---

# Codex の破壊的なコマンドを execpolicy の rules で確認にする

## 目次

- [関連](#related)
- [背景と目的](#background)
- [仕様の確認](#spec)
- [完了条件](#done-criteria)
- [規則](#rules)
- [方針](#approach)
- [採らなかった案](#rejected)
- [変更するファイル](#files)
- [手順](#steps)
- [対象外と残るリスク](#out-of-scope)

<a name="related"></a>

## 関連

- [codex/README.md の「今後の改善候補」](../../../codex/README.md#future-work) に残っていた案（`~/.codex/rules/*.rules` で `forbidden` / `prompt` にする）。
- 他者の dotfiles の rules と README を読んで参考にした。LICENSE がなく、規則もその人の環境向けなので、写さずに書いた。

<a name="background"></a>

## 背景と目的

Codex は Claude Code の予備として、エージェントとしても使う（`codex/config.base.toml` の `approval_policy = "on-request"`、`sandbox_mode = "workspace-write"`）。破壊的な操作は、`developer_instructions` の文章で止めているだけだった。

調べた結果、workspace-write の sandbox がすでに止めている操作が多かった（[実測](#spec-sandbox)）。この作業では、次の 2 つに効く規則だけを入れる。

1. **sandbox の中で確認なしに動くもの**: `git clean` と、`-f` のない `rm -r`。
2. **今は昇格の確認が出るが、「今後は聞かない」で確認が消えるもの**: `git push`・`git reset --hard`・`terraform apply` など。
   - TUI で昇格を承認するときに「今後は聞かない」を選ぶと、allow の規則が `~/.codex/rules/default.rules` に書かれる。以後は、同じ接頭辞のコマンドが sandbox の外で確認なしに動く。
   - 例: `git push` を許すと、`git push --force origin main` も確認なしに動く。
   - prompt の規則に当たるコマンドには、Codex がこの選択肢を出さない。すでにある allow の規則にも prompt が勝つ（[ソース](#spec-source)）。

`danger-full-access` で動かすときなど、sandbox が緩んだときの守りにもなる。

<a name="spec"></a>

## 仕様の確認

<a name="spec-docs"></a>

### 公式ドキュメント

[Rules](https://developers.openai.com/codex/rules)（2026-11-26 に確認。learn.chatgpt.com/docs/agent-configuration/rules へ転送される）から引用する。

| 項目 | 引用 |
| --- | --- |
| 置き場所 | "Create a `.rules` file under a `rules/` folder next to an active config layer" |
| 読み込み | "Codex scans `rules/` under every active config layer at startup" |
| プロジェクトの規則 | "Project-local rules under `<repo>/.codex/rules/` load only when the project `.codex/` layer is trusted." |
| TUI の許可 | "When you add a command to the allow list in the TUI, Codex writes to the user layer at `~/.codex/rules/default.rules`" |
| 強さの順 | "Codex applies the most restrictive decision when more than one rule matches (`forbidden` > `prompt` > `allow`)." |
| `allow` | "Run the command outside the sandbox without prompting." |
| `prompt` | "Prompt before each matching invocation." |
| `forbidden` | "Block the request without prompting." |
| `match`・`not_match` | "Examples that Codex validates when it loads your rules." |
| 複数のファイル | "Use more than one `--rules` flag to combine files"（`codex execpolicy check` の説明） |
| 状態 | "Rules are experimental and may change." |

prefix_rule の項目は `pattern`・`decision`・`justification`・`match`・`not_match`。

ドキュメントに書かれていないこと: `codex exec`・`codex review`（承認が `never`）での `prompt` の扱い、構文エラーのときの動き、リンクの扱い。ソースと実測で確かめた。

### 手元の codex

- `codex --version`: `codex-cli 0.172.0`（Homebrew の cask）。
- `codex execpolicy check --help`: `--rules <PATH>`（複数可）、`--pretty`、`--resolve-host-executables` がある。

<a name="spec-source"></a>

### ソース

[openai/codex の rust-v0.172.0](https://github.com/openai/codex/tree/rust-v0.172.0/codex-rs)（fc3036d）。パスは `codex-rs/` から。

| ファイル | 行 | わかったこと |
| --- | --- | --- |
| `core/src/exec_policy.rs` | 61-63 | ディレクトリは `rules`、拡張子は `rules`、TUI の書き込み先は `default.rules` |
| `core/src/exec_policy.rs` | 749-773, 1238-1287 | 設定の層ごとに `rules/` の `*.rules` を名前順に全部読む。`file_type().is_file()` で選ぶので、リンクは読まない |
| `core/src/exec_policy.rs` | 732-746 | TUI は、読み込みに失敗すると空の規則で続ける（全部の規則が効かなくなる） |
| `exec/src/lib.rs` | 643-645, 710-718 | `codex exec` は承認を `never` にする。読み込みに失敗すると `Error loading rules:` を出して終了 1 |
| `cli/src/main.rs` | 1229-1243 | `codex review` は `codex exec review` として動く（上と同じ） |
| `core/src/exec_policy.rs` | 225-247, 55-56 | 承認が `never` のとき、`prompt` は "approval required by policy, but AskForApproval is set to Never" で拒否される |
| `core/src/exec_policy.rs` | 1016-1045, 1068-1107 | 規則に当たるコマンドには、許可の規則を足す提案をしない |
| `core/src/exec_policy.rs` | 64-140 | 提案を禁じる接頭辞に `["git"]` はあるが、`["git", "push"]` などはない |
| `core/src/exec_policy.rs` | 401-403 | 照合では実行ファイル名で引く（`/usr/bin/git` も `git` の規則に当たる） |
| `execpolicy/src/parser.rs` | 133-150 | `match`・`not_match` は、その prefix_rule の規則だけと照らす |
| `execpolicy/src/decision.rs` | 22-29 | `.rules` に書ける decision は `allow`・`prompt`・`forbidden` だけ |
| `execpolicy/src/parser.rs` | 358-361 | `decision` を省くと `allow` になる。省かずに書く |
| `shell-command/src/command_safety/is_dangerous_command.rs` | 205-214 | 組み込みの判定は、`rm` の `-…f…`・`--force` を確認にする。`-f` のない `rm -r` は対象外 |
| `protocol/src/config_types.rs` | 180-190 | 承認の判定者 `approvals_reviewer` の既定は `user`。`auto_review` にすると、モデルが承認を判定する |
| `protocol/src/permissions.rs` | 2395-2438 | `.git`・`.codex`・`.agents`・`.aws` を読み取り専用にするのは、書き込める場所の直下だけ |
| `cli/src/debug_sandbox.rs` | 714-752 | `codex sandbox` は、config が `sandbox_mode` だけのときは read-only で動く |

<a name="spec-measured"></a>

### 実測（2026-11-26、codex-cli 0.172.0）

`codex execpolicy check`（Claude Code の sandbox の中で実行）:

- `git reset --hard` の規則に、`git -C /x reset --hard`・`git reset HEAD~1 --hard`・`git reset -q --hard` は当たらない（位置で決まる前方一致）。
- `match` の例が外れると "expected every example to match at least one rule" で失敗する。構文エラーは starlark のエラーになる。`--rules` に渡したファイルの 1 つでも壊れていると、全体が失敗する（終了 1）。
- `check` は `bash -lc '…'` をコマンドに分けない（Codex 本体は分ける）。

リンクの読み込み（一時の `CODEX_HOME` に壊した規則を置き、`codex exec` が止まるかで判定。モデルへの送信はない）:

| `~/.codex/rules` の形 | 読み込まれたか |
| --- | --- |
| 通常のファイル | 読み込まれた（`Error loading rules:`） |
| ファイルのリンク | **読み込まれない**（そのまま実行が続いた） |
| ディレクトリのリンク | 読み込まれた |

<a name="spec-sandbox"></a>

workspace-write の sandbox（ユーザーが通常のターミナルで `codex sandbox -c 'sandbox_mode="workspace-write"'` を実行。`$HOME` の下の一時リポジトリ）:

| コマンド | 結果 |
| --- | --- |
| `touch new.txt`（対照） | 作れた |
| `git status` | 通った |
| `git reset --hard`・`git checkout -- file`・`git restore file`・`git commit -am` | 失敗（`.git/index.lock` を作れない）。変更は残った |
| `git stash`・`git branch -D side` | 失敗（index と ref を書けない）。何も変わらなかった |
| `git clean -fd` | **通った。未追跡のファイルが消えた** |
| `rm -r dir`・`rm -rf dir` | **通った。ディレクトリが消えた**（`rm -rf` は、組み込みの判定が実行前に確認を出す） |
| `curl github.com` | 失敗（名前解決ができない） |

### 参考にした README の記述との照合

| 記述 | 結果 |
| --- | --- |
| pattern は位置で決まる前方一致で、任意の位置のフラグは表せない | 正しい（上の実測） |
| 構文エラーがあると `Error loading rules:` になり、全部の規則が無効になる | TUI では正しい。`codex exec`・`codex review` は終了 1 で止まる |
| `match`・`not_match` は読み込み時に評価される | 正しい（公式の引用と実測） |
| 確かめるコマンドは `codex execpolicy check --pretty --rules <file> -- <command>` | 正しい。`check` は 0.172.0 の `--help` にも出る |

<a name="done-criteria"></a>

## 完了条件

1. **規則**: 規則ごとに `codex execpolicy check` で、止めたいコマンドが `prompt` になる。`git status`・`git diff`・`git log`・`git show` などの止めたくないコマンドは、どの規則にも当たらない。[表せない形](#rules) が当たらないことも記録する。
2. **setup.sh**: 偽の HOME と、worktree ではない一時ディレクトリに写した `codex/` で次を確かめる。
   - 検査に通る規則なら、`~/.codex/rules/dotfiles.rules` に 0644 の通常のファイルとして入る。中身はリポジトリと同じ。
   - 壊した規則と、`decision = "allow"` を含む規則では止まり（終了 0 以外）、`~/.codex/rules/` に何も書かない。
3. **Codex の動き**（ユーザーが通常のターミナルで実行。規則を入れた後）:
   - Claude Code から頼む 2 つのレビューのコマンドが動く（`codex review --base main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` と `codex exec - -s read-only -c skills.include_instructions=false < <プロンプトのファイル>`）。
   - `codex exec` で、`git status --short` は動き、`git clean -n` は規則で拒否される（規則が読み込まれている証拠）。
   - TUI で `git clean -n` を頼むと、justification の文が付いた確認が出る。接頭辞で今後も許可する選択肢（「commands that start with …」）が出ない。ほかに出た選択肢も記録する（セッションの中だけ許可する選択肢が出るかは、ソースで確かめていない）。
4. **リポジトリの規約**: `python3 -B .github/scripts/check-repo.py`・`python3 -B .github/scripts/test-check-repo.py`・shellcheck・`actionlint`・`zizmor --offline .` が通る。

結果は `test-report.md` に書く。確認のスクリプトは scratchpad に置き、コミットしない。

<a name="rules"></a>

## 規則

decision はすべて `prompt`（ユーザーが明示すれば実行してよい操作なので、`forbidden` にしない）。`allow` は書かない。

| コマンド | decision | 理由 | 表せない形 |
| --- | --- | --- | --- |
| `git clean` | prompt | sandbox の中でも未追跡のファイルが確認なしに消える（実測）。`-n` にも確認が出る | `git -C <dir> clean`・`git -c k=v clean` → 文章のガードレールに任せる |
| `rm -r`・`rm -R`・`rm --recursive`（最初の引数） | prompt | sandbox の中でも確認なしに消える（実測）。`-rf`・`-fr`・`-r -f`・`--force` は組み込みの判定が確認にするので、規則に入れない | `rm dir -r`・`rm -v -r dir`・`find -delete` → 文章のガードレールに任せる |
| `git push` | prompt | 今は sandbox（ネットワーク）が止めるが、「今後は聞かない」で force push も main への push も確認なしに動くようになる | `git -C`・`git -c` の形 → 文章のガードレールに任せる |
| `git reset --hard` | prompt | 同上（`.git`）。未コミットの変更は戻せない | `git reset -q --hard`・`git reset HEAD~1 --hard` → 文章のガードレールに任せる |
| `git checkout --`・`git checkout .` | prompt | 同上 | `git checkout HEAD -- f`・`git checkout -f` → 文章のガードレールに任せる |
| `git restore` | prompt | 同上。`--staged` にも確認が出る | `git -C` の形 → 文章のガードレールに任せる |
| `terraform apply`・`terraform destroy` | prompt | 同上（ネットワーク）。実際のインフラを変える | `terraform -chdir=x apply` → 文章のガードレールに任せる |
| `gh pr merge` | prompt | 同上（ネットワーク）。マージは明示の依頼のときだけ | `gh api` での直接のマージ → 文章のガードレールに任せる |

全部の規則に共通して表せない形: 変数・リダイレクト・`$(...)`・制御構文を含むシェルのスクリプト（`bash -lc '… > /dev/null'` など）は、コマンドに分けられず、規則に当たらない。

外したもの（2026-11-26 にユーザーと決めた）:

- `git stash`・`git branch -D`: sandbox が止める。`git stash` は変更を残すうえ、`list`・`show` にも確認が出る。
- `git switch -f`・`git checkout -f`・`git rebase`・`git commit --amend`・`git filter-branch`: 文章のガードレールに任せる。
- `gh pr create`・`edit`・`comment` など: 後から戻せる。
- `rm -rf` とその書き方の揺れ: 組み込みの判定に任せる。
- `gh auth token` の `forbidden`: sandbox の中でトークンを読めるかを測っていないので、後続の候補にする。
- DB の drop・reset: 文章のガードレールに任せる。

<a name="approach"></a>

## 方針

### ファイルと入れ方

| パス | 役割 |
| --- | --- |
| `~/dotfiles/codex/rules/dotfiles.rules` | 規則の正本（Git 管理） |
| `~/dotfiles/codex/setup.sh` | 検査してから下へコピーする。ユーザーが通常のターミナルで実行する |
| `~/.codex/rules/dotfiles.rules` | Codex が読む写し（0644 の通常のファイル） |
| `~/.codex/rules/default.rules` | 使わない。TUI の「今後は聞かない」の書き込み先 |

最初の依頼（`codex/rules/default.rules` を作り、`~/.codex/rules/default.rules` へ AGENTS.md と同じようにリンクする）から、次の 2 点を変えた（2026-11-26 にユーザーが承認）。

- **リンクをやめてコピーにする**: ファイルのリンクは Codex が読まない（[実測](#spec-measured)）。
- **名前を `dotfiles.rules` にする**: コピー先を `default.rules` にすると、setup.sh を実行し直すたびに TUI で許可した内容が消える。逆に Codex が書き足すと、写しとリポジトリの中身が食い違う。

Codex は `~/.codex/rules/` の両方のファイルを読み、強いほうの decision を使う。

### setup.sh の処理

AGENTS.md のリンクの直後、プラグインのインストールの前に足す。

1. `dotfiles.rules` に `decision = "allow"`（引用符は `"` と `'` のどちらも）があれば、止める（この plan で足した提案）。「allow を書かない」を、文章ではなく仕組みで守る。
2. `codex execpolicy check --rules ~/dotfiles/codex/rules/dotfiles.rules -- git status` で検査する。構文の誤りと、`match`・`not_match` の例の食い違いで失敗する。失敗したら止める。読み込めない規則を入れると、`codex exec` と `codex review` が止まるため。
3. `~/.codex/rules/` がなければ作り、`install -m 0644` でコピーする。

エラーのメッセージは、setup.sh のほかのメッセージに合わせて英語にし、標準エラーに出す。

### 規則のファイルの書き方

- 規則ごとに、理由をコメントで書く（日本語）。`match` と `not_match` を必ず書く。
- `not_match` に、レビューで使う `git status`・`git diff`・`git log`・`git show` などを入れる。
- `justification` は、確認の画面に出て、モデルにも渡る。`developer_instructions` に合わせて日本語で書く。
- `host_executable()` は定義しない。定義すると、そこに書いていない場所の `git` などが規則に当たらなくなる。

<a name="rejected"></a>

## 採らなかった案

- **`~/.codex/rules/default.rules` へのリンク**（最初の依頼の案）: リンクは読まれない。`default.rules` は Codex が書き込む。
- **ディレクトリごとのリンク（`~/.codex/rules` → `~/dotfiles/codex/rules`）**: 読み込みはされる。しかし、TUI での許可が公開リポジトリの中の `default.rules` に書かれる。また、`~/dotfiles` で動く Codex が自分の規則を書き換えられるようになる。
- **`forbidden`**: ユーザーが明示すれば実行してよい操作なので `prompt` にする。
- **`git push --force` だけを止める**: 位置で決まる前方一致なので、`--force` の位置が変わると当たらない。push 全体を `prompt` にする。
- **規則の検査を CI（`check-repo.py`）に足す**: CI に codex を入れる必要がある。setup.sh の検査で、入れる前には止められる。後続の候補にする。

<a name="files"></a>

## 変更するファイル

- `codex/rules/dotfiles.rules`（新規）: [規則](#rules) の 8 つ。
- `codex/setup.sh`: [setup.sh の処理](#approach) を足す。
- `codex/README.md`:
  - 構成の図・`codex/` 内のファイルの表・ファイルと変更権限の表に足す。
  - 「`setup.sh` が行うこと」に手順を足す。
  - rules の節を作る（規則の一覧、入れ方と更新、確かめ方、注意）。
  - 「日常運用」に、規則を変えたときの手順を足す。
  - 「トラブルシューティング」に `Error loading rules:` を足す。
  - 「編集の指針」の Rules の文を、rules の節へのリンクに変える。
  - 「今後の改善候補」から rules の項を外す。
  - 「参考資料」に Rules のページを足す。
- `docs/work/20261126_codex-rules/`: この plan と `test-report.md`。

`codex/` は Edit ツールで書く（`.claude/settings.json` で、Bash からの書き込みが止まり、Edit は確認を求める）。

<a name="steps"></a>

## 手順

1. この plan を `/crit-review` で承認してもらう。
2. `codex/rules/dotfiles.rules` を書く → 完了条件 1 を確かめ、`test-report.md` に記録する。
3. `codex/setup.sh` を変える → 完了条件 2 を確かめる。
4. `codex/README.md` を変える → 完了条件 4 を確かめる。
5. `/review` → 指摘を直す。
6. ユーザーが通常のターミナルで規則を入れ、完了条件 3 を確かめる。
   - setup.sh は worktree の中では止まるので、この確認だけは、検査とコピーの 3 行を手で実行してもらう。手順は Claude が示す。
   - `codex review` の結果は、Codex のレビュー（1 回目）として扱う。SKILL_ROUTING の方法で記録を読み、`test-report.md` に書いてから採否を整理する。
7. `/crit-review` でブランチの差分を開く → 承認後にコミット・`cc-safe-push`・`cc-safe-pr`・`gh pr checks`。
8. マージ後、ユーザーが `~/dotfiles`（main）で `codex/setup.sh` を実行する。

ロールバック: `rm ~/.codex/rules/dotfiles.rules` を実行して、Codex を起動し直す（規則は起動時に読む）。リポジトリは、この PR の revert で戻る。データやほかの設定は変えない。

<a name="out-of-scope"></a>

## 対象外と残るリスク

- **experimental**: 仕様が変わりうる。Codex を更新した後は、setup.sh を実行し直して検査を通す。検査で気づけるのは読み込みの失敗だけで、照合の仕方が変わっても気づけない。
- **表せない形**: [規則](#rules) の表のとおり、文章のガードレールに任せる。
- **写しの食い違い**: コピーなので、規則を変えても setup.sh を実行し直すまで効かない。`~/.codex/rules/dotfiles.rules` を手で編集すると、検査を通らないまま読み込まれうる。
- **読み込みの失敗**: 写しが壊れると、`codex exec`・`codex review` が止まり、TUI では全部の規則が効かなくなる。ロールバックの手順で戻す。
- **allow の検査は文字列の一致**: starlark の文字列の連結などで書けば通る。主な守りは、`codex/` への書き込みの確認（`.claude/settings.json`）と、PR のレビュー。
- **`approvals_reviewer`**: `auto_review` にすると、`prompt` の確認をモデルが判定する（ソース）。人の確認が要る、という前提が崩れるので、設定しない。今は設定していない（既定は `user`）。
- **確認が多めに出る**: `git clean -n`・`git restore --staged`・ビルドの成果物の `rm -r` でも確認が出る。
- **`/tmp`・`$TMPDIR` の下のリポジトリ**: `.git` が守られない（ソースからの推測。実測はしていない）。この規則の対象は確認になるが、`git stash`・`git branch -D`・`git commit` などは確認なしに動く。
- **Codex のデスクトップ版**: 同じ `~/.codex/rules` を読むかは確かめていない。
- **sandbox の中で `gh auth token` などがトークンを読めるか**: 測っていない（後続の候補）。
