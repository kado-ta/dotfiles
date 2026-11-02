# dotfiles

macOS の開発環境の設定を管理する dotfiles。シェル（Zsh）・ターミナル・エディタ・言語ランタイム・AI コーディングエージェント（Claude Code / Codex）の設定を含む。各ディレクトリのスクリプトが、設定ファイルをホームディレクトリ配下へシンボリックリンクし、必要なツールをインストールする。

## 目次

- [前提](#prerequisites)
- [セットアップ](#setup)
- [ディレクトリ構成](#directory-structure)
- [Claude Code 設定](#claude-code)
- [日常運用](#operations)

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
| `.bin/init.sh` | Xcode Command Line Tools と Homebrew をインストールする    |
| `zsh/setup.sh` | Homebrew の Zsh をインストールし、ログインシェルに設定する |

完了したらターミナルを再起動する。

> [!WARNING]
> `.bin/init.sh` は、インストール済みの Command Line Tools（`/Library/Developer/CommandLineTools`）を削除してから再インストールする。既存の Mac で再実行するときは注意する。

<a name="setup-tools"></a>
### 2. 設定のリンクとツールのインストール（`setup.command`）

ターミナルを再起動したら、Finder で `setup.command` をダブルクリックする（ターミナルから `~/dotfiles/setup.command` を実行してもよい）。下表の 1〜9 が順に実行される。10〜12 は必要に応じて個別に実行する。

| #   | スクリプト             | 内容                                                                                                                            |
| --- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `.bin/link.sh`         | `.bin/` の dotfiles（`.zshrc`・`.zprofile`・`.gitconfig`・`.Brewfile` など）を `~` にリンクする                                 |
| 2   | `.bin/setup_brew.sh`   | `~/.Brewfile` のパッケージをインストールする（`brew bundle --global`）                                                          |
| 3   | `.config/link.sh`      | Starship・Sheldon・uv の設定を `~/.config/` にリンクする                                                                        |
| 4   | `zsh/setup_plugins.sh` | Sheldon で Zsh プラグインをインストールする                                                                                     |
| 5   | `.aws/link.sh`         | AWS CLI の設定（`config`・`credentials`）をリンクする                                                                           |
| 6   | `mise/setup.sh`        | mise の設定を `~/.config/mise/config.toml` にリンクし、言語ランタイム・ツールをインストールする                                 |
| 7   | `claude/setup.sh`      | Claude Code の設定をリンクし、プラグインと gstack をインストールする（[詳細](#claude-code)）                                    |
| 8   | `.codex/setup.sh`      | Codex の `AGENTS.md` をリンクし、プラグインとスキルをインストールする。7 でインストールした gstack を使うため、7 の後に実行する |
| 9   | `vscode/setup.sh`      | VSCode の設定をリンクし、拡張をインストールする                                                                                 |
| 10  | `ghostty/link.sh`      | Ghostty の設定を `~/.config/ghostty/` にリンクする                                                                              |
| 11  | `biome/setup.sh`       | Biome のグローバル設定を `~/Library/Application Support/biome/` にリンクする                                                    |
| 12  | `.obsidian/setup.sh`   | Obsidian の設定を Vault（`~/Obsidian/main/.obsidian/`）にリンクする。Vault を作成し、Obsidian を閉じてから実行する              |

<a name="setup-manual"></a>
### 3. 手動で行う作業

スクリプトで自動化していない作業。

- **Codex の設定の反映**: `codex-config-sync --dry-run` で差分を確認し、`codex-config-sync` で `~/.codex/config.toml` に反映する（[.codex/README.md](.codex/README.md#setup)）。
- **Obsidian のプラグイン**: コミュニティプラグインをインストールし、同期・バックアップを設定する（[.obsidian/README.md](.obsidian/README.md#setup)）。
- **Salesforce 拡張用の JDK**: mise でインストールした JDK を `JavaVirtualMachines` にリンクし、VSCode を設定する（[mise/JAVA.md](mise/JAVA.md#jvm-symlink)）。
- **AWS Session Manager プラグイン**: Staging / Production 環境への SSH 接続に使う。macOS（Apple Silicon）では次のコマンドでインストールする。他のプラットフォームは [公式ドキュメント](https://docs.aws.amazon.com/ja_jp/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) を参照する。

  ```shell
  curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac_arm64/sessionmanager-bundle.zip" -o "sessionmanager-bundle.zip"
  unzip sessionmanager-bundle.zip
  sudo ./sessionmanager-bundle/install -i /usr/local/sessionmanagerplugin -b /usr/local/bin/session-manager-plugin
  ```

<a name="directory-structure"></a>
## ディレクトリ構成

各ディレクトリは独立しており、それぞれのスクリプトでセットアップする。

| ディレクトリ | 内容                                                                                   | 主なリンク先                               | 詳細                                       |
| ------------ | -------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------ |
| `.bin/`      | Zsh・Git・Homebrew の設定（`.zshrc`・`.zprofile`・`.gitconfig`・`.Brewfile`）          | `~/`                                       | —                                          |
| `zsh/`       | Zsh 本体のインストールと、エイリアス・キーバインド・オプション。Sheldon が直接読み込む | なし                                       | [zsh/README.md](zsh/README.md)             |
| `.config/`   | Starship・Sheldon・uv の設定（`karabiner/` は現在リンクしていない）                    | `~/.config/`                               | —                                          |
| `mise/`      | 言語ランタイム・ツールのグローバルバージョン（`mise_config.toml`）                     | `~/.config/mise/config.toml`               | [mise/JAVA.md](mise/JAVA.md)               |
| `.aws/`      | AWS CLI のプロファイル設定（`credentials` は Git 管理外）                              | `~/.aws/`                                  | —                                          |
| `claude/`    | Claude Code の設定・フック・ルール・個人スキル                                         | `~/.claude/`                               | [Claude Code 設定](#claude-code)           |
| `.codex/`    | Codex CLI のグローバル指示（`AGENTS.md`）と共通設定（`config.base.toml`）              | `~/.codex/`                                | [.codex/README.md](.codex/README.md)       |
| `vscode/`    | VSCode の設定・キーバインド・タスク・拡張リスト・Project Manager 拡張の設定            | `~/Library/Application Support/Code/User/` | —                                          |
| `ghostty/`   | Ghostty の設定                                                                         | `~/.config/ghostty/`                       | —                                          |
| `biome/`     | Biome のグローバル設定。`$schema` のバージョンは mise の postinstall で自動更新する    | `~/Library/Application Support/biome/`     | —                                          |
| `.obsidian/` | Obsidian の Vault 設定と CSS スニペット                                                | `~/Obsidian/main/.obsidian/`               | [.obsidian/README.md](.obsidian/README.md) |
| `docs/`      | 設計・計画などの作業文書                                                               | —                                          | —                                          |
| `.github/`   | `init.command` を macOS ランナーで実行する CI（GitHub 上で無効化している）             | —                                          | —                                          |

リポジトリルートには、セットアップのエントリーポイント（`init.command`・`setup.command`）、保守用タスク（`mise.toml`）、AI エージェント向けのリポジトリガイド（[CLAUDE.md](CLAUDE.md)・`AGENTS.md`）を置いている。

<a name="claude-code"></a>
## Claude Code 設定

`claude/setup.sh` は次を行う。

- `settings.json`・`CLAUDE.md`・`rules/`・`mcp.json`・`hooks/`・`scripts/statusline.sh` を `~/.claude/` にリンクする。`~/.claude/hooks/` が実ディレクトリの場合は、削除してからリンクに置き換える。
- `skills/*/` の個人スキルを `~/.claude/skills/` にリンクする（全プロジェクトで使える）。
- プラグイン `superpowers`・`claude-code-setup` と、スキル集 [gstack](https://github.com/garrytan/gstack) をインストールする（インストール済みならスキップする）。

`settings.json` のセキュリティ設定は、[【2026年最新版】Claude Codeで行うべきセキュリティ設定 10選 - Qiita](https://qiita.com/miruky/items/51db293a7a7d0d277a5d) を参考にしている。

<a name="claude-code-hooks"></a>
### フック

| ファイル                       | イベント           | 動作                                                                                                                                        |
| ------------------------------ | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `hooks/validate-command.sh`    | PreToolUse（Bash） | `rm -rf` と、本番環境（`prod` / `prd`）を含むコマンドをブロックする。`sf devops` の参照系コマンドと PR 作成は、単独のコマンドに限り許可する |
| `hooks/protect-main-branch.sh` | PreToolUse（Bash） | `main`・`master`・`staging` ブランチへの `git commit` をブロックする                                                                        |
| `hooks/precompact-context.sh`  | PreCompact         | ブランチ名・未コミットの変更・直近のコミットを、コンテキスト圧縮後も残す情報として Claude に渡す                                            |
| `hooks/herdr-agent-state.sh`   | SessionStart       | herdr 上で起動したセッションの開始を herdr に通知する。herdr が生成・管理するため、直接編集しない                                           |

このほか、入力待ちや応答完了の通知、PR 作成時の URL 表示などのフックを `settings.json` に直接記述している。ステータスライン（`scripts/statusline.sh`）は、カレントディレクトリ・ブランチ・コンテキスト使用率・利用上限の使用率・モデル・effort を表示する。

フックを変更したら、回帰テストを実行する。

```shell
bash claude/hooks/tests/test-protect-main-branch.sh
```

<a name="operations"></a>
## 日常運用

<a name="mise-tasks"></a>
### mise タスク

保守用のタスクをリポジトリルートの `mise.toml` に定義している。`mise tasks` で一覧を表示する。

| コマンド                   | 内容                                                                   |
| -------------------------- | ---------------------------------------------------------------------- |
| `mise run brew:deps:show`  | Homebrew の依存関係をツリー形式で表示する                              |
| `mise run brew:dump`       | インストール済みのパッケージをリポジトリルートの `Brewfile` に書き出す |
| `mise run vscode:ext:list` | インストール済みの VSCode 拡張を `vscode/extensions` に書き出す        |

<a name="update-package-lists"></a>
### パッケージリストの更新

- **Homebrew**: 正本は `.bin/.Brewfile`。`mise run brew:dump` で生成した `Brewfile`（Git 管理外）と見比べて、`.bin/.Brewfile` に反映する。
- **VSCode 拡張**: `vscode/extensions` は `mise run vscode:ext:list` で生成する。手で編集しない。

<a name="other-operations"></a>
### その他の運用

- Zsh の設定・プラグインの変更: [zsh/README.md](zsh/README.md#operations)
- Codex の設定の同期・取り込み（`codex-config-sync` / `codex-config-import`）: [.codex/README.md](.codex/README.md#operations)
- Obsidian の設定の変更: [.obsidian/README.md](.obsidian/README.md#operations)
- gstack の更新: `gstack-upgrade`（`--check` で確認のみ）
