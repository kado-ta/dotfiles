---
status: in-progress
created: 2026-11-11
---

# sandbox からの GitHub トークン遮断 試験記録

計画は [plan.md](plan.md) を参照する。試験項目の番号は計画と同じ。

## 試験環境

| 項目 | 値 |
| --- | --- |
| Claude Code | 2.1.311 |
| GitHub CLI | 2.103.3 |
| 1Password CLI | 2.42.0 |
| 実施日 | 2026-11-11 |

## S0: Keychain の遮断（`claude --settings` による一時設定）

| # | コマンド | 結果 | 判定 |
| --- | --- | --- | --- |
| 1 | `gh auth status` | 失敗。取得元が `(keyring)` ではなく `(default)` になり、空のトークンで 401 | 遮断できている |
| 2 | `security find-generic-password -s gh:github.com` | auto mode の分類器が実行前に拒否 | V2 で確認 |
| 3 | `security find-internet-password -s github.com` | auto mode の分類器が実行前に拒否 | V2 で確認 |
| 4 | `ssh-add -l`（1Password の SSH Agent） | `Operation not permitted` | SSH Agent に届かない |
| 5 | `echo "$CC_P2_OK"` | `1` | `CLAUDE_ENV_FILE` が sandbox 内の Bash に効く |

## S1: 読み取り専用トークン（通常のターミナル、`kado-ta`）

| コマンド | 結果 |
| --- | --- |
| `gh pr view` | 成功 |
| `gh pr checks` | 問い合わせは成功（`no checks reported`）。CI のあるリポジトリがないため、チェック結果の読み取りは未確認 |
| `gh pr diff --name-only` | 成功 |
| `gh run list` | 成功（`no runs found`） |
| `gh issue list` | 成功 |
| 同じタイトルでの `gh api -X PATCH` | 403（`Resource not accessible by personal access token`） |

## 自動テスト

| コマンド | 結果 |
| --- | --- |
| `bash claude/hooks/tests/test-gh-read-token.sh` | 24 件成功 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | 66 件成功 |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | 94 件成功 |
| `bash claude/hooks/tests/test-validate-command.sh` | 13 件成功 |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` | 成功 |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` | 成功 |

`gh-read-token.sh` の変異テストは 13 件中 9 件を検出した。残りの 4 件は、owner の検査で同じ入力が拒否される重複（ホストの照合 2 件）、大文字と小文字を区別しないファイルシステムでは差が出ない小文字化、空のパスへの書き込みが失敗するだけの検査で、実害はない。

## V: 新しい設定での検証（このセッションを再開して実施）

| # | 条件 | 結果 | 判定 |
| --- | --- | --- | --- |
| V1 | Sandbox ON + auto | `gh` は `GH_TOKEN`（93 文字）で認証。`(default)` の Keychain は失敗。`gh pr view` とパイプ付きの `gh pr list` が成功。`GITHUB_TOKEN` は未設定 | 合格 |
| V2 | Sandbox ON + Manual | `security find-generic-password -s gh:github.com` は sandbox 内で exit 44、sandbox 外では exit 0。`find-internet-password -s github.com` は sandbox 外でも exit 44（項目なし） | 合格 |
| V3 | Sandbox ON + auto | 同じタイトルでの `gh api -X PATCH` を人間が承認して実行し、403 | 合格 |
| V4 | 組織のリポジトリで始めたセッション | 未実施（組織トークンの承認後に実施） | 未実施 |
| V5 | トークンのない owner | 単体テストで確認（`GH_TOKEN` が空になり、`GITHUB_TOKEN` なども消える） | 合格 |
| V6 | Sandbox ON | この作業のコミット後の `cc-safe-push` と `cc-safe-pr create` | 下記 |
| V7 | 通常のターミナル | `gh auth status` は `(keyring)` で成功 | 合格 |
