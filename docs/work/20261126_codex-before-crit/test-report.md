---
status: in-progress
created: 2026-11-26
---

# 試験記録: Codex レビューの提案を、ブランチの差分の Crit の前に出す

関連: [plan.md](plan.md)

<a name="plan-approval"></a>

## 1. Plan の承認

2026-11-26 に `/crit-review docs/work/20261126_codex-before-crit/plan.md` で開き、コメントなしで承認された（`approved: true`）。D1 は案 A（受け入れられたら先にコミットする）、D2 は `commit-staged-pr` に足して `sync-skill-docs` は変えない、D3 はフックで強制しない。

<a name="checks"></a>

## 2. 検証（plan の 6 章）

2026-11-26、ブランチ `docs/codex-before-crit`（作業ツリーの変更、未コミット）で実行した。`/review` の前の文面での結果で、grep の 2 行は、その後の F2 の修正で当たり方が変わった。`/review` の後の結果は [6 章](#checks-after-review)、最終の文面での結果は [12 章](#final-checks) にある。

| 確かめること | 結果 |
| --- | --- |
| `grep -n "で開く前" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| `grep -n "完了前に Codex\|変更が完了する前" …` | 何も出なかった（終了コード 1） |
| `claude/CLAUDE.md` の実効行数 | 79 |
| 早見表の D 章（111〜118 行目）の列幅 | 曖昧幅を 1 と数えて、すべての行で `(16, 425, 51)`。変更前（`(16, 356, 51)`）と同じ数え方で揃っている。曖昧幅を 2 と数えると変更前も揃っていない |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 警告なし（終了コード 0） |
| `actionlint` | 指摘なし（終了コード 0） |
| `zizmor --offline .` | No findings to report |

早見表の独立レビューの行が列で最も長いので、列の幅が広がり、D 章の表の 8 行すべてが変わった。ほかの 7 行の変更は空白だけ。

列幅の確認と揃え直しには、scratchpad の使い捨てのスクリプト（`table_width.py`・`repad_table.py`）を使った。コミットしない。

D1 の根拠（`codex review --base` が読む範囲）は、codex-cli 0.172.0（`/opt/homebrew/Caskroom/codex/0.172.0/bin/codex`）のバイナリの文字列から、指示文「The merge base commit for this comparison is {{merge_base_sha}}. Run `git diff {{merge_base_sha}}` to inspect the changes relative to {{base_branch}}.」を読んで確かめた（2026-11-26）。Codex は自分で `git status` などを実行しうるので、未追跡のファイルを必ず見ないとまでは言えない。先にコミットするのは、見るかどうかを指示文に頼らないため。版が変われば指示文も変わりうる。

<a name="review-1"></a>

## 3. `/review`（gstack）1 回目

2026-11-26、基準 `8e4a4c3`。PR の種類は application（スキルと CLAUDE.md の指示文を含む）。追跡しているファイルの差分は 27 行で 50 行未満なので、専門のサブエージェントは起動しなかった（State Machines も対象外）。gstack の `codex_reviews=disabled` のため、Codex の外部レビューは実行せず、Claude の敵対的レビュー（サブエージェント）だけを行った。スモークの確認（`check-repo.py`、新旧の表現、行数、表の列幅）は、すべて期待どおりだった。gstack の QA の証跡の記録ツールは使わず、リポジトリのコマンドで確かめた。

main は分岐の後に PR #141・#143 で進んだ（`bfd312d`）。`claude/SKILL_CHEATSHEET.md` が両方で変わっているが、main の変更は B 章と C 章の表で、D 章の表とは重ならない。

| 指摘 | 出どころ | 内容 | 対応 |
| --- | --- | --- | --- |
| F1 | 敵対的 | commit-staged-pr の手順 5 の「Crit に進む」（49 行目と 71 行目の 3 か所）が、足した Codex の項目を飛ばす | 直した（「Codex の項目に進む」。71 行目の「Crit に進まずに」は「先に進まずに」） |
| F2 | 敵対的・自分の確認 | 「完了前に」を「Crit で開く前に」に変えたので、Crit を開かない作業で提案が出なくなる（plan の前提「変えるのは時期だけ」に反する） | 直した（CLAUDE.md は「完了前（ブランチの差分を `/crit-review` で開くときは、その前）に」、SKILL_ROUTING.md も同じ形） |
| F3 | 敵対的 | 「先にコミット」に、提案の文面で伝えることと、コミットする範囲がない | 直した（「提案の文面で先にコミットすると伝え」「この作業の変更を」） |
| F4 | 敵対的 | commit-staged-pr が参照する表の「先にコミット」が、`git add` の禁止とぶつかる | 直した（手順 4 のコミットで済んでいるので、ほかにコミットしないと書いた） |
| F5 | 敵対的 | 2 回目以降の Codex では、直した変更が未コミットのまま | 直した（「コマンドを渡すたびに」） |
| F6 | 敵対的 | commit-staged-pr の `--base` にローカルの base を渡すと、古いときにマージ済みの変更まで読む | ユーザーの判断（D2 = A）で直した（`origin/<PR の base>` と、先に `git fetch`）。表の汎用のコマンド（`--base <base>`）は前からの書き方なので変えていない |
| F7 | 敵対的 | 未ステージの変更があるとき、PR に入る版を Codex が見ないことが抜けている | 直した（「PR に入る版ではなく作業ツリーの版を Codex が見る」） |
| F8 | 敵対的・自分の確認 | フェーズ 2 で Crit を開き直すとき、Codex を提案するかが決まっていない | ユーザーの判断（D1 = B）で直した（この作業でまだ提案していなければ提案する） |
| F9 | 敵対的 | `docs/work/` のないリポジトリで、Exit criteria の test-report が未追跡のファイルになる | ユーザーの判断（D3 = B）で変えない。スキルは最後に未追跡のファイルを報告する |
| F10 | 敵対的 | sync-skill-docs の手順 12 は Codex を挟まない | 数えない。plan の D2 で変えないと決め、Crit で承認された |
| F11 | 敵対的 | SKILL_ROUTING.md が CLAUDE.md の時期を繰り返し、条件の書き方が 3 通りになる | 数えない。2 行の言い換えは plan の 4.2 で承認された。条件の違いは plan の 7 章で別の作業にした |
| F12 | 敵対的 | 早見表は、Claude が毎回コミットするように読める | 数えない。行は Codex を実行するときの流れを書いていて、そのときはコミットしてから渡す |
| F13 | 敵対的 | D1 の根拠が版に依存し、test-report に記録がない | 直した（この章の前の段落に、確かめた版と指示文を書いた） |

<a name="review-2"></a>

## 4. `/review` 2 回目

1 回目で直したので、差分全体（基準 `8e4a4c3`）をもう一度見た。gstack の手順は 2 回目を修正の範囲だけで見るよう求めるが、その回は最終の回にできないので、差分全体を見た。自分の確認では新しい指摘はなかった。Claude の敵対的レビュー（新しいサブエージェント。1 回目の決着は 3 章を見るよう伝えた）の指摘と対応は次のとおり。

| 指摘 | 内容 | 対応 |
| --- | --- | --- |
| G1 | フェーズ 2 で Codex の指摘を直してコミットしても、手順 6（push）に戻る道が「Crit のコメントで修正したら」の場合にしか書かれていない。push されないまま PR を作りうる（F8 の修正で入った） | 直した（「Codex の指摘か Crit のコメントで修正したら」） |
| G2 | 2 章の記録と plan の 6 章の 1 行目の grep が、F2 の後の文面と食い違う | 直した（plan の grep を今の文面にし、2 章に注記を足し、最終の結果を 5 章に書いた） |
| G3 | commit-staged-pr の Codex の項目に、当てはまらないとき・断られたとき・直すものがないときの行き先がない | 直した（「そのまま Crit に進む」） |
| G4 | 「未追跡のファイルを見ない」と言い切っているが、根拠は版に依存する指示文だけ。commit-staged-pr では、未追跡のファイルへの指摘の扱いがない | 直した（SKILL_ROUTING.md は「指示文は…読ませ、未追跡のファイルを含まない」。commit-staged-pr は「それに触れた指摘が出たら、PR に含まれないと添える」） |
| G5 | `git fetch` を頼むだけで、成功したかを確かめていない | 直した（コマンドの前に `git fetch origin <base> &&` を付ける。失敗したら codex は動かない） |
| G6 | フェーズ 2 から始めた場合、「手順 4 でコミットした差分」がない | 直した（「ブランチの差分で条件を判定して」）。base の決め方は書き足していない（PR の案の base を使う） |
| G7 | crit-review のスキルに Codex の時期がなく、ユーザーが `/crit-review` を名指ししたときの扱いが割れる | 数えない。名指ししたスキルを優先する規則（`SKILL_ROUTING.md:9`）があり、名指しはユーザーの意図とみなす |
| G8 | 「コマンドを渡すたびに」が、提案は 1 回までの規則と、ユーザーが自分で再実行する場合と噛み合わない | 直した（「実行してもらう前に…コミットする（直した後の 2 回目以降も、コミットしてから再実行を頼む）」） |
| G9 | commit-staged-pr が、試行中の SKILL_ROUTING.md の表の行に依存している | 数えない。試行の見直し（2026-12-07 に測定）で表を変えるときに、commit-staged-pr も直す。auto memory の測定のメモに書き足した |

<a name="review-3"></a>

## 5. `/review` 3 回目

差分全体をもう一度見た。自分の確認では、スモークの確認で 2 章から 5 章（今の 6 章）へのリンクが切れていた（まだ書いていない章を指していた）。Claude の敵対的レビュー（新しいサブエージェント）の指摘と対応は次のとおり。gstack の手順は、修正を伴う回を 3 回までとしている。3 回目でも直したので、`/review` は収束しないまま終えた。最終の文面は、`/review` を重ねる代わりに、Codex レビュー（提案する）とブランチの差分の Crit で見る。

| 指摘 | 内容 | 対応 |
| --- | --- | --- |
| H1 | Crit の前に先にコミットすると、その後の指摘で消した秘密情報などが前のコミットに残る。Crit は差分の結果だけを見せ、`check-repo.py` は作業ツリーだけを見るので、公開リポジトリの履歴に push されうる | ユーザーの判断（D4 = A）で直した（秘密情報や公開できない内容を消したときは、先のコミットに残っていないかを確かめ、残っていれば push の前に伝える） |
| H2 | `git fetch origin <base> &&` を付ける位置が決まっておらず、`cd <repo>` の前に付けると別のディレクトリで fetch しうる | 直した（`cd <repo> && git fetch origin <base> && codex review --base origin/<base> ...` の形で書いた） |
| H3 | 「2 回目以降も…再実行を頼む」が、提案は 1 回までの規則とぶつかり、再実行が必須とも読める | 直した（「直した後に再実行するときも、その前にコミットする」） |
| H4 | commit-staged-pr の Codex の項目に、fetch や codex が失敗したときの行き先がない | 直した（先に進まずに伝え、どうするかを確認する） |
| H5 | フェーズ 1 の Codex の項目に、すでに提案したかの確認がなく、判定の範囲（手順 4 のコミット）がフェーズ 2（ブランチの差分）と違う | 直した（「この作業でまだ提案しておらず、ブランチの差分が…」） |
| H6 | 一般の規則で先にコミットした後に commit-staged-pr を頼むと、ステージが空で push もしていないので、スキルが止まる | 数えない。スキルは状況を伝えて止まる（10 行目）ので、害はない |
| H7 | 先にコミットする範囲が、index に残るほかの変更と、作業ツリーに残る変更を扱っていない | 直した（「この作業の変更だけをパスを指定してコミットする」） |
| H8 | フェーズ 2 の文が「先に Crit を開き」で、Codex との順序を決めていない | 直した（「手順 5 の Codex の項目を行い、その後に Crit を開いて」） |
| H9 | ユーザーのターミナルで実行する `git fetch` が、sandbox から書ける submodule の設定を読みうる | 数えない。スキルは前から `git fetch origin <base>` をユーザーに頼んでいる（36 行目）。submodule の設定の経路は Issue #75 の範囲 |
| H10 | plan の 4 章の案が古く、最終の文面を指す先も不正確 | 直した（4 章の案は承認したときのままと書き、理由は test-report の 3〜5 章、最終の文面はコミットの差分を指した） |

<a name="checks-after-review"></a>

## 6. `/review` の後の確認

2026-11-26、`/review` の 3 回目の修正と D4 の後の作業ツリー（未コミット）で、plan の 6 章の確認をすべて実行し直した。

| 確かめること | 結果 |
| --- | --- |
| `grep -n "で開くときは、その前" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| `grep -n "完了前（\|完了する前。" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| commit-staged-pr の 49〜71 行目に「Crit に進む」が残っていない | 0 件 |
| `claude/CLAUDE.md` の実効行数 | 79 |
| 早見表の D 章（111〜118 行目）の列幅 | 曖昧幅を 1 と数えて、すべての行で `(16, 425, 51)` |
| `python3 -B .github/scripts/check-repo.py` | 16 項目すべて PASS（終了コード 0） |
| `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 警告なし（終了コード 0） |
| `actionlint` | 指摘なし（終了コード 0） |
| `zizmor --offline .` | No findings to report（終了コード 0） |

main は `f25fb3b`（PR #141・#143〜#147）まで進んだ。分岐の後に main で変わったのは、変更した 4 ファイルのうち `claude/SKILL_CHEATSHEET.md` の 2 行（B 章と C 章の表）だけで、D 章の表とは重ならない。

<a name="codex-1"></a>

## 7. Codex レビュー 1 回目（`codex review`）

ユーザーが通常のターミナルで `git fetch origin main && codex review --base origin/main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を実行した。新しい規則のとおり、提案を受け入れてもらった後、実行の前に 2 つのコミット（`565fda6`・`5ca9619`）を作った。結果は SKILL_ROUTING.md の Exit criteria のコマンドで読んだ（2026-11-26T05:35:12Z、コミット `5ca9619`）。5 回の上限のうち 1 回目。

最終メッセージの判定は「patch is incorrect」（overall_confidence_score 0.97）。Codex 自身は `git diff --check`・ShellCheck・`actionlint` を実行して通り、Codex と Crit の対話の流れは実行していないと書いている。

| 指摘 | 優先度 | 内容 | 採否 | 理由と対応 |
| --- | --- | --- | --- | --- |
| C1-1 | P1 | commit-staged-pr で、未ステージの変更（例: 追跡しているファイルに残したローカルの認証情報）も `git diff <merge-base>` に入り、Codex に送られる。通常のターミナルの Codex には Claude の denyRead が効かないので、伝えるだけでは送信を防げない | 採用 | 事実（`git diff <merge-base>` は作業ツリーと比べる）。commit-staged-pr では、この変更で新しくできた経路。追跡しているファイルに未ステージの変更があるときは、コマンドを渡さずに伝え、片付けるか見送るかを選んでもらうようにした。一般の流れでも、ほかの変更が作業ツリーに残ると同じことが起きるので、SKILL_ROUTING.md の行にも同じ規則を足した |
| C1-2 | P2 | `git commit -- <path>` は部分ステージを尊重せず、そのファイルの作業ツリーの内容をまとめて記録する。パスの指定だけでは「この作業の変更だけ」を保証できない | 採用 | `/review` の H7 の修正（「パスを指定して」）で入った。「この作業のファイルだけをステージしてコミットする」にし、ほかの変更が index か作業ツリーに残るとき（同じファイルに混ざっているときも）は、コミットせずに伝えるようにした |
| C1-3 | P2 | フェーズ 2 で、Codex の項目と 100 行目の両方が同じ修正のステージとコミットを指示する。両方に従うと 2 回目はステージが空になる | 採用 | 100 行目のコミットの指示を Crit のコメントの場合だけにし、Codex の項目か Crit のコメントでコミットを足したときは、承認の後に手順 6 に進むとした |
| C1-4 | P2 | フェーズ 2 から始めると、PR の base を確かめないまま Codex の手順に入る（例: `release/*` 向けの PR） | 採用 | `/review` の G6 で書き足さなかった点。フェーズ 2 から始めた場合は、Codex の項目の前に PR の base を確かめるとした |
| C1-5 | P2 | 単一ブランチの clone などで、`git fetch origin <base>` が `origin/<base>` を更新しないことがある | 採用 | refspec を明示した（`git fetch origin +<base>:refs/remotes/origin/<base>`） |

指摘の修正で消した秘密情報や公開できない内容はないので、先のコミット（`565fda6`・`5ca9619`）の確かめ（D4）は要らない。

<a name="codex-2"></a>

## 8. Codex レビュー 2 回目（challenge）

ユーザーが `codex exec - -s read-only -c skills.include_instructions=false < tmp/codex-challenge-prompt.md` を実行した。プロンプトは変更前と比べた後退を全件挙げるよう頼むもので、全文は作業ツリーの `tmp/`（git の管理外）にある。1 回目と同時に実行されたので、見た版は 1 回目の修正の前（2026-11-26T05:35:15Z、コミット `5ca9619`）。5 回の上限のうち 2 回目。

指摘は 16 件（High 1、Medium 12、Low 3）。採否を決める前に、ユーザーが D5（先にコミットしない）を選び、この回の指摘は 9 章の回と合わせて扱った。

| 区分 | 指摘 |
| --- | --- |
| 1 回目の修正（7 章）で解消済み | #2（パスを指定したコミットが部分ステージを無視する）、#3（未追跡のファイルを `git commit -- <path>` に渡すと失敗する）、#5（作業ツリーの版を Codex が読む）、#8（フェーズ 2 の二重の指示）、#9（フェーズ 2 の base）、#10 のうち refspec |
| D5 で起きなくなった | #1（先のコミットに公開できない内容が残る。High）、#4（先にコミットできないときの進み方がない）、#13（sync-skill-docs で先のコミットと承認後のコミットの順序が割れる） |
| 9 章の回と同じ内容で、そちらで対応した | #7（提案済みで実行待ちを飛ばす）、#11（過去の回の結果で済んだと判断する）、#12（Codex の修正の後の再検証）、#14（Crit を開かない作業に表が Crit を求める）、#15（不採用の指摘と challenge の扱い） |
| 採用しない | #6（再ステージの後に手順 2 のシークレットの確認を繰り返さない。前から、確認スキルと Crit の戻り方も同じなので、まとめて後続の作業の候補にする）、#10 の残り（同じ名前のタグ、浅い clone。まれ）、#16（fetch のクォートと失敗条件。9 章の #13 で fetch の submodule の再帰だけ止めた） |

<a name="codex-3"></a>

## 9. D5 と Codex レビュー 3 回目（challenge の再実行）

### 9.1 D5

8 章の回の指摘の多く（#1・#4・#13）は、D1 の「Crit の前に先にコミットする」から出ていた。代わりの案として、`codex review --uncommitted`（codex-cli 0.172.0 の `codex review --help` では「Review staged, unstaged, and untracked changes」。指示文はバイナリでは確かめていない）を示し、ユーザーが D5 を選んだ。

- 一般の流れでは、レビューのために先にコミットはしない。ブランチに base より先のコミットがなければ `--uncommitted`、あれば `--base <base>` を使い、`--base` のときは Codex が見ない未追跡のファイルを伝える。
- この作業以外の変更（未追跡のファイルも）が作業ツリーか index にあれば、Codex に送られる。コマンドを渡す前に伝え、片付けるか見送るかを選んでもらう。
- D4 の規則（先のコミットに残った秘密情報を push の前に伝える）は、先のコミットがなくなったので消した。
- commit-staged-pr は、手順 4 でユーザーのステージをコミットしてから Codex に進むので、`--base` のまま。

### 9.2 指摘と採否

ユーザーが challenge を再実行した（2026-11-26T05:53:00Z、コミット `86b9f44`。1 回目の修正の後）。5 回の上限のうち 3 回目。指摘は 19 件（High 4、Medium 11、Low 4）。

| 指摘 | 重さ | 内容 | 採否と対応 |
| --- | --- | --- | --- |
| #1 | High | commit-staged-pr で、未ステージの変更だけを見ているので、PR に入らないステージ済みの別の変更が Codex に送られる | 採用。「追跡しているファイルにコミットしていない変更（ステージ済みも）があるとき」にした |
| #2 | High | 未追跡や無視対象のファイルを、差分から外れるだけで安全と扱える（Codex は周りのファイルも読める） | 採用しない。Codex が作業ツリーのファイルを読めるのは、Codex を使うこと自体の性質（前から）。見せてよいファイルだけの環境で動かす手順は、後続の作業の候補にする |
| #3 | High | 先のコミットに入った公開できない内容が、削除の経緯によって確認されない | D5 で起きなくなった（先にコミットしない） |
| #4 | High | 1 回目の結果を記録した test-report が、次の先行コミットで公開の履歴に入りやすい | D5 で再実行の前のコミットがなくなった。記録に機微な内容を写さないのは、CLAUDE.md の Safety（シークレットを出力・コミットしない）のとおり |
| #5 | Medium | 先行コミットと、Codex が実際に読んだ状態が一致する保証がない | D5 で先行コミットがなくなった。コマンドを渡した後にユーザーが作業ツリーを変える場合は、採用しない（まれ） |
| #6 | Medium | 今回の実行が失敗しても、過去の回の結果で Crit に進める | 採用。Exit criteria を「今回実行した回（時刻とコミットで見分ける）が出なければ、その回の結果を貼り付けてもらう」にした |
| #7 | Medium | Codex の修正の後の再検証が、コミットと Crit の順序に入っていない | 採用（commit-staged-pr）。「影響する検証をやり直し」を足した。一般の流れは CLAUDE.md の Verification が効く |
| #8 | Medium | 提案の返事待ちと、失敗の後の再開が決まっていない | 採用。commit-staged-pr の条件を「Codex レビューの対応が済んでおらず（まだ提案していないか、受け入れて結果を待っている）」にし、再実行は新しい提案に数えないとした。一般の流れは、CLAUDE.md の Crit の項目（採否を決めて直した後に開く）が効く |
| #9 | Medium | フェーズ 2 が Crit を二重に開ける。承認した HEAD の記録が曖昧 | 採用。フェーズ 2 は「手順 5 の Codex の項目と Crit の項目を行う」だけにし、Crit を開く箇所と HEAD の記録を手順 5 の Crit の項目に一本化した |
| #10 | Medium | Crit のコメントの修正で初めて Codex の条件に当たっても、提案を飛ばす | 採用。Crit の項目に「修正で Codex の条件に当たるようになったら、開き直す前に Codex の項目を行う」を足した |
| #11 | Medium | Codex は PR の base、Crit は default branch を基準にするので、二つのレビューの対象がずれる | 採用しない。Crit の基準は cc-crit の制約で、前から（スキルは PR の base が default branch でないときに伝える） |
| #12 | Medium | fetch が成功しても、同じ名前のタグや浅い clone で、正しい base を使うとは限らない | 採用しない（まれ。8 章の #10 と同じ） |
| #13 | Medium | 毎回の fetch が、submodule の再帰取得などの失敗と副作用を増やす | 一部を採用。`git fetch --no-recurse-submodules` にした（`/review` の H9 の submodule の経路も閉じる）。確認済みの SHA の再利用は採用しない |
| #14 | Medium | 先行コミットの対象がすでにコミット済みか、コミットに失敗した場合の分岐がない | D5 で起きなくなった |
| #15 | Medium | レビューの準備のコミットが、進行中のマージを確定させうる | D5 で起きなくなった |
| #16 | Low | Crit を使わない作業にも、表がブランチの Crit を求める読み方がある | 採用。SKILL_ROUTING.md の複雑の行を「`/crit-review <plan>` … PR を作るならブランチの差分の `/crit-review`」に、早見表を「完了前（ブランチの差分を `/crit-review` で開くなら、その前）」にした |
| #17 | Low | sync-skill-docs が、コミット済みの承認差分をもう一度コミットしようとする | D5 で起きなくなった |
| #18 | Low | commit-staged-pr の経路で challenge の要否を確かめない | 採用。「設計判断かセキュリティの境界を含むなら、表の challenge も一緒に提案する」を足した |
| #19 | Low | 不採用にした指摘まで直す必要があると読める | 採用。CLAUDE.md の Crit の項目を「その指摘の採否を決め、採用したものを直した後に開く」にした（行数は 79 のまま） |

後続の作業の候補（この PR では扱わない）: 8 章の #6（再ステージの後のシークレットの確認）、9 章の #2（Codex に見せてよいファイルだけの環境で動かす）。

<a name="checks-after-d5"></a>

## 10. D5 の後の確認

2026-11-26、D5 と 9 章の修正の後の作業ツリー（`86b9f44` に未コミットの修正）で実行した。

| 確かめること | 結果 |
| --- | --- |
| `grep -n "で開くときは、その前" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| `grep -n "完了前（\|完了する前。" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| 先にコミットする規則の文言（「先にコミットする」「先のコミットに残」「先行コミット」「Claude がコミットしてから」）が、変更した 4 ファイルに残っていない | 0 件 |
| `--uncommitted` が SKILL_ROUTING.md と早見表にある | `claude/rules/SKILL_ROUTING.md:50` と `claude/SKILL_CHEATSHEET.md:118` に当たった |
| commit-staged-pr の 49〜71 行目に「Crit に進む」が残っていない | 0 件 |
| `claude/CLAUDE.md` の実効行数 | 79 |
| 早見表の D 章（111〜118 行目）の列幅 | 曖昧幅を 1 と数えて、すべての行で `(16, 519, 51)` |
| `python3 -B .github/scripts/check-repo.py` | 16 項目すべて PASS（終了コード 0） |
| `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 警告なし（終了コード 0） |
| `actionlint` | 指摘なし（終了コード 0） |
| `zizmor --offline .` | No findings to report（終了コード 0） |

<a name="codex-4"></a>

## 11. Codex レビュー 4 回目（`codex review`）

D5 は新しい設計の変更なので、Crit の前にもう一度 `codex review` を実行してもらった（challenge は実行しない）。ブランチに base より先のコミットがあるので、D5 の規則のとおり先にコミットはせず、`git fetch origin main && codex review --base origin/main …` を渡した。修正はすべて追跡しているファイルなので、`--base` で読める。結果は 2026-11-26T06:34:57Z、コミット `86b9f44`（未コミットの D5 の修正を含む作業ツリー）。5 回の上限のうち 4 回目。

最終メッセージの判定は「patch is incorrect」（overall_confidence_score 0.95）。Codex 自身は `git diff --check`・ShellCheck・actionlint・zizmor を実行して通り、Codex から Crit までの流れは実行していないと書いている。

| 指摘 | 優先度 | 内容 | 採否と対応 |
| --- | --- | --- | --- |
| C4-1 | P1 | `--uncommitted` は未追跡のファイルも送るので、この作業で動作確認のために作った `.env` なども Codex に送られうる。今の確認は「この作業以外の変更」だけ | 採用。D5 で `--uncommitted` を入れたことでできた経路。SKILL_ROUTING.md の行を「Codex に送る範囲に、この作業以外の変更（未追跡のファイルも）か、この作業のものでも外部に送れない内容（`.env`・認証情報など）があれば…コマンドを渡す前に伝え」にした |
| C4-2 | P2 | Codex の指摘を直して再ステージした後、手順 2（シークレットの確認）を通らずに手順 4 でコミットする | 採用。8 章の #6 と同じ指摘で、2 回目。確認スキル・Codex・Crit から戻る 4 か所（commit-staged-pr の 70・71・72・75 行目）を「手順 2 の確認をして手順 4 でコミット」に揃えた。うち 3 か所は前からの書き方だが、同じ欠けなのでまとめて直した |
| C4-3 | P2 | 「受け入れて結果を待っている」も「提案する」の条件に入っていて、もう一度提案する | 採用。9 章の #8 の修正で、状態を 1 つの文にまとめたのが原因。提案は「まだ提案しておらず」のときだけにし、受け入れた後は「受け入れた回（challenge も含む）の結果がそろうか、ユーザーが残りを見送るまで Crit に進まない」と分けた |
| C4-4 | P2 | 早見表の B 章のコマンドの例が `--base` だけで、D 章の使い分けと合っていない | 採用。B 章の Codex の行を `--uncommitted` にし、先のコミットがあれば `--base <base>` と添えた。列幅は変わらず、変わったのは 90 行目だけ |

<a name="final-checks"></a>

## 12. 最終の確認

2026-11-26、11 章の修正の後の作業ツリー（`86b9f44` に未コミットの修正）で実行した。

| 確かめること | 結果 |
| --- | --- |
| `grep -n "で開くときは、その前" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| `grep -n "完了前（\|完了する前。" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | `claude/CLAUDE.md:98` と `claude/rules/SKILL_ROUTING.md:50` に当たった |
| 先にコミットする規則の文言（「先にコミットする」「先のコミットに残」「先行コミット」「Claude がコミットしてから」）が、変更した 4 ファイルに残っていない | 0 件 |
| `--uncommitted` が SKILL_ROUTING.md と早見表にある | `claude/rules/SKILL_ROUTING.md:50`、`claude/SKILL_CHEATSHEET.md:90`・`:118` に当たった |
| commit-staged-pr の 49〜71 行目に「Crit に進む」が残っていない | 0 件 |
| commit-staged-pr の再ステージからの戻り方が「手順 2 の確認をして手順 4 でコミット」になっている | 4 か所 |
| commit-staged-pr に「受け入れて結果を待っている」（提案の条件にまとめた書き方）が残っていない | 0 件 |
| `claude/CLAUDE.md` の実効行数 | 79 |
| 早見表の B 章（62〜91 行目）と D 章（111〜118 行目）の列幅 | 曖昧幅を 1 と数えて、B 章は `(21, 110, 161, 12)`、D 章は `(16, 519, 51)` で、それぞれすべての行で揃っている |
| `python3 -B .github/scripts/check-repo.py` | 16 項目すべて PASS（終了コード 0。この章を書いた後に実行） |
| `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 警告なし（終了コード 0） |
| `actionlint` | 指摘なし（終了コード 0） |
| `zizmor --offline .` | No findings to report（終了コード 0） |
