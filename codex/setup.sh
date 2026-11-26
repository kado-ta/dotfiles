#!/bin/bash -e
# curl | bash で、curl の失敗を検出するため。
set -o pipefail

if [ "$(uname)" != "Darwin" ] ; then
    echo "This is not macOS! codex setup is failed ;("
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# worktree の中から実行すると、リンクが worktree を指し、worktree を消すと警告なしに切れる。
# worktree では .git がファイルになるので、git を使わずに判定する。
if [ -f "$SCRIPT_DIR/../.git" ]; then
    echo "$SCRIPT_DIR is in a git worktree. Run this script from the main checkout (~/dotfiles) instead." >&2
    exit 1
fi

CODEX_DIR="$HOME/.codex"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CODEX_DIR: $CODEX_DIR"

if [ ! -d $CODEX_DIR ]; then mkdir -p $CODEX_DIR; fi
ln -snfv "$SCRIPT_DIR/AGENTS.md" "$CODEX_DIR/AGENTS.md"

# execpolicy の規則。Codex はリンクを読まないので、通常のファイルとしてコピーする。
# default.rules は TUI の「今後は聞かない」の書き込み先なので、別の名前にする。
# allow は当たったコマンドを sandbox の外で確認なしに動かすので、含むファイルは入れない。
# 読み込めない規則は codex exec と codex review を止めるので、検査に通ったときだけ入れる。
RULES_SRC="$SCRIPT_DIR/rules/dotfiles.rules"
if grep -nE "decision[[:space:]]*=[[:space:]]*[\"']allow[\"']" "$RULES_SRC"; then
    echo "$RULES_SRC has an allow rule. allow runs commands outside the sandbox without asking, so the rules are not installed." >&2
    exit 1
fi
if ! codex execpolicy check --rules "$RULES_SRC" -- git status > /dev/null; then
    echo "$RULES_SRC failed codex execpolicy check, so the rules are not installed." >&2
    exit 1
fi
mkdir -p "$CODEX_DIR/rules"
install -m 0644 "$RULES_SRC" "$CODEX_DIR/rules/dotfiles.rules"
echo "installed: $CODEX_DIR/rules/dotfiles.rules"

# superpowers プラグイン
# codex plugin list はオンラインだとリモートのカタログを返し、インストール済みでもこのプラグインを含まない。
# そのため、codex plugin add が作るインストール先の有無で判定する。
if [ -d "$CODEX_DIR/plugins/cache/openai-curated/superpowers" ]; then
  echo "superpowers plugin already installed, skipping"
else
  codex plugin add superpowers@openai-curated
fi

# Understand Anything スキルをインストールする。
# Codex 用のスキルのリンクと、install.sh が最後に作る ~/.understand-anything-plugin の両方を完了の目印にする。
# ~/.understand-anything-plugin は他のホスト向けのインストールでも作られるため、それだけでは判定しない。
# -e はリンク先をたどるので、リンク切れは未インストールとみなし、install.sh で張り直す。
if [ -e "$HOME/.agents/skills/understand" ] && [ -e "$HOME/.understand-anything-plugin" ]; then
  echo "Understand Anything already installed, skipping"
else
  curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex
fi

# Claude Code でインストール済みの gstack を Codex でも使用できるようにする。
# 先に Claude Code で gstack をインストールしていることを前提とする。
cd ~/.claude/skills/gstack
./setup --host codex

echo "codex setup is succeeded!"
