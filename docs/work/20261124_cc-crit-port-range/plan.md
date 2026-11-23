---
status: done
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
- Playwright MCP の守り（フックと `--blocked-origins`）は、新旧の範囲の和の 47800〜47829 を止める。cc-crit が使うのは 47810〜47829 だけ（2026-11-24、`/review` の後の人間の判断。理由は[レビューで変えたこと](#review-changes)）。

<a name="changes"></a>

## 変えるもの

| ファイル | 変更 |
| --- | --- |
| `claude/bin/cc-crit` | `PORTS = range(47810, 47830)` |
| `claude/bin/cc-crit.sb` | bind・inbound・outbound の 60 項目とコメントを 47810〜47829 にする |
| `claude/hooks/guard-playwright-mcp.sh` | 正規表現を `:0*478[0-2][0-9](?![0-9])`（47800〜47829）にし、コメントとメッセージの範囲を変える |
| `claude/mcp/playwright.json` | `--blocked-origins` を `*:47800;…;*:47829`（30 項目）にする |
| `claude/README.md` | 範囲の記述 3 か所 |
| `.claude/rules/CLAUDE_CONFIG.md` | 範囲の記述と、移す前の範囲も止める理由 |
| テスト 4 つ | [テスト](#tests)のとおり |

完了した作業文書（`docs/work/2026111*`）の 47800〜47819 は、その時点の記録なので変えない。

<a name="tests"></a>

## テスト

先にテストを変えて失敗を確かめ、それから実装を変える。

| テスト | 変更 | 変更前の実装での結果 |
| --- | --- | --- |
| `claude/hooks/tests/test-cc-crit.py` | profile の bind・inbound・outbound のポートが、それぞれ `PORTS` と同じ並びであることを確かめる静的なテストを足す。`PORTS` に 47809 が入らないことも確かめる。フックが `PORTS` のすべてを止め、`--blocked-origins` が `PORTS` を含むことを確かめるテストも足す | 47809 のテストが失敗する |
| `claude/hooks/tests/test-cc-crit-profile.py` | `PORTS` を新しい範囲にする。47809 での待ち受けと、47809 への接続が拒否されるテストを足す | 47809 のテストが失敗する（sandbox の外でだけ動く） |
| `claude/hooks/tests/test-guard-playwright-mcp.sh` | 止める範囲のすぐ外を 47799 と 47830 にし、止める例に 47800・47809 と新しい範囲（境界の 47810・47829 を含む）を入れる | 新しい範囲の 47820〜47829 が通って失敗する |
| `claude/scripts/test-register-mcp.py` | `--blocked-origins` の期待値を `range(47800, 47830)` にする | 失敗する |

<a name="verification"></a>

## 確かめること

sandbox の中（Claude）:

- `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py`
- フックの回帰テスト 7 つ（CLAUDE.md の規約のとおり。`$TMPDIR` から絶対パスで実行する）
- `python3 -B claude/scripts/test-register-mcp.py`
- `python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、shellcheck、`actionlint`

sandbox の外（人間。差分を Crit で確かめた後）:

- worktree で、47809 の拒否のテストが古い profile で失敗し、新しい profile で通ること（リポジトリの profile を試す）:

  ```sh
  git show c007b65:claude/bin/cc-crit.sb > "$TMPDIR/cc-crit-old.sb"
  CC_CRIT_PROFILE="$TMPDIR/cc-crit-old.sb" /usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py -k excluded  # 2 件失敗する
  /usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py  # すべて通る
  ```

- 入れた後に、[入れる手順](#rollout)の `cmp` と `mise run crit:profile-test`、`/crit-review` で Crit が 47810 で開くこと

<a name="rollout"></a>

## 入れる手順（端末ごと）

フック（main を取り込むと、リンクで即座に効く）・cc-crit（sudo で入れ直す）・Playwright MCP の定義（`register-mcp.sh` で登録し直し、セッションを始め直すと効く）の 3 つは、効き始める時期がずれる。フックが止めるのはツールの `url` 引数での直接の移動だけで、JS やリンクでの移動は `--blocked-origins` だけが止める。どちらも新旧の範囲の和（47800〜47829）を止めるので、新しい `--blocked-origins` を効かせてから新しい cc-crit を入れれば、Crit が待ち受けるポートは、どの時点でも両方の守りの中にある。

1. 開いている Crit のレビューをすべて終え（承認すると daemon は止まる）、Claude Code のセッションをすべて閉じる。前に開いたレビューには、入れ直した後の `cc-crit reply` が届かない。
2. `sudo lsof -nP -iTCP:47800-47829 -sTCP:LISTEN` で、crit の daemon が残っていないことと、47810〜47829 にほかのアプリケーションがないことを確かめる（`sudo` がないと、ほかのユーザーのプロセスが見えない）。もう一方の端末の 47809 のアプリケーションは出てよい。47810〜47829 にほかのアプリケーションがあれば、入れずに止め、範囲を考え直す。
3. `~/dotfiles` で main を取り込み、`/bin/bash ~/dotfiles/claude/scripts/register-mcp.sh` を実行する（`setup.sh` から呼ばれてもよい）。
4. [README のインストール](../../../claude/README.md#cc-crit-install)のとおりに `cc-crit` と `cc-crit.sb` を入れ直す。`cmp claude/bin/cc-crit /usr/local/libexec/claude-crit/cc-crit` と `cmp claude/bin/cc-crit.sb /usr/local/libexec/claude-crit/cc-crit.sb` が何も出さないことを確かめてから、`mise run crit:profile-test` を実行する。このテストはリポジトリの profile を試すので、入れたものとの一致は `cmp` で確かめる。
5. 新しいセッションで `/crit-review` を実行し、Crit が 47810 で開くことを確かめる。

手順 3 と 4 を入れ替えない。cc-crit を先に入れると、前の定義の `--blocked-origins`（47800〜47819）が残るあいだに、新しい cc-crit が 47820〜47829 で開いた Crit へ、JS やリンクで移動できる（同時に 11 件以上のレビューを開いたとき。[Codex のレビュー](test-report.md#codex)の指摘）。作業のあいだセッションを閉じておくのは、動いている MCP サーバーが、セッションを始め直すまで前の定義のままだから。

<a name="rollback"></a>

## 戻す手順

開いているレビューを終え、Claude Code のセッションをすべて閉じてから行う。PR を revert して main を取り込み、先に `cc-crit` と `cc-crit.sb` を入れ直す。`sudo lsof -nP -iTCP:47810-47829 -sTCP:LISTEN` で crit の daemon が残っていないことを確かめてから、`register-mcp.sh` を実行する。この順なら、守りが 47800〜47819 に縮む前に、新しい cc-crit とその daemon は止まっている。もう一方の端末では、47809 があるので、cc-crit は前と同じく拒否する。

<a name="risks"></a>

## 影響とリスク

- 変更の前に開いたレビューに、変更の後の `cc-crit reply` は届かない（`PORTS` の外の記録は使わない）。手順 1 で避ける。
- 専用 HOME の古い session ファイル（47800〜47819）は、`PORTS` の外なので無視される。消す必要はない。
- cc-crit の範囲の広さ（20）は変わらない。フックと `--blocked-origins` は 47800〜47829 を止めるので、Playwright MCP から 47800〜47809（もう一方の端末の 47809 のアプリケーションも）を開けなくなる。
- 47809 のアプリケーションが何かは分かっていない。2 つ目のインスタンスで 47810 を使う種類なら、cc-crit はまた拒否する（拒否する側に倒れるので、起きるのは使えなくなることだけ）。

<a name="review"></a>

## レビュー

高リスク（sandbox の profile のネットワークと、承認を守るフック）なので、`/review` の後に `/security-review` を行い、Codex のレビューを提案する。push と PR の前に、ブランチの差分を `/crit-review` で開く。

<a name="review-changes"></a>

## レビューで変えたこと

`/review`（専門レビュー 5 つと adversarial）の指摘のうち、次を採った（2026-11-24、人間の判断）。

- フックと `--blocked-origins` は、新旧の範囲の和（47800〜47829）を止める。
  - 3 つの部品は更新の時期がずれ、`register-mcp.sh` は `setup.sh` や Node の更新でも動く。
  - どちらの守りも新しい範囲だけにすると、`register-mcp.sh` が sudo での入れ直しより先に動いたとき、古い cc-crit が 47800 で開いた Crit を、フックも `--blocked-origins` も止めない。戻すときも同じことが起きる。
  - 和にすれば、順番によらず守られる。代わりに、Playwright MCP から 47800〜47809 を開けなくなる。
- `test-cc-crit.py` に、フックが `PORTS` のすべてを止め、`--blocked-origins` が `PORTS` を含むことを確かめるテストを足す。範囲を書く 4 か所のうち、`PORTS` と照らしていたのは profile だけだった。
- 入れたファイルとリポジトリを `cmp` で比べる手順を足す。`mise run crit:profile-test` はリポジトリの profile を試すので、入れ忘れや、違うブランチからの入れ直しに気づけない。cc-crit の起動時に確かめる案は採らない（root 所有のラッパーに profile の解析を足すことになり、依頼の範囲を超える）。
- 47809 の拒否のテストを、古い profile で失敗させてから新しい profile で通す手順を、[確かめること](#verification)に足す。

Codex のレビュー（1 回目）の指摘を受けて、[入れる手順](#rollout)と[戻す手順](#rollback)の順番を固定した（2026-11-24）。入れるときは `register-mcp.sh` を先に、戻すときは cc-crit を先にし、どちらも作業のあいだ Claude Code のセッションを閉じる。記録と採否は [test-report.md](test-report.md#codex) にある。
