---
status: done
created: 2026-11-25
---

# リンク用スクリプトの worktree の判定を check-repo.py で検査する

## 目次

- [関連](#related)
- [問題](#problem)
- [完了条件](#done-criteria)
- [方針](#approach)
  - [対象の選び方](#targets)
  - [判定の見つけ方](#guard)
  - [判定より前に置ける行](#prelude)
  - [置き場所の深さ](#depth)
  - [名前とメッセージ](#messages)
  - [CLAUDE.md に書くか](#claude-md)
- [テスト](#tests)
- [決めてほしいこと](#questions)
- [採らなかった案](#rejected)
- [変更するファイル](#files)
- [手順](#steps)
- [対象外と残るリスク](#out-of-scope)

<a name="related"></a>

## 関連

- [リンク用スクリプトを worktree の中では止める](../20261125_link-scripts-worktree-guard/plan.md)（PR #124、da165c1）。その [対象外と残るリスク](../20261125_link-scripts-worktree-guard/plan.md#out-of-scope) に、判定が抜けないようにする検査はマージ後に対応すると書いた（2026-11-25 のレビューで決定）。
- 判定を動かして確かめる方法: [前の作業の test-report.md](../20261125_link-scripts-worktree-guard/test-report.md#method)

<a name="problem"></a>

## 問題

PR #124 で、リンク用の 10 本のスクリプトに「ルートの `.git` がファイルなら終了コード 1 で止める」判定を足した。CI はこれらのスクリプトを動かさないので、次の変更に気づけない。

1. リンク用のスクリプトを新しく足し、判定を書き忘れる。
2. 判定より前に、書き込む処理を足す。判定で止まる前に、リンクやディレクトリができる。
3. スクリプトをルートの 2 つ以上下か、ルートに移す。判定は `$SCRIPT_DIR/../.git` を見るので、worktree の中でも偽になり、黙って止まらなくなる。
4. `SCRIPT_DIR=` の定義を消すか、判定より後ろに移す。`$SCRIPT_DIR` が空だと、判定は `/../.git`（`/.git`）を見て偽になる。`set -u` のない 8 本（`claude/setup.sh`・`obsidian/setup.sh` 以外）は、エラーにもならずに先へ進む。

<a name="done-criteria"></a>

## 完了条件

1. `test-check-repo.py` に足したテストのうち失敗を確かめるものが、検査を足す前は失敗し、足した後は通る。既存のテストもすべて通る。
2. このブランチで `python3 -B .github/scripts/check-repo.py` を実行すると、`link-guard` を含む全項目が PASS になる。
3. `git archive` で一時ディレクトリに写したリポジトリ（`git init` して追加する）で、次を確かめる。
   - 10 本すべての判定を消すと、`link-guard` が FAIL になり、10 本のパスがちょうど出る（hook のテストは出ない）。
   - `config/link.sh` の判定を `mkdir` の後ろに移すと、その `mkdir` の行番号を含む失敗が出る。
   - `ghostty/link.sh` を `ghostty/sub/link.sh` に移すと、深さの失敗が出る。
4. CLAUDE.md の規約の節の検査（`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・`zizmor --offline .`）が通る。

3 の確認のスクリプトは scratchpad に置き、コミットしない。結果は `test-report.md` に書く。リンク用のスクリプトは動かさない（書き方を読むだけの検査なので、動かす確認は要らない）。

<a name="approach"></a>

## 方針

`check-repo.py` に検査 `link-guard`（関数 `check_link_guard(root)`）を足す。スクリプトを動かさず、書き方を読んで確かめる。

<a name="targets"></a>

### 対象の選び方

- 対象は、`repo_files`（追跡中と、無視されていない未追跡のファイル。ほかの検査と同じ）のうち、`*.sh` で、コメント以外の行で `ln` をコマンドとして呼ぶもの。`claude/hooks/tests/` の下は除く（一時ディレクトリの中にリンクを作るテスト）。
- コメントは、空白の後に `#` で始まる行とする。行の途中の `#` からのコメントは見ない。
- `ln` をコマンドとして呼ぶ行: 行頭か、空白・`;`・`&`・`|`・`(`・`` ` ``・`"`・`'`・`=`・`\` の直後にある `ln` の後に、空白・`;`・`&`・`|`・`(`・`)`・`<`・`>`・`` ` ``・`"`・`'` か行末が続く。`/bin/ln` のようにパスが付いてもよい。オプションは問わない（ハードリンクも含む）。前後の文字は /review と Codex の指摘で広げた（`\ln -s`、`` `ln -s …` ``、`LN="ln -snfv"`、`LN=ln`、`LN="ln"` と `"$LN" -s`、`"/bin/ln"`、`ln>/dev/null` の形が漏れていた）。
- `SCRIPT_DIR=` があることは、選ぶ条件にしない。判定は `$SCRIPT_DIR` を使うので、定義がないことは失敗にしたい（[判定より前に置ける行](#prelude)）。条件にすると、その場合に対象から外れて黙って通る。
- `*.command` は対象にしない。`setup.command`・`init.command` は `cd ~/dotfiles` してから動くので、worktree を指すリンクを作らない（前の作業の plan の「問題」の節）。

scratchpad の試作で、今のリポジトリでは 10 本がちょうど対象になり、hook のテスト 7 本が除外に当たることを確かめた。次のものは当たらない。

- `biome/sync_schema.sh`（`SCRIPT_DIR=` はあるが `ln` がない）
- `claude/hooks/tests/test-guard-playwright-mcp.sh`（`SCRIPT_DIR=` はあるが `ln` がない）
- `claude/hooks/ask-shared-tree-git.sh`（正規表現の中の `-ln-`）
- `aws/link.sh`・`bin/link.sh`・`claude/setup.sh`・`config/link.sh`・`vscode/setup.sh` のコメントの中の `ln`

漏れと誤検知:

- 漏れ: `ln` 以外でリンクを作るスクリプト（`cp -s`、Python の `os.symlink` など）、拡張子が `.sh` でないスクリプト、`ln` を別のファイルに移して `source` するスクリプト、`ln` の名前を文字の連結や変数の展開で組み立てるスクリプト。
- 誤検知: 一時ディレクトリの中にだけリンクを作るほかのスクリプトや、文字列（`echo "… ln -s …"` やヒアドキュメント）の中に `ln` を書いたスクリプト、`command -v ln` のように存在を確かめるだけのスクリプト。除外の一覧（定数）に足して対応する。

<a name="guard"></a>

### 判定の見つけ方

- 行頭（インデントなし）の `if [ -f "$SCRIPT_DIR/../.git" ]; then` を判定の始まりとする。`${SCRIPT_DIR}` の形も認める（今の 10 本はこの 2 通り）。行末の空白は問わない。
- その次の行から、空行・コメント・`echo "…"`（後ろに `>&2` だけは可）だけを挟んで、`exit 1` だけの行があること（本体の許可リスト）。`echo` の引用符の中の `\"` は文字列を閉じないものとして読む。メッセージの文面は見ない（誤操作を防ぐのに要るのは止まることだけ）。
- `exit 1` の次の行（空行とコメントは飛ばす）が、パイプやリダイレクトの付かない `fi`（後ろのコメントは可）であること。`fi 2>&1 | sed …` のようにパイプが付くと、`if` 全体が子シェルで動き、`exit 1` は子シェルだけを終える。
  - この 2 つは Codex の指摘で足した。最初の `echo` の正規表現は、`\"` を含む正しい `echo` を拒否し、行末の `\"`（文字列が次の行へ続く）を受け入れて、その中の `exit 1` を数えていた。
  - /review の指摘で 2 回変えた。最初は「最初の `fi` だけの行まで」としていたので、入れ子の `if`・`else`・`elif` の中の `exit 1` を数え、`fi # …` や `fi;` では判定の終わりを見失って、後ろの関数の中の `exit 1` を拾っていた。次に「次の `if`・`elif`・`else`・`fi` まで」にしたが、`[ -n "${ALLOW_WORKTREE:-}" ] || {` の中、`||` の継続行、`case`・関数・`while` の中の `exit 1` が通った。区切りの語を並べる方式では終わりがないので、前置きと同じく置ける行を決めた（2026-11-25 にユーザーが選んだ）。
  - 本体に `echo` 以外の行（`printf`、入れ子の `if` など）を置くと、止まる形でも失敗になる。失敗は表に出るので、書き方を合わせるか許可を足す。
- ほかの書き方（`[[ … ]]`、`test -f`、`-e`、`../../.git`、インデントした `if`）は、判定がないものとして失敗にする。インデントを認めないのは、ほかのブロックの中に入った判定（実行されないことがある）を通さないため。

<a name="prelude"></a>

### 判定より前に置ける行

引き継ぎでは「最初の書き込み（`ln`・`mkdir`・`touch`・`cp`・`rm`・`>` など）より前に判定がある」と定義する案だったが、書き込むコマンドは並べきれない。`mise install`・`codex plugin add`・`curl … | bash` のようなツールの呼び出しも書き込み、前の作業の確認では、変更前の `claude/setup.sh` がリンクの後に動かした `/usr/bin/python3` が、偽の HOME の `~/Library/Caches` に 49 件を書いた。そこで逆に、**判定より前に置いてよい行を決め、それ以外があれば失敗にする**（許可リスト）。

判定より前に置いてよい行:

- 空行とコメント（shebang を含む）
- `set` とオプションだけの行（`set -euo pipefail`・`set -o pipefail`）
- `SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)`
- 前置きの確認の部品: `if [ … ]; then`（`] ; then` も可。条件に `;`・`&`・`|`・`<`・`>`・バッククォートを含まないもの）、`echo "…"`（後ろに `>&2` だけは可）、`exit <数字>`、`fi`

あわせて、前置きの `if` と `fi` の行を数え、次を確かめる。

- 判定の行で、前置きの `if` がすべて閉じていること（macOS の確認の `fi` の上に判定を差し込んだ形を止める）。
- `SCRIPT_DIR=` の行が、判定より前の、どの `if` の中でもない場所に 1 回以上あること。

深さの確認は /review の指摘で足した。最初は `SCRIPT_DIR=` があることだけを見ていたので、macOS の確認の中に入れた形も通っていた。深さは、許さない行も含めて、先頭の語が `if` の行で 1 つ増やし、`fi` で始まる行で 1 つ減らす。1 行で閉じる `if`（`if [ … ]; then mkdir …; fi`）は数えない。許さない複数行の `if`（`if ! command -v …; then` など）は、その行の失敗だけを出し、深さはずれない（最初の修正では許さない行を数えず、対応する `fi` だけを数えて、事実と違う失敗を 2 行出していた）。前置きの `fi` の後ろのコメントは許す。

今の 10 本の判定より前（shebang、`set`、macOS の確認、`claude/setup.sh` の `CLAUDECODE` の確認、コメント、`SCRIPT_DIR=`）は、すべてこれに収まることを試作で確かめた。書き込まない前置き（`command -v jq >/dev/null || exit 1` など）を足すときは、判定の後ろに置く（検査が失敗するので気づける）。`SCRIPT_DIR` の計算より前に要るもの（`cd` に効く `CDPATH` を消す `unset CDPATH` など）は後ろに移せないので、要るときに許可リストに足す（Codex の指摘。今の 10 本には要らない）。

<a name="depth"></a>

### 置き場所の深さ

- 対象がルートの 1 つ下（`<dir>/<name>.sh`）にないときは、失敗にする。選ぶ条件にはしない。条件にすると、深い場所に移したスクリプトが対象から外れて黙って通り、[問題](#problem) の 3 を見逃す。
- 深さの失敗と判定の失敗は、両方とも出す（どちらも直す必要がある）。

<a name="messages"></a>

### 名前とメッセージ

- 名前は `link-guard`。`CHECKS` の `rerere` の後に置く。
- メッセージはほかの検査に合わせて英語にする。パスはリポジトリからの相対パスだけを出す（CI のログは公開される）。

| 場合 | メッセージ |
| --- | --- |
| 深さ | `<rel>: runs ln but is not directly under a top-level directory (the worktree guard checks $SCRIPT_DIR/../.git)` |
| 判定がない | `<rel>: runs ln without the worktree guard (if [ -f "$SCRIPT_DIR/../.git" ]; then followed by only echo "..." lines and exit 1)` |
| `SCRIPT_DIR=` が前にない | `<rel>: SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd) must come before the worktree guard, outside any if block` |
| 判定の前に許さない行 | `<rel>:<lineno>: only blank lines, comments, set, SCRIPT_DIR=... and if/echo/exit/fi checks may come before the worktree guard` |
| 判定が前置きの if の中 | `<rel>: the worktree guard must not be inside another if block` |
| 読めない | `<rel>: cannot read (<例外の型>), so the worktree guard is not checked` |

読めない（UTF-8 でない、`git add` 前に消した）ファイルは、ファイルごとの失敗にして、ほかのスクリプトを調べ続ける。例外の本文（絶対パスを含む）は出さない。/review の指摘で足した（最初は検査全体が、ファイル名のない 1 件の例外になっていた）。

定数（除外の一覧、正規表現）には、ほかの検査と同じく理由のコメントを付ける。

<a name="claude-md"></a>

### CLAUDE.md に書くか

推奨は **書かない**。

- `INSTRUCTION_PLACEMENT.md` は、必ず守らせたいことを文章ではなく仕組みで強制し、CLAUDE.md には毎回必要な事実だけを置くとしている。この検査は CI と push 前の `check-repo.py` で強制され、失敗のメッセージが直し方を示す。
- 「sandbox と権限の禁止事項」の節は、外すと sandbox や権限が緩む設定の一覧になっている。この判定は誤操作を防ぐためのもので、節の性質と合わない。
- リンク用のスクリプトを足すことはまれで、毎回のセッションで読み込む行数に見合わない。

代わりの案: 規約の節に「リンク用のスクリプトはルートの 1 つ下に置き、`SCRIPT_DIR=` の直後に worktree の判定を置く（`check-repo.py` の `link-guard`）」を 1 行足す。新しいスクリプトを書く前に Claude が知れるが、上の理由で採らない。[決めてほしいこと](#questions) の 1 で確かめる。

<a name="tests"></a>

## テスト

`test-check-repo.py` の `setUp` に、判定のあるリンク用のスクリプト（`aws/link.sh` の形）を 1 本足す。ほかの検査と同じく、既存の `test_clean_fixture_passes` が通る場合を確かめる。足すテスト:

| 種類 | 場合 |
| --- | --- |
| 通る | `$SCRIPT_DIR` と `${SCRIPT_DIR}` の 2 通り。前置き（`set -euo pipefail`、macOS の確認、`CLAUDECODE` の確認、コメント）がある形も（subTest） |
| 通る | `claude/hooks/tests/` の下で `ln -s` を使い、判定がないスクリプト（対象外） |
| 通る | `SCRIPT_DIR=` はあるが `ln` がないスクリプトと、コメントにだけ `ln` があるスクリプト（対象外） |
| 失敗 | `ln -s` を使い、判定がない |
| 失敗 | `/bin/ln -s`・`command ln -s` の形で、判定がない（対象に入ること） |
| 失敗 | 判定の前に許さない行がある: `mkdir -p "$HOME/x"`、`touch`、`cat <<'EOF' >"$SCRIPT_DIR/config"`、`mise install`（subTest。行番号が出ること） |
| 失敗 | `SCRIPT_DIR=` が判定より後ろにあるか、ない |
| 失敗 | 判定に見えるが数えない形: `$SCRIPT_DIR/.git`、`$SCRIPT_DIR/../../.git`、`-d`、`exit 1` の代わりに `exit 0`、`exit` がない、インデントした `if`（subTest） |
| 失敗 | 判定はあるが深さが違う: `config/sf/link.sh`（2 つ下）、`link.sh`（ルート）、`claude/hooks/x.sh`（`tests/` の外の 2 つ下） |

/review の指摘で足したテスト:

| 種類 | 場合 |
| --- | --- |
| 通る | 判定の `fi` と前置きの `fi` の後ろにコメントがある |
| 失敗 | `\ln -s`、`` `ln -s …` ``、`LN="ln -snfv"`、`LN='ln -snfv'`、`LN=ln` の形で、判定がない |
| 失敗 | `exit 1` が入れ子の `if`・`else`・`elif`・`[ … ] \|\| {`・`\|\|` の継続行・`case` の中にある。`exit 1` のない判定の `fi` の後ろにコメントか `;` があり、後ろの関数に `exit 1` がある |
| 失敗 | インデントした `SCRIPT_DIR=` が macOS の確認の中にある。`SCRIPT_DIR=` と判定が macOS の確認の `fi` の上にある |
| 失敗 | 許さない複数行の `if` が前置きにある（その行の失敗だけが出ること） |
| 失敗 | UTF-8 でない `.sh`、`git add` 前に消した `.sh` がある（ほかのスクリプトの失敗も出ること、絶対パスを出さないこと） |

Codex の指摘で足したテスト:

| 種類 | 場合 |
| --- | --- |
| 通る | 判定の `echo` に `\"` を含む |
| 失敗 | `LN="ln"` と `"$LN" -s`、`ln>/dev/null -s`、`"/bin/ln" -snfv` の形で、判定がない |
| 失敗 | 判定の `echo` が行末の `\"` で次の行へ続き、`exit 1` が文字列の中にある。判定の `fi` にパイプが付く |

<a name="questions"></a>

## 決めてほしいこと

2026-11-25 に Crit で承認され（コメントなし）、3 つとも推奨どおりに決まった。

1. **CLAUDE.md に 1 行足すか**: 足さない（[CLAUDE.md に書くか](#claude-md)）。
2. **前の作業文書の `status` を `done` にするか**: `docs/work/` の plan で `in-progress` のまま残っているのは、前の作業の plan だけ（ほかの 28 件は `done`。test-report も `in-progress`）。PR #124 はマージ済みで、残っていた検査もこの作業で片付く。この PR で、2 つのファイルの `status` だけを `done` にする別のコミットを作る（本文は変えない）。
3. **実装に進むか**: 進む。

<a name="rejected"></a>

## 採らなかった案

- **明示の一覧（10 本）だけを検査する**: 新しいスクリプトを足したとき（いちばん起こりやすい漏れ）に気づけない。
- **`ln` で選んだものに、明示の一覧を足す**（一覧のスクリプトは `ln` がなくても対象にする）: `ln` を別のファイルに移すと選び方から外れる漏れを塞げるが、各ディレクトリは独立していて共通のファイルを `source` しない構成なので、起こりにくい。改名・削除のたびに一覧も直すことになる。
- **`SCRIPT_DIR=` と `ln -s` の両方を含むものを選ぶ**: `SCRIPT_DIR` 以外の名前でリポジトリの場所を求める新しいスクリプトが漏れる。`SCRIPT_DIR=` を消したときも対象から外れる。
- **名前（`*/link.sh`・`*/setup.sh`）で選ぶ**: ほかの名前のスクリプトが漏れ、リンクを作らない `zsh/setup.sh` に判定を求めることになる。
- **書き込むコマンドを並べ、その最初より前に判定があることを確かめる**: ツールの呼び出しなど、並べていない書き込みを見逃す（[判定より前に置ける行](#prelude)）。
- **深さに合わせた `../` の数の判定を認める**: 今は深い場所のリンク用スクリプトがない。要るときに、判定と検査を一緒に変える。
- **判定の 5 行を文字どおり比べる**: インデント（タブと空白）と `${SCRIPT_DIR}` の書き方が分かれているので、10 本を揃える変更が要る。止まることに関係しない違いで失敗させない。
- **スクリプトを動かして確かめる（CI で一時リポジトリの worktree から実行する）**: 確かな方法だが、CI でリンク用のスクリプトを動かすことになり（ツールのインストールに進むものもある）、検査が重くなる。書き方の検査で、誤操作を防ぐには足りる。

<a name="files"></a>

## 変更するファイル

- `.github/scripts/check-repo.py`: 定数と `check_link_guard` を足し、`CHECKS` に登録する。
- `.github/scripts/test-check-repo.py`: `setUp` のスクリプトと、[テスト](#tests) のテストを足す。
- `docs/work/20261125_link-guard-check/`: この plan と `test-report.md`。
- （[決めてほしいこと](#questions) の 2 で決まれば）`docs/work/20261125_link-scripts-worktree-guard/plan.md`・`test-report.md` の `status`。
- （1 で決まれば）`CLAUDE.md`。`CLAUDE.md` は Edit ツールで書くと承認を求められる。

10 本のスクリプトは変えない。

<a name="steps"></a>

## 手順

規模は通常（仕様は決まっていて、既存の検査の形に沿う）、高リスクには当たらない。

1. `test-check-repo.py` にテストを足す → 失敗を確かめるテストが失敗し、通ることを確かめるテストが通ることを確かめる（完了条件 1 の前半）。
2. `check-repo.py` に検査を足す → `test-check-repo.py` がすべて通り（完了条件 1）、このブランチで `check-repo.py` が全項目 PASS になる（完了条件 2）。
3. scratchpad の確認のスクリプトで、一時リポジトリに写して壊した場合を確かめる（完了条件 3）→ `test-report.md` に記録する。
4. shellcheck・actionlint・`zizmor --offline .` を実行する（完了条件 4）。
5. `/review` → 指摘を直す → `/crit-review` でブランチの差分を開く → 承認後に push と PR → `gh pr checks` で CI を確かめる。

ロールバックは、この PR の revert で足りる（検査を足すだけで、スクリプトの動きは変えない）。

<a name="out-of-scope"></a>

## 対象外と残るリスク

- 検査は書き方を見るだけで、守りではない（判定そのものと同じく、誤操作を防ぐためのもの）。わざと崩した書き方（条件や `echo` の中の `$( … )` で書き込む、判定を実行されない分岐に入れる、`SCRIPT_DIR` を判定の後で別の値にする）は通る。PR のレビューで見る。
- 検査は、そのブランチの中身にしか効かない。検査を含まない古いブランチ（2026-11-25 時点の `.claude/worktrees/add-gitleaks` の `feat/gitleaks-check` など）では動かず、その worktree のスクリプトには判定もない。古いブランチの worktree のスクリプトは、main を取り込むまで実行しない（前の作業と同じ）。
- 変更前からある問題（直さない）: bash で `source aws/link.sh` とすると、`$0` が bash になって `SCRIPT_DIR` がカレントディレクトリになり、判定を通る。そのとき、リポジトリのルートに ignore されない `config`・`credentials` を作る。PR #124 より前からある。
- /review で見つかり、2026-11-25 に見送ったもの:
  - 判定を後ろに移すと、判定より前の許さない行がすべて 1 行ずつ失敗として出る（`claude/setup.sh` では 69 行）。ログが読みにくいだけで、誤って通ることはない。
  - herdr が生成する `claude/hooks/herdr-agent-state.sh`（手で編集しない）に将来 `ln` が入ると、文字列の中でも対象になって失敗する。そのときに `LINK_GUARD_EXEMPT` に足す。
  - 深さの `2` を名前付きの定数にする案（advisory）。使うのは 1 か所だけ。
- 文字列の中の `ln`（`echo "ln -s is not allowed" >&2`、`grep -q 'ln -s'` など）でも対象になり、判定がなければ失敗する。漏れて黙って通るより、誤って失敗して除外に足すほうを選んだ（[対象の選び方](#targets)）。今のリポジトリでは当たらない。
- `git add` 前に消したファイルは、`link-guard` はファイルごとの失敗にするが、既存の `local-paths` は検査全体が例外（絶対パスを含む）になる。変更前からの動きで、この作業では変えない。
- `link-guard` は、追跡中の `.sh` の symlink のリンク先を読む。大文字小文字だけが違うリンク先の symlink は、macOS では読めても、Ubuntu の CI では `cannot read (FileNotFoundError)` で失敗する（Codex の指摘）。main に入った PR #128 で `local-paths` は symlink をたどらなくなったので、マージ後はこの失敗は `link-guard` だけから出る。今そういうファイルはなく、失敗は相対パスと型名で表に出るので、変えない。
- 作業中に見つけた食い違い（直さない）: `README.md` の表の `.github/` の行は「`init.command` を macOS ランナーで実行する CI（GitHub 上で無効化している）」としているが、今の CI（`.github/workflows/ci.yaml`）はリポジトリの検査とフックの回帰テストを PR と main への push で実行している。
