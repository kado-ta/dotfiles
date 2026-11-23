---
status: done
created: 2026-11-19
---

# 試験記録: git を経由した書き換えの確認（cc-checkout-guard）

関連: [design](design.md)・[plan](plan.md)・[research](research-git-route.md)

ブランチ `fix/git-route-writes` の f0594f5（Task 8 まで）で行った。手動の確認は、人間が 2026-11-19 に普段のターミナルと Claude Code の `!` で行った。

最終レビュー・`/review`・`/security-review` の修正の後、2026-11-20 に 00f19e1 で自動の検査（1 章）を取り直した。人間が確認コマンドを入れ直し（2 章）、速さ（5 章）を測り直した。3 章と 4 章の手動の確認は f0594f5 のときのもので、取り直していない。その後に足した止め方（pull、rerere、属性、`--output` など）は、自動の検査だけで確かめた。

<a name="auto"></a>

## 1. 自動の検査

worktree をカレントディレクトリにして、Claude の Bash ツール（sandbox の中）で、00f19e1 で実行した。f0594f5 のときは、確認コマンドのテストが 103 件、関数のテストが 10 件、`test-check-repo.py` が 78 件で、すべて OK だった。

| コマンド | 結果 |
| --- | --- |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-checkout-guard.py` | 138 件 OK（pty を使う 3 件は sandbox の中でスキップ） |
| `/usr/bin/python3 -B claude/hooks/tests/test-checkout-function.py` | 11 件 OK |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | pass=94 fail=0 |
| `bash claude/hooks/tests/test-validate-command.sh` | pass=29 fail=0 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | pass=66 fail=0 |
| `bash claude/hooks/tests/test-gh-read-token.sh` | pass=24 fail=0 |
| `bash claude/hooks/tests/test-guard-additional-dirs.sh` | pass=17 fail=0 |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` | 53 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` | 75 件 OK |
| `python3 -B .github/scripts/check-repo.py` | 11 項目すべて PASS（`checkout-guard` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 80 件 OK |
| `shellcheck -S warning`（追跡しているシェルスクリプト） | 終了コード 0 |
| `actionlint` | 終了コード 0 |

pty を使う 3 件（端末での y/N の確認）は、下の 3 章の手動の確認で代えた。

<a name="install"></a>

## 2. インストールと sandbox の判定

- 人間が普段のターミナルで、worktree から README の 2 行を実行した。`/usr/local/libexec/claude-guard/cc-checkout-guard` は root:wheel の 0755 で、ブランチの `claude/bin/cc-checkout-guard` と中身が同じだった（`cmp`）。
- `cc-checkout-guard status` の結果は、どれも期待どおりだった。
- 2026-11-20 に、人間が普段のターミナルで、確認コマンドを最後に変えたコミット（24cdd4c）の版を入れ直した。`cmp` で、ブランチの `claude/bin/cc-checkout-guard` と同じだった。

| 場所 | 結果 |
| --- | --- |
| Claude の Bash ツール | `sandbox: yes` |
| このセッションの `!` | `sandbox: no` |
| Ghostty | `sandbox: no` |
| VS Code の統合ターミナル | `sandbox: no` |

<a name="function"></a>

## 3. zsh の `git` 関数

`tmp/guard-trial.sh` が一時ディレクトリに作ったダミーのリポジトリで試した（`main`、`.claude/settings.json` を変える `feature`、README だけを変える `docs`）。関数は worktree の `bin/.zshrc` から読み込んだ。人間の git は Homebrew の 2.56.1。

| 形 | 結果 |
| --- | --- |
| Ghostty で `git switch feature`、N と答える | 差分が出て、`cc-checkout-guard: 止めました。`。終了コード 1、`main` のまま |
| Ghostty で `git switch feature`、y と答える | 切り替わった。終了コード 0 |
| Ghostty で `git switch docs` | 確認なしで切り替わった |
| Ghostty で、標準入力を `/dev/null` にした `git switch feature` | 止まり、`git -C <パス> switch feature` を案内した。終了コード 1 |
| 上に `SANDBOX_RUNTIME=1` を付けた形 | 同じく止まった |
| `!` で `/bin/zsh tmp/guard-bang-trial.sh <ダミー>` | 標準入力・標準エラーとも端末でなく、`sandbox: no`。止まり、`git -C` を案内した。終了コード 1 |
| Claude の Bash ツールで同じ形 | 確かめずに切り替わった（`sandbox: yes`） |

- 分かったこと: worktree で起動したセッションでは、`!` のコマンドの文字列に git があると（`/bin/zsh -c "… git switch …"` のように別のシェルに渡す形も）、Claude Code の worktree の隔離の検査が実行の前に拒否する。そのため、`!` の試しは git をスクリプトの中に置いた。

<a name="claude-worktree"></a>

## 4. `claude -w`

`tmp/guard-worktree-trial.sh` で、一時ディレクトリに bare の origin と、それを clone した元のチェックアウトを作った。元のチェックアウトの `.claude/settings.json`（コミット済み）に、入力を記録してから確認コマンドに渡す小さなスクリプトを、`WorktreeCreate` フックとして登録した。

| 確かめたこと | 結果 |
| --- | --- |
| 信頼していないディレクトリでの `claude -w probe` | フックを呼ぶ前に失敗した: `Error creating worktree: Workspace trust not yet accepted. Run claude once in this directory and accept the trust dialog, then retry with --worktree.` |
| 信頼の問い | `Trusting this folder loads .claude/settings.json (runs commands).` と表示された |
| 信頼した後の `claude -w probe` | `~/.cc-worktrees/cc-wt-trial-fdd8114c16a6/probe` に worktree ができ、Claude Code がそこでセッションを始めた。ブランチは `worktree-probe` |
| 置き場所の親 | `~/.cc-worktrees` とキーのディレクトリは、どちらも `drwx------` |
| 終了時の問い | `A WorktreeCreate hook made this worktree, so Claude Code can't tell whether it has unpushed commits.` と、`Keep worktree` / `Remove worktree` の 2 択 |
| 同じ名前で開き直す | フックがもう一度呼ばれ、同じ worktree が開いた |
| `Remove worktree` を選んだ後 | ディレクトリは消え、`worktree list` からも外れた（`WorktreeRemove` フックはない）。ブランチ `worktree-probe` と、キーの下の `.verified` は残った |
| `origin/HEAD` を `origin/evil`（settings を変えたブランチ）に向けた後の `claude -w probe2` | 失敗した。Claude Code は、フックの標準エラーをエラーの表示に含めた。`probe2` の worktree・登録・ブランチは残らなかった |
| フックの入力 | 4 回の呼び出しのどれも、`session_id`・`transcript_path`・`cwd`（元のチェックアウトの物理パス）・`scratchpad_dir`・`hook_event_name`・`name` を持っていた。`scratchpad_dir` は公式の文書にない |

- 見つかった改善点: `origin/HEAD` を差し替えたときの案内は、「元のチェックアウトが別のブランチにあります。既定ブランチに戻すか…」になる。`origin/HEAD` が指すブランチの名前を出さないので、人間が差し替えられた先へ切り替えようとしうる（その切り替えも関数が差分を見せて聞く）。最終レビューで扱い、その修正で直した。この案内は、手動では取り直していない。

<a name="speed"></a>

## 5. 速さ

Ghostty で worktree の `bin/.zshrc` から関数を読み込み、`~/dotfiles` で 20 回ずつ実行した。

| 日付と版 | 形 | 20 回の合計 | 1 回あたり |
| --- | --- | --- | --- |
| 2026-11-19、f0594f5 | `git status`（関数を通す） | 3.084 秒 | 約 154 ms |
| 2026-11-19、f0594f5 | `command git status` | 0.239 秒 | 約 12 ms |
| 2026-11-20、24cdd4c | `git status`（関数を通す） | 1.582 秒 | 約 79 ms |
| 2026-11-20、24cdd4c | `command git status` | 0.221 秒 | 約 11 ms |

- f0594f5 では、1 回あたり約 142 ms 増えていた。最終レビューの修正で、重い import と git の呼び出しの前に、引数だけで判定する早道を入れた。
- 24cdd4c では、増える分が約 68 ms になり、plan の目安（100 ms）を下回った。残りの大半は、Python の起動と sandbox の判定と見ている（推測。内訳は測っていない）。
- zsh の補完が git を呼ぶときも関数を通る見込みで、補完が git を何度も呼ぶと、そのたびに増える（推測）。補完の速さは測っていない。

<a name="after-merge"></a>

## 6. マージの後に人間が確かめること

- マージの前に、元のチェックアウトから確認コマンドを入れ直す（ブランチの最終版と同じ中身にする）。入れていないと、関数がすべての git を止める。
- 新しい zsh で `whence -w git` が `git: function` になる。
- `command git config --global --type=bool --get rerere.enabled` が `false` を出す（`~/.gitconfig` は元のチェックアウトの `bin/.gitconfig` を指すので、マージの前は効かない）。
- `~/dotfiles` で `claude -w <name>` を実行し、`~/.cc-worktrees/dotfiles-<12 桁>/<name>` に worktree ができる。
- 新しい Claude Code のセッションの Bash ツールで、git が確かめずに動く（`cc-checkout-guard status` が `sandbox: yes`）。
