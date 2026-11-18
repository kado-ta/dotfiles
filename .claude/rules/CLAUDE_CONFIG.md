---
paths:
  - "claude/**"
  - ".claude/**"
  - ".github/scripts/**"
---

# Claude Code 設定の設計メモ

`claude/`・`.claude/`・`.github/scripts/` のファイルを扱うときに読み込まれる。PR と Crit のラッパーと、sandbox 設定の設計理由を書く。禁止事項そのものは、常に読み込まれるルートの [CLAUDE.md](../../CLAUDE.md#sandbox-prohibitions) にある。

<a name="cc-safe-pr"></a>

## PR の作成・編集（cc-safe-pr）

Claude からの PR の作成・編集は、`claude/bin/cc-safe-pr` を root 所有でインストールしたラッパーで行う。`settings.json` は、`create` / `edit` の完全一致だけを `permissions.allow` と `sandbox.excludedCommands` に入れている。許可リストは `cc-safe-push` と共通で、リポジトリの判定には `cc-safe-push` の `evaluate()` をそのまま使う。

許可リストにないリポジトリでは拒否するので、人間が自分の端末で `gh pr create` を実行する。sandbox 内の `gh` は読み取り専用トークンで動くので、`permissions.ask` と `hooks/ask-gh-pr-write.sh` の承認画面で承認しても書き込めない（403）。

ラッパーは `evaluate()` の外で git を実行しない。index を読む git は `core.fsmonitor` を起動し、`core.hooksPath` では止まらないので、sandbox の外で任意のコードが動く経路になる。

sandbox 内からは Keychain を読めない（`sandbox.filesystem.denyRead`）ので、書き込みのできる `gh` のトークンを使えるのは、このラッパーと `cc-safe-push`、人間の端末だけ。sandbox 内の `gh` には `hooks/gh-read-token.sh` が読み取り専用トークンを渡す。詳細は [claude/README.md](../../claude/README.md#gh-read-token) を参照する。

<a name="cc-crit"></a>

## Crit のレビュー（cc-crit）

Claude から Crit の対話レビューを開くときは、`claude/bin/cc-crit` を root 所有でインストールしたラッパーを使う（個人スキル `/crit-review`）。`settings.json` は、`review` / `reply` の完全一致だけを `permissions.allow` と `sandbox.excludedCommands` に入れている。ラッパーは、crit を Crit 専用の Seatbelt profile（`claude/bin/cc-crit.sb`）と専用の HOME（`~/.cc-crit/crit-home`）の中で動かす。

`sandbox.filesystem.allowWrite` に `~/.crit` 配下を入れない。sandbox の外で動く crit（Crit プラグインの plan-hook と、人間が端末で実行する crit）は `~/.crit` の hooks・prompts・session・レビューを信頼するので、sandbox から書けると sandbox を抜ける経路になり、承認も偽造できる。`allowLocalBinding` も使わない（全インターフェースでの待ち受けと、localhost の全ポートへの接続を、sandbox 内のすべてのコマンドに許すことになる）。経緯は [docs/work/20261111_crit-sandbox/design.md](../../docs/work/20261111_crit-sandbox/design.md) を参照する。インストール手順は [claude/README.md](../../claude/README.md#cc-crit-install) を参照する。

`sandbox.network` の `allowUnixSockets`・`allowAllUnixSockets`・`allowLocalBinding` は設定しない（`check-repo.py` の `push-permissions` が失敗する）。Colima は既定で `$HOME` を書き込み可能でマウントするので、Docker のソケットや VM の SSH に届くと、`$HOME` のどこにでも書けて sandbox を抜けられる。同じ理由で、Colima（Lima）の VM に入る鍵（`~/.colima/_lima/_config`）を `denyRead` で読ませない。経緯は [docs/work/20261113_sandbox-escape-hardening/research-sandbox-escape.md](../../docs/work/20261113_sandbox-escape-hardening/research-sandbox-escape.md#risk-colima) を参照する。

<a name="cc-checkout-guard"></a>

## git の確認（cc-checkout-guard）

sandbox の中で作られたコミット・index・ref は、sandbox の外で動く git（人間の端末と `!`、`claude -w` の worktree の作成）によって、自動で読み込まれたり動いたりするファイルとして書かれうる。denyWrite と Edit の deny は sandbox の中のプロセスだけを縛るので、この経路には効かない。そこで、人間の zsh の `git`（`bin/.zshrc` の関数）と `WorktreeCreate` フックが、書く前に `claude/bin/cc-checkout-guard` で中身を確かめる。設計は [docs/work/20261118_git-route-writes/design.md](../../docs/work/20261118_git-route-writes/design.md) を、使い方は [claude/README.md](../../claude/README.md#cc-checkout-guard) を参照する。

- 確認コマンドは root 所有で置き、対象の一覧もその中に持つ。リポジトリの中の設定ファイルに一覧を置くと、一覧そのものを git の経路で書き換えられるため。関数は小さくし、どのサブコマンドを確かめるかなどの判断は、すべて確認コマンドで行う。関数とフックの登録は、sandbox から直接書けず、git の経路も関数が守るファイル（`bin/`・`claude/`）に置く。
- sandbox の中かどうかは、OS に問い合わせて（`sandbox_check`）決める。`SANDBOX_RUNTIME` などの環境変数は見ない。環境変数は `! SANDBOX_RUNTIME=1 git switch x` のように `!` でも付けられ、`command git` より目立たずに確認を飛ばせるため。確認コマンドは shebang の `env -i` で起動し、人間の環境変数で動きを変えられないようにしている。問い合わせに失敗したら、sandbox の外として扱う（確認が働く側に倒す）。sandbox の中で確かめずに通すのは、書き込みは sandbox が止め、関数は `command git` で飛ばせるので、確かめても守りにならないため。
- `claude -w` では、新しい worktree の対象のファイルを、元のチェックアウトの同じファイルと比べる。元のチェックアウトの対象のファイルは、sandbox から直接書けず、git の経路も関数が守るので、人間が確かめた中身とみなせる。書かれた結果を比べるので、ref・replace の ref・object のどれを差し替えられても見つかる。新しいディレクトリは、フックが終わるまでどのセッションからも読まれないので、書いた後に比べてよい。フックは、入力の `cwd` が元のチェックアウトの中にあることを、ファイルの同一性で確かめる。`.git/commondir` で共通の gitdir を別のリポジトリに向けられたときに、別のチェックアウトと比べないようにするため。
- worktree は、リポジトリの中（Claude Code の既定の `.claude/worktrees`）ではなく、ホームの下の `~/.cc-worktrees/<キー>/<name>` に作る（2026-11-19、人間の判断）。リポジトリの中は、元のチェックアウトで起動したセッションの sandbox が書ける。フックが確かめてから `git worktree add` するまでの間に `.claude/worktrees` を symlink に替えると、git が sandbox の外に書いた（レビューで実測。Claude Code の既定の `claude -w` にも同じ穴がある）。ホームの下は sandbox から書けないので、この競合が成り立たない。持ち主と mode の確認では人間と sandbox を区別できない（同じ uid）ので、`~` で起動したセッション（sandbox がホームに書ける）があると、この守りは崩れる。
- 入れ子のリポジトリ（作業ツリーの下の `.git` ファイルと `.git/modules/<名前>/config`）の設定からコードが動く経路は、次の作業にした。対象のファイルを書く経路ではなく、守り方（グローバルの git の設定、submodule の扱い）も別なため。確認を飛ばす形（`command git`・`\git`・絶対パスの git、zsh を通らない git）は、Claude が頼まないことを規則で決めているだけで、技術的には止めない。ほかに受け入れたリスクは、design の [7 章](../../docs/work/20261118_git-route-writes/design.md#accepted-risks) にある。

<a name="cso-state"></a>

## gstack の `/cso`

`sandbox.filesystem.allowWrite` に `~/.gstack/security/cso` を入れている。`/cso` は、ソースの読み取りも含めてすべての操作を `gstack-cso-launcher` で行い、そのたびにこの下に書く。ここに書けないと監査を始められない。

- `~/.gstack/security` ごとは許さない。隣の `egress.jsonl` は gstack が外部に送信した記録で、sandbox の中から改ざんできるようになるため。
- ランチャーを `excludedCommands` に入れない。引数はモデルが決め、モデルは監査対象（信頼しない入力）の影響を受ける。sandbox の外で任意の Git リポジトリを読めて `denyRead` を迂回でき、`--comprehensive` では Docker にも届く。
- 書き込みを許したので、sandbox の中のどのコマンドも cso の保存物（スナップショット・報告・修正案）を書き換えられる。sandbox の中から見た報告の完全性は保証しない。読み取りは前からできる。
- sandbox の中で動くのは静的な監査だけ。スキャナと `--comprehensive` は Docker が要り、Docker のソケットには上の理由で届かない。
- helper は、`.env*`・`*.pem`・`*.key` などの秘密ファイルも一度読んでマスキングし、写しを保存する。`permissions.deny` の `Read(...)` は sandbox の `denyRead` になり、`sandbox.filesystem.allowRead` でも外せない（2026-11-16 に実測）。そのため、これらを追跡しているリポジトリでは `start` が失敗する。回避の手順は [SKILL_INVENTORY.md](../../claude/SKILL_INVENTORY.md#cso-sandbox) にある。

<a name="edit-write-rules"></a>

## Edit・Write ツールの書き込み

Edit・Write ツールは sandbox の外で動くので、`permissions` の規則で守る。使い方はルートの [CLAUDE.md](../../CLAUDE.md#edit-write-rules) にある。

- `blockWritesOutsideWorkingDirectories` は、作業ディレクトリの外（ほかのリポジトリの `.git/hooks`、`~/Library/LaunchAgents` など）への書き込みを、場所を並べずにまとめて止める。作業ディレクトリの中の設定ファイルも拒むのは、設定ファイルからこの設定を外せるため。
- 作業ディレクトリの中でも、人間が操作しなくても sandbox の外で動くファイルは守る。`.git` の hooks は Edit を deny にしている（Bash は、sandbox が既定で `.git/hooks` と `.git/config` を止める。submodule の `.git/modules/*/` の下は、この一覧に入っていない）。mise の設定（`mise.toml`、`.tool-versions` など）は、Edit を ask にし、グローバルの設定の `paranoid`（`config`・`env_files`）で、信頼を中身のハッシュに結び付けている。mise は、信頼済みの設定がある場所に cd したときに、設定の hooks・`_.source`・`exec()` を動かす。パスで信頼すると、sandbox の中で作ったコミットや index を人間が sandbox の外の git 操作で書き出したときに、その中身が動く。paranoid では、中身が変われば、人間がファイルの全体と読み込む env ファイルを確かめて `mise trust <ファイル>` するまで読み込まない（mise は前の中身を持たないので、差分では確かめられない）。前は `sandbox.filesystem.denyWrite` にも入れていたが、mise の設定を追跡しているリポジトリで sandbox の中の git の操作が途中で止まるので外した（[design](../../docs/work/20261116_sandbox-path-gaps/design.md#approaches)）。
- `sandbox.filesystem.denyWrite` には、paranoid の土台の 3 つ（`~/.config/mise`・`~/dotfiles/mise`・`~/.local/state/mise`）を置いている。グローバルの設定は paranoid でもパスで信頼され、`~/dotfiles/mise` はその実体がある場所で、`~/.local/state/mise` には信頼の記録がある（書けると Claude が自分で信頼を済ませられる）。dotfiles で起動したセッションからは、もともと書けない場所だが、`~` などで起動したセッションのために置く。denyWrite が止めるのは Bash だけなので、Edit・Write ツールは `Edit(~/.local/state/mise/**)` の deny と `Edit(~/dotfiles/mise/**)` の ask で止める（`~/.config/mise` には `**/.config/mise/**` の ask が当たる）。ユーザー設定の `sandbox.filesystem` のパスは、接頭辞がないと `~/.claude` が基準になるので、`~/` を付ける。権限の規則（`Read(...)`・`Edit(...)`）は、接頭辞がないとカレントディレクトリが基準なので、同じ形でも当たる場所が違う。`check-repo.py` は、ユーザー設定の `denyRead`・`denyWrite`・`allowWrite`・`allowRead` の全項目が `~/` か `/` で始まることを確かめる。
- mise の Edit の ask は、接頭辞のない形と `//**/` の形を併記している。`.git` は、接頭辞のない hooks の deny に加えて、`//**/` の形の hooks と config の ask を置いている。接頭辞のない形も、`/add-dir` で足したディレクトリに当たる（2026-11-16 に実測。`.git/hooks` と `.git/config` は、ask の `//**/` の形より先に、接頭辞のない deny で拒否された）。`//**/` の形は、文書が接頭辞のない形の起点をカレントディレクトリとしているので、`/cd` などで起点が変わったときの備えとして残している。
- Edit の deny の規則は、sandbox の denyWrite にもなる（ask はならない）。`.git` の `//**/` の形を deny にすると、sandbox の中のどこでも `git init`・`git clone` が hooks のサンプルを写せずに失敗する見込みなので、ask にしている（deny にすると `check-repo.py` が失敗する）。接頭辞のない hooks の deny も、起動したディレクトリの中では同じ働きをする。入れ子のリポジトリの `git init`・`git clone` と、`hooks` という名前の階層を含む refs（`fix/hooks/x` のようなブランチ）への書き込みは、sandbox の中で失敗しうる。
- `permissions.additionalDirectories` に `~/.gstack/projects` を入れている。gstack のスキル（`/office-hours`・`/context-save` など）は、Write ツールでそこに書く。sandbox の allowWrite にも入っていて、Bash はもともと書けるので、書ける範囲は広がらない。`additionalDirectories` は sandbox の書き込み範囲にもなるので、`check-repo.py` は allowWrite にも同じパスがあることを確かめる。設定ファイルの `additionalDirectories` は、そのディレクトリの `.claude` の設定を読み込まない。ほかのディレクトリを足すと、そこでは `blockWritesOutsideWorkingDirectories` が効かなくなるので、`check-repo.py` が失敗する。
- `~/.gstack/projects` が symlink に差し替えられると、次のセッションの Edit・Write ツールはその先（`~/Library/LaunchAgents` など）に書ける（2026-11-16 に実測）。起動時に symlink が解決され、その先が作業ディレクトリとして扱われる見込みなので、PreToolUse のフック `hooks/guard-additional-dirs.sh` が、symlink のあいだは Edit・Write 系のツールをすべて止める。呼ばれた時点の状態だけを見るので、symlink を実体に戻してから書く迂回は止めない（受け入れている。[design の 7 章](../../docs/work/20261116_sandbox-path-gaps/design.md#accepted-risks)）。
- `.claude/settings.json` の ask に `Edit(/claude/**)` があるのは、worktree ではユーザー設定の `Edit(~/dotfiles/claude/**)` が当たらないため。
- Read の deny の `*.pem` を `~/**` に広げないのは、mise で入れた pip・Ruby・aws-cli の CA 証明書の束が `~/.local/share/mise` の下にあり、sandbox の中でそれらの HTTPS が失敗する見込みのため。

経緯は [docs/work/20261114_edit-write-rules/research-edit-write.md](../../docs/work/20261114_edit-write-rules/research-edit-write.md) を参照する。この規則の外に残る経路と、次の作業の候補は、その [8 章](../../docs/work/20261114_edit-write-rules/research-edit-write.md#residual-risks) にある。paranoid とフックの経緯と、受け入れたリスクは、[docs/work/20261116_sandbox-path-gaps/design.md](../../docs/work/20261116_sandbox-path-gaps/design.md) を参照する。
