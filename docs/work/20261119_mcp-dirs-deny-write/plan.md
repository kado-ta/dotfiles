---
status: in-progress
created: 2026-11-19
---

# Playwright MCP の入れる場所と出力先を、起動したディレクトリによらず書き込み禁止にする

<a name="goal"></a>
## 目的

PR #46 の Codex のレビュー（2026-11-18T16:36Z、"patch is incorrect"）の P1 の指摘に対応する。Playwright MCP の入れる場所（`~/.local/share/claude-mcp`）と出力先（`~/Library/Caches/playwright-mcp`）を、Claude Code をどこで起動しても、sandbox の中の Bash からも Edit・Write ツールからも書けないようにし、`check-repo.py` で確かめる。

<a name="related"></a>
## 関連

- [PR #46 の計画（Playwright MCP の導入）](../20261118_playwright-mcp/plan.md#decisions)
- [Claude Code 設定の設計メモ: Playwright MCP](../../../.claude/rules/CLAUDE_CONFIG.md#playwright-mcp)
- [Claude Code 設定の設計メモ: Edit・Write ツールの書き込み](../../../.claude/rules/CLAUDE_CONFIG.md#edit-write-rules)（mise の前例）
- Codex のレビューの記録: `~/.codex/sessions/2026/11/19/rollout-2026-11-19T01-36-52-*.jsonl`

<a name="background"></a>
## 経緯

指摘の要旨: `~` で起動すると、2 か所は sandbox の allowWrite の `.` に入り、書ける。denyWrite と Edit の deny は 2 か所を守っていない。`cli.js` を書き換えれば次の MCP の起動時に sandbox の外で動き、出力先は symlink に差し替えられる。

この指摘は、後で実行した Codex のレビュー（03:45、直すべき不具合なし）の結果に埋もれ、PR #46 では対応しなかった。記録を読み直し、このレビューの指摘は P1 の 1 件だけだったことを確かめた（2026-11-19）。

<a name="facts"></a>
## 事実

- `register-mcp.sh` は `~/.local/share/claude-mcp/<name>` に `npm install` し、`$(mise where node)/bin/node` で `cli.js` を起動する登録を作る。定義の `--output-dir` は `${HOME}/Library/Caches/playwright-mcp`。MCP サーバーと `register-mcp.sh` は sandbox の外で動く。
- リポジトリのルートで起動したセッションからは、2 か所に書けなかった（2026-11-19 に touch で確認済み）。`~` で起動したときに書けることは、まだ測っていない（[手順](#steps)の 1 で測る）。
- `~` で起動すると、`blockWritesOutsideWorkingDirectories` も 2 か所には効かない（作業ディレクトリの中になる）。
- sandbox の denyWrite は Bash しか止めない。Edit の deny は sandbox の denyWrite にもなる（ask はならない）。どちらも [CLAUDE_CONFIG.md](../../../.claude/rules/CLAUDE_CONFIG.md#edit-write-rules) に記録がある。
- `cc-crit` が設定と照合するのは `sandbox.filesystem.denyRead` だけ（`claude/bin/cc-crit` の `check_deny_read`、413〜429 行）。今回は denyRead も `Read(...)` の deny も足さないので、`COVERED_DENY_READ` と `cc-crit.sb` の更新は要らない。

<a name="changes"></a>
## 変更

| ファイル | 変更 | 編集する人 |
| --- | --- | --- |
| `claude/settings.json` | `sandbox.filesystem.denyWrite` に `~/.local/share/claude-mcp`・`~/Library/Caches/playwright-mcp`、`permissions.deny` に `Edit(~/.local/share/claude-mcp/**)`・`Edit(~/Library/Caches/playwright-mcp/**)` を足す | あなた |
| `.github/scripts/check-repo.py` | `playwright-mcp` の検査（定義があるあいだ）で、上の 4 項目があることと、定義の `--output-dir` が守っている場所と同じであること（[D4](#decision-output-check)）を確かめる | Claude |
| `.github/scripts/test-check-repo.py` | 上の検査のテスト。先に書いて失敗を確かめる | Claude |
| `.claude/rules/CLAUDE_CONFIG.md` | Playwright MCP の節の「sandbox から書けない場所にしている」を、明示的に守る形に直す。残るリスクを 1 行足す | Claude |
| `CLAUDE.md` | 禁止事項の Playwright MCP の行に、4 項目を足す | Claude |
| `claude/README.md` | MCP サーバーと Playwright MCP の節の「sandbox から書けない」を直す。削除の手順に 4 項目を足す | Claude |
| `claude/scripts/register-mcp.sh` | 9 行目のコメント「入れる場所は sandbox から書けない」を直し、場所を変えるときは設定と検査も変えると書く（コメントだけ） | Claude |

足す内容（HEAD の版に対して）:

```json
      "mcp__playwright__browser_file_upload",
      "Edit(~/.local/share/claude-mcp/**)",
      "Edit(~/Library/Caches/playwright-mcp/**)"
    ],
```

```json
      "denyWrite": [
        "~/.config/mise",
        "~/dotfiles/mise",
        "~/.local/state/mise",
        "~/.local/share/claude-mcp",
        "~/Library/Caches/playwright-mcp"
      ]
```

<a name="decisions"></a>
## 判断

<a name="decision-both"></a>
### D1. denyWrite と Edit の deny を両方置く

- Edit の deny は必須。denyWrite は Edit・Write ツールを止めない。
- denyWrite は、Edit の deny が sandbox の denyWrite にもなるので、今の Claude Code では効き目が重なる。それでも置く。
  - Bash の守りが、Edit の規則の形に依存しなくなる。出力を消したいなどの理由で Edit を ask に緩めると、ask は sandbox に変換されないので、Bash の守りが黙って消える。
  - mise の前例（`MISE_DENY_WRITE` と `MISE_EDIT_DENY`）と同じ形になり、検査も同じ形で書ける。
  - 費用がない。2 か所に sandbox の中から書く処理はない（`register-mcp.sh` と MCP サーバーは sandbox の外で動く）。
- 片方だけにする案: Edit の deny だけでも、今は Bash も止まる見込み。ただし上の 1 点目の理由で採らない。

<a name="decision-deny"></a>
### D2. Edit は ask ではなく deny にする

Claude が 2 か所に書く理由がない。スクリーンショットは Read で読める（Read は止めない）。出力を消すのは人間が行う（README の「いつ消してもよい」）。

<a name="decision-scope"></a>
### D3. 検査は `playwright-mcp` に入れ、定義があるあいだだけ求める

`~/.local/share/claude-mcp` は、ほかの MCP の定義にも使う場所だが、今の定義は Playwright だけなので、ほかの守りと同じく `claude/mcp/playwright.json` があるあいだだけ求める。定義を消すときは、削除の手順で一緒に外す。

<a name="decision-output-check"></a>
### D4. 定義の `--output-dir` と、守っている場所が同じかも確かめる

入れる（2026-11-19 にレビューで決定）。あなたの案にはない追加。denyWrite は、実際の出力先と同じパスのときだけ意味がある。定義の `--output-dir` を変えて設定を変え忘れると、守りが黙って外れる。定義は JSON なので、`args` の `--output-dir` の次の値が `${HOME}/Library/Caches/playwright-mcp` であることを 10 行ほどで確かめられる。`--output-dir=…` の形や 2 回の指定は失敗にする（安全側）。テストの最小構成の `playwright.json`（今は `{}`）に `args` を足す。

入れる場所（`register-mcp.sh` の `packages_dir`）は、シェルスクリプトの文字列を照合することになり壊れやすいので、検査しない。代わりにコメントで、変えるときは設定と検査も変えると書く。

<a name="decision-node"></a>
### D5. MCP を起動する mise の node は、この作業では守らない

守らない（2026-11-19 にレビューで決定）。MCP の `command` は `~/.local/share/mise/installs/node/<版>/bin/node` で、`~` で起動したセッションからは同じ理由で書ける見込み（推測。手順 1 で測る）。書き換えれば、次の MCP の起動時に sandbox の外で動く。

- 採らない理由: node は MCP 専用ではなく、端末のすべての `node` で使う。`~` で起動したセッションは、ほかにも sandbox の外で動く場所（`~/Library/LaunchAgents`、`~/.npm` のキャッシュなど）に書ける。1 か所ずつ塞ぐのは別の設計で、`~` で起動しない規則（グローバルの CLAUDE.md の Safety）が主な守り。
- 代わりに、CLAUDE_CONFIG.md の Playwright MCP の節に、残るリスクとして 1 行書く。
- 守る案: `~/.local/share/mise` を denyWrite と Edit の deny に足す。リポジトリのルートで起動したセッションでは、もともと Bash から書けないので、失うものは `~` で起動したセッションの `mise install` くらい。採るなら、MCP ではなく mise の守り（`MISE_DENY_WRITE`）として足す。

<a name="impact"></a>
## 影響

- 攻撃面: `~`（と、2 か所を含むほかのディレクトリ）で起動したセッションで、2 か所への Bash と Edit・Write の書き込みがなくなる。リポジトリのルートで起動したセッションは変わらない（もともと書けない）。
- 読み取りは変えない。出力先は sandbox の中から読めたまま（PR #46 で受け入れたリスクのまま）。
- `register-mcp.sh`・MCP サーバー・人間の端末の操作は sandbox の外なので、影響しない。
- 後方互換: 設定を足すだけ。`check-repo.py` は、設定を足す前の作業ツリーでは失敗する。

<a name="steps"></a>
## 手順

| # | 作業 | 確かめること | 誰が |
| --- | --- | --- | --- |
| 1 | 設定を変える前に、`~` で起動した短いセッションで、Bash の[測る命令](#probe)を実行する（再現） | 2 か所が `writable` になる。D5 の判断の材料に、`~/.local/share/mise` も見る | あなた（実行しなかった。設定を先に編集したので、変更前の状態はもう測れない） |
| 2 | `test-check-repo.py` にテストを足す | 新しいテストが失敗する | Claude |
| 3 | `check-repo.py` に検査を足す | `test-check-repo.py` がすべて通る。実際のリポジトリの `check-repo.py` は、設定を足す前なので `playwright-mcp` が失敗する | Claude |
| 4 | `claude/settings.json` を編集する（[変更](#changes)の 2 つの断片） | `check-repo.py` がすべて通る | あなた |
| 5 | 文書とコメントを直す | `check-repo.py` の `markdown-links` が通る | Claude |
| 6 | 検証: `check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・フックのテスト・`test-register-mcp.py` | すべて通る | Claude |
| 7 | 新しく `~` で起動したセッションで、[測る命令](#probe)の 2 つと、Write ツールでの 2 か所への書き込み（大文字・小文字を変えた綴りも）を試す | 2 か所が `denied`、綴りを変えても `denied`、Write も拒否される。対照の `~/Library/Caches`・`~/.local/share` は `writable`（`.` がホームであることの確認）。出力先がないときの結果で、[D8](#decision-case) の次の対応を決める | あなた |
| 8 | `/review` → `/security-review`。Codex のレビューは通常の端末で実行し、2 回以上なら全部の結果を貼ってもらう | 指摘への対応が決まる | Claude・あなた |
| 9 | コミット（`settings.json` は HEAD の版に今回の追加だけを入れたものを index に置く）。`/crit-review` でブランチの差分を開く | `approved: true` | Claude・あなた |
| 10 | `cc-safe-push`、`cc-safe-pr create`、`gh pr checks` を最大 60 分待つ | CI が通る。マージはあなた | Claude |

セッションの開始時の sandbox の設定の表示は、項目が多いと途中で切れる（このセッションでも `... and 111 more`）。表示で 2 か所を確かめられなければ、手順 7 の結果で判断する。設定を編集した後、このセッションの表示は `... and 115 more` になった（4 件増えた。どのパスかは表示されない）。

<a name="probe"></a>
### 測る命令

`~` で起動したセッションで、Claude に Bash ツールで実行させる。書けた場所には空のファイルを作ってすぐ消す。`~/.claude.json` は `touch -c` で更新日時だけを変える（MCP の登録があるファイルで、書ければ 2 か所を守っても登録ごと差し替えられるため、残るリスクの記録に使う）。

```bash
for d in ~/Library/Caches ~/.local/share ~/.local/share/claude-mcp ~/Library/Caches/playwright-mcp ~/.local/share/mise; do
  [ -d "$d" ] || { echo "missing:  $d"; continue; }
  if touch "$d/.cc-probe" 2>/dev/null; then rm -f "$d/.cc-probe"; echo "writable: $d"; else echo "denied:   $d"; fi
done
if touch -c ~/.claude.json 2>/dev/null; then echo "writable: ~/.claude.json"; else echo "denied:   ~/.claude.json"; fi
```

手順 7 では、続けて大文字・小文字を変えた綴りを試す（どちらもあるディレクトリに解決される）。

```bash
for d in ~/.local/share/CLAUDE-MCP ~/Library/Caches/Playwright-MCP; do
  if touch "$d/.cc-probe" 2>/dev/null; then rm -f "$d/.cc-probe"; echo "writable: $d"; else echo "denied:   $d"; fi
done
```

<a name="results"></a>
#### 結果

2026-11-19、設定を足した後に `~` で起動したセッションで、上の 1 つ目の命令を実行した（あなたが実行し、結果を貼った）。

| 対象 | 結果 |
| --- | --- |
| `~/Library/Caches`（対照） | writable |
| `~/.local/share`（対照） | writable |
| `~/.local/share/claude-mcp` | denied |
| `~/Library/Caches/playwright-mcp` | denied |
| `~/.local/share/mise` | writable（D5 のとおり守っていない） |
| `~/.claude.json` | denied（Claude Code が守っている） |

対照に書けたので、このセッションの `.` はホームで、2 か所はこの作業の設定で拒否されたとみなせる。変更前に書けたことは測っていない（手順 1 を実行しなかった）。

同じ日に、`~` で起動したセッションで、`~/.local/share/claude-mcp/playwright/node_modules/@playwright/mcp/cli.js`（あることを確かめた）へのハードリンクを `~/.cc-probe-link` に作ろうとした。`ln: …: Operation not permitted`（終了コード 1）で拒否された。書き込みを止めた場所のファイルを、書ける場所からのハードリンクで書き換える迂回は、このファイルについては成り立たない。ほかの場所では試していない。

同じ日に、`~` で起動したセッションで、大文字・小文字を変えた綴り（`~/.local/share/CLAUDE-MCP`・`~/Library/Caches/Playwright-MCP`）を試した。どちらも元のディレクトリに解決され（`ls -ld` で確認）、`touch: …: Operation not permitted`（終了コード 1）で拒否された。ディレクトリがあるあいだは、綴りを変えても迂回できない。

同じ日に、`~` で起動したセッションで、Write ツールで `~/.local/share/claude-mcp/.cc-probe` と `~/Library/Caches/playwright-mcp/.cc-probe` に書こうとした。どちらも `File is in a directory that is denied by your permission settings.` で拒否され、ファイルはできなかった。作業ディレクトリ（ホーム）の中なので、`blockWritesOutsideWorkingDirectories` ではなく、足した `Edit(...)` の deny が止めた。

出力先がないときの確認（[D8](#decision-case)）は、出力先を退避したうえで `~` で起動したセッションで試そうとしたが、そのセッションの権限の判定でコマンドが実行されなかった。出力先は元に戻した（中身が 17 項目のまま戻ったことを確認）。D8 は未測定のまま、残るリスクとして扱う。この作業をした dotfiles のセッションの `!` は、この日は sandbox の外で動いた（`~/.ssh/config` を読めた）ので、`!` は測定に使わない（`!` は人間が操作するもので、守りの穴ではない）。

出力先がないときの確認は、次の順で行う。1 と 3 は通常の端末で、2 は `~` で起動したセッションの Bash ツールで実行する。

1. `mv ~/Library/Caches/playwright-mcp ~/Library/Caches/playwright-mcp.bak`
2. `if mkdir ~/Library/Caches/Playwright-MCP 2>/dev/null; then rmdir ~/Library/Caches/Playwright-MCP; echo "writable: missing dir with another case"; else echo "denied:   missing dir with another case"; fi`
3. `mv ~/Library/Caches/playwright-mcp.bak ~/Library/Caches/playwright-mcp`

<a name="done"></a>
## 完了条件

- `test-check-repo.py` の新しいテストが、検査を足す前に失敗し、足した後に通る。
- 設定を足した後、`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・フックのテスト・`test-register-mcp.py` が通る。
- `~` で起動したセッションで、2 か所への Bash と Write ツールの書き込みが拒否される。大文字・小文字を変えた綴りでも拒否される（手順 7）。
- PR の CI が通る。

<a name="review-decisions"></a>
## レビューでの決定

`/review`（2026-11-19）の指摘への対応。どれも、あなたの判断。

<a name="decision-test-gap"></a>
### D6. 定義を消したときのテストに、denyWrite も含める

`test_without_playwright_definition_passes` が、定義を消したときに新しい denyWrite を求めないことを確かめていなかった（testing の指摘）。fixture の denyWrite から 2 か所も外した。検査を定義の有無の前に動かす変更を入れると、このテストが落ちることを確かめた。

<a name="decision-node-modules"></a>
### D7. Node がさかのぼる親の `node_modules` は守らず、残るリスクとして記録する

0.0.85 は起動時に、入っていない `bufferutil` を `require` する。Node は入れる場所の外の親（`~/.local/share/node_modules`・`~/.local/node_modules`・`~/node_modules`）と `~/.node_modules`・`~/.node_libraries` まで探す。偽の HOME で、置いたコードが動くことを実測した（敵対的レビュー）。`~` で起動したセッションがここにコードを置くと、以後のすべてのセッションで、MCP の起動時に sandbox の外で動く。D5 と同じ種類の経路なので、同じく守らない。

<a name="decision-case"></a>
### D8. 大文字・小文字だけ違う名前は、手順 7 で測り、出力先を消さない運用にする

ホームの APFS は大文字・小文字を区別しない。sandbox の照合が区別するなら、出力先がないあいだに `Playwright-MCP` のような名前で作られ、MCP がそこ（symlink の先も）に出力するおそれがある（Red Team と敵対的レビュー。どちらも未測定）。今は 2 か所ともある。README を「中身は消してよい、ディレクトリは残す」に直した。手順 7 で、出力先がないときに綴りを変えて作れたら、`register-mcp.sh` で出力先を作っておく修正を別に相談する。

<a name="decision-npmrc"></a>
### D9. `register-mcp.sh` が読む `~/.npmrc` は、残るリスクとして記録する

`register-mcp.sh` は sandbox の外で `cd ~` してから `npm install` するので、`~/.npmrc` を読む。`~` で起動したセッションが `registry=` を書き換えておくと、次に版を上げて登録したときに、差し替えた registry のパッケージを入れる場所に入れる。以前からある問題で、この差分で悪化していない。

<a name="rollback"></a>
## ロールバック

PR を revert し、`claude/settings.json` から 4 項目を消す。設定は足すだけなので、消せば今と同じに戻る。消した後に始めたセッションから効く。

<a name="residual-risks"></a>
## 残るリスク

次のリスクは受け入れた（2026-11-19 に、計画のレビューと `/review` の後に決定）。

- `~` で起動したセッションでは、2 か所以外の、sandbox の外で動く場所に書ける。D5 の node、[D7](#decision-node-modules) の親の `node_modules`、[D9](#decision-npmrc) の `~/.npmrc`、`~/Library/LaunchAgents` などがある。MCP の登録がある `~/.claude.json` は、`~` で起動したセッションからも書けなかった（[結果](#results)）。
- 親のディレクトリ（`~/Library/Caches`・`~/.local/share`）を別の名前に移して作り直す迂回を、sandbox が止めるかは確かめていない。移すと多くのものが壊れるので、測らない。
- 大文字・小文字だけ違う名前の迂回は、手順 7 の結果が出るまで未確認（[D8](#decision-case)）。
