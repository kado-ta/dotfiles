---
status: in-progress
created: 2026-11-16
---

# mise の設定と gstack の置き場所の守りの設計

mise の設定を、パスではなく中身で信頼させる（mise の paranoid）。そのうえで、sandbox の中の git 操作を途中で止めている mise の denyWrite を外す。あわせて、`~/.gstack/projects` を symlink に差し替える経路を、フックで止める。

関連: [research-path-gaps.md](research-path-gaps.md)、[前回の research の 8 章](../20261114_edit-write-rules/research-edit-write.md#residual-risks)、PR #43

<a name="intent"></a>

## 1. 目的と背景

- **mise の設定は、パスで信頼されている。** 信頼済みのパスにある設定は、中身が変わっても、人間が cd したときに hooks・`_.source`・`exec()` を sandbox の外で動かす。今は、sandbox の denyWrite と Edit の ask で直接の書き込みを止めている。
- **それでも、git を経由する経路は止められない。** sandbox の中で、mise の設定を変えたコミットや index を作れる。人間が `!` で `git switch`・`git merge`・`git restore` を実行すると、その中身が sandbox の外で書かれる。この作業の流れでは、sandbox の中で止まる git 操作を人間が `!` で行うことが多いので、起きやすい（[前回の research の 8.1](../20261114_edit-write-rules/research-edit-write.md#review-gaps)）。
- **denyWrite には副作用がある。** mise の設定を追跡しているリポジトリ（ksc の 4 つと `sf_conn_api_spec`）では、sandbox の中の `git switch`・`merge`・`rebase`・`pull` が mise の設定の書き換えで止まり、index が中途半端に残る。続けて `git add -A` すると、上流の変更を戻すおそれがある。
- **`~/.gstack/projects` の symlink（B2）:** `additionalDirectories` の根を symlink に差し替えると、次のセッションの Edit・Write ツールは、その先（`~/Library/LaunchAgents` など）に書ける。止めるのは auto mode の判定だけだった（[research の 2.5](research-path-gaps.md#results-symlink-root)）。sandbox（Bash）からは書けない。
- **`.env`（B4）:** 作業ディレクトリの中では守られている。作業ディレクトリの外の書ける場所と、そこへの symlink には置ける（[research の 3 章](research-path-gaps.md#findings)）。

<a name="goals"></a>

## 2. 目標・非目標・反目標

**目標**

- **G1:** どの経路で書かれたプロジェクトの mise の設定も、中身が変わったら、人間が確かめて信頼し直すまで動かない。グローバルの設定（`~/.config/mise/` の下）は paranoid でもパスで信頼されるので、G1 に含めない（非目標の 1 つ目）。
- **G2:** ほかのリポジトリで、sandbox の中の git 操作が mise の設定のために途中で止まらない。
- **G3:** `~/.gstack/projects` が symlink に差し替えられているあいだは、Edit・Write ツールがどこにも書かない。
- **G4:** 上の設定が消えたら、`check-repo.py` が失敗する。

**非目標**

- dotfiles のうち、`~` からのリンクでそのまま使われているファイルを、git を経由して書き換える経路。対象は、グローバルの mise 設定（`mise/mise_config.toml`）、`claude/` の `settings.json`・`hooks`・`rules`・`CLAUDE.md`・`mcp.json`、`bin/` の `.zshrc`・`.zprofile`・`.gitconfig` など。sandbox の中で、これらを変えたコミットや index を作れる。人間が `!` で `git switch`・`merge`・`restore` をすると、その中身が sandbox の外で書かれる。リンクで使われているファイル全体の問題で、mise だけを直しても残る。そのため、対策の案（リンクをやめてコピーで置く、切り替えの後に差分を警告する、など）を比べる設計を別に行い、次の作業の先頭にする（2026-11-17、人間の判断）。
  - /review で、同じ経路がすべてのリポジトリの、sandbox の外で自動で読み込まれたり動いたりするファイル（`.env*`・`.claude/settings.json`・`.claude/hooks`・`.mcp.json` など）にも当てはまると分かった（2026-11-18）。次の作業の範囲はこれらに広げる。当面の手当てとして、グローバルの `claude/CLAUDE.md` に、止まった git の続きを `!` で頼む前に、変わるファイルを確かめて伝える手順を置いた（2026-11-18、人間の判断）。
- mise の tasks が呼ぶスクリプトの改ざん。`mise run` は人間が選んで実行する。
- `.env` の残りの経路。受け入れて記録する（[7 章](#accepted-risks)）。
- 前回の research の 8.2 の 5〜7（git の設定と hooks のほかの置き場所、worktree の `claude/`、`*.pem` の範囲）と、ユーザー設定の `Edit(/etc/**)` の起点。次の作業にする。
- dotfiles のプロジェクト設定の `./mise`・`./mise.toml` の denyWrite を外すこと。`./mise` はグローバルの設定の実体を守っている。dotfiles の git 操作は `claude/` などでも止まるので、`./mise.toml` を外しても得がない。

**反目標**（技術的に動いても、こうなったら失敗）

- グローバルの mise 設定を、sandbox から書けるようになる（paranoid でもパスで信頼されるため）。
- Claude が自分で `mise trust` を済ませられる。
- 今のツールのインストールが壊れる。
- フックの誤検知で、普段の Edit・Write が止まる。

<a name="constraints"></a>

## 3. 制約

- **C1（設定は作業ツリーのまま効く）:** `~/.claude/settings.json`・`~/.claude/hooks`・`~/.claude/CLAUDE.md`・`~/.config/mise/config.toml` は、dotfiles の元のチェックアウトへのリンク。この作業は元のチェックアウトのブランチで行うので、ファイルを変えた時点で、人間のシェルと新しいセッションに効く。
- **C2（`claude/settings.json` は Claude から編集できない）:** `blockWritesOutsideWorkingDirectories` が設定ファイルへの書き込みを止める（前回の test-report の T9）。Claude が変更を用意し、人間が `!` で当てる。
- **C3（無関係な差分）:** `claude/settings.json` には、Claude Code が書いた差分（`"switchModelsOnFlag": false` の追加と、キーの並べ替え）がある。人間の判断で、コミットに含めない。作業ツリーからも消さない。
- **C4:** `claude/`・`CLAUDE.md`・`.claude/rules`・`mise/` は sandbox から書けない。Edit ツールでは確認の画面が出る。フックのテストは、書ける場所をカレントディレクトリにして実行する（`<<<` が sandbox の中で失敗するため）。
- **C5:** mise は 2026.11.8。`paranoid` はグローバルの設定でだけ効く。
- **C6:** `check-repo.py` はすでに `tomllib` を使っている。CI は ubuntu-latest の `python3`。
- **C7:** mise の信頼の記録（`~/.local/state/mise/trusted-configs`）は、sandbox から書けない（2026-11-16 に実測）。Edit・Write ツールからも、作業ディレクトリの外なので書けない。

<a name="paranoid-facts"></a>

## 4. paranoid について確かめたこと

2026-11-16 に、mise の公式ドキュメント（`paranoid.html`・`cli/trust.html`・`configuration.html`・`security.html`・`configuration/settings.html`）と、手元の `mise trust --help` で確かめた。

- **分類:** `config`・`env_files`・`plugins`・`provenance` の 4 つ。`paranoid = ["config", "env_files"]` のように、一部だけを有効にできる。
- **`config`:**
  - グローバルとシステムの設定（`~/.config/mise/` と `/etc/mise/` の下）を除く、すべての設定に信頼が要る。`.tool-versions`、tools だけの `mise.toml`、task のファイルも含む。
  - 信頼は中身のハッシュに結び付き、編集すると信頼されていない状態に戻る。ファイルごとに信頼する（`mise.toml` を信頼しても `mise.local.toml` は信頼されない）。
  - `mise run`・`mise install`・`mise exec` などが、読み込む設定を自動で信頼しなくなる。worktree は、元のチェックアウトの信頼を引き継がない。
  - シェルの起動や cd では確認の画面を出さず、信頼されていない設定を警告して読み飛ばす。端末のないコマンドは、信頼されていないというエラーで止まる。
- **`env_files`:** `_.file`・`_.source`・`env_file` の設定が読むファイルにも、中身に結び付いた信頼が要る。
- **`plugins`・`provenance`:** レジストリにないプラグインを拒否する。provenance の検査をやり直し、npm の provenance の失敗をエラーにする。
- **プロジェクトからは弱められない:** `paranoid`・`trusted_config_paths`・`yes` は、グローバルの設定でだけ効く。`.miserc.toml`（信頼なしで読み込まれる）に書けるのは `env`・`ignored_config_paths` など 7 つのキーだけで、グローバルの設定の場所も変えられない。
- **グローバルの設定は、paranoid でもパスで信頼される。** `trusted_config_paths` の下も同じ。
- **手元の設定:** dotfiles・ksc の 4 つ・`sf_conn_api_spec` の 6 つの設定は、どれも tools と tasks だけで、cd で動く機能を使っていない（2026-11-16 に実測）。

<a name="approaches"></a>

## 5. 進め方

**mise**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| A | paranoid（`config`・`env_files`）を入れ、mise の denyWrite を外す。グローバルの設定のディレクトリ `~/.config/mise` だけは denyWrite に残す | **採用**（2026-11-16、人間の判断） |
| B | paranoid を入れ、denyWrite も残す | 不採用。git の途中停止が残る。最後に人間が信頼を判断する点は A と同じなので、守りはあまり増えない |
| C | `paranoid = true`（4 つすべて） | 不採用。`npm:@salesforce/cli`（`trust_policy_excludes` で例外を入れている）のインストールを止める見込み（推測）。/review で、`provenance` は lockfile（`mise.lock`）の改ざんへの備えにもなる見込みと分かった（未確認。[7 章](#accepted-risks)） |
| D | dotfiles を `trusted_config_paths` に入れて、信頼し直しを省く | 不採用。パスでの信頼に戻る |

**B2（`~/.gstack/projects` の symlink）**

| 案 | 内容 | 判断 |
| --- | --- | --- |
| A | PreToolUse のフックで、symlink のあいだは Edit・Write を拒否する | **採用**（2026-11-16、人間の判断） |
| B | 受け入れて記録する | 不採用 |
| C | `additionalDirectories` から外す | 不採用。gstack のスキルが Write ツールで書けなくなる |

**`.env`（B4 の残り）:** 受け入れて記録する（2026-11-16、提案のとおり）。人間が、作業ディレクトリの外の書ける場所か、そこへの symlink に cd しないと起きない。env-zsh を置き換える案は、この作業の範囲外にする。

<a name="design"></a>

## 6. 設計

<a name="design-mise"></a>

### 6.1 mise の paranoid

- `mise/mise_config.toml`（`~/.config/mise/config.toml` の実体）に `[settings]` を足し、`paranoid = ["config", "env_files"]` にする。採らなかった 2 つの分類の理由を、コメントに 1〜2 行で書く。
- Claude は `mise trust` を実行しない（C7 で、できない）。信頼されていないという警告やエラーが出たら、人間に、ファイルの全体と読み込む env ファイルを確かめてから `mise trust <ファイル>` するよう頼む（/review で直した。mise は前の中身を持たないので、差分では確かめられない）。

<a name="design-sandbox"></a>

### 6.2 sandbox の denyWrite（ユーザー設定）

- **外す:** mise の 10 項目（`~/**/mise.toml`・`~/**/.mise.toml`・`~/**/mise.*.toml`・`~/**/.mise.*.toml`・`~/**/mise/config.toml`・`~/**/mise/config.*.toml`・`~/**/mise/conf.d`・`~/**/.mise`・`~/**/.config/mise`・`~/**/.tool-versions`）。
- **足す:** paranoid の土台になる、次の 3 つ。どれも、dotfiles などリポジトリで起動したセッションからは、もともと書けない（作業ディレクトリの外か、プロジェクト設定の `./mise`）。`~` などで起動したセッションで、作業ディレクトリに入ったときのために置く（ビルダーの判断。[2 章](#goals)の反目標の 1 と 2 を、起動した場所によらずに守るため）。
  - `~/.config/mise`: グローバルの設定のディレクトリ。paranoid でもパスで信頼される。
  - `~/dotfiles/mise`: グローバルの設定の実体（`~/.config/mise/config.toml` のリンク先）がある。
  - `~/.local/state/mise`: 信頼の記録がある。ここに書けると、Claude が自分で信頼を済ませられる。
- **Edit・Write ツール:** denyWrite は Bash しか止めない。`~` で起動したセッションでは、作業ディレクトリの外を止める設定も効かない。そのため、ユーザー設定の permissions に `Edit(~/.local/state/mise/**)` を deny、`Edit(~/dotfiles/mise/**)` を ask で足す（/review の指摘、2026-11-18、人間の判断）。`~/.config/mise` には、mise の Edit の ask（`**/.config/mise/**`）が当たる。
- **`~` で起動したセッション:** この 3 つのほかは、対象外のまま。`~/Library/LaunchAgents` なども書けるので、グローバルの CLAUDE.md の指示どおり、リポジトリのルートで起動し直してもらう。
- **残す:**
  - mise の Edit の ask（接頭辞のない形と `//**/` の形の 20 項目）。
  - dotfiles のプロジェクト設定の `./mise`・`./mise.toml` の denyWrite と ask。

<a name="design-hook"></a>

### 6.3 `~/.gstack/projects` のフック

- **ファイル:** `claude/hooks/guard-additional-dirs.sh`（新規）。
- **登録:** `claude/settings.json` の `hooks.PreToolUse` に、matcher `Edit|Write|MultiEdit|NotebookEdit`、command `/bin/bash ~/.claude/hooks/guard-additional-dirs.sh`、`timeout` 10、`onFailure` `block` で足す（`ask-gh-pr-write.sh` と同じ形）。
- **動き:**
  - `HOME` が空なら拒否する（終了コード 2）。
  - `$HOME/.gstack/projects` がなければ通す（終了コード 0）。
  - あって、symlink であるか、実体のパス（`cd -P` で解決したもの）が `$HOME/.gstack/projects` と違えば、拒否する。メッセージは英語で、人間に確かめてもらうよう書く。親の `~/.gstack` が symlink の場合も、実体のパスの比較で拒否になる。
  - それ以外は通す。
  - 入力（stdin の JSON）の中身は使わない。jq に頼らないので、jq が動かないときも動く。
  - /review で次の 2 点を変えた（2026-11-18、人間の判断）。比べる相手を「`HOME` を実体のパスに直したもの」にしたのは plan の判断。
    - 入力は最後まで読み捨てる。読まずに終わると、パイプの容量を超える入力で書き手が SIGPIPE で切られる（テストで確かめた）。
    - 拒否の理由は固定の文にし、symlink の先や解決した先を入れない。仕込んだ側が決められる文字列を、フックの理由として次のセッションの Claude に渡さないため。
- **すべての呼び出しを拒否する理由:** 起動時に symlink が解決されるので、解決した先は作業ディレクトリとして扱われる。対象のパスで絞ると、解決した先への直接の書き込みを通してしまう。
- **テスト:** `claude/hooks/tests/test-guard-additional-dirs.sh`（新規）。今のフックのテストと同じく、`HOME` を一時ディレクトリに差し替える。少なくとも、実体のディレクトリ（0）、symlink（2）、ない（0）、`HOME` が空（2）、親の `~/.gstack` が symlink（2）を確かめる。

<a name="design-check"></a>

### 6.4 `check-repo.py`

テストを先に直し、失敗させてから実装する。

- **denyWrite の検査:** `MISE_DENY_WRITE`（10 項目）をやめ、6.2 で足す 3 つがあることを確かめる。
- **paranoid の検査（新規）:** `mise/mise_config.toml` の `settings.paranoid` が `true`、または `config` と `env_files` を含むリストであることを確かめる。
- **フックの検査（新規）:** `hooks.PreToolUse` に、`guard-additional-dirs.sh` を呼ぶ項目があり、matcher が Edit・Write・MultiEdit・NotebookEdit を含み、`onFailure` が `block` であることを確かめる。
- mise の Edit の ask の検査（`MISE_ASK`）は残す。

<a name="design-docs"></a>

### 6.5 文書

- **ルートの `CLAUDE.md`:**
  - 「sandbox と権限の禁止事項」の、mise の Edit の ask と denyWrite の行を、paranoid・`~/.config/mise` の denyWrite・フックに合わせて直す。
  - 「規約」のフックのテストの一覧に、新しいテストを足す。
- **`.claude/rules/CLAUDE_CONFIG.md`:** 「Edit・Write ツールの書き込み」の mise の 2 項目を、paranoid で守る理由と、`~/.config/mise` だけを残す理由に書き換える。`additionalDirectories` の項目に、フックの理由を足す。
- **グローバルの `claude/CLAUDE.md`:**
  - Safety の「sandbox の中の git が、mise の設定で `unable to unlink`…」の行を消す。ほかのリポジトリでは起きなくなるため。dotfiles では、ルートの CLAUDE.md の手順が引き続き当てはまる。
    - /review で、この前提は誤りと分かった。ほかのリポジトリでも、Edit の deny から変換された denyWrite（`.env*`・lock ファイルなど）と、Claude Code が守る `.claude/settings.json` などで、git の操作は途中で止まる。そのため消さずに、mise に限らない形で残し、`!` で続きを頼む前に変わるファイルを確かめる手順を足した（2026-11-18、人間の判断）。
  - mise の信頼の警告が出たら、自分で信頼しようとせず、人間に頼む旨を 1 行で足す。
- **`claude/README.md`:** フックの一覧があれば足す。
- **research:** 判断の章を足し、この設計書にリンクする。

<a name="design-settings-patch"></a>

### 6.6 `claude/settings.json` の変え方（C2・C3）

- コミットには、この作業の変更（denyWrite の 10 項目を外す、`~/.config/mise` を足す、フックを登録する）だけを入れる。`switchModelsOnFlag` と並べ替えは入れない。
- 作業ツリーには、この作業の変更と、今ある無関係な差分の両方を残す。
- 作業ツリーへの反映は、Claude が用意したパッチを人間が `!` で当てる。手段（HEAD に対するパッチを index に、作業ツリーに対するパッチを作業ツリーに当てる、など）はビルダーが決める。

<a name="design-order"></a>

### 6.7 順番

C1 のとおり、変更は書いた時点で効く。paranoid が効く前に denyWrite を外すと、その間は、sandbox が信頼済みの設定を書き換えて動かせる。

1. `check-repo.py`、フックとテスト、文書を変える。フックは、まだ登録しないので効かない。
2. paranoid を有効にする。直後に人間が、6 つの設定の中身を確かめて `mise trust` する。worktree があれば、それも信頼する。
3. 人間が `claude/settings.json` の変更を当てる。denyWrite が外れ、`~/.config/mise` が入り、フックが登録される。新しいセッションから効く。
4. 新しいセッションで確かめる（[6.8](#design-verify)）。

<a name="design-verify"></a>

### 6.8 確かめ方

- **自動:**
  - `check-repo.py`・`test-check-repo.py`
  - フックの回帰テスト 5 本（新しいテストを含む）
  - shellcheck・actionlint
- **人間のセッション**（変更後の規則で起動する。ファイルは編集しないと伝える）:
  - **V1（paranoid）:** ダミーのディレクトリで、次の 4 点を確かめる。
    - 信頼すると、cd で設定が効く。
    - 中身を変えると、cd で警告が出て読み飛ばされる。
    - 端末のない `mise env` などは止まる。
    - Claude の Bash から `mise trust` を実行すると、失敗する。
  - **V2（denyWrite）:**
    - 作業ディレクトリの中で、Bash から `mise.toml` を作れる。
    - `~/.config` で起動したセッションでは、Bash から `~/.config/mise` の下に作れない。
  - **V3（フック）:**
    - 普段どおりの状態で、Edit・Write（作業ディレクトリと `~/.gstack/projects`）が通る。
    - 本物の `~/.gstack/projects` は差し替えない。拒否の動きは自動テストで確かめる。

<a name="design-rollback"></a>

### 6.9 戻し方

- **順番:** 6.7 と逆にする。先に `claude/settings.json` で denyWrite の 10 項目を戻し、その後で paranoid を外す。paranoid だけを先に外すと、sandbox から書ける設定がパスで信頼される状態になる（/review の指摘）。
- **paranoid:** `mise/mise_config.toml` の行を消す。パスでの信頼に戻る。`~/.local/state/mise/trusted-configs` には、paranoid の前のディレクトリ単位の信頼の記録（`~/dotfiles` など）が残っていて、パスでの信頼に戻るとその下の設定がすべて信頼される。戻すときは、要らない記録を `mise trust --untrust` で消すことも考える。
- **`claude/settings.json`:** 当てた変更を戻す（denyWrite の 10 項目を戻し、フックの登録と、mise の 2 つの Edit の規則を消す）。
- **フックの誤検知で Edit・Write が止まったとき:** `~/.gstack/projects` を確かめる。直せなければ、人間がフックの登録を外す。
- **マージの前:** `git switch main` で、すべて戻る。sandbox の中では途中で止まるので、人間が `!` で行う。切り替えたら、起動済みのセッションをすべて起動し直す。フックの登録が起動時のまま残っていると、スクリプトがなくなった時点で、onFailure block によって Edit・Write がすべて止まる見込み（推測）。

<a name="design-after-merge"></a>

### 6.10 マージの後

- 人間が、sandbox の外で main に切り替えて更新する。
- セッションをすべて起動し直す。
- `mise trust --show` で、6 つの設定が信頼されていることを確かめる。

<a name="accepted-risks"></a>

## 7. 受け入れるリスク

- **`.env`:** 作業ディレクトリの外の書ける場所（`$TMPDIR`・`~/.gstack/projects`）と、そこへの symlink のディレクトリ。人間がそこに cd しないと起きない。
  - /review で、git を経由する経路もあると分かった。sandbox の中で `.env` を含むコミットや index を作り、人間が `!` で `git switch`・`restore` をすると、作業ディレクトリに `.env` が書かれ、次の cd で env-zsh が読み込む。人間の cd は要らない。非目標の 1 つ目と同じ経路なので、次の作業で扱い、当面はグローバルの CLAUDE.md の手順（`!` を頼む前に変わるファイルを確かめる）で手当てする（2026-11-18、人間の判断）。
- **信頼の判断:** paranoid は、人間が中身を確かめずに `mise trust` すると守れない。Claude は信頼を頼むときに、ファイルの全体と読み込む env ファイルを確かめるよう添える。拒否のメッセージ（`validate-command.sh`・`protect-main-branch.sh`）も同じ案内にした。
- **paranoid の外:**
  - tasks の `run` が呼ぶスクリプト（人間が `mise run` を選ぶ）。
  - 信頼済みの設定が PATH に足すディレクトリの中身（`[env] _.path = ["{{config_root}}/node_modules/.bin"]` など）。そこに sandbox から書けると、人間が cd した後に打ったコマンドが sandbox の外で動く。今の 6 つの設定は使っていない。Claude は信頼を頼むときに、このことも添える（/review の指摘）。
  - lockfile（`mise.lock`）。`config` の信頼の対象外で、sandbox から書ける。今の 6 つのリポジトリにはない。`provenance` が備えになる見込みだが確かめていないので、次の作業で扱う（/review の指摘）。
  - グローバルの設定への直接の書き込み（`./mise` の denyWrite、作業ディレクトリの外、6.2 の 3 つの denyWrite で守る）。
  - プロジェクトの `[env]` に `MISE_PARANOID` を書いたときの動き（文書にない。設定そのものに信頼が要るので、信頼されるまでは効かない）。
- **dotfiles の、リンクで使われているファイルの git 経由の書き換え:** [2 章](#goals)の非目標の 1 つ目。この作業の前からある経路で、この作業では広がりも狭まりもしない。グローバルの mise 設定もここに入り、paranoid では守れない。次の作業で扱う（2026-11-17、人間の判断）。
- **フックの迂回（B2）:** フックは、呼ばれた時点の状態だけを見る。前のセッションで `~/.gstack/projects` を symlink に差し替えておき、次のセッションで、Bash が実体のディレクトリに戻してから Write ツールを使うと、フックは通す。起動時に解決した先は、作業ディレクトリのまま残る見込み（推測）。成り立たせるには、根を差し替え、次のセッションに指示を持ち越す、という 2 段階の仕込みが要る。sandbox から根を差し替えられるかも未確認（[research の 4 章](research-path-gaps.md#remaining)）。/review で、根ごと `$TMPDIR` に移せるなら gstack の記録を消さずに済み、気付かれにくいことが指摘された。受け入れの判断は、2 段階の仕込みが要ることに基づくので変えない。受け入れて記録する（2026-11-17、人間の判断）。起動時の状態を SessionStart のフックで記録して比べる案は、フックが 2 つになり、入力の JSON を読む（jq に頼る）必要が出るので採らない。
- **ホームの外:** `/tmp` に clone したものなどは、もともと denyWrite で守れなかった。paranoid で守れるようになる。

<a name="builder"></a>

## 8. ビルダーに任せること

- テストの名前と数（6.3・6.4 の最低限の場合を含める）、`check-repo.py` の関数と検査名の分け方。
- フックのメッセージの文面。
- 6.6 のパッチの当て方。
- コミットの分け方（1 コミット = 1 つの論理的な変更）。`.gitignore`（`tmp/`・`.tmp/`）と research も、このブランチのコミットにする。
- `mise/mise_config.toml` のコメントの文面。
