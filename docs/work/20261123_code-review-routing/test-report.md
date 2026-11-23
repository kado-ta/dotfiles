---
status: done
created: 2026-11-23
---

# 他人の PR のレビューを `/code-review` に分ける: 試験記録

関連: [plan.md](plan.md)、[PR #88](https://github.com/kado-ta/dotfiles/pull/88)

<a name="checks"></a>

## 検査

コミット `4ff34a6` で実行し、Codex の指摘を直した後にもう一度実行して、同じ結果だった（sandbox の中）。CLAUDE.md の行数（HTML コメントと空行を除く）は 79。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 93 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし |
| `actionlint` | 指摘なし |
| `python3 -B claude/scripts/test-skill-usage.py` | 5 件 OK（足したテストは、直す前に失敗することを確かめた） |
| `/usr/bin/python3 -B claude/scripts/skills-check.py check` | 違いなし |
| `gh pr diff 87 --name-only` | sandbox の中で読めた（公開のリポジトリ） |
| GitHub Actions（PR #88、`4ff34a6`） | Hook regression tests・Repository checks とも success |

<a name="codex-1"></a>

## Codex レビュー 1 回目

- 実行: 2026-11-23T14:05:52Z、コミット `4ff34a6`。ユーザーが通常のターミナルで `codex review --base main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を実行した。
- 結果は `~/.codex/sessions` の `last_agent_message` から読んだ。
- 全体: patch is incorrect（confidence 0.98）。Codex 自身の確認では、リポジトリの検査・スキルの文書の照合・ShellCheck・actionlint は通り、単体テスト 2 本は読み取り専用の sandbox で一時ディレクトリを作れず確かめられなかった。

| # | 優先度 | 場所 | 指摘 |
| --- | --- | --- | --- |
| C1 | P1 | `claude/SKILL_INVENTORY.md:257-258` | `gh pr diff --name-only` は PR の比較元からの変更しか示さない。別のブランチをベースにした PR では、ベースで足された `.claude/settings.json` が一覧に出ない。設定が同じでも、既存の hooks が呼ぶスクリプトだけが変われば、確かめていないコードが sandbox の外で動く。信頼済みのツリーと取得したコミットを比べ、自動で動く設定とその参照先を確かめられなければ、取り込まずに差分だけでレビューする |
| C2 | P2 | `claude/rules/SKILL_ROUTING.md:32` | 毎回読み込まれる SKILL_ROUTING は高リスクに `/security-review` を求めている。チェックアウトしていない PR に重ねない例外を、ルーティングにも書く |
| C3 | P2 | `claude/SKILL_INVENTORY.md:259-260` | `FETCH_HEAD` を確かめても、`/code-review medium <URL>` はその時点の差分を取り直す。取り込んだ後に PR が更新されると、古いファイルを新しい差分の文脈として読む |
| C4 | P2 | `claude/SKILL_INVENTORY.md:259` | `origin` がフォークで URL が上流を指すと、`pull/<番号>/head` を取得できないか、別の PR を取得する |
| C5 | P2 | `claude/SKILL_INVENTORY.md:252-253` | Claude Code は github.com の URL を `-R <owner>/<repo>` に直し、ホストを渡さない。`GH_HOST` が GitHub Enterprise の環境では、別の差分をレビューしうる |
| C6 | P3 | `claude/SKILL_INVENTORY.md:384` | 重複の判定は、セッションではなく対象ごとに行う。同じセッションにほかの PR の `/code-review` があっても、同じ差分に 2 種類のレビューを重ねた組があれば重複に数える |

<a name="codex-1-decisions"></a>

### 採否

C1 と C2 は前の決定（plan の D1・D3）を変えるので、人間が選んだ。

| # | 採否 | 理由と対応 |
| --- | --- | --- |
| C1 | 採用（手順をやめる） | 指摘どおり、変更ファイルの一覧では、ベースで足された設定と、hooks・MCP などが呼ぶスクリプトの書き換えを確かめきれない。参照先に上限がないので、確認を強めても漏れが残る。worktree に取り込む手順をやめ、全体が要るときはユーザーが `/code-review ultra <PR の URL>` を打つ（後の Crit で、`ultra` は提案せず人間が読むことにした。[plan](plan.md#crit-changes)） |
| C2 | 採用 | CLAUDE.md の Tools 節に「高リスクでも、今のブランチを見るレビューは重ねない」を足した。行数は 79 のまま。SKILL_ROUTING は変えない |
| C3 | 対象外 | C1 で worktree の手順ごとなくなった |
| C4 | 対象外 | 同上 |
| C5 | 不採用 | この環境の gh は `github.com` だけで、`GH_HOST`・`GH_ENTERPRISE_TOKEN` もない（2026-11-23 に確かめた） |
| C6 | 採用 | 計測の注記を、対象ごとに分けて判定する書き方に直した |
