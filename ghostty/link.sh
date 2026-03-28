#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
    echo "This is not macOS! ghostty setup is failed ;("
    exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
GHOSTTY_DIR="$HOME/.config/ghostty"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "GHOSTTY_DIR: $GHOSTTY_DIR"

if [ ! -d $GHOSTTY_DIR ]; then mkdir -p $GHOSTTY_DIR; fi
ln -snfv "$SCRIPT_DIR/config" "$GHOSTTY_DIR/config"

echo "ghostty setup is succeeded!"
