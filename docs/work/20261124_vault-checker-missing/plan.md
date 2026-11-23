---
status: done
created: 2026-11-24
---

# Vault の点検スクリプトがないときに知らせる 実装計画

関連: 前の作業 [20261124_check-vault-note-hook](../20261124_check-vault-note-hook/plan.md)（PR #102）、Vault のセッションが書いた依頼書（2026-11-24、ユーザーが実装を依頼）

<a name="goal"></a>

## 目的

`claude/hooks/check-vault-note.sh` は、Vault（`~/Obsidian/main`）に点検スクリプト `_System/Scripts/check_note.py` がないとき、何も出さずに exit 0 で終わる（前の作業の D2）。これを、Vault に限って、exit 2 で Claude に知らせる振る舞いに変える。

<a name="reason"></a>

## D2 を変える理由

依頼書より。

- 2026-11-24 01:27〜01:29 に、Vault の点検スクリプトが消えていた（原因は不明）。今の仕様では、そのあいだの Edit・Write は知らされずに点検されない。消えたことには、たまたま `ls` で気づいた。
- Vault の `_System/` は、Remotely Save の `syncUnderscoreItems` がオンの端末にだけ届く。オフの端末では、点検されていないことに気づけない。
- フックが点検するのは `~/Obsidian/main` だけなので、Vault に限れば、ほかのプロジェクトで知らせが出続けることはない。

Vault 以外のプロジェクトは今と同じにする（Python を起動せず、何も出さずに exit 0）。Command Line Tools がない Mac で、すべてのプロジェクトの編集のたびに知らせが出ないようにするため。

<a name="design"></a>

## 設計

<a name="design-sh"></a>

### `check-vault-note.sh`

今の `[ -f "$project/_System/Scripts/check_note.py" ] || skip` を、次に変える。

```bash
checker="$project/_System/Scripts/check_note.py"
if [ ! -f "$checker" ]; then
  # Vault（$HOME/Obsidian/main）でなければ、Python を起動しない。Vault なら、点検スクリプトがないことを Python の段で知らせる。
  real_project=$(cd -P -- "$project" 2>/dev/null && pwd) || skip
  real_vault=$(cd -P -- "${HOME:-/nonexistent}/Obsidian/main" 2>/dev/null && pwd) || skip
  [ "$real_project" = "$real_vault" ] || skip
fi
```

- Vault かどうかの判定は、Python の外の段（正式な判定）と、ここ（Python を起動するかどうかだけの判定）の 2 か所になる。ここで外しても、Python の段が改めて判定するので、点検の範囲は広がらない。
- `cd -P` と `pwd` は bash の組み込みで、PATH のコマンドを使わない。
- その後の Command Line Tools の確認は今のまま。Vault で点検スクリプトがなく、Command Line Tools もない端末では、Command Line Tools がないことを先に知らせる。

<a name="design-py"></a>

### `check-vault-note.py`（sandbox の外の段）

Vault の固定の判定の後、symlink の判定の前に、次を足す。

1. Vault の点検スクリプトが通常のファイルでない（`os.path.isfile` が偽。ない・ディレクトリ・FIFO など）→ 次を stderr に書いて exit 2。
   「Vault の点検スクリプト（_System/Scripts/check_note.py）がないか、通常のファイルでないため点検しない。ユーザーに、点検スクリプトが消えていないかと、Remotely Save の syncUnderscoreItems がオンかを確かめるよう頼む。」
2. 点検スクリプトを開くとき、`FileNotFoundError`（1 の判定の後に消えた場合）も、1 と同じ文で exit 2 にする。それ以外の `OSError` は今のまま（写しと違う扱い）。

通常のファイルかを先に確かめるのは、Vault では bash の `-f` の判定を通らずに Python まで進むので、FIFO の点検スクリプトを開いて 25 秒止まらないようにするため。入力は、判定の前に最後まで読んでいる（今のまま）。

<a name="design-tests"></a>

### 試験（`claude/hooks/tests/test-check-vault-note.sh`、Seatbelt に入る前に終わるので、どこでも動く）

- Vault に点検スクリプトがない → exit 2、「ない」の文、点検スクリプトを実行しない。
- Vault の点検スクリプトの場所がディレクトリ → exit 2、同じ文。
- Vault に点検スクリプトがなく、Command Line Tools もない（`DEVELOPER_DIR` を空のフォルダにする）→ exit 2、`xcode-select --install` を含む文。
- Vault 以外のプロジェクトで点検スクリプトがない → 今と同じく何も出さない（既存の 2 件）。
- 大きな入力を読み切る試験に、「Vault に点検スクリプトがない」場合を足す。
- 試験で確かめないもの: 1 の判定の後に消える競合（2 の `FileNotFoundError`）。判定と読み込みのあいだに消す競合でしか届かないため。

<a name="design-docs"></a>

### 文書

- `claude/README.md` の「Vault のノートの点検」に、Vault に点検スクリプトがないときの振る舞いを書く。別の端末の段落の「オフの端末では点検スクリプトが届かず、フックは何もしない」を、「…点検しないことを知らせる」に直す。
- 前の作業文書（`done`）は変えない。D2 を変えた理由は、この計画に記録する。
- Vault の README §6.5 の同じ記述は、Vault のセッションで直す（このセッションでは触らない）。

<a name="steps"></a>

## 手順

| # | 作業 | 確かめ方 |
| --- | --- | --- |
| 1 | 試験を足す | 今のフックで、Vault に点検スクリプトがない場合の試験が失敗する |
| 2 | フックと Python の部分を直す | sandbox の中で試験が通る（Seatbelt の部分はスキップ） |
| 3 | README を直す | `check-repo.py`、`test-check-repo.py`、shellcheck、`actionlint`、既存のフックの試験が通る |
| 4 | ユーザーが通常のターミナルで試験を実行する | `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh` がすべて通る |
| 5 | コミットし、`/crit-review` でブランチの差分を確かめてから push する | PR #102 の CI が通る |
| 6 | Codex のレビューを提案する（このブランチの回数に数える。これまで 2 回） | 指摘への対応を決める |
| 7 | 変えた振る舞いと試験の結果を、Vault のセッションに伝えられる形でまとめる | — |

PR #102 はまだマージされていないので、同じブランチ（`feat/check-vault-note-hook`）に足す。PR #102 の振る舞いの仕様（D2）を変える変更で、分けると、`main` に古い振る舞いが入る時期ができるため。

<a name="residual-risks"></a>

## 残る経路と受け入れるリスク

- Vault の点検スクリプトを消せば、点検は止まる（ただし、今度は知らせが出る）。
- 1 の判定の後に FIFO に差し替える競合では、読み込みで 25 秒止まる（資源を使わせるだけで、中身は出ない）。
- Vault かどうかの判定が 2 か所にある。bash 側の判定を外しても、Python の段が改めて判定するので、点検の範囲は広がらない。

<a name="rollback"></a>

## 戻し方

このコミットを revert すれば、D2（何も出さずに exit 0）に戻る。
