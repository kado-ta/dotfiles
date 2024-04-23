# dotfiles
## Setup
Finder から下記 2つのファイルを実行する。(**※ ダブルクリックで実行する。**)
1. `init.command` : Homebrew インストールや zsh 設定など。
2. `setup.command` : 開発環境に必要なランタイム・ライブラリ等のセットアップ。

## Directories
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
    ├── .asdfrc        # asdf 設定
    ├── .gitconfig     # Git 設定
    ├── .tool-versions # asdf が使用するグローバル・バージョン設定
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

### asdf
asdf セットアップ用スクリプト。

`./asdf/setup.sh` を実行することで、`.bin/.tool-versions` に記載の言語等をインストールする。


```shell
.
└── asdf
    ├── README.md
    └── setup.sh
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

### .config
各種設定情報。

`./.config/link.sh` を実行して、セットアップする。

```shell
.
└── .config
    ├── karabiner
    │   └── karabiner.json
    ├── link.sh
    ├── sheldon
    │   └── plugins.toml
    └── starship
        └── starship.toml
```

### vscode
`./vscode/setup.sh` を実行して、VSCode 設定のシンボリックを作成し、
VSCode 拡張をインストールする。

```shell
.
└── vscode
    ├── README.md
    ├── extensions    # VSCode 拡張リスト
    ├── settings.json # VSCode 設定
    └── setup.sh
```

## Makefile
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

### `vscode/extensions/list`
VSCode 拡張のリスト最新化する。

```shell
$ make vscode/extensions/list
```
