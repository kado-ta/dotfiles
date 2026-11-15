---
status: done
created: 2026-11-16
---

# スキル・プラグインの更新に文書を追従させる仕組み

## 関連

- 前の作業: [スキル・プラグインの役割分担](../20261116_skill-role-division/plan.md)（PR #29、マージ済み）
- 対象の文書: [SKILL_INVENTORY.md](../../../claude/SKILL_INVENTORY.md)、[SKILL_CHEATSHEET.md](../../../claude/SKILL_CHEATSHEET.md)、[rules/SKILL_ROUTING.md](../../../claude/rules/SKILL_ROUTING.md)

<a name="goal"></a>

## 目的と範囲

プラグインやスキルを足した・外した・更新したときに、棚卸し・チートシート・規則を追従させる。ユーザーが選んだ案 B に沿って、次の 2 つに分ける。

- **機械的に確かめられる部分:** スクリプトと mise のタスクにする。
- **判断が要る部分:** 薄い project スキルにする。差分があるときだけ使う。

やらないこと:

- プラグインやスキルの更新そのもの（`/gstack-upgrade`、`claude plugin update`）
- 呼び忘れを防ぐ SessionStart の通知（案 C。呼び忘れが実際に起きたら別に検討する）
- sandbox・permissions・hooks の変更

<a name="facts"></a>

## 前提（事実）

- 更新は多い。直近 21 日で `/gstack-upgrade` は 14 回入力された。understand-anything は自動更新が on。crit 1.8.15・understand-anything 2.9.8・gstack 1.99.4.0 の更新も予定されている。
- 照合に要る情報は、手元のファイルから取れる。
  - プラグインの版とスコープ: `~/.claude/plugins/installed_plugins.json`
  - 有効かどうかと、スキルの公開範囲: `settings.json` の `enabledPlugins`・`skillOverrides`
  - gstack の版: `VERSION`
  - スキルの状態: 各 SKILL.md の frontmatter
  - プラグインの hooks: 各プラグインの `hooks/hooks.json`
- 照合のスクリプトは、今は作業文書（`test-report.md`）と棚卸しのコードブロックの中にあり、取り出さないと実行できない。
- 棚卸しには既に古い記述がある。「superpowers など 4 つは dotfiles を projectPath とする project スコープにも登録がある」は、今の `installed_plugins.json` では消えている。
- 前回の skill-routing スキルは、自動起動に頼って 77 セッションで 0 回だった。今回のスキルは、更新の後にユーザーが呼ぶか、ユーザーが「更新した」と言ったときに Claude が起動する前提にする。

<a name="design"></a>

## 設計

<a name="files"></a>

### 作るもの・変えるもの

| ファイル | 中身 |
| --- | --- |
| `claude/scripts/skills-check.py`（新規） | 照合のスクリプト。`check` と `snapshot` の 2 つのサブコマンド |
| `claude/skills-snapshot.json`（新規） | 前回、文書を合わせたときの状態の記録。`snapshot` が書く |
| `claude/scripts/test-skills-check.py`（新規） | スクリプトの単体テスト。偽の `~/.claude` を一時ディレクトリに作って試す |
| `claude/scripts/skill-usage.py`（新規） | 規則の効果の測定のスクリプト。棚卸しのコードブロックから取り出す（判断してほしい点 1 で決定） |
| `claude/scripts/test-skill-usage.py`（新規） | 測定のスクリプトの単体テスト。偽のトランスクリプトで件数を確かめ、会話の中身を出さないことを確かめる |
| `mise.toml` | `claude:skills-check`・`claude:skills-snapshot`・`claude:skill-usage` のタスクを足す |
| `.claude/skills/sync-skill-docs/SKILL.md`（新規） | 文書を直す project スキル |
| `claude/SKILL_INVENTORY.md` | 「更新したときの見直し」をタスクとスキルを使う手順に書き換える。「規則の効果の確認」のコードブロックを、タスクの実行方法に置き換える。古い記述（project スコープの重複登録）を直す |
| `.github/workflows/ci.yaml` | 2 つの単体テストを Repository checks のジョブに足す（判断してほしい点 3 で決定） |
| `CLAUDE.md`（リポジトリ） | 規約に「スクリプトを変えたらテストを実行する」を 1 行足す |
| `docs/work/20261116_skill-docs-sync/` | この plan と test-report |

`claude/scripts/` の下は、`statusline.sh` だけが `~/.claude` にリンクされる。新しいスクリプトはリンクされない。

<a name="script"></a>

### スクリプト（`skills-check.py`）

読むだけで、書くのは `snapshot` のときのスナップショットだけ。ネットワークは使わない。

**`check`:** 次の 2 つを比べ、違いを一覧にする。違いがなければ「変化なし」で終了コード 0、あれば 1、読めないファイルなどの失敗は 2。

1. **入っている状態とスナップショット**（前回、文書を合わせてから何が変わったか）
   - プラグイン・gstack の増減と版
   - スキルの増減
   - `disable-model-invocation`・`user-invocable`・`skillOverrides` の変化
   - 説明文の変化（ハッシュで比べる）
   - プラグインとスキルの hooks の変化（コマンドのハッシュで比べる）
2. **文書と入っている状態**（文書が今の状態と合っているか）
   - 規則・チートシート・棚卸しに出てくるスキル名が実在するか（前の作業の照合と同じ。プラグインの接頭辞の抜けも見る）
   - 入っているスキルが、すべて棚卸しに載っているか
   - 棚卸しの「提供元」の表の版が、入っている版と一致するか
   - gstack の状態ごとの節（有効・明示だけ・無効）が `skillOverrides` と一致するか

**`snapshot`:** 今の状態を `claude/skills-snapshot.json` に書く。

- 公開リポジトリなので、ユーザー名を含むパスは書かない（`check-repo.py` の `local-paths`）。`projectPath` と `installPath` は書かず、`$HOME` は `~` にする。
- 説明文と hooks のコマンドは、ハッシュだけを書く。ほかのプロジェクトの文章をそのまま写さない。何が変わったかは、スキルが新しい SKILL.md を読んで確かめる。

```json
{
  "version": 1,
  "plugins": {"crit@crit": {"version": "1.8.14", "scope": "user", "enabled": true}},
  "gstack": {"version": "1.99.3.0"},
  "skills": {"crit:crit": {"dmi": false, "user_invocable": true, "override": null, "description": "sha256:…", "hooks": null}},
  "agents": ["pstack:poteto-agent"],
  "plugin_hooks": {"crit@crit": ["PermissionRequest ExitPlanMode sha256:…"]}
}
```

<a name="skill"></a>

### スキル（`/sync-skill-docs`）

dotfiles の project スキル（`.claude/skills/`）にする。直す文書が dotfiles にあるため。ほかのリポジトリで作業中に更新したときは、dotfiles で呼ぶ。

説明文は「プラグインやスキルを足した・外した・更新した後（`/gstack-upgrade`、`claude plugin update` など）に使う」とし、ユーザーが「更新した」と言ったときに Claude が起動できるようにする。手順は次のとおり。

1. `main` にいれば、作業ブランチを切る（CLAUDE.md）。
2. `mise run claude:skills-check` を実行する。「変化なし」なら、そう伝えて終える。
3. 違いがあれば、その元を読む。読むものは次のとおり。
   - 新しい SKILL.md と hooks
   - gstack の CHANGELOG（git の履歴で前後の版を比べる）
4. 棚卸しの凡例に沿って、起動・状態・制約を判定する。外部への書き込み（`git push`、`gh` の書き込み、`~/` の外への出力）、localhost、worktree の有無を見る。既存のスキルとの重複は、規則の「Overlapping skills」で裁定する。
5. 棚卸しを直す。チートシートと規則は、役割や名前が変わったときだけ直す。規則の変更は、差分の中で目立つように報告する。
6. 提供元を足した・外したときは、`claude/setup.sh` のインストールの処理と `claude/README.md` のプラグインの一覧も見る。
7. `settings.json`（新しい gstack のスキルの `skillOverrides`、deny など）は直さず、提案だけにする。
8. 提供元ごとの注意（棚卸しの表）に従って、ユーザーに頼むことを伝える。
   - crit: sandbox の外で `mise run crit:profile-test` を実行してもらう。
   - understand-anything: hooks が変わったら、続けて使うか判断してもらう。
9. `mise run claude:skills-snapshot` を実行し、続けて `claude:skills-check` が「変化なし」になることと、`check-repo.py` を確かめる。
10. 差分を `/crit-review` で開く。commit と PR は、頼まれたときだけ行う。

スキルは手順と判断だけを持つ。提供元ごとの注意は棚卸しの表に置き、スキルからはそこを読む（同じことを 2 か所に書かない）。

> [!NOTE]
> **実装中に変えた点（2026-11-16）:** 手順 9 のスナップショットの作り直しは、Claude ではなくユーザーが `!` で行う。
>
> - **理由:** dotfiles の `.claude/settings.json` の `sandbox.filesystem.denyWrite` が `./claude` 全体を含むので、sandbox の中の Bash は `claude/skills-snapshot.json` を書けない。main の checkout では `claude/` が `~/.claude` にリンクされた生きた設定なので、この制限は緩めない。
> - **スキルの動き:** `! /usr/bin/python3 -B claude/scripts/skills-check.py snapshot` を示して頼み、実行された後に `check` が 0 になることを確かめる。
> - **影響を受けないもの:** 読むだけの `check` は sandbox の中で動く。単体テストは一時ディレクトリに書くので影響しない。

<a name="steps"></a>

## 手順

| # | 作業 | 確認 |
| --- | --- | --- |
| 1 | `claude/scripts/test-skills-check.py` を先に書く（失敗することを確かめる） | 次のケースのテストがあり、スクリプトがないので失敗する: 変化なし、スキルの追加と削除、`skillOverrides` の変化、説明文の変化、hooks の変化、文書に実在しない名前、文書に載っていないスキル、提供元の表の版の違い、スナップショットにユーザー名のパスが入らないこと |
| 2 | `claude/scripts/skills-check.py` を書く | 1 のテストがすべて通る |
| 2b | `claude/scripts/test-skill-usage.py` を先に書き、`claude/scripts/skill-usage.py` を棚卸しのコードブロックから取り出す | テストが通る。同じ期間（2026-10-27〜11-16）で、取り出す前のスクリプトと出力が一致する（トランスクリプトが消えていれば、残っている期間で比べる） |
| 3 | `mise.toml` にタスクを足す | worktree で `mise run claude:skills-check` が動く（mise の trust で止まる場合は、直接 `python3` で実行し、その旨を記録する） |
| 4 | 今の状態で `check` を実行する（スナップショットはまだない） | 文書と入っている状態の違いが出る。予想できる違い（古い記述や、更新済みのプラグインの版）と照らし合わせる |
| 5 | `.claude/skills/sync-skill-docs/SKILL.md` を書く | 説明文と手順が、この plan の「スキル」の節と一致する |
| 6 | スキルの手順で、棚卸しを今の状態に合わせ、`snapshot` を作る（初回の実地の確認） | `check` が「変化なし」で終了コード 0。古い記述が直っている |
| 7 | 棚卸しの「更新したときの見直し」を書き換え、`CLAUDE.md` に 1 行、`ci.yaml` にテストを足す | 文書の手順がタスクとスキルを指している |
| 8 | 規定の検査: `check-repo.py`、`test-check-repo.py`、`shellcheck`、`actionlint`、`test-skills-check.py`、`test-skill-usage.py` | すべて成功する |
| 9 | `test-report.md` を書き、差分を `/crit-review` で開く | `approved: true` |

<a name="risks"></a>

## リスク

- **スナップショットを作り直し忘れる。** 次の `check` で、文書を合わせた分まで「変化」として出る。スキルの最後の手順で必ず作り直し、`check` が 0 になることを確かめる。
- **文書の書き方に依存する照合がある。** 提供元の表の版と、gstack の状態ごとの節は、Markdown の形を読んで比べる。表の形を変えると照合が壊れる。テストで形を固定し、壊れたときは「読めない」（終了コード 2）として止める。
- **CI では実物を照合できない。** CI の環境には `~/.claude` がない。CI で動かすのは偽の `~/.claude` を使う単体テストだけで、実物の照合は手元で行う。
- **worktree で作業している。** 以前、worktree を抜けた後に、sandbox の書き込み禁止の設定が古いパスに残ったことがある。作業の後は、新しいセッションで確かめてもらう。

<a name="decisions-needed"></a>

## 判断してほしい点

いずれも 1 回目のレビュー（2026-11-16）で推奨どおりに決まった。

| # | 内容 | 結果 |
| --- | --- | --- |
| 1 | 測定のスクリプトも取り出すか | 取り出す。`claude/scripts/skill-usage.py` と `claude:skill-usage` のタスクにし、単体テストも足す |
| 2 | スキルの名前と置き場所 | `sync-skill-docs`、dotfiles の project スキル |
| 3 | CI に単体テストを足すか | 足す。2 つのスクリプトの単体テストを、Repository checks のジョブで実行する |
