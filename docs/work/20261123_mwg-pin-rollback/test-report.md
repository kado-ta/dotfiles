---
status: done
created: 2026-11-23
---

# modern-web-guidance の取り込みの中断で mise の版も戻す修正の試験記録

<a name="related"></a>

## 関連

- 前の作業: [modern-web-guidance の導入と更新の自動化](../20261123_modern-web-guidance/test-report.md)（PR #77）
- 直した指摘: PR #77 のマージの後に、コミット `f279046` だけを対象にした Codex のレビュー

<a name="codex-review"></a>

## Codex のレビュー（このタスクの 3 回目）

ユーザーが通常のターミナルで `codex review --commit f279046 -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を実行した（main、`0547d97`）。結果は、規則のコマンドで `last_agent_message` から読んだ。

| 優先度 | 指摘 | 採否 |
| --- | --- | --- |
| P2 | `write_pin()` の `os.replace` が成功した直後、`then()` から戻る前に Ctrl-C が入ると、スキルだけが旧版に戻り、mise の版は新版のまま残る。もう一度 `--apply` しても「最新」で終わるので、スキルは直らない。`f279046` で戻しの範囲を広げたことで入った | 採用（ユーザーの承認のもとで直した） |

Codex は、メモリ上の再現（置き換えの直後に `KeyboardInterrupt`）で確かめていた。総評は「patch is incorrect」、確信度は 0.96。Codex は、このタスクで 3 回使った（上限は 5 回）。

<a name="fix"></a>

## 直したこと

- `apply_skills_and_pin()` を足した。書く前に mise の設定の中身を控え、戻すときに中身が変わっていれば元の中身を書き戻す（`undo`）。
- `write_skills()` に `undo` を足した。入れ替えか `then` が失敗したら（Ctrl-C を含む）、スキルを戻す前に呼ぶ。`then` が済んだかどうかは見ず、ディスクの中身で判断する。
- `undo` 自体が失敗したときは、スキルも戻さずに旧版の写しを残し、`main()` が git で両方を戻すコマンドを表示する（前からの動き）。

<a name="results"></a>

## 自動の試験と検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B claude/scripts/test-update-modern-web-guidance.py`（mise と `/usr/bin/python3`） | OK（67 件。足した 2 件を含む） |
| 足したテストを、直す前のコードで実行 | 失敗（版が `1.0.2` のまま残った。指摘を再現した） |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | OK |
| `/usr/bin/python3 -B claude/scripts/test-update-skills.py` | OK |
| `shellcheck -S warning`、`actionlint` | 指摘なし |
| `gstack-checks quick`（`/verify`） | `VERIFY skipped: the repo declares no checks or tests` |

<a name="mutation"></a>

## 変異テスト

写しで `write_skills()` の `undo()` の呼び出しを外すと、足したテストが失敗した（`FAILED (failures=1)`）。

<a name="unverified"></a>

## 確かめていないこと

- 本物の npm のパッケージでの `--out` の作り直しはしていない。検証と組み立ての処理は変えていないため。
- 新しい版があるときの `--apply` の流れは、前の作業と同じく、テストの偽物でだけ確かめた（npm に新しい版がない）。
