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
ln -snfv "$SCRIPT_DIR/config.toml" "$CODEX_DIR/config.toml"

echo "codex setup is succeeded!"
