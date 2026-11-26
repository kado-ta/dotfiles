---
status: done
created: 2026-11-26
---

# pm-assist スキルの試験記録

<a name="related"></a>

## 関連

- [plan.md](plan.md)、[research-improvements.md](research-improvements.md)
- 起動テストの依頼文: [assets/trigger-eval.json](assets/trigger-eval.json)

<a name="sources"></a>

## 出典の確認

Claude から読めなかった出典は、ユーザーに確かめてもらった（2026-11-26）。

| 出典 | 確かめ方 | 結果 |
| --- | --- | --- |
| PMI の PMBOK Guide のページ | Claude からは WebFetch・Playwright とも 403。ユーザーがブラウザで開いた | 7 つの領域は Governance・Scope・Schedule・Finance・Stakeholders・Resources・Risk。REFERENCE.md の見出しと一致 |
| Doshi のプレモーテムの記事（Medium） | Claude からは 403。ユーザーがブラウザで PDF に保存し、Claude が macOS の PDFKit で本文を取り出した（PDF は Git 管理外の `tmp/`） | Klein を必読として挙げる。Paper Tiger と Elephant の説明は REFERENCE.md の定義と一致。3 つの定義の表は画像で、本文の文字には入っていない。Tiger の緊急度の 3 区分は本文になかった |

<a name="trigger"></a>

## 起動テスト

<a name="trigger-setup"></a>

### 条件

- ユーザーが通常のターミナルで実行した。Claude Code 2.1.332、モデル `claude-opus-5-5`。
- skill-creator（anthropic-skills。`~/.claude/skills/synced/` にあるもの）の `scripts/run_eval.py`。1 件 3 回、閾値 0.5、タイムアウト 90 秒。
- カレントディレクトリは、`.claude/` だけを置いた `~/pm-assist-eval`。一時コマンドは `~/pm-assist-eval/.claude/commands/` に置かれ、1 回ごとに消された（終わった後に空であることを確かめた）。
- ユーザーのスキル・グローバルの CLAUDE.md・SessionStart のフックが入った状態で動く。
- 一時コマンドの名前は `pm-assist-skill-<乱数>` で、本物のスキルとは名前と種類（コマンド）が違う。

<a name="trigger-smoke"></a>

### 試し（2 件 × 1 回、並行なし）

2/2 合格。起動すべき依頼 1 番は 1/1 で起動し、起動すべきでない依頼 1 番は 0/1 だった。

<a name="trigger-run-1"></a>

### 並行の本番（無効。2 回）

`--num-workers 5` の本番は 2 回動いていた。会話の記録の時刻で、11:34〜11:35 と 11:44〜11:45 に 63 回ずつある。結果のファイルが残ったのは 2 回目（`~/pm-assist-eval/result-1.json`、11:46）だけで、11/21 合格（起動すべき依頼は 0/10 合格で、1/3 が 4 件、0/3 が 6 件。起動すべきでない依頼は 11/11 合格）。1 回目の出力の行方は分からない（worktree の直下に、11:34 に作られた 0 バイトの `result-1.json` があった。推測）。どちらも測定の不具合のため、結果を使わない。`claude -p` は、試しを含めて合計 191 回動いた。

- 原因: 並行して動く 5 つのプロセスが、それぞれの一時コマンドを同じ `.claude/commands/` に置いた。`claude -p` の会話の記録（`~/.claude/projects/` の下）に残った API の依頼を読むと、どちらの 63 回も、スキルの一覧に同じ内容の一時コマンドが ID 違いで 5 つ並んでいた。`run_eval.py` は自分の ID のコマンドが起動されたかで判定するので、ほかのプロセスのコマンドが選ばれた回は「起動しない」と数える。
- 起動すべき依頼の結果は低く出る。起動すべきでない依頼も、ほかのプロセスのコマンドを起動した回を見逃しうるので、合格を信用できない。
- 対処: plan の本番のコマンドを `--num-workers 1` に直した。

<a name="trigger-run-2"></a>

### 有効な本番（`--num-workers 1`）

21/21 合格。起動すべき依頼は 30 回中 30 回起動し、起動すべきでない依頼は 33 回中 0 回だった。会話の記録で、63 回のどれも、一覧の一時コマンドが 1 つだけだったことを確かめた。

| # | 依頼（要約） | 期待 | 起動した回数 | 判定 |
| --- | --- | --- | --- | --- |
| 1 | 新規プロダクトの立ち上げ。何から手をつけるか（`brainstorming` と競合） | 起動する | 3/3 | 合格 |
| 2 | 関係部署を集める初回の打ち合わせの準備 | 起動する | 3/3 | 合格 |
| 3 | 3 週間遅れの移行。範囲を削るか期限を交渉するか | 起動する | 3/3 | 合格 |
| 4 | 基幹システム刷新で起こりうる問題と備え | 起動する | 3/3 | 合格 |
| 5 | 進行中の状況から、進め方と判断事項 | 起動する | 3/3 | 合格 |
| 6 | 前回の整理の見直し（仕様変更と担当の離脱） | 起動する | 3/3 | 合格 |
| 7 | モバイルアプリ刷新のタスクとマイルストーン | 起動する | 3/3 | 合格 |
| 8 | 半年で SaaS を立ち上げる。PM としてまず決めること | 起動する | 3/3 | 合格 |
| 9 | 3 社合同の案件の共有の計画 | 起動する | 3/3 | 合格 |
| 10 | 終わりに向けた残作業と引き継ぎ | 起動する | 3/3 | 合格 |
| 11 | チケットを実装タスクに分解 | 起動しない | 0/3 | 合格 |
| 12 | 今日やることの優先順位 | 起動しない | 0/3 | 合格 |
| 13 | PR の変更のリスク（マイグレーション） | 起動しない | 0/3 | 合格 |
| 14 | API の設計案のリスク | 起動しない | 0/3 | 合格 |
| 15 | テストが通った後に何をすべきか | 起動しない | 0/3 | 合格 |
| 16 | 社内ツールを作る価値があるか（`/office-hours`） | 起動しない | 0/3 | 合格 |
| 17 | 招待機能の要件と設計（`brainstorming`） | 起動しない | 0/3 | 合格 |
| 18 | 設計書から実装の計画（`writing-plans`） | 起動しない | 0/3 | 合格 |
| 19 | 先週のコミットと PR の振り返り（`/retro`） | 起動しない | 0/3 | 合格 |
| 20 | 三点見積もりの式 | 起動しない | 0/3 | 合格 |
| 21 | 「このプロジェクト」のコードベースのセキュリティのリスク | 起動しない | 0/3 | 合格 |

合格の基準（起動すべきでない依頼がすべて 0.5 未満、起動すべき依頼の 8 件以上が 0.5 以上）を満たしたので、description は直さない。明示だけ（C2）への切り替えと、SKILL_ROUTING への 1 行の追加は要らない。

残る限界:

- `run_eval.py` は最初のツール呼び出しだけを見る。起動すべきでない依頼で、ほかのスキルや道具を先に使ってから pm-assist を起動する流れは数えない。起動すべき依頼で、pm-assist の後に `brainstorming` も重ねて起動するかも見ていない。
- 実行した場所は git リポジトリではない空のディレクトリで、どの回も新しい会話の最初の依頼として測った。開発の途中の会話（差分を読んだ後の「この変更のリスクを洗い出して」など）での誤起動は測っていない。
- 一時コマンドは本物のスキルと名前と種類が違う。本物のスキルでの起動は、マージの後に新しいセッションで確かめる（[plan のマージの後](plan.md#after-merge)）。

<a name="link"></a>

## 一時リンク

ユーザーが通常のターミナルで `ln -s ~/dotfiles/.claude/worktrees/pm-assist/claude/skills/pm-assist ~/.claude/skills/pm-assist` を実行した（2026-11-26）。`readlink` で向き先が worktree の `claude/skills/pm-assist` であることを確かめた。このセッションのスキル一覧に、`/reload-skills` なしで pm-assist が出た。リンク経由で `REFERENCE.md`・`TEMPLATES.md` を読めた。

`/review` の指摘（守りの境界が動く）を受けて、ユーザーが 12:58 ごろに `rm ~/.claude/skills/pm-assist` でリンクを外した。外す前に、リンク経由の `SKILL.md` がコミットとハッシュで一致することを確かめた。外した後、`~/.claude/skills/pm-assist` がないことと、worktree のファイルが残っていることを確かめた。照合は、pm-assist の 3 件（`skill removed: pm-assist`、チートシートと棚卸しの `/pm-assist`）と gstack の版の 2 件の違いを返す。pm-assist の 3 件は、マージの後にリンクを張れば消える。

<a name="output"></a>

## 出力の確認

このセッションで pm-assist を起動し（Skill ツール）、plan の 2 件を試した。2 件目は、読み込んだスキルのまま続けて試した。Claude 自身が出力し、Claude 自身が判定したので、独立した確認ではない。出力はチャットに示した。

| 依頼 | 見ること | 結果 |
| --- | --- | --- |
| 3 人で 2 か月の社内ツールの立ち上げ。ゴールは経理部の月次作業の半減 | 軽量型と判定する | 満たす（立ち上げのフェーズ、不確実性は「調べれば分かる」） |
| | WBS・RACI・ステークホルダー登録簿を出さない | 満たす |
| | リスクの節がある | 満たす（上位 3 件と、前提・課題・依存・分かっていないこと） |
| | 質問が 5 件以内 | 満たす（5 件） |
| | 次のアクションが 3〜7 個 | 満たす（4 個） |
| | 判断事項に、元に戻せるかと決める人がある | 満たす。D2 は D1 に依存するので、選択肢を出さず項目だけにした。D3 で「作らない」選択肢を挙げた（目的を問う原則） |
| ベンダー 2 社と 3 部署が関わる刷新が 3 週間遅れている | 立て直しのフェーズと判定する | 満たす（エンプラ型） |
| | 課題・依存がリスクと分かれている | 満たす |
| | 権限の外のリスクにエスカレーションを挙げる | 満たす（期限か範囲の判断を、権限のある人に上げる） |

<a name="docs-sync"></a>

## 文書の照合

sync-skill-docs の手順で、棚卸し・チートシートを直した。規則（SKILL_ROUTING.md）は、起動テストで誤った振り分けがなかったので変えていない。

- worktree の `mise.toml` が信頼されていないため、`mise run claude:skills-check` は止まった。中身の `/usr/bin/python3 -B claude/scripts/skills-check.py check` を直接実行した。
- 直す前: 2 件の違い（`skill added: pm-assist (personal)`、`not in SKILL_INVENTORY.md: pm-assist`）。
- 文書を直した後: 1 件（スナップショットの `skill added` だけ）。
- ユーザーが通常のターミナルで `skills-check.py snapshot` を実行した後: `RESULT: no differences`（終了コード 0）。スナップショットの差分は pm-assist の 8 行だけ。
- チートシートの新しい 2 行は、東アジアの文字幅で数えたセル幅が区切り行と同じことを確かめた。

<a name="repo-checks"></a>

## リポジトリの検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 14 項目すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 110 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了コード 0 |
| `actionlint` | 終了コード 0 |
| `zizmor --offline .` | 指摘なし |
| `/usr/bin/python3 -B claude/scripts/skills-check.py check` | 違いなし |

途中で 1 回、`check-repo.py` の `syntax` が、worktree の直下にあった 0 バイトの `result-1.json` で失敗した。作られた時刻が並行の本番の 1 回目（11:34）と合い、そのときにリダイレクトだけが作ったものと見られる（推測）。ユーザーが消した後は PASS した。

`/review` の途中（12:27 ごろ）で、gstack が 1.103.1.0 から 1.103.3.0 に更新された（この作業では更新していない）。そのため、照合の再実行は gstack の版の 2 件の違い（`gstack version: 1.103.1.0 -> 1.103.3.0` と、棚卸しの版）を返した。pm-assist についての違いはない。gstack の更新は、この PR の外の変更として扱う。

<a name="review"></a>

## /review

gstack の `/review` を実行した（Testing・Maintainability・Simplification の専門家、Red Team、Claude の敵対的レビュー。Codex は `codex_reviews: disabled` のため実行していない）。指摘と対応は次のとおり。どれも Claude のモデルによるレビューで、独立したモデルのレビューではない。

| 指摘 | 出どころ | 対応 |
| --- | --- | --- |
| 一時リンクの先（worktree の `claude/`）は、`~/dotfiles` で起動したセッションからは書き込みを止められていない見込みで、全セッションで自動起動するスキルを書き換えうる（未検証） | Red Team、敵対的レビュー | リンクを外し、マージの直後に `~/dotfiles` に張る（ユーザーの判断）。外す前に、リンク経由の `SKILL.md` がコミットとハッシュで一致することを確かめた。恒久策は別の Issue |
| `SKILL_INVENTORY.md` が未追跡の `test-report.md` にリンクしていて、手元の `check-repo.py` は未追跡のファイルも見るので通るが、CI では失敗する | 敵対的レビュー（main と合わせた tree で実測） | `test-report.md` を push の前にコミットする |
| 起動テストのコマンドの `python3 -m` は、カレントディレクトリを先に探すので、sandbox から書ける場所で実行すると、そこのコードが sandbox の外で動く | 敵対的レビュー | plan のコマンドを `-P` 付きにし、手順ごとに `cd` と変数から始めて、skill-creator がなければ止めるようにした。実際の実行は `~/pm-assist-eval`（`scripts/` はない）から行っていたので、害はなかった |
| 保存の指示が、既存の `plan.md` を上書きしうる。関係者の評価を公開・共有のリポジトリにコミットしうる。2 回目以降に保存した記録を探さない | 親の確認、敵対的レビュー、Red Team | `SKILL.md` の保存と 2 回目以降の節を直した（ユーザーの判断） |
| 見直しの雛形に、現状・共有・前提・分かっていないことがない。判断事項の表に依存の列がない。三点見積もりの式を PERT と区別していない | Maintainability、Red Team、敵対的レビュー | 雛形と `REFERENCE.md` を直した（ユーザーの判断） |
| 調査の文書と plan が、非公開の見込みの参考元の中身（行番号・語句の引用・定義の要約）を詳しく載せている | 敵対的レビュー | 一般的な説明に置き換え、push の前に 3 つのコミットを作り直した（ユーザーの判断。作業ツリーに触れない方法で行い、差し替えたのは調査の文書と plan だけ） |
| plan の依頼文の件数（20 件）、1 回目の本番の合格数（10/21）、記録のない並行実行、棚卸しの「書き込みはしない」の言い方、起動テストの限界の書き漏れ | Testing、Maintainability、Simplification、Red Team、敵対的レビュー | 直した |
| `REFERENCE.md` の「避けること」は `SKILL.md` と重なる（助言） | Simplification | 残す（承認済みの plan で残すと決めていた。ユーザーの判断） |
| 照合が gstack の版の違いを返す | 敵対的レビュー | この PR の外の変更として扱う |

<a name="after-output-check"></a>

### 出力の確認の後に変えたところ

`/review` の対応で、`SKILL.md`（保存と 2 回目以降の節）・`TEMPLATES.md`（見直しの雛形と判断事項の表）・`REFERENCE.md`（三点見積もり）を変えた。description は変えていないので、起動テストの結果はそのまま使える（スナップショットも、description と hooks のハッシュだけなので変わらない）。変えた本文での出力の確認はしていない（リンクを外したため）。マージの後に、新しいセッションで確かめる。
