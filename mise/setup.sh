#!/bin/bash -e

###########################################################
# mise
###########################################################
# 下記コマンドは ~/dotfiles/.config/mise/mise_config.toml のシンボリックリンクを作成後に実行すること。
# ~/.config/config.toml に記載の言語・プラグインをインストールする。
mise install $(awk -F ' = ' '/=/ {gsub(/"/, "", $2); printf "%s@%s ", $1, $2}' ~/.config/config.toml)
