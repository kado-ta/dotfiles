# Skill routing

スキルを選ぶときの規則。CLAUDE.md の Tools と Cross-model review (Codex) の節は繰り返さない。一覧と早見表は `~/dotfiles/claude/SKILL_CHEATSHEET.md`（人間向け）。

## Principles

- 通常の読解・検索・編集・テストで足りる作業には、スキルを使わない。スキルがあることは使う理由にならない。この規則は superpowers の「1% でも当てはまれば起動」より優先する。
- 作業の段階（調査・設計・実装・レビュー・リリース）ごとに、主担当のスキルを 1 つにする。1 つの対象（同じ差分・同じ要件・同じ不具合）に、同じ目的の別のスキルを重ねて使わない。直した後に同じスキルをもう一度使うのはよい。
- ユーザーが名指ししたスキルを優先する。ただし、スキルの手順に push・merge・PR の作成や編集・Issue の作成・deploy が含まれていても、CLAUDE.md の Git と Safety の規則が優先する。その手前で止めて、ユーザーに伝える。

## Size and risk

規模は次の 3 つのどれかに当てはめる。リスクは規模とは別に判定する。

- 軽微: 次をすべて満たす。1〜2 ファイルの局所的な変更である。仕様が明確である。既存のテストか確認コマンドで確かめられる。元に戻せる。高リスクに当たらない。
- 通常: 仕様と設計の方針は決まっていて、既存のパターンに沿って複数のファイルを変える。
- 複雑: 次のどれかに当たる。仕様か設計が決まっていない。設計の案が複数ある。複数のモジュールやシステムにまたがる。大規模である。
- 高リスク（規模とは別に判定）: 認証認可、DB スキーマ・マイグレーション・既存データ、公開 API・OpenAPI の契約、インフラ・Terraform、複数のアプリが使う共通基盤、本番のデータ、元に戻せない操作。1 行の変更でも当たる。
- セキュリティの境界: 認証認可、権限（IAM を含む）、秘密情報の扱い、外部からの入力（公開 API、webhook）、データとネットワークの公開範囲（テナントの分離、S3、ALB、Cloudflare）。

| 区分 | 構成 |
| --- | --- |
| 軽微 | スキルを使わない。テストか確認コマンドを実行して終える |
| 通常 | 振る舞いを変えるなら `test-driven-development`。PR の前に `/review` |
| 複雑 | `brainstorming` → `writing-plans` → `/crit-review` → 実装 → `/review` → Codex レビューを提案する |
| 高リスク | 規模の構成に次を足す。実装の前に変更の影響を確かめる（`/pstack:blast-radius` を提案する）。セキュリティの境界に触れるなら `/security-review`。ロールバックの手順。Codex レビューの提案 |

## Overlapping skills

- TDD・デバッグ・実装計画は superpowers を使う。
- 何を作るか自体の判断は `/office-hours`、機能の要件整理と設計は `brainstorming` を使う。同じ要件に両方は使わない。
- 今のブランチの差分のレビューは `/review` だけ（ほかの PR は CLAUDE.md の Tools 節）。同じ差分に `/code-review` や `requesting-code-review` を重ねない。
- セキュリティのレビューは `/security-review`。`/cso` はユーザーが指定したときだけ使う。sandbox が読めないファイル（`.env.example` など）を追跡していると失敗するので、始める前に `~/dotfiles/claude/SKILL_INVENTORY.md` の「`/cso` を sandbox で使う」に従う。
- コードの理解は、まず通常の読解（広く探すなら Explore）を使う。understand-anything のグラフ（`.ua/`）が既にあるリポジトリで、全体にまたがる質問なら `understand-chat` を使ってよい。グラフを作る `understand` は、自分では起動せず提案する（下の表）。
- PR とリリースは CLAUDE.md の Git 節に従う。`finishing-a-development-branch` の push と PR 作成の手順は使わない。

## Skills to suggest instead of starting

次のスキルとコマンドは、Claude からは起動できないか、重いので起動しない。場面が合うときは、手順を真似ずに、コマンドを 1 行で提案する。提案は 1 つのタスクで 1 回まで。

| コマンド | 提案する場面 |
| --- | --- |
| `/understand-anything:understand` | 大きくて慣れないリポジトリを、続けて理解したいとき（初回は重く、`.ua/` を作る。`.gitignore` への追加も提案する） |
| `/pstack:how` | 慣れない領域の仕組みを概観したいとき |
| `/pstack:why` | 設計の意図を履歴で確かめたいとき |
| `/pstack:architect with checkpoint` | 複雑か高リスクで、設計の案を比べたいとき |
| `/pstack:arena` | 実装・文面・設定の候補を並べて比べたいとき（`architect` の中でも使われるので、重ねない） |
| `/pstack:blast-radius` | 高リスクの差分で、差分の外への影響を確かめたいとき |
| `/pstack:interrogate` | `/review` の後に、実行で確かめられる不変条件が残るとき |
| 通常ターミナルで `cd <repo> && codex review --base <base> -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` | 複雑か高リスクの変更が完了する前（Bash からは実行しない。`!` では失敗することがある） |
| 通常ターミナルで `cd <repo> && codex exec - -s read-only -c skills.include_instructions=false < <プロンプトのファイル>`（challenge） | セキュリティの境界か設計判断を含む変更で、上の `codex review` に加えて 1 回（5 回の上限に数える）。プロンプトは Claude が書く。攻撃者として迂回を探せという書き方は OpenAI 側の判定で拒否されることがあるので、変更前と比べた後退や、壊れる入力を具体的に挙げるよう頼む。作業ディレクトリの中の git 管理外の場所（`git check-ignore` で確かめる）に置いて絶対パスで渡し、全文をチャットにも示す |
| `/careful`・`/freeze <dir>` | 本番に近い環境を調べる前（危険なコマンドの警告と、編集範囲の制限） |

## Exit criteria

- 調査: 根拠（ファイルと行）を付けて問いに答えたら終える。
- レビュー: 指摘への対応が決まったら終える。別のレビューを重ねるのは、ユーザーが指定したときと、高リスクのときだけ。
- Codex のレビュー: 結果は貼り付けに頼らず、次のコマンドで、そのブランチで実行した全回の最終メッセージ（`last_agent_message`）を読む。1 回ずつ test-report に記録してから、採否を整理する。記録のほかの部分は読まない。Codex は sandbox の外で動くので、コマンドの出力に denyRead のファイルの中身が入りうる。Codex を実行したのに何も出なければ、記録の形式か実行した場所が違う見込みがあるので、結果を貼り付けてもらう。

```sh
top=$(git rev-parse --show-toplevel) b=$(git branch --show-current)
for f in ~/.codex/sessions/*/*/*/rollout-*.jsonl*; do
  zstd -dcfq "$f" | jq -rn --arg cwd "$top" --arg b "$b" '[inputs] | (map(select(.type=="session_meta"))[0].payload) as $m
    | select($m.cwd==$cwd and $m.git.branch==$b) | .[] | select(.type=="event_msg" and .payload.type=="task_complete" and .payload.last_agent_message!=null)
    | "== \($m.timestamp) \($m.git.commit_hash[0:7])\n\(.payload.last_agent_message)"'
done
```
