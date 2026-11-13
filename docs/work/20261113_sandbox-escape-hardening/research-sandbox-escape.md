---
status: done
created: 2026-11-13
---

# sandbox の外で実行されるものの調査

Claude Code の sandbox の中から書けて、後で sandbox の外で実行・読み込みされるものを調べた記録。PR #15 の後に残った作業 A（A1〜A3）と、調査中に見つけた A4 をまとめる。

関連: PR #15、[20261111_crit-sandbox/design.md](../20261111_crit-sandbox/design.md)、[plan.md](plan.md)

<a name="method"></a>

## 1. 方法

- **実測:** Claude Code の Bash ツール（sandbox の中）から、2026-11-13 に実行した。
- **書き込みの確認:** ファイルを `O_WRONLY | O_APPEND` で開いて、何も書かずに閉じた。`O_CREAT` を付けないので、ファイルを作らず、内容も更新時刻も変えない。Seatbelt は開いた時点で書き込みを判定する。
- **コード:** sandbox-runtime（`f7a0f19`）のソースを読んだ。
- **推測:** ファイルの役割と、CLAUDE.md の説明から推測した。

<a name="mandatory-deny"></a>

## 2. sandbox-runtime が既定で守るもの（コード）

sandbox-runtime は、作業ディレクトリの下のどの深さにあっても、次の名前への書き込みを拒否する（`src/sandbox/sandbox-utils.ts:21-50`、`src/sandbox/macos-sandbox-utils.ts:103-136`）。

- **ファイル:** `.gitconfig`、`.gitmodules`、`.bashrc`、`.bash_profile`、`.zshrc`、`.zprofile`、`.profile`、`.ripgreprc`、`.mcp.json`
- **ディレクトリ:** `.vscode`、`.idea`、`.claude/commands`、`.claude/agents`、`.git/hooks`
- **git の設定:** `.git/config`

名前で判定する。そのため `bin/.zshrc` は守られるが、ドットの付かない `vscode/settings.json` などは守られない。

<a name="write-probe"></a>

## 3. dotfiles で書けるか（実測）

| ファイル | 結果 | sandbox の外で使われる経路（推測） |
| --- | --- | --- |
| `bin/.zshrc`・`bin/.zprofile`・`bin/.gitconfig` | 拒否 | 2 章の既定の保護 |
| `bin/.Brewfile` | 書ける | 人間が実行する `brew bundle`（tap や cask を足せる） |
| `bin/init.sh` | 書ける | 人間が実行するセットアップ |
| `vscode/settings.json` | 書ける | VS Code のユーザー設定の実体。リンクなので、書いた時点で動いている VS Code に効く |
| `codex/config.base.toml` | 書ける | 人間が実行する `sync.py` で `~/.codex/config.toml` にマージされる |
| `codex/AGENTS.md` | 書ける | `~/.codex/AGENTS.md`（すべてのリポジトリで Codex が読む指示） |
| `biome/sync_schema.sh` | 書ける | mise の postinstall から実行される |
| `config/uv/uv.toml` | 書ける | `~/.config/uv` の実体（パッケージの取得元を変えられる） |
| `config/sf/plugins.txt` | 書ける | 人間が実行する同期のタスクで、sf のプラグインを入れる |
| `obsidian/community-plugins.json` | 書ける | Vault の設定 |
| `init.command` | 書ける | 人間がダブルクリックで実行する |
| `CLAUDE.md` | 書ける | 次のセッションでプロジェクトの指示として読まれる（[5.3](#risk-instructions)） |

確かめていないが、同じディレクトリにあるので書けると推測するもの:

- `aws/config`: `~/.aws/config` の実体。`credential_process` を書き足すと、人間が aws CLI を使ったときに実行される
- `setup.command`
- `ghostty/link.sh`
- `vscode/keybindings.json`
- `vscode/projects.json`

いま守っているのは、プロジェクト設定（`.claude/settings.json`）の `denyWrite` と `ask` に入っている `claude`・`zsh`・`config/sheldon`・`config/starship`・`mise`・`mise.toml`・`ghostty/config`・`vscode/tasks.json` だけ。Edit・Write ツールについては、ユーザー設定の `ask` に `Edit(~/dotfiles/claude/**)` がある。

> [!IMPORTANT]
> **訂正**
> 前回の報告では、`bin/`（`.zshrc`・`.zprofile`・`.gitconfig`）に書けると書いた。根拠にしたのは、`bin/` に新しいファイルを作れたことだった。今回、`.zshrc` などのファイルそのものを確かめたところ、書き込みは拒否された。`bin/` で書けるのは `.Brewfile` と `.sh` のファイル。

<a name="xcrun"></a>

## 4. ラッパーのインタプリタ（A1）

- **shim（実測）:** ラッパー 3 本の shebang の `/usr/bin/python3` と、`cc-safe-push` が使う `/usr/bin/git` は、xcrun の shim。`DEVELOPER_DIR` に存在しないパスを渡すと、`xcrun: error: missing DEVELOPER_DIR path` で止まる。
- **環境変数を変える経路（実測と推測）:**
  - mise の hook-env は、Claude の Bash の中で動いている。`paranoid=false` なので、信頼はパスで決まる（実測）。
  - 信頼済みのリポジトリの `mise.toml` の `[env]` に何かを足すと、次のコマンドから環境変数が変わる（推測）。
  - `excludedCommands` で sandbox の外で動くラッパーも、同じ環境変数を引き継ぐ（推測）。
- **xcrun のキャッシュ（実測）:**
  - キャッシュは `$(getconf DARWIN_USER_TEMP_DIR)xcrun_db` にある。形式は `file` で `data`、最終更新は 2026-10-31 21:03。
  - sandbox からは書けない。
  - `TMPDIR` を変えて `xcrun --find python3` を実行しても、その場所にキャッシュはできなかった。そのため、場所は `TMPDIR` ではなく `confstr` で決まると推測する。
- **実体（実測）:** CLT の実体の所有者は、どれも root:wheel。
  - `/Library/Developer/CommandLineTools/usr/bin/git` は普通のファイル。
  - `/Library/Developer/CommandLineTools/usr/bin/python3` は、`../../Library/Frameworks/Python3.framework/Versions/3.9/bin/python3` へのリンク。
  - `/usr/bin/env` は shim ではない。
- **ラッパーの中（コード）:** 3 本とも `os.environ` を読まない。git や crit には、固定した環境変数を渡している。

<a name="colima"></a>

## 5. Colima（A3）と、範囲外のリスク

<a name="risk-colima"></a>

### 5.1 Colima の鍵と Docker のソケット

- **Lima の鍵:** `~/.colima/_lima/_config/user` はある。`test -r` では読めた。実際に開く確認は、自動判定で拒否された。`~/.lima/_config` はない。
- **Docker のソケット:** `~/.colima/default/docker.sock` と `containerd.sock` がある（所有者のみ読み書きできる）。`/var/run/docker.sock` はない。
  - sandbox-runtime は、`allowUnixSockets` か `allowAllUnixSockets` がなければ unix ソケットへの接続を止める（`macos-sandbox-utils.ts:1292-1315`）。
  - curl での接続の実験（`curl --unix-socket … /_ping`）は、3 回とも実行前に拒否された。原因は、ユーザー設定の `permissions.deny` にある `Bash(curl *)` だった。auto mode を外しても同じだった。最初の 2 回は、auto mode の自動判定による拒否だと誤って判断していた。
  - 代わりに、利用者の承認を得て、Python で接続だけを試した（要求は送らない。2026-11-13）。結果は `PermissionError: [Errno 1] Operation not permitted` で、sandbox の中からは接続できない（実測）。
    - ソケットの所有者は利用者なので、ファイルの権限で拒否されたのなら `EACCES`（13）になる。`EPERM`（1）が返ったので、sandbox による拒否と判断した。
    - sandbox の外から接続できるかの確認（対照）は行っていない。
- **影響:** `colima.yaml` の `mounts: []` には「既定で `$HOME` を書き込み可能でマウントする」とある。VM か Docker に入れると、`$HOME` のどこにでも書けるので、sandbox を抜けられる。

<a name="risk-actions"></a>

### 5.2 GitHub Actions（範囲外）

- **CI の設定（実測）:** `.github/workflows/ci.yaml` は、`pull_request` と、main への `push` で動く。設定は次のとおり。
  - `permissions: contents: read`
  - `persist-credentials: false`
  - secrets は参照していない
- **経路（推測。GitHub の仕様は公式ドキュメントで未確認）:**
  - Claude は、`cc-safe-push` と `cc-safe-pr` で、確認なしにブランチを push し、PR を作れる。
  - 同じリポジトリのブランチから作った PR では、そのブランチで書き換えた workflow がそのまま動く。
  - workflow の `permissions` は書き換えられる。リポジトリの既定は上限にならない。
- **できること（推測）:**
  - リポジトリの secrets を読める。
  - `contents: write` のトークンで main に直接 push できる（ruleset やブランチ保護がない場合）。
  - runner から自由に通信できる。
- **dotfiles への影響（推測）:** secrets と OIDC の信頼がなければ、影響は小さい。許可リストのほかのリポジトリ（デプロイ用の secrets や OIDC があるもの）では大きい。

<a name="risk-instructions"></a>

### 5.3 CLAUDE.md・AGENTS.md への指示の仕込み（一部は範囲外）

- **書けるもの（実測）:** sandbox から `CLAUDE.md`（リポジトリ直下）と `codex/AGENTS.md` に書ける。
- **守られているもの:** グローバルの `claude/CLAUDE.md` と `claude/rules` は守られている。
- **影響（推測）:** 書いても、それだけで sandbox は抜けられない。次のセッションも、同じ sandbox と権限で動く。ただし次の影響がある。
  - 書いた内容は、次のセッションで優先度の高い指示として読まれる。コンテキストの圧縮の後も消えない。
  - 指示で、確認なしで動くラッパー（公開リポジトリへの push）を使わせたり、人間に `!` コマンドや承認を促させたりできる。
  - commit されると、ほかのマシンや Codex（グローバルの AGENTS.md）にも広がる。
- **きっかけ（推測）:** Web ページ、Issue、依存パッケージなど、Claude が読む文書に紛れた指示。

<a name="risk-xcrun-cache"></a>

### 5.4 Edit・Write ツールからの xcrun のキャッシュの書き換え（範囲外。ただし A1 の方式に関わる）

- **sandbox の外で動く（コード・設定）:** Edit・Write ツールは Claude Code の本体で動き、Seatbelt を通らない。止めるのは権限の規則と auto mode の判定だけで、`/var/folders` への書き込みを拒否する規則はない。
- **書き換えると（推測）:** shim は、ラッパーのインタプリタ（`/usr/bin/python3`）と `cc-safe-push` の `/usr/bin/git` を、キャッシュに書かれたパスで起動する。
  - 好きなプログラムを、sandbox の外で、確認なしで動かせる。
  - ラッパーは `excludedCommands` に入っていて、`permissions.allow` で許可されている。
- **書き換えられるか（未確認）:** 次の 2 点を確かめていない。
  - xcrun がキャッシュの中身を確かめるか。
  - 形式が `data`（バイナリ）なので、文字列を書く Write ツールで作れるか。
- **env -i では防げない:** キャッシュの場所は環境変数で決まらないと推測するので、`env -i` を付けても防げない。

<a name="not-verified"></a>

## 6. 未確認のこと

| 項目 | 理由 | 扱い |
| --- | --- | --- |
| Lima の鍵を実際に開けること | 自動判定で拒否 | denyRead を足すので、結果によらず塞がる |
| macOS が shebang の引数を分けるか（`env -i` が使えるか） | 自動判定で拒否 | plan.md の Task 3 のテストで確かめる |
| ラッパーが mise の `[env]` を引き継ぐこと | 未実施 | `env -i` で結果によらず塞がる |
| `aws/config` などに書けること | 未実施 | Task 1 で守った後に、拒否されることを確かめる |
| xcrun がキャッシュを確かめるか | 確かめるには sandbox の外への書き込みが要る | D1 で xcrun を経由しない方式にすれば不要 |
