# claude

Claude Code の設定を管理するディレクトリ。`setup.sh` で `~/.claude/` にシンボリックリンクする。

<a name="setup"></a>

## セットアップ（`setup.sh`）

`setup.sh` は次を行う。

- `settings.json`・`CLAUDE.md`・`rules/`・`hooks/`・`scripts/statusline.sh` を `~/.claude/` にリンクする。`~/.claude/hooks/` が実ディレクトリの場合は、削除してからリンクに置き換える。
- `skills/*/` の個人スキルを `~/.claude/skills/` にリンクする（全プロジェクトで使える）。
- プラグイン `superpowers`・`claude-code-setup`・`ruby-lsp`・`crit`・`understand-anything`・`pstack` と、スキル集 [gstack](https://github.com/garrytan/gstack) をインストールする（インストール済みならスキップする）。`ruby-lsp` プラグインは LSP サーバーを含まないので、`ruby-lsp` gem を別途入れて PATH に通す。
- `mcp/*.json` の MCP サーバーを、`scripts/register-mcp.sh` で user スコープに登録する（登録済みなら置き換える。[MCP サーバー](#mcp)）。ネットワークや npm が使えずに失敗したときは、警告を出して先に進む。

`settings.json` のセキュリティ設定は、[【2026年最新版】Claude Codeで行うべきセキュリティ設定 10選 - Qiita](https://qiita.com/miruky/items/51db293a7a7d0d277a5d) を参考にしている。

gstack・プラグイン・crit の CLI は、sandbox の外で `claude/scripts/update-skills.sh` を実行してまとめて更新する（Claude Code からは `! /bin/bash ~/dotfiles/claude/scripts/update-skills.sh`、端末では `mise run claude:update` でもよい。gstack の確認だけなら zsh の `gstack-upgrade --check`）。手順は [SKILL_INVENTORY.md の「更新したときの見直し」](SKILL_INVENTORY.md#upgrade) にある。

pstack はサードパーティのマーケットプレイスなので自動更新されない。`update-skills.sh` か `claude plugin update pstack@cursor-plugins` で更新し、Claude Code を再起動する前に、hooks が増えていないか、スキルの一覧と依存が変わっていないかを確かめる（`/sync-skill-docs`）。`settings.json` の `permissions.deny` は、モデルから起動できる `setup-pstack` と、使わないエージェント 2 つを止めている。ほかの使わないスキルはモデルから起動できず、deny ではユーザーのスラッシュコマンドを止められないので、方針として使わない。スキルの分類は [pstack の導入の plan](../docs/work/20261114_pstack-skill-routing/plan.md#decisions) にある。

スキルの役割分担は、次の 3 つに分けて書いている。プラグインやスキルを更新したら、棚卸しの「更新したときの見直し」に従って 3 つを直す。

- [rules/SKILL_ROUTING.md](rules/SKILL_ROUTING.md): Claude がスキルを選ぶときの規則。全プロジェクトの全セッションで読み込まれる。
- [SKILL_INVENTORY.md](SKILL_INVENTORY.md): 全スキルの棚卸し（状態・制約・重複の裁定・更新したときの見直し・規則の効果の確認）。
- [SKILL_CHEATSHEET.md](SKILL_CHEATSHEET.md): タスク別の早見表（人間向け）。

<a name="hooks"></a>

## フック

| ファイル                       | イベント           | 動作                                                                                                                                                                                                                          |
| ------------------------------ | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hooks/validate-command.sh`    | PreToolUse（Bash） | `rm -rf` と、本番環境（`prod` / `prd`）を含むコマンドをブロックする。`sf devops` の参照系コマンドと PR 作成は、単独のコマンドに限り許可する。`cc-safe-push` / `cc-safe-pr` / `cc-crit` は、前後にコマンドや引数を付けた実行をブロックする |
| `hooks/protect-main-branch.sh` | PreToolUse（Bash） | `main`・`master`・`staging` ブランチへの `git commit` をブロックする                                                                                                                                                          |
| `hooks/ask-gh-pr-write.sh`     | PreToolUse（Bash） | `gh` の PR 書き込みと `gh api` を、表記ゆれも含めて人間の承認に回す                                                                                                                                                           |
| `hooks/guard-additional-dirs.sh` | PreToolUse（Edit・Write・MultiEdit・NotebookEdit） | `~/.gstack/projects`（`additionalDirectories`）が symlink に差し替えられているあいだ、Edit・Write 系のツールをすべてブロックする |
| `hooks/guard-playwright-mcp.sh` | PreToolUse（`mcp__playwright__.*`） | Playwright MCP の呼び出しのうち、ローカルのファイルを指す `filename`・`paths` 引数を含むものと、`url` が `file:` で始まるもの、Crit のポート（47800〜47819）を指すものをブロックする。入力を検査できないときもブロックする |
| `hooks/precompact-context.sh`  | PreCompact         | ブランチ名・未コミットの変更・直近のコミットを、コンテキスト圧縮後も残す情報として Claude に渡す                                                                                                                              |
| `hooks/herdr-agent-state.sh`   | SessionStart       | herdr 上で起動したセッションの開始を herdr に通知する。herdr が生成・管理するため、直接編集しない                                                                                                                             |
| `hooks/gh-read-token.sh`       | SessionStart       | sandbox 内の Bash に、作業中のリポジトリの owner 用の読み取り専用トークンを `GH_TOKEN` として渡す                                                                                                                             |

このほか、入力待ちや応答完了の通知、PR 作成時の URL 表示などのフックを `settings.json` に直接記述している。ステータスライン（`scripts/statusline.sh`）は、カレントディレクトリ・ブランチ・コンテキスト使用率・利用上限の使用率・モデル・effort を表示する。

`validate-command.sh` と `protect-main-branch.sh` は、jq が動かないなどでコマンドを検査できないときもブロックする。この状態では Bash ツールがすべて止まるので、メッセージに従って Claude Code を再起動するか、人間が mise の設定の全体を確かめてから `mise trust <ファイル>` を実行する。

フックや `cc-safe-push` を変更したら、新しいシェルで回帰テストを実行する（`jq` が mise の shim に解決される PATH では、`HOME` を変えて実行するテストが失敗する）。

```shell
bash claude/hooks/tests/test-protect-main-branch.sh
bash claude/hooks/tests/test-validate-command.sh
bash claude/hooks/tests/test-ask-gh-pr-write.sh
bash claude/hooks/tests/test-gh-read-token.sh
bash claude/hooks/tests/test-guard-additional-dirs.sh
bash claude/hooks/tests/test-guard-playwright-mcp.sh
/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py
/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py
```

PR と main への push では、GitHub Actions が macOS の `/bin/bash` と `/usr/bin/python3` で同じテストを実行する。

<a name="mcp"></a>

## MCP サーバー

`mcp/<name>.json` の定義を、`scripts/register-mcp.sh` が Claude Code の user スコープに `<name>` で登録する（`setup.sh` からも呼ばれる）。同じ名前の user スコープの登録を消してから足すので、何度実行してもよく、定義を変えれば置き換わる。`~/.claude.json` は状態や認証情報も持つので、直接編集・リンク・コミットしない。

定義の `npmPackage` は、`register-mcp.sh` が `~/.local/share/claude-mcp/<name>` に `npm install --ignore-scripts` で入れ、登録する定義からは外す。実行時に npx を使わないのは、npx が作業ディレクトリ（sandbox から書けるプロジェクト）の `node_modules`・`node_modules/.bin`・`.npmrc` を使い、そこに置かれたコードが sandbox の外で動くため。入れる場所は sandbox から書けないので、`sandbox.filesystem.allowWrite` に入れない。

定義の `${HOME}`・`${NODE_BIN}`（mise のグローバル設定の Node.js の `bin`）・`${PACKAGE_DIR}`（上の入れる場所）は、登録するときに実際のパスに置き換える。公開リポジトリにユーザー名を入れないためと、端末以外から起動したときの PATH や、プロジェクトの mise の設定（信頼していないと shim が失敗する）に左右されないようにするため。ほかの `${VAR:-default}` は、Claude Code がサーバーの起動時に展開する。Node.js を更新したら、`register-mcp.sh` を再実行する。

`~/.claude.json` と `~/.local/share/claude-mcp` に書くので、sandbox の外で実行する。通常の端末で `/bin/bash ~/dotfiles/claude/scripts/register-mcp.sh` を実行する。Claude Code のプロンプトの `!` は、セッションによっては sandbox の中で動き、失敗する（2026-11-19 に観測）。登録したサーバーは、次に始めたセッションから使える。

<a name="playwright-mcp"></a>

### Playwright MCP

[Playwright MCP](https://github.com/microsoft/playwright-mcp) を `playwright` で登録する。使い分けは `CLAUDE.md` の Tools 節にある。経緯と受け入れたリスクは [plan](../docs/work/20261118_playwright-mcp/plan.md#decisions) にある。

| 項目 | 値 | 理由 |
| --- | --- | --- |
| 版 | `npmPackage` で `@playwright/mcp@0.0.85` に固定 | `@latest` では、ツールが増えたこと（ファイルを読み書きする引数など）に気づけない。依存の `playwright`・`playwright-core` も完全に固定した版 |
| `command`・`args` の先頭 | `${NODE_BIN}/node` で `${PACKAGE_DIR}/node_modules/@playwright/mcp/cli.js` を起動 | npx を使わない（上記）。ネットワークも要らない |
| `--isolated` | プロファイルをメモリに置く | ログイン状態を残さない。並行したセッションでプロファイルがぶつからない |
| `--browser chrome` | インストール済みの Google Chrome | ダウンロードが要らない。Chrome の自動更新でセキュリティ修正が入る。既定値と同じだが、版を上げて既定が変わったときに気づけるよう明示する |
| `--output-dir` | `~/Library/Caches/playwright-mcp` | どのリポジトリにも出力しない。sandbox から書けない場所なので、symlink で出力先を向け替えられない |
| `--no-webmcp` | ページが登録するツールを使わない | 説明をページが決めたツールが、Claude のツールの一覧に入るのを防ぐ。今の用途では使わない |
| `--blocked-origins` | ポート 47800〜47819（`*:47800;…;*:47819`） | cc-crit の Crit の画面を開かせない。JS やリンクでの移動も止める（リダイレクトは止まらない） |
| `PLAYWRIGHT_MCP_HEADLESS` | 既定は `true` | ウィンドウを出さない。`--headless` 引数は環境変数より優先されて切り替えられなくなるので使わない |
| `env.PATH` | mise のグローバル設定の Node.js | 上の `${NODE_BIN}` の理由 |

MCP サーバーは sandbox の外で、ユーザーの権限で動く。sandbox の denyWrite・denyRead、Edit・Write の規則、ネットワークのプロキシは効かない。そのため、次を止めている。定義（`mcp/playwright.json`）があるあいだは、`check-repo.py` の `playwright-mcp` が、これらがあることを確かめる。

- `settings.json` の `permissions.deny`: `mcp__playwright__browser_run_code_unsafe`（Node のプロセスで任意のコードが動く。オプションでは無効にできない）と `mcp__playwright__browser_file_upload`（プロジェクトのファイルをページに送れる）。
- フック `hooks/guard-playwright-mcp.sh`: `filename` 引数（相対パスはプロジェクトのルートから解決され、プロジェクトの中のどこにでも書ける）と、`paths` 引数（`browser_drop` などがローカルのファイルをページに渡す）。`browser_drop` は `data`（テキスト）なら使える。`url` が Crit のポートを指す呼び出しも止める（ブラウザは localhost に届くので、開けば人間の承認を偽造できる）。`url` が `file:` で始まる呼び出しも止める（Playwright MCP の `file:` の拒否は、Node が解析できる URL にしか効かない）。
- `settings.json` の `sandbox.filesystem.denyRead` の `~/.crit` と `permissions.deny` の `Read(~/.crit/**)`: cc-crit 以外の crit（プラグインの自動プランレビュー、端末の crit）はランダムなポートで待ち受け、そのポートを `~/.crit/sessions` に書く。読めると、モデルがポートを知って開き、承認を偽造できる。`~/.crit` を読み書きする crit は sandbox の外で動くので、影響しない。ポートを端から試して見つける経路は残る。
- `settings.json` の `disabledMcpjsonServers` の `playwright`: プロジェクトの `.mcp.json` に同じ名前のサーバーがあると、user スコープの定義より優先され、上の起動オプションが外れるため。`claude mcp add`（既定は local スコープ）でも `playwright` を登録しない。別の名前で Playwright を起動するプロジェクトのサーバーは、deny もフックも効かないので承認しない。
- `check-repo.py` は、`mcp/playwright.json` 以外の定義に `playwright` が含まれていれば失敗する（`playwright`・`playwright-core` の CLI の `mcp` サブコマンドでも同じサーバーが動くため）。deny・フック・検査が、ツール名 `mcp__playwright__*` に結び付いているため。

<a name="playwright-mcp-install"></a>

#### 導入

1. Google Chrome を入れておく。
2. `register-mcp.sh` を実行する（上記）。`~/.local/share/claude-mcp/playwright` に `@playwright/mcp` を入れるので、ネットワークが要る。
3. `claude mcp get playwright` で、Scope が User config で、版とオプションが定義どおりかを確かめる。`claude mcp list` で接続を確かめる。

<a name="playwright-mcp-headed"></a>

#### ブラウザのウィンドウを表示する

`PLAYWRIGHT_MCP_HEADLESS=false claude` でセッションを始める。`PLAYWRIGHT_MCP_HEADLESS=`（空）は既定値ではなく空に展開され、Playwright MCP が解釈できずに headed になる。`claude mcp get playwright` は、この値を既定値（`:-true`）を省いて表示するが、登録には含まれている。

headless のブラウザを止めるサイトもある（login.salesforce.com の宣伝の枠は Access Denied になった）。そのときも headed で始める。

<a name="playwright-mcp-output"></a>

#### 出力

スクリーンショット・ページの構造・コンソールのログは、`~/Library/Caches/playwright-mcp` に自動の名前で溜まる。自動では消えないので、いつ消してもよい。

<a name="playwright-mcp-update"></a>

#### 更新

1. 最新の版を調べる: `npm view @playwright/mcp version dependencies`。依存が完全に固定した版のままかも見る。
2. [リリース](https://github.com/microsoft/playwright-mcp/releases)で、オプションと既定値の変化を確かめる。
3. [README のツールの一覧](https://github.com/microsoft/playwright-mcp#tools)で、既定で有効なツールに、ファイルのパスを受け取る引数（`filename`・`paths` 以外の名前も）、URL を受け取る引数、任意のコードを動かすものが増えていないかを確かめる。増えていれば、deny かフックを直す。
4. Playwright MCP を使っているセッションをすべて閉じる（`register-mcp.sh` は入れた場所を上書きし、登録を消してから足すので、動いているサーバーと、その間に始めたセッションに影響する）。
5. `mcp/playwright.json` の `npmPackage` の版を書き換え、`register-mcp.sh` を実行する。`"$(cd ~ && mise where node)/bin/node" ~/.local/share/claude-mcp/playwright/node_modules/@playwright/mcp/cli.js --help` で、使っているオプションが残っているかを確かめる。

<a name="playwright-mcp-remove"></a>

#### 削除

1. `claude mcp remove playwright -s user`
2. `mcp/playwright.json` を消す（残すと `setup.sh` が登録し直す）。
3. `settings.json` の deny（`mcp__playwright__*` の 2 つと `Read(~/.crit/**)`）、denyRead の `~/.crit`、`disabledMcpjsonServers` の `playwright`、フックの登録を消す。定義がなければ、`check-repo.py` はこれらを求めない。
4. 入れた `~/.local/share/claude-mcp/playwright` と、出力の `~/Library/Caches/playwright-mcp` を消す。

## cc-safe-push

Claude Code から `git push` するためのラッパー。`settings.json` で `git push` を deny にしているので、Claude はこのラッパーでしか push できない。どのリポジトリのどのブランチに送れるかは、root 所有のラッパーと許可リストで決める。

<a name="cc-safe-push-policy"></a>

### 動作

対象リポジトリに移動して、`/usr/local/libexec/claude-push/cc-safe-push` を引数なし・単独で実行する。現在のブランチを origin の同じ名前のブランチに送る。

`cd` や `; echo` などを前後に付けると `sandbox.excludedCommands` と一致せず、sandbox 内で動いて一時ディレクトリを作れずに失敗する（終了コード 1）。`hooks/validate-command.sh` は、この形の実行をブロックする。

| 状況                                                                                                          | 結果                                   |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 許可リストのリポジトリの、保護されていないブランチ                                                            | 確認なしで push する                   |
| 許可リストにないリポジトリ                                                                                    | 拒否する。人間が自分の端末で push する |
| `main`, `master`, `staging`（大文字・小文字を区別しない）                                                     | 拒否する                               |
| 判定できない場合（detached HEAD、origin が `git@github.com:OWNER/REPO.git` の形でない、許可リストの異常など） | 拒否する                               |

終了コードは、0 が成功、1 が push の失敗、2 が拒否。

upstream は設定されないので、PR は `gh pr create --head <branch>` で作る。upstream が必要なときは、人間が自分の端末で、そのブランチに切り替えて引数なしの `git push` を実行する。`bin/.gitconfig` の `push.autoSetupRemote = true` により、送るコミットがなくても upstream が設定される（未 push のコミットがあれば、それも送られる）。`git push origin <branch>` のように送り先を指定すると設定されない。

<a name="cc-safe-push-install"></a>

### インストール

Claude Code のセッションでは `sudo` を実行できないので、通常のターミナルで行う。

前提:

- Xcode Command Line Tools がインストールされている。ラッパーは `/Library/Developer/CommandLineTools/usr/bin/` の `python3` と `git` を直接使う。`/usr/bin/python3` と `/usr/bin/git` は xcrun の shim で、`DEVELOPER_DIR` や xcrun のキャッシュで起動するプログラムが変わるため。shebang の `env -i` で、呼び出し元の環境変数も引き継がない。
- CLT の git が `GIT_NO_LAZY_FETCH` に対応している（2.54.0 で確認済み）
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

<a name="cc-crit"></a>

## cc-crit

Claude Code から Crit の対話レビューを開くためのラッパー。sandbox の中の crit は `~/.crit` に書けず、localhost でも待ち受けられない。そこで `cc-crit` が sandbox の外で、Crit 専用の Seatbelt profile（`cc-crit.sb`）と専用の HOME（`~/.cc-crit/crit-home`）の中で crit を動かす。設計とセキュリティレビューは [docs/work/20261111_crit-sandbox/design.md](../docs/work/20261111_crit-sandbox/design.md) を参照する。

Plan Mode の plan のレビューは、Crit プラグインの hook（sandbox の外で動く）が行うので、`cc-crit` は使わない。

<a name="cc-crit-usage"></a>

### 使い方

Claude は個人スキル `/crit-review`（`claude/skills/crit-review/SKILL.md`）の手順に従う。作業ディレクトリに `.cc-crit-request.json` を書き、次のどちらかを単独で実行する。

| コマンド | 依頼ファイル | 動作 |
| --- | --- | --- |
| `/usr/local/libexec/claude-crit/cc-crit review` | `{"files": ["path"]}`、ブランチの差分なら `{}` | crit をポート 47800〜47819 で起動してブラウザを開き、Finish Review まで待つ |
| `/usr/local/libexec/claude-crit/cc-crit reply` | `{"session": "<id>", "replies": [{"reply_to": "c_…", "body": "…"}]}` | 既存のコメント（行・ファイルは `c_`、レビュー全体は `r_`）に返信する。author は `Claude Code` に固定 |

終了コードは、0 が成功、1 が失敗、2 が拒否。依頼ファイルは実行のたびに消える。

crit はレビュー中のファイルの全文を `~/.cc-crit` に書き出すので、`settings.json` で Claude の sandbox から `~/.cc-crit` を読ませない（`sandbox.filesystem.denyRead` と `permissions.deny` の `Read(~/.cc-crit/**)`）。結果は `cc-crit` の出力で Claude に届く。

<a name="cc-crit-install"></a>

### インストール

通常のターミナルで行う。crit（Homebrew）と Homebrew の git、Xcode Command Line Tools（ラッパーの python3。cc-safe-push と同じ）が前提。

```sh
cd ~/dotfiles
sudo install -d -o root -g wheel -m 0755 /usr/local/libexec/claude-crit
sudo install -o root -g wheel -m 0755 claude/bin/cc-crit /usr/local/libexec/claude-crit/cc-crit
sudo install -o root -g wheel -m 0644 claude/bin/cc-crit.sb /usr/local/libexec/claude-crit/cc-crit.sb
# 依頼ファイルをグローバルの ignore に追加する（すでに書かれていれば何もしない）
grep -qxF '.cc-crit-request.json' ~/.config/git/ignore || echo '.cc-crit-request.json' >> ~/.config/git/ignore
```

インストールしたら、sandbox の外で profile のテストを実行する。Claude Code の sandbox の中では `sandbox-exec` を入れ子にできないので、スキップされる。

```sh
mise run crit:profile-test
```

<a name="cc-crit-update"></a>

### 更新するとき

`cc-crit` か `cc-crit.sb` を変更したら、再度インストールする。crit、git、macOS を更新したら、profile のテストをやり直す（`mise run crit:profile-test`）。profile は crit と git の実行ファイルの場所と、動作に要る権限に依存する。

アンインストールは、`settings.json` の `cc-crit` の行を消して `sudo rm -r /usr/local/libexec/claude-crit` を実行する。専用 HOME の `~/.cc-crit` は残るので、要らなければ消す。

<a name="gh-read-token"></a>

## sandbox 内の gh

sandbox 内の Bash からは Keychain を読めない（`sandbox.filesystem.denyRead` に `~/Library/Keychains`）。`gh auth login` で保存した書き込みのできるトークンを使えるのは、sandbox の外で動く `cc-safe-push` と `cc-safe-pr`、人間の端末だけ。

起動元のシェルから引き継いだ `GITHUB_TOKEN`、`GH_ENTERPRISE_TOKEN`、`GITHUB_ENTERPRISE_TOKEN` は、`sandbox.credentials.envVars` の `deny` で sandbox 内から除き、下の 1 行でも消す。`gh` は `GH_TOKEN` が空のときにこれらを使うため。`GH_TOKEN` を `export` したシェルから Claude Code を起動しない（フックが動かなかった場合に残る）。

sandbox 内の `gh` には、`hooks/gh-read-token.sh` が owner ごとの読み取り専用トークンを `GH_TOKEN` として渡す。SessionStart で `CLAUDE_ENV_FILE` に 1 行を追記し、その 1 行が Bash コマンドのたびに、カレントディレクトリの origin の owner に対応するトークンを選ぶ。

| 操作                                                       | 結果                                                                                             |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 読み取り（`gh pr view`、`gh pr list`、`gh run list` など） | 成功する                                                                                         |
| 書き込み（PR の作成・編集・マージ、Issue の作成など）      | 403 で失敗する。許可リストのリポジトリの PR は `cc-safe-pr` で、それ以外は人間が自分の端末で行う |
| トークンを置いていない owner、origin のないディレクトリ    | `GH_TOKEN` が空になり未認証になる（private リポジトリは読めない）                                |

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
