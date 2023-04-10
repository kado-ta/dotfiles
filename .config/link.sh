#!/bin/bash -e

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
echo "SCRIPT_DIR: $SCRIPT_DIR"

CONFIG_DIR="$HOME/.config"
echo "CONFIG_DIR: $CONFIG_DIR"

# NOTE: .config/ ディレクトリ内の管理対象が増えた場合は、ここへ ln コマンドを追加する。
ln -snfv "$SCRIPT_DIR/karabiner/karabiner.json" "$CONFIG_DIR/karabiner/"
ln -snfv "$SCRIPT_DIR/sheldon/plugins.toml"     "$CONFIG_DIR/sheldon/"
ln -snfv "$SCRIPT_DIR/starship/starship.toml"   "$CONFIG_DIR/"

echo "Success!"
