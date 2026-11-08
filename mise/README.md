# mise

言語ランタイム・ツールのグローバルバージョンを管理するディレクトリ。

| ファイル           | 内容                                                      |
| ------------------ | --------------------------------------------------------- |
| `mise_config.toml` | グローバル設定。`~/.config/mise/config.toml` にリンクする |
| `setup.sh`         | 設定をリンクし、言語ランタイム・ツールをインストールする  |
| `JAVA.md`          | Salesforce 拡張用の JDK の設定手順                        |

<a name="tasks"></a>

## mise タスク

保守用のタスクをリポジトリルートの `mise.toml` に、どのディレクトリからでも使うタスクをこのディレクトリの `mise_config.toml` に定義している。`mise tasks` で一覧を表示する。

| コマンド                   | 内容                                                                   |
| -------------------------- | ---------------------------------------------------------------------- |
| `mise run brew:deps:show`  | Homebrew の依存関係をツリー形式で表示する                              |
| `mise run brew:dump`       | インストール済みのパッケージをリポジトリルートの `Brewfile` に書き出す |
| `mise run vscode:ext:list` | インストール済みの VSCode 拡張を `vscode/extensions` に書き出す        |
| `mise run sf:plugins`      | sf のプラグインを `plugins.txt` に同期する（グローバルタスク）         |

<a name="java"></a>

## Salesforce 拡張用の JDK

mise でインストールした JDK を `JavaVirtualMachines` にリンクし、VSCode を設定する（[JAVA.md](JAVA.md#jvm-symlink)）。
