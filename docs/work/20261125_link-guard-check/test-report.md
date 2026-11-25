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

レビュー中に main が `e9042b4`（PR #127。`check-repo.py`・`test-check-repo.py` も変えた）に進んだ。`git merge-tree --write-tree e9042b4 HEAD` は衝突なしで、マージ後の tree を一時リポジトリに写して、`check-repo.py` が全項目 PASS、`test-check-repo.py` が通ることを確かめた（修正の前の HEAD `37b842f` で 118 件。修正の後の結果は下の検査の節に書く）。

<a name="checks"></a>

## 検査（完了条件 4）

- `python3 -B .github/scripts/check-repo.py`: 全項目 PASS（Python 3.15.2）
- `python3 -B .github/scripts/test-check-repo.py`: 115 件 OK
- `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`: 指摘なし
- `actionlint`: 指摘なし
- `zizmor --offline .`: 指摘なし（v1.33.1）

<a name="not-verified"></a>

## 確かめていないこと

- CI（ubuntu-latest）での実行。PR の作成後に `gh pr checks` で確かめる。
