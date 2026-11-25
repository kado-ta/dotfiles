#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS! config setup is failed ;("
	exit 1
fi

# NOTE: この config/ ディレクトリ内の管理対象が増えた場合は ln コマンドを追加すること。

# 共通コマンド
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# worktree の中から実行すると、リンクが worktree を指し、worktree を消すと警告なしに切れる。
# worktree では .git がファイルになるので、git を使わずに判定する。
if [ -f "$SCRIPT_DIR/../.git" ]; then
	echo "$SCRIPT_DIR is in a git worktree. Run this script from the main checkout (~/dotfiles) instead." >&2
	exit 1
fi

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

# git（グローバルの ignore）
# ~/.config/git/ にはほかの Git の設定も置けるため、ファイル単位でリンクする。
# Claude Code は足りないパターンをこのファイルに追記するので、追記はリンク先（dotfiles）の差分になる。
GIT_CONF_DIR="$CONFIG_DIR/git"
echo "GIT_CONF_DIR: $GIT_CONF_DIR"
if [ ! -d $GIT_CONF_DIR ]; then mkdir $GIT_CONF_DIR; fi
# 実体に、リポジトリのファイルにない行（Claude Code が書き足した行など）があるときと、
# 確かめられないときは、リンクせずに残す。後の手順を止めないように、終了コードは 0 のままにする。
GIT_IGNORE_RC=1
if [ -f "$GIT_CONF_DIR/ignore" ] && [ ! -L "$GIT_CONF_DIR/ignore" ]; then
  GIT_IGNORE_RC=0
  grep -qvxF -e '' -f "$SCRIPT_DIR/git/ignore" "$GIT_CONF_DIR/ignore" || GIT_IGNORE_RC=$?
fi
if [ "$GIT_IGNORE_RC" -eq 1 ]; then
  ln -snfv "$SCRIPT_DIR/git/ignore" "$GIT_CONF_DIR/"
else
  echo "WARNING: $GIT_CONF_DIR/ignore にリポジトリにない行があるか、読めないのでリンクしなかった。次の行を $SCRIPT_DIR/git/ignore に移してから、もう一度実行する。" >&2
  grep -vxF -e '' -f "$SCRIPT_DIR/git/ignore" "$GIT_CONF_DIR/ignore" >&2 || true
fi

# NOTE: karabiner は使用していないので、関連コマンドをコメントアウトする。
# KARABINER_DIR="$CONFIG_DIR/karabiner"
# echo "KARABINER_DIR: $KARABINER_DIR"
# if [ ! -d $KARABINER_DIR ]; then mkdir $KARABINER_DIR; fi
# ln -snfv "$SCRIPT_DIR/karabiner/karabiner.json" "$KARABINER_DIR/"

echo "config setup is succeeded!"
