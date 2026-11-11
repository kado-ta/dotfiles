---
status: done
created: 2026-11-09
---

# R1 の解消: sandbox から書き込み可能な GitHub トークンを遮断する（Phase 2）

根拠の表記: 【実測】このセッションで確認 / 【公式】公式ドキュメント / 【推測】 / 【未確認】

## Context

Phase 1（`cc-safe-pr`、PR #4）の残余リスク R1 を解消する。`gh` の `repo` スコープのトークンが sandbox 内から Keychain 経由で読めるので【実測】、Claude が意図的に別の手段を使えば、マージを含む GitHub API を承認なしで呼べる。

**完了の定義**: sandbox 内のプロセスが、書き込み可能な GitHub の認証情報を読むことも使うこともできない。`cc-safe-push` と `cc-safe-pr` は引き続き動き、sandbox 内の `gh` の読み取りも動く。

**ユーザーの決定（2026-11-09）**:

- sandbox 内の `gh` の読み取りは、owner ごとの読み取り専用トークンで認証する。
- 未許可リポジトリの PR 作成など、人間が判断する書き込みは、`git push` と同じく人間が自分の端末で実行する。

## 調査で判明した前提

| 事実 | 根拠 | 影響 |
| --- | --- | --- |
| `sandbox.credentials` のマスクは値を隠すが、置換先の指定はホスト単位で、メソッドやパスで限定できない | 【公式】 | 書き込みを止められないので採用しない |
| `excludedCommands` の gh 読み取りパターンは、パイプや連結に当たらない。gstack の `gh` の約 9 割はこの形式（表の罫線を含む粗い値） | 【公式】【実測】 | 読み取りを sandbox 外にする案は採用しない |
| ルールセットは `required_approving_review_count: 0` | 【実測】 | GitHub 側の強制にはなっていない |
| Fine-grained PAT は 1 owner に 1 個。組織は既定で管理者承認が必要 | 【公式】 | `kado-ta` と 組織 に別のトークンが要る |
| `CLAUDE_ENV_FILE` は各 Bash コマンドの前にシェルコードとして実行される | 【公式】 | cwd に応じて毎回トークンを選べる |
| sandbox の定義に `com.apple.SecurityServer` の mach-lookup 許可が組み込まれている | 【実測】 | `denyRead` だけで Keychain を遮断できるかは【未確認】 |
| `gh` の認証情報は keyring のみで `hosts.yml` に値がない。`~/.netrc` と `~/.git-credentials` はない。`credential.helper` は `osxkeychain` | 【実測】 | 遮断の対象は Keychain に絞れる |

## 設計

```text
sandbox 内の Bash ─ 各コマンドの前に CLAUDE_ENV_FILE の 1 行を実行
                     └─ origin の owner から ~/.config/cc-gh-read/<owner>.token を選び GH_TOKEN に設定
                        トークンがなければ空 → Keychain も読めないので未認証（fail closed）
sandbox 内の Keychain ─ denyRead で遮断
cc-safe-push / cc-safe-pr ─ sandbox 外。環境変数を引き継がないので従来どおり（変更なし）
人間の端末 ─ 変更なし（GH_TOKEN は Claude Code のサブプロセスだけに設定）
```

**トークン**: owner ごとの Fine-grained PAT。権限は Metadata、Contents、Pull requests、Issues、Actions、Commit statuses の read のみ。正本は 1Password に置き、人間が `op read` で `~/.config/cc-gh-read/<owner>.token`（ファイル 0600、ディレクトリ 0700）に配置する。読み取り専用なので sandbox から読めることは許容する。

```sh
umask 077; mkdir -p ~/.config/cc-gh-read
op read 'op://<Vault>/<Item>/credential' > ~/.config/cc-gh-read/<owner>.token
```

**認証情報の使い分け**: 読み取り専用トークンを使うのは sandbox 内の `gh` だけで、PR の作成・編集には使わない。

| 操作 | 実行する場所 | 使う認証情報 |
| --- | --- | --- |
| sandbox 内の `gh`（読み取り） | sandbox 内 | 読み取り専用の Fine-grained PAT |
| PR の作成・編集（許可リポジトリ） | `cc-safe-pr`（sandbox 外） | 既存の `gh auth login` のトークン（`repo`、Keychain）。変更なし |
| push（許可リポジトリ） | `cc-safe-push`（sandbox 外） | 1Password SSH Agent。変更なし |
| 未許可リポジトリの PR 作成、マージなど | 人間の端末 | 既存の `gh auth login` のトークン |

`cc-safe-pr` は環境変数を引き継がず、sandbox の外で `gh auth token` を実行して Keychain からトークンを取得するので、`denyRead` と `GH_TOKEN` の影響を受けない。実行できるのは許可リポジトリの create / edit だけで、トークン自体は `repo` のまま。PR 専用の PAT への置き換えは今回の範囲外とする（root 所有のラッパーが権限を絞っているので、R1 の解消には不要）。

**トークンの置き場所（1Password CLI との比較）**: トークンは実行時に sandbox 内の `gh` に渡す必要があるので、どの方式でも実行中は平文になる。違いは、平文がどこに、どれだけの期間残るかである。

| 方式 | 平文が残る場所 | 人間の操作 | 非対話のセッション | 判定 |
| --- | --- | --- | --- | --- |
| 1Password を正本にしてファイルへ配置 | `~/.config/cc-gh-read/`（0600）に常時 | 作成・更新時のみ `op read` | 動く | **採用** |
| SessionStart フックで `op read` | セッションの env file（保存場所は公式に記載なし） | セッションの開始や再開のたびに 1Password の承認が必要になる見込み【未確認】 | 承認できず未認証 | 代替案（常時の平文ファイルを避けたい場合） |
| Bash コマンドごとに `op read` | なし | — | — | 不可。sandbox 内の `op` はデスクトップアプリに接続できない【実測】 |

採用の理由: 読み取り専用で、いずれにせよ sandbox から読める値なので、毎回の承認の負担に見合う効果が小さい。正本を 1Password に置くことで、作成と更新の管理は一元化できる。

フックは sandbox の外で動く【公式】ので、代替案は実現できる。`network.allowUnixSockets` で sandbox から 1Password に接続させる案は、sandbox から Vault 全体に手が届くので採用しない。

**1Password から Claude Code へトークンを渡す流れ（採用する方式）**:

| # | 実行する人 | 内容 |
| --- | --- | --- |
| 1 | 人間 | GitHub で owner ごとに読み取り専用の Fine-grained PAT を作る |
| 2 | 人間 | 1Password に owner ごとの項目として保存し、1Password アプリの「Copy Secret Reference」で `op://...` の参照を取得する（Vault 名と項目名は公開リポジトリに書かない） |
| 3 | 人間（通常のターミナル） | `op read` で `~/.config/cc-gh-read/<owner>.token` に書き出す（上記のコマンド。`<owner>` は小文字にそろえる）。実行時に 1Password の承認が求められる |
| 4 | Claude Code（SessionStart フック） | `gh-read-token.sh install` が `CLAUDE_ENV_FILE` に `export GH_TOKEN=...` の 1 行を追記する。ファイルにはトークンの値ではなく、取得するコマンドだけを書く |
| 5 | Claude Code（各 Bash コマンドの前） | その 1 行が実行され、`gh-read-token.sh` が origin の owner に対応するファイルを読んで `GH_TOKEN` に設定する |
| 6 | `gh`（sandbox 内） | `GH_TOKEN` を最優先で使う【公式】 |

`op` を実行するのは手順 3 の人間だけで、Claude Code の実行中は 1Password にアクセスしない。更新するときは手順 1〜3 をやり直す。ファイルは Bash コマンドのたびに読むので、再起動は要らない。

トークンの値は会話には出ないが、Bash の環境変数なので、Claude が `env` を実行すれば見える。読み取り専用なので許容する。

**代替案（SessionStart で `op read` する場合）の受け渡し**: 手順 3 を省き、手順 4 のフック（sandbox の外で動く）で次を実行する。`CLAUDE_ENV_FILE` にトークンの値そのものが書かれ、セッション中はそのファイルに平文で残る。

```sh
token="$(op read 'op://<Vault>/<Item>/credential')" && printf 'export CC_GH_READ_<OWNER>=%q\n' "$token" >> "$CLAUDE_ENV_FILE"
```

owner ごとに変数を分けて全 owner 分を読み込み、手順 5 では origin の owner に対応する変数を `GH_TOKEN` に設定する。承認されなければ変数が設定されず、未認証になる（fail closed）。

**新規 `claude/hooks/gh-read-token.sh`**:

- 引数 `install`（SessionStart から実行）: `CLAUDE_ENV_FILE` に次の 1 行を追記する。すでにあれば何もしない。

  ```sh
  export GH_TOKEN="$(/bin/bash "$HOME/.claude/hooks/gh-read-token.sh" 2>/dev/null)"
  ```

- 引数なし: `git config --get remote.origin.url` から owner を取り、`[A-Za-z0-9-]+` に一致するときだけ、対応するトークンファイルの内容を出力する。どの失敗でも無出力で exit 0 にする（各 Bash コマンドを止めないため）。

**`claude/settings.json` の差分**:

```diff
 "deny": [
+  "Read(~/Library/Keychains/**)",
+  "Edit(~/.config/cc-gh-read/**)",
 "SessionStart": [
+  { "matcher": "^(startup|resume|clear|compact|fork)$", "hooks": [{ "type": "command",
+      "command": "/bin/bash ~/.claude/hooks/gh-read-token.sh install", "timeout": 10 }] },
 "sandbox": { "filesystem": { "denyRead": [
+  "~/Library/Keychains",
```

`Bash(gh pr create*)` などの `ask` とフック `ask-gh-pr-write.sh` は残す。書き込みは 403 で失敗するが、無駄な実行の前に人間が気づける。

**ドキュメント**: `claude/CLAUDE.md` と `commit-staged-pr` スキルの未許可リポジトリの手順を「`gh pr create` のコマンドを提示して人間が実行する」に変更する。`CLAUDE.md` と `claude/README.md` の「セキュリティ境界ではない」の記述を実態に合わせ、トークンの作成・更新の手順を追記する。作業文書は `docs/work/20261109_gh-token-isolation/`（前回の `design.md` は完了済みなので編集しない）。

## 実装計画

| # | step | verify |
| --- | --- | --- |
| 0 | ユーザーが検証 S0 を実行（下記） | 下表のとおり。**Keychain を遮断できなければ停止して再計画する** |
| 1 | ユーザーが PAT を作成して検証 S1 を実行（下記） | 読み取りが成功し、書き込みが 403。**`gh pr checks` が動かなければ相談する** |
| 2 | ブランチ `feat/gh-read-token` を作成。`test-gh-read-token.sh` を先に書く | 失敗する |
| 3 | `gh-read-token.sh` を実装 | テストが通る |
| 4 | `settings.json` とドキュメントを更新 | JSON が有効、内部リンクが解決 |
| 5 | 全テストを実行 | 既存 5 テストと新規テストが成功 |
| 6 | ユーザーが Codex レビューを実行、採否を整理して修正 | Critical / High なし |
| 7 | ユーザーが通常のターミナルでトークンを配置し、新しいセッションで検証 V | 下表のとおり |
| 8 | コミットして `cc-safe-push`、`cc-safe-pr create` | PR 作成。マージはユーザー |

**S0: Keychain の遮断（通常のターミナル。永続的な変更なし）**

```sh
printf '%s' '{"sandbox":{"filesystem":{"denyRead":["~/Library/Keychains"]}},"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"[ -n \"$CLAUDE_ENV_FILE\" ] && echo \"export CC_P2_OK=1\" >> \"$CLAUDE_ENV_FILE\""}]}]}}' > /tmp/p2-spike.json
cd ~/dotfiles && claude --settings /tmp/p2-spike.json
```

そのセッションで 1 つずつ実行を依頼する。`security` は `-w` を付けないので、パスワードは出力されない。

| コマンド | 期待 |
| --- | --- |
| `gh auth status` | 未ログインまたは失敗 |
| `/usr/bin/security find-generic-password -s gh:github.com` | 失敗 |
| `/usr/bin/security find-internet-password -s github.com` | 失敗 |
| `SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock" /usr/bin/ssh-add -l` | 失敗 |
| `echo "$CC_P2_OK"` | `1`（`CLAUDE_ENV_FILE` が sandbox 内に効く） |

**S1: PAT の検証（通常のターミナル）**

`PR番号` には CI のある PR を指定する。最後のコマンドは同じタイトルでの PATCH なので、万一成功しても内容は変わらない。

```sh
export GH_TOKEN="$(< ~/.config/cc-gh-read/<owner>.token)"
gh pr view PR番号 -R OWNER/REPO --json number,state
gh pr checks PR番号 -R OWNER/REPO
gh pr diff PR番号 -R OWNER/REPO --name-only
gh run list -R OWNER/REPO --limit 1
gh issue list -R OWNER/REPO --limit 1
gh api -X PATCH repos/OWNER/REPO/pulls/PR番号 -f title="$(gh pr view PR番号 -R OWNER/REPO --json title -q .title)"  # 403 が期待
unset GH_TOKEN
```

**V: 新しいセッションでの検証（Sandbox ON + auto）**

| # | 手順 | 期待 |
| --- | --- | --- |
| V1 | `gh auth status`、`gh pr view`、パイプ付きの `gh pr list ... \| jq` | 読み取り専用トークンで成功 |
| V2 | `security find-generic-password -s gh:github.com`（`-w` なし） | 失敗 |
| V3 | `gh pr close` などの書き込みを承認して実行 | 403 で失敗 |
| V4 | 別 owner のリポジトリに `cd` して `gh pr view` | その owner のトークンで成功 |
| V5 | トークンのない owner のリポジトリで `gh pr view` | 未認証で失敗（fail closed） |
| V6 | `cc-safe-push` と `cc-safe-pr create` / `edit` | 従来どおり成功 |
| V7 | 通常のターミナルの `gh` | 影響なし |

**ロールバック**: `settings.json` の差分を戻す。次回のセッションから `GH_TOKEN` は設定されず、sandbox 内の `gh` は Keychain に戻る。`~/.config/cc-gh-read/` は残っていても影響しない。

## 残余リスクと未確認事項

| 内容 | 扱い |
| --- | --- |
| 読み取りトークンは sandbox から読める（private リポジトリの読み取りと、許可済みドメインへの持ち出しは現状と同じ） | 許容（読み取りの範囲に限られる） |
| 読み取りトークンは平文のファイルとして常時残る（同じユーザーのプロセスやバックアップから読める） | 許容。避けたい場合は SessionStart で `op read` する代替案に切り替える |
| `cc-safe-pr` は引き続き `repo` スコープのトークンを使う | 許容（sandbox からは届かず、ラッパーが操作を create / edit に限定する） |
| `gh pr checks` は Fine-grained PAT で動かない可能性がある（公式の制限に Checks API がある） | S1 で確認 |
| `CLAUDE_ENV_FILE` の sandbox 内での動作、resume 時の扱いは公式に記載がない | S0、V で確認。`install` は重複を防ぐ |
| PAT の期限（組織は最大 366 日）と owner の追加 | README に手順を書く |
| `cd` と連結したコマンドは、移動前の cwd でトークンを選ぶ | 許容（別 owner に移るときだけ未認証や別トークンになる） |
| ファイルに保存された GitHub 以外のサービスの認証情報は調査対象外 | 範囲外 |

## Codex レビューの結果（1 回目 / 上限 5 回）

判定: High 1。origin の解析、owner の検証、ラッパーの認証への影響は問題なしと評価された。

| 重大度 | 指摘 | 判定 | 対応 |
| --- | --- | --- | --- |
| High | 起動元の `GITHUB_TOKEN` が sandbox に残り、`GH_TOKEN` が空のとき `gh` がそれを使う | **採用** | `sandbox.credentials.envVars` の `deny` で `GITHUB_TOKEN`、`GH_ENTERPRISE_TOKEN`、`GITHUB_ENTERPRISE_TOKEN` を除き、環境ファイルの 1 行でも `unset` する。回帰テストを追加 |
| — | 起動元の `GH_TOKEN` は、フックが動かなかった場合に残る | **記録のみ** | `deny` にすると、環境ファイルとの実行順序次第で読み取りトークンも消えるため。README に「`GH_TOKEN` を export したシェルから起動しない」と記載 |
| — | トークンファイルの親ディレクトリのリンクや差し替え | **不採用** | `~/.config` は sandbox から書けず、攻撃の前提が成り立たない |
