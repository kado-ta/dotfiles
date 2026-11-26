---
status: in-progress
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

形を変えても、worktree の `settings.local.json` の規則はどれも効かなかった。ユーザー設定の `~/**/` の形は効いた。本番ではユーザー設定に置くので、ツールの規則はマージ後に確かめる（plan の手順 8）。

<a name="pending"></a>

## 未実施

- worktree の `.claude/settings.local.json` を元に戻す（plan の手順 4-4）。置いてあるあいだは、今入っている cc-crit が `/crit-review` を DENIED で止める。戻したら、試験用の Vault（`tmp/kad19`）を消す。
- マージ後の手順 7（cc-crit の入れ直しと `mise run crit:profile-test`）と手順 8（Vault で起動したセッションでの確認）。
