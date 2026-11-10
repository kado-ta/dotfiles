#!/bin/bash -e
# curl | bash で、curl の失敗を検出するため。
set -o pipefail

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
# codex plugin list はオンラインだとリモートのカタログを返し、インストール済みでもこのプラグインを含まない。
# そのため、codex plugin add が作るインストール先の有無で判定する。
if [ -d "$CODEX_DIR/plugins/cache/openai-curated/superpowers" ]; then
  echo "superpowers plugin already installed, skipping"
else
  codex plugin add superpowers@openai-curated
fi

# Understand Anything スキルをインストールする。
# install.sh は最後に ~/.understand-anything-plugin を作るので、完了の目印にする。
if [ -e "$HOME/.understand-anything-plugin" ]; then
  echo "Understand Anything already installed, skipping"
else
  curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex
fi

# Claude Code でインストール済みの gstack を Codex でも使用できるようにする。
# 先に Claude Code で gstack をインストールしていることを前提とする。
cd ~/.claude/skills/gstack
./setup --host codex

echo "codex setup is succeeded!"
