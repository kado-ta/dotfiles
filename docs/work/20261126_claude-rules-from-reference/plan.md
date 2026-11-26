---
status: in-progress
created: 2026-11-26
---

# 参考にした dotfiles の規則 4 つを Claude 向けの規則に取り込む

関連: [claude/CLAUDE.md](../../../claude/CLAUDE.md)、[claude/rules/SKILL_ROUTING.md](../../../claude/rules/SKILL_ROUTING.md)、[codex/AGENTS.md](../../../codex/AGENTS.md)

参考元の CLAUDE.md には LICENSE がないので、文面は写さず、このリポジトリの文体で書き直す。

<a name="decision"></a>

## 1. 決めたこと

2026-11-26 に、ユーザーが次のように決めた。

| 候補 | 決定 | 置き場所 |
| --- | --- | --- |
| 1. subagent の使い方（数回のツール呼び出しで済む作業は委譲しない、自分の作業の検証を subagent にさせない） | 入れない | — |
| 2. レビューの頼み方（「重大な指摘だけ」などと絞って頼まない。全件を出させ、絞り込みは別に行う） | 形を変えて入れる | `claude/rules/SKILL_ROUTING.md` の challenge の行に一句足す |
| 3. 空の応答（ツールや subagent の応答が空か壊れているとき、推測で埋めない） | 形を変えて入れる | `claude/CLAUDE.md` と `codex/AGENTS.md` の Verification の 2 つ目の項目を言い換える |
| 4. 完了の報告（ターンの末尾に「成果物」「要判断」「残タスク」を置く） | 入れる。3 つとも置く | `claude/CLAUDE.md` の Completion report の前置きを言い換える。Codex はレビューにだけ使い、対話では使わないので、`codex/AGENTS.md` には入れない |
| 関連: `codex/AGENTS.md` の「重大な指摘がなければ「指摘なし」」 | 「指摘がなければ」に変える | `codex/AGENTS.md` の Reviewing for Claude Code |

<a name="facts"></a>

## 2. 調べたこと（事実）

<a name="facts-builtin"></a>

### 2.1 Claude Code に元からある指示（v2.1.331）

- Agent ツールの説明に「Do the work yourself when it is a handful of tool calls ...; don't delegate a check you could run inline.」「Delegate review only when you want a read that isn't anchored on yours」「When in doubt, don't spawn.」がある。候補 1 の前半と同じ。後半（検証を委譲しない）は「don't delegate a check you could run inline」と重なる。独立した読みが欲しいときのレビューの委譲は、元からある指示が認めている（この作業の `/review` もその使い方）。
- Agent ツールの説明に「Never fabricate or predict a pending agent's results」がある。対象はまだ届いていない結果だけで、空か壊れた応答と、ツールの空の出力には触れていない（候補 3 は一部だけ重なる）。
- レビューの頼み方（候補 2）と、ターンの末尾の形（候補 4）に当たる記述はない。候補 2 とは逆に、絞る向きの記述がある（システムプロンプトの「give a recommendation, not an exhaustive survey」と、Agent ツールの説明の「keep the scope explicit and narrow」）。

<a name="facts-existing"></a>

### 2.2 既存の規則との重なり

- 候補 1: `SKILL_ROUTING.md` の「同じ差分に `/code-review` や `requesting-code-review` を重ねない」が、レビューの重ねがけを止めている。`SKILL_ROUTING.md` はスキルを選ぶ規則なので、subagent の使い方は範囲の外。
- 候補 2: 絞り込みを別に行う側は、`CLAUDE.md` の Cross-model review（採用/不採用と理由を整理する）と、`SKILL_ROUTING.md` の Exit criteria（1 回ずつ記録してから採否を整理する）にある。Claude が依頼の文面を書くのは、主に Codex の challenge のプロンプト。`/code-review medium` はユーザーが選んだ水準なので、対象にしない。
- 候補 3: `CLAUDE.md` の Verification の「実行していない検証を成功扱いしない」は検証だけが対象。`SKILL_ROUTING.md` の Exit criteria に、Codex の記録が空のときの個別の対処がある。
- 候補 4: Completion report は「完了時」だけが対象で、承認待ちや中断したターンには効かない。要判断と残タスクの欄もない。
- `codex/AGENTS.md` の Verification と Completion report は、`claude/CLAUDE.md` と同じ文。Reviewing for Claude Code の「重大な指摘がなければ「指摘なし」と明記する」は、軽い指摘を出さなくてよいとも読め、候補 2 と逆向き。

<a name="facts-criteria"></a>

### 2.3 行数と追記の基準

- `claude/CLAUDE.md` の冒頭の HTML コメントの目標は「非HTMLコメント・非空行で 80 行以内」。2026-11-26 の時点（9b81ce7）で 79 行。数え方は [4 章](#verification) のコマンド。どの変更も既存の行の言い換えで、行は増やさない。`check-repo.py` は行数を検査していない。
- 同じコメントの追記の基準は「同じ指摘を 2 回したら追記」。4 つとも、ユーザーが Claude に繰り返した指摘ではないので、基準には当たらない。候補 2 と 3 は、起きても人間から見えない失敗（絞られて消えた指摘、推測で埋めた結果）なので、繰り返しの指摘として現れない。そのため、行を増やさない形で入れる。候補 4 は、ユーザーが並行セッション（herdr）のために必要を明示した。
- `SKILL_ROUTING.md` は試行中で、2026-12-07 に効果を測る。行を足すのは具体的な誤ルーティングのときだけ、という方針がある。候補 2 は既存の行に一句足すだけで、ルーティングは変えない。

<a name="changes"></a>

## 3. 変更

<a name="change-verification"></a>

### 3.1 空の応答（`claude/CLAUDE.md` 68 行、`codex/AGENTS.md` 58 行）

両方を同じ文にする。

変更前:

```text
- 実行していない検証を成功扱いしない。実行できなかった場合は理由と未検証範囲を明記する。
```

変更後:

```text
- 実行していない検証を成功扱いしない。ツールやサブエージェントの応答が空か壊れているときは、推測で補わずに環境の障害として書き、再実行か自分での実行で実際の出力を得る。実行できなかった場合や出力を得られなかった場合は、理由と未検証範囲を明記する。
```

<a name="change-report"></a>

### 3.2 ターンの末尾（`claude/CLAUDE.md` 124 行）

変更前:

```text
完了時は次を簡潔に報告する（軽微な変更は 1〜2 行で可）:
```

変更後:

```text
調査・実装を伴うターンは、完了・承認待ち・中断のどれでも、末尾に「成果物」（PR の URL・変えたファイル・生成物と、確かめた時点の状態）と「要判断」（なければ「なし」）を置き、残りの作業があれば「残タスク」（次にやること・待っている相手と内容）を添える。並行するセッションから戻って末尾だけ読めば追えるようにするため。完了時はその前に次を簡潔に報告する（軽微な変更は 1〜2 行で可）:
```

`codex/AGENTS.md` の Completion report は変えない。2 つのファイルの Completion report の前置きは、ここから違う文になる。

<a name="change-challenge"></a>

### 3.3 レビューの頼み方（`claude/rules/SKILL_ROUTING.md` 51 行）

challenge の行の「変更前と比べた後退や、壊れる入力を具体的に挙げるよう頼む。」の後に、次の一文を足す。

```text
重大なものだけ、などと絞らずに全件を挙げてもらう。
```

`claude/SKILL_CHEATSHEET.md` の 91 行（人向けの要約）は変えない。頼む内容の要約で、頼み方の細部までは書いていないため。

<a name="change-reviewer"></a>

### 3.4 Codex のレビューの出力（`codex/AGENTS.md` 148 行）

変更前:

```text
- 確認できない Claude Code の作業状態や検証結果を推測で断定しない。重大な指摘がなければ「指摘なし」と明記する。
```

変更後:

```text
- 確認できない Claude Code の作業状態や検証結果を推測で断定しない。指摘がなければ「指摘なし」と明記する。
```

<a name="verification"></a>

## 4. 検証

| 確かめること | コマンド | 期待する結果 |
| --- | --- | --- |
| `claude/CLAUDE.md` の実効行数 | `python3 -c 'import re,sys; s=re.sub(r"<!--.*?-->","",open(sys.argv[1],encoding="utf-8").read(),flags=re.S); print(sum(1 for l in s.splitlines() if l.strip()))' claude/CLAUDE.md` | 79（80 以内） |
| リポジトリの検査 | `python3 -B .github/scripts/check-repo.py` | 失敗なし |
| 検査のテスト | `python3 -B .github/scripts/test-check-repo.py` | 失敗なし |
| シェルスクリプト | `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 警告なし |
| GitHub Actions | `actionlint`、`zizmor --offline .` | 指摘なし |

フックとラッパーは変えないので、フックの回帰テストは実行しない。

<a name="commits"></a>

## 5. コミットと PR

1 つの論理変更を 1 コミットにする。

1. `docs: plan adopting four rules from a reference dotfiles`（この plan）
2. `docs(claude): treat empty or broken tool output as an environment failure`（3.1）
3. `docs(claude): end investigation and implementation turns with deliverables and decisions`（3.2）
4. `docs(claude): ask the Codex challenge for every finding`（3.3）
5. `docs(codex): report minor findings in reviews for Claude Code`（3.4）
6. `docs: record the checks for the reference rules work`（4 章の結果を `test-report.md` に書き、この plan の `status` を変える）

PR の前に `/review` を実行し、指摘を直してから `/crit-review` でブランチの差分を開く。承認の後に `cc-safe-push` と `cc-safe-pr create` を実行し、`gh pr checks` で CI を確かめる。マージはユーザーが行う。

<a name="rejected"></a>

## 6. 採らなかった案

- 候補 1 を `CLAUDE.md` か `SKILL_ROUTING.md` に入れる。元からある指示とほぼ同じで、`CLAUDE.md` に 1 行足すと上限の 80 行に達し、ほかの追記の余地がなくなる。元からある指示が版で変わって、委譲しすぎが 2 回あれば入れ直す。
- 候補 4 を Stop フックで強制する。`INSTRUCTION_PLACEMENT.md` では「毎回 Y」はフックで強制する対象だが、軽い質問のターンを見分けにくく、止めるたびに書き直しの生成が増える。文章で守られないことが 2 回あれば、フックを検討する。
- 候補 2 を subagent へのレビューの依頼にも広げる。Claude がレビューを subagent に頼む経路は、元からある指示とスキルの規則で少ないので、今は challenge の行だけにする。
