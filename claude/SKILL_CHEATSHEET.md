# Claude Code スキル早見表

作業ごとに、どのスキルを使うか（使わないか）を引くための表。Claude が毎回読む規則は [rules/SKILL_ROUTING.md](rules/SKILL_ROUTING.md)、全スキルの一覧と状態は [SKILL_INVENTORY.md](SKILL_INVENTORY.md) にある。

> [!IMPORTANT]
> スキルを使わないのも正しい選択。通常の読解・検索・編集・テストで足りるなら、スキルは要らない。同じ対象に、同じ目的の別のスキルを重ねない（例: 同じ差分に `/review` と `/code-review`）。

- 「自動」は Claude が自分で起動するスキル。「明示」はユーザーが入力したときだけ動くスキル（pstack など）で、Claude は場面が合えば提案する。
- 高リスクは、認証認可、DB スキーマ・既存データ、公開 API・OpenAPI、インフラ・Terraform、共通基盤、本番のデータ、元に戻せない操作。1 行の変更でも当たる。
- スキル・エージェント・コマンドの名前はコード書式で書く。提供元（superpowers、gstack、pstack など）の名前は書式を付けない。

<a name="toc"></a>

## 目次

- [A. タスクから探す](#by-task)
- [B. スキルから探す](#by-skill)
- [C. 迷いやすいスキルの使い分け](#comparisons)
- [D. 規模別の推奨構成](#by-size)
- [E. 利用例](#examples)
- [F. スキル・プラグインのアップデート](#update)

<a name="by-task"></a>

## A. タスクから探す

| タスク                           | 主担当                                                        | 補完                                                                                                                            | 使う条件                                                           | 使わない場合                                                                                            |
| -------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| 既存コードの理解                 | 通常の読解（Claude に聞く）                                   | `/pstack:how`（明示）、`understand-chat`                                                                                        | 領域の全体像を知りたいなら `how`。グラフがあれば `understand-chat` | 1 つの関数・ファイルの質問                                                                              |
| 大きいリポジトリのキャッチアップ | `/understand-anything:understand`（提案）                     | `/understand-anything:understand-onboard`                                                                                       | 続けて何度も調べるリポジトリ                                       | 1 回だけの調査                                                                                          |
| 設計意図の調査                   | `/pstack:why`（明示）                                         | Claude の `git log`・`blame`                                                                                                    | 経緯がコミットや PR にある                                         | コードを読めば分かる                                                                                    |
| 企画・何を作るか                 | `/office-hours`                                               | —                                                                                                                               | 作るかどうか、何を作るかが決まっていない                           | 機能の要件整理（`brainstorming`）                                                                       |
| 新機能開発                       | `brainstorming` → `writing-plans` → `test-driven-development` | `/crit-review`、`/review`、Codex                                                                                                | 仕様か設計が決まっていない                                         | 既存のパターンに沿う小さな追加（TDD → `/review` だけ）                                                  |
| 既存機能の改修                   | `test-driven-development`                                     | `/review`                                                                                                                       | 振る舞いが変わる                                                   | 文言・設定値だけ                                                                                        |
| バグ修正                         | `systematic-debugging`                                        | `test-driven-development`（再現テスト）                                                                                         | 原因が分からない                                                   | 原因が明らかな数行（スキルなし。再現テストは書く）                                                      |
| 原因不明の障害調査               | `systematic-debugging`                                        | `/pstack:why`、`/careful`（明示）                                                                                               | 本番・ステージングの障害                                           | —                                                                                                       |
| リファクタリング                 | `writing-plans`                                               | `/pstack:blast-radius`、`/review`                                                                                               | 複数のモジュールにまたがる                                         | 1 ファイルの中（スキルなし。前後でテスト）。`/review` と同じ差分に `/simplify` を重ねない               |
| DB スキーマの設計・変更          | `brainstorming` → `writing-plans` → `/crit-review`            | `/pstack:blast-radius`、`/review`、Codex                                                                                        | 常に高リスク                                                       | —                                                                                                       |
| OpenAPI の設計・変更             | spec を先に更新 → `writing-plans`                             | `/review`、Codex                                                                                                                | 公開 API は高リスク                                                | 内部だけの型の変更                                                                                      |
| 認証・認可の変更                 | `brainstorming` → `writing-plans` → `/crit-review`            | `/pstack:blast-radius`、`/security-review`、`/pstack:interrogate`、Codex                                                        | 常に高リスク                                                       | —                                                                                                       |
| インフラ・Terraform の変更       | `writing-plans` と `terraform plan`                           | `/security-review`（IAM・公開範囲）、Codex                                                                                      | 常に高リスク                                                       | apply・destroy は Claude が実行しない                                                                   |
| セキュリティレビュー             | `/security-review`                                            | `/cso`（ユーザーが指定したとき。`.env.example` などを追跡しているリポジトリでは[一時的に消す](SKILL_INVENTORY.md#cso-sandbox)） | セキュリティの境界に触れる                                         | データの整合性だけの変更                                                                                |
| パフォーマンス改善               | `systematic-debugging`（計測から）                            | `/benchmark`（ブラウザが使えれば）                                                                                              | 遅い原因が分からない                                               | 計測せずに直すこと                                                                                      |
| テストの設計・実装               | `test-driven-development`                                     | `/test-audit`                                                                                                                   | 振る舞いの変更、テストの整理                                       | —                                                                                                       |
| コードレビュー（今のブランチ）   | `/review`                                                     | `/pstack:interrogate`（明示）、Codex                                                                                            | PR の前                                                            | 軽微な変更（`/crit-review` だけ）                                                                       |
| 今のブランチ以外の PR のレビュー | `/code-review medium <PR の URL>`（チェックアウトしない）     | 全体が要るときは人間が読む（`ultra` は Claude のアカウントに GitHub をつなぐので使わない）                                      | 作者を問わない。手元に取り込まず、指摘だけで直さない               | `--comment`・`--fix`。今のブランチを見る `/review`・`/security-review`・Codex・`interrogate`            |
| E2E・ブラウザ QA                 | `/qa`（直す）、`/qa-only`（報告だけ）                         | Playwright MCP（個別のブラウザ操作・調査）                                                                                      | 動く環境がある                                                     | `/qa`・`/qa-only` は sandbox でブラウザが動かないとき（Playwright MCP は sandbox の外で動くので使える） |
| 技術選定・PoC                    | Claude の調査（WebFetch）                                     | `anthropic-skills:deep-research`、`/pstack:arena`（明示）                                                                       | 候補が複数ある                                                     | 答えが公式ドキュメントで決まる                                                                          |
| PR 作成・リリース                | CLAUDE.md の Git 節、`/commit-staged-pr`                      | `/crit-review`（push の前に必須）                                                                                               | —                                                                  | `/ship`、`/document-release`、`finishing-a-development-branch` の push                                  |
| ドキュメント作成                 | 通常の編集（DOCUMENTS.md に従う）                             | —                                                                                                                               | —                                                                  | `/document-generate`（commit・push する）                                                               |
| Claude Code の設定改善           | `/claude-code-setup:claude-automation-recommender`            | `superpowers:writing-skills`、`/update-config`                                                                                  | 何を自動化するか知りたい                                           | 設定 1 行の変更                                                                                         |
| 作業の中断と再開                 | `/context-save`・`/context-restore`                           | —                                                                                                                               | 別のセッションで続ける                                             | 同じセッションで続ける                                                                                  |
| Salesforce のヘルプ記事          | `salesforce-help`                                             | —                                                                                                                               | help.salesforce.com を読む                                         | —                                                                                                       |
| テーマを問答で身につける         | `/socratic-tutor`（明示）                                     | —                                                                                                                               | 理解を確かめながら、1 つのテーマを身につけたい                     | 単発の質問、正解が 1 つでない判断、資料を渡さずに学習データより新しい仕様を学ぶ                         |
| Web フロントエンドの実装         | `modern-web-guidance`（自動）                                 | `/qa`（動く環境で確かめる）                                                                                                     | HTML・CSS・クライアントの JS を書く・直す                          | バックエンド・インフラ・ツールの設定だけの変更                                                          |
| Chrome 拡張機能の開発・公開      | `chrome-extensions`（自動）                                   | `modern-web-guidance`（拡張機能の中の Web API）                                                                                 | Manifest V3 の拡張機能を作る・直す・公開する                       | —                                                                                                       |

<a name="by-skill"></a>

## B. スキルから探す

| 提供元              | コマンド                                                                                                     | 用途                                                                                                                                                            | 起動       |
| ------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| superpowers         | `/superpowers:brainstorming`                                                                                 | 要件と設計を対話で固める                                                                                                                                        | 自動       |
|                     | `/superpowers:writing-plans` → `executing-plans` または `subagent-driven-development`                        | 計画を書いて実行する                                                                                                                                            | 自動       |
|                     | `/superpowers:test-driven-development`                                                                       | テスト駆動で実装する                                                                                                                                            | 自動       |
|                     | `/superpowers:systematic-debugging`                                                                          | 原因を切り分ける                                                                                                                                                | 自動       |
|                     | `/superpowers:verification-before-completion`                                                                | 完了の前に検証する                                                                                                                                              | 自動       |
| gstack              | `/review`                                                                                                    | 差分のレビューと修正（commit しない）                                                                                                                           | 自動       |
|                     | `/qa`・`/qa-only`・`/browse`                                                                                 | 動作確認（`/qa` は修正ごとに commit）                                                                                                                           | 自動       |
|                     | `/office-hours`                                                                                              | 何を作るかを決める                                                                                                                                              | 自動       |
|                     | `/plan-ceo-review`・`/plan-design-review`                                                                    | 計画をスコープ・デザインの観点でレビューする                                                                                                                    | 自動       |
|                     | `/plan-eng-review`                                                                                           | 計画をアーキテクチャ・テストの観点でレビューする                                                                                                                | 明示       |
|                     | `/context-save`・`/context-restore`                                                                          | 作業状態の保存と再開                                                                                                                                            | 自動       |
|                     | `/careful`・`/freeze <dir>`                                                                                  | 危険なコマンドの警告、編集範囲の制限                                                                                                                            | 明示       |
|                     | `/document-release`・`/document-generate`・`/spec`                                                           | 文書の更新・作成、Issue 化（push・Issue 作成は止まる）                                                                                                          | 明示       |
| pstack              | `/pstack:how`・`/pstack:why`                                                                                 | 仕組みの説明、設計意図の調査                                                                                                                                    | 明示       |
|                     | `/pstack:architect with checkpoint`                                                                          | 設計案を比べる（付けないと実装まで進む）                                                                                                                        | 明示       |
|                     | `/pstack:blast-radius`                                                                                       | 差分の外への影響を調べる                                                                                                                                        | 明示       |
|                     | `/pstack:interrogate`・`/pstack:arena`                                                                       | 実行で示す敵対的レビュー、候補の競争                                                                                                                            | 明示       |
| understand-anything | `/understand-anything:understand` → `understand-chat`・`understand-explain`・`understand-onboard`            | 知識グラフを作って使う（`.ua/` を作る）                                                                                                                         | 提案・自動 |
| 個人                | `/crit-review`                                                                                               | 人間のレビュー（plan の承認、push・PR の前）                                                                                                                    | 自動       |
|                     | `/commit-staged-pr`                                                                                          | ステージ済みの変更の commit・push・PR                                                                                                                           | 自動       |
|                     | `/socratic-tutor`                                                                                            | 1 つのテーマを、診断・習熟度の表・1 問ずつの問答・最終試験で身につける（Claude は起動も提案もしない）                                                           | 明示       |
|                     | `modern-web-guidance`                                                                                        | Web 標準の書き方のガイドを検索・取得する（HTML・CSS・クライアントの JS で起動する）                                                                             | 自動       |
|                     | `chrome-extensions`                                                                                          | Chrome 拡張機能（Manifest V3）の開発と、Chrome Web Store への公開のガイド                                                                                       | 自動       |
| 組み込み            | `/security-review`                                                                                           | セキュリティレビュー                                                                                                                                            | 自動       |
|                     | `/simplify`                                                                                                  | 変更したコードの整理                                                                                                                                            | 自動       |
|                     | `/code-review medium <PR の URL>`                                                                            | 今のブランチ以外の PR を、チェックアウトせずにレビューする（`--comment`・`--fix` は付けない）                                                                   | 自動       |
| Codex               | `cd <repo> && codex review --base <base> -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` | 別モデルの独立レビュー（ユーザーが通常のターミナルで実行する。`!` では失敗することがある）                                                                      | 明示       |
|                     | `cd <repo> && codex exec - -s read-only -c skills.include_instructions=false < <プロンプトのファイル>`       | challenge（変更前と比べた後退や、壊れる入力を挙げてもらう。プロンプトは Claude が書く。セキュリティの境界・設計判断を含む変更で、`codex review` に加えて 1 回） | 明示       |

<a name="comparisons"></a>

## C. 迷いやすいスキルの使い分け

| 組み合わせ                               | 使い分け                                                                                                                                                                                       | 併用                                                                            |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| superpowers と pstack                    | TDD・デバッグ・計画は superpowers。pstack の `tdd` は使わない。pstack は `how`・`why`（理解）と `architect`・`blast-radius`・`interrogate`（高リスクの設計と検証）だけ                         | 高リスクで、superpowers の計画に `/pstack:blast-radius` の影響調査を足す        |
| gstack と pstack                         | gstack の技術設計のスキルは、計画をレビューする `/plan-eng-review`（明示だけ）だけ（`/autoplan` は無効）。技術設計は superpowers と pstack。今のブランチの差分のレビューは gstack の `/review` | `/review` の後に `/pstack:interrogate`（高リスクだけ）                          |
| understand-anything と pstack            | understand-anything はリポジトリ全体のグラフを作って何度も使う。`/pstack:how` は 1 つの領域を 1 回説明する                                                                                     | 同じ質問に両方は使わない                                                        |
| crit と gstack                           | `/crit-review` は人間の承認で、CLAUDE.md が必須と定めている。gstack の `/plan-ceo-review`・`/office-hours` は AI の計画レビューで、任意                                                        | AI のレビューを先に済ませてから `/crit-review`                                  |
| gstack `/review` と `/code-review`       | `/review` は今のブランチと merge-base の差分を見て直す。`/code-review medium <PR の URL>` はチェックアウトせずに PR の差分を読み、直さない（今のブランチ以外の PR）                            | 同じ差分に重ねない。`/review` と打つと gstack が起動する                        |
| gstack `/review` と pstack `interrogate` | `/review` は専門家の観点で広く見て直す。`interrogate` は壊せるかを実行で示し、直さない                                                                                                         | 高リスクで、`/review` の後に実行で確かめたい不変条件が残るとき                  |
| gstack `/codex` と pstack `interrogate`  | どちらも別の視点だが、独立したモデルは Codex だけ（`interrogate` は Claude 同士）。`/codex` は Bash から拒否されるので、ユーザーが通常のターミナルで `codex review` を実行する                 | 複雑・高リスクでは Codex を提案する。`interrogate` は実行で示したいときだけ足す |

<a name="by-size"></a>

## D. 規模別の推奨構成

| 規模           | 構成                                                                                                                                                                                                                                                                                                                                                               | 終わり                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| 軽微な修正     | スキルなし。直してテストか確認コマンドを実行する                                                                                                                                                                                                                                                                                                                   | テストが通る。PR にするなら `/crit-review`        |
| 通常の機能開発 | `test-driven-development` → `/review` → `/crit-review` → PR                                                                                                                                                                                                                                                                                                        | `/review` の指摘に対応した                        |
| 複雑な機能開発 | `brainstorming` → `writing-plans` → `/crit-review` → 実装（TDD。独立したタスクが多ければ `subagent-driven-development`）→ `/review` → Codex → `/crit-review` → PR                                                                                                                                                                                                  | plan の完了条件を満たし、レビューの指摘に対応した |
| 高リスク変更   | 複雑の構成に足す: 実装の前に `/pstack:blast-radius`、セキュリティの境界なら `/security-review`、ロールバックの手順、必要なら `/pstack:interrogate`                                                                                                                                                                                                                 | ロールバックの手順と、影響の確認の結果がそろった  |
| 障害調査       | `systematic-debugging`（読み取りだけ）→ 必要なら `/pstack:why` → 原因と修正案を報告する。本番を変える操作は別に承認を得る                                                                                                                                                                                                                                          | 原因を根拠つきで説明でき、再現テストがある        |
| 独立レビュー   | `/review` の指摘を直した後に、ユーザーが通常のターミナルで `codex review ...` を実行する。セキュリティの境界か設計判断を含むなら、challenge（`codex exec`）も 1 回実行する。Claude は Codex の記録から全回の最終メッセージを読み（[rules/SKILL_ROUTING.md](rules/SKILL_ROUTING.md) の Exit criteria）、1 回ずつ test-report に記録してから、採用と不採用を整理する | 1 PR あたり 5 回まで（challenge も数える）        |

<a name="examples"></a>

## E. 利用例

| 依頼の例                                                                                      | 期待する選択                                                                                                                                                |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 「この Rails API の処理フローを調査し、関連するサービス・モデルと実行経路を整理してください」 | スキルなしで読んで答える。領域全体を初めて見るなら `/pstack:how` を提案する                                                                                 |
| 「このリポジトリに今日から参加する。全体像を把握したい」                                      | `/understand-anything:understand` を提案し、作った後は `understand-onboard`                                                                                 |
| 「なぜこのテーブルは論理削除なのか」                                                          | `/pstack:why` を提案する。Claude 自身は `git log` で調べてもよい                                                                                            |
| 「ユーザー一覧 API にページネーションを追加して。既存の注文一覧と同じ形で」                   | 通常: spec を更新 → `test-driven-development` → `/review`                                                                                                   |
| 「このメソッドの nil チェック漏れを直して」（原因が明らか）                                   | 軽微: スキルなし。再現テストを書いて直す                                                                                                                    |
| 「本番で 502 が出ている。原因を調べて」                                                       | `systematic-debugging`。調査は読み取りだけで、本番の変更は承認を得てから                                                                                    |
| 「OIDC と SAML の共通認証基盤に、Cognito のグループからロールを引く処理を足したい」           | 複雑かつ高リスク: `brainstorming` → `writing-plans` → `/crit-review` → `/pstack:blast-radius` を提案 → 実装 → `/review` → `/security-review` → Codex を提案 |
| 「orders テーブルの status を enum に変えたい。既存データと API の互換性を保って」            | 高リスク: `writing-plans`（移行とロールバック）→ `/crit-review` → `/pstack:blast-radius` を提案 → TDD → `/review` → Codex を提案                            |
| 「この PR をレビューして」（今のブランチの PR）                                               | `/review`。高リスクなら `/pstack:interrogate` と Codex を提案する                                                                                           |
| 「#123 をレビューして」（今のブランチ以外の PR）                                              | `gh pr view 123 --json url` で URL にし、`/code-review medium <URL>`。チェックアウトしない。高リスクでも `/security-review`・Codex は使わない               |
| 「ALB のリスナーに Cloudflare からの通信だけを許可する Terraform を書いて」                   | 高リスク: `writing-plans` → `terraform plan` まで → `/security-review` → Codex を提案。apply はしない                                                       |
| `/socratic-tutor OAuth。認可コードフローから。目標は 4/5`                                     | 診断の質問（1 問ずつ 3〜5 問）→ 習熟度の表 → 弱い項目から問答。中断は `save state`、次のセッションで `resume from:` に続けて貼って再開する                  |
| `/socratic-tutor このリポジトリの認証の流れ。コードを読んで根拠にして`                        | コードを読んでから問題を出す。社内のコードや学習データより新しい仕様は、根拠を指定しないと誤った問題や判定になりうる                                        |
| 「設定画面のダイアログを、背景のクリックでも閉じられるようにして」                            | `modern-web-guidance` で `search` → `retrieve` してから実装する。応答の末尾に、使ったガイドの `### Modern Web Guidance` の節が付く                          |
| 「この拡張機能を Chrome Web Store に出したい。権限の説明も書いて」                            | `chrome-extensions` の公開の参照ファイル（審査のチェックリスト・掲載情報・プライバシーポリシー）を読んで書く                                                |

<a name="update"></a>

## F. スキル・プラグインのアップデート

通常のターミナルで下記を実行する。

```sh
/bin/bash ~/dotfiles/claude/scripts/update-skills.sh
```

dotfiles 内では mise タスクとして実行できる。

```sh
mise run claude:update
```

gstack・プラグイン・crit の CLI を更新し、modern-web-guidance の新しい版を知らせるときの流れ。`update-skills.sh` の説明は [README.md の「スキル・プラグインのアップデート」](README.md#setup-update)、理由と提供元ごとの注意は [SKILL_INVENTORY.md の「更新したときの見直し」](SKILL_INVENTORY.md#upgrade) にある。

| #   | すること                                               | 誰が・どこで                                      | コマンド・スキル                                                                                 |
| --- | ------------------------------------------------------ | ------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 1   | まとめて更新する                                       | ユーザーが通常のターミナルで                      | `/bin/bash ~/dotfiles/claude/scripts/update-skills.sh`（dotfiles では `mise run claude:update`） |
| 2   | 入っている状態と文書を照合し、違いがあれば文書を直す   | Claude が dotfiles のセッションで（再起動の前に） | `/sync-skill-docs`（「gstack を更新した」と伝えるだけでもよい）                                  |
| 3   | スナップショットを作り直す（2 で文書を直したときだけ） | ユーザーが通常のターミナルで                      | 2 の最後に Claude が示す `/usr/bin/python3 -B <root>/claude/scripts/skills-check.py snapshot`    |
| 4   | 文書の差分を承認する                                   | ユーザーが Crit で                                | 2 の最後に Claude が開く `/crit-review`                                                          |
| 5   | Claude Code を再起動する                               | ユーザー                                          | 更新した hooks とプラグインは、再起動した後のセッションで読み込まれる                            |

- 1 は Claude Code のプロンプトの `!` で実行しない。`!` はセッションによっては sandbox の中で動き、更新も cc-crit の profile テストも失敗する。
- 1 で、確認が要るプラグイン（マーケットプレイスが宣言したインストールコマンドが変わったもの）は失敗に数えられる。通常のターミナルで `claude plugin update <id> --scope user` を実行する。
- 1 の最後に「取り込みを待つ更新: modern-web-guidance」と出たら、npm に新しい版がある（何も書いていない）。取り込むときは、中身を `--out <dir> --latest` で確かめてから、作業ブランチで `--apply` を実行し、PR にしてマージしてから `mise install` を実行する（[SKILL_INVENTORY.md の提供元ごとの注意](SKILL_INVENTORY.md#upgrade-source)）。
- gstack の新しい版があるかだけを見るなら、zsh の `gstack-upgrade --check`。Claude Code の `/gstack-upgrade` で更新したときは、後で通常のターミナルで `/usr/bin/python3 -B ~/dotfiles/claude/scripts/settings-home-paths.py` を実行する（gstack が `claude/settings.json` に書いた絶対パスを `~/` に戻す）。
- 2 で Claude は `claude/settings.json` を直さず、提案だけをする（増えた gstack のスキルの `skillOverrides` など）。採るかはユーザーが決めて編集する。
