# dotfiles
## ▍Setup
Finder から下記 2つのファイルを実行する。(**※ ダブルクリックで実行する。**)
1. `init.command` : Homebrew インストールや zsh 設定など。
2. `setup.command` : 開発環境に必要なランタイム・ライブラリ等のセットアップ。

## ▍Directories
下記は、セットアップ時の実行順に記載する。

### .bin
ローカル環境で使用するシェルやライブラリの設定情報。

下記の順にスクリプトを実行して、セットアップする。
1. `./.bin/init.sh` : Xcode Command Line Tools と Homebrew をインストールする。
2. `./.bin/link.sh` : このディレクトリ内のファイルが使用できるよう、シンボリックリンクを作成する。
3. `./.bin/setup_brew.sh` : `~/.Brewfile` を参照して、一括インストールする。

```shell
.
└── .bin
    ├── .Brewfile      # Homebrew のパッケージリストファイル
    ├── .gitconfig     # Git 設定
    ├── .zprofile      # Zsh 設定 (ログインシェルで一度だけ読み込まれる)
    ├── .zshrc         # Zsh 設定 (ログインシェルとインタラクティブシェルの場合だけ読み込まれる。)
    ├── init.sh
    ├── link.sh
    └── setup_brew.sh
```

### zsh
下記の順にスクリプトを実行して、Zsh とそのプラグインをセットアップする。

1. `./zsh/setup.sh` : Zsh をインストールし、使用できるようセットアップする。
2. `./zsh/setup_plugins.sh` : Zsh プラグインをインストールする。

```shell
.
└── zsh
    ├── README.md
    ├── alias.zsh               # Zsh で使用するコマンドのエイリアス定義
    ├── bindkey.zsh             # Zsh キーバインド設定
    ├── select-word-style.zsh   # Zsh 上での単語の区切り設定や入力補完の設定
    ├── setpot.zsh              # Zsh オプション設定
    ├── setup.sh
    ├── setup_plugins.sh
    └── zsh-autosuggestions.zsh # zsh-users/zsh-autosuggestions の設定
```

### mise
mise セットアップ用スクリプト。

`./mise/setup.sh` をを実行することで、`./mise/mise_config.toml` -> `~/.config/mise/config.toml` のシンボリックリンクが作成され、
`~/.config/mise/config.toml` に記載の言語・プラグインの指定バージョンがインストールされる。


```shell
.
└── mise
    └── mise_config.toml
    └── setup.sh
```

### .config
各種設定情報。

`./.config/link.sh` を実行して、セットアップする。


```shell
.
└── .config
    ├── karabiner
    │   └── karabiner.json
    ├── sheldon
    │   └── plugins.toml
    ├── starship
    │   └── starship.toml
    └── link.sh
```

### .aws
AWS 関連設定。

`./.aws/link.sh` を実行して、セットアップする。


```shell
.
└── .aws
    ├── config      # 各プロファイルの情報
    ├── credentials # IAM ユーザーのクレデンシャル
    └── link.sh
```

加えて、各 Staging / Production 環境へ SSH 接続するための Session Manager プラグインをインストールする。

これは、macOS でのインストール手順。
```shell
$ curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac_arm64/sessionmanager-bundle.zip" -o "sessionmanager-bundle.zip"
$ unzip sessionmanager-bundle.zip
$ sudo ./sessionmanager-bundle/install -i /usr/local/sessionmanagerplugin -b /usr/local/bin/session-manager-plugin
```
他のプラットフォームでのインストール手順は、下記 URL を参照。  
https://docs.aws.amazon.com/ja_jp/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html

### Claude Code
`./.claude/link.sh` を実行して、Claude Code 設定のシンボリックを作成する。


```shell
.
└── .claude
    ├── link.sh
    ├── settings.json       # Claude 設定
    └── validate-command.sh # PreToolUse フック用スクリプト
```
#### settings.json
`.claude/settings.json` 内のセキュリティ設定は、下記リンクの記事を参考に作成。
- [【2026年最新版】Claude Codeで行うべきセキュリティ設定 10選 - Qiita](https://qiita.com/miruky/items/51db293a7a7d0d277a5d)

#### validate-command.sh
Hooks の **PreToolUse フック** を使用して、ツール実行前にカスタムチェックを挟む。

```json
// ./.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/validate-command.sh"
          }
        ]
      }
    ]
  }
}
```

### VSCode
`./vscode/setup.sh` を実行して、VSCode 設定のシンボリックを作成し、
VSCode 拡張をインストールする。

```shell
.
└── vscode
    ├── README.md
    ├── extensions    # VSCode 拡張リスト
    ├── projects.json # PROJECT MANAGER 拡張用設定
    ├── settings.json # VSCode 設定
    └── setup.sh
```

## ▍Makefile
### `brew/deps/show`
Homebrew の依存関係をツリー形式で表示する。

```shell
$ make brew/deps/show
```

### `brew/dump`
Homebrew でインストール中のパッケージを Brewfile としてリスト抽出する。
その Brewfile をベースに .Brewfile を最新化する。

```shell
$ make brew/dump
```

### `vscode/ext/list`
VSCode 拡張のリスト最新化する。

```shell
$ make vscode/ext/list
```
