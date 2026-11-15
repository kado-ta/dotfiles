---
status: done
created: 2026-11-15
---

# pstack の導入の検証記録

関連: [plan.md](plan.md)、[research-skill-inventory.md](research-skill-inventory.md)

<a name="environment"></a>

## 環境

- Claude Code 2.1.323、sandbox 有効、permission mode は auto。
- pstack 0.15.42（`pstack@cursor-plugins`、user スコープ、gitCommitSha bf0c7cd）。事前に読んだのは 0.15.36 で、インストールの時点で上流が進んでいた。差分は [調査メモ](research-skill-inventory.md#pstack-focus) に書いた。
- インストールは、ユーザーが `!` で `claude plugin marketplace add cursor/plugins` と `claude plugin install pstack@cursor-plugins` を実行した。
- 動作の確認は、セッションを `claude --continue` で再開してプラグインと settings を読み直してから行った。

<a name="results"></a>

## 結果

| # | 確認 | 方法 | 結果 |
| --- | --- | --- | --- |
| 1 | インストール | `claude plugins list`、`installed_plugins.json` | pstack 0.15.42、user、有効 |
| 2 | 設定ファイルのリンク | `ls -la ~/.claude/settings.json` | dotfiles の `claude/settings.json` へのシンボリックリンクのまま |
| 3 | settings の差分 | `jq -S` で整形して HEAD と比較 | `enabledPlugins` と `extraKnownMarketplaces` の 2 項目と、手で足した deny 3 件だけ。CLI が書き込むときに `skillOverrides` を `model` の直後に移したが、中身は同じ |
| 4 | hooks・MCP・LSP | インストール先の探索、`claude plugin details` | どれもない |
| 5 | コンテキストに載るスキル | 再開後のセッションのスキル一覧 | `pstack:setup-pstack` だけ。ほかの 57 件は載らない。`claude plugin details` の常時約 3,523 トークンという見積もりは過大 |
| 6 | `Skill(pstack:setup-pstack)` の deny | Claude が Skill ツールで起動 | 「Skill execution blocked by permission rules」で止まった。deny を確定した後にも、もう一度止まることを確かめた。一覧からは消えない |
| 7 | `Agent(pstack:poteto-agent)`・`Agent(pstack:comment-sicko)` の deny | Claude がサブエージェントとして起動 | どちらも「denied by permission rule ... from userSettings」で止まった。`pstack:` を付ける書式で一致する |
| 8 | deny がユーザーのスラッシュコマンドを止めるか | `Skill(pstack:bro)` を deny に入れて、ユーザーが `/pstack:bro` を入力 | 止まらず、スキルが動いた。plan の判断 5 の「止めない場合」に確定し、`Skill(pstack:bro)` は外した |
| 9 | `/pstack:how` | 読み取りだけの質問（cc-safe-push の判定） | アダプタの相対リンクがインストール先で解決できた。Explore エージェント 1 つで動いた。引用した行番号 6 か所を照合して一致した。ファイルの変更なし |
| 10 | `/pstack:why` | 読み取りだけの質問（cc-safe-push が一時リポジトリから push する理由） | サブエージェントなしで、`git log` と `gh pr view`（読み取り専用トークン）で答えを出せた。導入時の PR #155 は今の origin では引けなかった（リポジトリの事情） |
| 11 | 依存ファイル | インストール先で存在を確かめた | 重点と依存の 22 スキル、architect の参照 3 件、アダプタ、`poteto-mode` の Subagents 節がすべてある |
| 12 | 既存のプラグイン | `claude plugins list`、スキル一覧 | superpowers・crit・understand-anything・claude-code-setup・ruby-lsp すべて有効のまま |
| 13 | `setup.sh` の判定 | 追加した grep の条件を、ネットワークを遮断した状態と許可した状態で実行。`bash -n` | どちらでも一致した。構文も問題なし |
| 14 | リポジトリの検査 | `python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、shellcheck、`actionlint` | すべて成功（test-check-repo は 43 件 OK） |

<a name="not-verified"></a>

## 検証していないこと

- `architect`・`interrogate`・`arena`・`blast-radius` の実行。書き込みと worktree を伴い重いので実行していない（動作未検証）。sandbox の中で worktree を使えるか、既定の Fable 5.2 をこのアカウントで使えるかも未確認。
- deny したエージェントの description が、Agent ツールの一覧から消えるか。
- 新しいマシンでの `setup.sh` の通しの実行。Claude Code のセッションの中では実行を拒否する作りなので、実行していない。

<a name="residual-risks"></a>

## 残るリスク

- 上流の更新が速い（0.15.36 から 0.15.42 まで 2 日で、`how` と `why` の作りと `arena` の既定のモデルが変わった）。自動更新は off のままにし、更新のたびに hooks・スキルの一覧・依存を見直す（`claude/README.md` に記載）。
- 使わないスキルは、ユーザーが入力すれば動く。`poteto-mode` の playbook は `gh pr create`・`gh pr merge`・`git push` を使うが、既存の制御（deny、ask と読み取り専用トークン、cc-safe-push）で止まる。
- 上流が新しいスキルを足しても、deny は自動では広がらない。モデルから起動できるスキルが増えたら、スキル一覧に現れるので、更新時に確かめる。
- `arena`・`interrogate`・`architect` は既定で複数の Claude のモデルを起動するので、コストがかさむ。別モデルによる独立レビューにはならない。
- CLI はプラグインの操作のたびに `settings.json` のキーの並びを変えうる。
