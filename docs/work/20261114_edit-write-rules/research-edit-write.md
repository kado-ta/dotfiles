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

<a name="not-verified"></a>

## 9. 未確認のこと

| 項目 | 理由 | 扱い |
| --- | --- | --- |
| 元のチェックアウトの `claude/settings.json` を、`blockWritesOutsideWorkingDirectories` が止めるか | 試験は worktree で行った | plan の Task 7 で確かめる |
| `Read(~/**/credentials)` がディレクトリの中身まで止めるか | 試験用のファイルの作成が拒否された | plan の Task 5 で、人間がファイルを作って確かめる |
| sandbox の `denyWrite` の `**/` の形が、作業ディレクトリの中に効くか | 未実施 | plan の Task 7 で確かめる（D4） |
| `Edit(**/.git/**/hooks/**)` のように、途中に `**` を置いた規則が、`.git/hooks` に当たるか | 未実施 | plan の Task 7 |
| `claude -w` の worktree で `git branch -m` が使えるか | EnterWorktree の worktree でだけ試した | plan の Task 6 で、文書に書く前に人間が確かめる |
