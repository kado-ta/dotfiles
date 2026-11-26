---
status: done
created: 2026-11-26
---

# Codex レビューの提案を、ブランチの差分の Crit の前に出す

関連: [claude/CLAUDE.md](../../../claude/CLAUDE.md)、[claude/rules/SKILL_ROUTING.md](../../../claude/rules/SKILL_ROUTING.md)、[claude/SKILL_CHEATSHEET.md](../../../claude/SKILL_CHEATSHEET.md)、[claude/skills/commit-staged-pr/SKILL.md](../../../claude/skills/commit-staged-pr/SKILL.md)

<a name="goal"></a>

## 1. 目的と前提

Codex レビューの提案を、ブランチの差分を `/crit-review` で開く前に出す。Crit を、Codex の指摘を直した後の差分を人間が見る最後の関門にする。

前提（仮定）:

- 提案する条件（設計判断を含む変更・大規模変更・セキュリティ関連の変更）は変えない。変えるのは時期だけ。
- 対象はブランチの差分の Crit だけ。design / plan の承認の Crit（`/crit-review <file>`）は対象にしない。
- 提案を断られたら、そのまま Crit を開く。提案は 1 つのタスクで 1 回まで（`SKILL_ROUTING.md` の「提案は 1 つのタスクで 1 回まで」のとおり）なので、Crit の後にもう一度提案しない。

<a name="facts"></a>

## 2. 調べたこと（事実）

<a name="facts-current"></a>

### 2.1 今の記述

| 場所 | 記述 | 時期 |
| --- | --- | --- |
| `claude/CLAUDE.md:98`（Cross-model review） | 「完了前に Codex レビューを提案する」 | 曖昧（Crit との前後がない） |
| `claude/CLAUDE.md:115`（Tools の Crit） | 「AI のレビュー（`/review` など）をするときは、その指摘を直した後に開く」 | Codex を名指ししていない |
| `claude/rules/SKILL_ROUTING.md:25`（複雑） | 「… → `/review` → Codex レビューを提案する」 | 差分の Crit が並んでいない |
| `claude/rules/SKILL_ROUTING.md:50`（`codex review` の行） | 「複雑か高リスクの変更が完了する前」 | 曖昧 |
| `claude/SKILL_CHEATSHEET.md:115`（複雑な機能開発） | 「… → `/review` → Codex → `/crit-review` → PR」 | 既に Crit の前（人間向けの早見表だけ） |
| `claude/SKILL_CHEATSHEET.md:118`（独立レビュー） | 「`/review` の指摘を直した後に、ユーザーが…`codex review ...` を実行する」 | Crit との前後がない |
| `claude/skills/commit-staged-pr/SKILL.md:48-74`（手順 5） | 確認スキル → Crit。Codex に触れていない | — |
| `.claude/skills/sync-skill-docs/SKILL.md:43`（手順 12） | 差分を Crit で開き、承認されたらコミットと PR | Codex に触れていない |

Claude が従う規則（CLAUDE.md と SKILL_ROUTING.md）には、Crit より前という指定がない。Crit の承認の後は確認を挟まずに PR まで進める（2026-11-24 のユーザーの指示）ので、Crit の後に Codex を提案すると、Codex の指摘の修正が PR の作成後になる。

<a name="facts-codex"></a>

### 2.2 `codex review --base` が読む範囲

codex-cli 0.172.0 のバイナリにある `--base` の指示文は「The merge base commit for this comparison is {{merge_base_sha}}. Run `git diff {{merge_base_sha}}` to inspect the changes」。`git diff <merge-base>` は merge-base と作業ツリーを比べるので、コミット済みと未コミットの変更（ステージ済み・未ステージ）は入るが、未追跡のファイルは入らない。

Crit の差分（依頼ファイル `{}`）は未追跡のファイルも含む。今の一般の流れでは、コミットは Crit の承認の後なので、Crit の前に Codex を実行すると、新しく作ったファイル（スクリプト・テスト・作業文書）を Codex が見ない。

`SKILL_ROUTING.md` の Exit criteria のコマンドは、Codex の各回をコミットのハッシュ（`commit_hash[0:7]`）付きで出す。未コミットのまま実行すると、どの内容を見た回かを後から区別できない。

<a name="facts-limits"></a>

### 2.3 行数と追記の基準

- `claude/CLAUDE.md` の実効行数は 79（目標 80 以内）。既存の行の言い換えだけにし、行を増やさない。
- `SKILL_ROUTING.md` は試行中（2026-12-07 に効果を測る）。行は足さず、既存の行の言い換えにする。

<a name="decisions"></a>

## 3. 決めること

<a name="decision-commit"></a>

### D1. 未追跡のファイルを Codex に見せる方法

| 案 | 内容 | 評価 |
| --- | --- | --- |
| A（推奨） | Codex の提案が受け入れられたら、Claude が先にコミットしてからコマンドを渡す。断られたら今までどおり Crit の承認の後にコミットする | Codex が全体を見る。各回がコミットに結び付く。手元のコミットなので戻せる。コミットの時期だけが今の習慣と変わる |
| B | 未追跡のファイルを `git add -N`（intent-to-add）にしてから渡す | コミットしないが、index を変える。`/commit-staged-pr` ではステージがユーザーの意図なので使えない |
| C | 未追跡のファイルがあれば、Codex が見ないと伝えるだけ | 最小だが、伝え忘れると Codex が黙って一部しか見ない |

A を推奨する。受け入れの返事を、コミットの許可として扱う（提案の文面で「先にコミットする」と伝える）。

> [!NOTE]
> D1 は、Codex の challenge の指摘（先のコミットに秘密情報が残る、コミットできないときの進み方がない、など）を受けて、2026-11-26 にユーザーが D5 に変えた。先にコミットはせず、ブランチに base より先のコミットがなければ `codex review --uncommitted` を使う（[test-report の 9 章](test-report.md#codex-3)）。

<a name="decision-skills"></a>

### D2. スキルの手順への反映

- `commit-staged-pr`: 手順 5 が「push の前に確認する」中身を確認スキルと Crit だけで書いているので、Codex がないと読まれる見込みが高い。確認スキルの後、Crit の前に Codex の項目を足す（推奨）。この手順はコミット（手順 4）の後なので D1 のコミットは要らない。ただし `git diff <merge-base>` は未ステージの変更も含むので、未ステージの変更があれば PR に入らない変更も Codex が見ると添える（`/cso --diff` の注意と同じ）。
- `sync-skill-docs`: 変えない。スキルと文書の同期で、Codex の条件にほぼ当たらない。当たるときは CLAUDE.md の規則が効く。

<a name="decision-hook"></a>

### D3. フックで強制するか

しない。Codex の条件（設計判断・大規模・セキュリティ）は判断で、`cc-crit review` の直前のフックでは、提案したかどうかも、条件に当たるかどうかも確かめられない。文章で決める。

<a name="changes"></a>

## 4. 変更

承認の後、`/review` の指摘で文面を変えた（「完了前」を残す、commit-staged-pr の移り先など）。下の 4.1〜4.4 は承認したときの案のままにしている。変えた理由は test-report の [3 章](test-report.md#review-1)・[4 章](test-report.md#review-2)・[5 章](test-report.md#review-3)（`/review`）と [7〜9 章](test-report.md#codex-1)・[11 章](test-report.md#codex-4)（Codex）に、最終の文面はコミットの差分にある。

<a name="change-claude-md"></a>

### 4.1 `claude/CLAUDE.md`（2 行の言い換え。行数は 79 のまま）

98 行目:

```diff
-- Codex はレビュワーとして使う。設計判断を含む変更、大規模変更、セキュリティ関連の変更では、完了前に Codex レビューを提案する。
+- Codex はレビュワーとして使う。設計判断を含む変更、大規模変更、セキュリティ関連の変更では、ブランチの差分を `/crit-review` で開く前に Codex レビューを提案する。
```

115 行目（Codex を名指しする）:

```diff
-  - PR を作るときは毎回、…どちらもしない。AI のレビュー（`/review` など）をするときは、その指摘を直した後に開く。
+  - PR を作るときは毎回、…どちらもしない。AI のレビュー（`/review`・Codex など）をするときは、その指摘を直した後に開く。
```

<a name="change-skill-routing"></a>

### 4.2 `claude/rules/SKILL_ROUTING.md`（2 行の言い換え）

25 行目（複雑）:

```diff
-| 複雑 | `brainstorming` → `writing-plans` → `/crit-review` → 実装 → `/review` → Codex レビューを提案する |
+| 複雑 | `brainstorming` → `writing-plans` → `/crit-review` → 実装 → `/review` → Codex レビューを提案する → ブランチの差分の `/crit-review` |
```

50 行目（`codex review` の提案する場面。D1 の A をここに書く）:

```diff
-| … | 複雑か高リスクの変更が完了する前（Bash からは実行しない。`!` では失敗することがある） |
+| … | 複雑か高リスクの変更で、ブランチの差分を `/crit-review` で開く前（Bash からは実行しない。`!` では失敗することがある）。`--base` は `git diff <merge-base>` を読み、未追跡のファイルを見ないので、受け入れられたら先にコミットしてからコマンドを渡す |
```

<a name="change-cheatsheet"></a>

### 4.3 `claude/SKILL_CHEATSHEET.md`（1 行の言い換え）

118 行目（独立レビュー）の先頭を「`/review` の指摘を直した後、ブランチの差分を `/crit-review` で開く前に、Claude がコミットしてから、ユーザーが通常のターミナルで `codex review ...` を実行する」にする。表の列の幅（全角を 2 として数える）を揃え直す。115 行目は既に Crit の前なので変えない。

<a name="change-commit-staged-pr"></a>

### 4.4 `claude/skills/commit-staged-pr/SKILL.md`（D2）

- 8 行目の「push の前に、確認スキルの提案と、Crit での人間のレビューを行う」を「push の前に、確認スキルと Codex レビューの提案と、Crit での人間のレビューを行う」にする。
- 手順 5 の確認スキルの項目と Crit の項目のあいだに、次の項目を足す。

```markdown
   - **Codex**: 手順 4 でコミットした差分がグローバルの CLAUDE.md の Cross-model review (Codex) の条件に当たるときは、確認スキルの後、Crit の前に Codex レビューを提案する。コマンドは `~/.claude/rules/SKILL_ROUTING.md` の表のもので、`--base` には PR の base を渡す。`--base` は merge-base から作業ツリーまでを読むので、未ステージの変更があれば、PR に入らない変更も Codex が見ると添える。指摘の採否を整理して直すときは、確認スキルと同じく、ステージはユーザーに任せ、ステージし直したと連絡を受けてから手順 4 でコミットし、Crit に進む。
```

<a name="non-goals"></a>

## 5. やらないこと

- Codex を提案する条件の変更。`CLAUDE.md`（設計判断・大規模・セキュリティ）と `SKILL_ROUTING.md`（複雑か高リスク）で書き方が違うが、この作業では揃えない（[7 章](#discrepancies)）。
- フックでの強制（D3）。
- `sync-skill-docs` の変更（D2）。
- `SKILL_CHEATSHEET.md` の利用例（E 章）の書き換え。Codex の後の Crit を書いていないが、規模別の構成（D 章）が順序を示している。

<a name="verification"></a>

## 6. 完了条件と検証

| 確かめること | コマンド | 期待する結果 |
| --- | --- | --- |
| Crit より前という指定が、Claude が従う規則にある | `grep -n "で開くときは、その前" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md`（`/review` の F2 で文面が変わったので grep も変えた） | CLAUDE.md の Cross-model と SKILL_ROUTING.md の 50 行目に当たる |
| Crit を開かない作業でも提案の時期がある（`/review` の F2 で変えた） | `grep -n "完了前（\|完了する前。" claude/CLAUDE.md claude/rules/SKILL_ROUTING.md` | CLAUDE.md の Cross-model と SKILL_ROUTING.md の 50 行目に当たる |
| `claude/CLAUDE.md` の実効行数 | 前の作業の plan の 4 章と同じ Python のコマンド | 79 |
| 早見表の D 章の列が揃っている | 列の幅を全角 2 で数える確認用のスクリプト（scratchpad） | すべての行で各列の幅が同じ |
| リポジトリの検査 | `python3 -B .github/scripts/check-repo.py` | 失敗なし |
| 検査のテスト | `python3 -B .github/scripts/test-check-repo.py` | 失敗なし |
| シェルスクリプト | `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 警告なし |
| GitHub Actions | `actionlint`、`zizmor --offline .` | 指摘なし |

フック・ラッパー・スクリプトは変えないので、フックの回帰テストは実行しない。PR の前に `/review` を実行し、指摘を直した後にブランチの差分を `/crit-review` で開く。この変更は設計判断を含むので、Crit の前に Codex レビューを提案する（この変更の規則に従う）。

<a name="discrepancies"></a>

## 7. 見つけた食い違い

- Codex を提案する条件が、`CLAUDE.md:98` は「設計判断を含む変更、大規模変更、セキュリティ関連の変更」、`SKILL_ROUTING.md:50` は「複雑か高リスク」。重なるが同じではない（例: 高リスクだが小さく設計判断のない変更）。揃えるかは別の作業で決める。
- `SKILL_CHEATSHEET.md:115`（人間向け）は既に Codex を Crit の前に置いているが、Claude が従う規則にはその指定がない。この作業で揃う。
