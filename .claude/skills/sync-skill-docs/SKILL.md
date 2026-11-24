---
name: sync-skill-docs
description: Use after adding, removing or updating a Claude Code plugin or skill (e.g. /gstack-upgrade, claude plugin update or install, 「gstack を更新した」「プラグインを入れた」), or when `mise run claude:skills-check` reports differences. Brings claude/SKILL_INVENTORY.md, SKILL_CHEATSHEET.md and rules/SKILL_ROUTING.md in line with what is installed.
---

# スキルの文書を、入っている状態に合わせる

プラグインやスキルを足した・外した・更新した後に、棚卸し（`claude/SKILL_INVENTORY.md`）・チートシート（`claude/SKILL_CHEATSHEET.md`）・規則（`claude/rules/SKILL_ROUTING.md`）を直す。照合は `mise run claude:skills-check` が機械的に行い、このスキルは違いがあるときの判断と文書の修正だけを行う。

更新そのもの（`claude/scripts/update-skills.sh`、`/gstack-upgrade`、`claude plugin update`）は行わない。

<a name="steps"></a>

## 手順

1. 今いるのが `main` なら、作業ブランチを切る（`git switch -c` と `git commit` は別の Bash 呼び出し）。
2. `mise run claude:skills-check` を実行する。`RESULT: no differences`（終了コード 0）なら「変化なし」と伝えて終える。終了コード 2 は照合できない状態なので、`ERROR:` の行を伝えて止まる。
3. 違いの元を読む。推測で書かない。
   - 足されたスキル・説明文や hooks が変わったスキル: 新しい SKILL.md（frontmatter と本文）
   - プラグインの hooks: `hooks/hooks.json`
   - gstack: `~/.claude/skills/gstack/CHANGELOG.md`。前の版との差分は `git -C ~/.claude/skills/gstack log`
4. 棚卸しの凡例に沿って、各スキルの「起動」「状態」「制約」を決める。見ること:
   - 外部への書き込み（`git push`、`gh` の書き込み、`~/` の外や `/tmp` への出力）
   - localhost での待ち受け、`git worktree add`、Bash からの Codex
   - 既存のスキルとの重複（規則の Overlapping skills で裁定する）
5. 棚卸しを直す。版・件数・表の行・一覧・制約を、入っている状態に合わせる。
6. チートシートと規則は、スキルの役割や名前が変わったとき（主担当が消えた、重複が増えた、など）だけ直す。規則は全プロジェクトで毎回読み込まれるので、変える行を最小にし、報告で目立たせる。
7. 提供元を足した・外したときは、`claude/setup.sh` のインストールの処理と、`claude/README.md` のプラグインの一覧も合わせる。
8. `claude/settings.json` は直さない。次のような変更は提案だけにする。
   - 新しい gstack のスキルの `skillOverrides`（増えたスキルは `on` のまま入る）
   - `permissions.deny` の追加
9. 棚卸しの「提供元ごとの注意」に沿って、ユーザーに頼むことを伝える。
   - crit: sandbox の外で `mise run crit:profile-test` を実行してもらう。
   - understand-anything: hooks が変わったら、続けて使うか判断してもらう。
10. `git diff claude/settings.json` に差分があれば、CLI がキーの並びを変えただけかを `jq -S` で確かめる（中身が変わっていたら伝える）。
11. 文書が合ったら、スナップショットの作り直しをユーザーに頼む。通常のターミナルで実行するよう、次のコマンドの `<root>` を、このセッションの作業ツリーのルート（`git rev-parse --show-toplevel`。worktree ならそのパス）の絶対パスに置き換え、そのまま入力できる形で示す。スナップショットは、スクリプトがあるツリーに書かれる。sandbox の中の Bash は `claude/` に書けない（dotfiles の `.claude/settings.json` の `denyWrite`）ので、Claude は実行しない。Claude Code のプロンプトの `!` も、セッションによっては sandbox の中で動き、失敗する。

    ```
    /usr/bin/python3 -B <root>/claude/scripts/skills-check.py snapshot
    ```

    ユーザーが実行したら、`mise run claude:skills-check` が終了コード 0 になることと、`python3 -B .github/scripts/check-repo.py` を確かめる。
12. 差分を `/crit-review` で開く。コメントが返ったら直して開き直す。`approved: true` が返ったら、確認を挟まずに、承認された差分をコミットし、CLAUDE.md の Git 節に従って push、PR の作成、`gh pr checks` の確認まで進める。PR のマージはしない。

<a name="notes"></a>

## 注意

- sandbox の中では、`claude/` と `.claude/skills/` に Bash から書けない。文書は Edit と Write のツールで直し、スナップショットはユーザーに通常のターミナルで作ってもらう（手順 11）。
- スナップショット（`claude/skills-snapshot.json`）は、文書を合わせた後にだけ作り直す。先に作り直すと、文書に残った古い記述が次の `check` で見つからなくなる。
- スナップショットには説明文と hooks のハッシュだけが入る。何が変わったかは、新しいファイルを読んで確かめる。
