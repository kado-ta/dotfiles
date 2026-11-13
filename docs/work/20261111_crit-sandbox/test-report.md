---
status: done
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

<a name="cc-crit-e2e"></a>

## 6. cc-crit の端から端までの検証（2026-11-13）

[design.md の 8 章](design.md#verification)の 2〜6 を行った。

準備:

- 環境: macOS 26.7.1（25G241）、Claude Code 2.1.311、crit 0.23.2、git 2.56.1
- 人間が通常のターミナルで、`cc-crit` と `cc-crit.sb` を `/usr/local/libexec/claude-crit/` に root 所有（0755 と 0644）でインストールした
- 人間が、今動いている `~/dotfiles/claude/settings.json` に、このブランチの cc-crit の 7 項目を未コミットで当てた（マージまでの一時的な設定）。Claude Code を再起動しなくても、sandbox の設定の `denyRead` に `~/.cc-crit` が、`allowWrite` に `**/.cc-crit-request.json` が入った
- Claude が実行したものは、すべて Claude Code の Bash ツールから実行した。`cc-crit review` は単独で、バックグラウンドで実行した

<a name="e2e-file"></a>

### 6.1 ファイルのレビュー

対象は `test-report.md`。

| 手順 | 結果 |
| --- | --- |
| `cc-crit review` | 成功。daemon が起動し（`localhost:47800`、session `9087441f6e57`）、ブラウザが自動で開いた（人間が確認） |
| コメントを付けて Finish | 成功。コメント `c_354fd0` が出力で Claude に返った（`approved: false`、exit 0） |
| `cc-crit reply` | 成功（`Added 1 reply`）。`crit comment --session <id> --json --author 'Claude Code'` の組み合わせが動くことを確認した |
| 2 ラウンド目の `cc-crit review` | 成功。同じ daemon につながった（`Connected to crit daemon`） |
| コメントなしで Finish | 成功。`approved: true` |
| 承認後の daemon | 止まった。次のレビューで、同じ 47800 に新しい daemon が起動した。最後の承認の後、人間が `lsof -nP -iTCP:47800-47819 -sTCP:LISTEN` を実行し、何も出なかった |

<a name="e2e-trust"></a>

### 6.2 ブランチの差分のレビューと、信頼の固定（T11）

worktree に `.crit/hooks/on_finish_approved.sh` と `on_finish_unresolved.sh` を一時的に置いた。中身は、実行されたら scratchpad に印のファイルを作るだけ。人間が実行権限を付け、hook を直接実行すると印ができることを確かめてから（陽性対照）、印を消した。

| 手順 | 結果 |
| --- | --- |
| `{}` で `cc-crit review` | 成功。daemon が起動し（session `1084e62c897c`、PID 86764）、ブラウザが自動で開いた |
| コメントを付けて Finish（unresolved） | 成功。信頼のダイアログ（「Trust project prompts?」）は出なかった（人間が確認）。`on_finish_unresolved` の印はできなかった |
| `cc-crit reply` → 2 ラウンド目で接続 → 人間が `kill -9 86764` | クライアントは `could not reach crit daemon on port 47800 … EOF` で止まった（exit 1） |
| `cc-crit review` で開き直す | 成功。同じ session で新しい daemon が起動した（PID 89780）。終了した daemon の session の記録に妨げられなかった（実装レビューの M6）。コメントは残っていた（出力の「1 comment」） |
| コメントを解決し、コメントなしで Finish（approved） | 成功。`approved: true`。`on_finish_approved` の印はできなかった |

試験の後、`.crit/` は削除した。

印ができなかったのは、信頼の固定（`defaults`）と、profile（`/bin/sh` の実行と scratchpad への書き込みを拒否する）の両方による。この試験では、どちらが止めたかを分けられない。信頼の固定が効いたことの直接の証拠は、ダイアログが出ずに Finish できたこと。信頼されていないリポジトリでは、選ぶまで Finish が 403 になる【コード】`internal/server/server.go:2572`。

<a name="e2e-failures"></a>

### 6.3 異常系

| 操作 | 結果 |
| --- | --- |
| 依頼ファイルなしで `cc-crit review` | 拒否（exit 2）: `no readable .cc-crit-request.json in the current directory` |
| `{"files": ["/etc/hosts"]}` | 拒否（exit 2）: `files must be inside the repository` |
| 壊れた JSON | 拒否（exit 2）: `request is not valid JSON` |
| 連結して実行（`cd . && …/cc-crit review`） | 拒否（exit 2）: `cannot read …/.cc-crit/crit-home/.crit.config.json; it must be a regular file you own`。sandbox の中で動き、`denyRead` のため専用 HOME の設定を読めずに止まった。想定していた `FAILED`（exit 1、`run cc-crit alone`）とは理由が違うが、安全側に倒れている。今動いている `validate-command.sh` は main の版なので、連結は hook で止まらなかった。マージ後は hook が先に止める |
| 人間が `127.0.0.1:47800` で `python3 -m http.server` を起動し、`cc-crit review` | 拒否（exit 2）: `port 47800 is in use by something other than cc-crit's crit; stop it and retry` |
| Claude の Bash で `ls ~/.cc-crit` | 権限ルールで拒否された。sandbox の中の cc-crit も専用 HOME を読めなかった（連結の試験） |

拒否のたびに、依頼ファイルは消えていた。

<a name="e2e-profile"></a>

### 6.4 profile のテスト

人間が sandbox の外で `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py` を実行した。22 件すべて OK。前に出ていた ResourceWarning は出なかった。

<a name="not-done"></a>

## 7. 未実施・未確認

- sandbox の中からは、crit の daemon の生死を確かめられない（`pgrep` は `sysmond service not found`、`lsof` は何も返さない）。daemon が止まったことは、人間の `lsof` と、同じポートで次の daemon が起動したことで確かめた。
- crit の信頼のキーは `filepath.Abs`、`cc-crit` は `os.path.realpath` でパスを計算する【コード】`internal/prompt/trust.go:30-37`。`cc-crit` は crit を toplevel の実際のパスで起動し、`PWD` を渡さないので、キーは一致すると推測している。シンボリックリンクを含むパスのリポジトリでは試していない。一致しない場合は信頼のダイアログが出て Finish できなくなる（hook は動かないので、安全側）。
- Lima の VM を経由してホストに書き込めるか（`allowLocalBinding` のリスク評価）は、確認していない。鍵を sandbox から読めるかを調べる操作（内容は出力しない）が、Claude Code の自動判定で認証情報の探索として拒否されたため。
  - 確認の方法: 次の 3 つがすべて成り立つと、`allowLocalBinding` を有効にしたときに、sandbox 内のコマンドが VM に SSH で入り、マウントを通して sandbox の外に書き込める。
    1. Lima の SSH の秘密鍵（Lima の既定では `~/.lima/_config/user`）を sandbox から読める。名前が `id_*` ではないので、今の denyRead のパターンには当たらない【推測】。人間の承認を得て、Claude の Bash で `test -r ~/.lima/_config/user && echo readable || echo unreadable` を実行する（内容は出力しない）。
    2. VM の SSH が localhost で待ち受けている。`limactl list` の SSH の列で確かめる（localhost で Lima が待ち受けていることは実測済み。[design.md の 3.3](design.md#root-cause)）。
    3. VM が、ホストのディレクトリを書き込み可能でマウントしている。`~/.lima/<インスタンス>/lima.yaml` の `mounts` の `writable` で確かめる。
  - 確認できないことの影響: 判断は変わらない。`allowLocalBinding` を採らない理由は、全インターフェースでの待ち受けと、localhost の全ポート（DB、Redis、VS Code など）への接続で、どちらも確認済み。この経路は、理由を 1 つ増やすだけ。採用した cc-crit の profile が接続を許すのは localhost の 47800〜47819 だけで、crit と git 以外は実行できないので、Lima の SSH には届かない。
  - 残るリスク:
    - 将来 `allowLocalBinding` を有効にすると、この経路が開くおそれがある。CLAUDE.md の cc-crit の節に、使わないことと理由を書いて防いでいる。
    - 1 が成り立つなら、`allowLocalBinding` と関係なく、鍵を sandbox から読めて、許可されたドメインに送り出せる。sandbox から localhost への接続は止まっていて（sandbox 内の `crit comment --session` が daemon に接続できずに失敗した【実測】）、Lima の SSH は localhost でだけ待ち受ける【推測】ので、鍵だけでは VM に入れず、影響は小さい。別の作業で 1 を確かめ、読めるなら denyRead に `~/.lima/_config` を足すことを提案する。
