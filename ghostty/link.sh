#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
    echo "This is not macOS! ghostty setup is failed ;("
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# worktree の中から実行すると、リンクが worktree を指し、worktree を消すと警告なしに切れる。
# worktree では .git がファイルになるので、git を使わずに判定する。
if [ -f "$SCRIPT_DIR/../.git" ]; then
    echo "$SCRIPT_DIR is in a git worktree. Run this script from the main checkout (~/dotfiles) instead." >&2
    exit 1
fi

GHOSTTY_DIR="$HOME/.config/ghostty"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "GHOSTTY_DIR: $GHOSTTY_DIR"

if [ ! -d $GHOSTTY_DIR ]; then mkdir -p $GHOSTTY_DIR; fi
ln -snfv "$SCRIPT_DIR/config" "$GHOSTTY_DIR/config"

echo "ghostty setup is succeeded!"
