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

# Homebrew の依存関係をツリー形式で表示する。
brew/deps/show:
	brew deps --installed --tree

# Homebrew でインストール中のパッケージを Brewfile としてリスト抽出する。
brew/dump:
	brew bundle dump

# Link AWS config & credentials.
aws/link:
	.aws/link.sh

# Link config files.
config/link:
	.config/link.sh

asdf/setup:
	asdf/setup.sh

# Set macOS system preferences.
# TODO: Mac の設定をコマンドで適用できるようにする。設定スクリプトの書き方は、下記URLを参考にする。
# https://github.com/JunichiSugiura/JunichiSugiura/blob/main/bundle/scripts/macos-defaults.sh
defaults:
	.bin/defaults.sh

# Link VSCode settings.json & install extensions.
vscode/setup:
	vscode/setup.sh

# VSCode 拡張のリスト最新化する。
vscode/extensions/list:
	code --list-extensions > vscode/extensions

# Setup Homebrew zsh.
zsh/setup:
	zsh/setup.sh
