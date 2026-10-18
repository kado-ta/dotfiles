#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
    echo "This is not macOS! codex setup is failed ;("
    exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
CODEX_DIR="$HOME/.codex"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CODEX_DIR: $CODEX_DIR"

if [ ! -d $CODEX_DIR ]; then mkdir -p $CODEX_DIR; fi
ln -snfv "$SCRIPT_DIR/AGENTS.md" "$CODEX_DIR/AGENTS.md"

# superpowers プラグイン
codex plugin add superpowers@openai-curated

# Understad Anything スキルをインストールする。
curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex

# Claude Code でインストール済みの gstack を Codex でも使用できるようにする。
# 先に Claude Code で gstack をインストールしていることを前提とする。
cd ~/.claude/skills/gstack
./setup --host codex

echo "codex setup is succeeded!"
