# bin

シェル・Git・Homebrew の設定と、最初に実行するセットアップスクリプトを管理するディレクトリ。

| ファイル                        | 内容                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------- |
| `.zshrc`・`.zprofile`           | Zsh の設定。`~` にリンクする                                                                |
| `.gitconfig`・`.gitconfig_numm` | Git の設定。`~` にリンクする                                                                |
| `.Brewfile`                     | Homebrew のパッケージリストの正本。`~` にリンクする                                         |
| `init.sh`                       | Xcode Command Line Tools と Homebrew をインストールする（`init.command` から実行）          |
| `link.sh`                       | このディレクトリの dotfile を `~` にリンクする（`setup.command` から実行）                  |
| `setup_brew.sh`                 | `~/.Brewfile` のパッケージをインストールする（`brew bundle install --global --no-upgrade`） |

> [!WARNING]
> `init.sh` は、インストール済みの Command Line Tools（`/Library/Developer/CommandLineTools`）を削除してから再インストールする。既存の Mac で再実行するときは注意する。

<a name="update-brewfile"></a>

## パッケージリストの更新

正本は `.Brewfile`。`mise run brew:dump` で生成した、リポジトリルートの `Brewfile`（Git 管理外）と見比べて、`.Brewfile` に反映する。
