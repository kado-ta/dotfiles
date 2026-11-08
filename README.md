# dotfiles

macOS の開発環境の設定を管理する dotfiles。シェル（Zsh）・ターミナル・エディタ・言語ランタイム・AI コーディングエージェント（Claude Code / Codex）の設定を含む。各ディレクトリのスクリプトが、設定ファイルをホームディレクトリ配下へシンボリックリンクし、必要なツールをインストールする。

## 目次

- [前提](#prerequisites)
- [セットアップ](#setup)
- [ディレクトリ構成](#directory-structure)

<a name="prerequisites"></a>

## 前提

- macOS。各スクリプトは macOS 以外では終了する。
- リポジトリを `~/dotfiles` に置く。Sheldon の設定や Zsh のエイリアスが `~/dotfiles` を直接参照するため。
- 管理者権限。セットアップの途中で `sudo` と `chsh` を実行する。

<a name="setup"></a>

## セットアップ

<a name="setup-init"></a>

### 1. 基盤のインストール（`init.command`）

Finder で `init.command` をダブルクリックする（ターミナルから `~/dotfiles/init.command` を実行してもよい）。次のスクリプトが順に実行される。

| スクリプト     | 内容                                                       |
| -------------- | ---------------------------------------------------------- |
| `bin/init.sh`  | Xcode Command Line Tools と Homebrew をインストールする    |
| `zsh/setup.sh` | Homebrew の Zsh をインストールし、ログインシェルに設定する |

完了したらターミナルを再起動する。

> [!WARNING]
> `bin/init.sh` は、インストール済みの Command Line Tools（`/Library/Developer/CommandLineTools`）を削除してから再インストールする。既存の Mac で再実行するときは注意する。

<a name="setup-tools"></a>

### 2. 設定のリンクとツールのインストール（`setup.command`）

ターミナルを再起動したら、Finder で `setup.command` をダブルクリックする（ターミナルから `~/dotfiles/setup.command` を実行してもよい）。下表の 1〜9 が順に実行される。10〜12 は必要に応じて個別に実行する。

| #   | スクリプト             | 内容                                                                                                                            |
| --- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `bin/link.sh`          | `bin/` の dotfiles（`.zshrc`・`.zprofile`・`.gitconfig`・`.Brewfile` など）を `~` にリンクする                                  |
| 2   | `bin/setup_brew.sh`    | `~/.Brewfile` のパッケージをインストールする（`brew bundle --global`）                                                          |
| 3   | `config/link.sh`       | Starship・Sheldon・uv・sf の設定を `~/.config/` にリンクする                                                                    |
| 4   | `zsh/setup_plugins.sh` | Sheldon で Zsh プラグインをインストールする                                                                                     |
| 5   | `aws/link.sh`          | AWS CLI の設定（`config`・`credentials`）をリンクする                                                                           |
| 6   | `mise/setup.sh`        | mise の設定を `~/.config/mise/config.toml` にリンクし、言語ランタイム・ツールをインストールする                                 |
| 7   | `claude/setup.sh`      | Claude Code の設定をリンクし、プラグインと gstack をインストールする（[詳細](claude/README.md)）                                |
| 8   | `codex/setup.sh`       | Codex の `AGENTS.md` をリンクし、プラグインとスキルをインストールする。7 でインストールした gstack を使うため、7 の後に実行する |
| 9   | `vscode/setup.sh`      | VSCode の設定をリンクし、拡張をインストールする                                                                                 |
| 10  | `ghostty/link.sh`      | Ghostty の設定を `~/.config/ghostty/` にリンクする                                                                              |
| 11  | `biome/setup.sh`       | Biome のグローバル設定を `~/Library/Application Support/biome/` にリンクする                                                    |
| 12  | `obsidian/setup.sh`    | Obsidian の設定を Vault（`~/Obsidian/main/.obsidian/`）にリンクする。Vault を作成し、Obsidian を閉じてから実行する              |

<a name="setup-manual"></a>

### 3. 手動で行う作業

スクリプトで自動化していない作業。

- **AWS CLI の設定**: `aws/link.sh` が作成した `aws/config` と `aws/credentials` を編集する（[aws/README.md](aws/README.md#setup)）。
- **AWS Session Manager プラグイン**: Staging / Production 環境への SSH 接続に使う（[aws/README.md](aws/README.md#session-manager)）。
- **cc-safe-push**: Claude Code からの push に必要。`sudo` でインストールする（[claude/README.md](claude/README.md#cc-safe-push-install)）。
- **Codex の設定の反映**: `codex-config-sync` で `~/.codex/config.toml` に反映する（[codex/README.md](codex/README.md#setup)）。
- **Obsidian のプラグイン**: コミュニティプラグインをインストールし、同期・バックアップを設定する（[obsidian/README.md](obsidian/README.md#setup)）。
- **Salesforce 拡張用の JDK**: mise でインストールした JDK をリンクし、VSCode を設定する（[mise/JAVA.md](mise/JAVA.md#jvm-symlink)）。
- **Salesforce CLI のプラグイン**: `mise run sf:plugins` でインストールする（[config/README.md](config/README.md#sf-plugins)）。

<a name="directory-structure"></a>

## ディレクトリ構成

各ディレクトリは独立しており、それぞれのスクリプトでセットアップする。

| ディレクトリ | 内容                                                                                   | 主なリンク先                               | 詳細                                     |
| ------------ | -------------------------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------------- |
| `bin/`       | Zsh・Git・Homebrew の設定（`.zshrc`・`.zprofile`・`.gitconfig`・`.Brewfile`）          | `~/`                                       | [bin/README.md](bin/README.md)           |
| `zsh/`       | Zsh 本体のインストールと、エイリアス・キーバインド・オプション。Sheldon が直接読み込む | なし                                       | [zsh/README.md](zsh/README.md)           |
| `config/`    | Starship・Sheldon・uv・sf の設定（`karabiner/` は現在リンクしていない）                | `~/.config/`                               | [config/README.md](config/README.md)     |
| `mise/`      | 言語ランタイム・ツールのグローバルバージョン（`mise_config.toml`）                     | `~/.config/mise/config.toml`               | [mise/README.md](mise/README.md)         |
| `aws/`       | AWS CLI の設定（`config`・`credentials` は Git 管理外）                                | `~/.aws/`                                  | [aws/README.md](aws/README.md)           |
| `claude/`    | Claude Code の設定・フック・ルール・個人スキル                                         | `~/.claude/`                               | [claude/README.md](claude/README.md)     |
| `codex/`     | Codex CLI のグローバル指示（`AGENTS.md`）と共通設定（`config.base.toml`）              | `~/.codex/`                                | [codex/README.md](codex/README.md)       |
| `vscode/`    | VSCode の設定・キーバインド・タスク・拡張リスト・Project Manager 拡張の設定            | `~/Library/Application Support/Code/User/` | [vscode/README.md](vscode/README.md)     |
| `ghostty/`   | Ghostty の設定                                                                         | `~/.config/ghostty/`                       | —                                        |
| `biome/`     | Biome のグローバル設定。`$schema` のバージョンは mise の postinstall で自動更新する    | `~/Library/Application Support/biome/`     | —                                        |
| `obsidian/`  | Obsidian の Vault 設定と CSS スニペット                                                | `~/Obsidian/main/.obsidian/`               | [obsidian/README.md](obsidian/README.md) |
| `docs/`      | 設計・計画などの作業文書                                                               | —                                          | —                                        |
| `.github/`   | `init.command` を macOS ランナーで実行する CI（GitHub 上で無効化している）             | —                                          | —                                        |

リポジトリルートには、セットアップのエントリーポイント（`init.command`・`setup.command`）、保守用タスク（`mise.toml`）、AI エージェント向けのリポジトリガイド（[CLAUDE.md](CLAUDE.md)・`AGENTS.md`）を置いている。
