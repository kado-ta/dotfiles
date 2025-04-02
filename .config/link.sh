#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

# NOTE: この .config/ ディレクトリ内の管理対象が増えた場合は ln コマンドを追加すること。

# 共通コマンド
SCRIPT_DIR=$(cd $(dirname $0) && pwd)
CONFIG_DIR="$HOME/.config"
if [ ! -d $CONFIG_DIR ]; then mkdir $CONFIG_DIR; fi

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CONFIG_DIR: $CONFIG_DIR"

ln -snfv "$SCRIPT_DIR/mise/mise_config.toml"  "$CONFIG_DIR/config.toml"
ln -snfv "$SCRIPT_DIR/starship/starship.toml" "$CONFIG_DIR/"

SHELDON_DIR="$CONFIG_DIR/sheldon"
echo "SHELDON_DIR: $SHELDON_DIR"
if [ ! -d $SHELDON_DIR ]; then mkdir $SHELDON_DIR; fi
ln -snfv "$SCRIPT_DIR/sheldon/plugins.toml" "$SHELDON_DIR/"

# NOTE: karabiner は使用していないので、関連コマンドをコメントアウトする。
# KARABINER_DIR="$CONFIG_DIR/karabiner"
# echo "KARABINER_DIR: $KARABINER_DIR"
# if [ ! -d $KARABINER_DIR ]; then mkdir $KARABINER_DIR; fi
# ln -snfv "$SCRIPT_DIR/karabiner/karabiner.json" "$KARABINER_DIR/"

echo "Success!"
