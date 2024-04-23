#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

# zsh を Homebrew からインストールする。
brew install zsh

# Homebrew でインストールした zsh の実行パスを確認する。
ZSH_PATH="$(brew --prefix)/bin/zsh"
echo "Zsh path: $ZSH_PATH"

# デフォルト・シェルを Homebrew でインストールした zsh へ変更する。
echo $ZSH_PATH >> /etc/shells
chsh -s $ZSH_PATH

# NOTE: 実行後にシェルを再起動すること。
