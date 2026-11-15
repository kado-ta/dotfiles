---
status: done
created: 2026-11-16
---

# 検証記録

[plan](plan.md) の手順 1〜8 の記録。

<a name="unit-tests"></a>

## 1. 単体テスト

テストを先に書き、スクリプトがない状態で失敗することを確かめてから実装した。

| テスト | 件数 | 結果（`python3` 3.15 と `/usr/bin/python3` 3.9） |
| --- | --- | --- |
| `claude/scripts/test-skills-check.py` | 16 | すべて成功 |
| `claude/scripts/test-skill-usage.py` | 3 | すべて成功 |

`test-skills-check.py` のケース:

- 変化なし（終了コード 0）
- スナップショットがない
- スキルの追加・削除
- 削除されたスキルが文書に残っている
- `skillOverrides` の変化と、gstack の状態ごとの節の不一致
- スナップショットがない状態での節の不一致
- 説明文の変化
- プラグインの hooks の変化
- SKILL.md の frontmatter の hooks の変化
- 文書の実在しない名前
- プラグインの版と gstack の版の変化（スナップショットと文書の両方）
- 無効にしたプラグインのスキルを数えないこと
- 提供元（gstack・個人・project）の判定と、その変化
- スナップショットにローカルのパスが入らないこと
- 棚卸しのアンカーがないとき終了コード 2

`test-skill-usage.py` のケース:

- 期間内の件数（期間の外を数えない）
- 会話の中身を出力しないこと
- 引数が足りないときに失敗すること

<a name="extraction"></a>

## 2. 測定のスクリプトの取り出し

- `claude/scripts/skill-usage.py` は、docstring より後のコードが、棚卸しにあったコードブロックと同じ（`cmp` で確認）。
- 2026-10-27〜11-17 の期間で、取り出す前と後の出力が一致した（87 行、`cmp` で確認）。
- 棚卸しのコードブロックは消し、`mise run claude:skill-usage 2026-11-16 2026-12-07` の実行方法に置き換えた。

<a name="real-run"></a>

## 3. 実地の確認（初回）

実物の `~/.claude` で `check` を実行し、見つかった違いを直した。

| # | 見つかったこと | 対応 |
| --- | --- | --- |
| 1 | `anthropic-skills:*`（13 件をまとめた書き方）を、実在しない名前と判定した | ワイルドカードを名前として扱わないようにし、テストに足した |
| 2 | 新しい project スキル `/sync-skill-docs` を、実在しない名前と判定した | リポジトリの `.claude/skills/` も集めるようにし、テストに足した。棚卸しの「提供元」の表とスキルの表に足した |
| 3 | 棚卸しの「superpowers など 4 つは project スコープにも登録がある」が、今の `installed_plugins.json` と合わない | 文章の記述なので、`check` では見つけられない（plan の時点で分かっていた）。この作業ではいったん行を消したが、並行して PR #30 が「重複登録があり、2026-11-16 に消した」という記録に書き換えていた。main（`4d318c1`）に rebase したときに衝突したので、main の記述を採った |
| 4 | gstack のスキル 62 件を個人スキルと判定した。gstack の状態ごとの節の照合が、何も比べずに一致を返していた | 下の節 |

<a name="provider-bug"></a>

### gstack の判定の誤り

- **原因:** 実物の配置が、テストの模擬環境と違っていた。
  - gstack のスキルは、ディレクトリ自体は実物で、中の `SKILL.md` だけが `gstack/<name>/SKILL.md` へのリンク。
  - `_gstack-command` と `connect-chrome` は、gstack の setup が直接置いた実ファイル。
  - スクリプトはディレクトリの実体を見ていたため、これらを個人スキルと判定した。テストはディレクトリごとのリンクしか作っていなかった。
- **見つけた経緯:** 初回のスナップショットを作った後に、提供元ごとの件数を数えたら、gstack 1・個人 66 だった（正しくは gstack 63・個人 4）。
- **対応:**
  - テストの模擬環境を実物の配置にし、実ファイルの場合と、提供元の変化の検出を足した。4 件が失敗することを確かめた。
  - スクリプトは、`SKILL.md` の実体の場所で判定するようにした。`~/.claude/skills` の外なら個人、中なら gstack。スナップショットとの比較に、提供元も入れた。
- **スナップショット:** 誤った状態で作ったものを、ユーザーに作り直してもらった。

<a name="final-state"></a>

## 4. 最終の状態

- `mise run claude:skills-check`: `RESULT: no differences`、終了コード 0
- スナップショット（`claude/skills-snapshot.json`、34 KB）:
  - 7 プラグイン、154 スキル（gstack 63、pstack 58、superpowers 15、understand-anything 9、個人 4、crit 3、claude-code-setup 1、project 1）、エージェント 12
  - `/Users/` を含む行は 0
  - ユーザーが `! /usr/bin/python3 -B claude/scripts/skills-check.py snapshot` で作った（sandbox の中の Bash は `claude/` に書けないため）
- mise のタスク: `claude:skills-check`・`claude:skill-usage` は worktree で動き、引数も渡ることを確かめた。`mise` は「tracking config」の記録を sandbox の中で書けずに WARN を出すが、実行には影響しない。

<a name="rebase"></a>

### main への追従

並行していた PR #30（project スコープの記録）と PR #31（`/cso`）のマージ後の main（`4d318c1`）に rebase した。

- sandbox の中の Bash は `claude/` に書けないので、rebase はユーザーが `!` で実行した。
- 衝突は棚卸しの 1 行だけで、main の記述を採って解決した（Edit ツール）。
- rebase の後、main との差分が自分の変更だけであることを確かめた。下の検査はすべて rebase の後に実行した。

<a name="commands"></a>

## 5. 実行した検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 8 項目すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | exit 0 |
| `actionlint` | exit 0（`ci.yaml` に足したステップを含む） |
| `python3 -B claude/scripts/test-skills-check.py` | 16 tests OK |
| `python3 -B claude/scripts/test-skill-usage.py` | 3 tests OK |

<a name="unverified"></a>

## 6. 確かめていないこと

- **スキルの起動:** ユーザーが「gstack を更新した」と言ったときに、Claude が `/sync-skill-docs` を起動するか。project スキルは、dotfiles で起動した新しいセッションでないと一覧に載らない。
- **差分があるときの通し:** スキルの手順を、実際の更新（crit 1.8.15、understand-anything 2.9.8、gstack 1.99.4.0）で最後まで試していない。最初の更新のときが、通しの確認になる。
- **CI:** 単体テストのステップが、GitHub Actions で通るか。PR の CI で確かめる。
