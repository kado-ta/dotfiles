#!/bin/bash -e

# ターミナルから実行した場合と、Finder から実行した場合とで、実行ディレクトリを一致させる。
if [ "$(basename $(pwd))" != "dotfiles" ]; then
		cd ~/dotfiles
fi

# xcode-select の実行, Homebrew のインストールなど、開発環境のベースを整える。
.bin/init.sh

# Homebrew から zsh をインストールし、デフォルト・シェルをその zsh へ変更する。
zsh/setup.sh

# ログイン・シェルを変更したので、ここでターミナルを再起動する。
echo
echo
echo "=========================================================="
echo
echo "  シェルを変更したので、ターミナルを再起動してください。"
echo
echo "=========================================================="
echo
