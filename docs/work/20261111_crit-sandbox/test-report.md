---
status: in-progress
created: 2026-11-11
---

# Crit の sandbox 対応の検証記録

## 関連

- 設計: [design.md](design.md)

## 環境

- macOS（Darwin 25.6.0）、Claude Code 2.1.311（sandbox 有効、auto mode）
- crit 0.23.2（Homebrew）、Crit プラグイン 1.8.14
- 検証はすべて Claude Code の Bash ツール（sandbox 内）から実行した。hook 経路だけは sandbox の外で動く

<a name="before"></a>

## 1. 変更前の切り分け

| # | 項目 | 結果 | 実行内容 |
| --- | --- | --- | --- |
| 1 | `~/.crit/sessions` への書き込み | 成功（`~/.crit` の許可があるとき） | 空ファイルを作成して削除 |
| 2 | `~/.crit/reviews` への書き込み | 成功（同上） | 同上 |
| 3 | `127.0.0.1:0` での待ち受け | **失敗**: `PermissionError [Errno 1]` | Python の `socket.bind` と `listen` |
| 4 | crit の起動 | **失敗**: `listen tcp 127.0.0.1:0: bind: operation not permitted`（exit 1） | `crit --no-open plan.md` |
| 5 | ブラウザの自動起動 | 未確認（4 で止まるため） | ソースでは非同期で、失敗しても止まらない |
| 6 | 手動でブラウザを開いてのレビュー | 未確認（4 で止まるため） | — |
| 7 | Hook 経由と直接実行の違い | hook 経由は動く（[3 章](#plan-hook)）。直接実行は 4 で止まる | — |

<a name="narrowed"></a>

## 2. `allowWrite` を `reviews` と `plans` に絞った時点

`~/.crit` を `~/.crit/reviews` と `~/.crit/plans` に置き換え、実行中のセッションに反映されたことを確認した。この状態は、後で Codex の指摘を受けて取りやめた（[4 章](#revert)）。

| 操作 | 結果 |
| --- | --- |
| `reviews/`・`plans/` にファイルを作成 | 許可 |
| `sessions/` にファイルを作成 | 拒否 |
| `hooks/`・`prompts/` を作成 | 拒否 |
| `custom.css` を作成、`stats.json` を追記モードで開く | 拒否 |
| `hooks` をシンボリックリンクで作成、`reviews/` 配下から `hooks` へリネーム | 拒否 |
| `~/.crit` 自体をリネーム | 拒否 |
| `~/.crit.config.json` を作成 | 拒否（変更前から） |
| `crit comment plan.md:3 …`（ヘッドレス） | 成功。書き込み先は `reviews/<key>/` だけ |
| `crit --no-open plan.md` | 失敗: `open …/sessions/<key>.lock: operation not permitted`（exit 1）。原因を示して止まる |

ここで確認したのは「保護したい名前の場所にリンクを作れない」ことまで。許可した場所（`plans/`）に置いたリンクを、sandbox の外の plan-hook がたどって書き込む経路は、この検証では確かめていない（[design.md の 3.2](design.md#shared-state)）。

<a name="plan-hook"></a>

## 3. Plan Mode（hook 経由）の端から端までの検証

テスト用の plan で EnterPlanMode → ExitPlanMode を実行し、人間がブラウザで操作した（2 章の設定のとき）。

| 手順 | 結果 |
| --- | --- |
| ExitPlanMode で Crit がブラウザで開く | 成功 |
| 付けたコメントが Finish Review で Claude に返る | 成功（`c_7abf44`） |
| 2 回目に、コメントなしの Finish Review で承認され、Plan Mode を抜ける | 成功。daemon は停止し、`sessions/` とレビューのファイルが片付いた |
| sandbox 内からの返信（`crit comment --plan … --reply-to`） | 承認後に実行したので、返信先がなく失敗した（`comment "c_7abf44" not found`）。承認でレビューのファイルが削除されたため |
| sandbox 内からの plan へのコメント追加と返信 | 成功（`c_60e6d4` / `rp_bc1969`）。`plans/<slug>/.crit/review.json` に書き込まれた |

検証で作った `~/.crit/plans/crit-plan-hook-e2e-plan-2026-11-11/` は削除した。`~/.crit/plan-sessions.json` は sandbox から書き込めないため、人間が端末で削除した。ファイルごと消したので、11/9 のセッションと `claude-code-pr-2026-11-09` の対応付けも消えている。crit はファイルがなければ空の対応表として扱い、次の plan-hook で作り直す【コード】`internal/session/plans.go:246`。

人間が端末で `crit docs/work/20261111_crit-sandbox/test-report.md` を実行し、コメントなしで承認した。承認後、daemon（PID 54436）は停止し、`sessions/` は空だった。

<a name="revert"></a>

## 4. `~/.crit` の書き込み許可を外した後

Codex の challenge の指摘 1〜3（[design.md の 9 章](design.md#codex-review)）を受け、`allowWrite` から `~/.crit/reviews` と `~/.crit/plans` を外した。

| 操作 | 結果 |
| --- | --- |
| `reviews/`・`plans/` にファイルを作成 | 拒否 |
| 既存の `plans/<slug>/current.md` を追記モードで開く | 拒否 |
| `~/.crit` 配下のシンボリックリンク（`find -type l`） | なし |
| `~/.crit` 配下のハードリンク（`find -type f -links +1`） | なし |
| `hooks/`・`prompts/`・`custom.css` | 存在しない |

書き込みを許可していた間（16:30 頃〜18:15 頃）に、リンクやスクリプトが置かれた形跡はなかった。

## 5. リポジトリの検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 8 項目すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 34 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし |
| `actionlint` | 指摘なし |

## 6. 未実施

- `cc-crit`（[design.md](design.md#design)）は未実装。実装レビューの経路の検証は、実装後に行う。
- Lima の VM を経由してホストに書き込めるか（`allowLocalBinding` のリスク評価）は、鍵を確認する操作が拒否されたため確認していない。
