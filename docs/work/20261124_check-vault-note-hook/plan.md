---
status: in-progress
created: 2026-11-24
---

# Vault のノートを点検するフック 実装計画

関連: 依頼書（2026-11-24 にチャットで受けた「Obsidian Vault のノートを点検するユーザーレベルのフックを追加する」）、Vault（`~/Obsidian/main`）の README §6.5 と AGENTS.md

<a name="goal"></a>

## 目的

Claude Code が Obsidian Vault のノートを Edit・Write したとき、Vault の点検スクリプト `_System/Scripts/check_note.py` を自動で実行し、誤りを Claude に知らせる PostToolUse フックを、dotfiles に置く。Vault の `.claude/` は Remotely Save で同期されないので、ほかの端末にも届く dotfiles に置く。

点検スクリプトは Vault の中（sandbox から書ける場所）にあり、フックは sandbox の外で動く。書き換えられたスクリプトを動かすと sandbox を迂回できるので、dotfiles に記録した承認済みの SHA-256 と一致するときだけ実行する。

<a name="decisions"></a>

## 決めたこと

2026-11-24 にユーザーが選んだ。

1. **照合と実行は、一度読んだ同じバイト列で行う。** 依頼の方式（`shasum` で照合した後、`python3 "$checker"` でファイルを読み直して実行）では、照合と実行のあいだにファイルを差し替えられる。sandbox の中のバックグラウンドの処理が、`mv` で正しい版と書き換えた版を入れ替え続けると、照合は正しい版を読み、実行は書き換えた版を読む組み合わせが起きる。フックは Edit・Write のたびに動くので、何度でも試せる。そこで、`/usr/bin/python3 -I -B -c` の中で点検スクリプトを一度だけ読み、そのバイト列の SHA-256 を照合し、同じバイト列を `compile` して実行する。
2. **Command Line Tools がない端末では、exit 2 で Claude に知らせる。** 公式ドキュメント（hooks reference）では、exit 0 のフックの stderr は Claude に渡らないので、依頼の案（stderr で知らせて exit 0）では誰にも伝わらない。ハッシュが合わないときと同じく、点検できないことと、ユーザーに頼むことを stderr に書いて exit 2 にする。
3. **`claude/settings.json` への登録は、同じ PR の別のコミットにする。** フック・試験・文書をコミットした後、ユーザーが作業ツリーの `claude/settings.json` に登録を足し、Claude がそれをコミットする。

<a name="diff-from-request"></a>

## 依頼との違い

- 上の 1 により、JSON の解析と SHA-256 の計算も Python の標準ライブラリで行う。PATH の `jq` と `shasum` を使わない（sandbox の外で、PATH の先のコマンドを動かさないため）。点検スクリプトのハッシュの値は `shasum -a 256` と同じ。
- 上の 2 により、Command Line Tools がないときは exit 0 ではなく exit 2 にする。
- 依頼の「作るもの」に加えて、ルートの `CLAUDE.md` の「規約」にある、フックを変えたときに実行する試験の一覧に、新しい試験を足す。リポジトリの規約がフックの試験をすべて並べているため。

<a name="design"></a>

## 設計

<a name="design-hook"></a>

### フック `claude/hooks/check-vault-note.sh`

macOS の `/bin/bash` 3.2 で動かす。`set -u`。上から順に判定する。

| # | 条件 | 動作 |
| --- | --- | --- |
| 1 | `CLAUDE_PROJECT_DIR` が空 | 入力を読み切り、何も出さずに exit 0 |
| 2 | `${CLAUDE_PROJECT_DIR%/}/_System/Scripts/check_note.py` が通常のファイルでない | 同上。Vault 以外のプロジェクトで Python を起動しないよう、bash で先に判定する |
| 3 | `$(/usr/bin/xcode-select -p)/usr/bin/python3` が実行できない（Command Line Tools がない） | 入力を読み切り、「点検できない。ユーザーに `xcode-select --install` を頼む」を stderr に書いて exit 2。`/usr/bin/python3` を呼ぶと導入を促すダイアログが出るので、呼ぶ前に判定する |
| 4 | それ以外 | `/usr/bin/python3 -I -B -c "$py" "$project" "$checker" "$hash_file" 1>&2 \|\| exit 2` |

3 の判定は、JSON を解析する前に行う。そのため、Command Line Tools がない端末では、Vault で起動したセッションの Edit・Write のたびに（`.md` 以外でも）知らせる。

`$hash_file` は、フックと同じフォルダ（`$(dirname -- "$0")`）の `check-vault-note.sha256`。本番では `~/.claude/hooks/`（dotfiles の `claude/hooks/` へのリンク）になる。

Python の部分（`$py`。bash の here document で変数に入れる）は次のとおり。点検スクリプトの stdout は、bash の `1>&2` で stderr に出る。

1. stdin の JSON から `tool_input.file_path` を読む。解析できない・文字列でない → exit 0。
2. パスが `$project/` で始まり `.md` で終わらない → exit 0。`..` などは正規化しない。点検スクリプト自身が `resolve()` して、Vault の外なら点検しない。
3. 点検スクリプトを `rb` で一度だけ読む。読めない → exit 0（ないときと同じ）。
4. ハッシュのファイルを読み、前後の空白を除いて、小文字の 16 進 64 文字でなければ（ない・空・形式が違う）不一致とする。
5. 不一致 → 実行せず、「Vault の点検スクリプトが承認済みの版と違うため実行しない。ユーザーにレビューと dotfiles の check-vault-note.sha256 の更新を頼む」を stderr に書いて exit 2。
6. 一致 → 新しいモジュール `__main__` を作り、`sys.modules["__main__"]` に入れ、`__file__` を点検スクリプトのパスに、`sys.argv` を `[点検スクリプト, ノート]` にして、3 で読んだバイト列を `compile(src, checker, "exec", dont_inherit=True)` して `exec` する。終了コードは点検スクリプトのもの（0・1・2）。例外は traceback を出して 1。bash が 0 以外を exit 2 にする。

`-I` は、Vault のフォルダとカレントディレクトリを `sys.path` に入れず、`PYTHON*` の環境変数を読まない。そのため、点検スクリプトの隣に置かれた偽の `re.py` などを読み込まない。`-B` は `__pycache__` を書かない。点検スクリプトは `Path(__file__).resolve().parents[2]` で Vault のルートを決めるので、`__file__` を本来のパスにすれば動く（2026-11-24 に、本物の点検スクリプトと Vault の 8 件のノートで、直接実行と出力・終了コードが同じことを確かめた）。

点検スクリプトが 0 を返したときの警告は、stderr に出すが Claude には届かない（exit 0 の stderr は Claude に渡らない）。依頼の仕様（0 = 誤りなし）のとおりで、前の Vault のフックとも同じ。

<a name="design-hash"></a>

### ハッシュ `claude/hooks/check-vault-note.sha256`

`367191ef765885ac31d0ebb439a1337398698fe3ba99368328a7ca080ae950c0` の 1 行（2026-11-23 に Crit でレビューし、承認された版）。2026-11-24 に `shasum -a 256` で、Vault の点検スクリプトと一致することを確かめた。

<a name="design-test"></a>

### 試験 `claude/hooks/tests/test-check-vault-note.sh`

`test-guard-additional-dirs.sh` の書き方に合わせる（`$BASH` でフックを起動する、`PASS` / `FAIL` と件数を出す、説明は英語）。フックを一時フォルダに写し、その隣に偽のハッシュを置き、偽の Vault に偽の点検スクリプトを置く。偽の点検スクリプトは、`__file__` から決めた Vault のルートに印のファイルを書き、決めた終了コードで終わる。本番の挙動を変える設定項目は足さない。Command Line Tools がない状態は、`DEVELOPER_DIR` を空のフォルダにして作る（`xcode-select -p` がその値を返すことを確かめた）。

| 区分 | 確かめること |
| --- | --- |
| 何もしない | `.md` 以外、プロジェクトの外、点検スクリプトがない、`CLAUDE_PROJECT_DIR` が空、入力を解析できない → exit 0、出力なし、印なし |
| 照合しない | ハッシュが違う、ハッシュのファイルがない、空 → exit 2、印なし、stderr に決まった文 |
| 照合する | 点検スクリプトが 1 → exit 2、出力が stderr に出て stdout は空。0 → exit 0。印のファイルが Vault のルートにでき、引数がノートのパス |
| 読み込み | 点検スクリプトと同じフォルダと、カレントディレクトリに置いた偽の `re.py` が読み込まれない。`__pycache__` ができない |
| 入れ替え | 正しい版と別の版を `mv` で入れ替え続けるあいだにフックを繰り返し実行し、別の版が一度も動かない。見逃しはありうるが、誤って失敗することはない。依頼の方式の写しでは失敗することを、開発中に確かめる（写しはコミットしない） |
| Command Line Tools | `DEVELOPER_DIR` が空のフォルダ → exit 2、stderr に決まった文、印なし |
| 入力 | 大きな入力を、早く終わる経路と Python の経路の両方で読み切る |

<a name="design-docs"></a>

### 文書

- `claude/README.md`: フックの表に 1 行、試験の一覧に 1 行を足す。ハッシュの更新手順の節を足す（点検スクリプトを変えたら、人間がレビューしてから `shasum -a 256 <点検スクリプト> | cut -d' ' -f1 > claude/hooks/check-vault-note.sha256` を実行してコミットする）。Vault の `.claude/` にフックを置かない理由も 1 行書く。
- `CLAUDE.md`（ルート）: 「規約」の試験の列挙に `bash claude/hooks/tests/test-check-vault-note.sh` を足す。

<a name="design-registration"></a>

### 登録（ユーザーが `claude/settings.json` に足す）

`hooks.PostToolUse` の配列に足す。`timeout` は、既定（600 秒）では長すぎるので 30 秒にする。`onFailure` は付けない（ツールは実行済みで、止める操作がない）。

```json
{
  "matcher": "Edit|Write|MultiEdit",
  "hooks": [
    {
      "type": "command",
      "command": "/bin/bash ~/.claude/hooks/check-vault-note.sh",
      "timeout": 30
    }
  ]
}
```

登録の前に、Vault のプロジェクトのフックが残っていないことをユーザーが確かめる。2026-11-24 の時点で、Vault の `.claude/settings.json` はないが、`.claude/hooks/check-note.sh`（照合なしで PATH の `python3` を使う）が残っている。`.claude/settings.local.json` に登録が残っていないかも確かめる（Claude からは読んでいない）。残っていると、照合なしの実行と二重の実行が起きる。

<a name="steps"></a>

## 手順

| # | 作業 | 確かめ方 |
| --- | --- | --- |
| 1 | 試験を書く | フックがない状態で `bash claude/hooks/tests/test-check-vault-note.sh` が失敗する |
| 2 | フックとハッシュを書く | 同じ試験が通る。入れ替えの試験が、依頼の方式の写し（一時フォルダ）では失敗する |
| 3 | `claude/README.md` と `CLAUDE.md` を直す | `python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、shellcheck、`actionlint`、既存のフックの試験がすべて通る |
| 4 | コミット 1（`feat(claude): …`） | `git show --stat` |
| 5 | ユーザーが Vault のフックの削除を確かめ、`claude/settings.json` に登録を足す | `check-repo.py` が通る（登録したフックが追跡されている） |
| 6 | コミット 2（登録） | `git show --stat` |
| 7 | `/review` → `/security-review` → Codex のレビューの提案 → `/crit-review` でブランチの差分 | 指摘への対応を決める |
| 8 | push・PR 作成 | `gh pr checks` |
| 9 | 実機の確認（ユーザー） | Vault で新しいセッションを起動し、誤りのあるノートを Edit させて、点検の結果が Claude に届く。結果を `test-report.md` に書く |

<a name="impact"></a>

## 影響

- ユーザー設定に登録するので、すべてのプロジェクトの Edit・Write のたびに bash が 1 回動く。Vault 以外では、ファイルが 1 つあるかを見て終わる。
- Vault の外で `_System/Scripts/check_note.py` があるプロジェクトでは、照合が走り、ハッシュが違えば `.md` の編集のたびに exit 2 で Claude に伝える（実行はしない）。

<a name="residual-risks"></a>

## 残る経路と受け入れるリスク

- Claude が Bash（`sed` など）で書き換えたノートは点検しない。matcher が Edit・Write だけのため。
- 承認するのは点検スクリプトのコードだけで、点検スクリプトが読むデータ（ノート・`_System/Tags.md`・リンク先）は sandbox の外で読まれる。リンク先の有無の判定（`dest.exists()`）は Vault の外のパスにも及ぶので、sandbox の denyRead の場所にファイルがあるかどうかと、Vault の外の `.md` にアンカーがあるかどうかは、点検の結果から分かる。中身は出さないので受け入れる。
- dotfiles で起動したセッションの Edit・Write ツールは、`claude/hooks/check-vault-note.sha256` を書き換えられる。ユーザー設定の `Edit(~/dotfiles/claude/**)` の ask で人間の承認に回り、ほかのフックのスクリプトと同じ扱いになる。Vault で起動したセッションからは、sandbox の denyWrite と `blockWritesOutsideWorkingDirectories` で書けない。
- `MultiEdit` は今の公式ドキュメントにないが、既存の `guard-additional-dirs.sh` の登録と揃えて、matcher に残す。

<a name="rollback"></a>

## 戻し方

`claude/settings.json` から登録を外せば、次のセッションからフックは動かない。コミットを revert しても戻せる。フックはツールの実行後に動き、ファイルを書かないので、戻した後に片付けるものはない。

<a name="done"></a>

## 完了条件

- 新しい試験と既存のフックの試験、`check-repo.py`、`test-check-repo.py`、shellcheck、`actionlint` が手元で通る。
- PR の CI（`gh pr checks`）が通る。
- 実機で、Vault のノートの誤りが Claude に届くことをユーザーが確かめる。
