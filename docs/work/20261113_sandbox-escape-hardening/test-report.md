---
status: done
created: 2026-11-14
---

# sandbox の外で実行されるものを守る（検証の記録）

[plan.md](plan.md) の Task 1〜5 を検証した記録。

関連: [research-sandbox-escape.md](research-sandbox-escape.md)

<a name="environment"></a>

## 1. 環境

| 項目 | 版 |
| --- | --- |
| macOS | 26.7.1 |
| CLT の python3（ラッパーの shebang） | 3.9.6 |
| CLT の git（`cc-safe-push` の `GIT`） | 2.54.0（Apple Git-157） |
| crit（Homebrew） | 0.23.2 |
| git（Homebrew。cc-crit の profile の中で crit が使う） | 2.56.1 |

<a name="automated"></a>

## 2. 自動テスト

Claude Code の Bash ツール（sandbox の中）で、worktree の `b612946` で実行した。profile のテストだけは、人間が sandbox の外で、`4695946` で実行した。

| コマンド | 結果 |
| --- | --- |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | pass=94 fail=0 |
| `bash claude/hooks/tests/test-validate-command.sh` | pass=29 fail=0 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | pass=66 fail=0 |
| `bash claude/hooks/tests/test-gh-read-token.sh` | pass=24 fail=0 |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` | 53 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` | 75 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` | 84 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`（人間、sandbox の外） | 24 件 OK（skipped=1: `~/.lima/_config` がない） |
| `python3 -B .github/scripts/check-repo.py` | 8 項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 43 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし |
| `actionlint` | 指摘なし |

<a name="red-green"></a>

## 3. 先に失敗させたこと

| Task | 失敗させたもの | 失敗の内容 |
| --- | --- | --- |
| 1 | `check-repo.py` | `project-permissions` で 22 項目（`ask` と `denyWrite` の不足） |
| 2 | `check-repo.py` | `push-permissions` で 3 項目（`Edit(~/.crit/**)` などの不足） |
| 3 | 3 本のテストの `InterpreterTests` | 8 件。shebang と `GIT` の値が違う。`DEVELOPER_DIR=/nonexistent` で `xcrun: error: missing DEVELOPER_DIR path` になる |
| 4 | `test-check-repo.py`、`check-repo.py`、`test-cc-crit.py` | 2 件、4 項目、1 件（`test_repository_settings_are_covered`。設定の `denyRead` が profile で覆われていない） |
| 5 | `test-check-repo.py` | 3 件の subTest（`allowUnixSockets`・`allowAllUnixSockets`・`allowLocalBinding`） |

先に失敗させられなかったもの:

- `test_empty_environment_prints_utf8`（cc-crit）: インタプリタの前提を確かめるテストなので、変更前から通る。
- profile のテストの Lima の 2 件: sandbox の中ではスキップされる。人間の実行で、通ることだけを確かめた。

<a name="measurements"></a>

## 4. 実測

<a name="measure-shebang"></a>

### 4.1 shebang の引数（Task 3）

`#!/usr/bin/env -i /Library/Developer/CommandLineTools/usr/bin/python3 -I` のラッパーを直接実行すると、`DEVELOPER_DIR=/nonexistent` を渡しても、通常の拒否（終了コード 2）を返した。macOS は shebang の引数を分けて `env` に渡す（plan の「特に確かめること」の 1）。

環境変数が空でも、CLT の python3 は日本語を UTF-8 で出力した（同じく 2）。

<a name="measure-docker"></a>

### 4.2 Docker のソケット（Task 5、D3）

- **curl:** `curl --unix-socket` は、ユーザー設定の `permissions.deny` にある `Bash(curl *)` で、実行前に拒否された。
- **Python:** 利用者の承認を得て、Python で接続だけを試した（要求は送らない）。結果は `PermissionError: [Errno 1] Operation not permitted` で、sandbox の中からは接続できない。詳細は [research の 5.1](research-sandbox-escape.md#risk-colima) を参照。

<a name="measure-deny-write"></a>

### 4.3 dotfiles への書き込み（Task 1）

worktree で、対象のファイルを書き込みモードで開くだけの確認をした。

- **変更前:** 15 個のファイルに書けた。既存の規則がある `zsh/setup.sh` は拒否された。
- **`.claude/settings.json` を変更した後:** 結果は同じだった。
- **推測:** このセッションの sandbox は、起動時に読んだ設定のまま動いていて、worktree の設定の変更は反映されなかった。
- **扱い:** plan のとおり、マージした後に main checkout で確かめる（[6 章](#not-verified)）。

<a name="codex"></a>

## 5. Codex のレビュー

この PR の 1 回目（2026-11-14）を、`codex review --base main`（読み取り専用）で受けた。

- **結果:** 今回の変更で入った不具合は、見つからなかった。`check-repo.py` は 8 項目 PASS、`git diff --check` も成功した。
- **Codex が確かめていないこと:**
  - 一時ファイルを作る回帰テスト（読み取り専用の環境のため）。このテストは、2 章で実行済み。
  - インストール後のラッパーと sandbox の動作。6 章でマージ後に確かめる。

<a name="not-verified"></a>

## 6. 未確認（マージ後に確かめること）

| 項目 | 確かめ方 | 担当 |
| --- | --- | --- |
| Task 1 の `denyWrite` が効くこと | マージ後、dotfiles で新しいセッションを起動し、4.3 と同じ方法で書けないことを確かめる | Claude |
| Task 1 の `ask` が効くこと | dotfiles で `bin/` などを Edit ツールで変えようとしたときに、確認の画面が出ること | 人間 |
| ラッパーの再インストール後の動作 | `cc-safe-push`・`cc-safe-pr`・`cc-crit` が動くこと | 人間と Claude |
| cc-crit がブラウザを開くこと | 再インストールの後、`/crit-review` でブラウザが自動で開くこと。ラッパーは環境変数を空にして起動するので、`/usr/bin/open` も空の環境変数で動く。sandbox の中では `open` が動かないので確かめられない | 人間 |
| CI の runner に CLT の実体があること | push の後、CI の「Show interpreters」の `ls -l` | Claude |
