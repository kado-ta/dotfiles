# Claude Code のスキル・プラグイン棚卸し

入っているプラグイン・スキル・エージェント・hooks・MCP の一覧と、その状態・制約を書く。スキルの選び方の規則は [rules/SKILL_ROUTING.md](rules/SKILL_ROUTING.md)（毎回読み込まれる）、タスク別の早見表は [SKILL_CHEATSHEET.md](SKILL_CHEATSHEET.md) にある。重複の裁定の根拠は [作業文書](../docs/work/20261116_skill-role-division/research-routing.md) にある。

- 時点: 2026-11-16。2026-11-23 に gstack 1.102.2.0 と pstack 0.15.46 への更新、個人スキル `/socratic-tutor`・`modern-web-guidance`・`chrome-extensions` の追加、gstack 1.103.0.0 への更新（`verify` を `build-check` に改名）を反映した。2026-11-24 に pstack 0.15.47 への更新（`reframe` の追加）を反映した。2026-11-25 に gstack 1.103.1.0・pstack 0.15.48・crit 1.8.18 への更新（スキルの増減なし）を反映した。2026-11-26 に個人スキル `/pm-assist` の追加と、gstack 1.103.3.0 への更新（スキルの増減なし）を反映した。2026-11-27 に workbook-intake 0.1.1（別リポジトリの local スコープ）の追加を反映した。Claude Code の版は 2.1.330（2026-11-23 に確認）。各スキルの SKILL.md・設定・hooks の実物を読んで書いた。
- この文書は `~/.claude` にリンクされない。Claude のコンテキストには載らない。
- プラグインやスキルを更新したら、[更新したときの見直し](#upgrade)に従って直す。

<a name="legend"></a>

## 凡例

| 列 | 値 | 意味 |
| --- | --- | --- |
| 起動 | 自動 | 説明文が Claude に見え、Claude が自分で起動できる |
| | 明示 | ユーザーが `/` で入力したときだけ動く（`disable-model-invocation: true` か `user-invocable-only`） |
| | 提案 | Claude は起動できるが、規則で「自分では起動せず提案する」にしている |
| 状態 | 有効 | 制限なし |
| | 制限 | `user-invocable-only`、`permissions.deny`、または規則で使う場面を絞っている |
| | 無効 | `skillOverrides` で `off`。Claude からも `/` からも呼べない |
| | 方針で使わない | 呼べるが、役割分担で使わないと決めた |

- スキル・エージェント・コマンドの名前はコード書式で書く。提供元（superpowers、gstack、pstack など）の名前は書式を付けない。

<a name="sources"></a>

## 提供元

| 提供元 | 版 | 入れ方・スコープ | スキル | エージェント | hooks | 更新 |
| --- | --- | --- | --- | --- | --- | --- |
| superpowers | 7.0.2 | プラグイン（claude-plugins-official）、user | 15 | 0 | SessionStart | `/plugin` |
| gstack | 1.103.3.0 | `git clone` で `~/.claude/skills/gstack`。プラグインではないので、名前に接頭辞が付かない | 64（有効 25、明示 8、無効 31） | 0 | スキルの frontmatter だけ | `update-skills.sh` か zsh の `gstack-upgrade`（sandbox の外） |
| pstack | 0.15.48 | プラグイン（cursor-plugins）、user | 59 | 2（deny） | なし | `/plugin`（自動更新 off） |
| understand-anything | 2.9.8 | プラグイン、user | 9 | 11 | SessionStart、PostToolUse | `/plugin`（自動更新 on） |
| crit | 1.8.18 | プラグイン、user。CLI は 0.24.0 | 3 | 0 | PermissionRequest | `/plugin` と Homebrew |
| claude-code-setup | 1.0.0 | プラグイン、user | 1 | 0 | なし | `/plugin` |
| ruby-lsp | 1.0.0 | プラグイン、user | 0（LSP だけ） | 0 | なし | `/plugin` |
| 個人スキル | — | dotfiles の `claude/skills/` を `~/.claude/skills/` にリンク | 8 | 0 | なし | dotfiles（`modern-web-guidance`・`chrome-extensions` は `update-skills.sh`） |
| dotfiles の project スキル | — | dotfiles の `.claude/skills/`。dotfiles で起動したセッションだけで使える | 1 | 0 | なし | dotfiles |
| 組み込み・claude.ai | — | Claude Code に同梱、または claude.ai のアカウントから提供 | 下の表 | 7 | — | Claude Code の更新 |
| salesforce-development | 2.5.0 | プラグイン、別リポジトリの local スコープ。このリポジトリでは無効 | — | — | — | — |
| workbook-intake | 0.1.1 | プラグイン（workbook-intake）、別リポジトリの local スコープ。このリポジトリでは無効。マーケットプレイスは `settings.json` でコミットの SHA に固定 | 1 | 1 | PreToolUse（xlide）、PostToolUse（AskUserQuestion） | [README の手順](README.md#workbook-intake-update)（`update-skills.sh` の対象外） |

- プラグインも `claude/scripts/update-skills.sh` でまとめて更新できる（user スコープのもの。ID が `@builtin` で終わる、Claude Code に同梱されたプラグインは、本体と一緒に更新されるので除く。crit は CLI も）。表の「更新」は、個別に更新するときの方法。手順は[更新したときの見直し](#upgrade)にある。
- superpowers・claude-code-setup・ruby-lsp・understand-anything には、dotfiles を projectPath とする project スコープの重複登録があった（`installed_plugins.json`）。2026-11-16 に `claude plugin uninstall <名前> --scope project --keep-data` で消した。登録日の 2026-10-05 は `claude/` が `.claude/` という名前で、ユーザー設定がプロジェクト設定としても読み込まれていたためと推測する。`claude plugin list` に `Scope: project` が再び出たら、同じ手順で消す。
- `~/.claude/commands/` と `~/.claude/agents/` はない。有効なプラグインにコマンドはない（`commands/` を持つのは salesforce-development だけ）。

<a name="superpowers"></a>

## superpowers（15）

呼び出しは `/superpowers:<名前>`。すべて Claude から起動できる。`using-superpowers` は SessionStart（startup・clear・compact。resume では動かない）で毎回注入され、「1% でも当てはまれば起動」と指示する。同じ文書は「CLAUDE.md などユーザーの指示がスキルより優先する」とも書いている。

| スキル | 機能（入力 → 出力） | 起動 | 状態 | 依存・制約 |
| --- | --- | --- | --- | --- |
| `brainstorming` | 対話で要件と設計を固める → design | 自動 | 有効 | 設計の承認前に実装しない（HARD-GATE）。軽微な作業の例外がある。次は `writing-plans`。保存先は DOCUMENTS.md に従い `docs/work/YYYYMMDD_<ID>_<slug>/design.md` |
| `writing-plans` | 仕様 → タスクに分けた実装計画 | 自動 | 有効 | 保存先は `docs/work/YYYYMMDD_<ID>_<slug>/plan.md` |
| `executing-plans` | 計画をこのセッションで自分で実行する | 自動 | 有効 | — |
| `subagent-driven-development` | 計画のタスクごとにサブエージェントで実装し、タスクごとにレビューする | 自動 | 有効 | サブエージェントが多い。独立したタスクが多い大きな計画のときだけ |
| `dispatching-parallel-agents` | 独立した 2 つ以上の作業を並列のサブエージェントに分ける | 自動 | 有効 | — |
| `test-driven-development` | 失敗するテスト → 実装 → リファクタ | 自動 | 有効 | 振る舞いを変えるとき。文書や設定だけの変更には当たらない |
| `systematic-debugging` | 再現 → 原因の切り分け → 仮説の検証 → 修正 | 自動 | 有効 | — |
| `verification-before-completion` | 完了と言う前に検証コマンドを実行し、結果を示す | 自動 | 有効 | — |
| `requesting-code-review` | レビュー役のサブエージェントに差分のレビューを頼む | 自動 | 制限 | 今のブランチの差分のレビューは `/review` に一本化。`subagent-driven-development` の中のタスク単位のレビューは別 |
| `receiving-code-review` | 受けた指摘を検証してから対応する | 自動 | 有効 | — |
| `using-git-worktrees` | 隔離した作業ツリーを作る | 自動 | 制限 | sandbox では `.git/worktrees` が読み取り専用で `git worktree add` が失敗する |
| `finishing-a-development-branch` | 統合の方法を選ぶ（merge・push と PR・残す・捨てる） | 自動 | 制限 | `git push -u origin` と PR 作成の手順は CLAUDE.md の Git 節（cc-safe-push・cc-safe-pr）と合わないので使わない |
| `writing-skills` | スキルをテスト駆動で作る・直す | 自動 | 有効 | — |
| `using-superpowers` | スキルの探し方と使い方 | SessionStart で注入 | 有効 | 「1% ルール」は [SKILL_ROUTING.md](rules/SKILL_ROUTING.md) の「使わない」原則が優先する |
| `diagnosing-superpowers` | superpowers のセッションの不調を診断し、バグ報告を作る | 自動 | 有効 | — |

<a name="gstack"></a>

## gstack（64）

呼び出しは `/<名前>`（接頭辞なし）。`proactive=core` なので、頼まれずに提案するのは `/office-hours`・`/review`・`/qa`（と無効の `/ship`）だけ。`codex_reviews=disabled`（2026-11-23 から。外部レビューの段でリポジトリの内容を Codex に送らない。Codex はユーザーが通常のターミナルで実行する。名前で呼んだ `/codex` は動く）。多くのスキルが共通の前処理で `~/.gstack/` に記録を書くが、`~/.gstack/projects` と `~/.gstack/security/cso` 以外は sandbox で書けず、失敗は無視される。

1.102.1.0 から、Claude Code はスキルを読み込むときに SKILL.md の `` !`…` `` の行を実行する。これで `bin/gstack-skill-load` が共通の前処理と開始の処理を動かす。各スキルの `allowed-tools` がこのコマンドを許可している。sandbox の中で動くかは確かめていない。1.100.0.0 から、説明文に「いつ使うか」の節が付いた（Claude が `/review` などを読み込みやすくするため）。

<a name="gstack-enabled"></a>

### 有効（25）

| スキル | 機能（入力 → 出力） | 起動 | 状態 | 書き込み・依存・制約 |
| --- | --- | --- | --- | --- |
| `review` | ベースブランチとの差分（未 commit・未追跡も含む）をレビューし、直す | 自動 | 有効 | 専門のサブエージェント（テスト、保守性、セキュリティ、API の契約、マイグレーションなど）を並列に起動し、自動で直せるものは直す。commit・push はしない。レビュー bot のコメントがあると PR に返信を投稿する（sandbox では 403）。Codex の段は `codex_reviews=disabled` で飛ばし、Claude の敵対的レビューだけを行う |
| `codex` | Codex CLI による別モデルの意見（review・challenge・consult） | 自動 | 制限 | ファイルは変えない。Bash から `codex exec` を呼ぶので、auto モードの判定で拒否された記録がある（2026-11-11）。独立レビューは、ユーザーが通常のターミナルで `codex review` を実行する（`!` では 2026-11-18 から、app-server の初期化が `Operation not permitted` で失敗している）。2026-11-21 から、セキュリティの境界・設計判断を含む変更では challenge（`codex exec`）も通常のターミナルで実行してもらい、結果は Claude が Codex の記録から全回分を読む。crit-sandbox の設計で `codex review` は指摘なし、challenge は P1 を 6 件挙げたことと、PR #46 で P1 が後の実行の結果に埋もれたため |
| `cso` | セキュリティ監査。範囲（`--infra`・`--code`・`--supply-chain`・`--owasp` など）と `--diff` を選べる | 自動 | 制限 | 規則でユーザーが指定したときだけにしている。sandbox では静的な監査だけで、`.env.example` などを追跡しているリポジトリでは失敗する（[`/cso` を sandbox で使う](#cso-sandbox)）。ソースはすべてランチャー経由で読む |
| `qa` | サイト・API・CLI を試し、見つけたバグを直して確かめる | 自動 | 有効 | 修正ごとに commit する（作業ツリーが汚れていれば commit か stash を尋ねる）。ブラウザは Aside か gstack のヘッドレスブラウザ。後者は localhost で待ち受けるので sandbox では動かない |
| `qa-only` | `qa` の報告だけ | 自動 | 有効 | 直さない、commit しない。ブラウザの制約は `qa` と同じ |
| `browse` | 1 回だけのブラウザ作業（開く、操作、スクリーンショット、console） | 自動 | 有効 | ブラウザの制約は `qa` と同じ。Aside が sandbox で動くかは未確認。1.103.3.0 から、Aside で保存するファイル（スクリーンショット・PDF）は、`bin/gstack-aside-repl`（bun）がスクリプトの標準出力から取り出して `--out` の場所（`browse` の既定はリポジトリの `.gstack/browse-reports/`）に書く。Aside がスクリプトの終わりに作業フォルダを消すため。`qa`・`design-review`・`canary` なども同じ経路を使う（保存先はスキルごとに違う）。Claude が直接ブラウザを操作するときは Playwright MCP を使う（CLAUDE.md の Tools 節）ので、gstack のスキルの中で使う |
| `benchmark` | ページの性能を測り、ベースラインと比べる | 自動 | 有効 | ブラウザが必要 |
| `canary` | デプロイ後にページを定期的に確かめる | 自動 | 有効 | ブラウザが必要。長く待つ |
| `office-hours` | 対話で「何を作るか」を詰め、設計文書を作る | 自動 | 有効 | 設計文書だけを書く。既定の保存先は `docs/designs/` と `~/.gstack/projects/`。DOCUMENTS.md が優先する。2 つ目の意見とデザイン案の Codex の段は、`codex_reviews=disabled` で尋ねずに飛ばす |
| `plan-ceo-review` | 計画をスコープと戦略の観点でレビューする（11 節。1 節目はアーキテクチャ） | 自動 | 有効 | 計画ファイルを編集する。外部レビュー（Codex）の段は `codex_reviews=disabled` で飛ばす |
| `plan-design-review` | 計画を UI・UX の観点で 0〜10 点で評価し、足りない決定を書き足す | 自動 | 有効 | 画像生成（OpenAI か Gemini の鍵）と localhost の比較ボードを使う。外部の意見の Codex の段は `codex_reviews=disabled` で飛ばし、Claude 側だけで行う |
| `design-consultation` | デザインシステム一式を提案し、DESIGN.md にまとめる | 自動 | 有効 | 画像生成、`/tmp` と `open` を使う（sandbox で不可）。外部の意見の Codex の段は `codex_reviews=disabled` で飛ばし、Claude 側だけで行う |
| `design-shotgun` | デザイン案を複数作って比べる | 自動 | 有効 | 画像生成、localhost の比較ボード |
| `design-html` | 承認済みのデザインから HTML/CSS を作る | 自動 | 有効 | localhost で待ち受ける |
| `design-review` | 稼働中のサイトの見た目を監査し、直す | 自動 | 有効 | 1 件ごとに commit する（`--build` は commit しない）。ブラウザが必要。外部の意見の Codex の段は `codex_reviews=disabled` で飛ばし、Claude 側だけで行う |
| `diagram` | 説明文か mermaid から図を作る | 自動 | 有効 | 描画で localhost に待ち受ける |
| `make-pdf` | Markdown から PDF を作る | 自動 | 有効 | 既定の出力先 `/tmp` と描画の待ち受けが sandbox で不可 |
| `health` | 型チェック・lint・テストなどを実行して点数にする | 自動 | 有効 | 直さない |
| `build-check` | リポジトリが宣言した検査とテストを、通るまで直しながら回す | 自動 | 有効 | 1.103.0.0 で `verify` から改名した。検査は CLAUDE.md の `gstack:verify:` 行（名前は変わっていない）、package.json などから探す。宣言がなければ何もしない（dotfiles では検査なし）。引数 `quick`・`pre-commit` は、commit の前の簡易の検査だけを行う |
| `test-audit` | 価値の低いテストと、それを残すためだけのコードを探す | 自動 | 有効 | 承認したまとまりだけ編集する |
| `deslop-shared-libs` | 最近の commit から共通化する価値のある箇所を挙げる | 自動 | 有効 | 読み取りだけ |
| `retro` | 期間内の commit と PR を振り返る | 自動 | 有効 | global モードは `~/.gstack/retros/` に書くので不可 |
| `context-save` | 作業状態を保存する | 自動 | 有効 | `~/.gstack/projects/<slug>/checkpoints/` |
| `context-restore` | 保存した作業状態を読み込む | 自動 | 有効 | 読み取りだけ |
| `gstack-upgrade` | gstack を更新する | 自動 | 有効 | `~/.claude/skills` に書くので sandbox の外で実行する |

<a name="gstack-limited"></a>

### 明示だけ（8。`user-invocable-only`）

| スキル | 機能 | 理由 |
| --- | --- | --- |
| `plan-eng-review` | 計画を、アーキテクチャ・データの流れ・境界条件・テスト・性能の観点でレビューし、計画ファイルを直す。`.gstack/tmp/` と `.git/info/exclude` に書き、Web の調査は Aside を使う。外部レビュー（Codex）の段は `codex_reviews=disabled` で飛ばす | 説明文が「機能を作る前に計画するとき」で、`brainstorming`・`writing-plans` と同じ場面に当たる。1.99.5.0 で戻った（2026-11-23） |
| `document-release` | 差分に合わせて README・CHANGELOG などを直し、commit・`git push`・PR の本文とタイトルの編集まで行う。Codex のレビューの段は `codex_reviews=disabled` で飛ばす | push と PR 編集が止まる。説明文の一致で自動起動させない（2026-11-16） |
| `document-generate` | 足りない文書を一から書き、commit・`git push` まで行う | 同上 |
| `spec` | 曖昧な要望を 5 段階で spec にし、GitHub Issue を作る。品質の判定の Codex の段は `codex_reviews=disabled` で飛ばす | Issue 作成が止まる。既定で `git worktree add` と `claude -p` を使う |
| `careful` | 危険なコマンドの前に警告する（スキルの hooks） | 手動で使う |
| `guard` | `careful` と `freeze` を合わせたもの | 手動で使う |
| `freeze` | 編集できるディレクトリを絞る | 手動で使う |
| `unfreeze` | `freeze` を解く | 手動で使う |

<a name="gstack-off"></a>

### 無効（31。`off`）

`ios-qa`、`ios-fix`、`ios-design-review`、`ios-sync`、`ios-clean`、`ship`（commit・`git push`・PR 作成）、`land-and-deploy`（PR のマージとデプロイの見守り）、`setup-deploy`、`landing-report`、`modernize`（rebase と `git push --force-with-lease`）、`connect-chrome`、`open-gstack-browser`、`setup-browser-cookies`、`pair-agent`、`scrape`、`skillify`、`autoplan`（CEO・デザイン・DX・エンジニアリングのレビューを続けて流す）、`plan-devex-review`、`devex-review`、`setup-gbrain`、`sync-gbrain`、`ubicloud`、`benchmark-models`、`eval-plan`、`gstack`（ルート）、`_gstack-command`、`plan-tune`、`learn`、`runaway-stopper`、`write-skill`、`design-motion`。

- `/investigate` は gstack で廃止された（CHANGELOG）。技術設計のレビューは、1.99.5.0 で戻ったスキルを[明示だけ](#gstack-limited)で使う。

<a name="cso-sandbox"></a>

### `/cso` を sandbox で使う

保存先 `~/.gstack/security/cso/` だけを sandbox の書き込み許可に入れている。理由は [CLAUDE_CONFIG.md](../.claude/rules/CLAUDE_CONFIG.md#cso-state) にある。

- 動くのは静的な監査だけ。スキャナ 6 種と `--comprehensive` は Docker が要るので、前提条件の不足として記録される。
- `--doctor` の static-snapshot は missing と出るが、監査（`start`）は動く。ランチャーが `TMPDIR` を渡さず、`/tmp` に書こうとするため。
- sandbox が読めないファイルを、追跡しているか、無視されていない未追跡として持つリポジトリでは、`start` が `INVALID_SCHEMA` で失敗する。読めないファイルは `permissions.deny` の `Read(...)` で決まる（`.env*`・`*.pem`・`*.key`・`credentials`・`id_rsa*`・`id_ed25519*`・`.ssh/`・`.aws/`・`.pgpass`）。helper は秘密ファイルも一度読んでマスキングし、写しを保存するため。`.gitignore` で無視したファイルは問題ない。

1.103.0.0 の CHANGELOG によると、`.env.example` のような秘密ファイルに似た名前のファイルと、`/cso` がもともと監査から外すファイル（依存・ツールの状態・エージェントの設定）は、読めなくても「読めなかった」と記録して監査を続けるようになった（#4395）。それ以外の読めないファイルでは、今も止まる。この環境ではまだ確かめていないので、下の手順を残す。

失敗するリポジトリでは、追跡中で変更のないファイルを一時的に消してから監査する。消したファイルは「履歴だけで評価」と記録され、結果は `partial` になる。`--diff` では、この削除も差分に入る。2026-11-16 に、`.env.example` を 1 つ追跡する検証用のリポジトリで確かめた。

1. Claude が、対象のファイルの名前だけを調べる（中身は読まない）。

   ```sh
   git ls-files -co --exclude-standard -- ':(glob)**/.env*' ':(glob)**/id_rsa*' ':(glob)**/id_ed25519*' ':(glob)**/.ssh/**' ':(glob)**/.aws/**' ':(glob)**/credentials' ':(glob)**/credentials/**' ':(glob)**/*.key' ':(glob)**/*.pem' ':(glob)**/.pgpass'
   ```

2. ユーザーが通常のターミナルで消す。Claude からは書き込み拒否で消せない。Claude Code のプロンプトの `!` は、セッションによっては sandbox の中で動き、同じく消せない。次のコマンドは、未追跡のファイルか変更のあるファイルが 1 つでも混じると、何も消さない。未追跡か変更があるファイルは、ユーザーがリポジトリの外へ移して、後で戻す。

   ```sh
   cd <repo> && git ls-files --error-unmatch -- <files> >/dev/null && git diff --quiet HEAD -- <files> && rm -- <files>
   ```

3. `/cso` を実行する。
4. ユーザーが通常のターミナルで戻し、`git status` で消えたままのファイルがないことを確かめる。

   ```sh
   cd <repo> && git restore -- <files> && git status --short
   ```

sandbox の外で `/cso` を実行すると、保存先に秘密ファイルの写しが残り、7 日後に sandbox の中で動く掃除が止まる。そのときは、sandbox の外で古い実行（`~/.gstack/security/cso/<repo>/<run>`）を消す。

<a name="pstack"></a>

## pstack（59）

呼び出しは `/pstack:<名前>`。`setup-pstack` 以外の 58 件は `disable-model-invocation: true` で、Claude からは起動できず、説明文も Claude に見えない。Claude Code ではすべて Claude のモデルで動く（Cursor の別モデルの指定は、セッションのモデルに置き換わる）。

| スキル | 機能 | 起動 | 状態 | 依存・制約 |
| --- | --- | --- | --- | --- |
| `how` | 「X はどう動くか」を、読み取り専用のサブエージェント 1 つで調べて説明する | 明示 | 有効（重点） | — |
| `why` | コミットと PR の議論から、作者が書いた意図を出典つきで示す | 明示 | 有効（重点） | `git`・`gh` の読み取り |
| `architect` | 設計案を複数作って合成し、実装まで進む | 明示 | 有効（重点） | 「with checkpoint」を付けると設計で止まる。付けないと確認なしで実装に進む |
| `blast-radius` | 差分の外で壊れうるものを探し、安全の根拠を実行で示す | 明示 | 有効（重点） | — |
| `interrogate` | 複数の敵役が変更を壊しにいき、実行で示せた指摘だけを残す | 明示 | 有効（重点） | 直さない。全員 Claude なので独立したモデルのレビューではない。worktree を使う |
| `arena` | 候補を並列に作り、基準で採点して土台を選び、ほかの良い部分を移す | 明示 | 有効（条件付き） | 審査役も Claude になる |
| `setup-pstack` | pstack が使うモデルを設定する（`~/.claude/rules/pstack-models.md` を書く） | 自動 | 制限（`Skill(pstack:setup-pstack)` を deny） | 書き込み先が公開リポジトリの `claude/rules/` になる |

- 依存（16。重点スキルが読む。直接は使わない）: `poteto-mode`、`in-your-own-words`、`unslop`、`principle-boundary-discipline`、`principle-encode-lessons-in-structure`、`principle-exhaust-the-design-space`、`principle-fix-root-causes`、`principle-foundational-thinking`、`principle-laziness-protocol`、`principle-make-operations-idempotent`、`principle-minimize-reader-load`、`principle-outcome-oriented-execution`、`principle-prove-it-works`、`principle-redesign-from-first-principles`、`principle-separate-before-serializing-shared-state`、`principle-subtract-before-you-add`。
- 方針で使わない（36）: `automate-me`、`benchmark-checklist`、`bro`、`correct`、`create-formal-verification-skill`、`create-verification-skill`、`figure-it-out`、`ketchup`、`ketchup-video`、`maintain-formal-verification-skill`、`maintain-verification-skill`、`make-bot-ui`、`no-comments`、`poteto-help`、`recall`、`reflect`、`reframe`、`sharpen`、`show-me-your-work`、`statechart`、`swarm`、`tdd`、`teach`、`technical-writing`、`typescript-best-practices`、`principle-attack-the-premise`、`principle-build-the-lever`、`principle-experience-first`、`principle-explain-the-number`、`principle-guard-the-context-window`、`principle-migrate-callers-then-delete-legacy-apis`、`principle-model-the-domain`、`principle-never-block-on-the-human`、`principle-sequence-verifiable-units`、`principle-test-behavior-not-implementation`、`principle-type-system-discipline`。入力すれば動く（deny はスラッシュコマンドを止めない）。
- 分類の理由は [pstack の導入の plan](../docs/work/20261114_pstack-skill-routing/plan.md#decisions) にある。
- `reframe`（0.15.47 で追加）は、作りたいものの説明から専門用語を 8〜12 個挙げ、隣の分野の用語も借りて、説明を書き直す。リンクを開いて確かめる（WebFetch）。何を作るかは `/office-hours`、要件の整理は `brainstorming` が主担当なので、`sharpen`・`teach` と同じく方針で使わない。依存のスキルを読まず、重点スキルからも読まれない。0.15.48 で、説明が 2〜3 個の別の問題に読めるときは、先に候補と見分け方を挙げ、いちばん見込みのあるものを選んでから用語を挙げるようになった。

<a name="understand-anything"></a>

## understand-anything（9）

呼び出しは `/understand-anything:<名前>`。すべて Claude から起動できる。グラフはリポジトリの `.ua/` に保存する（`.understand-anything/` があればそちら）。`.gitignore` には入らない。

| スキル | 機能 | 起動 | 状態 | 依存・制約 |
| --- | --- | --- | --- | --- |
| `understand` | リポジトリ全体の知識グラフを作る | 提案 | 制限 | エージェントを多数起動する（`file-analyzer` は最大 5 並列）。初回は重い |
| `understand-chat` | グラフで質問に答える | 自動 | 有効 | グラフが前提 |
| `understand-explain` | ファイル・関数・モジュールを深く説明する | 自動 | 有効 | グラフが前提 |
| `understand-diff` | 差分の影響を説明する | 自動 | 有効 | グラフが前提 |
| `understand-onboard` | 新しいメンバー向けのガイドを作る | 自動 | 有効 | グラフが前提 |
| `understand-domain` | 業務ドメインと処理の流れのグラフを作る | 自動 | 有効 | — |
| `understand-dashboard` | グラフのダッシュボードを開く | 自動 | 制限 | localhost で待ち受けるので sandbox では動かない |
| `understand-figma` | Figma のファイルからデザインのグラフを作る | 自動 | 有効 | Figma のトークンが必要 |
| `understand-knowledge` | Karpathy 型の LLM wiki からグラフを作る | 自動 | 有効 | — |

<a name="crit"></a>

## crit（3）・個人スキル（8）・project スキル（1）

| スキル | 機能 | 起動 | 状態 | 依存・制約 |
| --- | --- | --- | --- | --- |
| `/crit-review`（個人） | ファイルかブランチの差分を Crit で開き、人間のレビューを待つ | 自動 | 有効 | root 所有のラッパー `cc-crit` を使う。CLAUDE.md が、plan の承認と push・PR の前に使うと定めている |
| `/crit:crit` | Crit の対話レビュー | 明示（説明文で限定） | 制限 | sandbox では `~/.crit` に書けず、localhost で待ち受けられないので動かない。`/crit-review` を使う |
| `crit:crit-cli` | Crit のコメントを読み書きする | 自動（`/` には出ない） | 制限 | 同上。`crit comment` は直接実行しない |
| `/crit:crit-story` | Crit のストーリーを作る | 明示（説明文で限定） | 制限 | 同上 |
| `/commit-staged-pr`（個人） | ステージ済みの変更だけを commit し、push と PR まで進める | 自動 | 有効 | cc-safe-push・cc-safe-pr を使う |
| `code-style`（個人） | 命名・品質・スタイルの規則 | 自動 | 有効 | 全リポジトリに当たる個人の既定。リポジトリの規約・formatter・linter を優先する |
| `salesforce-help`（個人） | help.salesforce.com の記事を読む | 自動 | 有効 | — |
| `/socratic-tutor`（個人） | 1 つのテーマを、診断・習熟度の表（0〜5）・1 問ずつの問答・最終試験で教える | 明示 | 有効 | janestreet/agent_skills の `7c6715c`（2026-11-03）の写し。MIT なので `LICENSE.md` を同梱した。frontmatter に `disable-model-invocation: true` だけを足した（日本語の「〜について教えて」での誤起動を避けるため）。規則に載せていないので、Claude は起動も提案もしない。pstack `teach`（説明型。方針で使わない）とは役割が別 |
| `modern-web-guidance`（個人） | Web 標準の書き方のガイド（HTML・CSS・クライアントの JS）を、CLI で検索・取得する。既存のコードの古い書き方の検出（`legacy-scan`）もある | 自動 | 有効 | npm の `modern-web-guidance` の SKILL.md を、`claude/scripts/update-modern-web-guidance.py` が変換した写し（Apache-2.0。`LICENSE.md` を同梱）。手で編集しない。CLI は mise で版を固定する（`mise/mise_config.toml`）。コマンドに `DISABLE_TELEMETRY=1` を付けてテレメトリを止める（`settings.json` の `env` に置くと Claude Code の機能フラグも止まるため）。npx 系（`npx`・`pnpx`・`pnpm`・`bunx`・`bun`・`yarn`・`npm`・`deno`）での実行は `permissions.deny` で拒否する（`check-repo.py` の `modern-web-guidance` が確かめる。絶対パスや `sh -c` で包んだ形には当たらない）。説明文は「MANDATORY: Execute FIRST for all HTML/CSS and clientside JS tasks」で、応答の末尾に `### Modern Web Guidance` の節を付ける（どちらも原文のまま）。計画は [作業文書](../docs/work/20261123_modern-web-guidance/plan.md) |
| `chrome-extensions`（個人） | Chrome 拡張機能（Manifest V3）の開発と、Chrome Web Store への公開のガイド | 自動 | 有効 | 同じ npm の配布物から、手を加えずに写す（`LICENSE.md` を同梱）。参照ファイルは上流の名前のまま置く（`check-repo.py` の `markdown-names` の例外）。CLI とネットワークは使わない |
| `/pm-assist`（個人） | ゴールと期限のあるプロジェクトの現状・進め方・タスク・リスク・判断事項を整理する | 自動 | 有効 | 既定では書き込まない（保存は頼まれたときだけ。置き場所は DOCUMENTS.md の作業文書）。他の dotfiles の同名スキル（LICENSE なし）の考え方をもとに、文面は自分の言葉で書いた。起動の境界は description に書いた。起動テストの記録は [test-report.md](../docs/work/20261126_pm-assist-skill/test-report.md) にある |
| `/sync-skill-docs`（dotfiles の project） | スキル・プラグインの更新の後、この文書・チートシート・規則を入っている状態に合わせる | 自動 | 有効 | 照合は `mise run claude:skills-check`。スナップショットの作り直しはユーザーが通常のターミナルで行う |
| `/claude-code-setup:claude-automation-recommender` | Claude Code の自動化（hooks・スキル・MCP など）を勧める | 自動 | 有効 | 読み取りだけ |

- crit の plan-hook（PermissionRequest の ExitPlanMode）は、Plan Mode の plan を Crit で開く。そのときは `/crit-review` を使わない。

<a name="builtin"></a>

## 組み込み・claude.ai 提供

| スキル・コマンド | 機能 | 起動 | 状態・制約 |
| --- | --- | --- | --- |
| `/code-review` | 差分のバグを探す（`--fix`・`--comment` あり） | 自動 | 制限。今のブランチの差分は `/review` に一本化。今のブランチ以外の PR は、作者を問わず、チェックアウトせずに `/code-review medium <PR の URL>` で読む（`--comment`・`--fix` は付けない。下の箇条） |
| `/simplify` | 変更したコードの重複・簡素化を直す | 自動 | 有効 |
| `/security-review` | ブランチの未マージの変更のセキュリティレビュー | 自動 | 有効。セキュリティの境界に触れる変更で使う |
| `/init` | CLAUDE.md を作る | 自動 | 有効 |
| `/update-config` | settings.json を編集する | 自動 | 有効。dotfiles の `claude/settings.json` は Edit ツールで直す（Bash からは書けない） |
| `/fewer-permission-prompts` | よく使うコマンドを project の allow に足す | 自動 | 有効。dotfiles では `.claude/settings.json` に allow を足すと `check-repo.py` が失敗する |
| `/loop`・`/schedule` | 繰り返し実行・クラウドのルーティン | 自動 | 有効。クラウドのルーティンは手元のファイルを読めない |
| `/run` | アプリを起動して動作を確かめる | 自動 | 有効。サーバーは localhost で待ち受けられない |
| `/verify` | アプリをビルド・起動して、変更が意図どおり動くかを確かめる（テストや型チェックには頼らない） | 明示（Claude の一覧に出ない） | [公式ドキュメント](https://code.claude.com/docs/en/skills.md)の「Run and verify your app」に、`/run` とは別のスキルとしてある。2026-11-23 に、Claude のスキルの一覧に出ないことを確かめた（同じ名前の gstack のスキルは、1.103.0.0 で `build-check` に改名された）。ユーザーが `/verify` と打つと組み込みのスキルが起動する（2026-11-23、2.1.330 で確かめた）。記録した手順がないと、うまくいった手順を `.claude/skills/verify/SKILL.md` に書く（下の箇条） |
| `/claude-api`・`/workflow-authoring`・`/plugin-authoring`・`/keybindings-help` | 各分野の参照・作成 | 自動 | 有効 |
| `claude-in-chrome` | Chrome の拡張でブラウザを操作する | 自動 | 方針で使わない（CLAUDE.md） |
| `dataviz`・`artifact-design`・`artifact-diagramming`・`artifact-capabilities` | 図表と Artifact の作成 | 自動 | 有効 |
| `anthropic-skills:*`（13） | `built-in-browser`、`chrome-browser`、`computer-use`、`deep-research`、`docs`、`docx`、`google-workspace`、`import-memory`、`morning`、`pdf`、`pptx`、`skill-creator`、`xlsx` | 自動 | 有効。`deep-research` は技術調査の報告書を頼まれたときだけ（サブエージェントが多い） |
| `/doctor`・`/skill-doctor` | 設定とスキルの一覧の診断 | 明示（CLI のコマンド） | 有効 |

- 組み込みの `/code-review` は、別名 `review` を持つ（`aliases:["review"]`）。`/review` と打つと、同じ名前の gstack のスキルが優先される。gstack を消すか接頭辞を付けると、`/review` は黙って `/code-review` になる。
- gstack の `/review` と `/code-review` は、PR の扱いが違う（2026-11-23 に、2.1.330 の実行ファイルの文字列と gstack の SKILL.md で確かめた）。今のブランチ以外の PR は、作者を問わず、チェックアウトせずに `/code-review medium <PR の URL>` で読む（CLAUDE.md の Tools 節）。番号だけを渡されたら、`gh pr view <番号> --json url -q .url` で URL にする。
  - gstack の `/review` は PR 番号を受け付けない（`/review <番号>` と打っても番号は使われない）。今のブランチの `git merge-base origin/<base> HEAD` からの差分を見て、直す前提で動く（Fix-First）。ほかの PR に使うには、チェックアウトが要り、しかも書き換える。
  - `/code-review <PR番号>` は、差分を `gh pr diff <番号>` で読み、番号をカレントのリポジトリの PR として解決する（`pr diff` がない gh では `gh api repos/{owner}/{repo}/pulls/<番号>`）。URL で指定すると `gh pr diff <番号> -R <owner>/<repo>` で読む。どちらもチェックアウトは変えない。手元のファイルは、PR で追加された行を含むときだけ参照に使い、含まなければ差分だけで判断する。`--fix` は、その行を含むファイルにだけ当たる。
  - 番号で指定して差分が読めないと、`--fix`・`--comment` がなければ手元のブランチのレビューに切り替わり、指摘の前に「Could not read …: … was refused or failed. This review is of the checked-out branch instead, …」と書く。別のリポジトリの PR を番号で渡すと、手元のリポジトリに同じ番号の PR があれば、それを黙って読む。URL で指定したときと `--fix` を付けたときは、「…, so nothing was reviewed.」と書いて止まる。そのため URL で渡す。
  - sandbox の中で、公開の kado-ta/dotfiles の `gh pr diff` は通った（2026-11-23）。private の業務リポジトリでは確かめていない。
  - `--comment` は付けない。sandbox の `gh` は読み取り専用のトークンなので 403 になり、CLAUDE.md も GitHub への書き込みを禁じている。また、`--comment` を付けると、差分が読めなくても止まらず、手元のコードの指摘を PR に投稿しに行く。`--fix` も付けない（PR で追加された行を含む手元のファイルに、修正を当てる）。段階を省くと、ユーザーが前に打った段階（`low`〜`max`。`ultra` は保存されない）を使い回し、`max` が残りうるので、`medium` を明示する。
  - `/code-review ultra <PR番号>` は、クラウドが、Claude のアカウントにつないだ GitHub の権限で PR を clone する。手元の `gh` は、PR の大きさを見る `gh pr view --json additions,deletions,changedFiles` にだけ使う。手元の `gh` でログインしていても、アカウントに GitHub をつないでいなければ止まり（アクセスの確認が `github_not_connected`）、手元の GitHub CLI のログインを使ってつなぐコマンドを案内する。つなぐと、そのログインの権限をクラウドに渡す見込み（確かめていない）。gh の既定のスコープは `repo`・`read:org`・`gist` で、触れるすべてのリポジトリへの書き込みを含むので、渡す権限が大きすぎる。そのため、この方針では `ultra` を提案しない（2026-11-23 の Crit のレビューで決めた）。引数なしの `ultra` は手元のブランチを送る。料金もかかる。
  - 変更されたファイルの全体を読ませたい大きな PR も、手元には取り込まない。取り込むと、PR が変えた（またはベースのブランチで足された）`.claude/` の hooks・`.mcp.json`・`CLAUDE.md`・`AGENTS.md`・mise と direnv の設定と、それらが呼ぶスクリプトが、その作業ツリーで動く Claude Code・mise・direnv に読み込まれ、sandbox の外で動きうる。自動で動くファイルの参照先には上限がなく、`gh pr diff --name-only` の一覧では確かめきれない（2026-11-23 の Codex レビューの指摘で、取り込む手順をやめた）。全体が要るときは、人間が読む（`ultra` は上の理由で使わない）。
  - `/security-review`・`codex review --base`・`/pstack:interrogate` は、今のブランチ（手元のチェックアウト）の差分を見る。今のブランチ以外の PR には、高リスクでも使わない（PR を見ずに、手元のブランチを問題なしと報告しうる）。`/code-review` で読む（CLAUDE.md の Tools 節）。
- `/code-review` は、報告の後に `/verify` を続けて起動する指示を足すことがある（2026-11-23 に、2.1.330 の実行ファイルの文字列で確かめた）。次の 4 つをすべて満たすときに足す: 機能フラグ `tengu_opal_circuit` が on、提案の設定（proactivity）の判定が通る、Skill ツールがある、Claude が起動できるスキル（組み込みも数える）に `verify` がある。指示は、このセッションで `/verify` がまだ動いておらず、差分に実行時の振る舞いがある（テストや文書だけではない）ときに、`/verify` の起動を求める。組み込みの `/verify` は、同じフラグが on のときだけ Claude が起動できるので、on なら組み込みのものだけで条件を満たし、off なら個人や project に `verify` があっても指示は入らない。2026-11-23 の時点で、Claude のスキルの一覧に `verify` は出ない（フラグは off と見ている。推測）。フラグはサーバー側で変わりうる。on になると、チェックアウトしていない PR のレビューの後に、PR ではなく手元のブランチを動かし、`.claude/skills/verify/SKILL.md` を書く見込み（推測。動かして確かめていない）。止めるなら `permissions.deny` の `Skill(verify)` が候補で、モデルの起動だけを止め、ユーザーが打つ `/verify` は動く。今は入れていない。
- Bash ツールの説明の「commit の直前に `/verify` を実行する」という指示は、セッションの開始時に、`verify` か `simplify` という名前の、Claude が起動できるスキルが enterprise・個人・project・追加ディレクトリのどれかにあるとき（同じ名前の `.claude/commands/` のファイルも数える）に Claude Code が入れる。組み込み・プラグイン・claude.ai のスキルは数えない。docs と tests の変更は、この指示の対象から外れる。これまでは gstack の `verify` がこれに当たり、2026-10-27〜11-16 に 35 セッションで 65 回起動した。2026-11-16 に、このままにすると決めた（[research-routing.md](../docs/work/20261116_skill-role-division/research-routing.md#verify)）。gstack 1.103.0.0 で `build-check` に改名され、2026-11-23 に新しいセッションで、この指示が出なくなったことを確かめた。commit の前の検査は、CLAUDE.md の Verification 節で行う。組み込みの `/verify` は、記録した手順がないと、うまくいった手順をリポジトリのルート（monorepo では変更したパッケージのディレクトリ）の `.claude/skills/verify/SKILL.md` に書く。ルートに書いたものは project のスキルとして数えられ、次に始めるセッションから指示が戻る（公式ドキュメントの「Run and verify your app」と「Run your checks before each commit」）。

<a name="agents"></a>

## エージェント

| 提供元 | エージェント | 状態 |
| --- | --- | --- |
| 組み込み | `general-purpose`、`Explore`、`Plan`、`claude-code-guide`、`statusline-setup`、`web-fetch`、`claude` | 有効 |
| understand-anything | `project-scanner`、`file-analyzer`、`architecture-analyzer`、`tour-builder`、`graph-reviewer`、`assemble-reviewer`、`domain-analyzer`、`article-analyzer`、`design-analyzer`、`knowledge-graph-guide`、`code-lesson-writer` | 有効。主に `/understand-anything:understand` が使う。`code-lesson-writer`（2.9.8 で追加）は、`autoUpdate` が true のリポジトリでは commit の後の自動更新でも確認なしで起動する |
| pstack | `poteto-agent`、`comment-sicko` | 制限（`Agent(...)` を deny）。Agent の一覧に出ないことを 2026-11-16 に確認 |

<a name="hooks"></a>

## hooks

| イベント | 提供元 | 内容 |
| --- | --- | --- |
| PreToolUse（Bash） | settings | `validate-command.sh`（`rm -rf`・`prod` などを含むコマンドを止める）、`protect-main-branch.sh`、`ask-gh-pr-write.sh`、`ask-shared-tree-git.sh`（同じ作業ツリーの別セッション） |
| PreToolUse（Edit・Write・MultiEdit・NotebookEdit） | settings | `guard-additional-dirs.sh`（`~/.gstack/projects` が symlink のあいだ、Edit・Write 系をすべて止める） |
| PostToolUse（Bash） | settings | PR の URL を表示する |
| PostToolUse（Bash） | understand-anything | commit・merge などの後にグラフの更新を指示する |
| SessionStart | settings | `herdr-agent-state.sh`、`gh-read-token.sh`（読み取り専用のトークン） |
| SessionStart | superpowers | `using-superpowers` を注入する（startup・clear・compact） |
| SessionStart | understand-anything | `config.json` の `autoUpdate` が true のリポジトリだけ、グラフの更新を指示する |
| PermissionRequest（ExitPlanMode） | crit | `crit plan-hook` |
| Notification・Stop | settings | 通知音 |
| PreToolUse（Bash） | gstack のスキル | `careful`・`guard`・`freeze` を起動したセッションだけ |

- understand-anything や superpowers の一部の手順（一時ファイルの削除など）は、`validate-command.sh` で止まることがある。

<a name="mcp"></a>

## MCP・コネクタ

- MCP サーバーは `claude/mcp/*.json` の定義から user スコープに登録する（今は Playwright MCP だけ。[README](README.md#mcp)）。
- claude.ai のアカウントから、Claude Docs のコネクタが入る。easel（図表）は Claude Code の組み込みのプラグイン。

<a name="overlaps"></a>

## 重複と裁定

規則（[SKILL_ROUTING.md](rules/SKILL_ROUTING.md)）と同じ内容を、提供元の側から並べる。それぞれの代替・併用の条件・優先順位は [research-routing.md](../docs/work/20261116_skill-role-division/research-routing.md) にある。

| 領域 | 主担当 | 補完 | 使わないもの |
| --- | --- | --- | --- |
| TDD・デバッグ・実装計画 | superpowers | `/pstack:how`・`/pstack:why`（原因が設計の意図に関わるとき） | pstack `tdd` |
| 何を作るか | `/office-hours` | — | 同じ要件に `brainstorming` を重ねない |
| プロジェクトの運営 | `/pm-assist` | — | チケットや 1 日のタスクの分解、開発中の変更や設計のリスク（スキルなし）。何を作るかは `/office-hours`、機能の要件は `brainstorming`、実装の計画は `writing-plans` |
| 機能の要件・設計 | `brainstorming` → `writing-plans` | `/pstack:architect with checkpoint`（複雑か高リスク）、`/plan-eng-review`（明示だけ。計画のレビュー） | `/spec`、`/autoplan`（無効） |
| 変更の影響 | Claude 自身の読解 | `/pstack:blast-radius`（高リスク） | `understand-diff`（グラフが前提） |
| 差分のレビュー（今のブランチ） | `/review` | `/pstack:interrogate`（高リスクで実行による証明が要るとき） | 同じ差分に `/code-review`、`requesting-code-review` |
| 今のブランチ以外の PR のレビュー | `/code-review medium <PR の URL>`（チェックアウトしない。作者を問わない） | 全体が要るときは人間が読む | gstack の `/review`（チェックアウトして書き換える）、`/security-review`・`codex review`・`interrogate`（今のブランチを見る）、`--comment`・`--fix`、手元への取り込み、`ultra`（Claude のアカウントに GitHub をつなぐ） |
| 独立したモデルのレビュー | ユーザーが通常のターミナルで実行する `codex review` | challenge（`codex exec`。セキュリティの境界・設計判断を含む変更） | `/codex`（Bash から拒否される）、`interrogate`・`arena`（Claude 同士） |
| 計画の人間レビュー | `/crit-review` | — | `/crit:crit`（sandbox で動かない） |
| セキュリティ | `/security-review` | `/cso`（ユーザーが指定したとき） | 同じ差分に `/security-review` と `/cso` を重ねない |
| コードの理解 | 通常の読解・Explore | `understand-chat`（グラフがあるとき）、`/pstack:how` | `/understand-anything:understand` を自分で起動しない |
| E2E・ブラウザ | `/qa`（直す）、`/qa-only`（報告だけ） | Playwright MCP（Claude が操作して調べるとき）、`/browse`（gstack のスキルの中だけ） | `claude-in-chrome` |
| PR・リリース | CLAUDE.md の Git 節、`/commit-staged-pr` | — | `/ship`（無効）、`/document-release`（明示だけ）、finishing の push |
| 文脈の保存 | 自動の圧縮 | `/context-save`・`/context-restore` | pstack `recall`・`ketchup` |
| Claude Code の改善 | `claude-automation-recommender`、直接の編集 | `writing-skills` | pstack `correct`・`automate-me`・`reflect` |

<a name="upgrade"></a>

## 更新したときの見直し

<a name="upgrade-common"></a>

### 共通の手順

更新は、sandbox の外で `claude/scripts/update-skills.sh` を実行してまとめて行う。通常のターミナルで `/bin/bash ~/dotfiles/claude/scripts/update-skills.sh` を実行する（dotfiles では `mise run claude:update` でもよい）。gstack・user スコープのプラグイン・crit の CLI を更新し、gstack が `claude/settings.json` に書いた絶対パスを `~/` に戻し、modern-web-guidance の新しい版があれば知らせ（何も書かない）、cc-crit の profile テストまで実行する。Claude Code のプロンプトの `!` は、セッションによっては sandbox の中で動く（2026-11-19 に観測）。そのときは更新が失敗し、cc-crit の profile テストも「失敗した手順」に出る。profile テストは sandbox の中や crit がないときにスキップして終了コード 0 で終わるので、`update-skills.sh` は `CC_CRIT_PROFILE_REQUIRED=1` を付けて実行し、profile を確かめられないときは失敗させる。

- Claude Code のプロンプトの `!` で実行するときは、`mise run claude:update` ではなく `/bin/bash` の絶対パスを使う。`!` は sandbox の外で動くことがあり、mise は dotfiles のルートの設定ファイル（`mise.local.toml` など）を読み込み、ルートには sandbox から書けるため。paranoid で、信頼されていない設定は読み込まれないが、念のため mise を通さない。Claude が Bash ツールで実行する `mise run`（`/sync-skill-docs` の `claude:skills-check` など）は sandbox の中で動くので、これに当たらない。
- 確認が要るプラグイン（マーケットプレイスが宣言したインストールコマンドが変わったもの）は、TTY がないと拒否されて失敗に数えられる。ターミナルで `claude plugin update <id> --scope user` を実行する。
- 更新した hooks は、Claude Code を再起動した後のセッションで動き始める。再起動する前に、次の手順で見直す。

1. `mise run claude:skills-check` を実行する（スクリプトは `claude/scripts/skills-check.py`）。次の 2 つを照合する。
   - **入っている状態と、前回文書を合わせたときのスナップショット**（`claude/skills-snapshot.json`）:
     - プラグイン・gstack の増減と版
     - スキルの増減
     - `disable-model-invocation`・`user-invocable`・`skillOverrides` の変化
     - 説明文と hooks の変化（ハッシュで比べる）
   - **文書と入っている状態**:
     - 規則・チートシート・この文書のスキル名が実在するか
     - 入っているスキルとエージェントが、すべてこの文書に載っているか
     - 「提供元」の表の版
     - gstack の状態ごとの節
2. 終了コードが 0 なら終わり。1 なら、Claude に `/sync-skill-docs` を頼む（「gstack を更新した」と伝えるだけでもよい）。スキルが元のファイルを読んで文書を直し、差分を `/crit-review` で開く。スナップショットの作り直し（通常のターミナルで、作業しているツリー（worktree ならそのディレクトリ）に移って `mise run claude:skills-snapshot` か `/usr/bin/python3 -B claude/scripts/skills-check.py snapshot`）は、ユーザーが行う。sandbox の中の Bash は `claude/` に書けず、Claude Code のプロンプトの `!` もセッションによっては sandbox の中で動くため。2 は照合できない状態（ファイルが読めない、この文書のアンカーがない）。
3. `claude/settings.json` が書き換わっていないかを見る。CLI はキーの並びを変えることがあるので、`jq -S` で比べる。

<a name="upgrade-source"></a>

### 提供元ごとの注意

| 提供元 | 見ること |
| --- | --- |
| gstack（例: 1.99.4.0） | `update-skills.sh` か zsh の `gstack-upgrade` で更新する（`~/.claude/skills` に書くので sandbox の外で）。CHANGELOG で、廃止・追加されたスキルを見る。増えたスキルは `skillOverrides` が `on` のまま入るので、要るかを決める。`skillOverrides` は gstack が管理していない（dotfiles のコミット 02d0add で手で足した）。`/cso` が、読めない秘密ファイルで止まらなくなったかを確かめる（[`/cso` を sandbox で使う](#cso-sandbox)）。直っていれば、一時的に消す手順をやめ、規則で `/cso` を使う場面を決め直す。setup は、`~/.gstack/config.yaml` で on のフックを `claude/settings.json` に絶対パスで登録する（`_gstack_source` の項目）。どちらもこれを `~/` に戻す（setup は `~/` の項目も絶対パスに書き戻すので、更新のたびに要る）。`/gstack-upgrade` で更新したときは、後で通常のターミナルで `/usr/bin/python3 -B ~/dotfiles/claude/scripts/settings-home-paths.py` を実行する（`claude/settings.json` に書くので、sandbox の中で動いた `!` では失敗する）。timeline-stop-hook と ceo-review-gate は、`claude/setup.sh` のフラグで off にしている。1.102.0.0 から既定で on になった `skill_routing`（UserPromptSubmit）・`skill_contracts`（Stop）・`destructive_guard`（PreToolUse の Bash）も off にしている。どれも、そのたびに sandbox の外で bun が動く。setup.sh のフラグが config に保存されるのは setup.sh を実行したときだけで、保存されていないキーは、更新の setup が既定の値で登録する（2026-11-23 に、この 3 つが登録された）。項目が増えていたら、`gstack-config set <キー> off` を実行してから項目を消す（項目だけ消すと、次の setup で戻る） |
| understand-anything（例: 2.9.8） | 自動更新が on なので、気づかないうちに変わる。hooks は sandbox の外で動く（2026-11-14 に承知のうえで自動更新を選んだ）。hooks が変わったら判断し直す |
| crit（例: 1.8.15） | プラグインと CLI の版の組み合わせと、`plan-hook` の変化を見る。`update-skills.sh` は CLI の更新と cc-crit の profile テストまで実行する。個別に更新したときは、sandbox の外で `mise run crit:profile-test` を実行する。上流は 2026-11-24 に、設定を `~/.config/crit`、状態を `~/.local/state/crit` に置く XDG の配置に対応した（#1175。CLI 0.24.0 には入っていない。プラグイン 1.8.18 の `crit-cli` は両方の配置を書く）。既存のインストールは `crit migrate-xdg` を実行するまで `~/.crit` を使う。移すと、`~/.crit` の denyRead（Playwright MCP から承認を偽造させないため）が状態フォルダに当たらなくなる見込みなので、移す前に denyRead に足し、cc-crit（`COVERED_DENY_READ`・`cc-crit.sb`）も合わせる。対応した CLI に上げたら、`crit check` で使っているフォルダを確かめる |
| pstack | [README の「スキル・プラグインのアップデート」](README.md#setup-update)の手順で、hooks・スキルの一覧・依存を見直す。新しいスキルが増えても deny は広がらない |
| superpowers | SessionStart で注入する `using-superpowers` の変化を見る。とくに、ユーザーの指示を優先するという一文が残っているか |
| 個人スキル `socratic-tutor` | `update-skills.sh` の対象外。上流の変更は `gh api 'repos/janestreet/agent_skills/commits?path=socratic-tutor/SKILL.md&per_page=1' --jq '.[0].sha'` で、[個人スキルの表](#crit)のコミットと比べる。写し直すときは `disable-model-invocation: true` を残し、`LICENSE.md` も比べる |
| 個人スキル `modern-web-guidance`・`chrome-extensions` | `update-skills.sh` の手順 `modern-web-guidance`（`claude/scripts/update-modern-web-guidance.py`）は、npm に新しい版があると、最後に「取り込みを待つ更新」と表示する。何も書かないので、取り込むまで毎回出る。取り込むときは、(1) 中身を確かめる: Claude のセッションでも動く `--out <dir> --latest` で一時ディレクトリに書き、取り込み済みのスキルと比べて、SkillSpector（`--no-llm`）の要約を見る。(2) 作業ブランチで、通常のターミナルから `/usr/bin/python3 -I -B ~/dotfiles/claude/scripts/update-modern-web-guidance.py --apply` を実行する。2 つのスキルと `mise/mise_config.toml` の版を書き（両方そろって書けたときだけ残す）、パス付きの戻し方を表示する。書いた時点で有効になり、mise は足りない版を自動で入れうる。`check-repo.py` は `.github/scripts` が sandbox から書けるので、`--apply` からは実行せず、Claude のセッション（sandbox の中）で実行する。(3) PR にし、マージしてから `mise install` を実行する。次のどれかがあると、何も書かずに失敗する: frontmatter のキー（`name`・`description`・`license`・`metadata` 以外）、SKILL.md の LF 以外の改行、読み込み時に実行する書き方（`` !`…` ``・` ```! `）、package.json の依存・インストール時のスクリプト・`modern-web-guidance` 以外の `bin`・tarball にない `bin` の参照先、変換できない npx 系の指示、`package/` の外のエントリー・`binding.gyp`、正規でないパス・ドットで始まる名前・大文字小文字だけが違う名前、`chrome-extensions` の `SKILL.md`・`skill-version.txt`・`references/**/*.md` 以外のファイル。中身を確かめてから、スクリプトの規則を直すか手で取り込む |

<a name="measurement"></a>

## 規則の効果の確認

規則（[SKILL_ROUTING.md](rules/SKILL_ROUTING.md)）を置く前と後で、スキルの使われ方を比べる。予定と結果は Linear の dotfiles プロジェクトで管理する。基準値（2026-10-27〜11-16）は [test-report.md](../docs/work/20261116_skill-role-division/test-report.md#baseline) にある。

- 期間: 後の期間は PR #29 のマージ（2026-11-16）から 21 日間。測定日は 2026-12-07、期限は 2026-12-16（トランスクリプトは既定で 30 日で消える）。
- 実行: 新しいセッションで Claude に頼むか、自分で `mise run claude:skill-usage 2026-11-16 2026-12-07` を実行する（スクリプトは `claude/scripts/skill-usage.py`。終わりの日は含まない）。件数とセッション ID だけを出し、会話の中身は出さない。

判定の基準:

- **維持:** レビューの重複と、軽微な作業での計画系のスキルの起動が減るか 0 のままである。誤った選択の報告がない。
- **修正:** 誤った選択の具体例がある。その例に対応する 1〜2 行を直す。
- **削除:** 前後で差がなく、提案も使われていない。規則を消し、チートシートとこの文書だけを残す。

`/pstack:` の提案の回数には、スキルの設定を扱うセッション（この文書を作ったセッションなど）で Claude がコマンド名を書いた分も入る。増減は、セッションの一覧と合わせて見る。

後の期間の途中（2026-11-23）で gstack を 1.102.2.0 に更新した。説明文に「いつ使うか」の節が付き（1.100.0.0）、gstack のスキルの起動は、規則とは別の理由でも増えうる。gstack のスキルの増減は、この日の前後に分けて見る。同じ日に、自動で起動する個人スキル `modern-web-guidance`・`chrome-extensions` を足した。測る対象（レビューの重複、軽微な作業での計画系のスキル）とは役割が重ならない。さらに同じ日に gstack を 1.103.0.0 に更新し、`verify` が `build-check` に改名された。基準値の gstack の起動の多く（`verify` の 65 回）は commit の前の指示によるもので、改名の後はこの指示が出なくなった（2026-11-23 に新しいセッションで確かめた）ので、gstack の起動の数を比べるときは `verify`・`build-check` を除いて見る。同じ日に、今のブランチ以外の PR のレビューを `/review` から `/code-review medium <PR の URL>` に分けた（CLAUDE.md の Tools 節、SKILL_ROUTING.md の Overlapping skills）。`skill-usage.py` は、1 つのセッションで 2 種類以上のレビューのスキル（`review`・`code-review`・`superpowers:requesting-code-review`）が動くと重複に数えるので、この日の後は、今のブランチの `/review` と、ほかの PR の `/code-review` が同じセッションにあっても数えられる。スクリプトは、重複に数えたセッションの ID も件数の下に出す。そのセッションのレビューの呼び出しを、対象（そのセッションのブランチか、どの PR か）ごとに分け、同じ対象に 2 種類以上のレビューが動いた組が 1 つもなければ、重複から除く（ほかの PR の `/code-review` があっても、同じ差分に重ねた組があれば重複に数える）。

2026-11-26 に、自動で起動する個人スキル `/pm-assist` を足した。プロジェクトの運営の相談で起動し、計画系のスキル（`brainstorming`・`writing-plans`）と競合しうる。起動テストでは、新規プロダクトの立ち上げの相談で、最初に起動したのは `brainstorming` ではなく pm-assist だった（一時コマンドで、最初のツール呼び出しを見て測った。3 回中 3 回。[test-report.md](../docs/work/20261126_pm-assist-skill/test-report.md#trigger-run-2)）。この日の後は、立ち上げの相談での計画系のスキルの起動が減りうるので、計画系のスキルの増減は、この日の前後に分けて見る。
