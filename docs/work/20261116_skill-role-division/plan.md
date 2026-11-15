---
status: done
created: 2026-11-16
---

# Claude Code のスキル・プラグインの役割分担

## 関連

- 前の作業: [pstack の導入と重点スキルの最適化](../20261114_pstack-skill-routing/plan.md)（PR #28、マージ済み）
- 前の作業の調査メモ: [スキル・プラグインの棚卸し](../20261114_pstack-skill-routing/research-skill-inventory.md)。7 節（重複）と 8 節（気づいた点）を引き継ぐ。

<a name="goal"></a>

## 目的と範囲

入っているスキルを棚卸しし、作業の内容・規模・リスクに応じてスキルを選ぶ規則と、人間向けのチートシートを作る。Claude 向けの規則は最小限にして `claude/rules/` に置く。スキルを増やすことではなく、使わなくてよい場面で使わないことも含めて選び方をはっきりさせることを目的にする。

やらないこと（依頼の 11 節）:

- プラグインの追加・削除・無効化、pstack の導入・無効化の設定の変更
- sandbox・permissions・hooks の変更
- git commit・push・merge・deploy

<a name="facts"></a>

## 調査で分かったこと（事実）

各スキルの SKILL.md と設定を読んで確かめた。詳しくは実装の段階で `SKILL_INVENTORY.md` と `research-routing.md` に書く。

### 規模

| 提供元 | 件数と状態 |
| --- | --- |
| superpowers 7.0.2 | 15 スキル。すべてモデルから起動できる。SessionStart hook が `using-superpowers`（「1% でも当てはまれば起動」）を毎回注入する |
| gstack（`~/.claude/skills` のスキル。プラグインではない） | 63 件。有効 28、`user-invocable-only` 4、`off` 31（`skillOverrides`） |
| pstack 0.15.42 | 58 スキルと 2 エージェント。57 件は `disable-model-invocation: true` で、Claude からは起動できない |
| understand-anything 2.9.7 | 9 スキル、10 エージェント、hooks 2 つ |
| crit 1.8.14 | 3 スキル（`crit-cli` はユーザーから起動しない）、PermissionRequest hook |
| claude-code-setup 1.0.0 | 1 スキル（読み取りだけ） |
| ruby-lsp 1.0.0 | LSP だけ |
| 個人スキル（dotfiles） | `code-style`、`commit-staged-pr`、`crit-review`、`salesforce-help` |
| 組み込み・claude.ai 提供 | `/code-review`、`/simplify`、`/security-review`、`/init`、`/update-config`、`anthropic-skills:*` など |
| MCP | `claude/mcp.json` は空。claude.ai の Claude Docs コネクタと easel だけ |

<a name="constraints"></a>

### 選び方に効く制約

1. **pstack は人間だけが起動できる。** Claude が手順を真似ると、公式ドキュメントの指示に反する。規則で決められるのは、Claude がユーザーにコマンドを提案する場面だけ。
2. **外部に書き込む gstack スキルがある。**
   - 修正ごとに commit する: `/qa`、`/design-review`
   - commit と `git push` をし、PR の本文やタイトルも書き換える: `/document-release`、`/document-generate`
   - Issue を作る: `/spec`
   - PR のコメントに返信する: `/review`（レビュー bot のコメントがあるとき）

   push は deny で止まり、`gh` の書き込みは 403 になる。PR の作成とマージをするのは `/ship` と `/land-and-deploy` で、どちらも `off`。
3. **superpowers の `finishing-a-development-branch` は `git push -u origin` と PR 作成の手順を持つ。** CLAUDE.md の Git 節（cc-safe-push、cc-safe-pr）と合わない。
4. **Codex を Bash から呼ぶと、auto モードの判定で拒否された（2026-11-11）。** `/codex` と、`/review`・`/plan-ceo-review`・`/document-release` の中の Codex の段は、どれも Bash から `codex exec` を呼ぶ。同じように拒否されると思われる（未検証）。いま動くのは、ユーザーが `!` で実行する `codex review` だけ。
5. **sandbox の制限で動かないものがある。**
   - localhost で待ち受けられない（リポジトリの規則で `allowLocalBinding` を設定しない）。このため、gstack のヘッドレスブラウザ、`gstack-render`（`/diagram`・`/make-pdf`）、デザイン系の比較ボード、understand-anything のダッシュボードは動かない。ユーザーの実ブラウザを使う Aside が sandbox で動くかは未確認。
   - 書き込めない場所がある。`/cso` の保存先 `~/.gstack/security/` は書き込み許可の外。`/make-pdf` の既定の出力先 `/tmp` にも書けない。`.git/worktrees` は読み取り専用なので、`git worktree add` が失敗する。
6. **参考表の前提が実物と違う。**
   - `/ship` と `/autoplan` は `off`。
   - `/plan-eng-review` は gstack で廃止された（CHANGELOG:「`/plan-eng-review` is cut」）。
   - `/investigate` はこの版にない。
   - pstack の `interrogate` と `arena` は、Claude Code ではすべて Claude で動くので、独立したモデルによるレビューにならない。
7. **前回の調査メモに誤りがある。** understand-anything の保存先の既定は `.ua/` で、`.understand-anything/` があるときだけそれを使う（hook の 6 行目）。完了済みの文書は直さず、今回の文書に正しく書く。`/understand` が作る `.ua/` は `.gitignore` に入らない。
8. **自動で選ばせる公式の仕組みと、その限界。**

   | 手段 | 効き方 |
   | --- | --- |
   | CLAUDE.md・rules | コンテキストとして読まれるだけで、強制されない（公式ドキュメント） |
   | SKILL.md の `disable-model-invocation`（作者が設定） | モデルから起動されなくなる。確実に効く |
   | `skillOverrides` | 確実に効く。ただし `~/.claude/skills` のスキル（gstack）だけで、プラグインのスキルには効かない |
   | `permissions.deny` の `Skill(...)` | モデルからの起動だけを止める。ユーザーが入力したスラッシュコマンドは止めない（前回確認） |
   | hooks | 強制できる。今回は使わない |

   rules に書いても、期待したスキルが必ず選ばれる保証にはならない。

<a name="prior-decision"></a>

## 前の判断との食い違い（判断してほしい点 1）

2026-10-31 に、個人スキル `skill-routing`（スキルの選び方の表）を削除した。77 セッションで 1 回も起動されず、Claude はスキルの説明文と superpowers の注入だけで十分に選べていたため。そのとき、「誤ったスキルが選ばれた具体例が出るまで、ルーティングの表や規則を足さない。足すときも 1〜2 行」と決めた（例外は 11-02 に足した `/qa` と `/review` の 2 行）。

今回の依頼は、規則とその反映をはっきり求めている。

<a name="prior-cause"></a>

### 前回うまく働かなかった原因

削除したスキル（コミット 909ea9d で追加し、4c9cf87 で削除）を読み直した。原因は、届け方と中身の両方にあった。

**届け方の問題**

1. **起動されないと読まれなかった。** スキルの本文は、Claude が起動したときに初めて読み込まれる。Claude は作業のたびに、目的のスキル（brainstorming など）を説明文から直接選ぶ。「スキルを選ぶためのスキル」を先に起動する場面が来ない。
2. **同じ役割のものが先にあった。** 説明文は「Use when starting any task」だった。superpowers が毎回注入する `using-superpowers`（「Use when starting any conversation」）と役割が重なり、そちらが先に効いていた。
3. **dotfiles でしか使えなかった。** 置き場所が dotfiles の `.claude/skills/`（project スコープ）で、ほかのリポジトリのセッションには存在しなかった。

**中身の問題**

1. **説明文と同じことを書いていた。** 中身はシーン（新機能、バグ修正など）ごとの「起点スキル」の表で、各スキルの説明文から Claude が既に選べることだった。
2. **スキルを増やす方向だった。** 起点スキルの後に、`code-style` → verification → `/ship` などの連鎖を毎回提示する形だった。PR レビューは `requesting-code-review` の後に `/review` を回す二重のレビューで、今回の依頼の方針と逆だった。
3. **すぐに古くなった。** `/investigate`・`/ship`・`/land-and-deploy` を前提にしていたが、今はない（`/investigate` は gstack で廃止）か `off` になっている。

<a name="prior-improvement"></a>

### 今回うまく働くと考える根拠と、改善点

| 前回の原因 | 今回の対応 | 根拠 |
| --- | --- | --- |
| 起動されないと読まれない | `claude/rules/`（`~/.claude/rules`）に置く | rules のファイルは毎回コンテキストに入る（公式ドキュメント）。届くことは確実 |
| dotfiles でしか使えない | ユーザーのスコープで、`paths` を付けない | 全プロジェクトのセッションで読み込まれる |
| 説明文と同じことを書いた | 説明文では分からないことだけを書く。具体的には使わない場面、重複したスキルの裁定、この環境の制約、Claude から見えないスキルを提案する場面 | pstack の 57 件と `user-invocable-only` のスキルは説明文が Claude に見えないので、規則に書かない限り提案できない |
| スキルを増やす方向 | 「使わない」を原則の 1 つ目に置き、規模とリスクで構成を絞る | superpowers 自身が、CLAUDE.md などユーザーの指示を優先すると書いている |
| 古くなった | 棚卸しの文書に更新時の見直し手順を書き、規則は名前を最小限にする | — |

**確実でないこと:** 届くことは確実だが、従うかどうかは保証されない（CLAUDE.md と rules は強制ではない）。確実に止めたいもの（commit・push を伴う gstack スキル）は、`skillOverrides` でも止める（判断してほしい点 3 の回答）。

**効果の確かめ方:** 前回は「77 セッションで 0 回」という起動の記録で判断した。今回は、規則を入れる前の記録と、入れた後の記録を比べる。方法・置き場所・スケジュールは[効果の測定](#measurement)に書いた。

規則の全文案は [design.md](design.md) に書いた（判断してほしい点 1 への回答）。採用が決まったら、メモリの記録を今回の判断に合わせて書き換える。

<a name="deliverables"></a>

## 成果物と置き場所

依頼で挙がっていたファイル名（kebab-case）は、このリポジトリの規約に合わない（`docs/` の外の Markdown は英大文字と `_` だけ）。このため名前を変える。

| ファイル | 中身（依頼の節） | いつ読まれるか |
| --- | --- | --- |
| `claude/rules/SKILL_ROUTING.md`（新規。採用が決まった場合だけ） | 選択規則の要点（成果物 2。4 節）。全文案は [design.md](design.md) | 全プロジェクトの全セッションで毎回 |
| `claude/SKILL_INVENTORY.md`（新規） | 棚卸し、各重複の裁定、更新したときの見直し手順（成果物 1。2 節） | 読み込まれない。人間とスキル更新時の参照 |
| `claude/SKILL_CHEATSHEET.md`（新規） | タスク別の早見表とマトリクス、使い分け、規模別の構成、利用例（成果物 3。5 節と 7 節） | 読み込まれない。人間向け |
| `claude/README.md`（変更） | 上の 3 つへのリンクを足す | — |
| `claude/settings.json`（変更） | `skillOverrides` に `document-release`・`document-generate`・`spec` を `user-invocable-only` で足す（判断してほしい点 3 の回答） | — |
| `docs/work/20261116_skill-role-division/design.md`（新規） | 規則の全文案 | — |
| `docs/work/20261116_skill-role-division/research-routing.md`（新規） | 重複 8 組の裁定の根拠、参考表の再評価（2.2 節と 3 節） | — |
| `docs/work/20261116_skill-role-division/test-report.md`（新規） | ケース A〜I の机上検証、名前と状態の機械的な照合（6 節と 10 節） | — |

- 規則を CLAUDE.md ではなく rules に置くのは、CLAUDE.md（116 行）の構成を変えずに、規則だけを外したり差し替えたりできるようにするため。`paths` は付けない。スキル選びはどの作業にも関わるため。
- CLAUDE.md は変えない。Tools 節（`/browse`、`/qa`、`/review`、`/crit-review`）と「Cross-model review (Codex)」節はそのまま正とし、新しい規則には同じことを書かない。
- 棚卸しとチートシートは `claude/README.md` の隣に置く（判断してほしい点 2 で決定）。`claude/` の直下のファイルは `~/.claude` にリンクされない（リンクするのは `CLAUDE.md`・`rules`・`hooks`・`settings.json`・`mcp.json`・スキルだけ）ので、Claude のコンテキストには載らない。

<a name="routing-outline"></a>

## 規則の案

全文は [design.md](design.md) に書いた。1 回目のレビューの指摘を受けて、骨子から次の点を変えた。

- **規模とリスクを分けた。** 規模（軽微・通常・複雑）とリスク（高リスクかどうか）を別に判定する。1 行の変更でも、認証認可や DB に触れれば高リスクになる。それぞれの定義は design.md の「規模とリスク」と、[コメントへの回答](#size-definitions)にある。
- **複雑の構成に Codex レビューの提案を入れた。** CLAUDE.md は「設計判断を含む変更、大規模変更」で Codex レビューを提案すると定めている。最初の骨子は、これと食い違っていた。
- **提案の対象を広げた。** pstack だけでなく、Claude から起動しないスキルとコマンドに広げた。具体的には `/pstack:arena`、ユーザーが `!` で実行する Codex レビュー、gstack の `/careful`・`/freeze`。

<a name="size-definitions"></a>

### 規模とリスクの定義

| 区分 | 定義 | 例 |
| --- | --- | --- |
| 軽微 | 次をすべて満たす。1〜2 ファイルの局所的な変更である。仕様が明確である。既存のテストか確認コマンドで確かめられる。元に戻せる。高リスクに当たらない | 原因の分かったバグの数行の修正、誤字、設定値の変更 |
| 通常 | 仕様と設計の方針は決まっていて、既存のパターンに沿って複数のファイルを変える | 既存のエンドポイントと同じ形で API を 1 本足す |
| 複雑 | 次のどれかに当たる。仕様か設計が決まっていない。設計の案が複数ある。複数のモジュールやシステムにまたがる。大規模である | 新しい機能、大規模なリファクタリング |
| 高リスク（規模とは別） | 認証認可、DB スキーマ・マイグレーション・既存データ、公開 API・OpenAPI の契約、インフラ・Terraform、複数のアプリが使う共通基盤、本番のデータ、元に戻せない操作 | OIDC のクレームの扱いの変更（1 行でも）、カラムの削除 |

- Codex レビューを提案するのは、複雑と高リスク。CLAUDE.md の条件（設計判断を含む変更、大規模変更、セキュリティ関連の変更）に合わせた。
- 通常に入れないのは、仕様と設計が決まっていて CLAUDE.md の条件に当たらないため。Codex レビューはユーザーが `!` で実行し、1 PR あたり 5 回までなので、毎回は求めない。頼まれれば通常でも実行する。

<a name="reference-table"></a>

## 参考表の再評価（要点）

| 作業 | 参考表 | 変更後 | 理由 |
| --- | --- | --- | --- |
| コードベースの可視化 | understand-anything、`how` | 主担当は通常の読解。大きいリポジトリを続けて理解したいと頼まれたら `/understand`。領域の概観は `/pstack:how` を提案する | `/understand` は重く、`.ua/` を作る。ダッシュボードは sandbox で動かない |
| 設計意図の調査 | `why`、understand-anything | `/pstack:why` を提案する。Claude 自身は `git log`・`blame`・`gh` で調べる | グラフは設計意図を持たない |
| 企画・要求の整理 | `/office-hours` | 何を作るかは `/office-hours`、機能の要件は brainstorming | 粒度が違う |
| 技術設計・変更の影響 | `architect`・`blast-radius`、`/autoplan` | brainstorming → writing-plans → `/crit-review`。複雑か高リスクでは pstack を提案する | pstack は Claude から起動できない。`/autoplan` は `off` |
| 実装・テスト | superpowers | 同じ。ただし軽微な変更では使わない | — |
| バグの原因調査 | superpowers、`how`・`why` | systematic-debugging。原因が設計の意図に関わるときだけ `why` を提案する | — |
| 計画の人間レビュー | crit | `/crit-review` | crit プラグインの `/crit` は sandbox で動かない |
| AI のコードレビュー | `/review`、`interrogate` | `/review`。`interrogate` は高リスクで、実行による証明が要るときだけ | `interrogate` は Claude 同士で動く |
| 独立したモデルのレビュー | `/codex` | ユーザーが `!` で `codex review` を実行する | Bash からの Codex は拒否される（制約 4） |
| セキュリティ監査 | `/cso` | 今は `/security-review`。`/cso` が保存先に書けるようになったら、高リスクの差分は `/cso --diff` | 次の節 |
| E2E・ブラウザ QA | `/qa` | `/qa`（修正と commit を伴う）か `/qa-only`（報告だけ） | ブラウザを使う場合、sandbox では動かない可能性が高い（未検証） |
| PR 作成・リリースの準備 | `/ship` | CLAUDE.md の Git 節。ステージ済みの変更だけなら `commit-staged-pr` | `/ship` は `off` |
| Claude Code の環境改善 | claude-code-setup | 改善案は `claude-automation-recommender`。設定の編集は直接行う | — |

障害調査、DB スキーマ、OpenAPI、認証認可、Terraform には専用のスキルがない。規模とリスクの規則で決める（チートシートのマトリクスに行を設ける）。

<a name="cso"></a>

### `/cso` と `/security-review`

| 項目 | `/security-review`（組み込み） | `/cso`（gstack） |
| --- | --- | --- |
| 範囲 | 現在のブランチの未マージの変更 | 範囲を選べる（全体、`--infra`・`--code`・`--supply-chain`・`--owasp` など）。`--diff` で差分に絞っても、差分の外の呼び出し元・ミドルウェア・設定まで読む |
| 確からしさ | 1 回のレビュー | 指摘ごとに攻撃者・境界・影響を書き、独立した確認役（最大 3）が反証を試みる。`--comprehensive` は隔離環境で再現する（Docker が必要） |
| 記録 | 会話だけ | `~/.gstack/security/cso/` に保存し、`--resume`・`--recheck` で続きや再確認ができる |
| コスト | 小さい | 既定で 10 分、`--comprehensive` で 30 分の予算 |

**保存先に書けるとした場合の優先順位:**

- 通常の PR の差分: `/security-review`。軽く、重ねる価値は小さい。
- 高リスクの差分（認証認可、共通基盤）: `/cso --diff`。この場合、同じ差分に `/security-review` を重ねない。
- 定期的な全体の監査、インフラやサプライチェーン: `/cso`（範囲を選ぶ）。

**`!` で実行する案は採れない。** `/cso` は Claude が進める対話型の手順で、ソースもすべて gstack のランチャー（`gstack-cso-launcher`）を通して読む（本文:「Never use host `Read`/`Glob`/`Grep`」）。1 回の監査でランチャーを何十回も呼び、そのたびに `~/.gstack/security/` に書く。`!` で実行できるのは、ユーザーが入力した 1 つのコマンドだけなので、Claude が途中で呼ぶ分は sandbox の中で失敗する。

`/cso` を使えるようにする方法は 2 つある。どちらも sandbox の設定の変更なので今回は行わず、別の PR で判断してもらう。

1. `sandbox.filesystem.allowWrite` に `~/.gstack/security` を足す。範囲は狭いが、`--comprehensive` の Docker とループバックのポートは別に要る（未検証）。
2. `sandbox.excludedCommands` にランチャーを足す。ランチャーが行うことすべて（Docker、ネットワーク）が sandbox の外で動くので、範囲が広い。

<a name="not-changing"></a>

## 変えるもの・変えないもの・提案に留めるもの

変えるもの: `claude/settings.json` の `skillOverrides` に 3 件を足す（判断してほしい点 3 で決定）。

- 対象は `document-release`・`document-generate`・`spec`。値は `user-invocable-only`。
- Claude には見えなくなり、自動では起動されない。ユーザーは `/` から起動できる。
- `skillOverrides` は gstack が管理しているものではない。既存の 35 件も、dotfiles のコミット 02d0add で手で足した。gstack のスクリプトに `skillOverrides` を書き換える処理はない。
- 注意: `skillOverrides` はスキル名だけで照合し、全プロジェクトに効く。ほかのリポジトリに `spec` という名前の project スキルがあると、それも Claude から起動できなくなる（02d0add のコミットメッセージにある注意と同じ）。

変えないもの: `.claude/settings.json`、`settings.json` の `skillOverrides` 以外、hooks、プラグインの構成、CLAUDE.md、既存のスキル、gstack の設定（`~/.gstack`）。

提案に留めるもの（報告に書く）:

1. **gstack の `codex_reviews` を `disabled` にする。** 制約 4 が確かなら、`/review` が実行できない Codex の段を飛ばせる。まず、動作を確かめる必要がある。
2. **CLAUDE.md の Tools 節を見直す。** Tools 節は、対話型のブラウジングに `/browse` を指定している。しかし制約 5 で動かない可能性がある。
3. **`/cso` を sandbox で使えるようにする。** [上の節](#cso)のとおり。ユーザーが別のタスクとして進める（2 回目のレビューで決定）。それまでは、規則と文書に「今は `/security-review`」と書く。
4. 前回から残っている点: `code-style` の説明文が「for this project」になっていること、dotfiles を projectPath とする project スコープの重複登録。

<a name="upgrade"></a>

## 更新したときの見直し手順

`SKILL_INVENTORY.md` に、すべての提供元に共通の手順と、提供元ごとの注意を書く。予定している更新（crit 1.8.15、understand-anything 2.9.8、gstack 1.99.4.0）は、この手順の対象として例に挙げる。今回は更新しない。

共通の手順:

1. 更新の前後で、次の差分を見る。
   - hooks（`hooks/hooks.json`、SKILL.md の frontmatter の `hooks`）
   - スキルの増減
   - `disable-model-invocation`・`user-invocable` の変化
   - 説明文の変化（自動起動に効く）
   - 新しく増えた外部への書き込み（`git push`、`gh` の書き込み、`~/` の外への出力）
2. `claude/settings.json` が書き換わっていないかを見る（CLI はキーの並びを変えることがある。`jq -S` で比べる）。
3. 規則・チートシート・棚卸しに出てくる名前が、まだ存在するかを確かめる（照合のスクリプトを `test-report.md` に残す）。
4. 変わった点を、棚卸しの文書の「状態」と「制約」に反映する。

提供元ごとの注意:

| 提供元 | 見ること |
| --- | --- |
| gstack | `/gstack-upgrade` は `~/.claude/skills` に書くので、sandbox の外で実行する。CHANGELOG で、廃止・追加されたスキルを見る（`/investigate`・`/plan-eng-review` は更新で消えた）。増えたスキルは `skillOverrides` が `on` のまま入るので、要るかを決める |
| understand-anything | hooks は sandbox の外で動く（2026-11-14 に承知のうえで自動更新を選んだ）。hooks が変わったら、改めて判断してもらう |
| crit | プラグインと CLI の版の組み合わせ、`plan-hook` の変化。CLAUDE.md のとおり、更新後は sandbox の外で `mise run crit:profile-test` を実行する |
| pstack | `claude/README.md` の手順（hooks・スキルの一覧・依存の見直し）。新しいスキルが増えても deny は広がらない |
| superpowers | SessionStart で注入する内容（`using-superpowers`）の変化。とくに、ユーザーの指示を優先するという一文が残っているか |

<a name="measurement"></a>

## 効果の測定

<a name="measurement-place"></a>

### 置き場所

| 何を | どこに | 理由 |
| --- | --- | --- |
| 測定の方法（指標、集計のスクリプト、判定の基準） | `claude/SKILL_INVENTORY.md` の「規則の効果の確認」節 | 規則がある間は繰り返し使う。規則を変えたら一緒に直す |
| 基準値（規則を入れる前の記録） | この作業の `test-report.md` | トランスクリプトは既定で 30 日たつと消える（`cleanupPeriodDays` は未設定）。今記録しないと比べられなくなる |
| 測定の予定と結果 | GitHub Issue（kado-ta/dotfiles）。測定の作業は、新しい作業ディレクトリ `docs/work/GH-<番号>_<slug>/` で行う | 作業文書は完了後に変えない（DOCUMENTS.md）。後の測定をこの作業の文書には書けない。Issue なら PR とつながり、期限も付けられる |

- Issue は、sandbox の中の `gh` では作れない（読み取り専用のトークン）。本文は最後の報告に書くので、ユーザーが作る。
- `/schedule` のクラウドのルーティンは、手元のトランスクリプトを読めないので使えない。セッションの中の cron（CronCreate）は、セッションを閉じると消えるので使えない。

<a name="measurement-schedule"></a>

### スケジュール

期間は次のとおりにする。

- 前: 規則を置く直前の 21 日間。今集計して `test-report.md` に残す。
- 後: PR のマージから 21 日間。
- 測定日: マージの 21 日後。遅くともマージの 30 日後まで（それを過ぎると、後の期間の最初のトランスクリプトが消え始める）。

| 役割 | 誰が | どうやって |
| --- | --- | --- |
| 管理 | ユーザー | マージの直後に、測定日（マージの 21 日後）と期限（30 日後）をカレンダーに登録する。Issue にも同じ日付を書く |
| 実行 | Claude（ユーザーに頼まれたとき）か、ユーザー自身 | 新しいセッションで「Issue #N の測定をして」と頼むと、Claude が `SKILL_INVENTORY.md` の集計スクリプトを実行し、基準値と比べて判定する。スクリプトは件数だけを出すので、ユーザーが自分で実行してもよい |

カレンダーへの登録のリマインド（4 回目のレビューでの依頼）:

Claude はマージの瞬間を知ることができない。マージは、GitHub の画面か、別のセッションで行われる。このため、マージする人の目に入る場所に、次の 3 つを置く。

1. **PR の本文:** 冒頭に「マージ直後: 測定日（マージの 21 日後）と期限（30 日後）をカレンダーに登録する」のチェック項目を置く。GitHub の画面でマージするときに目に入る。PR は今回の作業では作らない（commit しない）ので、後で PR を作るときの本文に入れる。この plan と最後の報告に、その文面を書いておく。
2. **メモリ:** dotfiles のプロジェクトのメモリに、「この PR のマージを確かめたら、カレンダーへの登録をリマインドする」と書く。dotfiles のセッションでマージに触れたときに、Claude が思い出せるようにする。
3. **最後の報告:** Issue の本文と一緒に、同じリマインドを書く。

この 3 つでも、Claude が関わらずにマージし、PR の本文も見なかった場合は、リマインドが届かない。

Claude が期日に自動で実行する方法はない。

- `/schedule` のクラウドのルーティン: 手元のトランスクリプトを読めない。
- CronCreate: セッションを閉じると消える（`durable` は効かない、とツールの説明にある）。
- GitHub Actions のスケジュール: 手元のファイルを読めない。
- macOS の launchd などで `claude -p` を定期実行する方法はある。ただし、sandbox の外に自動化を増やすことになるので提案しない。

<a name="measurement-method"></a>

### 方法

トランスクリプト（`~/.claude/projects/*/*.jsonl`）から件数だけを集計する。会話の中身は出力しない。集計できることは、このセッションで確かめた（268 ファイル、2026-10-09〜11-15）。

| 指標 | 見ること |
| --- | --- |
| Claude が起動したスキル（Skill ツール）の、スキルごとの回数とセッション数 | 全体の傾向 |
| ユーザーが入力したスラッシュコマンドの回数 | pstack を含め、提案したスキルが使われたか |
| 1 つのセッションで、レビュー系のスキルを 2 つ以上使った回数（`review`・`code-review`・`superpowers:requesting-code-review`） | レビューの重複が減ったか |
| brainstorming と writing-plans を起動したセッションの一覧 | 軽微な作業で起動していないか（一覧を人が見て判断する） |
| Claude の発言に含まれる `/pstack:` の提案の回数 | 提案が多すぎないか、使われたか |
| ユーザーが気づいた、誤ったスキルの選択 | Issue にその都度書いてもらう |

判定の基準:

- **維持:** レビューの重複と、軽微な作業での計画系のスキルの起動が減るか 0 のままである。誤った選択の報告がない。
- **修正:** 誤った選択の具体例がある。その例に対応する 1〜2 行を直す。
- **削除:** 前後で差がなく、提案も使われていない。前回と同じように規則を消し、チートシートと棚卸しだけを残す。

<a name="steps"></a>

## 手順

| # | 作業 | 確認 |
| --- | --- | --- |
| 1 | `research-routing.md` に、重複 8 組の裁定を書く | 8 組すべてに、主担当・代替・補完・併用する条件・併用しない条件・優先順位がある |
| 2 | `claude/SKILL_INVENTORY.md` を書く（更新したときの見直し手順と、規則の効果の確認の方法を含む） | スクリプトで照合する。インストールされたスキルがすべて載っていること、状態が設定と frontmatter に一致すること |
| 3 | `claude/settings.json` の `skillOverrides` に 3 件を足す | `jq` で読めること。`git diff` で、`skillOverrides` の 3 行以外に差分がないこと。新しいセッションのスキル一覧から 3 件が消えること（実動作。このセッションで確かめられなければ未検証とする） |
| 4 | 規則の採用が決まったら、`claude/rules/SKILL_ROUTING.md` を design.md の本文で作る | design.md の本文と一致すること。実在しない名前がないこと |
| 5 | `claude/SKILL_CHEATSHEET.md` を書く | 依頼の A〜E 節がそろい、主担当が規則と一致し、実在しない名前がない |
| 6 | `claude/README.md` にリンクを足す | リンク先が存在する（`check-repo.py` の `markdown-links`） |
| 7 | `test-report.md` を書く。規則を置く前に、[効果の測定](#measurement)の基準値を集計して記録する | ケース A〜I と、依頼の 10 節の 10 項目。基準値の集計の期間と件数 |
| 8 | 規定の検査を実行する: `check-repo.py`、`test-check-repo.py`、`shellcheck`、`actionlint` | すべて成功する。`git diff --stat` で、hooks に差分がなく、`settings.json` の差分が手順 3 だけであること |
| 9 | 成果物を `/crit-review` で開く | `approved: true` |
| 10 | 最後の報告に、測定の Issue の本文（期限、方法へのリンク、基準値）と、PR の本文に入れるリマインドの文面を書く。メモリにリマインドを書く | ユーザーが Issue を作れる形になっている。メモリの索引（`MEMORY.md`）に 1 行ある |

- `claude/` 配下は sandbox の中から Bash で書けない。Write と Edit のツールで書くので、確認ダイアログ（`Edit(~/dotfiles/claude/**)` の ask）が出る。
- `claude/rules/` は `~/.claude/rules` からリンクされている。このブランチで書いた時点から、新しいセッションで規則が読み込まれる。main に戻すと読み込まれなくなる。`skillOverrides` も同じ。

<a name="verification"></a>

## 検証の区別

| 種類 | やること | 結果の書き方 |
| --- | --- | --- |
| 机上 | ケース A〜I、名前の実在、状態の一致、規則とチートシートの整合 | このセッションで確認済み |
| 実動作 | 規則を読んだ新しいセッションで、期待どおりのスキルが選ばれるか | sandbox の中からは `claude -p` で API に接続できないので、試せない。`test-report.md` に試すためのプロンプトと期待する結果を書き、未検証とする。マージの 3 週間後に、トランスクリプトで起動の回数を比べる（[効果の測定](#measurement)） |

<a name="risks"></a>

## リスク

- **常にコンテキストを使う。** 規則は全プロジェクトの全セッションで読み込まれる。書いた後に文字数を測って報告する。
- **抑えすぎるおそれがある。** 「軽微」を広く取ると、TDD や `/review` が必要な変更でも省かれる。このため、軽微は 5 つの条件をすべて満たすときに限る。
- **すぐに古くなる。** pstack（2 日で 6 版）や gstack の更新で、内容が古くなる。[更新したときの見直し手順](#upgrade)で防ぐ。

<a name="decisions-needed"></a>

## 判断してほしい点

| # | 内容 | 結果 |
| --- | --- | --- |
| 1 | 前の判断との食い違い | 全文案を [design.md](design.md) に書いた。採用するか判断してほしい |
| 2 | 棚卸しとチートシートの置き場所 | 推奨どおり `claude/` に置く（1 回目のレビューで決定） |
| 3 | `skillOverrides` の変更 | 3 件を `user-invocable-only` にする（1 回目のレビューで決定） |
