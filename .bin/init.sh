#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS :("
	exit 1
fi

# Install Xcode
# まず、Command Line Tools のインストールを確認する。
xcode-select -p
# rm による削除は、 Command Line Tools インストール時の下記エラーに対する対策。
# xcode-select: error: command line tools are already installed, use "Software Update" to install updates
sudo rm -rf /Library/Developer/CommandLineTools
xcode-select --install > /dev/null

# Install Homebrew
# https://brew.sh/index_ja
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" > /dev/null
brew update
