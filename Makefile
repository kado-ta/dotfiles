# すべての設定を実行する。
all: init bin/link aws/link config/link brew/setup

# Set initial preference.
init:
	.bin/init.sh

# Link dotfiles.
bin/link:
	.bin/link.sh

aws/link:
	.aws/link.sh

config/link:
	.config/link.sh

# Set macOS system preferences.
# TODO: Mac の設定をコマンドで適用できるようにする。
defaults:
	.bin/defaults.sh

# Install Homebrew applications.
brew/setup:
	.bin/setup_brew.sh
