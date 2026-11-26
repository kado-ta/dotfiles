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

<a name="environment"></a>

## 環境

- 2026-11-26、macOS（Darwin 25.6.0）、codex-cli 0.172.0（Homebrew の cask）。
- 完了条件 1・2・4 は、Claude Code の sandbox の中で実行した。確認のスクリプトは scratchpad に置き、コミットしていない。
- 完了条件 3 は、ユーザーが通常のターミナルで実行した。

<a name="rules-check"></a>

## 完了条件 1: 規則の照合

`codex execpolicy check --resolve-host-executables --rules codex/rules/dotfiles.rules -- <コマンド>` の `decision` を見た（コマンドは実行されない）。Codex 本体は常に実行ファイル名で照らす（`core/src/exec_policy.rs` L401-403）ので、`--resolve-host-executables` を付けた。`none` は、どの規則にも当たらないこと。

結果: 83 件すべてが期待どおり。

#### 止めたいコマンド（prompt になる）

| コマンド | 期待 | 結果 | 当たった接頭辞 | 判定 |
| --- | --- | --- | --- | --- |
| `git clean -fd` | prompt | prompt | git clean | OK |
| `git clean -fdx` | prompt | prompt | git clean | OK |
| `git clean -ffdx` | prompt | prompt | git clean | OK |
| `git clean -n` | prompt | prompt | git clean | OK |
| `/usr/bin/git clean -fd` | prompt | prompt | git clean | OK |
| `/opt/homebrew/bin/git clean -fd` | prompt | prompt | git clean | OK |
| `rm -r dir` | prompt | prompt | rm -r | OK |
| `rm -R dir` | prompt | prompt | rm -R | OK |
| `rm --recursive dir` | prompt | prompt | rm --recursive | OK |
| `rm -r -f dir` | prompt | prompt | rm -r | OK |
| `/bin/rm -r dir` | prompt | prompt | rm -r | OK |
| `git push` | prompt | prompt | git push | OK |
| `git push origin main` | prompt | prompt | git push | OK |
| `git push --force origin topic` | prompt | prompt | git push | OK |
| `git push -f` | prompt | prompt | git push | OK |
| `git push --force-with-lease origin topic` | prompt | prompt | git push | OK |
| `git reset --hard` | prompt | prompt | git reset --hard | OK |
| `git reset --hard HEAD~1` | prompt | prompt | git reset --hard | OK |
| `git reset --hard origin/main` | prompt | prompt | git reset --hard | OK |
| `git checkout -- file.txt` | prompt | prompt | git checkout -- | OK |
| `git checkout -- .` | prompt | prompt | git checkout -- | OK |
| `git checkout .` | prompt | prompt | git checkout . | OK |
| `git restore file.txt` | prompt | prompt | git restore | OK |
| `git restore .` | prompt | prompt | git restore | OK |
| `git restore --staged file.txt` | prompt | prompt | git restore | OK |
| `git restore --source HEAD~1 file.txt` | prompt | prompt | git restore | OK |
| `terraform apply` | prompt | prompt | terraform apply | OK |
| `terraform apply -auto-approve` | prompt | prompt | terraform apply | OK |
| `terraform destroy` | prompt | prompt | terraform destroy | OK |
| `terraform destroy -target=aws_s3_bucket.x` | prompt | prompt | terraform destroy | OK |
| `gh pr merge` | prompt | prompt | gh pr merge | OK |
| `gh pr merge 123 --squash --delete-branch` | prompt | prompt | gh pr merge | OK |

#### 止めたくないコマンド（どの規則にも当たらない）

| コマンド | 期待 | 結果 | 当たった接頭辞 | 判定 |
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
| `git checkout main` | none | none | - | OK |
| `git checkout -b topic` | none | none | - | OK |
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

Codex 本体では、組み込みの判定（`shell-command/src/command_safety/is_dangerous_command.rs` L205-214）が確認にする。`execpolicy check` は組み込みの判定を使わないので、ここでは `none` になる。

| コマンド | 期待 | 結果 | 当たった接頭辞 | 判定 |
| --- | --- | --- | --- | --- |
| `rm -rf dir` | none | none | - | OK |
| `rm -fr dir` | none | none | - | OK |
| `rm -f file.txt` | none | none | - | OK |
| `rm --force -r dir` | none | none | - | OK |

#### 表せない形（規則には当たらない。文章のガードレールに任せる）

`bash -lc '…'` は、Codex 本体では、変数・リダイレクト・`$(...)` を含まなければコマンドに分けて照らす。`execpolicy check` はスクリプトを分けないので、ここで確かめたのは、リダイレクトを含んで分けられない形だけ。

| コマンド | 期待 | 結果 | 当たった接頭辞 | 判定 |
| --- | --- | --- | --- | --- |
| `git -C /repo clean -fd` | none | none | - | OK |
| `git -c core.pager=cat push` | none | none | - | OK |
| `git -C /repo reset --hard` | none | none | - | OK |
| `git reset -q --hard` | none | none | - | OK |
| `git reset HEAD~1 --hard` | none | none | - | OK |
| `git checkout HEAD -- file.txt` | none | none | - | OK |
| `git checkout -f` | none | none | - | OK |
| `rm dir -r` | none | none | - | OK |
| `rm -v -r dir` | none | none | - | OK |
| `terraform -chdir=infra apply` | none | none | - | OK |
| `gh api -X PUT repos/o/r/pulls/1/merge` | none | none | - | OK |
| `bash -lc 'git clean -fd > /dev/null'` | none | none | - | OK |

<a name="setup"></a>

## 完了条件 2: setup.sh

worktree ではない一時ディレクトリ（`$TMPDIR` の下）に `codex/` を写し、偽の HOME で `./codex/setup.sh` を実行した（shebang の `-e` が効く形）。プラグインと Understand Anything は、偽の HOME に目印を置いて飛ばした。gstack の手順は偽の HOME にないので、規則の後のそこで止まる。

| 場合 | 確かめたこと | 結果 |
| --- | --- | --- |
| A. 正しい規則（`~/.codex/rules/default.rules` が既にある） | `installed:` と表示 / 通常のファイル（リンクではない）/ 権限が 644 / 中身がリポジトリと同じ / `default.rules` は変わらない / 規則の後の gstack の手順まで進む（終了 1。偽の HOME に gstack がないため） | すべて OK |
| B. 構文エラーを足した | 終了 1 / `failed codex execpolicy check` / `~/.codex/rules` を作らない / 後の手順に進まない | すべて OK |
| C. `decision = "allow"` を足した | 終了 1 / `has an allow rule`（該当行の番号も出る）/ `~/.codex/rules` を作らない / 後の手順に進まない | すべて OK |
| D. `decision='allow'`（一重引用符・空白なし） | C と同じ | すべて OK |
| E. `match` の例が外れる規則を足した | 終了 1 / `failed codex execpolicy check`（"expected every example to match at least one rule"）/ `~/.codex/rules` を作らない / 後の手順に進まない | すべて OK |

最初は `bash codex/setup.sh` で実行し、shebang の `-e` が効かずに A が終了 0 になった。B〜E は明示の `exit 1` で止まるので結果は同じだったが、README の実行の仕方に合わせて直接実行に変えた。

<a name="codex"></a>

## 完了条件 3: Codex の動き

（ユーザーが通常のターミナルで実行した後に記録する）

<a name="repo-checks"></a>

## 完了条件 4: リポジトリの規約

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 終了 0（すべて PASS） |
| `python3 -B .github/scripts/test-check-repo.py` | 終了 0（147 件 OK） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了 0 |
| `actionlint` | 終了 0 |
| `zizmor --offline .` | 終了 0（No findings） |

README と plan の内部リンクの参照先があり、アンカーが一意であることも確かめた。
