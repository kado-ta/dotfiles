---
status: done
created: 2026-11-21
---

# 信頼したフォルダの点検で、次にすることを出力する

## 関連

- 前の作業: [信頼したフォルダの点検タスク](../20261121_claude-trust-audit/plan.md)（PR #53、完了の記録は PR #54）
- 仕様: [claude/README.md の「信頼したフォルダの点検」](../../../claude/README.md#trust-audit)

<a name="goal"></a>

## 目的

`mise run claude:trust-audit` の出力を見ても、次に何をすればよいか分からなかった（2026-11-21、ユーザーが実物で実行して指摘）。原因は 3 つある（事実）。

1. 表のどの行が消す候補なのか、表だけでは分からない。
2. 結果の要約（候補が何件あり、残すと何が起きるか）がない。
3. 候補があると終了コード 1 になり、mise が最後に `ERROR task failed` と表示するので、失敗したように見える。

出力に、候補の印・結果の要約・番号付きの手順を足す。mise は候補があっても失敗と表示しないようにする。

<a name="done-criteria"></a>

## 完了条件

1. 表に「対応」列がある。候補の行は `消す`、ほかは `-`。
2. 候補があるときは、表の後に次を出す。
   - 結果: 候補の件数と内訳（フォルダがない / リポジトリの外で信頼している）と、対応不要の件数。
   - 残しておくと: 候補の種類ごとの影響。
   - 次の手順: 番号付きの 3 つ（閉じる・実行する・点検し直す）。
   - コマンド（今と同じ `cp` と jq）と、jq が項目ごと消すことの注意。
3. 候補がないときは、表の後に「結果: 消す候補はない。やることはない。」だけを出す。
4. スクリプトの終了コード（0: 候補なし、1: 候補あり、2: 点検できない）は変えない。mise タスクは、1 を成功として扱い、2 のときだけ失敗にする。
5. `test-trust-audit.py` が `/usr/bin/python3` と mise の `python3` で通る。`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint が通る。
6. 実物で、出力が下の形になる。人間が `mise trust` した後に `mise run claude:trust-audit` を実行し、`ERROR task failed` が出ない。

<a name="output"></a>

## 出力の形（2026-11-21 の状態で期待する結果）

ユーザーが選んだ形（2026-11-21）。

```text
区分      信頼   対応  パス
missing   true   消す  ~/Dev/example/gone-a
missing   true   消す  ~/Dev/example/gone-b
home      false  -     ~
not-repo  false  -     ~/claude-work/dotfiles-probe
repo      true   -     ~/Dev/example/repo-a
（repo の残り 14 件）

結果: 消す候補が 2 件ある（フォルダがない 2 件）。ほかの 17 件は対応不要。
残しておくと: 同じパスにフォルダを作り直したとき、確認なしで信頼される。急ぎではない。

次の手順:
1. Claude Code をすべて閉じる（claude --bg のセッションとデーモン、IDE、デスクトップアプリも）。
2. 通常のターミナルで、下のコマンドを上から順に実行する。
3. もう一度 mise run claude:trust-audit を実行し、「消す候補はない」と出ることを確かめる。

cp -p ~/.claude.json ~/.claude.json.bak-20261121-164429
(umask 077; jq '...' ~/.claude.json --args ... \
  > ~/.claude.json.new) && cat ~/.claude.json.new > ~/.claude.json && rm ~/.claude.json.new

jq は項目ごと消す。会話の記録は残る。項目にある local の MCP サーバーの設定なども消えるので、戻すときは上のバックアップから。
```

- リポジトリの外で信頼している項目が候補にあるときは、「残しておくと:」に「その下の、リポジトリでないフォルダも信頼されたままになる。」を足す。内訳も「リポジトリの外で信頼している n 件」を足す。
- 件数が 0 の内訳は出さない。

<a name="decisions"></a>

## 判断したこと

1. **終了コードは変えず、mise タスクで 1 を成功として扱う**（ユーザーが選んだ、2026-11-21）。`run` を `/usr/bin/python3 -B claude/scripts/trust-audit.py || [ $? -eq 1 ]` にする。スクリプトを直接実行したときの 0/1/2 と、そのテストは保つ。
   - 採らなかった案: スクリプトの終了コードを、候補があっても 0 にする。「候補があるか」を終了コードで見分けられなくなり、完了条件とテストも変わる。
   - 代わりに失うもの: `mise run` の終了コードでは、候補の有無が分からなくなる。`claude:skills-check` は、違いがあると `ERROR` のままなので、タスクごとに扱いが違う。
2. **表は全件を残す。** 一覧を見て、使っていないリポジトリを人間が決める前提（前の作業の plan）を保つ。

<a name="files"></a>

## 変更するファイル

| ファイル | 変更 |
| --- | --- |
| `claude/scripts/trust-audit.py` | 「対応」列、結果・残しておくと・次の手順を出す |
| `claude/scripts/test-trust-audit.py` | 上の出力のテスト。表を読む部分を 4 列にする |
| `mise.toml` | `claude:trust-audit` の `run` と、その説明 |
| `claude/README.md` | 出力の説明と、mise タスクの終了の扱い |
| `docs/work/20261121_trust-audit-next-action/` | この plan と test-report |

<a name="impact"></a>

## 影響

- スクリプトの終了コードと、出力するコマンドは変わらない。表の列と、表の後の文が増える。
- `mise.toml` を変えるので、人間が `mise.toml` の全体を確かめて `mise trust` し直すまで、ルートの mise タスクは読み込まれない。

<a name="steps"></a>

## 手順

1. テストを書く → 今のスクリプトで失敗し、スクリプトのない場所で全件失敗することを確かめる。
2. スクリプトを直す → テストが `/usr/bin/python3 -B` と mise の `python3 -B` で通る。
3. `mise.toml` と README を直す → `check-repo.py`・`test-check-repo.py`・shellcheck・actionlint が通る。`run` の式は、`sh -c` で終了コード 0・1・2 のときの結果を確かめる（sandbox の中では、信頼し直す前の mise は動かない）。
4. 実物で確かめる → Claude が `/usr/bin/python3 -B claude/scripts/trust-audit.py` を実行し、上の出力の形と比べる。人間が通常のターミナルで `mise trust` してから `mise run claude:trust-audit` を実行し、`ERROR` が出ないことを確かめる。
5. `/crit-review` でブランチの差分を確かめてもらう → push と PR。軽微な変更なので、`/review` は使わない。

<a name="out-of-scope"></a>

## 範囲外

- `claude:skills-check` など、ほかのタスクの終了の扱い
- 出力するコマンドの中身（前の作業のレビューで決めたまま）
