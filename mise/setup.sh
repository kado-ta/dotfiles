#!/bin/bash -e

###########################################################
# mise 設定ファイルのシンボリックリンク作成
###########################################################
if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS! mise setup is failed ;("
	exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
CONFIG_DIR="$HOME/.config"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CONFIG_DIR: $CONFIG_DIR"

if [ ! -d $CONFIG_DIR ]; then mkdir $CONFIG_DIR; fi

ln -snfv "$SCRIPT_DIR/mise_config.toml"  "$CONFIG_DIR/mise/config.toml"

echo "mise config is linked!"

###########################################################
# mise 管理ツール・言語のインストール
###########################################################
# 下記コマンドは ~/.config/mise/config.toml のシンボリックリンク作成済みであることを前提とする。
# ~/.config/mise/config.toml に記載の言語・プラグインをインストールする。
mise install $(awk -F ' = ' '/=/ {gsub(/"/, "", $2); printf "%s@%s ", $1, $2}' $CONFIG_DIR/mise/config.toml)
