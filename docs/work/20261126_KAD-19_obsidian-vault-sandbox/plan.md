---
status: in-progress
created: 2026-11-26
---

# Obsidian の Vault の `.obsidian` を Claude Code の sandbox から守る

Obsidian のコミュニティプラグイン（Vault の `.obsidian/plugins/<id>/`）は、次に Obsidian が起動したとき、Claude Code の sandbox の外で、ユーザーの権限で動く。Vault で起動したセッションでは Vault が作業ディレクトリになり、`.obsidian` にも書ける見込みである。プラグインの設定（Remotely Save の接続情報など）は `denyRead` に当たらないので、どのセッションからも読める。書き込みと読み取りの両方を、ユーザー設定で止める。

関連: Linear の KAD-19、PR #102（Vault のノートを点検するフック）

<a name="findings"></a>

## 調べたこと

2026-11-26 に調べた。

| 項目 | 結果 | 方法 |
| --- | --- | --- |
| dotfiles のセッションから、Remotely Save の `data.json` を開けるか | 開ける | sandbox の中で `: < <data.json のパス>`（中身は出さない） |
| dotfiles のセッションから、`obsidian/` に書けるか | 書けない | worktree で `touch obsidian/.kad19-probe` が `Operation not permitted` |
| Vault のセッションから、`.obsidian` に書けるか | 試していない。設定からは書ける見込み | ユーザー設定の `denyWrite` に当たる項目がなく、Vault の設定は sandbox を有効にするだけ |
| `~/Obsidian` の Vault | `main`、`dev_playbook`（`.claude` とプラグインあり）、`obsidian_kado.20261020`（プラグインなし） | `ls` |
| 作業用のリポジトリの `.obsidian` | `~/Dev` と `~/dotfiles` の深さ 6 までにない | `find` |
| グロブ | macOS では、`sandbox.filesystem` の 4 つのリストすべてで `*`・`**` を使える。`denyRead` は Read ツールを止めないので、`Read(...)` の deny も要る | 公式ドキュメント（settings-reference の Sandbox path prefixes、sandboxing） |
| ディレクトリを denyWrite にしたとき、そのディレクトリ自体の改名・削除も止まるか | 公式ドキュメントに記載がない | [実測で確かめる](#steps) |

Issue の「dotfiles で起動したセッションから `obsidian/` に書ける」は、2026-11-13 に対処済み（f08f15e）。Bash は `.claude/settings.json` の `./obsidian` の denyWrite、Edit は `Edit(/obsidian/**)` の ask で止まり、`check-repo.py` の `project-permissions` が守っている。この作業では扱わない。

<a name="decisions"></a>

## 決めたこと

1〜4 は 2026-11-26 の人間の判断。5 はリポジトリの慣習に合わせた（Crit で変えてよい）。6〜8 は 2026-11-26 の `/review` の後の人間の判断。

1. 範囲は、場所を問わず `.obsidian` という名前のフォルダ（`/**/.obsidian`）とする。`main` と `dev_playbook` に加えて、今後作る Vault も、ほかの場所へ動かした Vault も守る。最初はホームの下（`~/**/.obsidian`）としたが、手順 4 の実測と `/review` の指摘を受けて、名前で判定する形に変えた（6）。
2. 書き込みは `.obsidian` 全体を止める。`.obsidian` の中の symlink（`community-plugins.json` など）は、リンク先が dotfiles にあっても、リンク自体は Vault のセッションから差し替えられる見込みのため。テーマや、obsidian-git の設定（git の実行ファイルのパスなど）も止まる。Claude が `.obsidian` に書く理由はない。
3. 読み取りは `.obsidian/plugins` 全体を止める。`data.json` 以外の名前で認証情報を保存するプラグインにも効く。
4. Vault のルートの `.gitignore` も Bash から書けなくし、Edit ツールは ask にする。`.gitignore` で `.obsidian` を外すと、sandbox の外で動く obsidian-git の自動コミットが、プラグインの設定をリポジトリに入れる。そうなると、git のオブジェクトから読めてしまうため。グロブでは「`.obsidian` の隣の `.gitignore`」を表せないので、Vault の置き場所の決まり（`~/Obsidian/*/`）に絞る。
5. `check-repo.py` で守る（新しい検査 `obsidian-vault`）。mise・Playwright MCP と同じく、項目が欠けると失敗にする。
6. sandbox の項目は `/**/.obsidian`・`/**/.obsidian/plugins`、規則は `Edit(//**/.obsidian/**)`・`Read(//**/.obsidian/plugins/**)` にする。sandbox の中では、どこにも `.obsidian` という名前のフォルダを作れなくなる。`.gitignore` の項目は、場所で決まるので変えない。
7. この設定で止まらない経路は、公開リポジトリには書かず、Linear の KAD-19 に記録する。対策が要るものは、別の Issue にする。
8. Vault のノートの点検フックの profile（`claude/hooks/check-vault-note.sb`）にも、`.obsidian/plugins` を足す。この profile は、ユーザー設定の Read の deny が名前で拒否する場所を、`.md` でも読ませないことにしている。`~/dotfiles/obsidian`（Vault の設定ファイルの実体）は、ホームで起動したセッションから書けるが、コードが動く経路ではないので、この作業では守らない（Linear に記録する）。

<a name="changes"></a>

## 変えるもの

<a name="changes-settings"></a>

### `claude/settings.json`（ユーザー設定）

| キー | 足す項目 |
| --- | --- |
| `sandbox.filesystem.denyWrite` | `/**/.obsidian`、`~/Obsidian/*/.gitignore` |
| `sandbox.filesystem.denyRead` | `/**/.obsidian/plugins` |
| `permissions.deny` | `Edit(//**/.obsidian/**)`、`Read(//**/.obsidian/plugins/**)` |
| `permissions.ask` | `Edit(~/Obsidian/*/.gitignore)` |

denyWrite と Edit の deny を両方置く理由は、mise・Playwright MCP と同じ（Edit を ask に緩めても、Bash の守りが残る）。

<a name="changes-cc-crit"></a>

### cc-crit

`denyRead` に項目を足すと、今入っている cc-crit は `/crit-review` を DENIED で止める。そのため、同じ PR で次を直す。

| ファイル | 変更 |
| --- | --- |
| `claude/bin/cc-crit` | `COVERED_DENY_READ` に `/**/.obsidian/plugins` を足す |
| `claude/bin/cc-crit.sb` | `; denyRead: /**/.obsidian/plugins` と `(deny file-read* (regex #"/\.obsidian/plugins(/\|$)"))` を足す |
| `claude/hooks/tests/test-cc-crit.py` | `COVERED` に足す |
| `claude/hooks/tests/test-cc-crit-profile.py` | 試験用のリポジトリの `.obsidian/plugins/<id>/data.json` を読めないことのテスト |

<a name="changes-vault-note-hook"></a>

### Vault のノートの点検フック（決めたこと 8）

| ファイル | 変更 |
| --- | --- |
| `claude/hooks/check-vault-note.sb` | `.md` でも読ませない場所に `.obsidian/plugins/` を足し、コメントを直す |
| `claude/hooks/tests/test-check-vault-note.sh` | `.obsidian/plugins/` の下の `.md` を指すノートを読まないことのテスト（Seatbelt の部分。sandbox の外でだけ動く） |

<a name="changes-check-repo"></a>

### `check-repo.py`

- 定数 `OBSIDIAN_DENY_WRITE`・`OBSIDIAN_DENY_READ`・`OBSIDIAN_DENY`・`OBSIDIAN_ASK` と、検査 `obsidian-vault` を足す。どれかの項目が欠けると失敗する。
- `test-check-repo.py` に、すべてそろえば通ることと、1 つずつ欠けると失敗することのテストを足す。

<a name="changes-docs"></a>

### 文書

- `CLAUDE.md` の「sandbox と権限の禁止事項」に 1 項目足す。
- `.claude/rules/CLAUDE_CONFIG.md` に節「Obsidian の Vault」を足す（止める理由と、検査の内容）。
- `obsidian/README.md` の既知の制約に 1 項目足す（Claude Code からは `.obsidian` に書けず、プラグインのフォルダを読めない）。
- この作業の `test-report.md` を書く。

<a name="steps"></a>

## 手順と確かめ方

1. テストを先に書き、失敗することを確かめる。`python3 -B .github/scripts/test-check-repo.py`、`/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py`。
2. 設定・cc-crit・`check-repo.py` を直し、上の 2 つと `python3 -B .github/scripts/check-repo.py` が通ることを確かめる。
3. 文書を直し、`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・`zizmor --offline .` を実行する。
4. マージ前に、sandbox での効き方を実測する（人間の操作が要る）。
   1. Claude が、worktree の `tmp/kad19/`（Git の管理外）に、試験用の `.obsidian`（`plugins/p/data.json`、symlink、ふつうのファイル）を作る。
   2. 人間が、この worktree の `.claude/settings.local.json` に、[`claude/settings.json` に足す項目](#changes-settings)を一時的に足す。設定はセッション中に読み直される見込みで、効かなければセッションを開き直す。そのあいだ、cc-crit はこのファイルの denyRead を理由に `/crit-review` を止める。
   3. Claude が sandbox の中で、試験用の `.obsidian` への作成・上書き・削除・改名（`.obsidian` 自体も）・symlink の差し替え・読み取りが `Operation not permitted` になることを確かめる。Edit・Read ツールが拒否されることと、実在の Vault の `data.json` を `: <` で開けないことも確かめる。
   4. 人間が `settings.local.json` を元に戻す。
   5. 人間が、通常のターミナルで、worktree の `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py` を実行する。変更前の profile（`CC_CRIT_PROFILE` で指定する）では新しいテストが失敗することも確かめる。
5. `/review`、`/security-review`（sandbox の境界の変更のため）を実行し、Codex レビューを提案する。
6. ブランチの差分を `/crit-review` で開き、承認されたらコミット・push・PR 作成をする。CI を `gh pr checks` で確かめる。
7. マージ後（人間）: `~/dotfiles` を main に更新する。開いたままの Crit のレビューを閉じ、`pgrep -x crit` で何も出ないことを確かめてから、cc-crit を入れ直す（profile を先に入れる。[claude/README.md](../../../claude/README.md#cc-crit-install)）。その後、入れた 2 つのファイルがリポジトリのものと同じであることを `cmp` で確かめ、入れた profile でテストを実行する（`CC_CRIT_PROFILE=/usr/local/libexec/claude-crit/cc-crit.sb CC_CRIT_PROFILE_REQUIRED=1 /usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`）。`mise run crit:profile-test` はリポジトリの profile を試すので、入れた profile の確認にはならない。入れ直すまで、`/crit-review` は DENIED で止まる（安全側に倒れる）。
8. マージ後（人間が Vault で起動したセッション）:
   - 実在の Vault（`main`）では、読み取りだけを確かめる。`: < .obsidian/plugins/remotely-save/data.json` が拒否されること（`: <` は中身を出さない）。[Vault で起動したセッションへの影響](#impact-vault-session)のとおりかも確かめる（`git status`、Grep・Glob ツールでの Vault 全体の検索）。
   - 書き込みを伴う確かめ（`touch .obsidian/.kad19-probe`・`touch .gitignore`、Edit・Write ツール、試験用のノートの作成・編集・削除など）は、実在の Vault ではなく、試験用の Vault（`~/Obsidian/kad19-scratch`）で起動したセッションで行う（2026-11-26 の人間の判断）。何を確かめるかと、結果の扱いは Linear の KAD-19 に書く。
9. Linear の KAD-19 に、実測の結果と、この PR の外に残る経路を書く（公開リポジトリには書かない）。

<a name="impact"></a>

## 影響

- sandbox の中では、どこにも `.obsidian` という名前のフォルダを作れず、書き換えられない。`.obsidian` を追跡しているリポジトリでは、sandbox の中の git の操作（checkout など）が途中で止まる。今の作業用のリポジトリにはない。
- Claude は、プラグインのコードと設定を読めない。プラグインの不具合を調べるときは、人間がターミナルで見る。
- Vault の `.gitignore` は、Bash から書けない。Edit ツールでは承認画面が出る。
- マージしてから cc-crit を入れ直すまで、`/crit-review` は止まる。

<a name="impact-vault-session"></a>

### Vault で起動したセッション

`~/Obsidian/main` などで Claude Code を起動して、ノートを編集する場合の影響。どれも設定と Vault の手順書（AGENTS.md・README）から考えたもので、手順 8 で確かめる。

- 変わらないもの: ノートと添付ファイルの作成・編集・移動・削除（Edit・Write ツールと Bash）、`_System/` のスクリプトの実行、`.obsidian` の中のプラグイン以外の設定（`app.json` など）の読み取り、git の `status`・`add`・`commit`。`.obsidian/` は Vault の `.gitignore` で除外しているので、git はその中に触れない。手順書とスクリプトに `.obsidian` に書く手順はない（2026-11-26 に `AGENTS.md`・`README.md`・`_System/`・`.claude/skills/` を検索した）。Obsidian 本体は sandbox の外で動くので、影響を受けない。
- 変わるもの:
  - `.gitignore` を変えるときは、Edit ツールの承認画面が出る。Bash（`echo >> .gitignore` など）では書けない。
  - `.gitignore` を書き換える git の操作（ブランチの切り替え、`.gitignore` を変えたコミットのマージ・`restore`）は、sandbox の中では途中で止まる。Vault の Git は履歴を残すためのもので、ブランチを切り替える手順はないので、起きにくい。
  - `grep -r` や `find .` で Vault 全体を調べると、`.obsidian/plugins` の中で `Operation not permitted` が出て、終了コードが 0 でなくなる（結果はほかの場所の分は出る）。`rg` は既定で隠しフォルダを見ないので出ない。Grep・Glob ツールの挙動は、手順 8 で確かめる。

<a name="rollback"></a>

## 戻し方

PR を revert し、`~/dotfiles` を main に更新する。cc-crit は入れ直さなくても動く。新しい cc-crit は覆う項目が増えるだけなので、古い設定でも動く。ただし、入れ直すまでは、crit から `.obsidian/plugins` の下を読めないままになる。

<a name="out-of-scope"></a>

## 範囲外

この PR の外に残る経路は、Linear の KAD-19 に書く。
