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

- `apply_skills_and_pin()` を足した。書く前に mise の設定の中身を控え、戻すときに、今の中身がここで書いた版と同じなら元の中身を書き戻す（`undo`）。版を書く前に止まったときは、設定に触れない。
- `write_skills()` に `undo` を足した。入れ替えか `then` が失敗したら（Ctrl-C を含む）、スキルを戻す前に呼ぶ。`then` が済んだかどうかは見ず、ディスクの中身で判断する。
- `undo` 自体が失敗したときは、スキルも戻さずに旧版の写しを残す。版もスキルも新しいまま残るので、組み合わせは崩れない。版より先にスキルを戻すと、版が新しくスキルが古い組み合わせになるので、この順にしている。
- `main()` は、書き込み中の Ctrl-C も受け止め、git で両方を戻すコマンドを表示して、終了コード 130 で終える（前は OSError と `Failure` のときだけ表示し、Ctrl-C では traceback で終わっていた）。表示に「戻せなかったときは、旧版の写しを手で戻さず、git で版と一緒に戻す」を足した。

<a name="results"></a>

## 自動の試験と検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B claude/scripts/test-update-modern-web-guidance.py`（mise と `/usr/bin/python3`） | OK（70 件。足した 5 件を含む） |
| Codex の指摘のテストを、直す前のコードで実行 | 失敗（版が `1.0.2` のまま残った。指摘を再現した） |
| `/review` の指摘のテスト 2 件を、直す前のコードで実行 | 失敗（ほかから足した `node = "24"` が戻しで消えた。Ctrl-C を `main()` が受け止めなかった） |
| `undo` の書き戻しの失敗のテストを、直す前のコードで実行 | 成功（順を守るためのテストで、直す前の順も正しかった） |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | OK |
| `/usr/bin/python3 -B claude/scripts/test-update-skills.py` | OK |
| `shellcheck -S warning`、`actionlint` | 指摘なし |
| `gstack-checks quick`（`/verify`） | `VERIFY skipped: the repo declares no checks or tests` |

<a name="mutation"></a>

## 変異テスト

写しで次の変異を 1 つずつ入れると、どれも足したテストが失敗した。

| 変異 | 失敗したテスト |
| --- | --- |
| `write_skills()` の `undo()` の呼び出しを外す | `test_interrupt_right_after_pin_replaced_restores_both` |
| `undo()` を、スキルを戻した後に呼ぶ | `test_failed_pin_restore_leaves_skills_new` |
| `undo()` の失敗を握りつぶす | `test_failed_pin_restore_leaves_skills_new` |
| `undo` の条件を「書く前の中身と違えば戻す」に戻す | `test_failure_before_pin_is_written_leaves_config_alone` |
| `main()` で Ctrl-C を受け止めない | `test_interrupt_in_main_prints_restore` |

後の 2 つ（順と握りつぶし）は、`/review` の Testing の観点が、直す前のテストの全体を通ることを確かめていた。

<a name="review"></a>

## `/review`

コミット `8c1df90` を対象に、Testing・Maintainability・Security・Performance・Simplification の 5 つの観点と、攻撃者視点のレビュー（adversarial）で行った。Performance・Security・Simplification は指摘なし。Codex の外部のレビューは、規則でユーザーが通常のターミナルで実行するので、ここでは実行していない。

| # | 指摘 | 出どころ | 採否 |
| --- | --- | --- | --- |
| D1 | `undo` が、版を書く前の失敗でも、そのあいだにほかから書かれた mise の設定を書き戻して消す（この差分で入った後退） | adversarial（再現あり） | 直した（ユーザーの承認） |
| D2 | `undo` 自体が失敗したときの表示が版に触れず、Ctrl-C では git の戻し方も出ない。案内に従って旧版のスキルだけを手で戻すと、直した組み合わせを作る。順を守るテストがない。この試験記録の「`main()` が表示する」も誤り | Maintainability・Testing・adversarial | 直した（ユーザーの承認） |
| - | `bumped_pin()` と `old_pin` が設定を別々に読む | adversarial | 直さない。2 つの読み込みのあいだに書き込みはなく、成功したときにほかの変更を消すのは前からの動き |
| - | 控えと書き戻しがテキストの扱いで、CRLF の設定は LF で戻る | adversarial | 直さない。今の設定は LF で、`.gitattributes` もない。`write_pin` の前からの動き |
| - | SIGHUP・SIGTERM・電源断では戻さない。`os.replace` の前に fsync しない | adversarial | 直さない（前からの動き）。版を最後に書くので、残る状態は再実行で直る |
| - | 成功した後の一時ディレクトリの削除中の Ctrl-C で、成功の表示が出ずに終わる | adversarial | 直さない（前からの動き）。両方新しく、組み合わせは崩れない |
| - | 戻せた後にも、git の戻し方（`restore`・`clean -fdx`）を表示する | adversarial | 直さない（前からの動き）。作業ブランチで実行する前提で、戻せた後は効果がない |
| - | `test_success_writes_both` が `--apply` のテストと重なる | Testing（確信度 4） | 残す。新しいテストの仕組みの対照として |

<a name="qa"></a>

## 動作の確認（smoke probe）

QA の証跡を記録するツール（`gstack-qa-evidence`）は、権限で実行を拒否されたので使っていない。リポジトリのテストのコマンドと、一時ディレクトリだけを使う確認で、次を確かめた。

| 確認 | 結果 |
| --- | --- |
| 偽物の npm で `--apply` を通しで動かす（版の更新・一時ディレクトリが残らない・最新なら何もしない） | 合格 |
| 版の置き換えの直後の中断と、ほかの戻しの経路のテスト | 合格 |
| 版の置き換えの直後の中断に続いて、版の書き戻しも失敗する（テストがなかった経路） | 版もスキルも新しいまま残り、旧版の写しの場所を表示した。この結果からテストを足した |

<a name="unverified"></a>

## 確かめていないこと

- 本物の npm のパッケージでの `--out` の作り直しはしていない。検証と組み立ての処理は変えていないため。
- 新しい版があるときの `--apply` の流れは、前の作業と同じく、テストの偽物でだけ確かめた（npm に新しい版がない）。
