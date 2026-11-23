---
status: done
created: 2026-11-23
---

# 他人の PR のレビューを `/code-review` に分ける

他人の PR をレビューするときの手順を、CLAUDE.md・規則・スキルの文書に入れる。前のセッション（2026-11-23）で調べて決めた推奨に従う（人間が了承済み）。

関連: [SKILL_INVENTORY.md の「規則の効果の確認」](../../../claude/SKILL_INVENTORY.md#measurement)、[docs/work/20261116_skill-role-division/research-routing.md](../20261116_skill-role-division/research-routing.md)（「差分のレビューは `/review` に一本化」を決めた作業。完了しているので編集しない）

<a name="goal"></a>

## 目的

今の規則は「PR やブランチの差分のレビューには gstack の `/review`」だけを決めている。gstack の `/review` は PR 番号を受け付けず、今のブランチを見て直す前提で動くので、他人の PR に使うには共有の作業ツリーでチェックアウトする必要があり、しかも書き換える。他人の PR は、チェックアウトせずに組み込みの `/code-review <PR番号>` で読む、と決めて、4 つの文書で食い違わないようにする。

<a name="facts"></a>

## 確かめた事実

### 前のセッションで確かめたこと（Claude Code 2.1.330 の実行ファイルの文字列）

- 組み込みの `/code-review` は `aliases:["review"]` を持つ。`/review` と打つと gstack のスキル（`~/.claude/skills/review`）が優先される。
- `/code-review <PR番号>` は、差分を `gh pr diff <番号>` で読む（`pr diff` がない gh では `gh api repos/{owner}/{repo}/pulls/<番号>`）。指示文に「This checkout … must stay as it is」とあり、チェックアウトは変えない。手元のファイルは、PR で追加された行を含むときだけ参照に使う。`--fix` は、その行を含むファイルにだけ当たる。
- `gh pr diff` が失敗すると、`--fix`・`--comment` がなければ手元のブランチのレビューに切り替わり、報告の頭に「Could not read … This review is of the checked-out branch instead」と書く。`--fix` を付けたときと、URL で指定したときは止まる。
- sandbox の中で、公開の kado-ta/dotfiles の `gh pr diff 70 --name-only` は通った。private の業務リポジトリでは確かめていない。

### このセッションで確かめたこと（2026-11-23）

- gstack の `/review`（`~/.claude/skills/gstack/review/SKILL.md`）: base は今のブランチの `gh pr view` から決め、`git merge-base origin/<base> HEAD` からの差分を見る（222・235・277 行目）。「Fix-first, not read-only」（980 行目）。
- `/code-review ultra <PR番号>`: 文字列に「Ultrareview clones … in the cloud」「run /web-setup to reuse your GitHub CLI login」「GitHub isn't connected to your Claude account, so … can't be cloned in the cloud」がある。Claude Code のシステムプロンプトにも、ユーザーが起動して料金がかかること、引数なしでは手元のブランチを送ることが書いてある。
- `/verify` を続けて起動する条件（手順 1）。`/code-review` の指示文を作る関数 `Ci` は、次のすべてを満たすときだけ「After the review」の節を足す。
  1. 機能フラグ `tengu_opal_circuit` が on（関数 `RRs`。既定は false）。
  2. 提案の設定（proactivity）の判定（`Abl`）が通る。
  3. Skill ツールがある。
  4. Claude が起動できるスキルの一覧に、`verify` という名前のスキルがある。一覧の絞り込み（`KSe`）は、組み込み（`loadedFrom==="bundled"`）・個人・project などを数え、`disableModelInvocation` のものを除く。
- 節の文面は「`/verify` がこのセッションでまだ動いておらず、差分に実行時の振る舞いがある（テストや文書だけではない）なら、`/verify` を起動する」。
- 組み込みの `/verify` は `disableModelInvocation: () => !RRs()` で登録されている。同じフラグが on なら、組み込みのものだけで 4 を満たして続けて起動し、off なら、個人や project に `verify` があっても節は入らない。
- 今のセッションのスキルの一覧に `verify` はない。このアカウントでは今フラグが off と見ている（推測）。フラグはサーバー側で変わりうる。

<a name="decisions"></a>

## 決めたこと

Crit で承認したときの決定。`/review` の後に、振り分けの基準・PR の指定の形・worktree の手順を変えた（[/review で変えたこと](#review-changes)）。

- 自分の差分（今のブランチ）: 今のまま gstack の `/review`。
- 他人の PR: チェックアウトせずに `/code-review medium <PR番号>`。
  - `medium` を明示する。段階を省くと、ユーザーが前に打った段階を使い回し、`max` が残りうるため（`ultra` は保存されない。`/review` の後に直した）。
  - `--comment` は付けない。sandbox の `gh` は読み取り専用のトークンで 403 になり、CLAUDE.md も GitHub への書き込みを禁じている。
  - `--fix` は付けない。PR で追加された行を含む手元のファイルに、修正を当てることになる。
  - 報告の頭に「Could not read」とあれば、PR のレビューではないので、そう伝える。
- 変更されたファイルの全体を読ませたい大きな PR: 人間が `claude -w <name>` の worktree を作り、そこで PR を取り込んでから `/code-review <PR番号>` を実行する。共有の作業ツリーではブランチを切り替えない。private のリポジトリの fetch は sandbox の中では通らないので、人間が行う。

仮定: 「他人の PR」は、作者が自分でない PR を指す。自分の PR でチェックアウトしていないもの（別の作業ツリーのブランチなど）は、この変更では扱わない（そのブランチの作業ツリーで `/review` を使う）。

<a name="changes"></a>

## 変えるもの

| ファイル | 場所 | 変更 |
| --- | --- | --- |
| `claude/CLAUDE.md` | Tools 節の `/review` の行 | 自分の差分と他人の PR の 2 項目に分ける（下の文面） |
| `claude/rules/SKILL_ROUTING.md` | Overlapping skills の 32 行目 | 「自分の」を足し、他人の PR は CLAUDE.md の Tools 節を指す。内容は繰り返さない |
| `claude/SKILL_INVENTORY.md` | `requesting-code-review` の行（63）、`/code-review` の行（234）、組み込みの節の箇条（249）、重複と裁定の表（301）、計測の注記（370） | 上の事実と、確かめていないことを書く |
| `claude/SKILL_CHEATSHEET.md` | A の「コードレビュー」（45）、B の組み込み、C の使い分け、E の「この PR をレビューして」（131） | 自分の差分と他人の PR に分ける。表の桁は既存と同じ規則（東アジアの文字幅）でそろえる |
| メモリ | `skill-routing-merge-reminder.md`、`code-review-builtin-behavior.md` | 前者に変更日と内容を 1 行足す。後者に手順 1 の結果を書く |
| `claude/scripts/skill-usage.py`、`test-skill-usage.py` | レビューの重複の件数の下 | 重複のセッション ID を出す（`/review` の後に足した。D4） |

### `claude/CLAUDE.md`（Tools 節）

変更前:

```markdown
- PR やブランチの差分のレビュー依頼には gstack の `/review` を使う。Codex レビューの方針は「Cross-model review (Codex)」のとおりで、これを置き換えない。
```

変更後（目標の 80 行に対して 78 行 → 79 行）:

```markdown
- 自分の差分（今のブランチ）のレビューには gstack の `/review` を使う。Codex レビューの方針は「Cross-model review (Codex)」のとおりで、これを置き換えない。
- 他人の PR のレビュー依頼には、チェックアウトせずに `/code-review medium <PR番号>` を使う（gstack の `/review` は今のブランチを見て書き換える）。`--comment`・`--fix` は付けない。報告の頭に「Could not read」とあれば、PR ではなく手元のブランチのレビューなので、そう伝える。変更されたファイルの全体を読ませたい大きな PR は、人間に `claude -w` の worktree で PR を取り込んでもらい、そこで実行する。
```

### `claude/rules/SKILL_ROUTING.md`（32 行目）

```markdown
- 自分の差分のレビューは `/review` だけ（他人の PR は CLAUDE.md の Tools 節）。同じ差分に `/code-review` や `requesting-code-review` を重ねない。
```

### `claude/SKILL_INVENTORY.md`

- 63 行目（`requesting-code-review`）: 「差分のレビューは `/review` に一本化」を「自分の差分のレビューは `/review` に一本化」にする。
- 234 行目（`/code-review`）: 状態を「制限。自分の差分は `/review` に一本化。他人の PR は、チェックアウトせずに `/code-review medium <PR番号>` で読む（`--comment`・`--fix` は付けない。下の箇条）」にする。
- 249 行目の箇条を、次に置き換える（[確かめた事実](#facts)を、確かめた日と方法を付けて書く）。
  - `aliases:["review"]` と、gstack を消すか接頭辞を付けると `/review` が黙って `/code-review` になること。
  - gstack の `/review` と `/code-review <PR番号>` の、PR の扱いの違い。
  - `gh pr diff` が失敗したときの切り替わりと「Could not read」。
  - sandbox での確認の範囲（private は未確認）。
  - `--comment`・`--fix`・`medium` を決めた理由。
  - `ultra` の動きと料金。ユーザーが指定したときだけ使う。
  - 大きな PR の worktree の手順。
- 250 行目の前に `/verify` を続けて起動する条件の箇条を足す。内容は次のとおり。
  - 条件の 4 つ。
  - フラグが on になると、チェックアウトしていない PR のレビューの後に、PR ではなく手元のブランチを動かし、`.claude/skills/verify/SKILL.md` を書く見込み（推測。動かして確かめていない）。
  - 止めるなら `permissions.deny` の `Skill(verify)` が候補。モデルの起動だけを止め、ユーザーが打つ `/verify` は動く（2026-11-15 に別のスキルで確かめた）。この変更では入れない。
- 301 行目（重複と裁定の表）: 「差分のレビュー」を「差分のレビュー（自分のブランチ）」にし、「他人の PR のレビュー」の行を足す。
  - 主担当: `/code-review medium <PR番号>`（チェックアウトしない）。
  - 補完: 大きな PR は、人間が `claude -w` の worktree に取り込んでから `/code-review <PR番号>`。
  - 使わないもの: gstack の `/review`（チェックアウトして書き換える）、`--comment`・`--fix`。
- 370 行目（計測の注記）に足す。
  - 同じ日に、他人の PR のレビューを `/review` から `/code-review medium <PR番号>` に分けた（CLAUDE.md の Tools 節、SKILL_ROUTING.md の Overlapping skills）。
  - `skill-usage.py` は、1 つのセッションで 2 種類以上のレビューのスキル（`review`・`code-review`・`requesting-code-review`）が動くと重複に数える。この日の後は、自分の差分の `/review` と他人の PR の `/code-review` が同じセッションにあっても数えられる。
  - 重複に数えられたセッションは、`/code-review` の引数が PR 番号か（他人の PR か）を見て除く。

### `claude/SKILL_CHEATSHEET.md`

- A（45 行目）: 「コードレビュー」を「コードレビュー（自分の差分）」にし、次の行を足す。
  - タスク: 他人の PR のレビュー。
  - 主担当: `/code-review medium <PR番号>`（チェックアウトしない）。
  - 補完: 大きな PR は人間が `claude -w` の worktree に取り込む。
  - 使う条件: 指摘だけで、直さない。
  - 使わない場合: `--comment`・`--fix`、gstack の `/review`（チェックアウトして書き換える）。
- B: 組み込みに `/code-review medium <PR番号>` の行を足す（用途: 他人の PR を、チェックアウトせずにレビューする。起動: 自動）。
- C: 「gstack と pstack」の行の「差分のレビューは gstack の `/review`」を「自分の差分のレビューは gstack の `/review`」にする。「gstack `/review` と `/code-review`」の行を足す。
  - 使い分け: `/review` は今のブランチと merge-base の差分を見て直す（自分の差分）。`/code-review medium <PR番号>` はチェックアウトせずに PR の差分を読み、直さない（他人の PR）。`/review` と打つと gstack が起動する。
  - 併用: 同じ差分に重ねない。
- E（131 行目）: 「この PR をレビューして」を「（自分の PR）」にし、次の行を足す。
  - 依頼の例: 「#123 をレビューして」（他人の PR）。
  - 期待する選択: `/code-review medium 123`。チェックアウトしない。報告の頭に「Could not read」があれば、PR ではなく手元のブランチのレビューだと伝える。

<a name="review-changes"></a>

## /review で変えたこと

2026-11-23 に gstack の `/review` を実行した（Testing・Maintainability・Simplification・Red Team・adversarial のサブエージェント。Codex は、ユーザーの規則で Bash から実行しないので未実施）。判断が要る 4 件は、人間がすべて推奨の案を選んだ。

| # | 指摘 | 決めたこと |
| --- | --- | --- |
| D1 | 他人の PR を worktree に取り込むと、PR の `.claude/settings.json` の hooks・`.mcp.json`・`CLAUDE.md`・mise の設定が読み込まれ、hooks が sandbox の外で動きうる（CRITICAL） | 取り込む前に、Claude が head のコミットを控え、`gh pr diff <URL> --name-only` で設定ファイルが変わらないことを確かめる。変わるなら取り込まない。人間は控えたコミットを `pull/<番号>/head` から取り込み、`FETCH_HEAD` が同じかを確かめる |
| D2 | 危険を分けるのは作者ではなく、その PR が今のブランチかどうか。番号で渡すと、読めないときに手元のブランチを黙ってレビューし、別のリポジトリの PR では同じ番号の PR を読む | 今のブランチの差分は `/review`。それ以外の PR は作者を問わず `/code-review medium <PR の URL>`（URL なら読めないときに止まる）。`/review <番号>` で今のブランチ以外の PR を頼まれたら、止めて提案する |
| D3 | `/security-review`・`codex review`・`/pstack:interrogate` は今のブランチを見るので、他人の PR に重ねると、PR を見ずに問題なしと報告しうる | INVENTORY とチートシートに、今のブランチ以外の PR には使わないと書く（CLAUDE.md と SKILL_ROUTING は変えない） |
| D4 | 計測の注記の「`/code-review` の引数を見て除く」を、`skill-usage.py` の出力では実行できない。基準も、今のブランチの PR に重ねた本当の重複まで除く | `skill-usage.py` が重複のセッション ID を件数の下に出す（テストを先に書いた）。注記の基準を「対象がそのセッションのブランチの PR でなければ除く」に直す |

機械的に直したもの: worktree の手順と裁定の表に `medium` を付けた。`--fix` と `ultra` の理由の誤りを直した。`--comment` を付けると、差分が読めなくても手元のコードの指摘を投稿しに行くことを書いた。

<a name="non-goals"></a>

## 入れないもの

- `Skill(verify)` の deny や、`/verify` を止めるフック（提案に留める。今はフラグが off と見ているため）。
- `--comment` で PR にコメントを書く流れ（GitHub への書き込みは人間が行う）。
- worktree の作成や PR の取り込みの自動化（人間が行う）。
- docs/work/20261116_skill-role-division/ の編集（完了した作業文書）。

<a name="verification"></a>

## 検証

1. `python3 -B .github/scripts/check-repo.py`
2. `python3 -B .github/scripts/test-check-repo.py`
3. `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`
4. `actionlint`
5. 変えた Markdown の内部リンクの参照先があり、アンカー ID が一意であること（スクリプトで確かめる）。
6. CHEATSHEET の表を、整形のスクリプト（東アジアの文字幅）にかけても変わらないこと。
7. 4 つの文書を `review`・`code-review` で検索し、他人の PR の扱いが食い違う記述が残っていないこと。
8. `python3 -B claude/scripts/test-skill-usage.py`（D4 で足した）と `/usr/bin/python3 -B claude/scripts/skills-check.py check`。

<a name="done"></a>

## 完了条件

- CLAUDE.md・SKILL_ROUTING・INVENTORY・CHEATSHEET の 4 つで、他人の PR の扱いが食い違わない。
- 検証の 1〜8 がすべて通る。
- gstack の `/review` の指摘に対応し、`/crit-review` でブランチの差分が承認された。
- PR を作り、CI の結果を報告した（マージはしない）。

<a name="residual-risks"></a>

## 残る点

- private の業務リポジトリで、sandbox の中の `gh pr diff` が通るかは確かめていない。URL で渡すので、通らなければレビューせずに止まる。
- フラグ `tengu_opal_circuit` が on になると、`/code-review` の後に組み込みの `/verify` が続けて起動しうる。そのときの止め方は提案に留める（`/review` の adversarial も同じ点を挙げた）。
- 毎回読み込まれる SKILL_ROUTING は、高リスクなら `/security-review` と書いたまま。今のブランチ以外の PR には使わないことは、INVENTORY とチートシートにしか書いていない（D3 の範囲）。
- `/code-review` は既定で fork として、すべてのツールを持って動く。許可なしで実行できる `cc-safe-push`・`cc-safe-pr` も呼べるので、PR の差分に仕込まれた指示に従うと、ユーザーの名前で push や PR の作成ができる経路になる（adversarial の指摘。前からある種類の危険だが、他人の PR を読む機会が増える）。
- 非常に大きな PR では、GitHub の差分の上限で `gh pr diff` が失敗しうる（Red Team の推測。確かめていない）。
