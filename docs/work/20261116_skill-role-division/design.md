---
status: done
created: 2026-11-16
---

# スキル選択規則の案（`claude/rules/SKILL_ROUTING.md`）

[plan](plan.md) の「判断してほしい点 1」への回答として、毎回読み込まれる規則の全文案を示す。採用が決まったら、次の「本文」の節を `claude/rules/SKILL_ROUTING.md` に置く。採用しない場合は、チートシートだけを作る。

> [!NOTE]
> 5 回目のレビューの承認（2026-11-16）を採用と受け取り、規則を置いた。置くときは、2 段目の見出しだけを英語にした（Principles、Size and risk、Overlapping skills、Skills to suggest instead of starting、Exit criteria）。既存の rules（DOCUMENTS.md など）と同じく見出しを英語にすると、MARKDOWN.md が日本語の見出しに求めるアンカーが要らなくなるため。置いた時点では、本文は変えていない（`diff` で確認）。その後、成果物のレビュー（2026-11-16）で、スキル名をコード書式に揃えた（`brainstorming`・`writing-plans`・`test-driven-development`・`finishing-a-development-branch`・`architect` の 5 行。書式だけで、文言は同じ）。

- 長さ: 本文は 56 行（空行を含む）、2,714 文字。
- 書かないこと:
  - CLAUDE.md の Tools 節と「Cross-model review (Codex)」節に書いてあること
  - スキルの説明文で分かること（どのスキルが何をするか）
  - スキル同士の連鎖の手順
- 書くこと: 説明文だけでは Claude が判断できないこと。具体的には次の 4 つ。
  - 使わない場面
  - 重複したスキルの裁定
  - この環境の制約
  - Claude から見えないスキル（pstack と `user-invocable-only`）を提案する場面

<a name="body"></a>

## 本文

```markdown
# Skill routing

スキルを選ぶときの規則。CLAUDE.md の Tools と Cross-model review (Codex) の節は繰り返さない。一覧と早見表は `~/dotfiles/claude/SKILL_CHEATSHEET.md`（人間向け）。

## 原則

- 通常の読解・検索・編集・テストで足りる作業には、スキルを使わない。スキルがあることは使う理由にならない。この規則は superpowers の「1% でも当てはまれば起動」より優先する。
- 作業の段階（調査・設計・実装・レビュー・リリース）ごとに、主担当のスキルを 1 つにする。1 つの対象（同じ差分・同じ要件・同じ不具合）に、同じ目的の別のスキルを重ねて使わない。直した後に同じスキルをもう一度使うのはよい。
- ユーザーが名指ししたスキルを優先する。ただし、スキルの手順に push・merge・PR の作成や編集・Issue の作成・deploy が含まれていても、CLAUDE.md の Git と Safety の規則が優先する。その手前で止めて、ユーザーに伝える。

## 規模とリスク

規模は次の 3 つのどれかに当てはめる。リスクは規模とは別に判定する。

- 軽微: 次をすべて満たす。1〜2 ファイルの局所的な変更である。仕様が明確である。既存のテストか確認コマンドで確かめられる。元に戻せる。高リスクに当たらない。
- 通常: 仕様と設計の方針は決まっていて、既存のパターンに沿って複数のファイルを変える。
- 複雑: 次のどれかに当たる。仕様か設計が決まっていない。設計の案が複数ある。複数のモジュールやシステムにまたがる。大規模である。
- 高リスク（規模とは別に判定）: 認証認可、DB スキーマ・マイグレーション・既存データ、公開 API・OpenAPI の契約、インフラ・Terraform、複数のアプリが使う共通基盤、本番のデータ、元に戻せない操作。1 行の変更でも当たる。
- セキュリティの境界: 認証認可、権限（IAM を含む）、秘密情報の扱い、外部からの入力（公開 API、webhook）、データとネットワークの公開範囲（テナントの分離、S3、ALB、Cloudflare）。

| 区分 | 構成 |
| --- | --- |
| 軽微 | スキルを使わない。テストか確認コマンドを実行して終える |
| 通常 | 振る舞いを変えるなら test-driven-development。PR の前に `/review` |
| 複雑 | brainstorming → writing-plans → `/crit-review` → 実装 → `/review` → Codex レビューを提案する |
| 高リスク | 規模の構成に次を足す。実装の前に変更の影響を確かめる（`/pstack:blast-radius` を提案する）。セキュリティの境界に触れるなら `/security-review`。ロールバックの手順。Codex レビューの提案 |

## 重複したスキルの使い分け

- TDD・デバッグ・実装計画は superpowers を使う。
- 何を作るか自体の判断は `/office-hours`、機能の要件整理と設計は brainstorming を使う。同じ要件に両方は使わない。
- 差分のレビューは `/review` だけ。同じ差分に `/code-review` や `requesting-code-review` を重ねない。
- セキュリティのレビューは `/security-review`。`/cso` は sandbox の中では保存先に書けない。
- コードの理解は、まず通常の読解（広く探すなら Explore）を使う。understand-anything のグラフ（`.ua/`）が既にあるリポジトリで、全体にまたがる質問なら `understand-chat` を使ってよい。グラフを作る `understand` は、自分では起動せず提案する（下の表）。
- PR とリリースは CLAUDE.md の Git 節に従う。finishing-a-development-branch の push と PR 作成の手順は使わない。

## Claude が起動しないスキルの提案

次のスキルとコマンドは、Claude からは起動できないか、重いので起動しない。場面が合うときは、手順を真似ずに、コマンドを 1 行で提案する。提案は 1 つのタスクで 1 回まで。

| コマンド | 提案する場面 |
| --- | --- |
| `/understand-anything:understand` | 大きくて慣れないリポジトリを、続けて理解したいとき（初回は重く、`.ua/` を作る。`.gitignore` への追加も提案する） |
| `/pstack:how` | 慣れない領域の仕組みを概観したいとき |
| `/pstack:why` | 設計の意図を履歴で確かめたいとき |
| `/pstack:architect with checkpoint` | 複雑か高リスクで、設計の案を比べたいとき |
| `/pstack:arena` | 実装・文面・設定の候補を並べて比べたいとき（architect の中でも使われるので、重ねない） |
| `/pstack:blast-radius` | 高リスクの差分で、差分の外への影響を確かめたいとき |
| `/pstack:interrogate` | `/review` の後に、実行で確かめられる不変条件が残るとき |
| `! codex review --base <base> -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` | 複雑か高リスクの変更が完了する前（Bash からは実行しない） |
| `/careful`・`/freeze <dir>` | 本番に近い環境を調べる前（危険なコマンドの警告と、編集範囲の制限） |

## 終了条件

- 調査: 根拠（ファイルと行）を付けて問いに答えたら終える。
- レビュー: 指摘への対応が決まったら終える。別のレビューを重ねるのは、ユーザーが指定したときと、高リスクのときだけ。
```

<a name="notes"></a>

## 補足

- 規模とリスクを分けたのは、1 行の変更でも認証認可や DB に触れれば高リスクになるため。軽微の条件に「高リスクに当たらない」を入れて、両方に当たる場合をなくした。
- 複雑に Codex レビューの提案を入れた。CLAUDE.md は「設計判断を含む変更、大規模変更」で Codex レビューを提案すると定めているので、最初の案で複雑に入れなかったのは CLAUDE.md と食い違っていた。通常には入れない（仕様と設計が決まっていて、CLAUDE.md の条件に当たらない）。頼まれれば実行する。
- `user-invocable-only` にする `/document-release`・`/document-generate`・`/spec` は、提案の表に入れない。この環境では push・PR の編集・Issue の作成が止まるので、勧める場面がない。ユーザーが起動したときは、原則の 3 つ目に従う。
- `/security-review` は、高リスクのうちセキュリティの境界に触れる変更に使う。マイグレーションのように、データの整合性が主なリスクの変更では、指摘が的外れになりやすい。その確認はロールバックの手順と変更の影響の確認で行う。
- understand-anything の 9 スキルは、どれも Claude から起動できる（`disable-model-invocation` がない）。グラフを作る `understand` は、多くのエージェントを起動し、リポジトリに `.ua/` を作る。このため、Claude が自分で起動せずに提案する表に入れた。
- `/cso` の 1 行は、sandbox の設定を変えて保存先に書けるようにしたら、「高リスクの差分は `/cso --diff`」に書き換える（[plan](plan.md#cso)）。
