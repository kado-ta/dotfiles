---
status: in-progress
created: 2026-11-25
---

# 試験記録: リンク用スクリプトの worktree の判定を check-repo.py で検査する

## 関連

- [plan.md](plan.md)

<a name="tdd"></a>

## テストを先に書いた確認（完了条件 1）

`test-check-repo.py` に 8 つのテスト（subTest を含む）を足し、検査を足す前に `python3 -B .github/scripts/test-check-repo.py -k link` を実行した。

- 失敗を確かめるテストの 23 件（subTest）が失敗した。理由はどれも、検査がなく終了コードが 0 になったこと（`AssertionError: 0 != 1`）。
- 通ることを確かめるテスト（判定の書き方の違い、hook のテスト、`ln` のないスクリプトなど）は、検査を足す前から通った。対象を広げすぎないことを見るテストなので、足す前に通るのは想定どおり。

検査を足した後は、同じコマンドで 12 件（`-k link` に当たる既存の Markdown のテストを含む）が通り、全体の `python3 -B .github/scripts/test-check-repo.py` も 115 件が通った（変更前は 107 件）。

<a name="method"></a>

## 壊した場合の確認の方法（完了条件 3）

scratchpad に置いた確認のスクリプト（コミットしない）で、次を行った。Claude Code の sandbox の中で実行した。リンク用のスクリプトは動かしていない。

1. HEAD（`4b5e3cc`。10 本のスクリプトはこのブランチで変えていない）の中身を `git archive` で一時ディレクトリに展開し、`git init` とコミットをする（`GIT_CONFIG_GLOBAL=/dev/null`・`GIT_CONFIG_NOSYSTEM=1`）。共有の作業ツリーからは写さない。
2. 写したリポジトリを壊し、作業ツリーの `.github/scripts/check-repo.py` にそのリポジトリのパスを渡して実行し、`link-guard` の節を取り出す。
3. 判定の削除と移動は、判定の `if` の行から最初の `fi` の行までの範囲を `sed` で消したり写したりして行い、消した後に `../.git` が残っていないことを確かめた（検査と同じ正規表現は使っていない）。

<a name="results"></a>

## 結果

| 場合 | 期待 | 結果 |
| --- | --- | --- |
| 写しただけ | `PASS link-guard` | PASS |
| 10 本すべての判定を消す | 10 本のパスがちょうど出る（hook のテストは出ない） | PASS（10 行、すべて `runs ln without the worktree guard`） |
| `config/link.sh` の判定を `mkdir` の行（21 行目）の後ろに移す | 21 行目の失敗が出る | PASS（16 行目と 21 行目が出た） |
| `ghostty/link.sh` を `ghostty/sub/link.sh` に移す（`git mv`） | 深さの失敗が出る | PASS |

- `config/link.sh` の 16 行目は `CONFIG_DIR="$HOME/.config"`。変数の代入も判定より前に置いてよい行に入らないので、一緒に出た（[plan の判定より前に置ける行](plan.md#prelude) のとおり）。
- このブランチの作業ツリーで `python3 -B .github/scripts/check-repo.py` を実行すると、`link-guard` を含む全項目が PASS になった（完了条件 2）。

<a name="review-fixes"></a>

## /review の指摘の修正

/review（specialists 5・Red Team・Claude adversarial）で、誤って PASS になる書き方が見つかった。2026-11-25 にユーザーが修正を選んだもの（[plan](plan.md#guard) に反映）を、テストを先に書いて直した。

- 足したテストの 12 件（subTest）が、修正の前に失敗した。10 件は誤って PASS になって終了コード 0（`\ln`・バッククォート・`LN="ln …"`、入れ子の `if`・`else`・`elif` の中の `exit 1`、`fi # …`・`fi;` の後ろの関数の `exit 1`、macOS の確認の中の `SCRIPT_DIR=` と判定）、2 件は検査全体がファイル名のない 1 件の例外（UTF-8 でない `.sh`、`git add` 前に消した `.sh`）。
- 修正の後は、同じテストが通り、全体の `python3 -B .github/scripts/test-check-repo.py` は 117 件が通った。
- [壊した場合の確認](#method) をやり直し、4 つとも期待どおりだった。`ln` の選び方を広げた後も、10 本すべての判定を消すと出るのは 10 本のパスちょうどだった。`config/link.sh` の判定を `mkdir` の後ろに移した場合は、16 行目と 21 行目だけが出た（最初の修正では、21 行目の 1 行の `if` を深さに数えて「if の中」の失敗も出たので、許さない行は深さに数えないように直した）。

修正分の再レビュー（Testing・Red Team・Claude adversarial）で、前の指摘が塞がったことは確かめられたが、次が見つかった。

- 判定の本体の `[ … ] || {`・`||` の継続行・`case`・関数・`while` の中の `exit 1` がまだ通る。ユーザーが本体の許可リスト（空行・コメント・`echo "…"` の後の `exit 1`）を選んだ。
- 許さない複数行の `if` を深さに数えず、その `fi` だけを数えるので、事実と違う失敗が 2 行出る（上の「許さない行は深さに数えない」の直し方の副作用）。許さない行も先頭の語で深さに数え、1 行で閉じる `if` だけを除くように直した。
- `LN=ln`（行末の `ln`）が漏れ、`'` と `=` にテストがなかった。

テストを先に足し、修正の前に 6 件（subTest）が失敗した（4 件は誤って PASS、1 件は誤った失敗が 2 行余分に出る、1 件は前置きの `fi # macOS` を許していない）。`LN='ln -snfv'` の行は修正の前から失敗になる（`'` を残す意味を固定する行）。修正の後は、全体の 118 件が通り、[壊した場合の確認](#method) も 4 つとも期待どおりだった（判定を消すと出るのは 10 本のパスちょうど）。

<a name="merged-main"></a>

## main との合わせ

レビュー中に main が `e9042b4`（PR #127）、`1dd6739`（PR #128）に進んだ。どちらも `check-repo.py`・`test-check-repo.py` を変えている。

- `git merge-tree --write-tree e9042b4 37b842f`（修正の前）は衝突なし。マージ後の tree を一時リポジトリに写して、`check-repo.py` が全項目 PASS、`test-check-repo.py` が 118 件通った。
- `git merge-tree --write-tree 1dd6739 54cb442`（レビューの修正の後）も衝突なし。マージ後の tree（`00072ea`）で、`check-repo.py` が全項目 PASS、`test-check-repo.py` が 123 件通った。
- `git merge-tree --write-tree 1dd6739 4e3acc1`（Codex の指摘の修正の後）も衝突なし。マージ後の tree（`0003c2a`）で、`check-repo.py` が全項目 PASS、`test-check-repo.py` が 123 件通った。
- PR #128 の後も、`git add` 前に消したファイルは `local-paths` が読んで例外になる（[plan の対象外と残るリスク](plan.md#out-of-scope) の記述のまま）。
- PR を作った後、main に PR #129（`tool-versions` の検査）が入り、GitHub が `CONFLICTING` を返した。`c0de6fe` をこのブランチにマージし（`90cb915`）、`test-check-repo.py` の衝突（リンク用スクリプトの fixture と、#129 の fixture・`override_tool`）は両方を残して解消した。マージ後の作業ツリーで、`check-repo.py` は `tool-versions` を含む 16 項目すべて PASS、`test-check-repo.py` は 133 件 OK、shellcheck・actionlint・`zizmor --offline .` は指摘なしだった。

<a name="codex"></a>

## Codex

通常のターミナルで実行し、結果は `~/.codex/sessions` の記録の最終メッセージ（`last_agent_message`）から読んだ。

### 1 回目: `codex review --base main`（2026-11-25T04:55:36Z、`5d92f93`）

`overall_correctness: patch is incorrect`。読み取り専用の sandbox で動いたので、`secret-content` と `test-check-repo.py` は一時ディレクトリを作れずに確かめられなかったと書いている。

- [P2]（confidence 0.99）`check-repo.py:105`: `LN="ln"` と代入して `"$LN" -s …` と呼ぶ形や、`ln>/dev/null -s …` の形は、`ln` の直後が空白でも行末でもないので対象から外れ、判定がなくても通る。
- [P2]（confidence 0.99）`check-repo.py:111`: `echo` の許可が、エスケープした引用符を区別しない。途中に `\"` を含む正しい `echo` は拒否され、行末の `\"` は閉じ引用符として受理される。後の行で引用符が閉じるスクリプトでは、その間の `exit 1` が文字列の一部でも、終了として数えられる。

### 2 回目: `codex exec`（challenge、2026-11-25T05:08:20Z、`5d92f93`）

プロンプトは `.gstack/tmp/codex-challenge-link-guard.md`（git 管理外。変更前と比べた後退と、壊れる入力を具体的に挙げるよう頼んだ）。`VERDICT: FINDINGS`。コミットから読んだ検査関数にメモリ上の入力を渡して確かめたと書いている（ファイルの編集とリンク用スクリプトの実行はしていない）。

1. Medium: 判定の `fi` にパイプを付ける（`fi 2>&1 | sed 's/^/[aws] /' >&2`）と、`if` 全体が子シェルで動き、`exit 1` は子シェルだけを終える。`aws/link.sh` は `pipefail` がないので、後続のリンクへ進むが、検査は `exit 1` を見た時点で通す。
2. Medium: `"/bin/ln" -snfv …` のように実行ファイルを引用符で囲むと、対象から外れる（1 回目の 1 件目と同じ原因）。
3. Low: 判定の `echo` に `\"` を足すと、判定がないものとして失敗する（1 回目の 2 件目と同じ原因）。
4. Low: `SCRIPT_DIR=` の直前に `unset CDPATH` を足す正しい修正が、前置きの許可リストで失敗する。`SCRIPT_DIR` の計算より前に要るので、判定の後ろへは移せない。
5. Low: `command -v ln >/dev/null` のような存在確認だけのスクリプトも対象になり、判定を求められる。
6. Low: `config/sf/link.sh` に移して判定を `../../.git` に直しても、深さと判定の両方で失敗する（合意した配置の制約による運用の手間と書いている）。
7. Low: 大文字小文字だけが違うリンク先を持つ `.sh` の symlink は、macOS では読めても、Ubuntu の CI では `cannot read (FileNotFoundError)` で失敗する。変更前も `local-paths` が同じ理由で失敗していた、と書いている（実際の runner では確かめていない）。

### 採否と修正

| 指摘 | 判断 | 理由 |
| --- | --- | --- |
| 1 回目の 1 件目、2 回目の 2 | 採用 | 同じ原因（`ln` の直後に空白か行末しか許さない）。`ln` の直後にも `"`・`'`・`` ` ``・`;`・`)`・`<`・`>`・`\|`・`&`・`(` を許した |
| 1 回目の 2 件目、2 回目の 3 | 採用 | `echo` の正規表現を、`\"` を文字列の中として読む形に直した |
| 2 回目の 1 | 採用 | `exit 1` の次の行が、パイプやリダイレクトの付かない `fi` であることを求めた |
| 2 回目の 4（`unset CDPATH`） | 不採用 | 今の 10 本には要らず、失敗は表に出る。要るときに許可リストに足すと plan に書いた |
| 2 回目の 5（`command -v ln`） | 不採用 | 文字列の中の `ln` と同じく、受け入れた誤検知。plan の誤検知の例に足した |
| 2 回目の 6（`../../.git`） | 不採用 | plan の「採らなかった案」に既にある、合意した制約 |
| 2 回目の 7（symlink の大文字小文字） | 不採用 | 今そういうファイルはなく、失敗は表に出る。PR #128 の後は `link-guard` だけが失敗することを plan に書いた |

テストを先に足し、修正の前に 6 件（subTest）が失敗した（5 件は誤って PASS、`\"` を含む正しい `echo` の 1 件は誤って FAIL）。修正の後は、全体の 118 件が通り、`check-repo.py` は全項目 PASS、[壊した場合の確認](#method) も 4 つとも期待どおりだった（判定を消すと出るのは 10 本のパスちょうど）。Codex はこのタスクで 2 回使った（上限は 5 回）。

<a name="checks"></a>

## 検査（完了条件 4）

Codex の指摘の修正の後（`4e3acc1`）に実行した。

- `python3 -B .github/scripts/check-repo.py`: 全項目 PASS（Python 3.15.2）
- `python3 -B .github/scripts/test-check-repo.py`: 118 件 OK（main とのマージ後の tree では 123 件 OK）
- `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`: 指摘なし
- `actionlint`: 指摘なし
- `zizmor --offline .`: 指摘なし（v1.33.1）

<a name="not-verified"></a>

## 確かめていないこと

- CI（ubuntu-latest）での実行。PR の作成後に `gh pr checks` で確かめる。
