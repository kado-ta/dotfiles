---
status: in-progress
created: 2026-11-24
---

# cc-crit のポート範囲の移行の試験記録

関連: [plan.md](plan.md)

<a name="sandbox"></a>

## sandbox の中（Claude）

2026-11-24 に、ブランチ `fix/cc-crit-port-range` の worktree で実行した。

| コマンド | 結果 |
| --- | --- |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` | 94 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py` | skipped=1（sandbox の中では `sandbox-exec` を入れ子にできない） |
| フックの回帰テスト 7 つ（`$TMPDIR` から絶対パスで実行） | すべて fail=0（`test-guard-playwright-mcp.sh` は pass=51） |
| `python3 -B claude/scripts/test-register-mcp.py` | 21 件 OK |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 93 件 OK |
| shellcheck（CLAUDE.md の規約のコマンド）、`actionlint` | 指摘なし |

テストを先に変えたときの失敗:

- 範囲を移す前: `test_ports_exclude_47809` が失敗した（`47809 unexpectedly found in range(47800, 47820)`）。フックのテストは 4 件、`test-register-mcp.py` は 1 件失敗した。
- 守りを 47800〜47829 にする前: フックのテストの 47800 と 47809 の 2 件、`test-register-mcp.py` の 1 件が失敗した。

`test_playwright_guards_cover_the_wrapper_ports` は、`PORTS` を `range(47810, 47831)`（守りの外の 47830 を含む）に差し替えると失敗した。

<a name="probes"></a>

## 動作の確認（Claude、sandbox の中）

- フックに `browser_navigate` の `url` を渡した。47799 と 47830 は通り（exit 0）、47800・47808・47809・47810・47819・47820・47829 は止まった（exit 2）。
- `check_ports` の `port_listening` を差し替えて、待ち受けを模した。
  - 47809 だけが使われているとき: 47810 を返した（拒否しない）。
  - 47815 か 47829 が使われているとき: `port … is in use by something other than cc-crit's crit` で拒否した。

<a name="outside"></a>

## sandbox の外（人間）

[plan の確かめること](plan.md#verification)と[入れる手順](plan.md#rollout)のとおりに行い、結果をここに書く。

- [x] 古い profile で、47809 の拒否のテストが 2 件失敗する
- [x] 新しい profile で、`test-cc-crit-profile.py` が通る（ステルスモードがオンのあいだは、環境による ERROR が 1 件。下記）
- [ ] 端末ごと: `cmp` が何も出さない、`mise run crit:profile-test` が通る、`/crit-review` で Crit が 47810 で開く

2026-11-24 に、人間が worktree で実行した（crit 0.24.0、git 2.56.1、macOS 26.7.1）。

- 古い profile（`c007b65` の `cc-crit.sb` を `CC_CRIT_PROFILE` で指定、`-k excluded`）: `test_bind_loopback_excluded_port_denied` と `test_connect_loopback_excluded_port_denied` が、どちらも `ALLOWED` で失敗した。
- 新しい profile: 29 件のうち、28 件が通るかスキップされた（スキップは `~/.lima/_config` がない 1 件）。`test_crit_review_answers_health` が ERROR になった。
  - crit は範囲のポートで起動し、`127.0.0.1` の `/api/health` は `ok` を返した。
  - 最後の確認で、LAN のアドレスの同じポートへの接続が、拒否（`ConnectionRefusedError`）ではなく `socket.timeout` になった。
- ERROR の切り分け: 人間が通常のターミナルで、自分の LAN のアドレスの 47800・47809・47810・47829・47900・50123 に接続した。どれも `timeout` だった。
  - この Mac は、自分の LAN のアドレスへの接続を、ポートによらず応答なしで落とす。今回の範囲の変更とは関係しない。
  - 変更前の範囲でも同じになる見込み（main のテストは実行していない）。接続は成立していないので、LAN から届かないことは崩れていない。
  - テストは変えない。タイムアウトも通すと、この環境では、全インターフェースで待ち受けたときとの区別がつかなくなるため。
  - 原因はファイアウォールのステルスモードだった。人間がステルスモードをオフにして同じ接続を試すと、6 つのポートはどれも `refused` になった。ステルスモードがオンのあいだは、`test_crit_review_answers_health` は範囲によらず失敗する。
  - ステルスモードをオフにして `test-cc-crit-profile.py -k health` を実行すると、`test_crit_review_answers_health` は通った。新しい profile では、profile のテストがすべて通った。

<a name="codex"></a>

## Codex のレビュー

上限 5 回のうち 1 回目。結果は `~/.codex/sessions` の記録の最終メッセージから読んだ。

| 回 | 時刻（UTC） | コミット | 結果 |
| --- | --- | --- | --- |
| 1 | 2026-11-23T17:53:19Z | `75406e7` | 指摘 1 件（P2）。「patch is incorrect」。整合テスト、Playwright の定義のテスト、リポジトリの検査、ShellCheck、actionlint は通過したと報告 |

1 回目の指摘「[P2] 新ポートを使う前に Playwright の遮断設定を有効にする」（`claude/bin/cc-crit:39`、confidence 0.98）:

- 内容: 入れる手順は、cc-crit を先に入れることを許していた。前の `--blocked-origins` の MCP セッションが残っているあいだに、新しい cc-crit が 47820〜47829 で Crit を開くと、ブラウザの中の移動で届く。入れるときは、古い MCP セッションを終えて新しい設定を効かせてから新しい cc-crit を使い始め、戻すときは、新しい cc-crit と daemon を止めてから範囲を縮める順にすべき、という指摘。
- 採否: 採る。plan で受け入れていた隙間だが、`cc-crit review` は許可なしで実行できるので、操られたモデルがレビューを 11 件以上重ねれば作れる。守りを新旧の範囲の和にしたので、`register-mcp.sh` を先にしても危険はない。plan の入れる手順と戻す手順で順番を固定し、作業中は Claude Code のセッションを閉じることにした（コードは変えない）。

<a name="ports"></a>

## ポートの登録の確認

2026-11-24 に確かめた。

- `/etc/services`（macOS）: 47806 ap と 47808 bacnet だけが載っている。47809〜47829 はない。
- IANA の登録簿（検索ページの表を WebFetch で読んだ。最終更新 2026-11-19）:
  - 47806 ap（tcp・udp）
  - 47808 bacnet（tcp・udp）
  - 47809 presonus-ucnet（udp。説明は「PreSonus Universal Control Network Protocol」）。tcp は Reserved
  - 47810〜47999 Unassigned
