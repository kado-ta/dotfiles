---
status: in-progress
created: 2026-11-24
---

# cc-crit のポート範囲を 47810〜47829 に移す

別の端末で、cc-crit のポート範囲（47800〜47819）の 47809 を別のアプリケーションが使っていた。cc-crit は、範囲の中に cc-crit 以外の待ち受けが 1 つでもあると拒否する（`check_ports`）ので、その端末では Crit のレビューを開けない。範囲を 47809 を含まない 20 ポートに移す。

関連: [docs/work/20261111_crit-sandbox/design.md](../20261111_crit-sandbox/design.md)（範囲を cc-crit の daemon だけに限る理由。4.4 と P1）、[docs/work/20261118_playwright-mcp/plan.md](../20261118_playwright-mcp/plan.md)（Crit のポートを Playwright MCP から開かせない理由）

<a name="decision"></a>

## 決めたこと

- 新しい範囲は 47810〜47829（2026-11-24、人間の判断）。同時に開けるレビューの数（20）を変えない。
- 47810〜47829 は IANA で未割り当て。古い範囲 47800〜47819 は、登録済みの 47806（ap）・47808（bacnet）・47809（presonus-ucnet。PreSonus Universal Control の UDP）を含んでいた（2026-11-24 に IANA の登録簿と `/etc/services` で確かめた）。
- 使われているポートを飛ばして起動する案は採らない。範囲の中に cc-crit 以外の待ち受けがあると、profile の中の crit がそこへ接続できる（design の P1）。拒否は守りとして残し、範囲から外す。
- 比べた案:
  - 47800〜47808 に縮める: もう一方の端末で空いていたことがわかっている（`check_ports` は 47800 から順に調べ、47809 で止まった）。ただし、同時に開けるレビューは 9 つになる。
  - 47809 だけ抜く（19 ポート）: 範囲が飛び飛びになり、正規表現・profile・テストが読みにくくなる。
- 47810〜47829 は、もう一方の端末でも空いている。2026-11-24 に人間が `sudo lsof -nP -iTCP:47810-47829 -sTCP:LISTEN` を実行し、何も出なかった。入れる直前にもう一度確かめる（[入れる手順](#rollout)）。

<a name="changes"></a>

## 変えるもの

| ファイル | 変更 |
| --- | --- |
| `claude/bin/cc-crit` | `PORTS = range(47810, 47830)` |
| `claude/bin/cc-crit.sb` | bind・inbound・outbound の 60 項目とコメントを 47810〜47829 にする |
| `claude/hooks/guard-playwright-mcp.sh` | 正規表現を `:0*478[12][0-9](?![0-9])` にし、コメントとメッセージの範囲を変える |
| `claude/mcp/playwright.json` | `--blocked-origins` を `*:47810;…;*:47829` にする |
| `claude/README.md` | 範囲の記述 3 か所 |
| `.claude/rules/CLAUDE_CONFIG.md` | 範囲の記述 1 か所 |
| テスト 4 つ | [テスト](#tests)のとおり |

完了した作業文書（`docs/work/2026111*`）の 47800〜47819 は、その時点の記録なので変えない。

<a name="tests"></a>

## テスト

先にテストを変えて失敗を確かめ、それから実装を変える。

| テスト | 変更 | 変更前の実装での結果 |
| --- | --- | --- |
| `claude/hooks/tests/test-cc-crit.py` | profile の bind・inbound・outbound のポートが、それぞれ `PORTS` と同じ並びであることを確かめる静的なテストを足す。`PORTS` に 47809 が入らないことも確かめる | 47809 のテストが失敗する |
| `claude/hooks/tests/test-cc-crit-profile.py` | `PORTS` を新しい範囲にする。47809 での待ち受けと、47809 への接続が拒否されるテストを足す | 47809 のテストが失敗する（sandbox の外でだけ動く） |
| `claude/hooks/tests/test-guard-playwright-mcp.sh` | 範囲のすぐ外を 47809 と 47830 にし、止める例を新しい範囲（境界の 47810・47829 を含む）に変える | 47809 が止まり、新しい範囲の 47820〜47829 が通って失敗する |
| `claude/scripts/test-register-mcp.py` | `--blocked-origins` の期待値を `range(47810, 47830)` にする | 失敗する |

<a name="verification"></a>

## 確かめること

sandbox の中（Claude）:

- `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py`
- フックの回帰テスト 7 つ（CLAUDE.md の規約のとおり。`$TMPDIR` から絶対パスで実行する）
- `python3 -B claude/scripts/test-register-mcp.py`
- `python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、shellcheck、`actionlint`

sandbox の外（人間。差分を Crit で確かめた後）:

- worktree で `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`（リポジトリの profile を試す）
- 入れた後に、`mise run crit:profile-test` と、`/crit-review` で Crit が 47810 で開くこと

<a name="rollout"></a>

## 入れる手順（端末ごと）

フック（リンクで即座に効く）・cc-crit（sudo で入れ直す）・Playwright MCP の定義（`register-mcp.sh` で登録し直す）の 3 つで、効き始める時期がずれる。Crit が待ち受けるポートを、フックか `--blocked-origins` のどちらかが常に止めているように、次の順で行う。

1. 開いている Crit のレビューをすべて終える（承認すると daemon は止まる）。古い範囲で動いている daemon が残ると、手順 4 の後はどちらも止めない。
2. `sudo lsof -nP -iTCP:47810-47829 -sTCP:LISTEN` で何も出ないことを確かめる（`sudo` がないと、ほかのユーザーのプロセスが見えない）。出たら入れずに止め、範囲を考え直す。
3. `~/dotfiles` で main を取り込み、[README のインストール](../../../claude/README.md#cc-crit-install)のとおりに `cc-crit` と `cc-crit.sb` を入れ直し、`mise run crit:profile-test` を実行する。
4. Playwright MCP を使っているセッションを閉じ、`/bin/bash ~/dotfiles/claude/scripts/register-mcp.sh` を実行する。

手順 4 を 3 より先にしない（`setup.sh` も `register-mcp.sh` を呼ぶ）。古い cc-crit が 47800 で Crit を開いたとき、フックも `--blocked-origins` も止めなくなる。手順 3 と 4 のあいだは、フックが新しい範囲を止める。

<a name="rollback"></a>

## 戻す手順

PR を revert して main を取り込み、上と同じ順で、`cc-crit` と `cc-crit.sb` を入れ直してから `register-mcp.sh` を実行する。もう一方の端末では、47809 があるので、cc-crit は前と同じく拒否する。

<a name="risks"></a>

## 影響とリスク

- 変更の前に開いたレビューに、変更の後の `cc-crit reply` は届かない（`PORTS` の外の記録は使わない）。手順 1 で避ける。
- 専用 HOME の古い session ファイル（47800〜47819）は、`PORTS` の外なので無視される。消す必要はない。
- 守りの強さは変わらない。範囲の広さは同じで、profile・フック・`--blocked-origins` は同じ範囲を指す。

<a name="review"></a>

## レビュー

高リスク（sandbox の profile のネットワークと、承認を守るフック）なので、`/review` の後に `/security-review` を行い、Codex のレビューを提案する。push と PR の前に、ブランチの差分を `/crit-review` で開く。
