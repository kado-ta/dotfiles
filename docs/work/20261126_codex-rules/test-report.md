---
status: in-progress
created: 2026-11-26
---

# Codex の rules の試験記録

[plan.md](plan.md#done-criteria) の完了条件の結果。事前の実測（`codex sandbox`・リンクの読み込み）は [plan.md の実測](plan.md#spec-measured) にある。

## 目次

- [環境](#environment)
- [完了条件 1: 規則の照合](#rules-check)
- [完了条件 2: setup.sh](#setup)
- [完了条件 3: Codex の動き](#codex)
- [完了条件 4: リポジトリの規約](#repo-checks)
- [レビュー](#review)
- [Codex のレビュー](#codex-review)

<a name="environment"></a>

## 環境

- 2026-11-26、macOS（Darwin 25.6.0）、codex-cli 0.172.0（Homebrew の cask）。
- 完了条件 1・2・4 は、Claude Code の sandbox の中で実行した。確認のスクリプトは scratchpad に置き、コミットしていない。
- 完了条件 3 は、ユーザーが通常のターミナルで実行した。

<a name="rules-check"></a>

## 完了条件 1: 規則の照合

`codex execpolicy check --resolve-host-executables --rules codex/rules/dotfiles.rules -- <コマンド>` の `decision` を見た（コマンドは実行されない）。Codex 本体は実行ファイル名でも照らす（`core/src/exec_policy.rs` L401-403）ので、`--resolve-host-executables` を付けた。`none` は、どの規則にも当たらないこと。

- 組み込みの判定に任せる形: Codex 本体では、組み込みの判定（`shell-command/src/command_safety/is_dangerous_command.rs` L205-214）が確認にする。`execpolicy check` は組み込みの判定を使わないので、ここでは `none` になる。
- `bash -lc '…'`: Codex 本体は、変数・リダイレクト・`$(...)` を含まなければコマンドに分けて照らす。`execpolicy check` はスクリプトを分けないので、ここで確かめたのは、リダイレクトを含んで分けられない形だけ。
- 最後の表は、`--rules` にもう 1 つ、先頭が絶対パスの `allow` だけのファイルを渡した（TUI の「今後は聞かない」と同じ形）。

結果: 97 件すべてが期待どおり（[レビュー](#review) の後の規則で実行）。
#### 止めたいコマンド（prompt になる）

| コマンド | 期待 | 結果 | 当たった接頭辞（decision） | 判定 |
| --- | --- | --- | --- | --- |
| `git clean -fd` | prompt | prompt | git clean (prompt) | OK |
| `git clean -fdx` | prompt | prompt | git clean (prompt) | OK |
| `git clean -ffdx` | prompt | prompt | git clean (prompt) | OK |
| `git clean -n` | prompt | prompt | git clean (prompt) | OK |
| `/usr/bin/git clean -fd` | prompt | prompt | /usr/bin/git clean (prompt) | OK |
| `/opt/homebrew/bin/git clean -fd` | prompt | prompt | /opt/homebrew/bin/git clean (prompt) | OK |
| `rm -r dir` | prompt | prompt | rm -r (prompt) | OK |
| `rm -R dir` | prompt | prompt | rm -R (prompt) | OK |
| `rm --recursive dir` | prompt | prompt | rm --recursive (prompt) | OK |
| `rm -rv dir` | prompt | prompt | rm -rv (prompt) | OK |
| `rm -Rv dir` | prompt | prompt | rm -Rv (prompt) | OK |
| `rm -vr dir` | prompt | prompt | rm -vr (prompt) | OK |
| `rm -vR dir` | prompt | prompt | rm -vR (prompt) | OK |
| `rm -r -f dir` | prompt | prompt | rm -r (prompt) | OK |
| `/bin/rm -r dir` | prompt | prompt | /bin/rm -r (prompt) | OK |
| `git push` | prompt | prompt | git push (prompt) | OK |
| `git push origin main` | prompt | prompt | git push (prompt) | OK |
| `git push --force origin topic` | prompt | prompt | git push (prompt) | OK |
| `git push -f` | prompt | prompt | git push (prompt) | OK |
| `git push --force-with-lease origin topic` | prompt | prompt | git push (prompt) | OK |
| `git reset --hard` | prompt | prompt | git reset --hard (prompt) | OK |
| `git reset --hard HEAD~1` | prompt | prompt | git reset --hard (prompt) | OK |
| `git reset --hard origin/main` | prompt | prompt | git reset --hard (prompt) | OK |
| `git checkout -- file.txt` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout -- .` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout .` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout file.txt` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout HEAD -- file.txt` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout -f` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout main` | prompt | prompt | git checkout (prompt) | OK |
| `git checkout -b topic` | prompt | prompt | git checkout (prompt) | OK |
| `git restore file.txt` | prompt | prompt | git restore (prompt) | OK |
| `git restore .` | prompt | prompt | git restore (prompt) | OK |
| `git restore --staged file.txt` | prompt | prompt | git restore (prompt) | OK |
| `git restore --source HEAD~1 file.txt` | prompt | prompt | git restore (prompt) | OK |
| `terraform apply` | prompt | prompt | terraform apply (prompt) | OK |
| `terraform apply -auto-approve` | prompt | prompt | terraform apply (prompt) | OK |
| `terraform destroy` | prompt | prompt | terraform destroy (prompt) | OK |
| `terraform destroy -target=aws_s3_bucket.x` | prompt | prompt | terraform destroy (prompt) | OK |
| `gh pr merge` | prompt | prompt | gh pr merge (prompt) | OK |
| `gh pr merge 123 --squash --delete-branch` | prompt | prompt | gh pr merge (prompt) | OK |
| `/opt/homebrew/bin/gh pr merge 123` | prompt | prompt | /opt/homebrew/bin/gh pr merge (prompt) | OK |

#### 止めたくないコマンド（どの規則にも当たらない）

| コマンド | 期待 | 結果 | 当たった接頭辞（decision） | 判定 |
| --- | --- | --- | --- | --- |
| `git status` | none | none | - | OK |
| `git status --short --branch` | none | none | - | OK |
| `git diff` | none | none | - | OK |
| `git diff --stat main` | none | none | - | OK |
| `git diff --merge-base main` | none | none | - | OK |
| `git log --oneline -5` | none | none | - | OK |
| `git log main..HEAD` | none | none | - | OK |
| `git show HEAD` | none | none | - | OK |
| `git merge-base main HEAD` | none | none | - | OK |
| `git rev-parse HEAD` | none | none | - | OK |
| `git branch --show-current` | none | none | - | OK |
| `git fetch` | none | none | - | OK |
| `git pull` | none | none | - | OK |
| `git switch main` | none | none | - | OK |
| `git reset` | none | none | - | OK |
| `git reset --soft HEAD~1` | none | none | - | OK |
| `git reset HEAD file.txt` | none | none | - | OK |
| `git stash list` | none | none | - | OK |
| `git add -A` | none | none | - | OK |
| `git commit -m msg` | none | none | - | OK |
| `rm file.txt` | none | none | - | OK |
| `mkdir -p dir` | none | none | - | OK |
| `ls -la` | none | none | - | OK |
| `terraform plan` | none | none | - | OK |
| `terraform init` | none | none | - | OK |
| `terraform fmt` | none | none | - | OK |
| `terraform validate` | none | none | - | OK |
| `terraform show` | none | none | - | OK |
| `gh pr view 123` | none | none | - | OK |
| `gh pr list` | none | none | - | OK |
| `gh pr checks` | none | none | - | OK |
| `gh pr diff` | none | none | - | OK |
| `gh pr create` | none | none | - | OK |

#### 組み込みの判定に任せる形（規則には当たらない）

| コマンド | 期待 | 結果 | 当たった接頭辞（decision） | 判定 |
| --- | --- | --- | --- | --- |
| `rm -rf dir` | none | none | - | OK |
| `rm -fr dir` | none | none | - | OK |
| `rm -f file.txt` | none | none | - | OK |
| `rm --force -r dir` | none | none | - | OK |

#### 表せない形（規則には当たらない。文章のガードレールに任せる）

| コマンド | 期待 | 結果 | 当たった接頭辞（decision） | 判定 |
| --- | --- | --- | --- | --- |
| `git -C /repo clean -fd` | none | none | - | OK |
| `git -c core.pager=cat push` | none | none | - | OK |
| `git -C /repo reset --hard` | none | none | - | OK |
| `git reset -q --hard` | none | none | - | OK |
| `git reset HEAD~1 --hard` | none | none | - | OK |
| `rm dir -r` | none | none | - | OK |
| `rm -v -r dir` | none | none | - | OK |
| `rm -rd dir` | none | none | - | OK |
| `terraform -chdir=infra apply` | none | none | - | OK |
| `gh api -X PUT repos/o/r/pulls/1/merge` | none | none | - | OK |
| `bash -lc 'git clean -fd > /dev/null'` | none | none | - | OK |

#### ほかのファイルに、先頭が絶対パスの allow があるとき（default.rules に `/usr/bin/git`・`/opt/homebrew/bin/git`・`/bin/rm`・`/opt/homebrew/bin/gh`・`/usr/local/bin/git` の allow）

| コマンド | 期待 | 結果 | 当たった接頭辞（decision） | 判定 |
| --- | --- | --- | --- | --- |
| `/usr/bin/git push --force origin main` | prompt | prompt | /usr/bin/git (allow), /usr/bin/git push (prompt) | OK |
| `/opt/homebrew/bin/git reset --hard` | prompt | prompt | /opt/homebrew/bin/git (allow), /opt/homebrew/bin/git reset --hard (prompt) | OK |
| `/bin/rm -r dir` | prompt | prompt | /bin/rm (allow), /bin/rm -r (prompt) | OK |
| `/opt/homebrew/bin/gh pr merge 123` | prompt | prompt | /opt/homebrew/bin/gh (allow), /opt/homebrew/bin/gh pr merge (prompt) | OK |
| `git push` | prompt | prompt | git push (prompt) | OK |
| `/usr/local/bin/git push --force origin main` | allow | allow | /usr/local/bin/git (allow) | OK |
| `/usr/bin/git status` | allow | allow | /usr/bin/git (allow) | OK |


<a name="setup"></a>

## 完了条件 2: setup.sh

worktree ではない一時ディレクトリ（`$TMPDIR` の下）に `codex/` を写し、偽の HOME で `./codex/setup.sh` を実行した（shebang の `-e` が効く形）。プラグインと Understand Anything は、偽の HOME に目印を置いて飛ばした。gstack の手順は偽の HOME にないので、規則の後のそこで止まる（終了 1）。sandbox の中では macOS の mktemp の既定の場所に書けないので、`TMPDIR` を環境変数で渡した。

結果: 18 通り・88 項目がすべて OK（[Codex のレビュー](#codex-review) の修正の後の setup.sh で実行）。

| 場合 | 確かめたこと | 結果 |
| --- | --- | --- |
| A. 正しい規則（`default.rules` に名前だけの allow が既にある） | `installed:` と表示 / 通常のファイル / 権限が 644 / 中身がリポジトリと同じ / 規則の後の手順まで進む / 一時ディレクトリを残さない / `default.rules` は変わらない / `new file:` と表示 / 警告しない | OK |
| K. A の後に、規則を変えて入れ直す | A の前半と同じ / 差分に変えた行が出る | OK |
| B. 構文エラー | 終了 1 / `codex execpolicy check failed on` / `dotfiles.rules` を入れない / 後の手順に進まない | OK |
| C. `decision = "allow"` | 終了 1 / `has an allow rule`（該当の行も出る）/ 入れない / 進まない | OK |
| D. `decision='allow'`（一重引用符・空白なし） | C と同じ | OK |
| E. `match` の例が外れる | 終了 1 / `codex execpolicy check failed on`（"expected every example to match at least one rule"）/ 入れない / 進まない | OK |
| F. `decision` を省く（allow になる） | 終了 1 / `without decision` / 入れない / 進まない | OK |
| G. `decision =` の後で改行して `"allow"` | 終了 1 / `has an allow rule`（`"allow"` の行が出る）/ 入れない / 進まない | OK |
| H. `git diff` に当たる forbidden | 終了 1 / ``matches `git diff` `` / 入れない / 進まない | OK |
| I. 既存の `default.rules` が壊れている | 終了 1 / `cannot be loaded together` / 入れない / 進まない | OK |
| J. 既存の `default.rules` に `["/usr/local/bin/git"]` の allow | A の前半と同じ / `WARNING: the allow rules above` / 該当の行を表示 | OK |
| L. `~/.codex/rules` に、壊れたファイルへのリンク | A の前半と同じ（リンクは組み合わせの検査に含めない） | OK |
| M. `.` で始まる名前の壊れた規則（`.local.rules`。Codex は読む） | 終了 1 / `cannot be loaded together` / 入れない / 進まない | OK |
| N. 読み取り専用（0444）の `default.rules` | A の前半と同じ（一時の写しの後片付けで止まらない） | OK |
| O. バイト順で先の `B.rules` の `host_executable()` で、`a.rules` の `match` の例が外れる | 終了 1 / `cannot be loaded together` / 入れない / 進まない | OK |
| P. `~/.codex/rules` 自体が、壊れた規則を含むディレクトリへのリンク | 終了 1 / `cannot be loaded together` / 入れない / 進まない | OK |
| Q. 既存の規則が読み取れない（権限 000） | 終了 1 / `install:` の失敗 / 入れない / 進まない | OK |
| R. `/usr/bin/git diff` にだけ当たる規則 | 終了 1 / ``matches `/usr/bin/git diff` `` / 入れない / 進まない | OK |

経緯:

- 最初は `bash codex/setup.sh` で実行し、shebang の `-e` が効かずに A が終了 0 になった。README の実行の仕方に合わせて、直接実行に変えた。
- macOS の `mktemp -d` は、テンプレートがないと `_CS_DARWIN_USER_TEMP_DIR` を使い、`TMPDIR` を見ない（`man mktemp`）。setup.sh は `mktemp -d "${TMPDIR:-/tmp}/codex-rules.XXXXXX"` にした。通常のターミナルの `TMPDIR` は同じ `/var/folders/…/T/` なので、場所は変わらない。
- N の、ターミナルで `rm` が読み取り専用の写しの削除の確認を求める状況そのものは、sandbox の中で端末を開けない（openpty が止まる）ので再現していない。写しを `install -m 0600` で作ることをコードで確かめた。
- O は、`/bin/bash`（3.2.57）の glob が `LANG=ja_JP.UTF-8` では `a.rules B.rules`、`LC_ALL=C` では `B.rules a.rules`（Codex と同じバイト順）に並ぶことを確かめたうえで足した。

<a name="codex"></a>

## 完了条件 3: Codex の動き

ユーザーが通常のターミナルで、worktree の `codex/rules/dotfiles.rules` を `~/.codex/rules/dotfiles.rules` に入れた（setup.sh は worktree の中では止まるので、検査とコピーだけを手で行った。SHA-256 `4e74fccb…bfb91` で、コミット 32870c8 の中身と同じ）。`~/.codex/rules` には、ほかのファイルはない。結果は、SKILL_ROUTING の方法で `~/.codex/sessions` の最終メッセージから読んだ。

| 確認 | コマンド | 結果 |
| --- | --- | --- |
| `codex exec` が動き、規則が効く | `codex exec - -s read-only -c skills.include_instructions=false < tmp/codex-exec-check.md`（`git status --short` と `git clean -n` を順に実行させる） | `Error loading rules:` で止まらずに動いた。`git status --short` は終了 0。`git clean -n` は `approval required by policy, but AskForApproval is set to Never` で拒否された |
| `codex review` が動く | `codex review --base main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` | 最後まで動き、指摘 6 件を返した（[Codex のレビュー](#codex-review)） |
| TUI で確認が出て、「今後は聞かない」が出ない | 一時の git リポジトリで `codex` を起動し、`git clean -n` を頼む | 確認が出た。選択肢は「Yes, proceed」と「No, and tell Codex what to do differently」の 2 つだけで、接頭辞で許可する選択肢も、セッションの中だけ許可する選択肢も出なかった（ユーザーの報告） |

<a name="repo-checks"></a>

## 完了条件 4: リポジトリの規約

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 終了 0（すべて PASS） |
| `python3 -B .github/scripts/test-check-repo.py` | 終了 0（147 件 OK） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了 0 |
| `actionlint` | 終了 0 |
| `zizmor --offline .` | 終了 0（No findings） |

README（ルートと `codex/`）・plan・この文書の内部リンクの参照先があり、アンカーが一意であることも確かめた。

<a name="review"></a>

## レビュー

2026-11-26 に `/review` を実行した。差分は 9b81ce7..13e6195（レビューの後の修正の前）。

- 専門家: Testing・Maintainability・Security・Simplification。Security は範囲の検出（`SCOPE_AUTH=false`）では選ばれなかったが、Codex の承認の規則（権限の境界）を変えるので加えた。
- Red Team（差分が 200 行を超えるため）と、Claude の adversarial のレビュー。Codex の外部レビューは、gstack の `codex_reviews` が無効なので行っていない。
- Simplification は NO FINDINGS。

指摘と対応（判断は [plan.md](plan.md#review-changes) の D1〜D4）:

| 指摘 | 出どころ | 確かめたこと | 対応 |
| --- | --- | --- | --- |
| `decision` を省いた規則（allow になる）が setup.sh の検査を通って入る | 中心のレビュー・Testing・Maintainability・Security | 偽の HOME で再現（`"decision":"allow"`、`installed:`） | D1 で直した（完了条件 2 の F） |
| `decision =` の後で改行した `"allow"`、変数の allow も通る | Security・adversarial | 数の一致の検査で止まることを試した | D1 で直した（G） |
| `/usr/bin/git` などの絶対パスの allow があると、名前だけの規則が当たらない。`/usr/bin/git fetch` の「今後は聞かない」でも作られうる | Red Team・adversarial | `execpolicy/src/policy.rs` L403-412 を読み、再現した | D2 で直した（完了条件 1 の最後の表、完了条件 2 の J） |
| `git checkout <path>` が当たらない | 中心のレビュー・adversarial | — | D3 で checkout 全体を prompt にした |
| `rm -rv`・`-Rv`・`-vr`・`-vR` が当たらない | Red Team・adversarial | 再現した（`matchedRules: []`） | D4 で足した |
| git の読み取りに当たる規則が入っても検査が通り、レビューが拒否される | adversarial | — | D1 で直した（H） |
| 既存のファイルと組み合わせると読み込めない場合（別のファイルの `host_executable()`、壊れた `default.rules`）を検査しない | Red Team | `host_executable()` での読み込みの失敗を再現した | D1 で直した（I）。絶対パスを先頭の候補に入れたので、`match` の絶対パスの例は完全一致で当たる |
| 検査とコピーでファイルを別々に読む。作業ツリーの中身を差分なしに入れる | Red Team・adversarial | — | D1 で直した（同じ写しを使う。差分を表示する。K） |
| ルートの README の setup.sh と `codex/` の説明が古い | 中心のレビュー | — | 直した |
| トラブルシューティングのコマンドが `default.rules` を見ない | adversarial | — | 1 ファイルずつ検査するコマンドにした |
| `codex` がないときのメッセージが原因と合わない | adversarial | — | メッセージに `(is codex installed?)` を足した |
| プロジェクトの `.codex/rules`、Codex による `codex/rules/` の書き換え、同梱の codex の版の違い | Red Team・adversarial | 同梱の codex の版（`0.171.0-alpha.13.2`）を確かめた | plan の [対象外と残るリスク](plan.md#out-of-scope) に書いた |
| 完了条件 3 がまだ空 | Testing | — | plan の手順 6 で、ユーザーが実行する予定のもの |

動作の確認（smoke）: gstack の `gstack-qa-evidence` は権限で拒否されるので使わず、scratchpad のスクリプトで行った。修正の前の setup.sh で、`decision` を省いた規則が入ることを再現した。修正の後は、完了条件 1・2 をすべて実行し直した。

### 2 回目（修正の範囲）

13e6195 から作業ツリーまでの修正を、Claude の adversarial のレビューで見直した。専門家と Red Team は、もう一度は動かしていない（費用に見合わないと判断した。ブランチ全体の独立した見直しは、完了条件 3 の `codex review` で行う）。指摘 9 件と対応は [plan.md](plan.md#review-changes) の 2 つ目の表にある。コードを直したのは、組み合わせの検査の並びと `.` で始まる名前（完了条件 2 の M・O）と、一時の写しの権限と trap（N）。ほかは文書を直した。`canonical_matching` は公式ドキュメントにないので使わない。

全体を見直す 3 回目は行っていないので、`/review` としては収束していない（修正の回数は 2）。

<a name="codex-review"></a>

## Codex のレビュー

### 1 回目（2026-11-26、32870c8）

完了条件 3 の `codex review --base main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を、このタスクの Codex のレビューの 1 回目とした（上限は 5 回）。`--base main` は、HEAD と main の merge-base（9b81ce7）からの差分を見る（`codex-rs/prompts/src/review_request.rs` L21・L62-68）ので、ローカルの main が先に進んでいても、このブランチの変更だけが対象になる。結果は SKILL_ROUTING の方法で、最終メッセージ（`last_agent_message`）から読んだ。

Codex の総評は "patch is incorrect"（confidence 0.98）。指摘と採否:

| # | 指摘（優先度） | 採否 | 理由と対応 |
| --- | --- | --- | --- |
| 1 | `CODEX_HOME` を変えていると、規則が使われる場所に入らない（P2） | 文書だけ | `AGENTS.md` のリンクも `~/.codex` 固定で、README に書いてある前からの決まり。ユーザーは `CODEX_HOME` を使っていない。README のトラブルシューティングに、規則も同じだと書いた |
| 2 | `~/.codex/rules` 自体がリンクだと、`find` が中を見ない（P2） | 採用 | Codex はディレクトリのリンクを読む（[plan の実測](plan.md#spec-measured)）。`find -H` にした（完了条件 2 の P） |
| 3 | 既存の規則を写すのに失敗しても検査が続く（P2） | 採用 | `find -exec … \;` は子の失敗を返さない。1 つずつ `install` し、`-e` で止まるようにした（Q） |
| 4 | 読み取りの検査が、絶対パスの git を見ない（P2） | 採用 | `git`・`/usr/bin/git`・`/opt/homebrew/bin/git` のそれぞれで照らすようにした（R） |
| 5 | 複数行で書いた絶対パスの allow を警告しない（P2） | 文書だけ | TUI が書くのは 1 行の形（`execpolicy/src/amend.rs` L78-79）。複数行を見るには規則の解釈が要る。警告は 1 行の形だけを見る、と setup.sh のコメントと README に書いた |
| 6 | トラブルシューティングで、Codex と同じ対象と順でまとめて検査する（P3） | 採用 | まとめて検査するコマンドを先に置き、1 つずつの検査は原因を絞る手順にした。偽の HOME の zsh で、正しい規則では `OK`、壊れた `.local.rules` を足すと失敗と `NG:` が出ることを確かめた |
