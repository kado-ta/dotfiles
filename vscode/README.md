# vscode

VSCode の設定を管理するディレクトリ。`setup.sh` で設定をリンクし、拡張をインストールする。

| ファイル                                          | 内容                                                                   |
| ------------------------------------------------- | ---------------------------------------------------------------------- |
| `settings.json`・`keybindings.json`・`tasks.json` | VSCode の設定。`~/Library/Application Support/Code/User/` にリンクする |
| `projects.json`                                   | Project Manager 拡張のプロジェクト一覧                                 |
| `extensions`                                      | インストールする拡張の一覧                                             |
| `setup.sh`                                        | 設定をリンクし、拡張をインストールする                                 |

<a name="update-extensions"></a>

## 拡張のリストの更新

`extensions` は `mise run vscode:ext:list` で生成する。手で編集しない。
