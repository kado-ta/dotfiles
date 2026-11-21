---
status: in-progress
created: 2026-11-21
---

# 信頼したフォルダの点検タスクの試験記録

## 関連

- [plan](plan.md)

<a name="unit-tests"></a>

## 単体テスト（手順 1・2）

- RED（最初の版）: スクリプトを置く前に `/usr/bin/python3 -B claude/scripts/test-trust-audit.py` を実行し、14 件のうち 13 件が失敗した（failures=13 は subTest を含む数、errors=2）。`test_does_not_print_other_values` は、出力が空でも目印が出ないので通っていた。これは `/review` で分かり、下の[レビュー](#review)で直した。
  - 最初の版では、終了コード 2 のテスト 4 件と、書き込みのテストも、スクリプトなしで通った。python3 はスクリプトを開けないときも終了コード 2 で終わるため。stderr にスクリプトのメッセージ（「点検できない」）があることと、書き込みのテストで終了コードが 1 であることを確かめるよう直してから、上の RED を確かめた。
- GREEN（最初の版）: `/usr/bin/python3 -B`（3.9.6）と mise の `python3 -B`（3.15.2）で、14 件が通った。

<a name="jq-check"></a>

## jq のフィルタの確認

plan の jq のフィルタを、一時ファイルに対して、ファイルの後に `--args '/a/drop me' '/a/drop$(touch P)'` を付けて実行した。渡した 2 つのキーだけが消え、ほかのキーと値は残った。`P` は作られなかった（jq 1.8.2）。生成したコマンドの引用は、テストの `shlex.split` の往復で確かめている。生成したコマンドそのものを bash で実行する確認は、権限の確認で拒否されたので行っていない。レビューの後は、フィルタの動作をテスト（`test_suggested_jq_removes_only_the_listed_entries`）でも確かめている。

<a name="repo-checks"></a>

## リポジトリの検査（手順 3）

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 83 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了コード 0 |
| `actionlint` | 終了コード 0 |

<a name="real-run"></a>

## 実物での確認（手順 4）

- Claude が Bash（sandbox の中）で `/usr/bin/python3 -B claude/scripts/trust-audit.py` を実行した。終了コード 1。18 件が `missing` 2・`home` 1・`not-repo` 1（信頼 `false`）・`repo` 14 に分かれ、plan の[出力の例](plan.md#output)と一致した。
- レビューの後の版でも、同じ 18 件の区分と終了コード 1 を確かめた。出力するコマンドは、バックアップの `cp` と、`missing` の 2 件を消す jq の 1 行になった（[plan との違い](#deviations)の 6）。
- 人間が通常のターミナルで `mise trust` してから `mise run claude:trust-audit` を実行する確認: 未実施。

<a name="sources"></a>

## 出典の確認（README の仕様）

サブエージェントが公式ドキュメント（permissions・security・claude-directory・cli-reference）を取得して確かめた。

- plan の要点のうち、記録先・キーの単位・下のフォルダへの効果・ホームの扱い・`claude purge` の動作は、記述があった。
- 信頼を一覧・取り消す公式のコマンドは、読んだ範囲では見つからなかった（settings-reference と errors のページは一部しか読んでいない）。
- plan になかったことで README に足したこと: worktree ではキーが main checkout のルートになる。親の信頼では、下のフォルダの `permissions.allow` と `additionalDirectories` は使われない。`claude purge` はパスを 1 つだけ取り、`~/.claude/backups/` の写しは消さない。フォルダがないパスに使えることは、ドキュメントには書かれていない。

<a name="review"></a>

## レビュー（手順 5 の `/review`）

gstack の `/review` を 1 回実行した。専門のレビュー 5 つ（testing・maintainability・security・performance・simplification）、red team、Claude の敵対的レビュー、探索的な確認（実物での実行と、手順 1〜3 の検査の再実行）を行った。Codex は、Bash から実行しない規則なので実行していない。

自動で直したこと:

- テストの使っていない `import re` を消した。
- `ORDER` のコメントとテスト名が、実際の表示の順と合っていなかったので直した。

ユーザーが決めたこと（2026-11-21、すべて推奨のとおり）:

| # | 指摘 | 決定 |
| --- | --- | --- |
| D1 | `missing` に purge を出すと、外したボリューム・点検の後に戻ったフォルダ・改名したフォルダ（記録のディレクトリ名が改名後と同じになる）でも、元に戻せない削除を勧める | purge は出さず、`missing` も jq で項目を消す候補にする。purge は README で手作業の手順として案内する |
| D2 | 制御文字を含むキーで表示を偽装できる。相対パスのキーや `CLAUDE_CONFIG_DIR` で別の対象を点検する。一時ファイルが 0644。同じ日のバックアップが上書きされる。止めるべきプロセスが README にない | 制御文字・絶対パスでないキー・`CLAUDE_CONFIG_DIR` は終了コード 2。一時ファイルは `umask 077` のサブシェルで作る。バックアップ名に時刻を付ける。README に `--bg`・デーモン・IDE・デスクトップアプリを書く |
| D3 | jq は項目ごと消すので、local の MCP サーバーの設定なども消える | 項目ごと消す方式のまま、出力の見出しと README に明記する |
| D4 | 秘密を出さないテストがスクリプトなしで通る。バックアップが先に出る順序と、jq のフィルタの動作をテストしていない | 3 件ともテストを直す・足す。この記録の RED の記述も直した |
| D5 | plan の出力の例に、業務のフォルダ名が載っている（公開リポジトリ） | 3 件を仮の名前（`~/Dev/example/...`）に置き換える。名前を含むコミットは push 前に作り直す |

直した後の RED と GREEN:

- 新しいテストは、直す前のスクリプトで 12 件（subTest を含む）が失敗した。
- テストの写しを、スクリプトのないディレクトリで実行し、17 件すべてが失敗することを確かめた（最初は、足した `test_does_not_suggest_purge` がスクリプトなしで通ったので、終了コード 1 と jq の行があることも確かめるよう直した）。
- 直した後、`/usr/bin/python3 -B` と mise の `python3 -B` で 17 件が通った（jq のテストもスキップされずに実行）。

採らなかった指摘（理由）:

- ホームの項目の信頼が `true` のときも候補にする: ドキュメントはホームの信頼を保存しないと明記しており、今の項目は `false`。古い項目が読まれるかは未確認なので、見えたら判断する。
- 中身のない `.git` があるフォルダを `repo` とみなす: git の判定とずれるが、起きる入力が見当たらない。
- bool でない `hasTrustDialogAccepted`、`| head` での `BrokenPipeError`: Claude Code は bool を書き、出力をパイプしない。
- mise タスクに `-I` を付ける: 隣のタスクと同じ形で、`claude/` は sandbox から書けない。
- 起動中の Claude Code を `pgrep` で確かめる行を足す: README と出力の見出しで止めるプロセスを示すことにした。

<a name="deviations"></a>

## plan との違い

1. フォルダを調べる権限がないとき（`stat` がフォルダがない以外の理由で失敗したとき）は、終了コード 2 で止める。plan の区分にはない。`missing` とみなすと、使っているフォルダの項目を消す候補にするため（テスト `test_exits_2_when_a_folder_cannot_be_checked`）。
2. 表示の順は `missing` → `home` → `not-repo` → `repo`（出力の例に合わせた）。判定の順とは別。
3. `shlex.quote` は、引用の要らないパスには引用符を付けない。出力の例の `'<パス>'` と違い、今の 2 件は引用符なしで出る。
4. キーに制御文字があるか絶対パスでないとき、`CLAUDE_CONFIG_DIR` が設定されているときも、終了コード 2 で止める（レビューの D2）。
5. バックアップ名に時刻を付け（`bak-YYYYMMDD-HHMMSS`）、jq の一時ファイルは `umask 077` のサブシェルで作る（レビューの D2）。
6. `claude purge` は出さない。`missing` の項目も、`not-repo` で信頼が `true` の項目と同じ jq の 1 行で消す（レビューの D1）。plan の出力の例の「1.」「2.」の 2 つの見出しは、1 つになった。
7. plan の出力の例のフォルダ名を仮の名前に置き換えた（レビューの D5）。Crit で承認した後の、本文の唯一の変更。
