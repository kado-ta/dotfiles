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

`claude/setup.sh` がメインのエントリーポイント。Claude Code のセッション内と IDE の統合ターミナルでは実行を拒否する（セッション中にリンクを張り直すと、Claude Code のサンドボックスがリンクを削除し、deny ルール・フック・サンドボックスが無効になるため）。通常のターミナルで、すべてのセッションを閉じてから実行する。

`claude/`・`.claude/`・`.github/scripts/` を扱うときは、PR と Crit のラッパーと sandbox 設定の設計理由が [.claude/rules/CLAUDE_CONFIG.md](.claude/rules/CLAUDE_CONFIG.md) から読み込まれる。

### フック

`hooks/herdr-agent-state.sh` は herdr が生成・上書きするファイルのため編集しない。

`validate-command.sh` と `protect-main-branch.sh` は、jq や git が動かないなどでコマンドを検査できないときもブロックする（fail closed）。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、`mise trust` を実行する。

### git push

Claude からの push は、`claude/bin/cc-safe-push` を root 所有でインストールしたラッパーだけで行う。`settings.json` は、引数なしの完全一致だけを `permissions.allow` と `sandbox.excludedCommands` に入れ、`git push` を deny にしている。判定はすべてラッパーで行い、フックには依存しない。

push は、元のリポジトリの設定とフックを読まないように、macOS のユーザー専用の一時ディレクトリに作った空のリポジトリから行う（作業ディレクトリと `$TMPDIR` は sandbox から書けるので使わない）。元のリポジトリには書き込まないので、upstream は設定されない。

ラッパーと許可リストは、Claude が書き換えられないように root 所有にする。ラッパーを変更したら、再度インストールする。インストール手順と許可リストの書き方は、[claude/README.md](claude/README.md#cc-safe-push-install) を参照する。

<a name="sandbox-prohibitions"></a>

### sandbox と権限の禁止事項

- `sandbox.filesystem.allowWrite` に `~/.crit` 配下を入れない。
- `sandbox.network` の `allowUnixSockets`・`allowAllUnixSockets`・`allowLocalBinding` を設定しない（`check-repo.py` の `push-permissions` が失敗する）。
- Colima（Lima）の VM に入る鍵（`~/.colima/_lima/_config`）を `denyRead` から外さない。

## 規約

- テストは `claude/hooks/tests/` のフック回帰テストと、`.github/scripts/` のリポジトリの検査。フックを変更したら `bash claude/hooks/tests/test-protect-main-branch.sh`、`bash claude/hooks/tests/test-validate-command.sh`、`bash claude/hooks/tests/test-ask-gh-pr-write.sh`、`bash claude/hooks/tests/test-gh-read-token.sh` を実行する。`claude/bin/cc-safe-push` か `claude/bin/cc-safe-pr` を変更したら `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` と `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` を実行する。`claude/bin/cc-crit` か `claude/bin/cc-crit.sb` を変更したら `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` を実行し、sandbox の外で `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py` を実行する（Claude Code の sandbox の中ではスキップされる）。`jq` が mise の shim に解決される PATH では `HOME` を変えて実行するテストが失敗するので、新しいシェルで実行する。設定ファイル・シェルスクリプト・Markdown・`.github/` を変更したら、`python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、`git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`、`actionlint` を実行する。これらとフック回帰テストは、PR と main への push で GitHub Actions も実行する。CI は push の後に動くので、ユーザー名を含むパスなどを公開前に防ぐには、push する前に手元で `check-repo.py` を実行する（`git add` 前のファイルも検査する）。それ以外の動作確認はセットアップスクリプトを手動実行して行う。
- Homebrew のパッケージリストの正規版は `bin/.Brewfile`。リポジトリルートの `Brewfile` は `mise run brew:dump` で生成し、`bin/.Brewfile` を最新化するためのベースとして使う。
- `vscode/extensions` は `mise run vscode:ext:list` で生成するため手動編集しない。
- `aws/config` , `aws/credentials` は gitignore 済み。公開リポジトリであるため、AWS CLI 設定も credentials もコミットしない。
- Markdown ファイル名（`.md` を除く部分）は英大文字と `_` のみで構成する（例: `README.md`, `SYNC_BACKUP.md`）。新規作成・リネーム時に適用する。`docs/` 配下は例外とし、グローバル規約の保存パスに従う。
