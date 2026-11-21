---
status: in-progress
created: 2026-11-21
---

# protect-main-branch で、一覧と表示だけの git branch をブランチの切り替えとみなさない

<a name="goal"></a>
## 目的

`protect-main-branch.sh` は、同じ Bash 呼び出しの中で `git commit` より前に `git branch` があると、引数によらずブロックする。`git branch --show-current` のように一覧や表示だけの呼び出しは、ブロックしないようにする。HEAD のブランチを変えうる呼び出しは、今までどおりブロックする。

<a name="related"></a>
## 関連

- 導入したコミット: `d6577fe`（2026-11-09、fix(claude): detect aliased commits and branch switches in protect-main-branch）
- 起きた場面: PR #51 の作業（2026-11-21）

<a name="facts"></a>
## 事実

- `claude/hooks/protect-main-branch.sh` の 198 行目は、サブコマンドが `checkout`・`switch`・`branch`・`symbolic-ref`・`rebase` のどれかなら、引数を見ずに `BRANCH_CHANGE=1` にする。213 行目は、エイリアスが行き着いた組み込みコマンドについて同じことをする。
- `d6577fe` のコミットメッセージには、`branch` を入れた理由は書かれていない（推測: 現在のブランチを改名する `-m` のため）。
- 2026-11-21 に、`git branch --show-current && git add ... && git commit ...` がブロックされた。`git rev-parse --abbrev-ref HEAD` に書き換えて通した。
- git 2.56.1 の一時リポジトリで、`feature/x` にいるときに試した結果:

| 呼び出し | 実行後の HEAD |
| --- | --- |
| `git branch -c copy1`、`git branch -C copy2` | `refs/heads/feature/x`（変わらない） |
| `git branch newb` | `refs/heads/feature/x`（変わらない） |
| `git branch -m main` | `refs/heads/main`（変わる） |
| `git branch -m main feature/y`（現在のブランチを改名） | `refs/heads/feature/y`（変わる） |
| `git branch --show-current`、`-vv`、`-a`、`--list` | 変わらない |

<a name="changes"></a>
## 変更

1. `claude/hooks/protect-main-branch.sh`: サブコマンドが `branch` のときは、区切り（`&&`・`||`・`;`・`|`）までの引数を見る。引数がないか、すべてが次の一覧に入っていれば、ブランチの切り替えとみなさない。それ以外（`-m`・`-c`、ブランチ名、リダイレクト、`)` や `` ` `` の付いた語、一覧にないオプション）は、今までどおり切り替えとみなす。
   - 一覧: `--show-current`、`--list`、`--all`・`-a`、`--remotes`・`-r`、`--verbose`・`-v`・`-vv`
   - `&` は区切りとみなさない（[D5](#decision-ampersand)）。
   - 一覧で判定するのは、`git` が記号より前で、裸の語としてコマンドの先頭にあるときだけ（[D6](#decision-command-start)）。
2. `claude/hooks/tests/test-protect-main-branch.sh`: テストを足す。
   - 通る（0）: feature ブランチで `git branch --show-current && git commit`、`git branch; git commit`、`git branch -vv && git commit`、`cd <dir> && git branch --show-current && git commit -m "a b"`
   - 止める（2）: feature ブランチで `git branch -m main && git commit`、`git branch -M main && git commit`、`git branch --show-current -m main && git commit`、`git branch new && git commit`、`git branch --show-current 2>/dev/null && git commit`
   - 止める（2）: main ブランチで `git branch --show-current && git commit`（cwd の検査で止まる）
   - 止める（2）: `branch` に展開されるエイリアスの後の commit（今までどおり）
   - 止める（2、`/review` で追加）: `git branch &>/dev/null -m main`、`git branch -a&>>/dev/null -m main`、`$(echo git branch -v) -m main`、`a=( git branch -v); "${a[@]}" -m main`、`` git branch -v` echo m main` ``、文字列やヒアドキュメントの中の行に置いた `git branch -v`、引用符の中の `;`、`(git branch --show-current)`、`-c`・`-C` の値に引用符・ブレース・グロブがある `git ... branch`、ブレース展開を使う関数で git を上書きした後の commit
   - 通る（0、Codex のレビューで追加）: `cd ~ && cd <dir> && git branch --show-current && git commit`

文書は変えない。`claude/README.md` のフックの表と CLAUDE.md は、ブランチの切り替えの判定の細部を書いていない。グローバルの CLAUDE.md の「`git switch -c` と `git commit` は別の Bash 呼び出しにする」は、変更後もそのまま正しい。

<a name="decisions"></a>
## 判断

<a name="decision-allowlist"></a>
### D1. 拒否する引数を並べるのではなく、許す引数を並べる

HEAD を変えるのは `-m`・`-M`・`--move` だけなので、それらを拒否する案もある。この案なら、ブランチの作成や複製も通せる。しかし、`-fm` のようにまとめた短いオプションや、今後の git のオプションを見落とすと、ブロックが外れる側に倒れる。必要なのは表示だけなので、許す一覧にする。一覧にない引数は、今までどおりブロックする（fail closed）。

<a name="decision-alias"></a>
### D2. `branch` に展開されるエイリアスは、今までどおり切り替えとみなす

エイリアスの値に含まれる引数は解析していない。表示だけのエイリアスでブロックされても、別の呼び出しに分ければ済む。

<a name="decision-redirect"></a>
### D3. リダイレクトは一覧に入れない

`git branch --show-current 2>/dev/null` は、`2>/dev/null` が一覧にないのでブロックされる。リダイレクトの書き方は多く、正しく読み分けるには解析が要る。ブロックされたら、リダイレクトを外すか別の呼び出しに分ければ済む。

<a name="decision-process"></a>
### D4. 権限の境界としては扱わず、TDD と `/review` で進める

このフックは誤操作を防ぐためのもので、迂回できる経路が元からある（[残るリスク](#residual-risks)）。`main` への push は `cc-safe-push` が拒否する。変更は 2 ファイルで、ブロックを外すのは表示だけの呼び出しに限る。Codex のレビューは任意とする（D1 の判断だけを含む小さな変更のため）。

<a name="impact"></a>
## 影響

- `git branch` を一覧と表示だけで使ったときに、同じ呼び出しの commit がブロックされなくなる。コミット先は、今までどおりフックの cwd と、解決した対象のブランチで判定する。
- そのほかの `git branch` の呼び出しと、`checkout`・`switch`・`symbolic-ref`・`rebase` の扱いは変わらない。

<a name="steps"></a>
## 手順

| # | 作業 | 確かめること | 誰が |
| --- | --- | --- | --- |
| 1 | この plan を `/crit-review` で開く | `approved: true` | あなた |
| 2 | 作業ブランチ `fix/protect-main-branch-read-only-branch` を切る（ファイルは変わらない）。共有の作業ツリーにいるほかのセッションも、このブランチに移る | ブランチが切り替わる | Claude |
| 3 | テストを足す | 「通る」の 3 件が失敗し、ほかは通る | Claude |
| 4 | フックを直す | フックのテストがすべて通る | Claude |
| 5 | 検証: フックのテスト 6 本（CLAUDE.md の規約の一覧）、`check-repo.py`、`test-check-repo.py`、shellcheck、actionlint | すべて通る（`check-repo.py` は、ほかの作業の未追跡の文書による失敗を除く） | Claude |
| 6 | `/review` | 指摘への対応が決まる | Claude |
| 7 | コミット（plan・フック・テスト）。`/crit-review` でブランチの差分を開く | `approved: true` | Claude・あなた |
| 8 | `cc-safe-push`、`cc-safe-pr create`、`gh pr checks` | CI が通る。マージはあなた | Claude |

フックのテストは、`$TMPDIR` を cwd にして絶対パスで実行する。sandbox では、書き込めない cwd でヒアストリングが失敗するため。

<a name="done"></a>
## 完了条件

- 足したテストのうち「通る」の 3 件が、フックを直す前に失敗し、直した後に通る。
- 「止める」のテストと既存のテストが、直す前も後も通る。
- 手順 5 の検証がすべて通る。
- PR の CI が通る。

<a name="review-decisions"></a>
## レビューでの決定

`/review` の攻撃者の視点のレビュー（Claude のサブエージェント、2 回）が、変更で生じた後退を挙げた。どれも、変更前のフックと変更後のフックに同じ入力を与え、変更前は 2、変更後は 0 になることを確かめた。

<a name="decision-ampersand"></a>
### D5. `&` を区切りとみなさない

`sed` は `&` の前後に空白を入れるので、`&>/dev/null` はトークン `&` と `>/dev/null` に分かれる。`&` を区切りとみなすと、`git branch &>/dev/null -m main && git commit` の `-m main` を見ずに通す。`&` を一覧にないトークンとして扱い、ブロックする。`git branch -v & ...` も、変更前と同じくブロックされる。

<a name="decision-command-start"></a>
### D6. 一覧で判定するのは、`git` が記号より前で、裸の語としてコマンドの先頭にあるときだけにする

フックはコマンドを空白で区切るだけなので、引用符・置換・ヒアドキュメント・配列の中の `;` や改行も区切りのトークンになる。そのため、次の形では `git` の語がコマンドの先頭に見えても、引数がその外に続く。

- 1 回目のレビュー: `$(echo git branch -v) -m main`、`a=( git branch -v); "${a[@]}" -m main`
- 2 回目のレビュー: `` git branch -v` echo m main` ``（末尾の `` ` `` がコマンド置換を開く）、複数行の配列や文字列、ヒアドキュメントの中の行に置いた `git branch -v`、引用符の中の `;`
- 3 回目のレビュー: `git -c "a.b=x \" branch -v ; " branch -m main`、`git -C "d branch -v ; " branch -m main` など、`git` と `branch` のあいだのオプションの値に引用符がある形（オプションを読むループの引用符のつなぎ方が、シェルとずれる）

1 回目の後は、`git` が区切りの直後にあることだけを求め、`)` や `` ` `` で閉じた語をコマンドの終わりとみなしていた。2 回目で、例外を 1 つずつ塞いでも別の形が見つかるとわかったので、許す形を狭めた（2026-11-21、あなたの判断）。

- `git` のトークンが、`(` や `` ` `` の付かない裸の `git` であり、区切りの直後にある。
- `git` より前のどのトークンにも、`'`・`"`・`\`・`$`・`` ` ``・`(`・`)`・`<`・`{`・`}`・`*`・`?`・`[`・`^`・`#` がない（ブレースから後ろは [D9](#decision-expansion) で追加）。`git` と `branch` のあいだのトークン（`-c`・`-C` の値など）にもない（3 回目のレビューで追加）。
- 引数は一覧の語だけで、`)` や `` ` `` を取り除いて照合することはしない。

`cd <dir> && git branch --show-current && git add ... && git commit -m "..."` は通る（引用符が `git branch` より後ろにあるため）。`(git branch --show-current)`、`LC_ALL=C git branch --show-current`、`command git branch`、`` echo `git branch --show-current` ``、`echo "x" && git branch --show-current`、`git -c 'x=y' branch --show-current` は、変更前と同じくブロックされる。

<a name="decision-function"></a>
### D7. `git` のシェル関数による上書きは、D6 で止まるようになった

1 回目の後は、`git() { command git "$@" -m main; }; git branch && git commit` が通った（変更前は止まる）。フックは `git` の語が git 本体だと仮定しているので、字句を見るだけでは防げない。関数やクォート（`br"anch"`）で中身を隠す迂回は前からあるので、残るリスクとして記録する判断だった（2026-11-21、あなたの判断）。

D6 の後は止まる。`git()` の `(`、引数を渡す `"$@"`、中身を隠す引用符が、どれも D6 の記号に当たるため。`function git { command git br"anch" -m main; }` と `function git { command git branch -m main; }` の形も、変更前と同じく 2 になることを確かめた。

<a name="decision-global-options"></a>
### D8. 値を別のトークンに取るグローバルオプションの穴は、別の作業にする

`git --git-dir .git branch -m main && git commit` は、変更前から通る。オプションを読むループが `-C`・`-c` 以外の `-*` を 1 トークンだけ飛ばすので、`.git` をサブコマンドと読む。`checkout`・`switch` と、`--work-tree`・`--namespace`・`--config-env` でも同じ。今回の範囲外なので、[残るリスク](#residual-risks)に書き、別の作業で直す（2026-11-21、あなたの判断）。

<a name="decision-expansion"></a>
### D9. ブレース展開とグロブも記号に入れる

Codex のレビュー（[試験記録](test-report.md#codex-review-3)）が、D6 の記号にブレース展開がないため、変更前は止まり変更後は通る形を 2 種類挙げた。どちらも採用した。

- `function git { command git {branch,-M,main}; }; git branch; unfunction git; git commit`: 関数の中身の `{branch,-M,main}` は `branch` と読まれず、後ろの裸の `git branch` が表示だけとみなされる。zsh は関数を呼ぶときに `git branch -M main` を実行する。
- `git -C {.,branch,-m} branch && git commit`（`-c` でも同じ）: フックは値を 1 つのトークンとして読み飛ばすが、zsh は `git -C . branch -m branch` に展開する。

1 つのトークンを複数の引数にする展開は、グロブも同じなので、`*`・`?`・`[` も足した。前のコマンドで `-m` などの名前のファイルを作れば、`git -C * branch` で引数を組み立てられる。`zsh/setpot.zsh` で `extended_glob` が有効なので、`^`（否定）と `#`（繰り返し）も足した。`~` は足さない。語の先頭ではホームのパス、途中では除外で、どちらも語を複数に増やさない。足すと `cd ~/dotfiles && git branch --show-current && ...` も止まる。

<a name="rollback"></a>
## ロールバック

PR を revert する。フックの判定が今と同じに戻る。フックはシンボリックリンクなので、revert した後の次の Bash 呼び出しから効く。

<a name="residual-risks"></a>
## 残るリスク

今回の範囲外。フックは `commit` の文字列と、`commit` に展開されるエイリアスだけを見る。そのため、現在のブランチにコミットを作るほかのコマンド（`merge`・`cherry-pick`・`revert`・`am`・`pull`、`commit-tree` と `update-ref` の組み合わせ）は検査しない。2026-11-21 に、dotfiles が `main` にあるあいだ、一時リポジトリでの `commit-tree` が止められないことを確かめた。`main` への push は `cc-safe-push` が拒否するので、こうしたコミットはローカルに留まる。直すかどうかは別の作業で決める。

ブランチの切り替えの判定にも、字句だけを見ることによる迂回が、変更前から残る。今回の変更による後退ではない。

- 値を別のトークンに取るグローバルオプション（`--git-dir <dir>` など）の後ろのサブコマンド（[D8](#decision-global-options)）。直すときは、値を取るオプションを 2 トークン飛ばし、知らない `--*` はブロックする。
- `git` の語に記号が付いた形（`\git branch -m main` など）。トークンが `git` と一致しないので、解析されない。
