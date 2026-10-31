# Zsh 設定の dotfiles 管理

## 目次

- [概要](#overview)
- [ディレクトリ構成](#directory-structure)
- [読み込みの仕組み](#loading)
- [セットアップ](#setup)
- [設定ファイル](#config-files)
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

`.zshrc` 本体（環境変数・プロンプト・履歴・Sheldon / Starship / mise の初期化）は `.bin/.zshrc` で管理しており、このディレクトリには含まれない。

<a name="directory-structure"></a>
## ディレクトリ構成

```text
~/dotfiles/
├── .bin/
│   ├── .zshrc                      # ~/.zshrc へリンク（.bin/link.sh）。sheldon source を実行する
│   └── .zprofile                   # ~/.zprofile へリンク。brew shellenv を実行する
├── .config/
│   └── sheldon/plugins.toml        # ~/.config/sheldon/plugins.toml へリンク（.config/link.sh）
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
- 起動時に即時読み込みが必要な設定は `sync.zsh` に書く想定だが、現在 `plugins.toml` の該当設定はコメントアウトされており、`sync.zsh` も存在しない。即時に必要な設定は `.bin/.zshrc` に書く。

<a name="setup"></a>
## セットアップ

### 前提条件

- macOS（`setup.sh` は macOS 以外では終了する）。
- Homebrew がインストール済みであること（`.bin/init.sh` / `init.command`）。
- `setup_plugins.sh` の実行時点で、`sheldon` がインストール済み（`.bin/.Brewfile`）、かつ `~/.config/sheldon/plugins.toml` がリンク済み（`.config/link.sh`）であること。

### 1. `setup.sh`：Zsh のインストールとログインシェル変更

`init.command` から呼ばれる。単独で実行してもよい。

1. macOS であることを確認する。
2. `brew install zsh` で Zsh をインストールする。
3. `$(brew --prefix)/bin/zsh` を `/etc/shells` に追記する。
4. `chsh -s` でログインシェルを Homebrew の Zsh に変更する。

```bash
~/dotfiles/zsh/setup.sh
```

**実行後はターミナルを再起動する。** 以降のスクリプトは新しいシェルで実行する。

### 2. `setup_plugins.sh`：Sheldon プラグインのインストール

`setup.command` から呼ばれる。単独で実行してもよい。

`sheldon lock --reinstall` を実行し、`plugins.toml` に記載したプラグインを取得し直してロックファイルを再生成する。何度実行してもよい。

```bash
~/dotfiles/zsh/setup_plugins.sh
exec zsh
```

### 新しい Mac での実行順序

```bash
# 1. Homebrew・Xcode CLI Tools・Zsh（init.command 経由でも可）
~/dotfiles/.bin/init.sh
~/dotfiles/zsh/setup.sh
# → ターミナルを再起動

# 2. Sheldon 本体と設定ファイルを用意してからプラグインを入れる
~/dotfiles/.bin/link.sh          # ~/.Brewfile, ~/.zshrc などをリンク
~/dotfiles/.bin/setup_brew.sh    # sheldon / starship / mise などをインストール
~/dotfiles/.config/link.sh       # ~/.config/sheldon/plugins.toml をリンク
~/dotfiles/zsh/setup_plugins.sh
exec zsh
```

`setup.command` は `zsh/setup_plugins.sh` を最初に実行するため、新しい Mac ではこの時点で `sheldon` や `plugins.toml` が揃っておらず失敗しうる（[既知の制約・注意点](#limitations) 参照）。

<a name="config-files"></a>
## 設定ファイル

| ファイル | 内容 |
| --- | --- |
| `alias.zsh` | コマンドのエイリアス・関数（下表） |
| `bindkey.zsh` | Emacs 風キーバインド（`bindkey -e`） |
| `select-word-style.zsh` | 単語区切り文字（`/` も区切りにして `^W` でパス 1 階層分を削除）、補完の大文字小文字無視、`sudo` 後のコマンド補完、`ps` のプロセス名補完 |
| `setpot.zsh` | `setopt` によるシェルオプション（ヒストリ共有・重複除外、`auto_cd`、`auto_pushd`、`extended_glob`、`no_beep` など） |
| `zsh-autosuggestions.zsh` | zsh-autosuggestions の候補表示色（`ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=242'`） |

### `alias.zsh` の主な定義

| 名前 | 内容 |
| --- | --- |
| `ls` / `la` / `ll` | OS 別の色付き表示（macOS は `ls -G -F`） |
| `rm` / `cp` / `mv` | `-i` で上書き・削除前に確認 |
| `mkdir` | `-p` で親ディレクトリも作成 |
| `be` | `bundle exec` |
| `typora <file>` | Typora でファイルを開く（`open -a Typora`、macOS のみ） |
| `sudo` | `sudo ` 後のコマンドでもエイリアスを展開 |
| `L` / `G`（グローバル） | `\| less` / `\| grep` |
| `codex-config-sync` / `codex-config-import` | Codex 設定の同期・取り込み（[.codex/README.md](../.codex/README.md) 参照） |
| `ua-dashboard [dir]` | Understand Anything のダッシュボードを起動（関数） |
| `gstack-upgrade [--check]` | gstack を最新版へ更新（`--check` は確認のみ）（関数） |

### プラグイン（`.config/sheldon/plugins.toml`）

プラグインの追加・削除は `plugins.toml` で行う。現在の構成は以下のとおり（記載順に読み込まれる）。

| プラグイン | 読み込み | 役割 |
| --- | --- | --- |
| `romkatv/zsh-defer` | 即時 | 遅延読み込み機能 |
| `johnhamelink/env-zsh` | 即時 | 作業ディレクトリの `.env` から環境変数を読み込む |
| `colors`（inline） | 遅延 | プロンプトの色 |
| `zdharma/fast-syntax-highlighting` | 遅延 | シンタックスハイライト |
| `zsh-users/zsh-autosuggestions` | 遅延 | 入力候補のグレー表示 |
| `mise-activate`（inline） | 遅延 | `mise activate zsh` |
| `zsh-users/zsh-completions` | 遅延 | 補完定義の追加 |
| `compinit`（inline） | 遅延 | 補完の有効化と aws-cli 補完 |
| `z-shell/H-S-MW` | 遅延 | `Ctrl-R` で複数キーワード AND 検索 |
| `dotfile-defers`（local） | 遅延 | `~/dotfiles/zsh/*.zsh` |

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
- 遅延読み込みのため、プロンプト表示前に必要な設定（`PROMPT` など）は `.bin/.zshrc` に書く。

### プラグインを追加・削除した

`~/dotfiles/.config/sheldon/plugins.toml` を編集し、プラグインを再取得する。

```bash
~/dotfiles/zsh/setup_plugins.sh   # sheldon lock --reinstall
exec zsh
```

`plugins.toml` は**記載順に読み込まれる**。`zsh-defer` は先頭、`dotfile-defers` は末尾に置く。

<a name="limitations"></a>
## 既知の制約・注意点

1. **`setup.sh` の `/etc/shells` 追記は root 権限が必要。** スクリプトは `sudo` を付けずに `echo ... >> /etc/shells` を実行するため、通常ユーザーでは書き込みに失敗し、`bash -e` によりそこで終了する。その場合は手動で追記してから `chsh` を実行する。

   ```bash
   echo "$(brew --prefix)/bin/zsh" | sudo tee -a /etc/shells
   chsh -s "$(brew --prefix)/bin/zsh"
   ```

2. **`setup.sh` は `/etc/shells` の重複を確認しない。** 再実行すると同じパスが追記される。
3. **`setup.command` の実行順序。** `zsh/setup_plugins.sh` が `.bin/setup_brew.sh`（`sheldon` のインストール）や `.config/link.sh`（`plugins.toml` のリンク）より前に実行される。新しい Mac では [新しい Mac での実行順序](#setup) に従う。
4. **mise の二重初期化。** `.bin/.zshrc` と `plugins.toml` の `mise-activate` の両方で `mise activate zsh` を実行している。
5. **自動テストはない。** 変更後は新しいシェルを起動して動作を確認する。

<a name="troubleshooting"></a>
## トラブルシューティング

**`command not found: sheldon`**

- `.bin/setup_brew.sh` で Brewfile のパッケージをインストールする。

**追加した `.zsh` ファイルが読み込まれない**

- `sheldon lock` を実行してから `exec zsh` する。
- ファイル名が `sync.zsh` でないこと、拡張子が `.zsh` であることを確認する。
- 読み込み対象は次のコマンドで確認できる。

  ```bash
  sheldon source | grep dotfiles/zsh
  ```

**ログインシェルが `/bin/zsh`（macOS 標準）のまま**

- `echo $SHELL` と `cat /etc/shells` を確認し、[既知の制約・注意点](#limitations) の 1. の手順で変更する。

**プロンプト表示直後にエイリアスやキーバインドが効かない**

- `zsh/*.zsh` は遅延読み込みのため、起動直後のわずかな間は未適用になる。即時に必要な設定は `.bin/.zshrc` に移す。

<a name="references"></a>
## 参考資料

- [Sheldon: GitHub](https://github.com/rossmacarthur/sheldon)
- [zsh-defer: GitHub](https://github.com/romkatv/zsh-defer)
- [Sheldon と zsh-defer によるプラグイン遅延読み込み（Zenn）](https://zenn.dev/ganta/articles/e1e0746136ce67)
