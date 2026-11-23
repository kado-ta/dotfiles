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

未実施。[plan の確かめること](plan.md#verification)と[入れる手順](plan.md#rollout)のとおりに行い、結果をここに書く。

- [ ] 古い profile で、47809 の拒否のテストが 2 件失敗する
- [ ] 新しい profile で、`test-cc-crit-profile.py` がすべて通る
- [ ] 端末ごと: `cmp` が何も出さない、`mise run crit:profile-test` が通る、`/crit-review` で Crit が 47810 で開く

<a name="ports"></a>

## ポートの登録の確認

2026-11-24 に確かめた。

- `/etc/services`（macOS）: 47806 ap と 47808 bacnet だけが載っている。47809〜47829 はない。
- IANA の登録簿（検索ページの表を WebFetch で読んだ。最終更新 2026-11-19）:
  - 47806 ap（tcp・udp）
  - 47808 bacnet（tcp・udp）
  - 47809 presonus-ucnet（udp。説明は「PreSonus Universal Control Network Protocol」）。tcp は Reserved
  - 47810〜47999 Unassigned
