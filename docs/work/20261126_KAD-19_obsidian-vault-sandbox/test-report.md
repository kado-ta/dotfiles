---
status: done
created: 2026-11-26
---

# 試験記録: Obsidian の Vault の `.obsidian` を sandbox から守る

関連: [plan.md](plan.md)

<a name="checks"></a>

## テストと検査

2026-11-26 に、この worktree の sandbox の中で実行した。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/test-check-repo.py` | 実装前は、新しいテストが 6 件（subTest 単位）失敗した。実装後は 151 件 OK |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` | 実装前は 3 件失敗した。実装後は 94 件 OK |
| `python3 -B .github/scripts/check-repo.py` | 全 PASS（`obsidian-vault` を含む） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし |
| `actionlint` | 指摘なし |
| `zizmor --offline .` | 指摘なし |
| `CC_CRIT_PROFILE=<変更前の cc-crit.sb> /usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`（sandbox の外、人間が実行） | 新しい `test_read_obsidian_plugin_data_denied` の 1 件だけが失敗した（30 件、スキップ 1） |
| `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`（sandbox の外、人間が実行） | OK（30 件、スキップ 1） |
| `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh`（sandbox の外、人間が実行。`check-vault-note.sb` を直す前） | 新しい `.obsidian/plugins/` のケースの 1 件だけが失敗した（pass=44 fail=1） |
| `bash claude/hooks/tests/test-check-vault-note.sh`（sandbox の中、`check-vault-note.sb` を直した後） | pass=27 fail=0（Seatbelt の部分はスキップ） |
| `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh`（sandbox の外、人間が実行。`check-vault-note.sb` を直した後） | pass=45 fail=0 skip=0 |

<a name="sandbox-probe"></a>

## sandbox での実測（plan の手順 4）

worktree の `tmp/kad19/vault`（Git の管理外）に試験用の Vault を作った。worktree の `.claude/settings.local.json` に、ユーザー設定に足すのと同じ項目を一時的に置き、sandbox の中の Bash から同じ操作をした。項目は、最初の形（`~/**/.obsidian` など）と、`/review` の後に変えた名前で判定する形（`/**/.obsidian` など。plan の決めたこと 6）の 2 回置いた。

| 操作 | 規則なし | 最初の形 | 名前で判定する形 |
| --- | --- | --- | --- |
| `.obsidian` にファイルを作る | できた | `Operation not permitted` | `Operation not permitted` |
| `.obsidian/app.json` に追記する | できた | `Operation not permitted` | `Operation not permitted` |
| プラグインのコード（`plugins/p/main.js`）に追記する | できた | `Operation not permitted` | `Operation not permitted` |
| `.obsidian` のファイルを消す | できた | `Operation not permitted` | `Operation not permitted` |
| `.obsidian` の中の symlink を差し替える | できた | `Operation not permitted` | `Operation not permitted` |
| `.obsidian` 自体を改名する | できた | `Operation not permitted` | `Operation not permitted` |
| 別の場所に `.obsidian` を作る | できた | `Operation not permitted` | `Operation not permitted` |
| Vault をホームの外（`$TMPDIR`）へ動かし、動かした先でプラグインのコードに追記する | できた | できた | `Operation not permitted`（動かすことはできる） |
| `$TMPDIR` に `.obsidian` を作る | 試していない | 試していない | `Operation not permitted` |
| プラグインの設定（`plugins/p/data.json`）を読む | できた | `Operation not permitted` | `Operation not permitted` |
| `plugins` を一覧する | できた | `Operation not permitted` | `Operation not permitted` |
| 実在の Vault の Remotely Save の `data.json` を開く（中身は出さない） | できた | `Operation not permitted` | `Operation not permitted` |
| `grep -r` で、`data.json` の偽の値を探す | 見つかった | 見つからない | 見つからない |
| `.obsidian/app.json` を読む | できた | できた（想定どおり） | できた（想定どおり） |
| ノートに追記する、ノートを作る | できた | できた（想定どおり） | できた（想定どおり） |

大文字・小文字を変えたパス（`.OBSIDIAN`・`.Obsidian`・`PLUGINS` など）でも、どちらの形でも、作成・追記・読み取り・一覧の 7 項目がすべて `Operation not permitted` になった（ホームの APFS は大文字・小文字を区別しない）。

この PR の外に残る経路は、Linear の KAD-19 に書く。

実測の後、人間が worktree の `.claude/settings.local.json` を消し、Claude が試験用の Vault（`tmp/kad19`）を消した（2026-11-26）。

<a name="tool-rules"></a>

### Read・Edit ツール

worktree の `.claude/settings.local.json` に置いた Read・Edit の deny は、ツールに効かなかった。sandbox の設定には取り込まれていた（Bash は上の表のとおり止まった）。Read ツールで試験用の `data.json` と実在の Vault のプラグインの `manifest.json`（秘密を含まない）を読めた。Edit ツールで試験用の `.obsidian/app.json` を書き換えられた。

規則の形のせいかを切り分けるため、存在しないパスを Read ツールで読み、拒否されるかを比べた。

| 置いた場所 | 規則 | 結果 |
| --- | --- | --- |
| `settings.local.json`（worktree） | `Read(~/**/.obsidian/plugins/**)` | 拒否されない |
| `settings.local.json`（worktree） | `Read(~/**/kad19-probe-a)` | 拒否されない |
| `settings.local.json`（worktree） | `Read(~/kad19-probe-b/**)` | 拒否されない |
| `settings.local.json`（worktree） | `Read(//<HOME>/kad19-probe-c/**)` | 拒否されない |
| `settings.local.json`（worktree） | `Read(**/kad19-probe-d)`（worktree の中のパス） | 拒否されない |
| ユーザー設定 | `Read(~/.ssh/**)` | 拒否された |
| ユーザー設定 | `Read(~/**/credentials)` | 拒否された |
| ユーザー設定 | `Read(~/**/*.key)`（`Read(**/*.key)` も当たりうる） | 拒否された |

形を変えても、worktree の `settings.local.json` の規則はどれも効かなかった。ユーザー設定の `~/**/` の形は効いた。

<a name="tool-rules-user-settings"></a>

#### 本番のユーザー設定での確認

Codex の 1 回目の指摘を受けて、マージ前に確かめた（2026-11-26）。人間が `~/dotfiles/claude/settings.json` をバックアップし、`permissions.deny` の `Edit(//**/.obsidian/**)`・`Read(//**/.obsidian/plugins/**)` と、`permissions.ask` の `Edit(~/Obsidian/*/.gitignore)` を一時的に足した。試験用のファイル（`tmp/kad19-tool`。中身は偽の値）と存在しないパスで、次を確かめた。

| ツール | 対象 | 結果 |
| --- | --- | --- |
| Read | 試験用の `.obsidian/plugins/p/data.json` | 拒否された |
| Read | ホームの下の、存在しない `.obsidian/plugins/x.json` | 拒否された |
| Read | ホームの外（`/private/tmp`）の、存在しない `.obsidian/plugins/x.json` | 拒否された |
| Read | 実在の Vault の `plugins/html-viewer/manifest.json`（秘密を含まない） | 拒否された |
| Read | 大文字・小文字を変えたパス（`.OBSIDIAN/PLUGINS/p/data.json`） | 拒否された |
| Read | プラグインの設定を指す、`.obsidian` の外の symlink | 拒否された（文言は「Permission to read … has been denied」） |
| Edit | 試験用の `.obsidian/app.json` | 拒否された。中身は変わっていない |
| Write | 試験用の `.obsidian/new-probe.json`（新しいファイル） | 拒否された。作られていない |
| Write | 大文字・小文字を変えたパス（`.OBSIDIAN/case-probe.json`） | 拒否された。作られていない |

`Edit(~/Obsidian/*/.gitignore)` の ask は、この worktree の外の場所なので、ここでは確かめられなかった（作業ディレクトリの外への書き込みは、規則より先に止まる）。マージ後に、試験用の Vault で起動したセッションで確かめる（plan の手順 8）。

<a name="codex-review"></a>

## Codex のレビュー

<a name="codex-review-1"></a>

### 1 回目（2026-11-26T13:07Z、af46b2c、`codex review --base main`）

結論は "patch is incorrect"（確信度 0.96）。指摘は 3 件で、すべて P2。

| 指摘 | 採否 | 対応 |
| --- | --- | --- |
| cc-crit のインストールで、ラッパーを profile より先に入れている。profile の入れ替えが失敗すると、新しいラッパーが古い profile で crit を動かす | 採用 | `claude/README.md` のインストールの手順で、profile を先に入れる |
| 入れ直す前から動いている crit の daemon は、古い profile のまま使われ続ける（cc-crit は同じレビューの daemon につなぐ） | 採用 | `claude/README.md` の更新の手順と plan の手順 7 に、開いたままのレビューを閉じて `pgrep -x crit` で確かめることを足す |
| Read・Edit・Write ツールの拒否を、マージ前に本番と同じユーザー設定の範囲で確かめていない | 採用（2026-11-26 の人間の判断） | 本番のユーザー設定に一時的に規則を足して確かめた（[本番のユーザー設定での確認](#tool-rules-user-settings)） |

<a name="codex-challenge-1"></a>

### 2 回目（2026-11-26T13:24Z、af46b2c、challenge）

変更前と比べた後退と、壊れる入力・設定・手順を、全件挙げるよう頼んだ。1 回目と重なる 2 件（profile を先に入れる、古い daemon）のほかは、次のとおり。

| 指摘 | 採否 | 理由・対応 |
| --- | --- | --- |
| 入れ直した後の `mise run crit:profile-test` は、リポジトリの profile を試すので、入れた profile の確認にならない | 採用 | plan の手順 7 に、`cmp` と、入れた profile を `CC_CRIT_PROFILE` で指定したテストを足した |
| 設定を revert しても、新しい profile のままでは crit から `.obsidian/plugins` を読めない | 採用 | plan の戻し方に書き足した |
| `obsidian/setup.sh`・他の Vault への反映・新しい端末の手順（`git restore -- .gitignore`）は、Claude Code の sandbox の中では止まる | 採用 | `obsidian/README.md` に、通常のターミナルで実行することを書き足した |
| plan の手順 8 が、実在の Vault で `touch` を試すことになっていて、書き込みは試験用の Vault で行う決まりと食い違う | 採用 | 実在の Vault では読み取りだけを確かめ、書き込みは試験用の Vault で行うように直した |
| `CLAUDE_CONFIG.md` の「dotfiles のセッションから `~/dotfiles/obsidian/` に書けない」は、Edit ツールでは承認すれば書ける | 採用 | 「Bash から書けず、Edit ツールは承認を求める」に直した |
| 試験記録では、一時的な設定を戻すのが未実施のままになっている | 採用 | 下の「未実施」を直した（戻して、試験用の Vault も消した） |
| `.obsidian` を含むリポジトリ・アーカイブ・stash の展開や、プラグインのフォルダの検索が、sandbox の中で止まる | 不採用（受け入れる） | 決めたこと 6 で受け入れた引き換え。plan の「影響」に書いてある。今の作業用のリポジトリにはない |
| 以前に追跡したプラグインのファイルがあると、`.gitignore` の前提が崩れる | 不採用 | `main`・`dev_playbook` の Vault とも、`.obsidian` の下は今も過去も追跡していない（`git ls-files` と `git log --all` で 0 件。2026-11-26 に確かめた） |
| 普通のノートからプラグインの `.md` へのアンカー付きリンクがあると、点検フックの点検全体が止まる | 不採用（受け入れる） | そうしたリンクは今のノートの使い方では起きにくい。Linear の KAD-19 に記録する |
| `check-repo.py` の `obsidian-vault` は、項目の文字列があるかだけを見る（sandbox を無効にしても通るなど） | 不採用 | ほかの検査と同じ方針で、この PR より前からの性質 |
| `check_deny_read` が照合する設定の範囲が、Claude Code が読む設定の範囲と違う | 不採用 | この PR より前からの性質。Linear の KAD-19 に記録済み |
| 大文字・小文字を変えたパスを、cc-crit と点検フックの profile でも止められるかは試していない | 記録だけ | Claude Code の sandbox（同じ Seatbelt）では止まった。2 つの profile では試していない |

<a name="post-merge"></a>

## マージ後の確認（plan の手順 7・8）

2026-11-27 に、PR #156 のマージ後の main（`~/dotfiles`）で確かめた。

<a name="post-merge-cc-crit"></a>

### 手順 7: cc-crit の入れ直し

- plan の `pgrep -x crit` は、cc-crit 以外の crit（Crit プラグインやターミナルの crit）も数えるので、10 件出た。cc-crit の crit はポート 47810〜47829 で待ち受けるので、人間が `lsof -nP -iTCP:47810-47829 -sTCP:LISTEN` で確かめ、何も出なかった。`claude/README.md` の更新の手順を、この確かめ方に直した。
- 人間が、profile、ラッパーの順に入れ直した。`cmp` では、2 つともリポジトリのものと同じだった。
- 入れた profile でのテスト（`CC_CRIT_PROFILE=/usr/local/libexec/claude-crit/cc-crit.sb CC_CRIT_PROFILE_REQUIRED=1`）: 30 件で OK（スキップ 1）。スキップは、ファイルがあるときだけ動くテストのどれか。`CC_CRIT_PROFILE_REQUIRED=1` では、profile を適用できないときは、スキップではなく失敗になる。
- `claude/README.md` のインストールの手順の `mise run crit:profile-test` は、リポジトリの profile を試す。その前に `cmp` で確かめる手順を足した。

<a name="post-merge-vault"></a>

### 手順 8: Vault で起動したセッション

人間が通常のターミナルで、試験用の Vault（`~/Obsidian/kad19-scratch`）を作った。中身は次のとおりで、git で 1 回コミットした。そこで起動したセッションで確かめた。

- `.obsidian/plugins/probe/data.json` と `.obsidian/app.json`: 偽の値
- `.gitignore`: `.obsidian/`

| # | 操作 | 結果 |
| --- | --- | --- |
| 1 | Bash: `touch .obsidian/.kad19-probe` | 拒否された（権限の設定。実行の前に止まった） |
| 2 | Bash: `touch .gitignore` | `Operation not permitted`（sandbox） |
| 3 | Bash: `: < .obsidian/plugins/probe/data.json` | `operation not permitted`（sandbox） |
| 4 | Bash: `: < .obsidian/app.json` | 通った |
| 5 | Read ツール: `.obsidian/plugins/probe/data.json` | 拒否された |
| 6 | Read ツール: `.obsidian/app.json` | 通った |
| 7 | Write ツール: `.obsidian/kad19-probe.md` | 拒否された |
| 8 | Edit ツール: `.gitignore` に 1 行足す | 承認画面が出た（人間が拒否し、書き込まれていない） |
| 9 | Write・Edit ツールと Bash の `rm` で、ノートを作り、直し、消す | どれも通った |
| 10 | Bash: `git status --short` | 通った（変更なし） |
| 11・12 | Grep・Glob ツール | 実行できなかった。セッションにツールがなかった（ToolSearch でも見つからない）。dotfiles のセッション（Claude Code 2.1.332）にもない |
| 13 | Bash: `grep -rl kad19-dummy .` | `note.md` だけが出て、終了コードは 0。エラーは出なかった |

1 は、sandbox まで届かなかった。denyWrite が allowWrite の中でも効くことは、dotfiles のセッションで確かめた。`$TMPDIR`（allowWrite に入る）の下に `.obsidian` を作ると、`Operation not permitted` になった。マージ前の実測と同じ結果。

13 は、plan の「[影響](plan.md#impact-vault-session)」の見込み（`Operation not permitted` が出て、終了コードが 0 でなくなる）と違った。

- Bash ツールの `grep` は、Claude Code が定義するシェル関数で、同梱の ugrep を `--ignore-files --hidden` で動かす。
- Vault の `.gitignore` が `.obsidian/` を外しているので、`.obsidian` ごと見ない。`.obsidian/app.json` も出なかった。
- この動きは、`$TMPDIR` に `.gitignore` のある場所とない場所を作って確かめた。
- `/usr/bin/grep -rl` で試験用の Vault を調べると、見込みのとおりだった。`.obsidian/plugins` で `Operation not permitted` が出て、ほかの結果（`note.md`・`.obsidian/app.json`）は出て、終了コードは 2 だった。
- `find .` は試していない。

dotfiles のセッション（本番のユーザー設定）でも、次を確かめた。

- Read ツールで、実在の Vault の `.obsidian/plugins/` の下の、存在しないパスを読む: 拒否された。
- Write ツールで、scratchpad の `.obsidian/` の下に書く: 拒否された。
- Bash で、実在の Vault の `data.json` を `: <` で開く: 実行の前に拒否された。権限の設定と auto mode の判定のどちらで止まったかは分からない。
- sandbox の denyRead は、マージ前に同じファイルで確かめた。このセッションの sandbox の denyRead に `/**/.obsidian/plugins` があることは、セッションに渡された設定で確かめた。

実在の Vault（`main`）での `git status` と検索は、試していない。同じ構成の試験用の Vault で確かめたので、完了の条件にしない。ふだんの作業で異常が出たら、Linear に起票する。
