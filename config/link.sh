#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS! config setup is failed ;("
	exit 1
fi

# NOTE: この config/ ディレクトリ内の管理対象が増えた場合は ln コマンドを追加すること。

# 共通コマンド
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CONFIG_DIR="$HOME/.config"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CONFIG_DIR: $CONFIG_DIR"

if [ ! -d $CONFIG_DIR ]; then mkdir $CONFIG_DIR; fi

# starship
ln -snfv "$SCRIPT_DIR/starship/starship.toml" "$CONFIG_DIR/"

# sheldon
SHELDON_DIR="$CONFIG_DIR/sheldon"
echo "SHELDON_DIR: $SHELDON_DIR"
if [ ! -d $SHELDON_DIR ]; then mkdir $SHELDON_DIR; fi
ln -snfv "$SCRIPT_DIR/sheldon/plugins.toml" "$SHELDON_DIR/"

# uv
UV_DIR="$CONFIG_DIR/uv"
echo "UV_DIR: $UV_DIR"
if [ ! -d $UV_DIR ]; then mkdir $UV_DIR; fi
ln -snfv "$SCRIPT_DIR/uv/uv.toml" "$UV_DIR/"

# sf
# ~/.config/sf/ には sf の設定や状態ファイルも置かれるため、ファイル単位でリンクする。
SF_DIR="$CONFIG_DIR/sf"
echo "SF_DIR: $SF_DIR"
if [ ! -d $SF_DIR ]; then mkdir $SF_DIR; fi
ln -snfv "$SCRIPT_DIR/sf/plugins.txt" "$SF_DIR/"
ln -snfv "$SCRIPT_DIR/sf/sync-plugins.sh" "$SF_DIR/"
ln -snfv "$SCRIPT_DIR/sf/unsignedPluginAllowList.json" "$SF_DIR/"

# herdr
# ~/.config/herdr/ にはログ・ソケット・セッションの状態も置かれるため、ファイル単位でリンクする。
HERDR_DIR="$CONFIG_DIR/herdr"
echo "HERDR_DIR: $HERDR_DIR"
if [ ! -d $HERDR_DIR ]; then mkdir $HERDR_DIR; fi
ln -snfv "$SCRIPT_DIR/herdr/config.toml" "$HERDR_DIR/"

# atuin
# atuin は ~/.atuin/config.toml を ~/.config/atuin/config.toml より先に読み、どちらもなければ ~/.atuin/config.toml を作る。
# このスクリプトより先に atuin が動いて作ったファイルも置き換えられるよう、~/.config/ ではなく ~/.atuin/ にリンクする。
ATUIN_DIR="$HOME/.atuin"
echo "ATUIN_DIR: $ATUIN_DIR"
# atuin が自分で作るときと同じく、ほかのユーザーから見えないようにする。
if [ ! -d $ATUIN_DIR ]; then mkdir -m 700 $ATUIN_DIR; fi
ln -snfv "$SCRIPT_DIR/atuin/config.toml" "$ATUIN_DIR/"

# NOTE: karabiner は使用していないので、関連コマンドをコメントアウトする。
# KARABINER_DIR="$CONFIG_DIR/karabiner"
# echo "KARABINER_DIR: $KARABINER_DIR"
# if [ ! -d $KARABINER_DIR ]; then mkdir $KARABINER_DIR; fi
# ln -snfv "$SCRIPT_DIR/karabiner/karabiner.json" "$KARABINER_DIR/"

echo "config setup is succeeded!"
