---
status: in-progress
created: 2026-11-18
---

# git を経由した書き換えの守りの設計

sandbox の中で作られた git の中身（コミット・index・ref）が、sandbox の外で動く git によって、自動で読み込まれたり動いたりするファイルとして書かれることがある。その前に、人間が中身を見て止められるようにする。入口は 2 つある。人間が zsh で打つ `git`（普段の端末と `!`）と、Claude Code の `claude -w` である。

関連: [research-git-route.md](research-git-route.md)、[前回の design の非目標 1 と 7 章](../20261116_sandbox-path-gaps/design.md#goals)、[前回の test-report の 4 章](../20261116_sandbox-path-gaps/test-report.md#review)、[前々回の research の 8.2](../20261114_edit-write-rules/research-edit-write.md#residual-risks)

<a name="intent"></a>

## 1. 目的と背景

- **sandbox は `.git` のほとんどを書ける。**
  - 試して書けたのは、objects・index・HEAD・`refs/heads/main`・`refs/remotes/origin/`・`info/` である（[research の 3.1](research-git-route.md#results-sandbox)・[3.9](research-git-route.md#results-claude-worktree)）。
  - sandbox の設定は `.git` 全体を書けるようにしていて、拒否は `config` と `hooks` だけである。そのため、stash・`refs/replace`・途中の操作の状態（rebase の手順など）も書ける見込み（推測。試していない）。
  - 拒否されたのは、`.git/config`・`hooks`・worktree の `.git` ファイル・gitdir・`config.worktree` である。このリポジトリと worktree については、git に別の設定を読ませる経路を sandbox が止めている。
  - ただし、入れ子のリポジトリの設定は書ける。作業ツリーの下の `.git` ファイルと、`.git/modules/<名前>/config` を作れた（[research の 3.1](research-git-route.md#results-sandbox)）。人間の git がその中で動くと、設定からコードが動く見込み（推測）。
- **sandbox の外の git が、その中身を作業ツリーに書く。** 人間の git（普段の端末と `!`）と、`claude -w` の worktree の作成がこれにあたる。書かれるのは、sandbox の外で自動で読み込まれたり動いたりするファイルである（[research の 3.4](research-git-route.md#results-inventory)）。直接の書き込みへの守り（denyWrite、sandbox-runtime が名前で守るもの、Edit の deny）は、sandbox の中のプロセスだけを縛るので、この経路には効かない。
- **書かれた後では間に合わない。** Claude Code は設定ファイルを監視していて、hooks の変更も動いているセッションにその場で効く（[research の 3.5](research-git-route.md#results-claude-code)）。書かれた後に動く git のフックでは拾えない操作もある（[research の 3.2](research-git-route.md#results-hooks)）。
- **今の手当ては、Claude 側の手順だけである。** グローバルの CLAUDE.md に、`!` を頼む前に変わるファイルを確かめて伝える手順がある。仕込んだ側の Claude は、この手順を飛ばせる。

<a name="goals"></a>

## 2. 目標・非目標・反目標

**目標**

- **G1（zsh の `git`）:** 人間が zsh で打った `git` が対象のファイルを書く前に、書かれる中身を確かめる。計算には、そのときの状態を使う。普段の端末では、差分を見せて y/N で確認する（既定は N）。`!` では止めて、普段の端末で打つコマンドを表示する。
- **G2（`claude -w`）:** 新しい worktree の対象のファイルが、元のチェックアウトの同じファイルと一致しないときは、worktree を作らない。
- **G3（守りの守り）:** 確かめるコードと対象の一覧は root 所有に置く。`git` 関数と `WorktreeCreate` フックの登録は、sandbox からの直接の書き込みと、git の経路の両方から守られたファイルに置く。
- **G4（普段の操作）:** 対象のファイルを変えない git の操作は、今までどおり確認なしで動く。
- **G5（検査）:** 関数・フックの登録・対象の一覧・mise の設定が崩れたら、`check-repo.py` が失敗する。
- **G6（小さな項目）:** check-repo で mise の `trusted_config_paths` を拒否する。`mise.lock` を守りの対象に入れる。ユーザー設定の `Edit(/etc/**)` を整理する。

**非目標**

- **zsh で `git` という名前を通らない git:** `command git`・`\git`・`/opt/homebrew/bin/git`、IDE・`gh pr checkout`・lazygit・スクリプトの中の git。人間は、zsh で打つ git のほかは使っていない（2026-11-18、人間の回答）。Claude がこれらの形を `!` で頼まないことは、規則に書く（[6.11](#design-docs)）。
- **sandbox の中の git（Bash ツール）:** 素通りさせる。書き込みは sandbox が縛っていて、関数は `command git` で飛ばせるので、ここで確かめても守りにならない。sandbox の中かどうかは、確認コマンドが OS に問い合わせて判断する（[6.4](#design-check)）。
- **sandbox から直接書けるファイル:** プロジェクトの mise の設定（paranoid が中身で信頼する）や、ほかのリポジトリの `CLAUDE.md` など。git の経路を止めても、直接書けるので守りは増えない。
- **すでにある worktree:** `claude -w` で開き直すときや、`claude --resume` で戻るときは確かめない（[7 章](#accepted-risks)）。
- **`git clone`:** 新しいリポジトリを信頼するかは、人間が決めることとする。
- **`.worktreeinclude` の読み取りの経路**（[research の 4 章の 10](research-git-route.md#implications)）: 書き込みの経路ではないので、次の作業にする。
- **入れ子のリポジトリの設定からコードが動く経路**（[research の 3.1](research-git-route.md#results-sandbox)）: sandbox は、作業ツリーの下の `.git` ファイルと `.git/modules/<名前>/config` を作れる。人間の git がその中で動くと、読むだけのコマンドでも設定からコードが動く見込み。対象のファイルを書く経路ではなく、守り方（グローバルの git の設定、submodule の扱い）も別なので、次の作業の最初にする（2026-11-18、人間の判断）。
- **前回からの後回しの項目:** `_.path`、`~/.gstack/projects` の根の rename、guard フックの matcher、`*.pem` の範囲。前々回の research の 8.2 の 5（worktree の `.git` ファイルと `config.worktree`）は、sandbox が止めていたので、手当ては要らない（[research の 3.7](research-git-route.md#results-other-git)）。8.2 の 6（worktree の `claude/`）は、[6.2](#design-target-list) の対象の一覧に吸収した。

**反目標**（技術的に動いても、こうなったら失敗）

- Claude が承認を作れる。承認の値が会話に出たり、人間に貼らせたりできる。
- 対象のファイルを変えない普段の git で確認が出る。確認が多いと、読まずに y を押すようになる。
- 確認コマンドそのものが、リポジトリの設定やファイルからコードを動かす（`core.fsmonitor`・textconv・外部 diff・フック・ページャ）。
- 確認コマンドが入っていないと、確かめずに git が動く。
- Claude の普段の git（sandbox の中）が止まる。

<a name="constraints"></a>

## 3. 制約

- **C1（効く時点）:** この作業は worktree で行う。`~/.claude/settings.json`・`~/.zshrc` のリンク先は元のチェックアウトなので、マージして元のチェックアウトに取り込むまで、変更は効かない。
- **C2（Claude が書けないもの）:** `claude/settings.json` は、Claude からは編集できない（`blockWritesOutsideWorkingDirectories`）。Claude が変更を用意し、人間が当てる。root 所有の場所へのインストールは、人間が `sudo` で行う。
- **C3（名前に「git」を入れない）:** worktree を守るフックは、コマンドに「git」が複数あると拒否する。パスの中の「git」も数える。一時ディレクトリでの git も拒否する。新しいファイルの名前に「git」を入れない。そうしないと、Claude がテストを実行できない。テストの中の git は、Python の中から呼ぶ。
- **C4（`!` と Bash ツールの環境）:** [research の 3.3](research-git-route.md#results-bang) の表のとおり。`!` は標準入力が端末でないので、y/N を聞けない。`SANDBOX_RUNTIME` があるのは Bash ツールだけだが、`!` でも `SANDBOX_RUNTIME=1 git …` と打てば作れる。そのため、sandbox の中かどうかの判断には使わない。
- **C5（版）:** git は 2.56.1（Homebrew。人間と sandbox が使う）と 2.54.0（Command Line Tools）。Claude Code は 2.1.326。mise は 2026.11.9。
- **C6（git の設定）:** `bin/.gitconfig` の alias に、作業ツリーに書くもの（`co = checkout`・`sw = switch`）がある。`pull.ff = only`、`merge.ff = false`。`filter.lfs` が `required = true` で定義されている。
- **C7（`claude -w`）:** 作り方は文書の要約による（[research の 3.9](research-git-route.md#results-claude-worktree)）。原文とは照らし合わせていない。
- **C8（macOS のファイルシステム）:** 大文字と小文字を区別しない。Unicode の正規化の違うパスを、同じファイルとして扱う。

<a name="approaches"></a>

## 4. 進め方

**守り方**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| A | dotfiles のリンクをやめて、コピーで置く | 不採用。アプリが書く設定がずれる（`claude/settings.json` は 2026-11 だけで 34 コミット。[research の 3.8](research-git-route.md#results-drift)）。ほかのリポジトリには効かない |
| B | 書かれた後に動く git のフックで警告する | 不採用。拾えない操作があり、Claude Code の設定には間に合わない（[research の 4 章の 1](research-git-route.md#implications)） |
| C | 書く前に、root 所有のコマンドで確かめる | **採用**（2026-11-18、人間の判断） |

**C の形**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| 1 | 人間が確認コマンドを明示して打ち、続けて git を打つ | 不採用。仕込んだ側の Claude は、確認を頼まずに `! git switch` だけを頼める |
| 2 | 人間の zsh の `git` を関数で包み、作業ツリーに書く前に確認コマンドを呼ぶ | **採用**（2026-11-18、人間の判断） |

**対象のファイルが変わるときの扱い**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| a | 普段の端末では、差分を見せて y/N（既定は N）。`!` では止めて、普段の端末で打つコマンドを表示する | **採用**（2026-11-18、人間の判断） |
| b | a と同じ。ただ、`!` では、表示した差分に結び付いた承認の値を付けて再実行できる | 不採用。承認の値が会話に出るので、Claude が人間に貼らせられる |
| c | 警告だけで止めない | 不採用。読み飛ばすと守れない |

**`claude -w`**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| 1 | `WorktreeCreate` フックで、worktree を自分で作り、使われる前に元のチェックアウトと比べる | **採用**（2026-11-18、人間の判断） |
| 2 | 範囲の外にして、受け入れるリスクにする | 不採用。いちばん使う入口が残る |
| 3 | zsh で `claude` を包み、作成元を予測して確かめる | 不採用（私の判断）。Claude Code の内部の判断（24 時間の fetch、記録がないときの戻り先）を真似る必要があり、壊れやすい |

**sandbox の中かどうかの判断**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| 1 | 関数は常に確認コマンドを呼ぶ。確認コマンドが、自分が sandbox の中かを OS に問い合わせる | **採用**（2026-11-18、人間の判断）。Claude の git の呼び出しごとに Python の起動の時間が足され、確認コマンドが入っていないと Claude の git も止まる |
| 2 | 関数が `SANDBOX_RUNTIME` を見て素通りさせ、偽る形は規則で禁じる | 不採用。`! SANDBOX_RUNTIME=1 git switch x` で確認を飛ばせる。`command git` より目立たず、人間に貼らせやすい（builder check の指摘） |

**確かめた後、git が書くまでのあいだの差し替え:** 確認の後に、Claude が ref や index を差し替えることがありうる。git の実行の後にもう一度比べて、違えば警告する（[6.5](#design-verify)。私の判断）。防ぐには、確かめた中身を git に固定して渡す必要があり、サブコマンドごとに作りが大きくなる。

<a name="design"></a>

## 5. 全体の形

| 部品 | 置き場所 | 役割 |
| --- | --- | --- |
| 確認コマンド `cc-checkout-guard` | 元は `claude/bin/cc-checkout-guard`。root 所有で `/usr/local/libexec/claude-guard/cc-checkout-guard` に置く | `check`（git の前）・`verify`（git の後）・`worktree-create`（フック）の 3 つの動き。対象の一覧を中に持つ |
| `git` 関数 | `bin/.zshrc`（`~/.zshrc` の実体） | 確認コマンドを呼び、許可されたら `command git` を実行する |
| `WorktreeCreate` フック | `claude/settings.json`（`~/.claude/settings.json` の実体） | `claude -w` の作成を、確認コマンドの `worktree-create` に置き換える |
| 検査 | `.github/scripts/check-repo.py` | 上の 3 つと、mise の設定が崩れたら失敗する |

- **名前:** C3 のため、「git」を含まない名前にした。置き場所は、Claude が呼ぶラッパー（`claude-push`・`claude-crit`）と分ける。この確認コマンドは、人間のシェルと Claude Code のフックから呼ばれ、Claude からは呼ばれないからである（私の判断）。
- **実装の言語:** `cc-safe-push` と同じく、Python の標準ライブラリだけで書く。shebang は `#!/usr/bin/env -i /Library/Developer/CommandLineTools/usr/bin/python3 -I` とする。理由は、関数から呼ぶときに、人間の環境変数で動きを変えられないようにするためである（私の判断）。

<a name="design-detail"></a>

## 6. 設計

<a name="design-targets"></a>

### 6.1 対象のファイルを選ぶ基準

対象にするのは、次の 2 つを両方満たすファイルである。

- sandbox の外で、自動で読み込まれたり動いたりする（[research の 3.4](research-git-route.md#results-inventory)）。
- sandbox からの直接の書き込みは、すでに止めている。

直接書けるファイルは、git の経路だけを止めても守りが増えないので、対象にしない。

<a name="design-target-list"></a>

### 6.2 対象の一覧

一覧は確認コマンドの中に持つ。リポジトリの中の設定ファイルには置かない。置くと、一覧そのものを git の経路で書き換えられるためである。

**すべてのリポジトリ**（リポジトリの中の相対パス。深さは問わない）

| パターン | 理由 |
| --- | --- |
| 名前が `.env` で始まるファイル | env-zsh が、cd のたびに `source` する |
| `.claude/` の下のすべて | 設定・hooks・skills など。設定と hooks は、動いているセッションにその場で効く |
| `.mcp.json` | セッションの起動時に読まれる |
| `.vscode/` の下のすべて | `tasks.json` は、フォルダーを開いたときに動く設定にできる。sandbox-runtime が名前で守っている |
| `.idea/` の下のすべて | sandbox-runtime が名前で守っている。実行の設定を持てる |
| 名前が `mise.lock` のファイル | [6.8](#design-mise-lock) で直接の書き込みを止めるので、あわせて対象にする |

**dotfiles の元のチェックアウトだけ**（`~/dotfiles` からの絶対パス）

- dotfiles のプロジェクト設定（`.claude/settings.json`）の denyWrite と同じ 16 項目: `claude`・`zsh`・`config`・`mise`・`mise.toml`・`ghostty`・`vscode`・`bin`・`codex`・`biome`・`obsidian`・`aws`・`init.command`・`setup.command`・`CLAUDE.md`・`.claude/rules`。
- 理由: リンクと sheldon で使われているのは、元のチェックアウトのファイルだけである。dotfiles の worktree の `claude/` などは、どこからも使われない。
- 同じ範囲にするのは、検査で揃っていることを確かめられるからである（[6.10](#design-check-repo)）。`CLAUDE.md` や `.claude/rules` のように、実行はされないものも含む。

**照らし合わせ方**

- 大文字と小文字を区別せず、Unicode を正規化してから照らし合わせる（C8）。`.Claude/Settings.json` も対象になる。
- 対象のパスの親ディレクトリが変わる場合も含める。たとえば、`.claude` がファイルや symlink に変わる場合である。

<a name="design-function"></a>

### 6.3 zsh の `git` 関数

- **置き場所:** `bin/.zshrc` の最後（sheldon と mise の `eval` の後）に置く。`zsh/*.zsh` には置かない。zsh-defer で遅れて読まれるので、最初のコマンドや、Claude Code のシェルのスナップショットに入らないおそれがある。
- **動き:**
  1. どこで動いていても（sandbox の中も）、確認コマンドの `check` に、引数とカレントディレクトリを渡す。環境変数を見て飛ばすことはしない。
  2. 確認コマンドが見つからない、または 0 以外で終わったら、git を実行せずにその終了コードを返す（fail closed）。見つからないときは、インストールの手順の場所を表示する。
  3. 許可されたら `command git "$@"` を実行し、`check` が求めたときだけ、続けて確認コマンドの `verify` を呼ぶ。返すのは git の終了コードとする。ただし、`verify` が食い違いを見つけたときは 0 以外にする。
- **関数は小さく保つ。** どのサブコマンドを確かめるかなど、判断はすべて確認コマンドで行う。関数に判断を書くと、root 所有でない場所に判断が分かれるためである。
- **速さ:** まず、すべての呼び出しを確認コマンドに通して測る。`git status` や補完が目に見えて遅くなるなら、plan で対処を決める。

<a name="design-check"></a>

### 6.4 確認コマンドの `check`

**sandbox の中かどうか**

- 最初に、自分が macOS の sandbox の中で動いているかを OS に問い合わせる（候補は `sandbox_check`。使えるかは plan で確かめる）。確認コマンドは、sandbox の中のシェルから呼ばれると、同じ sandbox の中で動く。
- 中なら、何も確かめずに許可する。`verify` も求めない。
- 環境変数は使わない（C4）。問い合わせに失敗したら、外にいるものとして扱う。その場合、sandbox の中でも確認が働き、対象のファイルが変わる操作は止まる（Claude の git が止まる側に倒れる）。

**呼び出しの読み取り**

- git の全体のオプション（`-C`・`-c`・`--git-dir`・`--work-tree` など）を読み、対象のリポジトリとサブコマンドを決める。
- alias は、人間の git の設定から展開する（`co`・`sw` など）。`!` で始まる alias（シェルを動かす alias）は、確かめられない形として扱う。
- 人間の環境に `GIT_DIR`・`GIT_WORK_TREE`・`GIT_INDEX_FILE`・`GIT_OBJECT_DIRECTORY`・`GIT_ALTERNATE_OBJECT_DIRECTORIES` があるときも、確かめられない形として扱う。関数は、これらがあることを確認コマンドに伝える。確認コマンドは `env -i` で動くので、自分では見えない。

**サブコマンドの分類**

- **作業ツリーに書かないもの**（`status`・`diff`・`log`・`fetch`・`add`・`commit`・`push` など）: すぐに許可する。
- **作業ツリーに書くもの:** 書きうる中身を計算する。少なくとも、[research の 3.2](research-git-route.md#results-hooks) の 21 個を含める。ほかに、`apply`・`am`・`bisect`・`sparse-checkout`・`submodule update`・`rm`・`mv`・`clean`・`worktree add`、`merge`・`rebase`・`cherry-pick`・`revert`・`am` の `--continue`・`--skip`・`--abort` を含める。
- **知らないサブコマンドと、確かめられない形:** 止める（下の「止める場合」）。

**書きうる中身の計算**

- 原則: そのコマンドが書きうる対象のファイルのパスと中身を、確かめる時点の状態からすべて求める。途中の状態も含める（rebase と cherry-pick の範囲の各コミット）。途中で止まると、その状態が作業ツリーに残るためである。
- git が書かないパスは、候補に入れない。たとえば `switch` では、HEAD と切り替え先で違うパスだけを候補にする。手元で編集中のファイルがあるだけで確認が出ないようにするためである（反目標の 2 つ目）。
- `.git` の中の、sandbox が書ける状態は、すべて信用しない。ref、index、stash、`ORIG_HEAD`・`MERGE_HEAD`・`FETCH_HEAD`、rebase と cherry-pick の手順のファイル、`info/` などである。`--continue` などでは、手順のファイルにある残りのコミットも候補にする。
- 中身は、書く git と同じ見え方で読む。replace の ref（`refs/replace`）と alternates を、git と同じく効かせたまま読む。git と違う見え方で読むと、確認で見せた中身と書かれる中身がずれる。
- `pull` は、fetch と merge（`pull.ff = only` なら fast-forward）に分けて考える。対応する形と、fetch をいつ行うかは、plan で決める。
- `worktree add` は、新しいディレクトリに書く。まだどこからも読まれないので、書いた後に [6.6](#design-worktree-hook) と同じ比べ方で確かめてよい。違ったら差分を見せて、残すかを y/N で聞く。N なら worktree を消す。

**止める場合**（対応する形でも止める）

- 対象のパス、またはその親が、symlink か gitlink（submodule）になる。symlink の先は、後から sandbox が書ける場所かもしれないからである。
- 対象のパスに、書くときに中身を変える属性がつく（`filter`・`working-tree-encoding`・`ident`）。属性は `.gitattributes` と `.git/info/attributes` から来て、どちらも sandbox が書ける。`filter=lfs` なら、書かれる中身は blob ではなく、LFS のサーバーから来る。

**確かめるときに動かさないもの**

- git は、`/Library/Developer/CommandLineTools/usr/bin/git` を固定のパスで使う。`core.fsmonitor` を切り、textconv・外部 diff・ページャ・フックを使わない。理由は `cc-safe-pr` と同じで、確認コマンドが sandbox の外でコードを動かす入口にならないようにするためである。
- リポジトリの `.git/config` は読む。sandbox からは書けない。

**結果の出し方**

| 状況 | 普段の端末（標準入力が端末） | `!` など（標準入力が端末でない） |
| --- | --- | --- |
| 対象のファイルが変わらない | 何も出さずに許可する | 何も出さずに許可する |
| 対象のファイルが変わる | 変わるファイルの一覧と差分（追加・変更・削除・モード）を出し、y/N を聞く。既定は N | 変わるファイルの一覧と、普段の端末で打つ `git -C <リポジトリのルート> <引数>` を出して止める |
| 止める場合・確かめられない形 | 理由を出して止める。確かめずに実行したいときは、人間が自分で `command git` を打つ | 理由を出して止める |

- y/N を飛ばす環境変数やオプションは作らない。
- `!` で表示するコマンドの引数は、シェルで安全に貼れるように quote する。

<a name="design-verify"></a>

### 6.5 確認コマンドの `verify`

- git が終わった後に、対象のファイルの中身を、`check` で許可した中身と比べる。変わらないはずのファイルは、変わっていないことを確かめる。
- 違っていたら、目立つ警告を出す。内容は、食い違ったファイルの一覧と、「動いている Claude Code のセッションを止めて、中身を確かめる」という案内である。終了コードは 0 以外にする。
- `check` から `verify` に渡す状態は、sandbox から書けない場所に置く。`cc-safe-push` と同じく、macOS のユーザー専用の一時ディレクトリを使う。あるいは、関数の変数で渡す。方法は plan で決める。

<a name="design-worktree-hook"></a>

### 6.6 `WorktreeCreate` フック

**登録:** ユーザー設定（`claude/settings.json`）の `hooks.WorktreeCreate` に、`/usr/local/libexec/claude-guard/cc-checkout-guard worktree-create` を登録する。

**動き**

1. フックの入力（JSON）から `name` とカレントディレクトリを読む。`name` は、英数字と `.`・`_`・`-` だけを許す。`.` で始まる名前は拒否する。
2. 元のチェックアウトのルートを求める。置き場所は `<ルート>/.claude/worktrees/<name>`、ブランチは `worktree-<name>` とする（Claude Code の既定と同じ）。
3. その場所に worktree がすでにあれば、確かめずにパスを返す（非目標。[7 章](#accepted-risks)）。
4. 作成元を決める。ローカルの `origin/HEAD` が指すコミットを使い、なければ元のチェックアウトの HEAD を使う。fetch はしない（plan で変更。下の注）。
   - 作成元が sandbox に差し替えられていても、5 の比較が守る。作成元の選び方は使い勝手のためで、守りではない。
   - 注: 初版では「fetch を 5 秒程度まで試す」としていた。確認コマンドは `env -i` で動くので、fetch には cc-safe-push と同じ SSH の扱いがもう 1 つ要る。fetch は守りに関わらないので、plan で外した（2026-11-18）。元のチェックアウトで pull すれば `origin/HEAD` の先も新しくなる。
5. `git worktree add -b worktree-<name> <置き場所> <作成元>` で作る。そのうえで、すべてのリポジトリ向けの対象（[6.2](#design-target-list)）について、新しい worktree のファイルと、元のチェックアウトの同じパスのファイルを、実際の中身で比べる。比べるのは、どちらかで追跡されているパスである。
   - ファイルの有無と中身が一致しなければ、失敗とする。対象のパスやその親が symlink のときも失敗とする。
   - dotfiles だけの対象（`claude/` など）は比べない。worktree の中のものは使われないからである。
6. 失敗したら、作った worktree とブランチを消し、違ったファイルの一覧を出して 0 以外で終わる。Claude Code は作成を失敗にする。案内は、理由ごとに書き分ける。
   - 元のチェックアウトが既定ブランチにあり、origin より遅れている: 元のチェックアウトで `git pull` をする（関数が差分を見せる）。そのうえで、もう一度 `claude -w` を実行する。
   - 元のチェックアウトが別のブランチにある: 既定ブランチに戻すか、元のチェックアウトで作業する。
   - 元のチェックアウトの対象のファイルに、コミットしていない変更がある: その変更を片付ける。
   - どれにも当たらない（origin の既定ブランチと、元のチェックアウトの同じブランチが一致しているのに違う）: ref か object が差し替えられたおそれがあるので、作業を止めて中身を確かめる。
7. 成功したら、worktree のパスを標準出力の最後の行に出す。

**書いた後に比べてよい理由:** フックが終わるまで、新しいディレクトリはどのセッションからも読まれない。中身は、書かれた結果そのものを比べるので、ref の差し替え、replace の ref、object の差し替えのどれでも拾える。

**元のチェックアウトを基準にする理由:** 元のチェックアウトの対象のファイルは、sandbox から直接書けない。git の経路も、この作業の関数が守る。そのため、人間が確かめた中身とみなせる。

**変わること:**

- origin で対象のファイルが変わったら（`.claude/settings.json` を変える PR をマージしたときなど）、先に元のチェックアウトで pull が要る。
- 元のチェックアウトが別のブランチにあるときと、対象のファイルに未コミットの変更があるときも失敗する。人間の使い方では、どちらもまれである（2026-11-18、人間の回答）。
- `.worktreeinclude` は処理されなくなる。今のリポジトリには、`.worktreeinclude` がない（[research の 3.9](research-git-route.md#results-claude-worktree)。`~/Dev` は深さ 4 まで確かめた）。

<a name="design-mise"></a>

### 6.7 mise の `trusted_config_paths`

- `check_mise_paranoid` は、グローバルの設定（`mise/mise_config.toml`）の `[settings]` に `trusted_config_paths` があれば、値によらず失敗する。
- 同じ検査で、`bin/.zshrc`・`bin/.zprofile`・`zsh/*.zsh`・`mise/mise_config.toml` に `MISE_TRUSTED_CONFIG_PATHS` か `MISE_PARANOID` があっても失敗する。環境変数は設定ファイルより優先されるためである（私の判断）。
- `yes` は検査しない（[research の 4 章の 8](research-git-route.md#implications)）。

<a name="design-mise-lock"></a>

### 6.8 `mise.lock`

- ユーザー設定の `permissions.deny` に `Edit(**/mise.lock)` を足す。Edit の deny は、sandbox の denyWrite にもなる。あわせて、[6.2](#design-target-list) の対象に入れる。
- 理由（推測を含む）: 信頼された設定の隣に置かれた `mise.lock` は、取得先と checksum をまとめて変えられる見込みがある。paranoid の `config` は lock を対象にしない（[research の 3.6](research-git-route.md#results-mise)）。今は、どのリポジトリにも lock がないので、止めても困らない。
- paranoid に `provenance` は足さない。attestation のあるツールにしか効かず、前回、`npm:@salesforce/cli` のインストールを止める見込みがあるとした（[前回の design の 5 章](../20261116_sandbox-path-gaps/design.md#approaches)）。lock を使い始めるときに見直す。

<a name="design-etc"></a>

### 6.9 ユーザー設定の `Edit(/etc/**)`

- 消す。独立したコミットにする。
- 理由: ユーザー設定では `~/.claude/etc/**` を指していて、`/etc` を守っていない（[research の 3.5](research-git-route.md#results-claude-code)）。`//etc/**` に直しても、守りはほとんど増えない。`/etc` は root でないと書けず、Edit ツールは `blockWritesOutsideWorkingDirectories` が止める。`/etc` の実体は `/private/etc` なので、直した規則が sandbox で効くかも分からない。

<a name="design-check-repo"></a>

### 6.10 `check-repo.py`

足す検査（どれも、今の `edit-permissions`・`mise-paranoid` と同じ書き方にする）:

- `bin/.zshrc` が、確認コマンドの絶対パスを呼ぶ `git` 関数を定義している。
- `claude/settings.json` の `hooks.WorktreeCreate` に、確認コマンドの `worktree-create` が、完全一致で 1 つだけ登録されている。
- `claude/bin/cc-checkout-guard` の dotfiles 向けの一覧が、`PROJECT_DENY_WRITE` をすべて含む。すべてのリポジトリ向けの一覧が、[6.2](#design-target-list) のパターンを含む。
- `Edit(**/mise.lock)` が deny にある。
- [6.7](#design-mise) の mise の検査。

<a name="design-docs"></a>

### 6.11 文書

- **グローバルの `claude/CLAUDE.md`:**
  - git の続きを `!` で頼むときの手順を直す。対象のファイルが変わる場合は、`!` では止まると書く。その場合は、普段の端末で打つ `git -C <パス> …` を示す。
  - `command git`・`\git`・絶対パスの git を `!` で頼まないと書く。
  - 今の「変わるファイルを確かめて伝える」は残す。
- **リポジトリの `CLAUDE.md`:**
  - 禁止事項に、関数・フックの登録・`Edit(**/mise.lock)` を外さないことを足す。
  - 確認コマンドを変えたときのテストの手順を書く。
- **`claude/README.md`:** 確認コマンドのインストールと戻し方を書く（`cc-safe-push` の節と同じ形）。
- **`.claude/rules/CLAUDE_CONFIG.md`:** 設計の理由を短く書く。

<a name="design-order"></a>

### 6.12 順番

1. 確認コマンドとそのテスト。
2. check-repo の検査（mise の検査、`Edit(**/mise.lock)` の検査を含む）。
3. `bin/.zshrc` の関数。
4. `claude/settings.json` の変更（フックの登録、`Edit(**/mise.lock)` の追加）。C2 のため、人間が当てる。
5. `Edit(/etc/**)` を消す（独立したコミット）。C2 のため、人間が当てる。
6. 文書。

**インストールとマージの順:** 確認コマンドは、マージの前に、人間が worktree から root 所有でインストールする。呼ぶ側（関数とフック）は、マージした後、元のチェックアウトに取り込んだ時点で効く（C1）。逆の順にすると、新しいシェルの git（Claude の Bash ツールを含む）と `claude -w` がすべて止まる（fail closed）。

<a name="design-verify-plan"></a>

### 6.13 確かめ方

**自動のテスト**（Python。一時ディレクトリのダミーのリポジトリを、テストの中の git で作る）

- 対応するサブコマンドごとに、次を確かめる。
  - 対象のファイルを変えないときは許可する。
  - 変えるときは、端末なら確認を出し、端末でなければ止める。
  - index だけを変えた状態からの `restore`・`checkout --`・`checkout-index`。
- 次のときに止まるか、差分に出る。replace の ref、symlink、`.Claude` のような大文字と小文字の違い、Unicode の正規化の違い、`filter` の属性、削除とモードの変更。
- 確かめられない形（知らないオプション、`!` で始まる alias、`GIT_DIR` があるとき）では止まる。
- sandbox の中かどうかの判断: sandbox の外で `SANDBOX_RUNTIME` を付けても確認が働く。sandbox の中では素通りする（sandbox の中で動かすテストは、Claude の Bash ツールで実行して確かめる）。
- `verify` が食い違いを見つける。
- `worktree-create`:
  - `origin/HEAD` を差し替えたダミーでは、失敗して、worktree とブランチが残らない。
  - 一致するときは、パスを返す。
- y/N の入力は、疑似端末で確かめる。

**新しいセッションでの確認**（人間が行う。マージの後）

- 新しい zsh で、`whence -w git` が関数になっている。
- ダミーのリポジトリで、`git switch` の確認が出る。`!` では止まり、表示されたコマンドを普段の端末で打てる。`! SANDBOX_RUNTIME=1 git switch …` でも止まる。
- Bash ツールの git が今までどおり動く。
- `claude -w` で、dotfiles の worktree が今までどおりできる。ダミーのリポジトリで、`origin/HEAD` を差し替えると失敗する。
- `git status` と補完の速さを測る。

**ほかの検査:** `check-repo.py`・`test-check-repo.py`・shellcheck・actionlint。

<a name="design-rollback"></a>

### 6.14 戻し方

- **順番:** 先に `claude/settings.json` のフックの登録を外す。確認コマンドを先に消すと、`claude -w` が失敗するためである。次に `bin/.zshrc` の関数を外す。最後に、確認コマンドを `sudo rm` で消す。
- **急ぎのとき:** 動いているシェルでは、`unfunction git` で関数を外せる。`command git` は、確認を通らずに動く。

<a name="accepted-risks"></a>

## 7. 受け入れるリスク

- **確認を飛ばす形:** `command git`・`\git`・絶対パスの git と、zsh を通らない git。Claude が頼むのを規則で禁じるだけで、技術的には止めない。人間が頼まれて打てば通る。
- **確認から実行までの差し替え:** 確認と git の実行のあいだに、sandbox が ref や index を差し替えると、確かめていない中身が書かれうる。`verify` が後から見つけるが、Claude Code の設定と hooks は、書かれた時点で効く。
- **すでにある worktree:** `claude -w` で開き直すときと、`claude --resume` では確かめない。元のチェックアウトで起動したセッションの sandbox が、`.claude/worktrees/<name>/.claude/settings.json` に直接書けるかは確かめていない。
- **`claude -w` の変化:** Claude Code が worktree の作り方を変えると、フックとずれる。`#1234` の形（PR から作る）は、フックでは扱わない見込み（未確認）。
- **dotfiles の pull のたびの確認:** dotfiles の PR の多くは `claude/` を変える。元のチェックアウトで pull するたびに、確認が出る。人間が実際の中身を見る場面として受け入れる。
- **Claude Code の仕様:** `claude -w`、`WorktreeCreate`、信頼の扱いは、文書の要約による（C7）。新しいセッションでの確認（[6.13](#design-verify-plan)）で確かめる。
- **`claude -w` の失敗:** 元のチェックアウトが別のブランチにあるときと、対象のファイルに未コミットの変更があるときは、`claude -w` が失敗する（[6.6](#design-worktree-hook)）。まれなので受け入れる。
- **Claude の git の遅さ:** sandbox の中の git も、呼び出しごとに確認コマンドを起動する。
- **`.worktreeinclude` の読み取りの経路:** 次の作業にする。
- **入れ子のリポジトリの設定からコードが動く経路:** 今もすでに開いている。次の作業の最初にする（非目標）。

<a name="builder"></a>

## 8. ビルダーに任せること

- 確認コマンドの内部の作り。サブコマンドごとの計算の方法、対応する形の一覧、出力の書き方。いずれも [6.4](#design-check) の原則に従う。
- `check` から `verify` への状態の渡し方。
- 関数の速さへの対処（測った後）。
- `worktree-create` の `name` の検査の細部。
- テストの組み立て。
