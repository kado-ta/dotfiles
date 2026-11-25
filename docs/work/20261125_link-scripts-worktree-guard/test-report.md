---
status: done
created: 2026-11-25
---

# 試験記録: リンク用スクリプトを worktree の中では止める

## 関連

- [plan.md](plan.md)

<a name="method"></a>

## 方法

scratchpad に置いた確認のスクリプト（コミットしない）で、次を行った。Claude Code の sandbox の中で実行した。

1. 確かめるコミットの中身を `git archive` で一時ディレクトリに展開し、`git init` とコミットをして、`git worktree add` で worktree を作る（`GIT_CONFIG_GLOBAL=/dev/null`・`GIT_CONFIG_NOSYSTEM=1`）。worktree の `.git` がファイルであることを確かめる。共有の作業ツリーは途中でほかのセッションが切り替えたので、作業ツリーからは写さない。
2. 10 本のスクリプトを、それぞれ新しい偽の HOME で、`env -i HOME=<偽の HOME> PATH=/usr/bin:/bin:/usr/sbin:/sbin` で直接実行する（shebang の `-e` を効かせるため、`bash <スクリプト>` にはしない）。`env -i` で `CLAUDECODE` も外れるので、`claude/setup.sh` が別の理由で止まることはない。`obsidian/setup.sh` のために、偽の HOME に `Obsidian/main/.obsidian` を先に作る。
3. worktree の中から実行したものは、終了コードが 1 であること、標準エラーに `git worktree` を含むこと、偽の HOME に新しいものがないこと（実行の前後の `find` の比較）、`aws/link.sh` では worktree の `aws/` に `config`・`credentials` がないことを確かめる。
4. 本体から実行したものは、メッセージが出ないことと、リンクが 1 つ以上あって worktree を指すものがないことを確かめる。リンクの一覧（パスとリンク先）を書き出して、変更の前後で比べる。

PATH にツールがないので、`claude`・`codex`・`mise` の 3 本はリンクを作った後で、ツールが見つからずに終了コード 127 で終わる。`vscode/setup.sh` は `code` がないので、案内を出して終わる。リンクの後、ツールの呼び出しまでに書き込みがないことは、実行の前にスクリプトを読んで確かめた。

worktree の中で偽の HOME を使って確かめたいときも、この方法（一時リポジトリに写す）を使う。判定は HOME を見ないので、worktree の中では偽の HOME でも止まる。

<a name="results"></a>

## 結果

変更前は main の `305dba0`、変更後はこのブランチの `939d13b`（main の上に載せ直した後）で確かめた。その後のコミットは文書だけを変えている。

| スクリプト | 変更前: worktree | 変更後: worktree | 本体（前後で同じ） |
| --- | --- | --- | --- |
| `aws/link.sh` | FAIL（終了コード 0、HOME に 3 件、worktree に `config`・`credentials`） | PASS | 終了コード 0、リンク 2 |
| `bin/link.sh` | FAIL（終了コード 0、HOME に 5 件） | PASS | 終了コード 0、リンク 5 |
| `biome/setup.sh` | FAIL（終了コード 0、HOME に 4 件） | PASS | 終了コード 0、リンク 1 |
| `claude/setup.sh` | FAIL（終了コード 127、HOME に 56 件） | PASS | 終了コード 127、リンク 5 |
| `codex/setup.sh` | FAIL（終了コード 127、HOME に 2 件） | PASS | 終了コード 127、リンク 1 |
| `config/link.sh` | FAIL（終了コード 0、HOME に 16 件） | PASS | 終了コード 0、リンク 9 |
| `ghostty/link.sh` | FAIL（終了コード 0、HOME に 3 件） | PASS | 終了コード 0、リンク 1 |
| `mise/setup.sh` | FAIL（終了コード 127、HOME に 3 件） | PASS | 終了コード 127、リンク 1 |
| `obsidian/setup.sh` | FAIL（終了コード 0、HOME に 7 件） | PASS | 終了コード 0、リンク 7 |
| `vscode/setup.sh` | FAIL（終了コード 0、HOME に 7 件） | PASS | 終了コード 0、リンク 3 |

- 件数はディレクトリも含む。`claude/setup.sh` の 56 件のうち 49 件は、変更前のスクリプトがリンクの後に動かした `/usr/bin/python3` のキャッシュ（`~/Library/Caches/com.apple.python`）。
- 本体から作ったリンクの一覧（35 件）は、変更の前後で `diff` の差がなかった。
- `claude -w` と同じ配置（本体の `.claude/worktrees/<名前>`）で、名前に空白を含む worktree の中から `./config/link.sh` と相対パスで起動しても、終了コード 1 で止まり、リンクは 0 件だった（`939d13b`）。同じ一時リポジトリの本体からは 9 件を作った。
- 止まったときのメッセージの例: `<一時ディレクトリ>/main/.claude/worktrees/w x/config is in a git worktree. Run this script from the main checkout (~/dotfiles) instead.`
- この Mac の `claude -w` の worktree（`~/dotfiles/.claude/worktrees/add-gitleaks`）で、`.git` がファイル（`gitdir: ~/dotfiles/.git/worktrees/add-gitleaks`）であり、`claude/../.git` に `-f` が真になることを、スクリプトを動かさずに読み取りで確かめた。本体の `~/dotfiles/.git` はディレクトリ。

<a name="checks"></a>

## 検査

- `python3 -B .github/scripts/check-repo.py`: 全項目 PASS
- `python3 -B .github/scripts/test-check-repo.py`: 93 件 OK
- `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`: 指摘なし
- `actionlint`: 指摘なし
- `zizmor --offline .`: 指摘なし（v1.33.1）

<a name="not-verified"></a>

## 確かめていないこと

- 実際の HOME と `~/dotfiles` での実行（今の設定のリンクを張り直すことになるので、しなかった）。
- `claude -w` で作った worktree の中から、スクリプトそのものを動かすこと。`.git` がファイルで判定が真になることは、上のとおり読み取りで確かめた。
- Homebrew の bash での実行。`#!/usr/bin/env bash` の 2 本（`claude/setup.sh`・`obsidian/setup.sh`）は、PATH を絞ったので `/bin/bash`（3.2）で動いた。判定の構文は 3.2 と新しい bash で違いはない。
