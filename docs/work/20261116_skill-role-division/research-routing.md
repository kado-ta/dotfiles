---
status: done
created: 2026-11-16
---

# 重複したスキルの裁定と、参考表の再評価

[plan](plan.md) の手順 1。依頼の 2.2 節（重複・競合の分析）と 3 節（参考表の再評価）に答える。事実は各スキルの SKILL.md・設定・トランスクリプトで確かめた。推測には「推測」と書く。

## 関連

- [plan](plan.md)、[規則の案](design.md)
- [前の作業の調査メモ](../20261114_pstack-skill-routing/research-skill-inventory.md#overlaps)（7 節を引き継ぐ）

<a name="pairs"></a>

## 1. 重複 8 組の裁定

<a name="pair-1"></a>

### 1-1. superpowers と pstack（TDD・デバッグ・実装計画）

| 項目 | 内容 |
| --- | --- |
| 主担当 | superpowers（`test-driven-development`、`systematic-debugging`、`writing-plans`） |
| 代替手段 | pstack の `tdd`（方針で使わない）。デバッグの手順を持つ pstack のスキルはない |
| 補完役割 | `/pstack:how`・`/pstack:why`（原因がよく知らない領域や設計の意図に関わるとき）、`/pstack:architect with checkpoint`（設計の案を比べたいとき） |
| 併用条件 | 複雑か高リスクで、superpowers の計画に、設計案の比較や影響の確認を足すとき |
| 併用しない条件 | 同じ設計の判断に `brainstorming` と `architect` の両方を使わない。軽微な変更ではどちらも使わない |
| 優先順位 | superpowers が先（Claude が自分で起動できる）。pstack はユーザーへの提案 |

理由: superpowers はモデルから起動でき、TDD とデバッグの手順が具体的。pstack の 57 件は Claude から起動できないので、主担当にすると Claude が手順を真似ることになり、公式ドキュメントの指示に反する。

<a name="pair-2"></a>

### 1-2. superpowers と gstack（計画・実装のワークフロー）

| 項目 | 内容 |
| --- | --- |
| 主担当 | superpowers（計画と実装）。gstack は「何を作るか」の `/office-hours` と、レビュー・QA |
| 代替手段 | gstack の `/spec`（明示だけ。Issue 作成が止まる）、`/autoplan`（無効） |
| 補完役割 | `/office-hours`（作るかどうか自体が未定のとき）、`/plan-ceo-review`（スコープを見直したいとき） |
| 併用条件 | プロダクトの判断（`/office-hours`）の後に、機能の設計（`brainstorming`） |
| 併用しない条件 | 同じ要件に `/office-hours` と `brainstorming` を重ねない |
| 優先順位 | 機能の要件と設計は `brainstorming`、何を作るかは `/office-hours` |

理由: gstack の有効なスキルに、実装のワークフローはない（`/ship`・`/autoplan` は無効）。`/office-hours` は設計文書だけを書く（HARD GATE）ので、粒度が違う。

<a name="pair-3"></a>

### 1-3. gstack と pstack（技術設計）

| 項目 | 内容 |
| --- | --- |
| 主担当 | superpowers の `writing-plans` と `/crit-review`（人間の承認） |
| 代替手段 | gstack の `/plan-ceo-review`（1 節目がアーキテクチャ。ただし CEO の観点が中心） |
| 補完役割 | `/pstack:architect with checkpoint`、`/pstack:blast-radius` |
| 併用条件 | 複雑か高リスクで、設計の案が複数あるとき |
| 併用しない条件 | `/pstack:architect` を「with checkpoint」なしで使わない（確認なしで実装に進む） |
| 優先順位 | `writing-plans` → `/crit-review`。pstack は提案 |

理由: gstack の技術設計のレビュー（`/plan-eng-review`）は廃止され、`/autoplan` の段に移った（CHANGELOG:「`/plan-eng-review` is cut」）。`/autoplan` は無効。参考表の「補完: gstack `autoplan`」は前提が合わない。

<a name="pair-4"></a>

### 1-4. gstack と pstack（コードレビュー）

| 項目 | 内容 |
| --- | --- |
| 主担当 | gstack の `/review`（CLAUDE.md の Tools 節が指定） |
| 代替手段 | 組み込みの `/code-review`、superpowers の `requesting-code-review`（どちらも同じ差分には重ねない） |
| 補完役割 | `/pstack:interrogate`（実行で示した指摘だけを残す。直さない） |
| 併用条件 | 高リスクで、`/review` の後に、実行で確かめられる不変条件（権限の境界、データの整合性など）が残るとき |
| 併用しない条件 | 通常の PR。`interrogate` は worktree を使い、サブエージェントが 2 つ以上で重い |
| 優先順位 | `/review` → （高リスクなら）`/pstack:interrogate` |

理由: `/review` は専門家のサブエージェントを差分の大きさに応じて起動し、自動で直す（「Fix-first, not read-only」）。`interrogate` は直さず、証明できた指摘だけを返すので、役割が違う。

<a name="pair-5"></a>

### 1-5. understand-anything と pstack（コードの理解）

| 項目 | 内容 |
| --- | --- |
| 主担当 | 通常の読解（Explore を含む） |
| 代替手段 | — |
| 補完役割 | `/pstack:how`（1 つの領域を 1 回説明する）、`/understand-anything:understand`（リポジトリ全体のグラフ。何度も使う） |
| 併用条件 | 大きいリポジトリを続けて理解するときは understand-anything でグラフを作り、以後は `understand-chat`・`understand-explain` |
| 併用しない条件 | 同じ質問に `how` と `understand-chat` の両方は使わない。1 回だけの調査で `/understand-anything:understand` を使わない |
| 優先順位 | 通常の読解 → グラフがあれば `understand-chat` → `how` の提案 |

理由: `/understand-anything:understand` は多くのエージェントを起動し（`file-analyzer` は最大 5 並列）、`.ua/` を作る。`.gitignore` には入らない。ダッシュボードは localhost で待ち受けるので sandbox では動かない。ユーザーは `understand-chat` をよく使っている（2026-10-27〜11-16 に 5 回入力）。

<a name="pair-6"></a>

### 1-6. crit とほかの計画レビュー

| 項目 | 内容 |
| --- | --- |
| 主担当 | `/crit-review`（人間の承認。CLAUDE.md が必須と定めている） |
| 代替手段 | crit プラグインの `/crit:crit`（sandbox では動かない）、Plan Mode の plan-hook（Plan Mode のときだけ） |
| 補完役割 | AI の計画レビュー（`/plan-ceo-review`、`/plan-design-review`） |
| 併用条件 | スコープやデザインに迷いがあるとき、AI のレビューを先に済ませてから `/crit-review` |
| 併用しない条件 | plan-hook で開いた plan を `/crit-review` でもう一度開かない |
| 優先順位 | `/crit-review` は置き換えない。AI のレビューは任意 |

<a name="pair-7"></a>

### 1-7. gstack `/codex` と pstack `interrogate`

| 項目 | 内容 |
| --- | --- |
| 主担当 | 独立したモデルのレビューは Codex。ユーザーが `!` で `codex review` を実行する |
| 代替手段 | gstack の `/codex`（Bash から `codex exec` を呼ぶので、auto モードの判定で拒否された記録がある。2026-11-11） |
| 補完役割 | `/pstack:interrogate`（Claude 同士。実行で示す） |
| 併用条件 | 高リスクで、別のモデルの視点（Codex）と、実行による証明（`interrogate`）の両方がほしいとき |
| 併用しない条件 | `interrogate` を独立したレビューの代わりにしない |
| 優先順位 | Codex（複雑・高リスクでは提案。1 PR あたり 5 回まで）→ 必要なら `interrogate` |

注: Claude は gstack の `codex` を 2026-10-27〜11-16 に 10 セッションで 12 回起動した。拒否されたか成功したかは集計していない（推測では、多くが拒否か確認待ち）。

<a name="pair-8"></a>

### 1-8. gstack と pstack（PR・リリース）

| 項目 | 内容 |
| --- | --- |
| 主担当 | CLAUDE.md の Git 節（cc-safe-push・cc-safe-pr）と、個人スキル `/commit-staged-pr` |
| 代替手段 | gstack の `/ship`・`/land-and-deploy`（無効）、superpowers の `finishing-a-development-branch` の push と PR（使わない）、pstack の `poteto-mode`（`gh pr create`・`gh pr merge`・`git push` を使う。方針で使わない） |
| 補完役割 | `/crit-review`（push と PR の前に必須） |
| 併用条件 | — |
| 併用しない条件 | `/document-release`・`/document-generate` は commit と `git push` をするので、明示だけにした（`user-invocable-only`） |
| 優先順位 | CLAUDE.md の Git 節が、どのスキルの手順より優先する |

<a name="reference-table"></a>

## 2. 参考表の再評価

依頼の 3 節の 7 つの観点で見た。表の「変更後」は [plan](plan.md#reference-table) と同じ。

| 観点 | 結果 |
| --- | --- |
| 1. 実装に合っているか | 合わない行が 5 つ。`/ship`・`/autoplan` は無効、`/codex` は Bash から拒否される、`/cso` は保存先に書けない、pstack は Claude から起動できない |
| 2. 主担当は最適か | 「コードベースの可視化」の主担当を通常の読解に、「技術設計」を `writing-plans` と `/crit-review` に変えた |
| 3. ほかのスキルの方がよいか | 「セキュリティ監査」は `/security-review`、「PR 作成」は CLAUDE.md の Git 節と `/commit-staged-pr` |
| 4. 重複を減らせるか | 差分のレビューを `/review` に一本化した（`/code-review`・`requesting-code-review` を重ねない） |
| 5. pstack の価値を活かせるか | 規則に、提案する場面を書いた。書かないと、説明文が見えないので Claude は提案できない |
| 6. 自動起動と競合しないか | superpowers の「1% ルール」と、規則の「使わない」原則がぶつかる。superpowers 自身がユーザーの指示を優先すると書いているので、規則を優先した |
| 7. スキルを使わない方がよいタスク | 軽微な修正、1 つの関数・ファイルの質問、文書や設定の小さな変更、公式ドキュメントで答えが決まる調査 |

<a name="other-findings"></a>

## 3. ほかに分かったこと

- **gstack の `verify` が多く起動している。** Claude は 2026-10-27〜11-16 に 35 セッションで 65 回起動した。理由と対応の選択肢は [次の節](#verify)。今回は変えない。
- **レビューの重複は、規則の前から 0 だった。** 同じセッションで 2 つ以上のレビュー系のスキルを使った回数は 0。規則の効果は「0 のまま」で見る。
- **pstack の `/pstack:` を含む Claude の発言は 8 回あった。** ほぼこの作業と前の作業のセッションで、スキルの名前を書いた分と見られる（推測）。
- **前の作業の調査メモの誤り。** understand-anything の保存先の既定は `.ua/` で、`.understand-anything/` があるときだけそちらを使う（hook のコマンドで確認）。前のメモには `.understand-anything/config.json` と書いた。

<a name="verify"></a>

## 4. 組み込みの `/verify` と gstack の `verify`

出典は公式ドキュメントの [Skills](https://code.claude.com/docs/en/skills.md)（「Run and verify your app」「Run your checks before each commit」「Resolve skills that share a name」）と [Settings reference](https://code.claude.com/docs/en/settings-reference.md)（`disableBundledSkills`・`includeGitInstructions`・`skillOverrides`）。調査役のエージェントが読んで引用したものを使った。

<a name="verify-difference"></a>

### 違い

| 項目 | 組み込みの `/verify` | gstack の `verify` |
| --- | --- | --- |
| 目的 | アプリをビルドして起動し、変更が意図どおり動くかを確かめる。テストや型チェックには頼らない（「Build and run your app to confirm a code change does what it should, without falling back to tests or type checks」） | リポジトリが宣言した検査（型チェック・lint・build など）とテストを、通るまで直しながら回す |
| 何を実行するか | アプリのビルドと起動。手順が分からないときは、成功した手順を `.claude/skills/verify/SKILL.md` に記録する | `CLAUDE.md` の `gstack:verify:` 行、`package.json` の scripts などから探した検査。宣言がなければ何もしない |
| ファイルの変更 | 手順の記録ファイルだけ（commit するかは文書に記載なし） | 失敗すればコードを直す。テストや設定を弱めることは禁止、5 回で打ち切り |
| 大きさ | — | SKILL.md が 213 行、約 11 KB。起動のたびにコンテキストに入る |
| この環境での状態 | 隠れている。同じ名前のユーザーのスキルがあると、ユーザーの方が組み込みを置き換える | 有効（Claude が起動できる） |

<a name="verify-trigger"></a>

### commit の前に起動される理由

公式ドキュメントによると、セッションの開始時に `verify` か `simplify` という名前のスキルがあると、Claude Code の commit の指示に「commit の直前にそれを実行する（文書とテストだけの変更を除く）」が入る（v2.1.286 以降）。数えるのは、ユーザー・プロジェクト・enterprise の場所にあるスキルで、Claude が起動できるものだけ。組み込みの `/verify` と `/simplify`、プラグインのスキルは数えない。

この環境では、gstack の `verify` が `~/.claude/skills/verify` にある（ユーザーのスキル）。このため、Bash ツールの説明に「Always run `/verify` right before the `commit` command」が入り、65 回の起動につながったと考えられる（文書の条件からの推測。ほぼ確実）。指しているのは gstack の版で、組み込みの版ではない。

<a name="verify-options"></a>

### 対応の選択肢（判断はユーザー）

| 案 | やること | 効果 | 欠点 |
| --- | --- | --- | --- |
| A. そのまま | 何もしない | 検査を宣言したリポジトリでは、commit の前に検査が回る | 宣言のないリポジトリ（dotfiles など）でも毎回 11 KB を読み込み、何もしない。CLAUDE.md の Verification 節（テスト・lint などを実行する）と役割が重なる |
| B. `skillOverrides` で `"verify": "user-invocable-only"` | settings に 1 行足す | Claude が起動できなくなるので、commit の前の指示が出なくなる（文書の条件から推測）。`/verify` と入力すれば gstack の版を使える | 検査の自動の繰り返しがなくなる（CLAUDE.md の Verification 節で Claude が検査を実行するのは変わらない）。組み込みの `/verify` は隠れたまま |
| C. gstack の `verify` を `~/.claude/skills` から外す（gstack の `disabled_skills` など） | gstack の設定を変える | 組み込みの `/verify`（アプリを動かして確かめる）が使えるようになり、commit の前の指示も出なくなる（推測） | gstack の設定の仕組みを確かめる必要がある。gstack の更新で戻らないかも確かめる |
| D. `includeGitInstructions: false` | settings に 1 行足す | 指示が消える | commit と PR の組み込みの指示がすべて消える。勧めない |

- **推奨は B。** 検査の実行は CLAUDE.md の Verification 節で足りる。gstack の検査の繰り返しが欲しいときだけ `/verify` と入力すればよい。B は `skillOverrides` の 1 行で、元に戻すのも簡単。
- `skillOverrides` は名前で照合するので、`"verify": "off"` にすると、組み込みの版も一緒に隠れる可能性がある（文書に明記なし）。B では `off` ではなく `user-invocable-only` を使う。
- B・C の効果（指示が消えること）は実動作で確かめていない。変えた後の新しいセッションで、Bash ツールの説明から「`/verify`」の指示が消えたかを見る。
