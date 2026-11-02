# settings.json の 2 重読み込みに関する注意事項

dotfiles リポジトリのディレクトリで Claude Code を起動したときに起きる、設定の 2 重読み込みについてまとめる。

> [!NOTE]
> 2026-11-03 に `.claude/` を `claude/` へ改名した（案 B）。結果と手順は[改名の結果](#rename-result)、[他のマシンへの展開](#deploy-to-other-machines)、[リンクが消えたときの復旧](#link-recovery)を参照する。それ以外の節は、改名前の 2026-11-02 時点の調査記録で、Claude Code の仕様変更で変わる可能性がある。

<a name="summary"></a>
## 要点

- dotfiles で起動すると、`.claude/settings.json` は User 設定と Project 設定の両方として読み込まれる。
- フックは 2 回実行されない。`/hooks` の表示は重複するが、実害は小さい。
- 改名すると `.claude` 配下の保護が一部外れるため、現時点では改名しないことを推奨する。

<a name="facts"></a>
## 確認した事実

- **読み込み:** `~/.claude/settings.json` の実体は `dotfiles/.claude/settings.json` なので、dotfiles で起動すると同じファイルが User と Project の両方で読まれる。調査時の `/hooks` の 19 件の内訳は、設定由来の 8 件 × 2 とプラグイン由来の 3 件で、実質は 11 件。
- **フックの実行回数:** [公式ドキュメント](https://code.claude.com/docs/en/hooks)に "If you define the same handler in more than one settings file, it runs once." とある。過去のトランスクリプトでも、PostToolUse の `jq` フックは記録のある 27 回すべてで 1 回だけの実行だった。他のフックは記録がなく、ドキュメントでの確認のみ。
- **permissions:** 配列はマージされるが、中身が同じなので動作は変わらない。
- **実害:** あるセッションで、`CLAUDE.md`（約 9KB）の同じ内容が 2 回コンテキストに入った。起動時に 1 回、`.claude/` 配下を読んだ後にもう 1 回。読んだことが原因というのは推測。

<a name="rename-risks"></a>
## 改名のリスク

1. **保護が一部外れる:** `.claude` 配下の書き込みは自動承認されない仕様だが、`claude/` にすると通常のファイルになる。
   - `hooks/*.sh` と `statusline.sh` はサンドボックス外で実行されるので、権限境界に関わる。
   - `settings.json` はシンボリックリンク先として保護が続くとドキュメントにある。
   - `Edit(*.md)` の許可により、`claude/CLAUDE.md` や `rules/` が自動承認される可能性もある。
2. **設定が一時的に無効になる:** 改名してから `setup.sh` を再実行するまでリンクが切れ、deny ルール、サンドボックス、フックが効かなくなるはず（推測）。他のマシンでも `git pull` 後に同じことが起きる。古い文書に `/Users/kado/dotfiles` というパスがあるので、別のマシンがあるかもしれない。
3. **手元での実行が必要:** サンドボックスが `~/.claude` への書き込みを拒否するので、Claude Code から実行する場合は、移動とリンクの張り直しを `!` で実行する。

<a name="options"></a>
## 選択肢

| 案                                           | 効果                                                          | 代償                                                   |
| -------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------ |
| **A. 現状維持（推奨）**                      | 保護がそのまま残る                                            | `/hooks` の重複表示と `CLAUDE.md` の重複が残る         |
| **B. `claude/` に改名**                      | 原因がなくなり、dotfiles でも他のプロジェクトと同じ動作になる | [改名のリスク](#rename-risks)への対策と移行作業が必要  |
| **C. `--setting-sources user,local` で起動** | 改名せずに済む                                                | 毎回フラグが必要で、効果の範囲もドキュメントでは不明確 |

A を推奨するのは、B で得られる効果が表示の整理と少量のコンテキスト削減にとどまり、セキュリティを優先する方針に合わないため。`CLAUDE.md` の重複が気になる場合や、dotfiles でも他のプロジェクトと同じ動作で確認したい場合は、B にする価値がある。

<a name="rename-plan"></a>
## B に進む場合の計画

1. **移行:** `git mv .claude claude` と `setup.sh` の再実行を続けて行い、リンク先を確認する。
2. **保護の追加:** `ask` に `Edit(~/dotfiles/claude/**)` を追加する。サンドボックスの保護が足りなければ `sandbox.filesystem.denyWrite` も追加する。
3. **参照の更新:** `README.md`、`CLAUDE.md`、`.codex/README.md`、`.obsidian/README.md`、`setup.command` を直す。`docs/` の 10 ファイルは履歴なので変更しない。
4. **検証:** 新しいセッションで次を確認する。
   - `/hooks` が 11 件になっていること
   - `: >> claude/hooks/validate-command.sh` がサンドボックスで拒否されること
   - `test-protect-main-branch.sh` が通ること

<a name="rename-result"></a>
## 改名の結果

- **解消した:** `/hooks` の表示が 19 件から 11 件になり、`[Project]` がなくなった。
- **別途対処した:** `claude/` 配下のファイルを読むと、`claude/CLAUDE.md` が入れ子の `CLAUDE.md` として読み込まれ、同じ内容がコンテキストに重複していた。`.claude/settings.json` の `claudeMdExcludes` で除外した。
- **保護:** サンドボックスの書き込み拒否を改名前後で比べると、`skills/` だけが外れた。`.claude/settings.json` の `sandbox.filesystem.denyWrite` で `claude/` 全体を保護した。シェル起動時に読まれる `zsh/`、`.config/sheldon/`、`.config/starship/`、`mise/`、`mise.toml` と、アプリが読み込む `ghostty/config`、`vscode/tasks.json` も同様に保護した。

<a name="deploy-to-other-machines"></a>
## 他のマシンへの展開

> [!CAUTION]
> `~/.claude/` のリンクを張り直すときは、VS Code のものも含めて Claude Code のセッションをすべて閉じる。

セッション内の `!` でリンクを張り直したときは、次のサンドボックス付きコマンドが終わった時点で、`~/.claude/` の `settings.json`・`CLAUDE.md`・`rules`・`hooks` のリンクが消え、deny ルール・フック・サンドボックスがすべて無効になった。

Claude Code 2.1.309 のバイナリには `scrubbed replaced symlinked-deny path` という処理があり、時刻と消えたリンクの範囲も一致する。保護対象のリンクの差し替えを改ざんとして扱う処理が原因と考えられる（ソースは読めないので推測を含む）。リンクを張り直す前から開いている別のセッションも、同じ理由でリンクを消すおそれがある。`claude/setup.sh` は、Claude Code のセッション内と IDE の統合ターミナルでは実行を拒否する。IDE 拡張は統合ターミナルにも `CLAUDECODE` を設定するので、この 2 つを区別しない。IDE が開いていれば、セッションが残っている可能性も高い。

1. Claude Code のセッションをすべて閉じる。
2. `git pull` する。この時点で `~/.claude/settings.json` は Project 用の `.claude/settings.json` を指したままになり、他のリンクは切れる。`settings.json` はリンク切れにならないので気づきにくいが、`permissions`・`hooks`・`sandbox.enabled` が読み込まれず、保護が外れた状態になる。
3. IDE の統合ターミナルではなく、通常のターミナルで `~/dotfiles/claude/setup.sh` を実行する。
4. `ls -l ~/.claude/settings.json ~/.claude/CLAUDE.md ~/.claude/rules ~/.claude/hooks` でリンクを確認する。`~/.claude/settings.json` が `dotfiles/claude/settings.json` を指していること。`dotfiles/.claude/settings.json` のままなら、保護が外れている。
5. 新しいセッションで `/hooks` が 11 件になっていることを確認する。

<a name="link-recovery"></a>
## リンクが消えたときの復旧

> [!CAUTION]
> `claude/` がないコミット（改名前の `main` など）へ切り替えるときは、先に Claude Code のセッションをすべて閉じる。

`claude/` がないコミットへ切り替えると、リンク先がなくなるだけでなく、リンクそのものが消えることがある。2026-11-03 には、切り替えの 5 秒後に `~/.claude/` の `settings.json`・`CLAUDE.md`・`rules`・`hooks` のリンクが消えた（リンクを張り直したときと同じ処理が原因と考えられるが、推測を含む）。`mcp.json` などのリンクは残ったが、リンク先がないので切れた状態になった。

`claude/` があるブランチに戻しても、消えたリンクは戻らない。リンクが消えている間は、グローバルの deny ルール・フック・指示が読み込まれない。Claude Code からの張り直しは、サンドボックスと auto mode に拒否された。

1. Claude Code のセッションをすべて閉じる。
2. `claude/` があるブランチにいることを確認する。なければ `git switch` で戻す。
3. IDE の統合ターミナルではなく、通常のターミナルで `~/dotfiles/claude/setup.sh` を実行する。
4. `ls -l ~/.claude/settings.json ~/.claude/CLAUDE.md ~/.claude/rules ~/.claude/hooks` で、4 つとも `dotfiles/claude/` 配下を指していることを確認する。
5. 新しいセッションで `/hooks` が 11 件になっていることを確認する。

<a name="references"></a>
## 関連

- [Hooks](https://code.claude.com/docs/en/hooks)
- [Settings](https://code.claude.com/docs/en/settings)
- [Sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Permission modes](https://code.claude.com/docs/en/permission-modes)
