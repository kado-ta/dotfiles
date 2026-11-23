---
status: in-progress
created: 2026-11-24
---

# Vault の点検スクリプトがないときに知らせる 試験記録

関連: [plan.md](plan.md)

<a name="tests"></a>

## 試験の結果

| 実行した場所 | コマンド | 結果 |
| --- | --- | --- |
| Claude Code の sandbox | `bash claude/hooks/tests/test-check-vault-note.sh` | pass=27 fail=0 skip=1（Seatbelt の中の確認はスキップ） |
| ユーザーのターミナル | `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh` | pass=44 fail=0 skip=0 |
| Claude Code の sandbox | 既存のフックの試験 7 本、`check-repo.py`、`test-check-repo.py`、shellcheck、`actionlint` | すべて通過 |

足した試験（どこでも動く）:

- Vault に点検スクリプトがない → exit 2、`syncUnderscoreItems` を含む文
- Vault の点検スクリプトの場所がディレクトリ → exit 2、同じ文
- Vault に点検スクリプトがなく、Command Line Tools もない → exit 2、`xcode-select --install` を含む文
- 大きな入力を、Vault に点検スクリプトがない場合も読み切る

Vault 以外のプロジェクトで点検スクリプトがない場合（Command Line Tools がない場合も）は、既存の試験のとおり何も出さない。

<a name="mutations"></a>

## 壊した写しでの確認

一時フォルダに写して壊したフックで、試験が失敗することを確かめた（写しはコミットしていない）。

| 壊し方 | 失敗した試験 |
| --- | --- |
| bash で、Vault でも点検スクリプトがなければ何もしない（変更前に戻す） | Vault の 3 件 |
| Python で、通常のファイルかを確かめない | ディレクトリの件（「写しと違う」の文になる） |
| bash で、点検スクリプトがなければ常に Python まで進む | Command Line Tools がないとき、Vault 以外のプロジェクトでも知らせが出る |

確かめていないもの: 通常のファイルかを確かめた後に消える競合（`FileNotFoundError` の分岐）。判定と読み込みのあいだに消す競合でしか届かないため。

<a name="codex-review-3"></a>

## Codex のレビュー（このブランチの 3 回目、`090be95`）

ユーザーが通常のターミナルで `codex review --base main` を実行した（2026-11-23T20:05:25Z）。結果は `~/.codex/sessions` の記録の最終メッセージから読んだ。全体の判定は「patch is incorrect」。指摘は 4 件で、3 件は点検スクリプト（Vault の版と写し）の誤報、1 件はフックの出力の形。

| # | 指摘 | 確かめた結果 | 対応 |
| --- | --- | --- | --- |
| 1 | [P2] 入れ子のリストの中で、行頭から 4 文字以上字下げしたフェンスを認識しない。コード例の `[[example]]` を Wikilink と誤報する | 再現した（写しは exit 1）。Vault の新しい版（SHA-256 `24b70d52…`）では exit 0 | 採用。Vault 側で直った版を写しに取り込む |
| 2 | [P2] `[ガイド](guide(v2).md)` のように、リンク先に対応の取れた丸括弧があると、`guide(v2` を探してリンク切れを誤報する | 写しと Vault の新しい版の両方で再現した（`リンク先 guide(v2 がない`） | Vault 側で直す（このブランチでは写しを変えない） |
| 3 | [P3] 出力の `- # …` は、Markdown ではリストの中の見出しになる。Vault 直下の `# Draft.md` のような名前で起きる | コードで確かめた | 不採用（提案）。出力は、描画されない文字列として Claude に届く。`- ` は、引用した行が出力の構造の外に見えないように付けている。見出しの文と合わせて、行が点検の出力の一部だと分かる |
| 4 | [P3] 見出しが `Topic`・`Topic-1`・`Topic` の順だと、3 つ目にも `topic-1` を割り当て、有効な `#topic-2` へのリンクを誤報する | 写しと Vault の新しい版の両方で再現した（`リンク先のアンカー #topic-2 がない`） | Vault 側で直す（このブランチでは写しを変えない） |

再現に使ったノートは、一時ディレクトリに作った（コミットしていない）。点検スクリプトは `/usr/bin/python3 -I -B` で直接実行した。

Codex のレビューは、このタスク（PR #102）で 3 回目（上限は 5 回）。

<a name="copy-update"></a>

## 写しの更新（指摘 1 への対応）

Vault のセッションが `mask_code()` を書き直した版（引用とリスト項目の入れ子の中のフェンス、複数行の HTML コメント）を、写しに取り込んだ。

- 写しと Vault の版の差分は +101・−20 行で、すべて `mask_code()` の書き直しと、そのための定数・関数の追加だった。import・ファイルの読み書き・外部プログラムの起動は変わっていない。dotfiles 側には、合わせる変更はなかった。
- ユーザーが、README の手順（sandbox から書けない一時ディレクトリに写す → `git diff --no-index` で差分を確かめる → 置き換える）で置き換えた。SHA-256 は `24b70d52a65d6661afe62ee282aa0a65fde01493cd8860d1cd1b69aa3451ee0e` で、Vault の版とバイト列が同じ。

| 確かめたこと | 結果 |
| --- | --- |
| Vault の点検スクリプトの試験（一時ディレクトリに写し・`test_check_note.py`・`Tags.md` を並べて `/usr/bin/python3 -I -B` で実行） | 17/17 件が期待どおり |
| 本物の Vault の 80 件のノート（同じバイト列の Vault の版を直接実行） | 誤りになる 4 件が、更新の前と同じ |
| `test-check-vault-note.sh`（sandbox の中） | pass=27 fail=0 skip=1 |
| `check-repo.py` | 通過 |
