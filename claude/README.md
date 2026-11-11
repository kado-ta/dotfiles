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
| `hooks/ask-gh-pr-write.sh`     | PreToolUse（Bash） | `gh` の PR 書き込みと `gh api` を、表記ゆれも含めて人間の承認に回す                                                                         |
| `hooks/precompact-context.sh`  | PreCompact         | ブランチ名・未コミットの変更・直近のコミットを、コンテキスト圧縮後も残す情報として Claude に渡す                                            |
| `hooks/herdr-agent-state.sh`   | SessionStart       | herdr 上で起動したセッションの開始を herdr に通知する。herdr が生成・管理するため、直接編集しない                                           |
| `hooks/gh-read-token.sh`       | SessionStart       | sandbox 内の Bash に、作業中のリポジトリの owner 用の読み取り専用トークンを `GH_TOKEN` として渡す                                           |

このほか、入力待ちや応答完了の通知、PR 作成時の URL 表示などのフックを `settings.json` に直接記述している。ステータスライン（`scripts/statusline.sh`）は、カレントディレクトリ・ブランチ・コンテキスト使用率・利用上限の使用率・モデル・effort を表示する。

`validate-command.sh` と `protect-main-branch.sh` は、jq が動かないなどでコマンドを検査できないときもブロックする。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、`mise trust` を実行する。

フックや `cc-safe-push` を変更したら、新しいシェルで回帰テストを実行する（`jq` が mise の shim に解決される PATH では、`HOME` を変えて実行するテストが失敗する）。

```shell
bash claude/hooks/tests/test-protect-main-branch.sh
bash claude/hooks/tests/test-validate-command.sh
bash claude/hooks/tests/test-ask-gh-pr-write.sh
bash claude/hooks/tests/test-gh-read-token.sh
/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py
/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py
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

<a name="cc-safe-pr"></a>

## cc-safe-pr

Claude Code から PR を作成・編集するためのラッパー。`cc-safe-push` と同じ許可リストのリポジトリでは、承認なしで動く。許可リストにないリポジトリでは拒否するので、人間が自分の端末で `gh pr create` を実行する。マージとクローズの機能はない。

> [!NOTE]
> sandbox 内の `gh` は読み取り専用トークンで動き、書き込みのできるトークンには届かない（[sandbox 内の gh](#gh-read-token)）。フックと `ask` ルールはセキュリティ境界ではないが、sandbox 内からの書き込みは GitHub が 403 で拒否する。

<a name="cc-safe-pr-usage"></a>

### 使い方

カレントディレクトリに `.cc-pr-request.json` を書き、そのディレクトリで次のコマンドを単独で実行する。ほかのコマンドと連結すると sandbox の中で動き、監査ログを開けずに拒否される。

```sh
/usr/local/libexec/claude-push/cc-safe-pr create  # または edit
```

```json
{ "version": 1, "op": "create", "head": "feature/x", "title": "fix: …", "body": "…", "base": "main", "draft": false }
{ "version": 1, "op": "edit", "head": "feature/x", "number": 123, "title": "…", "body": "…" }
```

| キー      | create | edit | 内容                                                                 |
| --------- | ------ | ---- | -------------------------------------------------------------------- |
| `version` | 必須   | 必須 | `1`                                                                  |
| `op`      | 必須   | 必須 | コマンドの引数と同じ値                                               |
| `head`    | 必須   | 必須 | 現在のブランチ名。違うと拒否する                                     |
| `title`   | 必須   | 任意 | 制御文字なし、1〜256 文字                                            |
| `body`    | 必須   | 任意 | 65536 文字以下。`edit` では `title` と `body` の少なくとも一方が必要 |
| `base`    | 任意   | なし | 省略するとリポジトリの既定ブランチ                                   |
| `draft`   | 任意   | なし | `true` または `false`                                                |
| `number`  | なし   | 必須 | PR の番号                                                            |

依頼ファイルは 1 回限りで、ラッパーが読むとすぐに消える。拒否や失敗のあとに再実行するときは書き直す。

終了コードは、0 が成功、1 が失敗（変更なし）、2 が拒否、3 が要確認（PR が作成・変更された可能性があり、再実行せずに状態を確認する）。

<a name="cc-safe-pr-policy"></a>

### 拒否する条件

- `cc-safe-push` が拒否する条件（許可リストにない、保護ブランチ、detached HEAD など）
- `create`: ブランチが GitHub にない、ローカルの HEAD と SHA が違う（先に `cc-safe-push` を実行する）、同じ head と base の open な PR がある、リポジトリがアーカイブされている
- `edit`: PR が同じリポジトリのブランチでない（fork）、open でない、現在のブランチの PR でない、自分が作った PR でない
- GitHub が返すリポジトリ名が許可リストの `github` と違う（大文字・小文字も区別する。push は通るのに PR だけ拒否されるときは、許可リストの表記を確認する）

<a name="cc-safe-pr-install"></a>

### インストール

通常のターミナルで行う。`cc-safe-push` がインストール済みであることが前提で、`gh auth login` の認証を使う。

```sh
cd ~/dotfiles
sudo install -o root -g wheel -m 0755 claude/bin/cc-safe-pr /usr/local/libexec/claude-push/cc-safe-pr
# 依頼ファイルをグローバルの ignore に追加する（すでに書かれていれば何もしない）
grep -qxF '.cc-pr-request.json' ~/.config/git/ignore || echo '.cc-pr-request.json' >> ~/.config/git/ignore
```

ラッパーか `cc-safe-push` を変更したら、再度インストールして両方のテストを実行する。`cc-safe-pr` は同じディレクトリの `cc-safe-push` を読み込むので、片方だけ古いと動かないことがある。

アンインストールは、`settings.json` の `cc-safe-pr` の行を消して `sudo rm /usr/local/libexec/claude-push/cc-safe-pr` を実行する。`cc-safe-push` と許可リストには影響しない。

<a name="cc-safe-pr-audit"></a>

### 監査ログ

`~/Library/Logs/cc-safe-pr/audit.jsonl` に、判定と結果を 1 行ずつ記録する。5 MiB を超えると `audit.jsonl.1` に置き換える（1 世代）。トークン、タイトル、本文は記録しない（長さとハッシュのみ）。書き込めないときは送信しない。

ユーザーの権限で書かれるので、改ざんを防ぐものではない。GitHub 側の記録との突合には `github_request_id`（`X-GitHub-Request-Id`）と PR の URL を使う。

<a name="gh-read-token"></a>

## sandbox 内の gh

sandbox 内の Bash からは Keychain を読めない（`sandbox.filesystem.denyRead` に `~/Library/Keychains`）。`gh auth login` で保存した書き込みのできるトークンを使えるのは、sandbox の外で動く `cc-safe-push` と `cc-safe-pr`、人間の端末だけ。

起動元のシェルから引き継いだ `GITHUB_TOKEN`、`GH_ENTERPRISE_TOKEN`、`GITHUB_ENTERPRISE_TOKEN` は、`sandbox.credentials.envVars` の `deny` で sandbox 内から除き、下の 1 行でも消す。`gh` は `GH_TOKEN` が空のときにこれらを使うため。`GH_TOKEN` を `export` したシェルから Claude Code を起動しない（フックが動かなかった場合に残る）。

sandbox 内の `gh` には、`hooks/gh-read-token.sh` が owner ごとの読み取り専用トークンを `GH_TOKEN` として渡す。SessionStart で `CLAUDE_ENV_FILE` に 1 行を追記し、その 1 行が Bash コマンドのたびに、カレントディレクトリの origin の owner に対応するトークンを選ぶ。

| 操作 | 結果 |
| --- | --- |
| 読み取り（`gh pr view`、`gh pr list`、`gh run list` など） | 成功する |
| 書き込み（PR の作成・編集・マージ、Issue の作成など） | 403 で失敗する。許可リストのリポジトリの PR は `cc-safe-pr` で、それ以外は人間が自分の端末で行う |
| トークンを置いていない owner、origin のないディレクトリ | `GH_TOKEN` が空になり未認証になる（private リポジトリは読めない） |

トークンは cwd の origin で選ぶので、`-R` で別の owner のリポジトリを指定しても、その owner のトークンは使われない。

`gh pr checks` は、Fine-grained PAT の制限で CI のチェック結果を読めない可能性がある（CI のあるリポジトリでは未確認）。

<a name="gh-read-token-setup"></a>

### トークンの作成と配置

1. GitHub の Fine-grained tokens で、owner ごとにトークンを作る。権限は Actions、Commit statuses、Contents、Issues、Pull requests を Read-only にする（Metadata は自動で付く）。組織の owner では管理者の承認が必要な場合がある。
2. 1Password に「API 認証情報」として保存し、「秘密参照をコピーする」(`'op://<Vault>/<Item>/credential'`) で参照をコピーする。Vault 名と項目名はこのリポジトリに書かない。
3. 通常のターミナルで配置する。ファイル名の **owner は小文字**にする。

   ```sh
   umask 077; mkdir -p ~/.config/cc-gh-read
   op read 'op://<Vault>/<Item>/credential' > ~/.config/cc-gh-read/<owner>.token
   ```

更新するときは 1〜3 をやり直す。Bash コマンドのたびにファイルを読むので、Claude Code の再起動は要らない。owner を追加するときも、トークンを置くだけでよい。

`settings.json` の変更を戻すと、次のセッションから `GH_TOKEN` は設定されず、sandbox 内の `gh` は Keychain のトークンを使うようになる。
