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
| 1 | 設定を変える前に、`~` で起動した短いセッションで、Bash の[測る命令](#probe)を実行する（再現） | 2 か所が `writable` になる。D5 の判断の材料に、`~/.local/share/mise` も見る | あなた |
| 2 | `test-check-repo.py` にテストを足す | 新しいテストが失敗する | Claude |
| 3 | `check-repo.py` に検査を足す | `test-check-repo.py` がすべて通る。実際のリポジトリの `check-repo.py` は、設定を足す前なので `playwright-mcp` が失敗する | Claude |
| 4 | `claude/settings.json` を編集する（[変更](#changes)の 2 つの断片） | `check-repo.py` がすべて通る | あなた |
| 5 | 文書とコメントを直す | `check-repo.py` の `markdown-links` が通る | Claude |
| 6 | 検証: `check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・フックのテスト・`test-register-mcp.py` | すべて通る | Claude |
| 7 | 新しく `~` で起動したセッションで、手順 1 の命令と、Write ツールでの 2 か所への書き込みを試す | 2 か所が `denied`、Write も拒否される。対照の `~/Library/Caches`・`~/.local/share` は `writable`（`.` がホームであることの確認） | あなた |
| 8 | `/review` → `/security-review`。Codex のレビューは通常の端末で実行し、2 回以上なら全部の結果を貼ってもらう | 指摘への対応が決まる | Claude・あなた |
| 9 | コミット（`settings.json` は HEAD の版に今回の追加だけを入れたものを index に置く）。`/crit-review` でブランチの差分を開く | `approved: true` | Claude・あなた |
| 10 | `cc-safe-push`、`cc-safe-pr create`、`gh pr checks` を最大 60 分待つ | CI が通る。マージはあなた | Claude |

セッションの開始時の sandbox の設定の表示は、項目が多いと途中で切れる（このセッションでも `... and 111 more`）。表示で 2 か所を確かめられなければ、手順 7 の結果で判断する。

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

<a name="done"></a>
## 完了条件

- `test-check-repo.py` の新しいテストが、検査を足す前に失敗し、足した後に通る。
- 設定を足した後、`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・フックのテスト・`test-register-mcp.py` が通る。
- `~` で起動したセッションで、2 か所への Bash と Write ツールの書き込みが拒否される（手順 7）。
- PR の CI が通る。

<a name="rollback"></a>
## ロールバック

PR を revert し、`claude/settings.json` から 4 項目を消す。設定は足すだけなので、消せば今と同じに戻る。消した後に始めたセッションから効く。

<a name="residual-risks"></a>
## 残るリスク

次の 2 つは受け入れた（2026-11-19 にレビューで決定）。

- `~` で起動したセッションでは、2 か所以外の、sandbox の外で動く場所に書ける（D5 の node、`~/Library/LaunchAgents` など）。`~/.claude.json` に書けるかは手順 1 で測り、書けるならこの文書と CLAUDE_CONFIG.md に記録して、別の作業の候補にする。
- 親のディレクトリ（`~/Library/Caches`・`~/.local/share`）を別の名前に移して作り直す迂回を、sandbox が止めるかは確かめていない。移すと多くのものが壊れるので、測らない。
