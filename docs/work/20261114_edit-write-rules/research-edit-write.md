---
status: in-progress
created: 2026-11-14
---

# Edit・Write ツールからの書き込みの調査

Claude の Edit・Write ツールで、sandbox の外で後から実行・読み込みされるファイルに書けるかを調べた記録。前回の調査で残った次の 2 つを、まとめて扱う。

- **2:** Edit・Write ツールからの書き込み
- **3:** `CLAUDE.md`・`AGENTS.md` への指示の仕込み（[前回の 5.3](../20261113_sandbox-escape-hardening/research-sandbox-escape.md#risk-instructions)）

関連: [plan.md](plan.md)、PR #18、[20261113_sandbox-escape-hardening/research-sandbox-escape.md](../20261113_sandbox-escape-hardening/research-sandbox-escape.md)

<a name="method"></a>

## 1. 方法

- **文書:** 2026-11-14 に原文で読んだ。
  - Claude Code（code.claude.com）: permissions、permission-modes、settings-reference、sandboxing、worktrees
  - mise（mise.jdx.dev）: configuration、hooks、environments、templates、cli/trust、paranoid
- **実測:** Claude Code の Bash・Edit ツールで、2026-11-14 に行った。版は、scratchpad の試験が 2.1.311、それ以外が 2.1.323。
- **人間の試験:** `--settings` で設定を 1 つ足したセッションを、人間が起動して確かめた（[3.2](#trial-session)）。
- **集計:** `~/.claude/projects` のセッションの記録（過去 90 日、247 セッション）から、Edit・Write などのツール名と書き込み先のパスだけを数えた。内容は読んでいない。

<a name="docs"></a>

## 2. 文書で確かめたこと

<a name="docs-outside-sandbox"></a>

### 2.1 Edit・Write ツールは sandbox の外で動く

sandboxing の文書には「The sandbox covers shell commands only. Claude's file tools, MCP servers, and hooks run outside it.」とある。Edit・Write ツールを止めるのは、権限の規則と auto mode の判定だけ。

<a name="docs-pattern-anchor"></a>

### 2.2 規則のパスの起点

| 書き方 | 起点 |
| --- | --- |
| `//path` | ファイルシステムのルート |
| `~/path` | ホームディレクトリ |
| `/path` | 設定ファイルによる。プロジェクト設定では主な作業ディレクトリ、ユーザー設定では `~/.claude/` |
| `path`・`./path` | カレントディレクトリ |

- 先頭に何も付けない `Edit(**/.git/config)` は、カレントディレクトリより下にしか効かない。ほかのリポジトリの `.git/config` は守れない。
- deny と ask の規則は、カレントディレクトリより下のどの深さにも当たる。
- ユーザー設定の `/path` は `~/.claude/` から見る。すべてのプロジェクトに効かせるには `//` か `~/` を使う、と文書にある。

<a name="docs-protected"></a>

### 2.3 保護パス

permission-modes の「Protected paths」にある。

- **ディレクトリ:** `.git`、`.config/git`、`.vscode`、`.idea`、`.husky`、`.cargo`、`.devcontainer`、`.yarn`、`.mvn`、`.claude`（`.claude/worktrees/`、plan のファイル、auto memory の `.md` などは例外）
- **ファイル:** `.gitconfig`、`.gitmodules`、シェルの rc ファイル、`.envrc`、`.npmrc`、`.pre-commit-config.yaml`、lefthook の設定、`.mcp.json`、`.claude.json` など
- **auto mode での扱い:** 「Routed to the classifier, which decides」。止まるとは限らない。
- **allow の規則:** 保護パスへの書き込みを事前に許可しない。
- **保護パスにないもの:** `mise.toml`、`~/Library/LaunchAgents`、`CLAUDE.md`、`AGENTS.md`

<a name="docs-classifier"></a>

### 2.4 auto mode の判定の順番

1. allow・ask・deny の規則に当たれば、それで決まる。ただし、保護パスへの書き込みは、allow に当たっても判定に回る。
2. 作業ディレクトリの中の編集は、自動で許可する。保護パスへの書き込みは除く。
3. それ以外は判定に回る。

作業ディレクトリの外への編集は、文書には直接書かれていない。2 に当たらないので、3 で判定に回ると読んだ（推測）。

<a name="docs-write-block"></a>

### 2.5 `permissions.blockWritesOutsideWorkingDirectories`

settings-reference にある。v2.1.314 以降で使える。

- **止めるもの:** Write・Edit・NotebookEdit ツールの、作業ディレクトリの外への書き込み。`bypassPermissions` を含むどのモードでも止める。Bash・MCP のツール・フックは止めない。
- **作業ディレクトリに含まれるもの:** `--add-dir`、`/add-dir`、ユーザー設定の `additionalDirectories` で足したディレクトリ。リポジトリの設定だけで足したものは含まれない。
- **書けるまま残るもの:** plan のファイル、scratchpad、バックグラウンドのセッションの `tmp`、このプロジェクトの auto memory の `.md`
- **作業ディレクトリの中でも止めるもの:** Claude Code の設定ファイル（設定ファイルでこの設定を外せるため）
- **どの設定ファイルに書くか:** どのファイルで `true` にしても効く。リポジトリの設定で、ユーザー設定の `true` を外すことはできない。
- **worktree への影響:** EnterWorktree と ExitWorktree のツールがなくなる（[2.6](#docs-worktree)）。

<a name="docs-worktree"></a>

### 2.6 worktree との関係

worktrees の「Claude has no EnterWorktree tool」に、この設定をオンにしたまま worktree で作業する方法がある。

- **対話のセッション:** `claude --worktree <name>`（短い形は `-w`）で始める。worktree は `.claude/worktrees/<name>/` に、ブランチ `worktree-<name>` で作られる。
- **バックグラウンドのセッション:** `claude --bg --worktree` で始める。
- **サブエージェントの worktree:** 作業ディレクトリの外にあると、編集を止める。`/add-dir` でリポジトリ直下の `.claude/worktrees` を足す。

<a name="measured"></a>

## 3. 実測

<a name="probe-git-config"></a>

### 3.1 作業ディレクトリの外の `.git/config`

scratchpad にダミーの `probe/.git/config` を作り、Edit ツールで 1 行変えた。確認の画面も、規則による拒否もなく通った。

- ユーザー設定の `Edit(**/.git/config)` は、作業ディレクトリの外には効いていない。[2.2](#docs-pattern-anchor) と合う。
- scratchpad は Claude Code の例外の場所なので、ほかの場所で同じ結果になるかは確かめていない。文書のとおりなら、判定に回る。

<a name="trial-session"></a>

### 3.2 `blockWritesOutsideWorkingDirectories` を試したセッション

人間が、この設定だけを書いたファイルを `--settings` で読ませ、`claude -w trial-block` で worktree のセッションを始めて確かめた（Claude Code 2.1.323）。

| # | 試したこと | 結果 |
| --- | --- | --- |
| 1 | Write ツールで `~/block-test.txt` を作る | 拒否された |
| 2 | worktree の中のファイルを編集する | 普段どおり編集できた |
| 3 | worktree の `claude/settings.json` を編集する | 拒否されず、確認の画面も出なかった |
| 4 | Bash で `touch claude/x` | sandbox が止めた（Operation not permitted） |

- 4 から、プロジェクト設定の denyWrite（`./claude`）は、worktree の側にも効く。
- 3 は、worktree の `claude/settings.json` が、そのセッションが読み込んだ設定ファイルではないためと考える（推測）。元のチェックアウトの `claude/settings.json`（`~/.claude/settings.json` のリンク先）を止めるかは、試していない。

<a name="gap-worktree-claude"></a>

### 3.3 worktree の `claude/` は、確認なしで編集できる

3.2 の 3 から分かった抜け穴。

- **Bash:** プロジェクト設定の denyWrite（`./claude`）で止まる。
- **Edit・Write ツール:** 止める規則がない。
  - プロジェクト設定の `permissions.ask` は、denyWrite と同じディレクトリを並べているが、`Edit(/claude/**)` だけがない。
  - PR #18 で、ユーザー設定の `Edit(~/dotfiles/claude/**)` に任せると決めた（[plan.md](../20261113_sandbox-escape-hardening/plan.md) の Task 1 の表）。この規則は、元のチェックアウトにしか当たらない。
- **影響:** worktree では、`claude/` の settings・hooks・rules・bin を、確認なしで書き換えられる。
  - いま使っている設定に届くのは、PR をマージして、元のチェックアウトに pull した後。
  - 人間が worktree から sandbox の外で動かすものには、すぐ届く。`test-cc-crit-profile.py`、`mise run crit:profile-test`、ラッパーのインストールなど。
- この抜け穴は、`blockWritesOutsideWorkingDirectories` とは関係なく、いまもある。

<a name="branch-rename"></a>

### 3.4 worktree のブランチ名の変更

EnterWorktree で作った worktree の中で、`git branch -m fix/edit-write-rules` を実行した。

- ブランチ名は変わった。
- `error: could not lock config file .git/config` が出た。sandbox が `.git/config` を守っているため。
- 元のブランチ名の設定（`branch.<name>.*`）がなかったので、影響はない。`claude -w` で作った worktree でも、同じ方法で規約の名前（`fix/…` など）に変えられると考える（推測）。

<a name="probe-sandbox-anchor"></a>

### 3.5 sandbox の `denyWrite` の `**/` の形（plan の Task 7 の T6）

2026-11-16 に 2.1.325 で試した。変更後の規則を `--settings` で読ませた worktree のセッションで、sandbox の中の Bash から書き込んだ。

- `denyWrite` に `**/mise.toml`・`**/.tool-versions`・`**/.config/mise` があっても、`touch tmp-probe/mise.toml`、`touch tmp-probe/.tool-versions`、`mkdir tmp-probe/.config/mise` はどれも成功した。sandbox の拒否も出なかった。
- 同じセッションで、`denyRead` の `~/**/*.key` は `~/cc-probe/b.key` の読み取りを止めた（T8）。
- settings-reference の「Sandbox path prefixes」には、`./` と接頭辞なしは「Relative to the project root for project settings, or to `~/.claude` for user settings」とある。権限の規則（[2.2](#docs-pattern-anchor)）では接頭辞なしの起点はカレントディレクトリなので、同じ `**/mise.toml` でも、権限の規則と sandbox とで当たる場所が違う。
- `--settings` で渡したファイルでの起点は、文書に書かれていない。
- 同じ文書には、macOS では `*`・`?`・`**` が sandbox の 4 つのリストすべてで使えるとある。
- 文書は WebFetch で取得した本文で読んだ。逐語かどうかは原文で確かめていない。
- ユーザー設定の `**/mise.toml` は `~/.claude/**/mise.toml` として扱われ、作業ディレクトリに当たらなかったと考える（推測）。起点を確かめる試験は、作業ディレクトリの外に書く操作が自動判定で拒否されたので、していない。
- dotfiles の設定で、接頭辞のない sandbox のパスは、この mise の 10 項目だけだった。`denyRead` などは、すべて `~/` か `/` で始まる。
- **対応（2026-11-16、人間の判断）:** D4 は戻さずに、`~/**/mise.toml` の形に変えた。
  - ホームの下の全プロジェクトに当たる見込み。ホームの外（`/tmp` に clone したものなど）は守れない。
  - `~/Dev`、bun のキャッシュ、mise の installs、`~/.cache` の依存パッケージの中に、同じ名前のファイルはなかった。巻き込みで `npm install` などが失敗するおそれは小さい。

<a name="write-targets"></a>

## 4. 過去 90 日の書き込み先

247 セッションの、Edit・Write・MultiEdit・NotebookEdit の呼び出しを数えた。

| 書き込み先 | 作業ディレクトリの中 | 外 | 備考 |
| --- | --- | --- | --- |
| scratchpad・一時ディレクトリ | — | 629 | 書けるまま残る |
| auto memory | — | 334 | `.md` は書けるまま残る |
| plan のファイル（`~/.claude/plans`） | — | 73 | 書けるまま残る |
| その他 | 2219 | 38 | 外の 38 は、別のリポジトリのセッションから dotfiles や `~/Dev/ksc` を直したもの、サブディレクトリで起動して親の README を直したものなど |
| `CLAUDE.md`・`AGENTS.md` など | 245 | 4 | 外の 4 はすべて scratchpad の中 |
| `mise.toml` 系 | 4 | 1 | 外の 1 は scratchpad の中 |
| `.git` の中 | 1 | 1 | 外の 1 は scratchpad の中 |

- **`CLAUDE.md`・`AGENTS.md` を編集したセッション:** dotfiles が 22、sf_hpf_metadata が 19、そのほかが 6。sf_hpf_metadata の `AGENTS.md` だけで 128 回。
- **worktree の `claude/` の編集:** cc-crit などの 3 つの worktree のセッションで、約 100 回。
- **作業ディレクトリの中の Claude Code の設定ファイル:** sf_hpf_metadata の `.claude/settings.json` が 39 回、dotfiles の `.claude/settings*.json` が 9 回。`blockWritesOutsideWorkingDirectories` をオンにすると、人間が編集することになる。

<a name="mise"></a>

## 5. mise の設定ファイル

- **読み込むファイル:** カレントディレクトリからルートまでの各ディレクトリで、次を読む。
  - `mise.toml`、`mise.local.toml`。どちらもドットで始まる形も読む
  - `mise.<env>.toml`、`mise.<env>.local.toml`
  - `mise/config.toml`、`mise/conf.d/*.toml`
  - `.mise/config.toml`、`.mise/conf.d/`
  - `.config/mise.toml`、`.config/mise/`
  - `config.toml` の横の `config.local.toml`
  - `.tool-versions`
- **`cd` で動くもの:**
  - `[hooks]` の `enter`・`cd`（`mise activate` が要る）
  - `[env]` の `_.source`（bash のスクリプトを実行する）
  - テンプレートの `exec()`（`[env]`・`[tools]`・`[vars]`・`[hooks]` の値の中で、設定を読むたびに実行する。`.tool-versions` もファイル全体がテンプレート）
- **信頼:** コードを動かす部分には信頼が要る。paranoid でなければ、信頼はパスで決まる（推測。文書はパスで決まるとは書いていないが、内容に結び付くのは paranoid のときだけと書いている）。
  - 元のチェックアウトで信頼した設定は、worktree の同じパスも信頼する（文書に明記）。
  - グローバル設定（`mise/mise_config.toml`）に `trusted_config_paths` はない（実測）。
- **ほかのリポジトリ:** sf_hpf_metadata にも `mise.toml` がある（実測）。信頼済みなら、そこに書かれた hook や `_.source` は、人間がそのディレクトリに `cd` したときに sandbox の外で動く。
  - Bash（sandbox の中）は、作業ディレクトリの中の `mise.toml` に書ける。sandbox-runtime が既定で守る名前（[前回の 2 章](../20261113_sandbox-escape-hardening/research-sandbox-escape.md#mandatory-deny)）に入っていない。
  - Edit・Write ツールは、作業ディレクトリの中なので自動で許可される。保護パスではない。

<a name="read-rules"></a>

## 6. Read の規則を `~/**` に広げたときの影響

Read の deny の規則は、sandbox の `denyRead` にもなる（このセッションの sandbox の設定に、Read の規則と同じパターンが入っている）。広げると、sandbox の中の Bash からも読めなくなる。

- **`*.pem`（実測）:** CA 証明書の束が `~/.local/share/mise/installs/` の下にある。
  - pip が同梱する `certifi/cacert.pem`
  - Ruby の `libexec/cert.pem` と、rubygems の `ssl_certs`
  - aws-cli（botocore）の `cacert.pem`
  - `~/**/*.pem` にすると、sandbox の中で pip・gem・aws の HTTPS が失敗する見込み（推測）。
  - Python と Ruby の既定の CA は `/etc/ssl/cert.pem` で、ホームの外にある（実測）。
- **`*.key`（実測）:** 主なものは `~/.claude/sessions/*.key`（23 個）で、ほかは codex の実行環境のテスト用の鍵など。
  - `~/.claude/sessions/*.key` は Claude Code のファイルなので、sandbox の中の `claude` コマンド（`claude plugins` など）が読むかを確かめる必要がある。
  - macOS の Keynote の書類も `.key` で、読めなくなる。
- **`credentials` という名前のディレクトリ（実測）:** bun のキャッシュの `@anthropic-ai/sdk` の中に 2 つある。
  - 今のユーザー設定の `Read(~/**/credentials)` が、ディレクトリの中身まで止めるかは確かめていない。試験用のファイルを作業ディレクトリの外に作る操作が、自動判定で拒否されたため。

<a name="decisions"></a>

## 7. 判断（2026-11-14）

- **2 の方式:** `blockWritesOutsideWorkingDirectories` をオンにし、作業ディレクトリの中向けに規則を少し足す。あわせて、プロジェクト設定の ask に `Edit(/claude/**)` を足す（[3.3](#gap-worktree-claude)）。詳細は [plan.md](plan.md)。
  - もう 1 つの案は、`~/**` の形の deny の規則を、守る場所ごとに並べるものだった。並べ忘れた場所を守れないので、採らなかった。
- **3 の扱い:** `CLAUDE.md`・`AGENTS.md` のための規則は足さずに閉じる。
  - ほかのリポジトリの分は、Edit・Write ツールは 2 の対策で止まり、Bash はもともと書けない（sandbox で書けるのは作業ディレクトリと一時ディレクトリなど）。
  - 作業中のリポジトリの分は、編集が普段の作業の一部で（[4 章](#write-targets)）、ask にすると確認の画面が多く出る。差分と PR のレビューで確かめる。
  - dotfiles の `CLAUDE.md`・`codex/AGENTS.md`・`claude/CLAUDE.md` は、すでに denyWrite と ask で守られている。
  - 前回の 3 の 2 つ目の問い（denyWrite に `**/CLAUDE.md` を書いたときの動き）は、`CLAUDE.md` については試さない。mise について同じことを確かめる（plan の D4）。
- **作業の場所:** この会話のまま EnterWorktree で worktree に入り、出ずに最後まで進める。

<a name="residual-risks"></a>

## 8. 残るリスク

- **作業中のリポジトリの `CLAUDE.md`・`AGENTS.md`（dotfiles 以外）:** 未コミットの書き換えを、次のセッションが読む。差分を確かめて防ぐ。
- **auto memory の `.md`:** 保護パスの例外で、`blockWritesOutsideWorkingDirectories` でも書けるまま残る。次のセッションの文脈に読み込まれる。ハーネスは「指示ではなく背景情報」として渡すので、`CLAUDE.md` より影響は小さいと考える（推測）。
- **作業ディレクトリの中の、人間が実行するもの:** `package.json` の scripts、Makefile、テストのスクリプトなど。人間が自分で実行を選ぶものなので、この作業の範囲外にする。
- **作業ディレクトリの中の保護パス:** `.vscode`・`.mcp.json` などは、auto mode では判定に回るだけ。plan では `.git` の hooks だけを deny にする。

<a name="review-gaps"></a>

### 8.1 /review で見つかった、規則の外の経路（D9）

2026-11-16 の /review（adversarial と red team のサブエージェント）で見つかった。どれもこの作業が持ち込んだものではない。実測していないものは「未確認」と書く。

- **git の index 経由の mise の設定（未確認）:** sandbox の中から `git hash-object -w` と `git update-index --cacheinfo`（または `git commit`）で、作業ツリーに触れずに、mise の設定の中身を index やブランチに入れられる見込み。人間が `git restore`・`checkout`・`pull` などを実行したときに、sandbox の外で書かれる。dotfiles の `./mise.toml` にも前からある経路。
- **mise の設定を追跡しているリポジトリの git 操作（未確認）:** `~/**/mise.toml` などの denyWrite のため、sandbox の中の checkout・switch・merge・rebase・pull は、mise の設定の書き換えで EPERM になり、途中で止まる見込み。git は HEAD と index を進めるので、古いファイルが変更ありに見え、続く `git add -A` で上流の変更を戻すおそれがある。該当するのは、sf_hpf_metadata・land_match_poc・hpf_login_guide・rplus_net の `mise.toml` と、sf_conn_api_spec の `.tool-versions`。グローバルの CLAUDE.md に、止まって報告するよう書いた。
- **ハードリンクと大文字・小文字（未確認）:** パスで決める規則（sandbox の denyWrite と Edit の規則）を、ハードリンクや `MISE.TOML` のような名前で抜けられるか。
- **権限の規則から変換された denyRead・denyWrite の `**/`（未確認）:** `Read(**/.ssh)`・`Edit(**/.env*)` などが、sandbox で作業ディレクトリに効くか（[test-report 7 章](test-report.md#not-verified)）。env-zsh（`config/sheldon/plugins.toml`）は、cd のたびに `.env` と `.env.term` を信頼の確認なしで読み込むので、mise と同じく守る対象になる。
- **git の設定と hooks のほかの置き場所:** submodule の `.git/modules/*/config` と `hooks`、worktree の `config.worktree`、`claude -w` の worktree の `.git` ファイル（gitdir を書き換えられる）、作業ツリーの中の bare リポジトリ、`core.hooksPath` が作業ツリーの中を指すリポジトリ（husky、`.githooks` など。2026-11-16 の時点で、`~/Dev` の深さ 4 までにはない）。
- **sandbox の外で動くものから呼ばれるファイル:** `.claude/settings.json` の hooks が呼ぶスクリプトと、mise の設定の `_.source`・`[hooks]`・`_.path` が指すファイル。設定ファイル本体だけを守っても、参照先は書ける。
- **元のチェックアウトから worktree の `claude/`:** 元のチェックアウトのセッションでは、プロジェクト設定の `Edit(/claude/**)` と denyWrite の `./claude` が、`.claude/worktrees/<name>/claude/` に当たらない。
- **起動したディレクトリ:** `~` や `~/Dev` で起動すると、すべてのリポジトリが作業ディレクトリに入り、`blockWritesOutsideWorkingDirectories` が効かない。Ghostty の新しいウィンドウは `~/Dev` で開く（`ghostty/config` の `working-directory`）。グローバルの CLAUDE.md に、最初に人間に伝えるよう書いた。
- **`*.pem` の範囲:** `~/Dev` と作業ディレクトリの外の `.pem`（`~/Downloads` の EC2 のキーペアなど）は読める。CA 証明書の束を巻き込まない範囲（`~/Downloads/**` など）に絞って足す案がある。
- **`~/.gstack/projects` の symlink（未確認）:** sandbox の allowWrite に入っているので、Bash で中身を消し、`~/Library/LaunchAgents` などへの symlink に差し替えられる見込み。次のセッションがそのパスを実体に解決すると、sandbox（allowWrite）と Edit・Write ツール（`additionalDirectories`、D7）のどちらからも、ログイン時に動く場所に書けるおそれがある。allowWrite はこの作業の前からある（2 回目の /review の adversarial が指摘、D11）。
- **接頭辞のない hooks の deny の副作用:** Edit の deny は sandbox の denyWrite にもなるので、起動したディレクトリの中では、入れ子のリポジトリの `git init`・`git clone` と、`hooks` という名前の階層を含む refs（`fix/hooks/x` のようなブランチ）への書き込みが、sandbox の中で失敗しうる。2026-11-16 の時点で、dotfiles の refs にも `~/Dev` の submodule にも該当はない。

<a name="next-candidates"></a>

### 8.2 次の作業の候補

1. **mise の paranoid:** 信頼を、設定ファイルの中身のハッシュに結び付ける。Edit・Bash・git の index・ホームの外・`/add-dir` の経路を、まとめて塞げる見込み。代わりに、mise の設定を変えるたびに人間の `mise trust` が要る。採るなら、denyWrite を外して git の巻き込みをなくす案もある。
2. **`~/.gstack/projects` の symlink:** ダミーで確かめる。成り立つなら、SessionStart のフックで実体のディレクトリかを確かめる案か、allowWrite と `additionalDirectories` から外す案。
3. **ハードリンクと大文字・小文字のダミーでの確認。**
4. **権限の規則から変換された `**/` の確認**（env-zsh の `.env` を含む）。
5. **git の設定と hooks のほかの置き場所**（submodule、`.git` ファイル、`core.hooksPath`、`safe.bareRepository`）。Edit の deny は sandbox の denyWrite にもなるので、PreToolUse のフックで拒否する案も比べる。
6. **元のチェックアウトから worktree の `claude/`。**
7. **`*.pem` の範囲。**

<a name="not-verified"></a>

## 9. 未確認のこと

この章を書いた時点で未確認だった項目。どれも、後の Task で確かめた。

| 項目 | 理由 | 結果 |
| --- | --- | --- |
| 元のチェックアウトの `claude/settings.json` を、`blockWritesOutsideWorkingDirectories` が止めるか | 試験は worktree で行った | 確認の画面なしで拒否された（[test-report の T9](test-report.md#human-sessions)） |
| `Read(~/**/credentials)` がディレクトリの中身まで止めるか | 試験用のファイルの作成が拒否された | 中身まで止まる（[test-report 4.1](test-report.md#measure-credentials)） |
| sandbox の `denyWrite` の `~/**/` の形が、作業ディレクトリの中に効くか | `**/` の形は効かなかった（[3.5](#probe-sandbox-anchor)） | 効く（[test-report の T6](test-report.md#human-sessions)） |
| `Edit(**/.git/**/hooks/**)` のように、途中に `**` を置いた規則が、`.git/hooks` に当たるか | 未実施 | 両方の深さに当たる（[test-report の T4](test-report.md#human-sessions)） |
| `claude -w` の worktree で `git branch -m` が使えるか | EnterWorktree の worktree でだけ試した | 名前は変わるが、終了コードは 128（[test-report 4.2](test-report.md#measure-branch-rename)） |
