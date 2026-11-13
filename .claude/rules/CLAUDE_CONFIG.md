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
