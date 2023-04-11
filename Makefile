# すべての設定を実行する。
all: init bin/link brew/setup aws/link config/link asdf/setup

# Set initial preference.
init:
	.bin/init.sh

# Link dotfiles.
bin/link:
	.bin/link.sh

# Install Homebrew applications.
brew/setup:
	.bin/setup_brew.sh

# Link AWS config & credentials.
aws/link:
	.aws/link.sh

# Link config files.
config/link:
	.config/link.sh

asdf/setup:
	asdf/setup.sh

# Set macOS system preferences.
# TODO: Mac の設定をコマンドで適用できるようにする。
defaults:
	.bin/defaults.sh

# Link VSCode settings.json & install extensions.
vscode/setup:
	vscode/setup.sh

# Setup Homebrew zsh.
zsh/setup:
	zsh/setup.sh
