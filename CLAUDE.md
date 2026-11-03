# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

シェル・エディタ・開発ツールの設定を管理する macOS dotfiles リポジトリ。各ディレクトリの `link.sh` / `setup.sh` を通じて設定ファイルを `~` にシンボリックリンクする。ビルド手順は存在せず、テストはフックの回帰テストのみ。

<a name="mise-tasks"></a>
## mise タスク

タスクはリポジトリルートの `mise.toml` に定義する。`mise tasks` で一覧を表示する。

```sh
mise run brew:deps:show   # Homebrew の依存関係ツリーを表示
mise run brew:dump        # インストール済みパッケージから Brewfile を再生成
mise run vscode:ext:list  # vscode/extensions リストを再生成
```

## アーキテクチャ

各トップレベルディレクトリは独立しており、それぞれ `setup.sh` / `link.sh` を持つ:

| ディレクトリ | 役割                                                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.bin/`      | シェルコア設定（`.zshrc`, `.zprofile`, `.gitconfig`, `.Brewfile`）                                                                               |
| `zsh/`       | Zsh のインストールとシェル設定（エイリアス・キーバインド・オプション・autosuggestions）。プラグインの定義は `.config/sheldon/plugins.toml`       |
| `mise/`      | `mise_config.toml` — 言語ランタイムのバージョン管理                                                                                              |
| `.config/`   | starship, sheldon, uv の設定（`karabiner/` は `link.sh` でリンクしていない）                                                                     |
| `.aws/`      | AWS CLI プロファイル設定（credentials は gitignore 済み）                                                                                        |
| `claude/`    | Claude Code の設定・フック・スキル・セットアップスクリプト                                                                                       |
| `.codex/`    | Codex CLI の設定（`AGENTS.md` を `~/.codex/AGENTS.md` にリンク。`config.base.toml` は `sync.py` で `~/.codex/config.toml` にマージ）             |
| `.obsidian/` | Obsidian の Vault 設定と CSS スニペット（`~/Obsidian/main/.obsidian/` にシンボリックリンク）、Vault の同期・バックアップ手順（`SYNC_BACKUP.md`） |
| `vscode/`    | VSCode 設定・拡張リスト・プロジェクトマネージャー設定                                                                                            |
| `ghostty/`   | Ghostty ターミナル設定                                                                                                                           |
| `biome/`     | Biome のグローバル設定（`biome.jsonc`）。`$schema` のバージョンは mise の postinstall から `sync_schema.sh` で更新する                           |

## Claude Code 設定（`claude/`）

このディレクトリを `.claude/` という名前にしない。dotfiles で起動したときに、`~/.claude/` のリンク先と同じファイルが Project 設定としても読み込まれるため（[経緯](claude/DOUBLE_LOAD_WARNING.md)）。

dotfiles で起動したときだけ必要な設定（`denyWrite`、`claudeMdExcludes`）は、`.claude/settings.json` に置く。

`claude/setup.sh` がメインのエントリーポイント。Claude Code のセッション内と IDE の統合ターミナルでは実行を拒否する（[経緯](claude/DOUBLE_LOAD_WARNING.md#deploy-to-other-machines)）。通常のターミナルで、すべてのセッションを閉じてから実行する。以下を実行する:
- `settings.json`、`CLAUDE.md`、`rules/`、`mcp.json` を `~/.claude/` にシンボリックリンク
- `hooks/` ディレクトリを `~/.claude/hooks/` にシンボリックリンク
- `scripts/statusline.sh`（ステータスライン）を `~/.claude/scripts/` にシンボリックリンク
- プラグイン `superpowers@claude-plugins-official`, `claude-code-setup@claude-plugins-official` をインストールし、gstack を `~/.claude/skills/gstack` に clone してセットアップ
- `skills/*/` を `~/.claude/skills/` にシンボリックリンク

### フック

| ファイル                       | トリガー          | 動作                                                                                                                        |
| ------------------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `hooks/validate-command.sh`    | PreToolUse (Bash) | `rm -rf` および `prod`/`prd` を含むコマンドをブロック（`sf devops` の参照系コマンドと PR 作成は、単独のコマンドに限り許可） |
| `hooks/protect-main-branch.sh` | PreToolUse (Bash) | `main`, `master`, `staging` への `git commit` をブロック                                                                    |
| `hooks/precompact-context.sh`  | PreCompact        | ブランチ名・`git status --short`・直近 5 件のコミットを `additionalContext` として渡す                                      |
| `hooks/herdr-agent-state.sh`   | SessionStart      | herdr にセッション開始を通知する。herdr が生成・上書きするファイルのため編集しない                                          |

上記のほか、通知（Notification / Stop）や PR 作成時の URL 表示（PostToolUse）のフックは `settings.json` に直接記述している。

フックが exit code `2` を返すとツール実行がブロックされ、stderr の内容が Claude に表示される。

`protect-main-branch.sh` は、フックの cwd と、コマンド中のすべての `git commit` について `cd <dir>` と `git -C <dir>` から解決したリポジトリのブランチを判定し、いずれかが保護ブランチならブロックする。移動先を解決できない場合（変数を含むパス、存在しないディレクトリなど）もブロックする。

`validate-command.sh` と `protect-main-branch.sh` は、jq が動かないなどでコマンドを検査できないときもブロックする（fail closed）。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、`mise trust` を実行する。

### 個人スキル

`skills/*/` 配下の個人スキルは `~/.claude/skills/` にグローバルシンボリックリンクされ、全プロジェクトで使える。各スキルの用途は `SKILL.md` の `description` を参照する。

## 規約

- テストは `claude/hooks/tests/` のフック回帰テストのみ。フックを変更したら `bash claude/hooks/tests/test-protect-main-branch.sh` と `bash claude/hooks/tests/test-validate-command.sh` を実行する。`jq` が mise の shim に解決される PATH では `HOME` を変えて実行するテストが失敗するので、新しいシェルで実行する。それ以外の動作確認はセットアップスクリプトを手動実行して行う。
- Homebrew のパッケージリストの正規版は `.bin/.Brewfile`。リポジトリルートの `Brewfile` は `mise run brew:dump` で生成し、`.bin/.Brewfile` を最新化するためのベースとして使う。
- `vscode/extensions` は `mise run vscode:ext:list` で生成するため手動編集しない。
- `.aws/credentials` は gitignore 済み。credentials をコミットしない。
- Markdown ファイル名（`.md` を除く部分）は英大文字と `_` のみで構成する（例: `README.md`, `SYNC_BACKUP.md`）。新規作成・リネーム時に適用する。`docs/` 配下は例外とし、グローバル規約の保存パスに従う。
