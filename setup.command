#!/bin/bash -e

# 実行方法や実行場所によらず、~/dotfiles を対象にする。
cd ~/dotfiles

# bin/link.sh でリンクする .zprofile は実行中のプロセスに反映されないので、ここで PATH を通す。
eval "$(/opt/homebrew/bin/brew shellenv)"

# dotfile 系のシンボリックリンクを作成する。
bin/link.sh

# Brewfile にしたがって、ライブラリを一括インストールする。
bin/setup_brew.sh

# $HOME/.config 下に必要な設定ファイルのシンボリックリンクを作成する。
config/link.sh

# Sheldon で管理する zsh のプラグインをインストールする。
zsh/setup_plugins.sh

# AWS CLI の設定と Credentils のシンボリックリンクを作成する。
aws/link.sh

# mise で管理する言語・プラグインをインストールする。
mise/setup.sh

# Claude Code 設定のシンボリックリンクを作成する。
claude/setup.sh

# Codex 設定のシンボリックリンクを作成する。
codex/setup.sh

# Set macOS system preferences.
# TODO: Mac の設定をコマンドで適用できるようにする。設定スクリプトの書き方は、下記URLを参考にする。
# https://github.com/JunichiSugiura/JunichiSugiura/blob/main/bundle/scripts/macos-defaults.sh
#
#	bin/defaults.sh

# VSCode は brew bundle でインストール済み。
# ここでは、settings.json のシンボリックリンクを作成し、拡張機能をインストールする。
vscode/setup.sh
