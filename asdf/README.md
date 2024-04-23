# asdf
## asdf
TBA ...

## asdf-direnv
Starship + asdf を使用する環境において、プロンプトの表示が遅くなり警告が表示されることがある。

```shell
[WARN] - (starship::utils): Executing command "/Users/kado/.asdf/shims/node" timed out.
[WARN] - (starship::utils): You can set command_timeout in your config to a higher value to allow longer-running commands to keep executing.
```

この表示遅延への対策として **asdf-direnv** を使用する。

### インストール

```shell
$ asdf plugin-add direnv
$ asdf install direnv latest
$ asdf global direnv latest
```

### 初期設定
下記のコマンドで asdf-direnv の初期設定を行う。

```shell
$ asdf direnv setup --shell zsh --version latest
```

下記 2つのファイルが生成され、
- `~/.config/asdf-direnv/zshrc`
- `~/.config/direnv/lib/use_asdf.sh`

`~/.zshrc` へ下記のコマンドが追加される。

```shell
source "${XDG_CONFIG_HOME:-$HOME/.config}/asdf-direnv/zshrc"
```

#### 参考リンク
- [starship direnv プロンプトの表示が遅い問題 - Qiita](https://qiita.com/ucan-lab/items/38e5663e43bafaca1a0b)
- [starship+asdfでプロンプトの表示が遅くなるのを改善する - ぶていのログでぶログ](https://tech.buty4649.net/entry/2021/07/29/201613)

#### ※ Salesforce Data Loader 対応
Salesforce Data Loader を使用する場合、これまでの設定ではエラーが発生し、Data Loader が起動しない。

`~/.zshrc` の asdf-direnv 読込設定へ **IF文を追加**し、Data Loader と競合しないようにする。

```shell
SCRIPT_NAME="$(basename -- "$0")"
if [[ $SCRIPT_NAME != "dataloader" && $SCRIPT_NAME != "dataloader_console" ]]; then
  source "${XDG_CONFIG_HOME:-$HOME/.config}/asdf-direnv/zshrc"
fi
```
