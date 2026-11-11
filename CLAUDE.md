# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

シェル・エディタ・開発ツールの設定を管理する macOS dotfiles リポジトリ。各ディレクトリの `link.sh` / `setup.sh` を通じて設定ファイルを `~` にシンボリックリンクする。ビルド手順は存在せず、テストはフックの回帰テストと、リポジトリの検査（`.github/scripts/check-repo.py`）。PR と main への push で GitHub Actions（`.github/workflows/ci.yaml`）が実行する。

<a name="mise-tasks"></a>

## mise タスク

リポジトリ保守用のタスクはリポジトリルートの `mise.toml` に定義する。どのディレクトリからでも使うタスクは `mise/mise_config.toml` にグローバルタスクとして定義する。`mise tasks` で一覧を表示する。

```sh
mise run brew:deps:show   # Homebrew の依存関係ツリーを表示
mise run brew:dump        # インストール済みパッケージから Brewfile を再生成
mise run vscode:ext:list  # vscode/extensions リストを再生成
mise run sf:plugins       # sf のプラグインを config/sf/plugins.txt に同期（グローバルタスク）
```

## アーキテクチャ

各トップレベルディレクトリは独立しており、それぞれ `setup.sh` / `link.sh` を持つ:

| ディレクトリ | 役割                                                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `bin/`       | シェルコア設定（`.zshrc`, `.zprofile`, `.gitconfig`, `.Brewfile`）                                                                               |
| `zsh/`       | Zsh のインストールとシェル設定（エイリアス・キーバインド・オプション・autosuggestions）。プラグインの定義は `config/sheldon/plugins.toml`        |
| `mise/`      | `mise_config.toml` — 言語ランタイムのバージョン管理                                                                                              |
| `config/`    | starship, sheldon, uv, sf の設定（`karabiner/` は `link.sh` でリンクしていない）                                                                 |
| `aws/`       | AWS CLI プロファイル設定（config, credentials は gitignore 済み）                                                                                |
| `claude/`    | Claude Code の設定・フック・スキル・セットアップスクリプト                                                                                       |
| `codex/`     | Codex CLI の設定（`AGENTS.md` を `~/.codex/AGENTS.md` にリンク。`config.base.toml` は `sync.py` で `~/.codex/config.toml` にマージ）             |
| `obsidian/`  | Obsidian の Vault 設定と CSS スニペット（`~/Obsidian/main/.obsidian/` にシンボリックリンク）、Vault の同期・バックアップ手順（`SYNC_BACKUP.md`） |
| `vscode/`    | VSCode 設定・拡張リスト・プロジェクトマネージャー設定                                                                                            |
| `ghostty/`   | Ghostty ターミナル設定                                                                                                                           |
| `biome/`     | Biome のグローバル設定（`biome.jsonc`）。`$schema` のバージョンは mise の postinstall から `sync_schema.sh` で更新する                           |

## Claude Code 設定（`claude/`）

このディレクトリを `.claude/` という名前にしない。dotfiles で起動したときに、`~/.claude/` のリンク先と同じファイルが Project 設定としても読み込まれるため。

dotfiles で起動したときだけ必要な設定（`denyWrite`、`claudeMdExcludes`）は、`.claude/settings.json` に置く。

`claude/setup.sh` がメインのエントリーポイント。Claude Code のセッション内と IDE の統合ターミナルでは実行を拒否する（セッション中にリンクを張り直すと、Claude Code のサンドボックスがリンクを削除し、deny ルール・フック・サンドボックスが無効になるため）。通常のターミナルで、すべてのセッションを閉じてから実行する。以下を実行する:

- `settings.json`、`CLAUDE.md`、`rules/`、`mcp.json` を `~/.claude/` にシンボリックリンク
- `hooks/` ディレクトリを `~/.claude/hooks/` にシンボリックリンク
- `scripts/statusline.sh`（ステータスライン）を `~/.claude/scripts/` にシンボリックリンク
- プラグイン `superpowers@claude-plugins-official`, `claude-code-setup@claude-plugins-official`, `crit@crit` をインストールし、gstack を `~/.claude/skills/gstack` に clone してセットアップ
- `skills/*/` を `~/.claude/skills/` にシンボリックリンク

### フック

| ファイル                       | トリガー          | 動作                                                                                                                        |
| ------------------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `hooks/validate-command.sh`    | PreToolUse (Bash) | `rm -rf` および `prod`/`prd` を含むコマンドをブロック（`sf devops` の参照系コマンドと PR 作成は、単独のコマンドに限り許可） |
| `hooks/protect-main-branch.sh` | PreToolUse (Bash) | `main`, `master`, `staging` への `git commit` をブロック                                                                    |
| `hooks/ask-gh-pr-write.sh`     | PreToolUse (Bash) | `gh` の PR 書き込みと `gh api` を、表記ゆれも含めて人間の承認に回す                                                         |
| `hooks/precompact-context.sh`  | PreCompact        | ブランチ名・`git status --short`・直近 5 件のコミットを `additionalContext` として渡す                                      |
| `hooks/herdr-agent-state.sh`   | SessionStart      | herdr にセッション開始を通知する。herdr が生成・上書きするファイルのため編集しない                                          |
| `hooks/gh-read-token.sh`       | SessionStart      | sandbox 内の Bash に、作業中のリポジトリの owner 用の読み取り専用トークンを `GH_TOKEN` として渡す                           |

上記のほか、通知（Notification / Stop）や PR 作成時の URL 表示（PostToolUse）のフックは `settings.json` に直接記述している。

フックが exit code `2` を返すとツール実行がブロックされ、stderr の内容が Claude に表示される。

`protect-main-branch.sh` は、フックの cwd と、コマンド中のすべての `git commit` について `cd <dir>` と `git -C <dir>` から解決したリポジトリのブランチを判定し、いずれかが保護ブランチならブロックする。移動先を解決できない場合（変数を含むパス、存在しないディレクトリなど）もブロックする。`commit` に展開される git のエイリアス（`-c alias.*` を含む）も検査する。エイリアスは移動先のリポジトリの設定で解決し、多段のエイリアスもたどる（循環などでたどりきれなければ、commit とみなす）。移動先を解決できない場合は、git の組み込みコマンド以外をブロックする。シェルエイリアス（`!` で始まるもの）とオプションで始まるエイリアスは commit とみなす。同じ呼び出しの中で commit より前にブランチを切り替えるコマンド（`checkout`、`switch`、`branch`、`symbolic-ref`、`rebase`）があれば、フックは実行前のブランチで判定するため、ブロックする。

`validate-command.sh` と `protect-main-branch.sh` は、jq や git が動かないなどでコマンドを検査できないときもブロックする（fail closed）。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、`mise trust` を実行する。

### git push

Claude からの push は、`claude/bin/cc-safe-push` を root 所有でインストールしたラッパーだけで行う。`settings.json` は、引数なしの完全一致だけを `permissions.allow` と `sandbox.excludedCommands` に入れ、`git push` を deny にしている。判定はすべてラッパーで行い、フックには依存しない。

| 状況                                                                                                          | 結果                                   |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 許可リストのリポジトリの、保護されていないブランチ                                                            | 確認なしで push する                   |
| 許可リストにないリポジトリ                                                                                    | 拒否する。人間が自分の端末で push する |
| `main`, `master`, `staging`（大文字・小文字を区別しない）                                                     | 拒否する                               |
| 判定できない場合（detached HEAD、origin が `git@github.com:OWNER/REPO.git` の形でない、許可リストの異常など） | 拒否する                               |

push は、元のリポジトリの設定とフックを読まないように、macOS のユーザー専用の一時ディレクトリに作った空のリポジトリから行う（作業ディレクトリと `$TMPDIR` は sandbox から書けるので使わない）。元のリポジトリには書き込まないので、upstream は設定されない。

ラッパーと許可リストは、Claude が書き換えられないように root 所有にする。ラッパーを変更したら、再度インストールする。インストール手順と許可リストの書き方は、[claude/README.md](claude/README.md#cc-safe-push-install) を参照する。

### PR の作成・編集

Claude からの PR の作成・編集は、`claude/bin/cc-safe-pr` を root 所有でインストールしたラッパーで行う。`settings.json` は、`create` / `edit` の完全一致だけを `permissions.allow` と `sandbox.excludedCommands` に入れている。許可リストは `cc-safe-push` と共通で、リポジトリの判定には `cc-safe-push` の `evaluate()` をそのまま使う。

許可リストにないリポジトリでは拒否するので、人間が自分の端末で `gh pr create` を実行する。sandbox 内の `gh` は読み取り専用トークンで動くので、`permissions.ask` と `hooks/ask-gh-pr-write.sh` の承認画面で承認しても書き込めない（403）。

ラッパーは `evaluate()` の外で git を実行しない。index を読む git は `core.fsmonitor` を起動し、`core.hooksPath` では止まらないので、sandbox の外で任意のコードが動く経路になる。

sandbox 内からは Keychain を読めない（`sandbox.filesystem.denyRead`）ので、書き込みのできる `gh` のトークンを使えるのは、このラッパーと `cc-safe-push`、人間の端末だけ。sandbox 内の `gh` には `hooks/gh-read-token.sh` が読み取り専用トークンを渡す。詳細は [claude/README.md](claude/README.md#gh-read-token) を参照する。

### 個人スキル

`skills/*/` 配下の個人スキルは `~/.claude/skills/` にグローバルシンボリックリンクされ、全プロジェクトで使える。各スキルの用途は `SKILL.md` の `description` を参照する。

## 規約

- テストは `claude/hooks/tests/` のフック回帰テストと、`.github/scripts/` のリポジトリの検査。フックを変更したら `bash claude/hooks/tests/test-protect-main-branch.sh`、`bash claude/hooks/tests/test-validate-command.sh`、`bash claude/hooks/tests/test-ask-gh-pr-write.sh`、`bash claude/hooks/tests/test-gh-read-token.sh` を実行する。`claude/bin/cc-safe-push` か `claude/bin/cc-safe-pr` を変更したら `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` と `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` を実行する。`jq` が mise の shim に解決される PATH では `HOME` を変えて実行するテストが失敗するので、新しいシェルで実行する。設定ファイル・シェルスクリプト・Markdown・`.github/` を変更したら、`python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、`git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`、`actionlint` を実行する。これらとフック回帰テストは、PR と main への push で GitHub Actions も実行する。CI は push の後に動くので、ユーザー名を含むパスなどを公開前に防ぐには、push する前に手元で `check-repo.py` を実行する（`git add` 前のファイルも検査する）。それ以外の動作確認はセットアップスクリプトを手動実行して行う。
- Homebrew のパッケージリストの正規版は `bin/.Brewfile`。リポジトリルートの `Brewfile` は `mise run brew:dump` で生成し、`bin/.Brewfile` を最新化するためのベースとして使う。
- `vscode/extensions` は `mise run vscode:ext:list` で生成するため手動編集しない。
- `aws/config` , `aws/credentials` は gitignore 済み。公開リポジトリであるため、AWS CLI 設定も credentials もコミットしない。
- Markdown ファイル名（`.md` を除く部分）は英大文字と `_` のみで構成する（例: `README.md`, `SYNC_BACKUP.md`）。新規作成・リネーム時に適用する。`docs/` 配下は例外とし、グローバル規約の保存パスに従う。
