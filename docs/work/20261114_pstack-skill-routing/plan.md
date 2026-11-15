---
status: done
created: 2026-11-14
---

# pstack の導入と重点スキルの最適化

関連: [research-skill-inventory.md](research-skill-inventory.md)

<a name="goal"></a>

## 目的

pstack を公式版で入れ、重点スキル（`how`・`why`・`architect`・`blast-radius`・`interrogate`、条件付きで `arena`）を使えるようにする。それ以外のスキルは、検証できる方法で、できる範囲まで無効化・制限する。全プラグインの役割分担のルールとチートシートは次の作業で扱い、ここでは作らない。

<a name="facts"></a>

## 判断の前提になる事実

詳細と出典は [research-skill-inventory.md](research-skill-inventory.md) にある。

1. 公式版 0.15.36 は 58 スキルと 2 エージェントで、hooks と MCP はない。Claude Code は `harness/pstack/claude-code/` を入れる。
2. `setup-pstack` 以外の 57 スキルは `disable-model-invocation: true`。Claude のコンテキストに載らず、Claude からは起動できない。ユーザーのスラッシュコマンドでだけ動く。
3. 依存は、Claude が別のスキルの SKILL.md を Read して解決する。`how`・`why`・`arena` は `poteto-mode` の Subagents 節を読む。
4. スキルの制御の手段は次のとおり。

   | 区分 | pstack に使える手段 | 状態 |
   | --- | --- | --- |
   | ロード対象から外す | スキル単位ではない（`skillOverrides` はプラグインのスキルに効かない）。プラグイン全体の無効化か、必要なスキルだけを写した最小構成だけ | 使わない（判断 3） |
   | 自動起動を抑える | pstack 側の `disable-model-invocation` | 57 スキルは設定なしで済んでいる |
   | 明示起動だけにする | 同上 | 同上 |
   | 呼び出しを禁止する | `permissions.deny` の `Skill(...)`・`Agent(...)` | モデルの呼び出しは止まる。ユーザーのスラッシュコマンドを止めるかと、書式は未確認なので実機で確かめる |
   | 方針として使わない | — | 上の手段で止められないものに適用する |

5. `Skill(...)` の deny は Read を止めない。依存の読み込みを壊さない代わりに、ほかのスキルが不要なスキルを読むことも止めない。
6. 既定のモデルの置き換えで、Claude Code ではすべて Claude で動く。重点スキルは外部モデルの CLI を使わないので、Codex の連携に影響しない。`interrogate` と `arena` は独立モデルレビューにならない。
7. `~/.claude/plugins` と dotfiles の `claude/` は sandbox から書けない。インストールはユーザーが `!` で実行する。

<a name="decisions"></a>

## 判断

1. 公式版 `pstack@cursor-plugins` を user スコープで入れる。移植版は入れない（SessionStart hook で毎セッション文脈を足し、67 スキルすべてがモデルから起動できる。名前も衝突する）。
2. `setup-pstack` と `~/.claude/rules/pstack-models.md` は使わない。既定のモデルの置き換えで動き、書き先が dotfiles の `claude/rules/`（全セッションで読み込まれる）になる。選べるモデルが Claude だけなので、設定しても独立性は変わらない。コストを下げたくなったら（調査役を sonnet にするなど）別に検討する。
3. スキルを選んで入れる方法（自分のマーケットプレイスで一部のスキルだけを公開する、`~/.claude/skills/` にシンボリックリンクで置く、コピーや fork）は採らない（[調査メモ](research-skill-inventory.md#pstack-selective-install)）。どの方法も公式の手順から外れ、アダプタへの相対リンクが切れるか、上流に手で追従することになる。得るものは不要なスキルが / メニューから消えることだけで、不要なスキルはもともとコンテキストを使わない。
4. 全 58 スキルを次のように分ける。

   | 分類 | スキル | 対応 |
   | --- | --- | --- |
   | 重点（5） | `how`、`why`、`architect`、`blast-radius`、`interrogate` | 有効 |
   | 条件付き（1） | `arena` | 有効。比べる価値のある案が複数あるときだけ使う |
   | 依存（16） | `poteto-mode`、`in-your-own-words`、`unslop`、principle 13 件（[調査メモ](research-skill-inventory.md#pstack-dependencies)） | 有効。`poteto-mode` だけは、直接の起動を判断 5 の deny の対象にする（ファイルとしての読み込みは止まらない） |
   | 不要（36） | 下の一覧 | 判断 5 |

   不要の内訳と理由:

   - ワークフローが superpowers・CLAUDE.md と重なるか矛盾する: `swarm`、`tdd`、`figure-it-out`、`poteto-help`、`principle-never-block-on-the-human`（人の確認を待たない方針が、Plan 承認のルールと矛盾）
   - リポジトリやスキルに書き込む: `automate-me`、`correct`、`reflect`、`create-verification-skill`、`maintain-verification-skill`、`create-formal-verification-skill`、`maintain-formal-verification-skill`、`setup-pstack`
   - 規約と矛盾する: `no-comments`（コメントを消す。日本語のコードコメントの規約と矛盾）、`technical-writing`（英語の文体基準）
   - 今は使わない: `statechart`（TLA+）、`make-bot-ui`、`ketchup`、`ketchup-video`、`recall`、`show-me-your-work`、`sharpen`、`teach`、`bro`、`benchmark-checklist`、`typescript-best-practices`
   - 重点スキルが読まない principle 11 件: attack-the-premise、build-the-lever、experience-first、explain-the-number、guard-the-context-window、migrate-callers-then-delete-legacy-apis、model-the-domain、sequence-verifiable-units、test-behavior-not-implementation、type-system-discipline（と上の never-block-on-the-human）

5. 制限は `claude/settings.json` の `permissions.deny` で入れる。範囲は実機の確認の結果で決める。
   - 必ず入れる: `Skill(pstack:setup-pstack)`（唯一モデルから起動できる）、`Agent(pstack:poteto-agent)`、`Agent(pstack:comment-sicko)`（不要なスキルからだけ使われ、description は Claude に見える）。書式が合わなければ、確認で通った書式に直す。
   - deny がユーザーのスラッシュコマンドも止めると確認できた場合: 不要の 36 件と `poteto-mode` に `Skill(pstack:<name>)` を入れる。
   - 止めない場合: 上の 3 件だけにする。ほかの不要なスキルはモデルから起動できないので、deny を足しても効果がない。報告では「自動起動されない・明示起動はできる・方針で使わない」と書き、無効化済みとは書かない。

<a name="changes"></a>

## 変更するファイル

| ファイル | 変更 | 効く範囲 |
| --- | --- | --- |
| `claude/settings.json` | インストールのコマンドが `extraKnownMarketplaces.cursor-plugins` と `enabledPlugins["pstack@cursor-plugins"]` を足す（手では書かず、差分を確かめる）。判断 5 の deny を足す | 全セッション（user） |
| `claude/setup.sh` | understand-anything と同じ形で、pstack のマーケットプレイスの追加とインストールを足す | 新しいマシンのセットアップ |
| `claude/README.md` | セットアップ節のプラグインの一覧に pstack を足す。pstack を更新したら、スキルの一覧の差分を分類し直して deny を見直すことを書く | 文書 |
| `docs/work/20261114_pstack-skill-routing/` | この plan と調査メモ。検証の結果を `test-report.md` に書く | 文書 |

<a name="steps"></a>

## 手順

1. main から作業ブランチを切る → `git status` でブランチを確かめる。
2. ユーザーが `! claude plugin marketplace add cursor/plugins` と `! claude plugin install pstack@cursor-plugins` を実行する → `claude plugins list` に pstack 0.15.36（user）が出る。`~/.claude/settings.json` がシンボリックリンクのままである。`git diff claude/settings.json` が上の 2 項目だけである。`claude plugin details pstack@cursor-plugins` で中身とトークンの見積もりを見る。インストールされたツリーに hooks がない。
3. `permissions.deny` に必ず入れる 3 件と、確認用の `Skill(pstack:bro)`（不要で、動いても害がない）を足す。
4. ユーザーがこのセッションを終了し、`claude --resume` で再開する（プラグインと settings を読み直すため）。次を確かめる。
   - ユーザーが `/pstack:how`（例: cc-safe-push が許可リストをどう判定するか）と `/pstack:why`（例: cc-safe-push がなぜ空の一時リポジトリから push するか）を実行する → アダプタ・参照ファイル・`poteto-mode` の Subagents 節を解決して答えが出る。
   - ユーザーが `/pstack:bro` を入力する → 止まるかどうかで判断 5 の範囲が決まる。
   - Claude が `pstack:setup-pstack` を Skill ツールで起動しようとする → 拒否される（拒否されなくても、書き込む前に予算を尋ねるので、そこで止める）。
   - Claude が `pstack:comment-sicko` に「何も読まず OK とだけ返す」依頼を出す → 拒否される。Agent ツールの一覧に 2 つのエージェントが出るかも見る。
   - 既存のプラグインのスキルが一覧に出ていて、`claude plugins list` で有効のままである。
5. 確認の結果で deny を確定する → 確定した deny から 1 件を選んで、もう一度確かめる。
6. `setup.sh` と `README.md` を編集する → `python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、shellcheck、`actionlint` が通る。
7. `architect`・`interrogate`・`arena` は、書き込みと worktree を伴い重いので実行しない。依存のファイルがインストールされたツリーにあることだけを確かめ、報告では動作未検証とする。
8. コミットと push はしない。

<a name="out-of-scope"></a>

## 対象外

- 全プラグインの役割分担のルール、チートシート、CLAUDE.md へのルーティングの追記（次の作業）。
- 既存プラグインの削除・設定変更、gstack の設定変更、`installed_plugins.json` の整理。
- `setup-pstack` の実行と、pstack の自動更新の有効化。
