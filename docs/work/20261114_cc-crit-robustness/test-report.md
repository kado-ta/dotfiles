---
status: done
created: 2026-11-14
---

# cc-crit の競合と細かな不具合を直す（検証の記録）

[plan.md](plan.md) の Task 1〜9 を検証した記録。

<a name="environment"></a>

## 1. 環境

| 項目 | 版 |
| --- | --- |
| macOS | 26.7.1 |
| crit（Homebrew） | 0.23.2 |
| git（Homebrew。profile の中で crit が使う） | 2.56.1 |
| ラッパーの python3（CLT） | 3.9.6 |
| Go（テンプレートの確認だけに使った） | 1.27.4 |

<a name="automated"></a>

## 2. 自動テスト

Claude Code の Bash ツール（sandbox の中）で、worktree の `343d1d6` で実行した。`test-cc-crit.py` は、空白を直した `ae1c65b` でも実行した。profile のテストだけは、人間が sandbox の外で実行した。

| コマンド | 結果 |
| --- | --- |
| フックの回帰テスト 4 本（`test-protect-main-branch.sh`・`test-validate-command.sh`・`test-ask-gh-pr-write.sh`・`test-gh-read-token.sh`） | pass=94 / 29 / 66 / 24、fail=0 |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` | 53 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` | 75 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` | 91 件 OK（変更前は 84 件） |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`（人間、sandbox の外） | 27 件 OK（skipped=1: `~/.lima/_config` がない）。新しい 3 件も ok |
| `python3 -B .github/scripts/check-repo.py` | 8 項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 43 件 OK |
| shellcheck / actionlint | 指摘なし |

<a name="red-green"></a>

## 3. 先に失敗させたこと

| Task | 失敗させたテスト | 失敗の内容 |
| --- | --- | --- |
| 1 | `test_config_write_waits_for_the_lock` | ロックがないので、ほかの cc-crit がロックを持っていても review が成功した |
| 2 | `test_no_free_port_still_reconnects`、`test_no_free_port_without_a_session_explains` | ポートが尽きると crit を動かす前に失敗した。案内が `crit stop` を勧めていた |
| 3 | `BrowserTests` の 2 件 | URL が `localhost` だった |
| 4 | `test_fifo_settings_are_denied` | FIFO の読み込みで、5 秒たっても終わらなかった |
| 5 | `test_config_replaces_the_finish_prompt` | 設定に `prompts` がなかった |

先に失敗させられなかったもの:

- **Task 1 のロックを外すことの 3 件:** ロックがない間は通る。そこで、`StartLock.release` を何もしない形に差し替え、3 件とも失敗することを確かめた。
- **Task 7 の profile のテスト:** sandbox の中ではスキップされる。すでに拒否している規則にテストを足したもので、人間の実行で通ることを確かめた。

<a name="local-checks"></a>

## 4. 手元での確認

- **案内文のテンプレート（Task 5）:** crit と同じ Go の `text/template`（オプションなし）で、1 件と 2 件の場合を描画できた。session の埋め込みも、件数による分岐も正しかった。
- **mise のタスク（Task 9）:** `MISE_TRUSTED_CONFIG_PATHS` で worktree の設定だけを信頼させて確かめた。mise の状態には書き込んでいない。
  - `mise tasks` に `crit:profile-test` が出た。
  - `mise run crit:profile-test` でテストが起動した（sandbox の中なのでスキップ）。

<a name="e2e"></a>

## 5. E2E

人間がブランチの `cc-crit`（`343d1d6`）をインストールした後、Claude Code の Bash ツールから行った（2026-11-14）。インストールした版と `ae1c65b` の違いは、空白 1 つだけ。

| 確認 | 結果 |
| --- | --- |
| 2 つのレビューを同時に開く | A（`plan.md`）と B（`crit-review/SKILL.md`）を続けて起動した。A は 47800、B は 47801 で起動した |
| ブラウザ | `127.0.0.1:47800` と `127.0.0.1:47801` の 2 つのタブが、自動で開いた（人間が確認） |
| 新しい案内文（Task 5） | A にコメントを 1 つ付けて Finish した。出力は新しい案内文になり、session（`81bdbf2f644b`）も埋め込まれていた |
| 案内どおりの返信 | 案内どおりの依頼ファイルで `cc-crit reply` を実行し、`Added 1 reply` になった |
| 案内どおりの次のラウンド | `cc-crit review` で同じ daemon につなぎ直した（`Connected`）。コメントは解決済みになり、承認された |
| B | コメントなしで承認された |

<a name="codex"></a>

## 6. Codex のレビュー

この PR の 1 回目（2026-11-14）を、`codex review --base main`（読み取り専用）で受けた。

- **結果:** 指摘なし。`git diff --check` と `check-repo.py` は成功した。
- **Codex が確かめていないこと:** cc-crit の回帰テストと、Seatbelt profile の検証。読み取り専用の環境で一時ディレクトリを作れないため。どちらも、2 章と 5 章で実行済み。

<a name="not-verified"></a>

## 7. 確かめていないこと

- **E2E での競合:** 2 つのレビューが、実際にロックを取り合ったかは分からない（起動の時刻を記録していない）。ロックの動きは、自動テストで確かめている。
- **ポートが尽きた状態の E2E:** 20 個のポートを埋める必要があるので、行っていない。自動テストで確かめている。
- **sandbox の外での `mise run crit:profile-test`:** マージした後に、人間が通常のターミナルで実行する。
