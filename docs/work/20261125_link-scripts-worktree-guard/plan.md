---
status: in-progress
created: 2026-11-25
---

# リンク用スクリプトを worktree の中では止める

## 目次

- [関連](#related)
- [問題](#problem)
- [完了条件](#done-criteria)
- [方針](#approach)
- [採らなかった案](#rejected)
- [変更するファイル](#files)
- [手順](#steps)
- [対象外と残るリスク](#out-of-scope)

<a name="related"></a>

## 関連

- PR #117（グローバルの ignore のリンク）の作業中に見つかった。この PR より前からある問題。
- PR #118（README の atuin の追記）

<a name="problem"></a>

## 問題

次の 10 本のスクリプトは、`SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)` をリンク元にしている。worktree の中のスクリプトを実行すると、`~` の設定が worktree の中を指す。worktree を消すと、そのリンクは警告なしに切れる。

`aws/link.sh`・`bin/link.sh`・`biome/setup.sh`・`claude/setup.sh`・`codex/setup.sh`・`config/link.sh`・`ghostty/link.sh`・`mise/setup.sh`・`obsidian/setup.sh`・`vscode/setup.sh`

影響の大きいもの:

- `claude/setup.sh`: `~/.claude/settings.json`・`hooks`・`rules` が worktree を指す。worktree を消すと、deny ルール・フック・sandbox の設定が外れる。`CLAUDECODE` での拒否は、通常のターミナルから worktree のパスで実行すると通る。
- `aws/link.sh`: worktree の `aws/` に空の `credentials` を作り、`~/.aws/credentials` のリンクをそこへ張り替える。このスクリプトが前に作ったリンクは実体ではないので、`link()` の確認では止まらない（`~/dotfiles/aws/credentials` 自体は残る）。
- `bin/link.sh`: `~/.zshrc`・`~/.gitconfig` などが worktree を指す。`rerere.enabled = false` も worktree の版になる。
- `config/link.sh`: worktree を消すと、グローバルの ignore が外れる（PR #117 で文書にした症状と同じ）。
- `mise/setup.sh`: `~/.config/mise/config.toml` が worktree を指す。mise の postinstall（biome の `sync_schema.sh`）も、このリンクをたどって worktree のスクリプトを動かす。

入口の `setup.command` は `cd ~/dotfiles` してから実行し、`init.command` もカレントディレクトリの名前が `dotfiles` でなければ `cd ~/dotfiles` するので、影響しない。

<a name="done-criteria"></a>

## 完了条件

1. 一時ディレクトリに作った git リポジトリの worktree の中から 10 本を実行すると、終了コード 1 で止まり、偽の HOME に何も作らない。`aws/link.sh` は、worktree の `aws/` に `config`・`credentials` も作らない。
2. 変更前のスクリプトでは、1 の確認が失敗する（再現）。
3. 同じ一時リポジトリの本体（`.git` がディレクトリ）から実行すると、10 本とも今と同じリンクを偽の HOME に作る。リンクの後でツールを呼ぶ 4 本（`claude`・`codex`・`mise`・`vscode`）は、PATH を `/usr/bin:/bin:/usr/sbin:/sbin` にして、ツールがないところで止める（実行の前に、リンクとツールの呼び出しのあいだに、ほかの書き込みがないことを読んで確かめる）。
4. `python3 -B .github/scripts/check-repo.py`・`python3 -B .github/scripts/test-check-repo.py`・shellcheck・actionlint が通る。

確認のスクリプトは scratchpad に置き、コミットしない。結果は `test-report.md` に書く。

<a name="approach"></a>

## 方針

- **判定**: スクリプトのあるリポジトリのルート（`$SCRIPT_DIR/..`）の `.git` がファイルなら、worktree とみなして止める。worktree の `.git` は本体の `.git/worktrees/<name>` を指すファイルで、本体のチェックアウトではディレクトリになる。10 本ともルートの 1 つ下にある。
- **git を使わない**: 判定のために git を動かすと、worktree の設定を読む git を実行することになる。ファイルの種類だけなら、新しい Mac で git がまだ使えないときにも判定できる。
- **置き場所**: 各スクリプトの `SCRIPT_DIR=` の直後、最初の書き込みより前に、同じ 5 行を書く。README の「各ディレクトリは独立しており」に合わせて、共通のファイルは作らない。
- **止める範囲**: スクリプト全体（リンクの後のインストールも）。worktree からインストールだけを動かす使い方は想定しない。
- **メッセージ**: これらのスクリプトのほかのエラーに合わせて英語にし、標準エラーに出す。終了コードは 1。

```bash
# worktree の中から実行すると、リンクが worktree を指し、worktree を消すと警告なしに切れる。
# worktree では .git がファイルになるので、git を使わずに判定する。
if [ -f "$SCRIPT_DIR/../.git" ]; then
  echo "$SCRIPT_DIR is in a git worktree. Run this script from the main checkout (~/dotfiles) instead." >&2
  exit 1
fi
```

<a name="rejected"></a>

## 採らなかった案

- **リンク元を常に `~/dotfiles` に固定する**: worktree で試しているつもりでも、main のファイルにリンクされる。
- **`~/dotfiles` 以外のチェックアウトをすべて止める（clone も含む）**: 偽の HOME での確認（PR #117 で使った方法）ができなくなる。別の場所の clone（`~/ClaudeWork` の案）は Issue #75 で保留しているので、そのときに判断する。
- **`git rev-parse --git-dir` と `--git-common-dir` を比べる**: git が要り、worktree の設定を読む git を動かす。
- **共通の関数のファイルを `source` する**: ディレクトリごとに独立している今の構成と合わない。5 行の重複は受け入れる。

<a name="files"></a>

## 変更するファイル

- 上の 10 本のスクリプト: 判定を足す。
- `README.md`: 「2. 設定のリンクとツールのインストール」の表の後に、worktree の中から実行すると止まること、`~/dotfiles` のものを実行することを 1 行で書く。
- `docs/work/20261125_link-scripts-worktree-guard/`: この plan と `test-report.md`。

`claude/setup.sh` は `claude/` の下なので、Edit ツールで書くと承認を求められる。

<a name="steps"></a>

## 手順

1. 確認のスクリプトを書き、変更前のスクリプトで完了条件 1 が失敗することを確かめる → `test-report.md` に記録する。
2. 10 本に判定を足す → 完了条件 1・3 を確かめる。
3. `README.md` に追記する → 完了条件 4 を確かめる。
4. `/review` → 指摘を直す → `/crit-review` でブランチの差分を開く → 承認後に push と PR。

ロールバックは、この PR の revert で足りる（スクリプトの先頭で止めるだけで、データやリンクは変えない）。

<a name="out-of-scope"></a>

## 対象外と残るリスク

- `git clone --separate-git-dir` で作ったチェックアウトも `.git` がファイルなので止まる。このリポジトリでは使っていない。
- 別の場所の clone からの実行は止めない（Issue #75）。
- 既に worktree を指しているリンクは直さない。2026-11-25 に、この Mac の主なリンク（`~/.zshrc`・`~/.gitconfig`・`~/.config/` の下・`~/.atuin/config.toml`・`~/.claude/` の settings・hooks・rules・`~/.codex/AGENTS.md`・biome・VSCode）がどれも `~/dotfiles` を指していることを確かめた。`~/.aws` は sandbox から読めないので見ていない。
- リンクを作らないスクリプト（`bin/init.sh`・`bin/setup_brew.sh`・`zsh/setup.sh`・`zsh/setup_plugins.sh`・`biome/sync_schema.sh`）は変えない。`sync_schema.sh` は mise の設定のリンクをたどって動くので、`mise/setup.sh` を止めれば足りる。
- 判定は、スクリプトがルートの 1 つ下にあることに頼る。スクリプトを深い階層に移すときは、判定のパスも変える。
