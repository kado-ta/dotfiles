---
status: done
created: 2026-11-09
---

# cc-safe-pr 試験記録

設計は [design.md](design.md) を参照する。試験項目の番号は設計 9 章と同じ。

## 試験環境

| 項目 | 値 |
| --- | --- |
| Claude Code | 2.1.311 |
| GitHub CLI | 2.103.3 |
| `/usr/bin/git` | 2.54.0 |
| `/usr/bin/python3` | 3.9.6（LibreSSL 2.8.3） |
| 実施日 | 2026-11-09 |

## 自動テスト

| コマンド | 結果 |
| --- | --- |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-pr.py` | 73 件成功 |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` | 49 件成功 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | 66 件成功 |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | 94 件成功 |
| `bash claude/hooks/tests/test-validate-command.sh` | 13 件成功 |

変異テスト（`cc-safe-pr` に 1 か所ずつバグを入れてテストが検出するかを確認）は 56 件中 55 件を検出した。残りの 1 件は `parse_constant` を外す変異で、全項目の型検証で同じ入力が拒否されるため、実害はない。

`cc-safe-push` はリポジトリの版とインストール済みの版が一致し、変更していない。

## 統合テスト

インストール後、許可リストの実物で、未 push のブランチに `cc-safe-pr create` を実行した。exit 2 で `is not on GitHub; run cc-safe-push first` と拒否され、GitHub への書き込みは発生しなかった。

## 人間の UI 確認

| # | 条件 | 手順 | 結果 | 判定 |
| --- | --- | --- | --- | --- |
| M1 | Sandbox ON + auto | 許可リポジトリで `cc-safe-pr create` | 承認画面なし | 合格 |
| M2 | Sandbox ON + auto | 未許可リポジトリで `cc-safe-pr create` | exit 2、`is not on the allowlist`。監査ログに deny を記録 | 合格 |
| M3 | Sandbox ON + auto | 未許可リポジトリで `gh pr create` | 承認画面あり、拒否 | 合格 |
| M4 | Sandbox ON + auto | `gh pr new`、`gh pr -R`、`gh -R`、絶対パス、`env` 経由の 5 種 | 5 件とも承認画面あり、拒否 | 合格 |
| M5 | Sandbox ON | `cd` と連結して `cc-safe-pr create` | exit 2、監査ログを開けず拒否 | 合格 |
| M6 | Sandbox ON | `excludedCommands` から `gh` を外したあとの `gh pr view`、`gh pr checks` | `view` は成功。`checks` は CI なしの応答で、認証と TLS は成功 | 合格 |
| M7 | Sandbox OFF | `cc-safe-pr create` と `gh pr create` | ラッパーは承認画面なし、`gh pr create` は承認画面あり | 合格 |
| M8 | Sandbox ON + Manual | `cc-safe-pr create` と `gh pr create` | ラッパーは承認画面なし、`gh pr create` は承認画面あり | 合格 |
| M9 | `claude --settings` | 失敗するフックに `onFailure: "block"` を指定して `git status` | フックによりブロック | 合格 |
| M10 | plan | `cc-safe-pr create` | plan モードでは Claude が実行できないため省略 | 未実施 |
| M11 | Sandbox ON | フック適用後に `cc-safe-push` | 承認画面なしで push 成功 | 合格 |

M1 と M3 の auto mode は、実施者から訂正がなかったことによる。M4 は許可リポジトリのセッションで実施した。フックはコマンドの文字列だけで判定するので、リポジトリには依存しない。

作業中、`gh pr create` という文字列を含むスクリプトの実行でフックの承認画面が出た。設計 6 章に記載した既知の誤検知で、確認が増えるだけである。

## 実 GitHub での確認

| # | 手順 | 結果 | 判定 |
| --- | --- | --- | --- |
| E1 | 通常のターミナルで `/etc/ssl/cert.pem` を使い `api.github.com` に接続 | 200 | 合格 |
| E2 | `cc-safe-push` のあとに `cc-safe-pr create` | 承認なしで draft の PR #4 を作成。監査ログに `X-GitHub-Request-Id` を記録 | 合格 |
| E3 | `cc-safe-pr edit`（本文のみ） | 本文だけが変更され、タイトル、draft、head、base は変更なし | 合格 |
| E4 | 依頼ファイルを書き直して同じ create を再実行 | exit 2、既存の URL を表示。PR は 1 件のまま | 合格 |

設計では E2〜E4 を使い捨てのリポジトリで行う予定だったが、実施者の判断で、この作業の PR を使った。

## 未確認事項の結果

| # | 内容 | 結果 |
| --- | --- | --- |
| U1 | TLS 検証 | E1 で確認済み |
| U2 | `excludedCommands` の完全一致 | M5、M6、E2 で確認済み |
| U3 | auto mode の `ask` が承認画面になること | M3、M4 で確認済み |
| U4 | sandbox 外からの Keychain の読み取り | E2 で確認済み |
| U5 | Fine-grained PAT のマージ権限 | 未確認（Phase 2） |
| U6 | plan モードでのラッパーの扱い | 未確認（M10 を省略） |
| U7 | `~/Library/Keychains` の `denyRead` の効果 | 未確認（Phase 2） |
| U8 | もう 1 件の許可リポジトリの `extensions.worktreeConfig` | 未確認（ラッパーは index を読まないので影響はない見込み） |
| U9 | Codex によるレビュー | 2 回実施し、採否を設計書に記録 |

## 残余リスク

重大度が高いものは R1 のみ。`repo` スコープのトークンが sandbox 内から読めるので、Claude が意図的に別の手段で GitHub API を呼ぶことは止められない。対処は設計 12 章の Phase 2 として別タスクで扱う。
