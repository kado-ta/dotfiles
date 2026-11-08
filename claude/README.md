# claude

Claude Code の設定を管理するディレクトリ。`setup.sh` で `~/.claude/` にシンボリックリンクする。

<a name="setup"></a>

## セットアップ（`setup.sh`）

`setup.sh` は次を行う。

- `settings.json`・`CLAUDE.md`・`rules/`・`mcp.json`・`hooks/`・`scripts/statusline.sh` を `~/.claude/` にリンクする。`~/.claude/hooks/` が実ディレクトリの場合は、削除してからリンクに置き換える。
- `skills/*/` の個人スキルを `~/.claude/skills/` にリンクする（全プロジェクトで使える）。
- プラグイン `superpowers`・`claude-code-setup`・`crit` と、スキル集 [gstack](https://github.com/garrytan/gstack) をインストールする（インストール済みならスキップする）。

`settings.json` のセキュリティ設定は、[【2026年最新版】Claude Codeで行うべきセキュリティ設定 10選 - Qiita](https://qiita.com/miruky/items/51db293a7a7d0d277a5d) を参考にしている。

gstack は `gstack-upgrade` で更新する（`--check` で確認のみ）。

<a name="hooks"></a>

## フック

| ファイル                       | イベント           | 動作                                                                                                                                        |
| ------------------------------ | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `hooks/validate-command.sh`    | PreToolUse（Bash） | `rm -rf` と、本番環境（`prod` / `prd`）を含むコマンドをブロックする。`sf devops` の参照系コマンドと PR 作成は、単独のコマンドに限り許可する |
| `hooks/protect-main-branch.sh` | PreToolUse（Bash） | `main`・`master`・`staging` ブランチへの `git commit` をブロックする                                                                        |
| `hooks/precompact-context.sh`  | PreCompact         | ブランチ名・未コミットの変更・直近のコミットを、コンテキスト圧縮後も残す情報として Claude に渡す                                            |
| `hooks/herdr-agent-state.sh`   | SessionStart       | herdr 上で起動したセッションの開始を herdr に通知する。herdr が生成・管理するため、直接編集しない                                           |

このほか、入力待ちや応答完了の通知、PR 作成時の URL 表示などのフックを `settings.json` に直接記述している。ステータスライン（`scripts/statusline.sh`）は、カレントディレクトリ・ブランチ・コンテキスト使用率・利用上限の使用率・モデル・effort を表示する。

`validate-command.sh` と `protect-main-branch.sh` は、jq が動かないなどでコマンドを検査できないときもブロックする。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、`mise trust` を実行する。

フックや `cc-safe-push` を変更したら、新しいシェルで回帰テストを実行する（`jq` が mise の shim に解決される PATH では、`HOME` を変えて実行するテストが失敗する）。

```shell
bash claude/hooks/tests/test-protect-main-branch.sh
bash claude/hooks/tests/test-validate-command.sh
/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py
```

## cc-safe-push

Claude Code から `git push` するためのラッパー。`settings.json` で `git push` を deny にしているので、Claude はこのラッパーでしか push できない。どのリポジトリのどのブランチに送れるかは、root 所有のラッパーと許可リストで決める。

<a name="cc-safe-push-policy"></a>

### 動作

対象リポジトリに移動して、`/usr/local/libexec/claude-push/cc-safe-push` を引数なし・単独で実行する。現在のブランチを origin の同じ名前のブランチに送る。

| 状況                                                                                                          | 結果                                   |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 許可リストのリポジトリの、保護されていないブランチ                                                            | 確認なしで push する                   |
| 許可リストにないリポジトリ                                                                                    | 拒否する。人間が自分の端末で push する |
| `main`, `master`, `staging`（大文字・小文字を区別しない）                                                     | 拒否する                               |
| 判定できない場合（detached HEAD、origin が `git@github.com:OWNER/REPO.git` の形でない、許可リストの異常など） | 拒否する                               |

終了コードは、0 が成功、1 が push の失敗、2 が拒否。

upstream は設定されないので、PR は `gh pr create --head <branch>` で作る。

<a name="cc-safe-push-install"></a>

### インストール

Claude Code のセッションでは `sudo` を実行できないので、通常のターミナルで行う。

前提:

- Xcode Command Line Tools がインストールされている（`/usr/bin/python3` と `/usr/bin/git` を使う）
- `/usr/bin/git` が `GIT_NO_LAZY_FETCH` に対応している（2.54.0 で確認済み）
- 1Password の SSH Agent を使っている
- `~/.ssh/known_hosts` に github.com が登録されている
- 許可するリポジトリの origin が `git@github.com:OWNER/REPO.git` の形になっている
- 許可するリポジトリが shallow clone でない（push が失敗することがある）

1. [許可リスト](#cc-safe-push-allowlist)を作る。

   ```sh
   ${EDITOR:-vi} /tmp/allowlist.jsonc
   ```

2. ラッパーと許可リストを root 所有で配置する。

   ```sh
   cd ~/dotfiles
   sudo install -d -o root -g wheel -m 0755 /usr/local/libexec/claude-push /usr/local/etc/claude-push
   sudo install -o root -g wheel -m 0755 claude/bin/cc-safe-push /usr/local/libexec/claude-push/cc-safe-push
   sudo install -o root -g wheel -m 0644 /tmp/allowlist.jsonc /usr/local/etc/claude-push/allowlist.jsonc
   rm /tmp/allowlist.jsonc
   ```

| 配置先                                        | 役割                         |
| --------------------------------------------- | ---------------------------- |
| `/usr/local/libexec/claude-push/cc-safe-push` | ラッパー                     |
| `/usr/local/etc/claude-push/allowlist.jsonc`  | 許可リスト。Git の管理対象外 |

Claude は実行ユーザーの権限で動くので、root 所有にすると書き換えられない。ラッパーは、許可リストとその親ディレクトリが root 所有でないときや、グループやほかのユーザーが書き込めるときは、すべて拒否する。

`settings.json` には登録済みなので、`setup.sh` でリンクしていれば追加の設定は要らない。

<a name="cc-safe-push-allowlist"></a>

### 許可リストの書き方

```jsonc
// Claude Code で git push を承認なしで実行するための許可リスト
// /usr/local/libexec/claude-push/cc-safe-push が参照する。
//
// allowList 配列内には、許可対象として下記のキーを持つオブジェクトを作成する。
// - gitCommonDir: 許可対象リポジトリクローン内 .git ディレクトリの **絶対パス** を指定する。
//     - 絶対パス取得コマンド: git rev-parse --path-format=absolute --git-common-dir
// - github: 許可対象 GitHub のリポジトリを owner/repo 形式で指定する。
//
// ※ 行全体のコメントだけを書ける。行末のコメントと /* */ は書けず、すべての push が拒否される。
// ※ JSON と同じく、最後の要素のあとにカンマは書けない。
{
  "version": 1,
  "allowList": [
    // リポジトリの説明、確認なしプッシュを許可する理由など
    {
      "gitCommonDir": "/Users/<user>/src/example/.git",
      "github": "<owner>/<repo>"
    }
  ]
}
```

| キー           | 値                                                                                                       | 調べ方                                                  |
| -------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `gitCommonDir` | クローンの `.git` の絶対パス。worktree からでも同じ値になる                                              | `git rev-parse --path-format=absolute --git-common-dir` |
| `github`       | `OWNER/REPO` だけを、origin と大文字・小文字まで同じに書く。URL 全体を書くと、すべての push が拒否される | `git remote get-url origin` の `OWNER/REPO` の部分      |

コメントは行全体の `//` だけを書ける。行末のコメント、`/* */`、末尾のカンマを書くと、すべての push が拒否される。

<a name="cc-safe-push-update"></a>

### 更新するとき

- ラッパーを変更したら、再度インストールする。リポジトリのファイルを直しただけでは、動作は変わらない。

  ```sh
  sudo install -o root -g wheel -m 0755 claude/bin/cc-safe-push /usr/local/libexec/claude-push/cc-safe-push
  ```

- 許可リストは `sudo` で編集する。

  ```sh
  sudo vi /usr/local/etc/claude-push/allowlist.jsonc
  ```
