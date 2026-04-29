# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

シェル・エディタ・開発ツールの設定を管理する macOS dotfiles リポジトリ。各ディレクトリの `link.sh` / `setup.sh` を通じて設定ファイルを `~` にシンボリックリンクする。ビルド手順・テストスイートは存在しない。

## セットアップフロー

新しいマシンでは以下の順に実行する:
1. `init.command` — Homebrew + Xcode CLI Tools のインストール（Finder からダブルクリック）
2. `setup.command` — ランタイム・ライブラリ・ツール設定（Finder からダブルクリック）

以下の個別スクリプトはシェル再起動後に実行する必要がある（`Makefile` コメント参照）:
- `.bin/link.sh` — dotfiles を `~` にシンボリックリンク
- `.bin/setup_brew.sh` — `Brewfile` からパッケージをインストール
- `zsh/setup.sh` / `zsh/setup_plugins.sh`
- `mise/setup.sh` — mise 設定をシンボリックリンクしランタイムをインストール
- `.config/link.sh`, `.aws/link.sh`, `ghostty/link.sh`, `vscode/setup.sh`
- `.claude/setup.sh` — Claude Code 設定のシンボリックリンク作成とプラグインインストール

## Makefile ターゲット

```sh
make brew/deps/show   # Homebrew の依存関係ツリーを表示
make brew/dump        # インストール済みパッケージから Brewfile を再生成
make vscode/ext/list  # vscode/extensions リストを再生成
```

## アーキテクチャ

各トップレベルディレクトリは独立しており、それぞれ `setup.sh` / `link.sh` を持つ:

| ディレクトリ | 役割 |
|---|---|
| `.bin/` | シェルコア設定（`.zshrc`, `.zprofile`, `.gitconfig`, `.Brewfile`） |
| `zsh/` | Zsh プラグイン設定（エイリアス・キーバインド・オプション・autosuggestions） |
| `mise/` | `mise_config.toml` — 言語ランタイムのバージョン管理 |
| `.config/` | karabiner, sheldon, starship の設定 |
| `.aws/` | AWS CLI プロファイル設定（credentials は gitignore 済み） |
| `.claude/` | Claude Code の設定・フック・スキル・セットアップスクリプト |
| `vscode/` | VSCode 設定・拡張リスト・プロジェクトマネージャー設定 |
| `ghostty/` | Ghostty ターミナル設定 |

## Claude Code 設定（`.claude/`）

`.claude/setup.sh` がメインのエントリーポイント。以下を実行する:
- `settings.json` と `CLAUDE.md` を `~/.claude/` にシンボリックリンク
- `hooks/` ディレクトリを `~/.claude/hooks/` にシンボリックリンク
- プラグインをインストール: `superpowers@claude-plugins-official`, `claude-code-setup@claude-plugins-official`, `gstack`
- `skills/*/` を `~/.claude/skills/` にシンボリックリンク

### フック

| ファイル | トリガー | 動作 |
|---|---|---|
| `hooks/validate-command.sh` | PreToolUse (Bash) | `rm -rf` および `prod`/`prd` を含むコマンドをブロック |
| `hooks/protect-main-branch.sh` | PreToolUse (Bash) | `main`, `master`, `staging` への `git commit` をブロック |

フックが exit code `2` を返すとツール実行がブロックされ、stderr の内容が Claude に表示される。

### 個人スキル

`skills/code-style/` と `skills/superpowers-doc-conventions/` は `~/.claude/skills/` にグローバルシンボリックリンクされ、Superpowers スキルの動作を上書き・拡張する。

## 規約

- テストは存在しない。動作確認はセットアップスクリプトを手動実行して行う。
- `Brewfile` はリポジトリルートが正規版。`make brew/dump` で再生成する。
- `vscode/extensions` は `make vscode/ext/list` で生成するため手動編集しない。
- `.aws/credentials` は gitignore 済み。credentials をコミットしない。
