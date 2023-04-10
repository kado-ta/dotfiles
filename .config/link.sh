#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
CONFIG_DIR="$HOME/.config"
KARABINER_DIR="$CONFIG_DIR/karabiner"
SHELDON_DIR="$CONFIG_DIR/sheldon"

echo "SCRIPT_DIR:    $SCRIPT_DIR"
echo "CONFIG_DIR:    $CONFIG_DIR"
echo "KARABINER_DIR: $KARABINER_DIR"
echo "SHELDON_DIR:   $SHELDON_DIR"

if [ ! -d $CONFIG_DIR ];    then mkdir $CONFIG_DIR; fi
if [ ! -d $KARABINER_DIR ]; then mkdir $KARABINER_DIR; fi
if [ ! -d $SHELDON_DIR ];   then mkdir $SHELDON_DIR; fi

# NOTE: .config/ ディレクトリ内の管理対象が増えた場合は、ここへ ln コマンドを追加する。
ln -snfv "$SCRIPT_DIR/karabiner/karabiner.json" "$KARABINER_DIR/"
ln -snfv "$SCRIPT_DIR/sheldon/plugins.toml"     "$SHELDON_DIR/"
ln -snfv "$SCRIPT_DIR/starship/starship.toml"   "$CONFIG_DIR/"

echo "Success!"
