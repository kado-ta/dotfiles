---
status: done
created: 2026-11-21
---

# 信頼したフォルダの点検で、次にすることを出力する: 試験記録

## 関連

- [plan](plan.md)

<a name="unit-tests"></a>

## 単体テスト（手順 1・2）

- RED: テストを直した後、直す前のスクリプトで 20 件のうち 6 件が失敗した（failures=2、errors=4）。errors は、表を 4 列として読めないことと、「次の手順:」の行がないことによる。テストの写しを、スクリプトのないディレクトリで実行し、20 件すべてが失敗することも確かめた。
- GREEN: `/usr/bin/python3 -B`（3.9.6）と mise の `python3 -B`（3.15.2）で、20 件が通った。

<a name="mise-task"></a>

## mise タスクの式（手順 3）

mise は `run` の文字列を `sh -c -o errexit` で実行する。同じ形で、`<スクリプト> || [ $? -eq 1 ]` の終了コードを確かめた。

| スクリプトの終了コード | タスクの終了コード |
| --- | --- |
| 0 | 0 |
| 1 | 0 |
| 2 | 1 |

sandbox の中では、`mise.toml` を変えた後の mise は信頼し直すまで動かないので、`mise run` そのものは手順 4 で人間が確かめる。

<a name="repo-checks"></a>

## リポジトリの検査（手順 3）

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了コード 0 |
| `actionlint` | 終了コード 0 |

<a name="real-run"></a>

## 実物での確認（手順 4）

- Claude が Bash（sandbox の中）で、mise タスクと同じ式（`sh -c -o errexit '/usr/bin/python3 -B claude/scripts/trust-audit.py || [ $? -eq 1 ]'`）を実行した。終了コード 0。出力は plan の[出力の形](plan.md#output)と同じだった。19 件のうち、フォルダがない 2 件が `消す`、ほかの 17 件が `-` で、結果・残しておくと・次の手順・コマンド・jq の注意が出た。
- 人間が通常のターミナルで `mise trust` してから `mise run claude:trust-audit` を実行し、最後に `ERROR task failed` が出なくなったことを確かめた（2026-11-21、PR #56 のマージ後）。

<a name="deviations"></a>

## plan との違い

1. 「残しておくと:」は、候補の種類ごとに 1 行にし、主語（「フォルダがない項目は、」「リポジトリの外の項目は、」）を付けた。2 種類が並んだときに、どちらの影響か分かるようにするため。
2. 「急ぎではない。」は、フォルダがない項目の行にだけ付けた。リポジトリの外で信頼している項目は、その下のフォルダにも信頼が及んでいるので、急ぎではないとは言えないため。
