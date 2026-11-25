# config

`~/.config/` に配置するツールの設定を管理するディレクトリ。`link.sh` でリンクする。

| ディレクトリ | 内容 | リンク先 |
| --- | --- | --- |
| `starship/` | Starship の設定 | `~/.config/starship.toml` |
| `sheldon/` | Sheldon の設定（Zsh プラグインの定義） | `~/.config/sheldon/plugins.toml` |
| `uv/` | uv の設定 | `~/.config/uv/uv.toml` |
| `sf/` | Salesforce CLI のプラグインの一覧と同期スクリプト | `~/.config/sf/` |
| `herdr/` | herdr の設定 | `~/.config/herdr/config.toml` |
| `atuin/` | atuin の設定。atuin は `~/.config/atuin/` より `~/.atuin/` の設定を先に読むので、`~/.atuin/` にリンクする（履歴の DB も `~/.atuin` に置かれる） | `~/.atuin/config.toml` |
| `git/` | Git のグローバルの ignore（どのリポジトリでも無視するファイル）。Claude Code は足りないパターンを追記するので、追記はこのファイルの差分になる。`~/dotfiles` をこのファイルがないブランチに切り替えるとリンクが切れ、Git は警告を出さずに、どのリポジトリでもこれらのファイルを無視しなくなる | `~/.config/git/ignore` |
| `karabiner/` | Karabiner の設定（現在はリンクしていない） | なし |

<a name="sf-plugins"></a>

## Salesforce CLI のプラグイン

`mise run sf:plugins` で `sf/plugins.txt` のプラグインをインストールする。

プラグインを変更するときは、`sf/plugins.txt` を編集して `mise run sf:plugins` を実行する。一覧から消してもアンインストールはしないので、`sf plugins uninstall` で手動で削除する。署名のないプラグインを入れるときは `sf/unsignedPluginAllowList.json` にも追加する。
