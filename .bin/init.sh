#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS :("
	exit 1
fi

# Install Xcode
xcode-select --install > /dev/null

# Install Homebrew
# https://brew.sh/index_ja
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" > /dev/null

# Install zsh via Homebrew & Set Homebrew zsh as default shell.
brew install zsh --ignore-dependencies
ZSH_PATH="$(brew --prefix)/bin/zsh"
echo $ZSH_PATH >> /etc/shells
chsh -s /usr/local/bin/zsh
exec -L $SHELL
