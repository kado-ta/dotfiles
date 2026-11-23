# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

シェル・エディタ・開発ツールの設定を管理する macOS dotfiles リポジトリ。各ディレクトリの `link.sh` / `setup.sh` を通じて設定ファイルを `~` にシンボリックリンクする。ビルド手順は存在せず、テストはフックの回帰テストと、リポジトリの検査（`.github/scripts/check-repo.py`）。PR と main への push で GitHub Actions（`.github/workflows/ci.yaml`）が実行する。

<a name="mise-tasks"></a>

## mise タスク

リポジトリ保守用のタスクはリポジトリルートの `mise.toml` に定義する。どのディレクトリからでも使うタスクは `mise/mise_config.toml` にグローバルタスクとして定義する。`mise tasks` で一覧を表示する。`mise run crit:profile-test` は sandbox の外で、crit・git・macOS を更新した後に実行する。

## Claude Code 設定（`claude/`）

このディレクトリを `.claude/` という名前にしない。dotfiles で起動したときに、`~/.claude/` のリンク先と同じファイルが Project 設定としても読み込まれるため。

dotfiles で起動したときだけ必要な設定（`denyWrite`、`claudeMdExcludes`）は、`.claude/settings.json` に置く。ここには制限を足す設定（`claudeMdExcludes`、`permissions.ask` / `deny`、`sandbox.filesystem.denyWrite` / `denyRead`）だけを置く。ほかのキーを足したり、今の ask と denyWrite の項目を消したりすると、`check-repo.py` の `project-permissions` が失敗する。外すときは検査の定数も一緒に変える。

この denyWrite のため、sandbox の中の git は、`claude/`・`mise/`・`mise.toml`・`CLAUDE.md`・`.claude/rules` などを書き換える操作（ブランチの切り替え・マージなど）の途中で止まる。`unable to unlink` や `Operation not permitted` が出たら、続けずに `git status` を確かめて報告し、その状態の作業ツリーをコミットしない。

`claude/setup.sh` がメインのエントリーポイント。Claude Code のセッション内と IDE の統合ターミナルでは実行を拒否する（セッション中にリンクを張り直すと、Claude Code のサンドボックスがリンクを削除し、deny ルール・フック・サンドボックスが無効になるため）。通常のターミナルで、すべてのセッションを閉じてから実行する。

`claude/`・`.claude/`・`.github/scripts/` を扱うときは、PR と Crit のラッパーと sandbox 設定の設計理由が [.claude/rules/CLAUDE_CONFIG.md](.claude/rules/CLAUDE_CONFIG.md) から読み込まれる。

### フック

`hooks/herdr-agent-state.sh` は herdr が生成・上書きするファイルのため編集しない。

`validate-command.sh` と `protect-main-branch.sh` は、jq や git が動かないなどでコマンドを検査できないときもブロックする（fail closed）。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、人間が mise の設定の全体を確かめてから `mise trust <ファイル>` を実行する。

### git push

Claude からの push は、`claude/bin/cc-safe-push` を root 所有でインストールしたラッパーだけで行う。`settings.json` は、引数なしの完全一致だけを `permissions.allow` と `sandbox.excludedCommands` に入れ、`git push` を deny にしている。判定はすべてラッパーで行い、フックには依存しない。

push は、元のリポジトリの設定とフックを読まないように、macOS のユーザー専用の一時ディレクトリに作った空のリポジトリから行う（作業ディレクトリと `$TMPDIR` は sandbox から書けるので使わない）。元のリポジトリには書き込まないので、upstream は設定されない。

ラッパーと許可リストは、Claude が書き換えられないように root 所有にする。ラッパーを変更したら、再度インストールする。インストール手順と許可リストの書き方は、[claude/README.md](claude/README.md#cc-safe-push-install) を参照する。

<a name="edit-write-rules"></a>

### Edit・Write ツールの書き込み

ユーザー設定で `permissions.blockWritesOutsideWorkingDirectories` をオンにしている。Edit・Write ツールは作業ディレクトリの外に書けず、Claude Code の設定ファイルは作業ディレクトリの中でも編集できない。外に書く必要があるときは、人間が `/add-dir` でディレクトリを足す。設定ファイルは人間が編集する。gstack の置き場所（`~/.gstack/projects`）は、`permissions.additionalDirectories` に入れているので書ける。規則の理由は [.claude/rules/CLAUDE_CONFIG.md](.claude/rules/CLAUDE_CONFIG.md#edit-write-rules) にある。

worktree は `claude -w <name>` で始める。この設定では EnterWorktree・ExitWorktree を使えない。ブランチ名は `worktree-<name>` になるので、規約の名前（`fix/…` など）には `git branch -m <新しい名前>` で変える。sandbox が `.git/config` を守っているので、`could not lock config file` と出て終了コード 128 で終わるが、名前は変わる。元のブランチに `branch.<name>.*` の設定がなければ、影響はない。終了コードが 0 でないので、`&&` で後ろにコマンドをつながない。

<a name="sandbox-prohibitions"></a>

### sandbox と権限の禁止事項

- `sandbox.filesystem.allowWrite` に `~/.crit` 配下を入れない。
- `sandbox.network` の `allowUnixSockets`・`allowAllUnixSockets`・`allowLocalBinding` を設定しない（`check-repo.py` の `push-permissions` が失敗する）。
- Colima（Lima）の VM に入る鍵（`~/.colima/_lima/_config`）を `denyRead` から外さない。
- `permissions.blockWritesOutsideWorkingDirectories`、`.git` の hooks の Edit の deny、mise の設定の Edit の ask、`Edit(~/.local/state/mise/**)` の deny と `Edit(~/dotfiles/mise/**)` の ask、`sandbox.filesystem.denyWrite` の `~/.config/mise`・`~/dotfiles/mise`・`~/.local/state/mise`、PreToolUse の `guard-additional-dirs.sh` の登録を外さない（`check-repo.py` の `edit-permissions` が失敗する）。
- `mise/mise_config.toml` の `paranoid` から `config`・`env_files` を外さない（`mise-paranoid` が失敗する）。
- `mise/mise_config.toml` に `settings.trusted_config_paths` を足さない（空のリストでも）。`bin/.z*`・`zsh/*.zsh`・`config/sheldon/plugins.toml`・`mise/mise_config.toml` に `MISE_TRUSTED_CONFIG_PATHS`・`MISE_PARANOID` を書かない（`mise-paranoid` が失敗する。理由は [.claude/rules/CLAUDE_CONFIG.md](.claude/rules/CLAUDE_CONFIG.md#edit-write-rules)）。
- `permissions.additionalDirectories` に `~/.gstack/projects` 以外を足さない（`edit-permissions` が失敗する）。
- `Edit(//**/.git/**/hooks/**)` と `Edit(//**/.git/config)` を deny にしない。Edit の deny は sandbox の denyWrite にもなり、どこでも `git init`・`git clone` が失敗する見込み（`edit-permissions` が失敗する）。
- ユーザー設定の `sandbox.filesystem` に、接頭辞のないパスを書かない。`~/` か `/` で始める（接頭辞がないと `~/.claude` が基準になる。`edit-permissions` が失敗する）。
- Read の deny の `*.pem` を `~/**` に広げない。
- `claude/mcp/playwright.json` があるあいだは、`permissions.deny` の `mcp__playwright__browser_run_code_unsafe`・`mcp__playwright__browser_file_upload`・`Read(~/.crit/**)`・`Edit(~/.local/share/claude-mcp/**)`・`Edit(~/Library/Caches/playwright-mcp/**)`、`sandbox.filesystem.denyRead` の `~/.crit`、`sandbox.filesystem.denyWrite` の `~/.local/share/claude-mcp`・`~/Library/Caches/playwright-mcp`、`disabledMcpjsonServers` の `playwright`、PreToolUse の `guard-playwright-mcp.sh` の登録（matcher `mcp__playwright__.*`、`onFailure: block`）を外さない（`check-repo.py` の `playwright-mcp` が失敗する）。Playwright MCP を実行時に npx で起動しない。`sandbox.filesystem.allowWrite` に `~/.local/share/claude-mcp` と `~/Library/Caches/playwright-mcp` を入れない（理由は [.claude/rules/CLAUDE_CONFIG.md](.claude/rules/CLAUDE_CONFIG.md#playwright-mcp)）。
- `bin/.gitconfig` の `rerere.enabled = false` を外さない。その後ろに include（`include.path`・`includeif.*.path`）を置かない（`check-repo.py` の `rerere` が失敗する。理由は [.claude/rules/CLAUDE_CONFIG.md](.claude/rules/CLAUDE_CONFIG.md#git-rerere)）。

## 規約

- テストは `claude/hooks/tests/` のフック回帰テストと、`.github/scripts/` のリポジトリの検査。フックを変更したら `bash claude/hooks/tests/test-protect-main-branch.sh`、`bash claude/hooks/tests/test-validate-command.sh`、`bash claude/hooks/tests/test-ask-gh-pr-write.sh`、`bash claude/hooks/tests/test-ask-shared-tree-git.sh`、`bash claude/hooks/tests/test-gh-read-token.sh`、`bash claude/hooks/tests/test-guard-additional-dirs.sh`、`bash claude/hooks/tests/test-guard-playwright-mcp.sh` を実行する。`claude/bin/cc-safe-push` か `claude/bin/cc-safe-pr` を変更したら `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` と `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` を実行する。`claude/bin/cc-crit` か `claude/bin/cc-crit.sb` を変更したら `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` を実行し、sandbox の外で `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py` を実行する（Claude Code の sandbox の中ではスキップされる）。`claude/scripts/skills-check.py`・`claude/scripts/skill-usage.py`・`claude/scripts/trust-audit.py`・`claude/scripts/settings-home-paths.py`・`claude/scripts/update-skills.sh`・`claude/scripts/register-mcp.sh`（と `claude/mcp/*.json`）を変更したら、それぞれの `python3 -B claude/scripts/test-<名前>.py`（`test-skills-check.py`・`test-skill-usage.py`・`test-trust-audit.py`・`test-settings-home-paths.py`・`test-update-skills.py`・`test-register-mcp.py`）を実行する。`jq` が mise の shim に解決される PATH では `HOME` を変えて実行するテストが失敗するので、新しいシェルで実行する。設定ファイル・シェルスクリプト・Markdown・`.github/` を変更したら、`python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、`git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`、`actionlint` を実行する。これらとフック回帰テストは、PR と main への push で GitHub Actions も実行する。CI は push の後に動くので、ユーザー名を含むパスなどを公開前に防ぐには、push する前に手元で `check-repo.py` を実行する（`git add` 前のファイルも検査する）。それ以外の動作確認はセットアップスクリプトを手動実行して行う。
- Homebrew のパッケージリストの正規版は `bin/.Brewfile`。リポジトリルートの `Brewfile` は `mise run brew:dump` で生成し、`bin/.Brewfile` を最新化するためのベースとして使う。
- `vscode/extensions` は `mise run vscode:ext:list` で生成するため手動編集しない。
- `aws/config` , `aws/credentials` は gitignore 済み。公開リポジトリであるため、AWS CLI 設定も credentials もコミットしない。
- Markdown ファイル名（`.md` を除く部分）は英大文字と `_` のみで構成する（例: `README.md`, `SYNC_BACKUP.md`）。新規作成・リネーム時に適用する。`docs/` 配下は例外とし、グローバル規約の保存パスに従う。
