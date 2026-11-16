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
- 作業ディレクトリの中でも、人間が操作しなくても sandbox の外で動くファイルは守る。`.git` の hooks は Edit を deny にしている（Bash は、sandbox が既定で `.git/hooks` と `.git/config` を止める。submodule の `.git/modules/*/` の下は、この一覧に入っていない）。mise の設定（`mise.toml`、`.tool-versions` など）は、Edit を ask にし、`sandbox.filesystem.denyWrite` にも入れている。mise は、信頼済みのパスに cd したときに、設定の hooks・`_.source`・`exec()` を動かすため。
- mise の `denyWrite` は `~/**/` の形にしている。ユーザー設定の `sandbox.filesystem` のパスは、接頭辞がないと `~/.claude` が基準になり、作業ディレクトリに当たらない。権限の規則（`Read(...)`・`Edit(...)`）は、接頭辞がないとカレントディレクトリが基準なので、同じ `**/mise.toml` でも当たる場所が違う。ホームの外（`/tmp` に clone したものなど）は、sandbox では守れない。`check-repo.py` は、ユーザー設定の `denyRead`・`denyWrite`・`allowWrite`・`allowRead` の全項目が `~/` か `/` で始まることを確かめる。
- mise の Edit の ask は、接頭辞のない形と `//**/` の形を併記している。`.git` は、接頭辞のない hooks の deny に加えて、`//**/` の形の hooks と config の ask を置いている。接頭辞のない形も、`/add-dir` で足したディレクトリに当たる（2026-11-16 に実測。`.git/hooks` と `.git/config` は、ask の `//**/` の形より先に、接頭辞のない deny で拒否された）。`//**/` の形は、文書が接頭辞のない形の起点をカレントディレクトリとしているので、`/cd` などで起点が変わったときの備えとして残している。
- Edit の deny の規則は、sandbox の denyWrite にもなる（ask はならない）。`.git` の `//**/` の形を deny にすると、sandbox の中のどこでも `git init`・`git clone` が hooks のサンプルを写せずに失敗する見込みなので、ask にしている（deny にすると `check-repo.py` が失敗する）。接頭辞のない hooks の deny も、起動したディレクトリの中では同じ働きをする。入れ子のリポジトリの `git init`・`git clone` と、`hooks` という名前の階層を含む refs（`fix/hooks/x` のようなブランチ）への書き込みは、sandbox の中で失敗しうる。
- `permissions.additionalDirectories` に `~/.gstack/projects` を入れている。gstack のスキル（`/office-hours`・`/context-save` など）は、Write ツールでそこに書く。sandbox の allowWrite にも入っていて、Bash はもともと書けるので、書ける範囲は広がらない。`additionalDirectories` は sandbox の書き込み範囲にもなるので、`check-repo.py` は allowWrite にも同じパスがあることを確かめる。設定ファイルの `additionalDirectories` は、そのディレクトリの `.claude` の設定を読み込まない。ほかのディレクトリを足すと、そこでは `blockWritesOutsideWorkingDirectories` が効かなくなるので、`check-repo.py` が失敗する。
- `.claude/settings.json` の ask に `Edit(/claude/**)` があるのは、worktree ではユーザー設定の `Edit(~/dotfiles/claude/**)` が当たらないため。
- Read の deny の `*.pem` を `~/**` に広げないのは、mise で入れた pip・Ruby・aws-cli の CA 証明書の束が `~/.local/share/mise` の下にあり、sandbox の中でそれらの HTTPS が失敗する見込みのため。

経緯は [docs/work/20261114_edit-write-rules/research-edit-write.md](../../docs/work/20261114_edit-write-rules/research-edit-write.md) を参照する。この規則の外に残る経路と、次の作業の候補は、その [8 章](../../docs/work/20261114_edit-write-rules/research-edit-write.md#residual-risks) にある。
