---
status: done
created: 2026-11-14
---

# Claude Code のスキル・プラグイン棚卸し（2026-11-14 時点）

関連: [plan.md](plan.md)

<a name="method"></a>

## 調べ方

- インストール済みの実物を優先した。`claude plugins list`、`~/.claude/plugins/installed_plugins.json`、各プラグインの `hooks/hooks.json` と `SKILL.md` の frontmatter、`~/.claude/skills/`、`claude/settings.json`、`gstack-config get`。
- pstack は `cursor/plugins` を 05b4917（2026-11-13）で取得した。Claude Code が実際に入れる `harness/pstack/claude-code/` を読んだ（マーケットプレイスの `source` がこのディレクトリを指す）。移植版 `michael-denyer/pstack-claude` は a12b047 で比較した。
- Claude Code の仕様（`skillOverrides`、`disable-model-invocation`、プラグインの書き込み先）は公式ドキュメント（code.claude.com の skills / plugins / sub-agents）で確認した。
- 「推測」「未確認」と書いたもの以外は、上の実物か公式ドキュメントで確認した事実。

<a name="environment"></a>

## 1. 環境

| 項目 | 値 |
| --- | --- |
| Claude Code | 2.1.323 |
| 設定の実体 | `~/.claude/settings.json`・`CLAUDE.md`・`rules/`・`hooks/`・個人スキルは、`claude/setup.sh` が dotfiles の `claude/` へのシンボリックリンクとして張る |
| sandbox | `enabled: true`、`failIfUnavailable: true`、`allowUnsandboxedCommands: false` |
| 書き込めない場所（sandbox） | `~/.claude/plugins`、`~/.claude/skills`、dotfiles の `claude/`（`settings.json`・`CLAUDE.md`・`rules/`・`hooks/` を含む） |
| permission mode | auto |

<a name="plugins"></a>

## 2. プラグインとスキル集

| 名前 | 版 | 入手元 | スコープ | hooks | スキル | エージェント |
| --- | --- | --- | --- | --- | --- | --- |
| superpowers | 7.0.2 | claude-plugins-official | user（dotfiles の project にも登録あり） | SessionStart（startup / clear / compact）で `using-superpowers` を注入 | 15（すべてモデルから起動できる） | 0 |
| claude-code-setup | 1.0.0 | claude-plugins-official | user（同上） | なし | 1 | 0 |
| ruby-lsp | 1.0.0 | claude-plugins-official | user（同上） | なし | 0（LSP のみ） | 0 |
| understand-anything | 2.9.7 | Egonex-AI/Understand-Anything | user（同上） | SessionStart（グラフが古いと更新を指示）、PostToolUse（Bash） | 9 | 10 |
| crit | 1.8.14 | tomasz-tomczyk/crit | user | PermissionRequest（ExitPlanMode）で `crit plan-hook` | 3 | 0 |
| salesforce-development | 2.5.0 | claude-plugins-official | local（別リポジトリ） | — | — | — |
| gstack | 1.99.3.0（6b033e7） | `git clone` で `~/.claude/skills/gstack` | user のスキル（プラグインではない） | 有効なスキルでは `plan-ceo-review` の frontmatter に PostToolUse（Bash） | 66 のうち 33 を `skillOverrides` で `off` / `user-invocable-only` | — |

- gstack はプラグインではないので、スキル名に接頭辞が付かない（`/review`、`/codex`）。`skill_prefix=false`。
- gstack の設定: `proactive=core`（頼まれずに提案するのは `/office-hours` `/review` `/qa` `/ship` だけ）、`codex_reviews=enabled`、`routing_declined=true`、`telemetry=off`。
- この版の gstack には `/investigate` と `/plan-eng-review` がない。`/ship` と `/autoplan` は `skillOverrides` で `off`。
- 個人スキル（dotfiles の `claude/skills/`）: `code-style`、`commit-staged-pr`、`crit-review`、`salesforce-help`。
- `~/.claude/commands/` と `~/.claude/agents/` はない。

<a name="auto-invocation"></a>

## 3. 自動起動の仕組み

1. superpowers の SessionStart hook が `using-superpowers` を注入する。「1% でも当てはまるならスキルを起動する」という強い指示で、モデルから起動できるスキル全体の選択に効く。
2. モデルから起動できるスキルの description は、Claude のスキル一覧に載る。Claude はこれを見て選ぶ。
3. `claude/CLAUDE.md` の Tools 節が `/browse`・`/qa`・`/review`・`/crit-review` と Codex レビューの使いどころを決めている。
4. gstack の `proactive=core`。`routing_declined=true` なので、gstack は CLAUDE.md にルーティング規則を書き足さない。
5. `skillOverrides`（gstack の 33 件）。gstack はプラグインではなく `~/.claude/skills/` のスキルとして入っているので効く。プラグインのスキル（pstack など）には効かない。
6. understand-anything は、`.understand-anything/config.json` で `autoUpdate` が true のリポジトリに限り、SessionStart で確認なしのグラフ更新を指示する。dotfiles にはこのディレクトリがない。
7. crit の plan-hook は ExitPlanMode の許可要求で Crit のレビューを開く。

<a name="call-graph"></a>

## 4. スキル間の呼び出し関係

- superpowers: `brainstorming` → `writing-plans` → `subagent-driven-development` または `executing-plans` → `test-driven-development`・`requesting-code-review`・`using-git-worktrees`・`finishing-a-development-branch`。`systematic-debugging` → `test-driven-development`・`verification-before-completion`。
- gstack `/review`: 専門のサブエージェント（Review Army）、Claude の adversarial パス（Agent）、`codex_reviews=enabled` なら Codex（`codex exec`、read-only）を回し、Fix-First で修正まで行う。
- gstack `/codex`: `codex exec -s read-only`。review / challenge / consult の 3 モード。
- understand-anything: `/understand` が `project-scanner`・`file-analyzer`（最大 5 並列）などのエージェントでグラフを作る。`understand-chat`・`understand-explain`・`understand-diff`・`understand-onboard` はグラフが前提で、なければ `/understand` を先に促す。
- pstack: `architect` → `how`・`why`・`arena`。`interrogate` → `arena` の Phase A・B。`teach` → `how`・`why`。`blast-radius` は大きい変更のとき `arena`。

<a name="pstack"></a>

## 5. pstack（公式版）

- Claude Code 用のツリー `harness/pstack/claude-code/` は `pstack/` から生成される。Cursor 専用の automations などは含まれない。
- 中身は 58 スキルと 2 エージェント（`poteto-agent`、`comment-sicko`）。hooks・MCP・LSP はない（0.15.36 と 0.15.42 で同じ）。
- `setup-pstack` 以外の 57 スキルは `disable-model-invocation: true`。Claude からは起動できず、description もコンテキストに載らない。Claude が起動しようとすると Claude Code が止め、別の方法で手順を再現しないよう Claude に指示する（公式ドキュメント）。
- `claude plugin details` は常時のコストを約 3,523 トークンと見積もる。スキルごとの always-on の値は 57 スキルの description も数えていて、上の公式ドキュメントの記述と合わない。実際にコンテキストに載るかは、セッションのスキル一覧で確かめる。
- `skillOverrides` はプラグインのスキルに効かない（公式ドキュメント）。個別の有効化・無効化は settings ではできない。
- 各スキルの既定のモデルは Cursor の名前で、版によって変わる（0.15.36 は `grok-4.7-xhigh-fast` と `claude-opus-5-5-xhigh`、0.15.42 の arena は `claude-fable-5-2-high`・`claude-opus-5-5-high-fast`・`gemini-4-carbon-high`）。Claude Code 用のアダプタは、Claude の名前を `model` と `effort` に置き換え、Claude 以外の名前を「`model` を省略してセッションのモデルで動かす」に置き換える。Claude Code ではすべて Claude で動く。
- `arena` の審査役は親と別のモデルファミリーから選ぶ。Claude Code では Claude 以外の名前がセッションのモデルに置き換わるので、審査役も Claude になる。
- `setup-pstack` は `~/.claude/rules/pstack-models.md` を書く。この環境では dotfiles の `claude/rules/`（公開リポジトリで、全セッションで読み込まれる）に入る。
- サードパーティのマーケットプレイスの自動更新は既定で off（公式ドキュメント）。

<a name="pstack-focus"></a>

### 重点スキルの中身

インストールしたのは 0.15.42（gitCommitSha bf0c7cd、2026-11-15）。事前に読んだ 0.15.36 から、`how` と `why` が大きく簡素になり、`arena` の既定のモデルが変わった。下の表は 0.15.42 の内容。

| スキル | 何をする | サブエージェント | 書き込み・外部 | 注意 |
| --- | --- | --- | --- | --- |
| `how` | 処理の流れと置き場所を、オンボーディング向けの説明にまとめる | 読み取り専用の説明役 1（調査と説明を 1 回で行う） | 読み取りのみ | 0.15.36 では、複雑な質問に調査役 2〜4 を足していた |
| `why` | コミットと PR の議論から、作者が書いたことを出典つきで示し、推測と分けて答える | なし（本文 9 行） | `git` と `gh` の読み取り | 0.15.36 では、証拠の種類ごとの調査役と合成役を起動していた |
| `architect` | 関係するサブシステムを把握し（必要なら `why`）、`arena` で 2 つ以上の設計案を作って合成し、実装まで進む | 多い | 書き込みあり | 既定では人の確認なしで実装に進む。「with checkpoint」と指定すると設計で止まる |
| `blast-radius` | 差分の外で壊れうるものを探し、安全の根拠になる 1 つの事実をコードを動かして証明する | なし（大きい変更なら `arena`） | 検証スクリプトの実行 | 呼び出し元の一覧ではなく、grep で見えない壊れ方を探す |
| `interrogate` | 複数の adversary が変更を壊しにいき、実行で証明できた指摘だけを残す。修正はしない | 2 以上（worktree） | worktree の作成 | Claude Code では全員 Claude |
| `arena` | N 個の候補を並列に作り、基準で採点して土台を選び、他の候補の良い部分を移植する | 既定で 3（Fable 5.2 high、Opus high、Gemini はセッションのモデルに置き換わる） | 候補ごとの出力先 | 審査役は親と別ファミリーの Gemini を選ぶが、Claude Code ではセッションのモデル（Claude）で動く |

<a name="pstack-dependencies"></a>

### 重点スキルの依存関係

Claude Code 用のアダプタ（`docs/harness/claude-code.md`）は、スキルから別のスキルを使うときは `<pstack>/skills/<name>/SKILL.md` を Read して従うと定めている。依存はファイルの読み込みで解決し、Skill ツールを通らない。

| スキル | 読む pstack スキル | 補助ファイル |
| --- | --- | --- |
| `how` | なし | なし |
| `why` | なし | なし |
| `architect` | `why`、`arena`、`interrogate`（任意）、principle 12 件 | `references/` の design-red-flags・rationale-template・runner-prompt |
| `blast-radius` | `arena`（大きい変更）、`unslop` | なし |
| `interrogate` | `in-your-own-words`、`arena` | なし |
| `arena` | `poteto-mode`（Subagents 節）、principle 4 件 | なし |

- architect と arena が読む principle は、boundary-discipline、encode-lessons-in-structure、exhaust-the-design-space、fix-root-causes、foundational-thinking、laziness-protocol、make-operations-idempotent、minimize-reader-load、outcome-oriented-execution、prove-it-works、redesign-from-first-principles、separate-before-serializing-shared-state、subtract-before-you-add の 13 件。依存の 16 件（`poteto-mode`、`in-your-own-words`、`unslop` と principle 13 件）は 0.15.36 と同じ。
- `why` 以外の重点スキルは、セッションごとに 1 回アダプタを読む。
- 外部コマンド: `why` は `git` と `gh`（読み取り）。`arena` と `architect` は git worktree を使い、使えなければ一時ディレクトリに出力する。外部モデルの CLI（codex など）はどの重点スキルも使わない。
- `poteto-mode` の playbook は `gh pr create`・`gh pr merge`・`git push` を使う。どれも既存の制御（deny、ask と読み取り専用トークン、cc-safe-push）で止まる。
- `poteto-agent` と `comment-sicko` は、`poteto-mode` と `no-comments` からだけ使われる。重点スキルは general-purpose と Explore を使う。

<a name="pstack-controls"></a>

### スキルを制御する手段（公式ドキュメント）

| 区分 | 使える手段 | 確認できたこと |
| --- | --- | --- |
| ロード対象から外す | プラグイン単位の無効化・アンインストールだけ | `skillOverrides` はプラグインのスキルに効かない。スキル単位で外す公式の手段は見つからなかった |
| 自動起動を抑える | SKILL.md の `disable-model-invocation: true`（作者側） | Claude のコンテキストから完全に消える |
| 明示起動だけにする | 同上 | ユーザーのスラッシュコマンドでだけ起動する |
| 呼び出しを禁止する | `permissions.deny` の `Skill(...)`・`Agent(...)` | モデルの Skill ツール呼び出しと、名前が一致するサブエージェントを止める。ユーザーのスラッシュコマンドを止めるか、プラグインのスキル・エージェントの書式（`pstack:` を付けるか）は未確認 |
| 方針として使わない | — | — |

- `Skill(...)` の deny は Read を止めない。依存の読み込みは壊さないが、ほかのスキルが不要なスキルの SKILL.md を読むことも止めない。

<a name="pstack-selective-install"></a>

### スキルを選んで入れる方法

公式の手順（`claude plugin install pstack@cursor-plugins`）では、58 スキルすべてが入る。選んで入れる方法と問題点は次のとおり（公式ドキュメントと実物で確認）。

| 方法 | できるか | 問題点 |
| --- | --- | --- |
| `plugin.json` の `skills` で絞る | できない | `skills` は既定の `skills/` の読み込みに追加されるだけで、置き換えない |
| 自分のマーケットプレイスの entry で `skills` を列挙する（source は `git-subdir` で `harness/pstack/claude-code`） | できない | pstack には `plugin.json` がある。`strict: false` で entry がコンポーネントを宣言すると conflict で読み込まれず、`strict` が true なら追加になる |
| 同上で、source を `harness/pstack/claude-code/skills` にして `strict: false` と `skills` を列挙する（公式マーケットプレイスの amd-skills と同じ形） | できる | プラグインの外の `docs/harness/claude-code.md`（アダプタ）がキャッシュにコピーされない。全スキルが最初に読むアダプタが欠け、Cursor の名前（`Task`、`readonly`、grok のモデル名）の置き換えが当てにならない。プラグイン ID が `pstack@<自分のマーケットプレイス>` になり、上流の生成物のディレクトリ構成に依存する |
| `cursor/plugins` を clone し、必要なスキルだけを `~/.claude/skills/` にシンボリックリンクで置く（gstack と同じ形） | できる | 名前が `/how` のように接頭辞なしになる。スキルの基準ディレクトリがリンクのパスになるので（個人スキル crit-review で確認）、`../../docs/...` のアダプタへの相対リンクが切れる。依存の解決先（`<pstack>`）もあいまいになる。更新は setup.sh の clone と pull に頼る |
| 必要なファイルをコピーまたは fork する | できる | 上流に手で追従する。依頼の方針（安易な fork・コピーをしない）に反する |

- 共通の利点は、不要なスキルが / メニューに出なくなること。不要なスキルは `disable-model-invocation` でもともとコンテキストを使わないので、得るのはこれだけ。
- 選んで入れても、依存のスキル（`poteto-mode` など 16 件）はファイルとして必要になる。

<a name="port-comparison"></a>

## 6. 移植版との比較

公式版は [cursor/plugins の pstack](https://github.com/cursor/plugins/tree/main/pstack) で、作者が Cursor 向けに書いている。Claude Code が入れるのは、同じリポジトリの [harness/pstack/claude-code](https://github.com/cursor/plugins/tree/main/harness/pstack/claude-code) にある生成物。`pstack/` からスクリプトで生成し、古いままだと CI が失敗する。違いは、各 SKILL.md の冒頭にアダプタを読む指示が 1 行入ることと、Cursor 専用の automations などが入らないことだけ。リポジトリ直下の `.claude-plugin/marketplace.json` がこのディレクトリを `pstack` として公開している。

| 項目 | 公式版（cursor/plugins） | 移植版（michael-denyer/pstack-claude） |
| --- | --- | --- |
| 版 | 0.15.36 | 0.9.138 |
| hooks | なし | SessionStart（毎セッション文脈を注入）、PreToolUse |
| モデルからの起動 | 58 のうち 57 は不可 | 67 すべて可 |
| プラグイン名 | `pstack` | `pstack`（同時に入れると衝突する） |

<a name="overlaps"></a>

## 7. 重複・競合

7 と 8 は、次の作業（全プラグインの役割分担）への引き継ぎとして残す。今回の作業では扱わない。

| 領域 | 重なるスキル | 違い |
| --- | --- | --- |
| コードの理解 | understand-anything、pstack `how`、通常の読解 | understand-anything はグラフを作る初回が重く、以後は安い。`how` は質問ごとにエージェントを起動する |
| 設計 | superpowers `brainstorming` → `writing-plans`、pstack `architect`、gstack `/spec`・`/office-hours`・`/plan-ceo-review` | superpowers は対話と文書。`architect` は型の下書きを競わせ、実装まで進む |
| デバッグ | superpowers `systematic-debugging`、pstack の principle 群 | pstack にデバッグの手順を持つスキルはない |
| TDD | superpowers `test-driven-development`、pstack `tdd` | superpowers は機能追加とバグ修正の両方で厳格。pstack はバグ修正で、安いテストがあるときだけ |
| 並列実行 | superpowers `dispatching-parallel-agents`・`subagent-driven-development`、pstack `swarm`・`arena` | superpowers は実装タスクの分担。pstack は網羅的な探索と案の競争 |
| コードレビュー | gstack `/review`、組み込み `/code-review`、superpowers `requesting-code-review`、pstack `interrogate` | `/review` は専門エージェント・adversarial・修正まで。`interrogate` は実行で証明できた指摘だけ |
| 変更の影響 | pstack `blast-radius`、understand-anything `understand-diff`、gstack `/review` の sideways sweep | `blast-radius` は安全の根拠を実行で証明する。`understand-diff` はグラフが前提。sweep は見つかった指摘の横展開だけ |
| 別モデルのレビュー | gstack `/codex` | OpenAI の Codex CLI。pstack `interrogate` と gstack `/review` の adversarial パスは Claude |
| セキュリティ | gstack `/cso`（`--diff` あり）、組み込み `/security-review` | `/cso` は監査範囲を選べ、差分の外の呼び出し元も読む |
| 文章 | pstack `unslop`・`technical-writing` | 英語の文体基準。日本語の文書には合わない（推測） |
| 文脈の保存 | gstack `/context-save`・`/context-restore`、pstack `recall`・`ketchup` | — |
| Claude Code の改善 | claude-code-setup、pstack `correct`・`automate-me`・`reflect`、superpowers `writing-skills`、組み込み `/update-config` | — |

<a name="issues"></a>

## 8. 既存運用で気づいた点

1. 参考案の前提と実物が違う: gstack `/ship` と `/autoplan` は `off`、`/investigate` はこの版にない。
2. `installed_plugins.json` に、dotfiles を projectPath とする project スコープの登録が 4 件ある（superpowers、claude-code-setup、ruby-lsp、understand-anything）。`.claude/settings.json` に `enabledPlugins` はない。原因と影響は未確認。
3. gstack の `codex_reviews=enabled` で、`/review` が Bash から Codex を呼ぶ。2026-11-11 のセッションで、Bash からの `codex review` が権限の判定で拒否された記録がある。`/review` の外部レビューが失敗するか確認待ちになる可能性がある（今回は未検証）。
4. 個人スキル `code-style` の description が「for this project」で、全リポジトリのコード作業に当たる。
5. コードレビューの手段が 4 つ重なる（上の表）。CLAUDE.md は PR とブランチの差分に `/review` を指定済み。
