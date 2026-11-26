# Zsh 設定の dotfiles 管理

## 目次

- [概要](#overview)
- [ディレクトリ構成](#directory-structure)
- [読み込みの仕組み](#loading)
- [セットアップ](#setup)
- [設定ファイル](#config-files)
- [プロジェクトの環境変数](#project-env)
- [日常運用](#operations)
- [既知の制約・注意点](#limitations)
- [トラブルシューティング](#troubleshooting)
- [参考資料](#references)

<a name="overview"></a>

## 概要

このディレクトリでは、Zsh 本体のインストールと、エイリアス・キーバインド・オプションなどの**シェル設定**を管理する。

- Zsh 本体は Homebrew でインストールし、ログインシェルに設定する（`setup.sh`）。
- プラグインは [Sheldon](https://github.com/rossmacarthur/sheldon) で管理する（`setup_plugins.sh`）。
- `zsh/*.zsh` は Sheldon のローカルプラグインとして、[zsh-defer](https://github.com/romkatv/zsh-defer) により**遅延読み込み**される。

`.zshrc` 本体（環境変数・プロンプト・履歴・Sheldon / Starship / mise / atuin の初期化）は `bin/.zshrc` で管理しており、このディレクトリには含まれない。

<a name="directory-structure"></a>

## ディレクトリ構成

```text
~/dotfiles/
├── bin/
│   ├── .zshrc                      # ~/.zshrc へリンク（bin/link.sh）。sheldon source を実行する
│   └── .zprofile                   # ~/.zprofile へリンク。brew shellenv を実行する
├── config/
│   └── sheldon/plugins.toml        # ~/.config/sheldon/plugins.toml へリンク（config/link.sh）
└── zsh/                            # このディレクトリ
    ├── README.md
    ├── setup.sh                    # Zsh のインストールとログインシェル変更
    ├── setup_plugins.sh            # Sheldon プラグインのインストール
    ├── alias.zsh
    ├── bindkey.zsh
    ├── select-word-style.zsh
    ├── setpot.zsh
    └── zsh-autosuggestions.zsh
```

`zsh/` 内のファイルは `~` へシンボリックリンクしない。Sheldon が `~/dotfiles/zsh` を直接参照する。

<a name="loading"></a>

## 読み込みの仕組み

シェル起動時の流れは以下のとおり。

1. `~/.zprofile`（ログインシェル）で Homebrew の環境変数を設定する。
2. `~/.zshrc` が `eval "$(sheldon source)"` を実行する。
3. Sheldon が `~/.config/sheldon/plugins.toml` の記載順にプラグインを読み込む。
4. 最後の `[plugins.dotfile-defers]` で、`~/dotfiles/zsh/` の `*.zsh`（`sync.zsh` を除く）を読み込む。

```toml
[plugins.dotfile-defers]
local = "~/dotfiles/zsh"
use = ["{!sync,*}.zsh"]
```

- `plugins.toml` のデフォルトが `apply = ["defer"]` のため、`zsh/*.zsh` は `zsh-defer source` で**プロンプト表示後に**読み込まれる。
- `use` のグロブに一致したファイル一覧は、`sheldon lock` 実行時に `~/.local/share/sheldon/plugins.lock` へ記録される。**ファイルを追加・削除・リネームしたときは再ロックが必要**（[日常運用](#operations) 参照）。
- 起動時に即時読み込みが必要な設定は `sync.zsh` に書く想定だが、現在 `plugins.toml` の該当設定はコメントアウトされており、`sync.zsh` も存在しない。即時に必要な設定は `bin/.zshrc` に書く。

<a name="setup"></a>

## セットアップ

### 前提条件

- macOS（`setup.sh` は macOS 以外では終了する）。
- Homebrew がインストール済みであること（`bin/init.sh` / `init.command`）。
- `setup_plugins.sh` の実行時点で、`sheldon` がインストール済み（`bin/.Brewfile`）、かつ `~/.config/sheldon/plugins.toml` がリンク済み（`config/link.sh`）であること。

### 1. `setup.sh`：Zsh のインストールとログインシェル変更

`init.command` から呼ばれる。単独で実行してもよい。

1. macOS であることを確認する。
2. `brew install zsh` で Zsh をインストールする。
3. `$(brew --prefix)/bin/zsh` を `/etc/shells` に追記する（`sudo tee -a`）。
4. `chsh -s` でログインシェルを Homebrew の Zsh に変更する。

```bash
~/dotfiles/zsh/setup.sh
```

**実行後はターミナルを再起動する。** 以降のスクリプトは新しいシェルで実行する。

### 2. `setup_plugins.sh`：Sheldon プラグインのインストール

`setup.command` から呼ばれる。単独で実行してもよい。

`sheldon lock` を実行し、`plugins.toml` に記載したプラグインのうち未取得のものを取得して、ロックファイルを再生成する。取得済みのプラグインは取り直さないので、何度実行してもよい。プラグインを取り直すときは `sheldon lock --reinstall` を手動で実行する。

```bash
~/dotfiles/zsh/setup_plugins.sh
exec zsh
```

### 新しい Mac での実行順序

```bash
# 1. Homebrew・Xcode CLI Tools・Zsh（init.command 経由でも可）
~/dotfiles/bin/init.sh
~/dotfiles/zsh/setup.sh
# → ターミナルを再起動

# 2. Sheldon 本体と設定ファイルを用意してからプラグインを入れる（setup.command 経由でも可）
~/dotfiles/bin/link.sh          # ~/.Brewfile, ~/.zshrc などをリンク
~/dotfiles/bin/setup_brew.sh    # sheldon / starship / mise などをインストール
~/dotfiles/config/link.sh       # ~/.config/sheldon/plugins.toml をリンク
~/dotfiles/zsh/setup_plugins.sh
exec zsh
```

<a name="config-files"></a>

## 設定ファイル

| ファイル                  | 内容                                                                                                                                    |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `alias.zsh`               | コマンドのエイリアス・関数（下表）                                                                                                      |
| `bindkey.zsh`             | Emacs 風キーバインド（`bindkey -e`）                                                                                                    |
| `select-word-style.zsh`   | 単語区切り文字（`/` も区切りにして `^W` でパス 1 階層分を削除）、補完の大文字小文字無視、`sudo` 後のコマンド補完、`ps` のプロセス名補完 |
| `setpot.zsh`              | `setopt` によるシェルオプション（ヒストリ共有・重複除外、`auto_cd`、`auto_pushd`、`extended_glob`、`no_beep` など）                     |
| `zsh-autosuggestions.zsh` | zsh-autosuggestions の候補表示色（`ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=242'`）と、候補の出どころ（zsh の履歴。atuin の初期化が変えるので戻す） |

### `alias.zsh` の主な定義

| 名前                                        | 内容                                                                     |
| ------------------------------------------- | ------------------------------------------------------------------------ |
| `ls` / `la` / `ll`                          | OS 別の色付き表示（macOS は `ls -G -F`）                                 |
| `rm` / `cp` / `mv`                          | `-i` で上書き・削除前に確認                                              |
| `mkdir`                                     | `-p` で親ディレクトリも作成                                              |
| `be`                                        | `bundle exec`                                                            |
| `typora <file>`                             | Typora でファイルを開く（`open -a Typora`、macOS のみ）                  |
| `sudo`                                      | `sudo ` 後のコマンドでもエイリアスを展開                                 |
| `L` / `G`（グローバル）                     | `\| less` / `\| grep`                                                    |
| `codex-config-sync` / `codex-config-import` | Codex 設定の同期・取り込み（[codex/README.md](../codex/README.md) 参照） |
| `ua-dashboard [dir]`                        | Understand Anything のダッシュボードを起動（関数）                       |
| `gstack-upgrade [--check]`                  | gstack を最新版へ更新し、settings.json の絶対パスを `~/` に戻す（`--check` は確認のみ）（関数） |

### プラグイン（`config/sheldon/plugins.toml`）

プラグインの追加・削除は `plugins.toml` で行う。現在の構成は以下のとおり（記載順に読み込まれる）。

| プラグイン                         | 読み込み | 役割                                             |
| ---------------------------------- | -------- | ------------------------------------------------ |
| `romkatv/zsh-defer`                | 即時     | 遅延読み込み機能                                 |
| `colors`（inline）                 | 遅延     | プロンプトの色                                   |
| `zdharma/fast-syntax-highlighting` | 遅延     | シンタックスハイライト                           |
| `zsh-users/zsh-autosuggestions`    | 遅延     | 入力候補のグレー表示                             |
| `zsh-users/zsh-completions`        | 遅延     | 補完定義の追加                                   |
| `compinit`（inline）               | 遅延     | 補完の有効化と aws-cli 補完                      |
| `dotfile-defers`（local）          | 遅延     | `~/dotfiles/zsh/*.zsh`                           |

作業ディレクトリの `.env` を読み込むプラグインは入れない（[プロジェクトの環境変数](#project-env)）。

`Ctrl-R` の履歴の検索は、プラグインではなく atuin が受け持つ。`bin/.zshrc` で初期化し、設定は `config/atuin/config.toml` に置く（[config/README.md](../config/README.md)）。`~/.zsh_history` は自動では取り込まれないので、最初に一度だけ `atuin import zsh` を実行する（もう一度実行すると全件が重複する）。取り込みは秘密情報の除外（`secrets_filter`）を通らないので、続けて `atuin history prune` で該当する行を検索から外す。どちらも `~/.atuin` に書くので、Claude Code の sandbox の中ではなく通常のターミナルで実行する。prune しても DB のファイルには平文が残るので、履歴に残っていた秘密情報は失効させる。

<a name="completions"></a>

### コマンドの補完

`mise` の補完に手動の設定は要らない。Homebrew の `mise` が `$(brew --prefix)/share/zsh/site-functions/_mise` を配置し、`.zprofile` の `brew shellenv` がこのディレクトリを `fpath` に追加するので、`compinit` が読み込む。

- `.zprofile` を読まない非ログインシェルでは `fpath` に入らないため、補完は効かない。
- `mise completion zsh --install` は実行しなくてよい。書き出し先の `~/.local/share/zsh/site-functions/` は `fpath` に入っておらず、読み込まれない。コマンドが表示する `fpath` の行も、Homebrew 版で足りるので追加しない。

<a name="project-env"></a>

## プロジェクトの環境変数

プロジェクトごとの環境変数は、そのプロジェクトの `mise.toml` の `[env]` で読み込む。作業ディレクトリの `.env` を読み込む zsh のプラグインは入れない（[env-zsh を外した理由](#env-zsh-removed)）。

<a name="project-env-file"></a>

### `.env` を読み込む

そのプロジェクトの `mise.toml` に次のように書く。

```toml
[env]
_.file = ".env"
```

- mise は `.env` を `KEY=value` として解析し、シェルとして実行しないので、`$(...)` や `~` は書いたままの文字列になる。
- `PATH` の値は使われないので、足すディレクトリは `_.path` に書く。
- `.env.term` で値を上書きしていたなら、`_.file = [".env", ".env.term"]` のように後ろに並べる（後ろのファイルの値が勝つ）。

<a name="project-env-trust"></a>

### 信頼する

グローバルの設定の paranoid（`mise/mise_config.toml`）により、`mise.toml` と `.env` は、信頼するまで読み込まれず、中身が変わると信頼が外れる。全体を確かめたファイルだけを、1 つずつ信頼する。

```bash
mise trust mise.toml
mise trust .env
```

パスを省いた `mise trust` は、その設定が読む env ファイルとスクリプトもまとめて信頼するので使わない。

<a name="project-env-secrets"></a>

### 秘密の値

mise は読み込んだ値を export し、そのディレクトリで起動したプロセス（Claude Code を含む）にも渡す。秘密の値は `_.file` で読み込まず、要るコマンドにだけ渡す。

<a name="env-zsh-removed"></a>

### env-zsh を外した理由

前は sheldon のプラグイン env-zsh で `.env` を読み込んでいた。env-zsh は、ディレクトリを移るたびに `.env` と `.env.term` をシェルのコードとして読み込み、中身を確かめる仕組みがなかったので外した（KAD-11）。外す前から開いている zsh は、起動し直すまで読み込みを続けるので、[プラグインを追加・削除した](#operations)ときの手順で起動し直す。

<a name="operations"></a>

## 日常運用

### 既存の `.zsh` ファイルを編集した

新しいシェルを開くか `exec zsh` を実行する。再ロックは不要。

### `.zsh` ファイルを追加・削除・リネームした

ロックファイルのファイル一覧を更新してから再起動する。

```bash
sheldon lock
exec zsh
```

- `sync.zsh` という名前のファイルは `use` のグロブで除外されるため読み込まれない。
- 遅延読み込みのため、プロンプト表示前に必要な設定（`PROMPT` など）は `bin/.zshrc` に書く。

### プラグインを追加・削除した

`~/dotfiles/config/sheldon/plugins.toml` を編集し、未取得のプラグインを取得する。

```bash
~/dotfiles/zsh/setup_plugins.sh   # sheldon lock
exec zsh
```

`plugins.toml` は**記載順に読み込まれる**。`zsh-defer` は先頭、`dotfile-defers` は末尾に置く。

<a name="limitations"></a>

## 既知の制約・注意点

1. **`setup.sh` は `/etc/shells` の重複を確認しない。** 再実行すると同じパスが追記される。
2. **自動テストはない。** 変更後は新しいシェルを起動して動作を確認する。

<a name="troubleshooting"></a>

## トラブルシューティング

**`command not found: sheldon`**

- `bin/setup_brew.sh` で Brewfile のパッケージをインストールする。

**追加した `.zsh` ファイルが読み込まれない**

- `sheldon lock` を実行してから `exec zsh` する。
- ファイル名が `sync.zsh` でないこと、拡張子が `.zsh` であることを確認する。
- 読み込み対象は次のコマンドで確認できる。

  ```bash
  sheldon source | grep dotfiles/zsh
  ```

**ログインシェルが `/bin/zsh`（macOS 標準）のまま**

- `echo $SHELL` と `cat /etc/shells` を確認する。`/etc/shells` に Homebrew の Zsh がなければ追記してから、ログインシェルを変更する。

  ```bash
  echo "$(brew --prefix)/bin/zsh" | sudo tee -a /etc/shells   # /etc/shells にない場合のみ
  chsh -s "$(brew --prefix)/bin/zsh"
  ```

**プロンプト表示直後にエイリアスやキーバインドが効かない**

- `zsh/*.zsh` は遅延読み込みのため、起動直後のわずかな間は未適用になる。即時に必要な設定は `bin/.zshrc` に移す。

<a name="references"></a>

## 参考資料

- [Sheldon: GitHub](https://github.com/rossmacarthur/sheldon)
- [zsh-defer: GitHub](https://github.com/romkatv/zsh-defer)
- [Sheldon と zsh-defer によるプラグイン遅延読み込み（Zenn）](https://zenn.dev/ganta/articles/e1e0746136ce67)
