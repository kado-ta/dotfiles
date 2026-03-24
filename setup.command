#!/bin/bash -e

# Sheldon で管理する zsh のプラグインをインストールする。
zsh/setup_plugins.sh

# Brewfile にしたがって、ライブラリを一括インストールする。
.bin/setup_brew.sh

# dotfile 系のシンボリックリンクを作成する。
.bin/link.sh

# $HOME/.config 下に必要な設定ファイルのシンボリックリンクを作成する。
.config/link.sh

# AWS CLI の設定と Credentils のシンボリックリンクを作成する。
aws/link.sh

# mise で管理する言語・プラグインをインストールする。
mise/setup.sh

# Claude Code 設定のシンボリックリンクを作成する。
.claude/link.sh

# Set macOS system preferences.
# TODO: Mac の設定をコマンドで適用できるようにする。設定スクリプトの書き方は、下記URLを参考にする。
# https://github.com/JunichiSugiura/JunichiSugiura/blob/main/bundle/scripts/macos-defaults.sh
#
#	.bin/defaults.sh

# VSCode は brew bundle でインストール済み。
# ここでは、settings.json のシンボリックリンクを作成し、拡張機能をインストールする。
vscode/setup.sh
