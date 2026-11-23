---
status: done
created: 2026-11-18
---

# git を経由した書き換えの経路の調査

sandbox の中で作った git の状態（コミット・ref・index・stash）は、人間が sandbox の外で git を操作すると、作業ツリーに書かれる。書かれたファイルが、sandbox の外で自動で読み込まれたり動いたりするものなら、その中身が sandbox の外で効く。この経路への対策を比べるための調査。設定は変えていない。

関連: [前回の design の 2 章（非目標の 1 つ目）](../20261116_sandbox-path-gaps/design.md#goals)と [7 章](../20261116_sandbox-path-gaps/design.md#accepted-risks)、[前回の test-report の 4 章](../20261116_sandbox-path-gaps/test-report.md#review)、[前々回の research の 8 章](../20261114_edit-write-rules/research-edit-write.md#residual-risks)、[sandbox-runtime が既定で守るもの](../20261113_sandbox-escape-hardening/research-sandbox-escape.md#mandatory-deny)

<a name="scope"></a>

## 1. 範囲

2026-11-18 に人間と決めた。

| 候補 | 扱い |
| --- | --- |
| 本題: git を経由した書き換え（すべてのリポジトリの自動で読み込まれるファイルと、dotfiles のリンクで使われるファイル） | 含める |
| 前々回の research の 8.2 の 5 のうち、worktree の `.git` ファイルと `config.worktree` | 含める。submodule・bare リポジトリ・`core.hooksPath` は、今あてはまるものがあるかだけを確かめる |
| `mise.lock` と provenance | research で判断する |
| check-repo の `trusted_config_paths` の検査 | 含める |
| ユーザー設定の `Edit(/etc/**)` の起点 | 独立したコミットで含める |
| 8.2 の 6（元のチェックアウトから見た worktree の `claude/`） | 本題に吸収する |
| `_.path`、`~/.gstack/projects` の根の rename、guard フックの matcher、8.2 の 7（`*.pem`） | 後回し |

<a name="method"></a>

## 2. 方法

- **sandbox の境界:** Claude Code 2.1.326 の `claude -w git-route` のセッションの Bash で、2026-11-18 に測った。効いている規則は、元のチェックアウトの main（1a3cfe4）のユーザー設定。
  - 既存のファイルは、0 バイトの追記（`: >> <ファイル>`）で書けるかを見た。中身は変わらない。
  - 新しいファイルは `cc-probe` という名前で作り、すぐ消した。
  - 置き換えは、同じ中身の複製を `mv` で重ねて試した。
- **git のフック:** git 2.56.1。このセッションからは、worktree を守るフックが一時ディレクトリでの git を止める。そのため、人間が普段のターミナルでスクリプト（`tmp/r2-git-hooks.sh`。Git の管理外）を 2 回実行した。動いたフックと作業ツリーの結果は、2 回とも同じだった。
  - mktemp のディレクトリの中だけで動かし、ユーザーとシステムの git の設定は読ませなかった。
  - `core.hooksPath` に、呼ばれたことを記録するだけのフック（post-checkout・post-merge・post-rewrite・post-index-change）を置いた。
  - 用意した状態: main（`a.txt` が 1）と feature（`a.txt` が 2、`.env` を追跡）。
  - 「index から書く」操作は、`git update-index --cacheinfo` で、作業ツリーに触れずに index の `a.txt` だけを 3 にしてから実行した。sandbox の中でもできる操作。
- **公式ドキュメント:** Claude Code（code.claude.com）と mise（mise.jdx.dev）を、サブエージェントが読んだ。Claude Code の引用は、取得の道具がモデルで抜き出した文で、原文とは照らし合わせていない（sandbox の curl は拒否された）。

<a name="results"></a>

## 3. 結果

<a name="results-sandbox"></a>

### 3.1 sandbox から書ける git の状態

| 対象 | 結果 |
| --- | --- |
| `~/dotfiles/.git/index`（元のチェックアウトの index） | 書ける |
| `~/dotfiles/.git/HEAD` | 書ける |
| `~/dotfiles/.git/refs/heads/main` | 書ける |
| `~/dotfiles/.git/info/`（`exclude` と新しいファイル） | 書ける |
| `~/dotfiles/.git/worktrees/git-route/index` | 書ける |
| `~/dotfiles/.git/config` | 拒否 |
| `~/dotfiles/.git/hooks/` に新しいファイル | 拒否 |
| worktree の `.git` ファイル（追記と、同じ中身での置き換え） | 拒否 |
| `~/dotfiles/.git/worktrees/git-route/gitdir`・`commondir` | 拒否 |
| `~/dotfiles/.git/worktrees/git-route/config.worktree` の作成 | 拒否 |
| 作業ツリーの下のディレクトリに、`.git` という名前のファイルを作る | 書ける（2026-11-18。作ってすぐ消した） |
| `~/dotfiles/.git/modules/<名前>/config` の作成 | 書ける（2026-11-18。作ってすぐ消した） |

- **worktree のセッションからでも、元のチェックアウトの index・HEAD・ローカルの main を書き換えられる（事実）。** objects も書ける（これまでの作業で、sandbox の中からコミットしている）。
- そのため、「元のチェックアウトにはレビュー済みの main しか置かない」という運用では足りない。人間が触れていなくても、ローカルの main や index は変わりうる。
- git に別の設定を読ませる経路のうち、このリポジトリと worktree のもの（gitdir の差し替え、`config.worktree`、`config`、`hooks`）は、sandbox が止めていた。`extensions.worktreeConfig`・`core.hooksPath`・`core.fsmonitor` は設定されていない（`git config` で確かめた）。
- ただし、入れ子のリポジトリの設定は書ける（上の表の最後の 2 行）。作業ツリーの下に `.git` ファイルを置き、sandbox が書ける gitdir（`.git/modules/<名前>` など）を指せば、その中の `config` は守られない。人間の git がそのディレクトリで動くと、`core.fsmonitor`・`core.pager` などが sandbox の外で動く見込み（git の仕様からの推測。動くかは試していない）。index に gitlink を足せば、元のリポジトリでの `git status` が submodule の中に入る見込みもある（推測）。作業ツリーの中の bare リポジトリ（`config` という名前のファイル）も、git が見つける見込み（`safe.bareRepository` は既定で `all`。推測）。

<a name="results-hooks"></a>

### 3.2 作業ツリーに書く git の操作と、動くフック

`post-index-change` の列は、1 つ目の引数（作業ツリーを更新したか）が 1 の呼び出しがあったかを示す。「0 だけ」は、呼ばれたが引数が 0 だったもの。

| 操作 | 作業ツリーの結果 | post-checkout | post-merge | post-rewrite | post-index-change |
| --- | --- | --- | --- | --- | --- |
| `switch feature` | 2、`.env` あり | 動く | — | — | 1 |
| `checkout feature` | 2、`.env` あり | 動く | — | — | 1 |
| `checkout feature -- a.txt` | 2 | 動く（flag 0） | — | — | 0 だけ |
| `restore --source=feature a.txt` | 2 | 動く（flag 0） | — | — | 呼ばれない |
| index から `restore a.txt` | 3 | 動く（flag 0） | — | — | 0 だけ |
| index から `checkout -- a.txt` | 3 | 動く（flag 0） | — | — | 0 だけ |
| index から `checkout-index -f -a` | 3 | — | — | — | 呼ばれない |
| `reset --hard feature` | 2、`.env` あり | — | — | — | 1 |
| `reset --merge feature` | 2、`.env` あり | — | — | — | 1 |
| `read-tree -u -m HEAD feature` | 2、`.env` あり | — | — | — | 1 |
| `merge --ff-only feature` | 2、`.env` あり | — | 動く | — | 1 |
| `merge --no-edit feature`（分岐あり） | 2、`.env` あり | — | 動く | — | 1 |
| `pull --ff-only . feature` | 2、`.env` あり | — | 動く | — | 1 |
| `rebase feature`（分岐あり） | 2、`.env` あり | 動く | — | 動く | 1 |
| `cherry-pick feature` | 2、`.env` あり | — | — | — | 1 |
| `revert HEAD`（feature の上で） | 1、`.env` なし | — | — | — | 1 |
| `stash push` | 1 | — | — | — | 1 |
| `stash apply` | 5 | — | — | — | 1 |
| `stash pop` | 5 | — | — | — | 1 |
| `worktree add <dir> feature` | 新しいディレクトリに 2、`.env` あり | 動く | — | — | 1 |
| `clone -b feature` | 新しいディレクトリに 2、`.env` あり | 動く | — | — | 1 |

- **1 つのフックで、すべての操作を拾えるものはない（事実）。** post-checkout・post-merge・post-index-change の 3 つを合わせても、`checkout-index` は拾えない。
- `post-index-change` の作業ツリーの引数は、パスを指定した checkout と restore では 0 のままだった（事実）。この引数だけでは判定できない。
- post- のフックは、作業ツリーを書いた後に呼ばれる（git のフックの仕様）。
- index から書く 3 つの操作（`restore`・`checkout --`・`checkout-index`）は、sandbox の中で index だけを変えておけば、人間の操作でその中身が作業ツリーに出る（事実。ダミーで再現）。

<a name="results-bang"></a>

### 3.3 `!` が動く場所

- `claude -w` のセッションの `!` は、worktree で動いた（`pwd` が `~/dotfiles/.claude/worktrees/git-route`。2026-11-18 に人間が実行）。公式ドキュメントには、どこで動くかの記載がない。sandbox の外で動くことは書かれている。
- `!` のコマンドで PreToolUse などのフックが呼ばれるかは、文書にない（未確認）。
- 人間が普段のターミナルで打つ git は、そのときのカレントディレクトリで動く。2026-11-18 に、worktree のブランチ名を変えるつもりで頼んだ `git branch -m` が、人間の普段のターミナルで `~/dotfiles` の main の名前を変えた（その後に戻した）。頼むときは、`git -C <パス>` で対象を明示する必要がある。
- `!` と Bash ツールの環境（2026-11-18 に実測。`!` は人間が実行した）:

  | | 標準入力 | `SANDBOX_RUNTIME` | `CLAUDECODE` | `.zshrc` で定義された関数（`prompt_starship_precmd`） |
  | --- | --- | --- | --- | --- |
  | Bash ツール | 端末ではない | ある | ある | ある |
  | `!` | 端末ではない | ない | ある | ある |

  - `.zshrc` に git の関数を置くと、どちらでも定義される見込み（推測。starship の関数と同じく、シェルのスナップショットに入る）。
  - `!` では、標準入力から答えを読めない。

<a name="results-inventory"></a>

### 3.4 自動で読み込まれたり動いたりするファイル

直接の書き込みは、sandbox-runtime が名前で守るもの（`.zshrc`・`.mcp.json` など）と、denyWrite が守るもの（`claude/` の下など）がある。git を経由すると、書くのは sandbox の外で動く人間の git なので、どちらの守りも効かない（sandbox は、中で動くプロセスだけを縛る）。

**すべてのリポジトリ**

| ファイル | いつ効くか | 直接の書き込みへの今の守り |
| --- | --- | --- |
| `.env*` | cd のたびと zsh の起動時に、env-zsh が `source` する（[前回の research](../20261116_sandbox-path-gaps/research-path-gaps.md#method)） | `Edit(**/.env*)` の deny（sandbox の denyWrite にもなる） |
| `.claude/settings.json`・`settings.local.json` | セッションの起動時。動いているセッションも、変更を監視して読み直す（hooks を含む。3.5） | sandbox の denyWrite（このセッションの設定に出ている） |
| `.claude/hooks/` など、hooks が呼ぶスクリプト | 呼ばれるたびに読む | `.claude/hooks` は sandbox の denyWrite。ほかの場所は守りなし |
| `.mcp.json` | セッションの起動時。サーバーごとに承認がいる | sandbox-runtime が既定で守る |
| mise の設定（`mise.toml`・`.tool-versions` など） | cd のたび | paranoid（中身で信頼する） |
| `mise.lock` | 設定と一緒に読まれ、インストールで使われる（3.6） | なし（paranoid の `config` の対象外） |

**dotfiles のリンクで使われるファイル**（`*/link.sh`・`*/setup.sh` から）

| ファイル | 置き先 | いつ効くか |
| --- | --- | --- |
| `claude/settings.json` | `~/.claude/settings.json` | セッションの起動時と、変更のたび（動いているすべてのセッション） |
| `claude/hooks/` | `~/.claude/hooks` | ツールの呼び出しのたび（動いているすべてのセッション） |
| `claude/CLAUDE.md`・`claude/rules/` | `~/.claude/` | セッションの起動時（rules は、`paths` に当たるファイルを読んだとき） |
| `claude/mcp.json` | `~/.claude/mcp.json` | 読まれるかは未確認 |
| `claude/scripts/statusline.sh` | `~/.claude/scripts/` | ステータスラインを更新するたび |
| `mise/mise_config.toml` | `~/.config/mise/config.toml` | プロンプトのたび（`mise activate`）。paranoid でもパスで信頼される |
| `bin/.zshrc`・`bin/.zprofile` | `~/` | zsh の起動時 |
| `bin/.gitconfig`・`bin/.gitconfig_numm` | `~/` | git のコマンドのたび（alias・`core.*`。`.gitconfig_numm` は `~/Dev/numm/` の下で `includeIf` で読む） |
| `config/sheldon/plugins.toml` | `~/.config/sheldon/` | zsh の起動時（プラグインを読み込む） |
| `zsh/*.zsh`（`sync.zsh` を除く） | リンクしない。sheldon が `~/dotfiles/zsh` から直接読む（`plugins.toml` の `dotfile-defers`） | zsh の起動の後（zsh-defer で遅らせて `source` する） |
| `config/starship/starship.toml` | `~/.config/` | プロンプトのたび（`custom` モジュールはコマンドを実行する。今は使っていない） |
| `config/uv/uv.toml` | `~/.config/uv/` | uv の実行時（パッケージの取得先） |
| `config/sf/`（`plugins.txt`・`sync-plugins.sh`・`unsignedPluginAllowList.json`） | `~/.config/sf/` | 人間が同期を実行したときと、sf の実行時 |
| `vscode/settings.json`・`keybindings.json`・`tasks.json` | VS Code のユーザー設定 | 動いている VS Code に、その場で |
| `ghostty/config` | `~/.config/ghostty/` | Ghostty の起動時 |
| `codex/AGENTS.md` | `~/.codex/AGENTS.md` | Codex の実行時（Codex のレビューへの指示になる） |
| `biome/biome.jsonc`・`obsidian/` の下 | 各アプリの設定 | アプリが読んだとき（コードを動かす項目があるかは確かめていない） |

- 直接の書き込みは、dotfiles のプロジェクト設定（`.claude/settings.json`）の denyWrite が止める。対象は `./claude`・`./zsh`・`./config`・`./mise`・`./bin` など 16 項目で、上の表のディレクトリをすべて含む（2026-11-18 に設定を読んで確かめた）。worktree のセッションでは、元のチェックアウトはそもそも書き込みの範囲の外にある（このセッションの sandbox の設定）。
- `bin/.gitconfig` の alias に、作業ツリーに書くもの（`co = checkout`・`sw = switch`）がある。`pull.ff = only`、`merge.ff = false`。

<a name="results-claude-code"></a>

### 3.5 Claude Code の仕様（公式ドキュメント）

サブエージェントの要約で、原文とは照らし合わせていない（[2 章](#method)）。

- **パスの起点**（`permissions`）: ユーザー設定の `/path` は `~/.claude/path` を指す。絶対パスは `//path` と書く。そのため、ユーザー設定の `Edit(/etc/**)` は `~/.claude/etc/**` に当たる。
- **sandbox への変換**（`sandboxing`）: 権限の規則のパスは、sandbox の設定に合わせて入る。ユーザー設定の `/path` の Edit の規則が、どのパスの denyWrite になるかは書かれていない。
- **設定の読み直し**（`settings` の「When edits take effect」）: 設定ファイルを監視し、変わったら読み直す。動いているセッションにも、`permissions` と `hooks` の変更を含めて、再起動なしで効く。
- **信頼の確認**（`permissions` の「What runs before you trust a folder」）: 設定ファイルの hooks は、フォルダーを信頼する前から使われる。ワークスペースの信頼の確認が対象にするのは、プロジェクトの `.claude/settings.json` の `permissions.allow` と `additionalDirectories`。ファイルが変わったときに確認し直すかは、書かれていない。
- **`ConfigChange` フック**（`security`）: セッション中の設定の変更を、記録したり止めたりできる。
- **`.mcp.json`**（`mcp`・`settings-reference`）:
  - プロジェクトのサーバーは、対話のセッションで、使う前に承認を求める。サーバーのコマンドが変わったときに承認を求め直すかは、書かれていない。
  - `disabledMcpjsonServers` は、どの設定ファイルに書いても効く。
- **`!`**（`sandboxing`）: sandbox の外で動く。

<a name="results-mise"></a>

### 3.6 mise（公式ドキュメント）

mise は 2026.11.9。

- **`mise.lock` の中身**（`mise-lock-reference`）: ツールごとの版と、プラットフォームごとの `url`・`checksum`・`provenance` など。
- **信頼との関係**（`security`）:
  - `mise.lock` は、その設定ファイルと一緒に読まれる。
  - 設定が信頼されるまでは、lock は版と checksum を決めるだけで、取得はバックエンドが普段使う場所から行う。
  - 信頼された設定では、lock の URL から取得する見込み（推測。`locked` でないときについての明記はない）。
- **`locked`:** 版と URL を lock から取ることを必須にする。
- **paranoid の `provenance`:**
  - インストールのたびに provenance を確かめ直す。インストール済みのツールは確かめ直さない。
  - これがないと、`mise install` は lock を信じて provenance を確かめない。
  - 書き換えた URL や checksum を見つけるかは、書かれていない。
- **`yes`:** 信頼の確認にも答えるが、paranoid のときは答えない。
- **`trusted_config_paths`:** paranoid でも、その下の設定を中身によらずに信頼する。グローバルの設定でだけ効く。
- **自動のインストール:**
  - `auto_install`・`exec_auto_install`・`task.run_auto_install`・`not_found_auto_install` は、どれも既定で有効。
  - shim は、設定の版が入っていなければインストールする。
- **手元:** `~/Dev` と `~/dotfiles` の深さ 4 までに `mise.lock` はない（2026-11-18 に実測）。

<a name="results-other-git"></a>

### 3.7 git の設定と hooks のほかの置き場所（8.2 の 5）

- worktree の `.git` ファイル・gitdir・`config.worktree` は、sandbox から書けない（[3.1](#results-sandbox)）。
- `~/Dev` の深さ 4 までに `.gitmodules` はなく、深さ 5 までの `.git/config` に `hooksPath`・`fsmonitor`・`worktreeConfig` はない。dotfiles にも `.gitmodules` はない（2026-11-18 に実測）。

<a name="results-drift"></a>

### 3.8 アプリが書く設定（コピーで置いたときのずれ）

- `claude/settings.json` は、2026-11 だけで 34 回コミットされている。変えたら新しいセッションですぐ確かめる流れ（前回の design の C1）で作業している。
- Claude Code 自身も `claude/settings.json` に書く（前回の design の C3。`switchModelsOnFlag` の追加とキーの並べ替え）。
- VS Code と Obsidian の設定は、アプリの画面から書かれる（推測）。

<a name="results-claude-worktree"></a>

### 3.9 `claude -w` の作成元

公式ドキュメント（`worktrees`・`hooks`・`settings`・`permissions`）を、サブエージェントが読んだ要約。原文の引用はあるが、私は原文と照らし合わせていない。

- **作成元**（`worktrees`）:
  - `worktree.baseRef` で決まる。既定は `fresh` で、リモートの既定ブランチ（`origin/HEAD`）から作る。もう 1 つの値は `head`（ローカルの `HEAD`）。ブランチ名は指定できない。
  - 24 時間以内に fetch していなければ、既定ブランチを fetch する（5 秒まで）。失敗したら、ローカルに記録されている ref を使う。`origin/HEAD` の記録がなく、fetch もできなければ、ローカルの `HEAD` から作る。
- **`WorktreeCreate` フック**（`hooks`）:
  - 作成そのものを置き換える。フックが失敗するか、パスを返さなければ、作成は失敗する。入力に `name` がある。
  - このフックを使うと、`.worktreeinclude` は処理されない。Bash で実行した `git worktree add` では呼ばれない。
- **新しい worktree のセッション**（`settings`・`permissions`）:
  - そのセッションの作業ディレクトリの `.claude/settings.json` を読む。
  - worktree の信頼は、元のチェックアウトのルートの信頼を使う。
- **`.worktreeinclude`**（`worktrees`）: パターンに合い、gitignore されているファイルを、元のチェックアウトから新しい worktree にコピーする。

手元で確かめたこと（2026-11-18）:

- sandbox から `~/dotfiles/.git/refs/remotes/origin/` に書けた（ref にならない名前のファイルで試し、すぐ消した）。
- ユーザー設定とプロジェクト設定に `worktree.baseRef` はない（既定の `fresh`）。
- `~/dotfiles` に `.worktreeinclude` はない。

<a name="implications"></a>

## 4. 設計への含意（推測と提案）

1. **書かれた後に動くフック（前々回の返信の案 B）は、守りの中心にならない。**
   - 1 つのフックでは足りず、3 つ合わせても `checkout-index` を拾えない（[3.2](#results-hooks)）。
   - Claude Code の設定と hooks のスクリプトは、書かれた時点で、動いているセッションに効く（[3.4](#results-inventory)・[3.5](#results-claude-code)）。警告は間に合わない。
   - すべてのリポジトリに効かせるには、グローバルの `core.hooksPath` が要る。そうすると、各リポジトリの `.git/hooks` が無効になる。
2. **確かめるのは書く前にし、確かめるコードは sandbox から書けない場所に置く（案 C か案 A）。**
   - sandbox は index・HEAD・ローカルの main を書けるので（[3.1](#results-sandbox)）、変わるファイルは、確かめる時点の状態から計算する必要がある。Claude が前もって出した一覧は信用できない。
   - 作業ツリーに書く操作は多い（[3.2](#results-hooks) の 21 個）。git のすべてを包むのは難しいので、次のどちらかを design で決める。
     - 包む操作を、人間が頼まれて実行するもの（switch・merge・pull・restore・reset・stash）に絞る。
     - 操作によらず、実行の前に「今の作業ツリーと、操作の後になる tree（または index）」の差を見せる確認のコマンドにする。
3. **`!` は worktree で動く（[3.3](#results-bang)）。** Claude が `!` で頼む git の対象は、その worktree になる。元のチェックアウトの作業ツリーが書かれるのは、人間がそこで git を打つとき（`git pull` など）。
4. **dotfiles のコピー（案 A）には、ずれの問題がある。**
   - アプリが書く設定は、毎回ずれる。設定を変えてすぐ確かめる今の流れ（2026-11 だけで 34 回）も変わる（[3.8](#results-drift)）。
   - 実行されるファイルに絞るなら、候補は `claude/hooks`・`claude/settings.json`・`bin/.zshrc`・`bin/.zprofile`・`bin/.gitconfig`・`mise/mise_config.toml`・`config/sheldon`・`config/starship`。
   - ただし、`claude/settings.json` は Claude Code が書くので、絞ってもずれは残る。
5. **Claude Code の設定には、`ConfigChange` フックが、動いているセッションへの備えになる見込み（未確認）。** 外からのファイルの変更（git の操作）で呼ばれ、止められるかを確かめる必要がある。
6. **`mise.lock`:**
   - 信頼された設定のプロジェクトで lock を変えると、取得先と checksum をまとめて変えられる。次の自動インストール（shim・`mise exec`・`mise run`）で、sandbox の外でインストールされる見込み（推測）。
   - 手当ての候補は 3 つ。確かめる対象の一覧に `mise.lock` を入れる。paranoid に `provenance` を足す（attestation のあるツールにだけ効く）。自動のインストールを止める。
   - 今のリポジトリには lock がない（[3.6](#results-mise)）。
7. **`Edit(/etc/**)` は `~/.claude/etc/**` を指している（[3.5](#results-claude-code)）。**
   - `/etc` を指すなら `Edit(//etc/**)` と書く。
   - ただし、`/etc` は root でないと書けず、作業ディレクトリの外は `blockWritesOutsideWorkingDirectories` も止める。直しても、守りはほとんど増えない。消すか直すかを design で決める。
8. **`trusted_config_paths` は、paranoid の中身での信頼を飛ばす。** check-repo で、グローバルの mise 設定にないことを確かめる。`yes` は paranoid では信頼の確認に答えないので、検査は要らない。
9. **`claude -w` は、zsh を通らずに、sandbox が書ける ref から作業ツリーを作る（[3.9](#results-claude-worktree)。推測を含む）。**
   - sandbox は `refs/remotes/origin/` を書ける。`origin/HEAD` を、fetch で上書きされない名前の ref に向けることもできる。そうすると、次の `claude -w` の worktree は、sandbox が作ったコミットになる。
   - 新しいセッションは、その worktree の `.claude/settings.json`（hooks を含む）を、元のチェックアウトの信頼のもとで読む見込み。
   - zsh の `git` 関数は、この経路を通らない。`WorktreeCreate` フックなら、作成を自分で行い、使われる前に確かめられる。
10. **`.worktreeinclude` は、読み取りの経路になりうる（推測）。** gitignore されたファイル（`aws/config` など）を worktree にコピーする。コピー先は、パスで指定した denyRead に当たらない。元のチェックアウトのルートに `.worktreeinclude` を置く必要があり、元のチェックアウトで起動したセッションなら sandbox から置ける。書き込みの経路ではないので、この作業の範囲の外。

<a name="not-verified"></a>

## 5. 確かめていないこと

- Claude Code の引用と、原文との照合（curl が拒否された）。
- `.mcp.json` のサーバーのコマンドが変わったときに、承認を求め直すか。
- `ConfigChange` フックが、外からのファイルの変更（git の操作）で呼ばれ、止められるか。
- `!` のコマンドで PreToolUse などのフックが呼ばれるか。
- 信頼された設定で `mise.lock` の URL が使われるか。provenance が書き換えた lock を見つけるか。
- `~/.claude/mcp.json` を Claude Code が読むか。
- VS Code の `tasks.json` が自動で動く設定（`runOn: folderOpen`）と、Obsidian・biome の設定に、コードを動かす項目があるか。
- 人間のほかに（IDE の自動の pull など）、sandbox の外で git を動かすものがあるか。人間は、zsh で打つ git のほかは使っていない（2026-11-18、人間の回答）。`claude -w` は [3.9](#results-claude-worktree)。
- `claude -w` が「24 時間以内に fetch したか」を何で判断するか。同じ名前の worktree を開き直すときに `WorktreeCreate` が呼ばれるか。新しい worktree の `.claude/settings.json` の hooks が、実際に信頼の確認なしで動くか。
