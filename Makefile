all:
	sh ./.bin/init.sh
	sh ./zsh/setup.sh
# 下記は、シェルを再起動した上で実行すべきスクリプト。
# 簡単のために、無効化しておく。
#	sh ./zsh/setup_plugins.sh
#	sh ./.bin/setup_brew.sh
#	sh ./asdf/setup.sh
#	sh ./.bin/link.sh
#	sh ./.aws/link.sh
#	sh ./.config/link.sh

# Homebrew の依存関係をツリー形式で表示する。
brew/deps/show:
	brew deps --installed --tree

# Homebrew でインストール中のパッケージを Brewfile としてリスト抽出する。
# このコマンドで生成される Brewfile をベースに .Brewfile を最新化する。
brew/dump:
	brew bundle dump

# VSCode 拡張のリスト最新化する。
vscode/extensions/list:
	code --list-extensions > vscode/extensions
