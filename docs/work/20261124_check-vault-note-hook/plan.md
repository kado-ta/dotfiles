---
status: in-progress
created: 2026-11-24
---

# Vault のノートを点検するフック 実装計画

関連: 依頼書（2026-11-24 にチャットで受けた「Obsidian Vault のノートを点検するユーザーレベルのフックを追加する」）、Vault（`~/Obsidian/main`）の README §6.5 と AGENTS.md

> [!IMPORTANT]
> 2026-11-24 の `/review` の指摘を受けて、設計を作り直した（[レビューを受けた変更](#review-changes)）。最初の版（承認済みの SHA-256 と照合して、Vault の点検スクリプトを sandbox の外で実行する）は、コミット `f8e1825`・`462aaf9` にある。

<a name="goal"></a>

## 目的

Claude Code が Obsidian Vault のノートを Edit・Write したとき、Vault の点検スクリプト `_System/Scripts/check_note.py` を自動で実行し、誤りを Claude に知らせる PostToolUse フックを、dotfiles に置く。Vault の `.claude/` は Remotely Save で同期されないので、ほかの端末にも届く dotfiles に置く。

フックは sandbox の外で動く。sandbox から書ける場所のコードを動かさないことと、sandbox が読ませないファイルを点検スクリプトに読ませないことの 2 つを守る。

<a name="review-changes"></a>

## レビューを受けた変更

`/review`（2026-11-24）で、最初の版に次の 2 つの CRITICAL の指摘があった。

- **C1: 読む場所を固定していない。** 照合で固定していたのは、点検スクリプトの中身だけだった。点検スクリプトは `Path(__file__).resolve().parents[2]` で Vault のルートを決める。そのため、`_System/Scripts/check_note.py` を、`$HOME` の 2 階層下に置いた承認済みの写しへの symlink にすると、Vault のルートが `$HOME` になる。その状態でノートを symlink に差し替えると、sandbox の外の点検スクリプトが Vault の外のファイルを読み、その中身の一部（Properties の行の先頭 40 文字、値、見出し、リンク先）を、誤りの文として Claude に返す。偽のデータで再現した。
  - 位置を realpath で固定しても、点検スクリプトの中の `resolve()` と読み込みのあいだの競合は残る。Red Team が、入れ替えのループで 400 回中 3 回の漏れを実測した。
- **C2: 承認の手順に競合がある。** 人間がレビューしたバイト列と、`shasum` がハッシュを取るバイト列が結び付いていない。sandbox の中で入れ替えを続けられると、悪意のある版のハッシュが記録され、sandbox の外で任意のコードが動く。

ユーザーが選んだ直し方（2026-11-24）:

1. **実行するコードは、dotfiles のレビュー済みの写し `claude/hooks/vault/check_note.py` だけにする（C2）。** 承認は、写しの git の差分のレビューになる。`claude/hooks` は sandbox から書けないので、レビューしたバイト列がそのまま動く。Vault の点検スクリプトは、写しと同じかを比べるためだけに読む。違えば、点検せず、exit 2 でそのことを知らせる。ハッシュのファイルはなくす。
2. **写しは Seatbelt（`sandbox-exec`）の中で動かす（C1）。** `$HOME`・`/private/tmp`・`/private/var/folders`・`/Volumes` の読み込みを拒否し、Vault（realpath）と、フックが実行に使う 2 つのファイルだけを許す。書き込みとネットワークも拒否する。カーネルが、symlink を解決した後のパスで判定するので、競合は残らない。
3. **写しは公開してよい。** dotfiles は公開リポジトリなので、写しも公開される。中身は Vault のフォルダ構成・Properties の規約・タグの規則で、絶対パスや秘密は含まない（2026-11-24 に全文を読んだ）。
4. **黙って点検しない場合は、依頼の仕様のままにする。** Vault で点検スクリプトがないときと、Vault のサブフォルダや `/add-dir` のセッションでは、何もしない。

<a name="decisions"></a>

## 決めたこと

最初の版から引き継ぐもの（2026-11-24 にユーザーが選んだ）:

- Command Line Tools がない端末では、exit 2 で Claude に知らせる。公式ドキュメント（hooks reference）では、exit 0 のフックの stderr は Claude に渡らないため。
- `claude/settings.json` への登録は、同じ PR の別のコミットにする（`462aaf9`）。

<a name="diff-from-request"></a>

## 依頼との違い

- 依頼では、Vault の点検スクリプトを、ハッシュ（`check-vault-note.sha256`）と照合して実行するとしていた。これを、dotfiles の写しを Seatbelt の中で実行し、Vault の点検スクリプトとは比べるだけ、に変えた（[レビューを受けた変更](#review-changes)）。ハッシュのファイルと、その更新手順はなくす。
- JSON の解析は Python の標準ライブラリで行う。PATH のコマンド（`jq`・`shasum`・`cat`・`dirname`）は使わず、外部のコマンドは絶対パスで呼ぶ。
- Command Line Tools がないときは、exit 0 ではなく exit 2 にする。
- ルートの `CLAUDE.md` の「規約」にある、フックの試験の一覧に、新しい試験と、sandbox の外で実行することを足す。CI の手順に、Seatbelt の試験のスキップを失敗として扱う環境変数を足す。

<a name="design"></a>

## 設計

<a name="design-files"></a>

### ファイル

| ファイル | 役割 |
| --- | --- |
| `claude/hooks/check-vault-note.sh` | 登録するフック。早く終わる判定と、Command Line Tools の確認だけをして、Python の部分を呼ぶ |
| `claude/hooks/check-vault-note.py` | Python の部分。sandbox の外の段（入力の判定と、写しとの比較）と、Seatbelt の中の段（写しの実行）の 2 つの段を持つ |
| `claude/hooks/check-vault-note.sb` | Seatbelt の profile |
| `claude/hooks/vault/check_note.py` | Vault の点検スクリプトの写し（レビュー済み）。最初は 2026-11-23 に Crit で承認された版（SHA-256 `367191ef…`） |
| `claude/hooks/check-vault-note.sha256` | 削除する |

<a name="design-hook"></a>

### フック `check-vault-note.sh`

macOS の `/bin/bash` 3.2 で動かす。`set -u`。here document を使わない（bash 3.2 は一時ファイルに書き、書けないと 1 で終わって点検が黙って止まる）。上から順に判定する。

| # | 条件 | 動作 |
| --- | --- | --- |
| 1 | `CLAUDE_PROJECT_DIR` が空 | 入力を `/bin/cat` で読み切り、何も出さずに exit 0 |
| 2 | `${CLAUDE_PROJECT_DIR%/}/_System/Scripts/check_note.py` が通常のファイルでない | 同上 |
| 3 | `$(/usr/bin/xcode-select -p)/usr/bin/python3` が実行できない | 入力を読み切り、「点検できない。ユーザーに `xcode-select --install` を頼む」を stderr に書いて exit 2 |
| 4 | それ以外 | `"$dev/usr/bin/python3" -I -B "$(/usr/bin/dirname -- "$0")/check-vault-note.py" "$project" "$python" 1>&2 \|\| exit 2` |

`/usr/bin/python3`（xcrun の shim）ではなく、`xcode-select -p` の先の python3 を直接使う。shim は `/private/var/folders` のキャッシュを使うので、Seatbelt の中で動かすと読めないため。

<a name="design-py"></a>

### Python の部分 `check-vault-note.py`

`-I`（スクリプトのフォルダとカレントディレクトリを `sys.path` に入れない。`PYTHON*` の環境変数を読まない）と `-B`（`__pycache__` を書かない）で動かす。

**sandbox の外の段**（引数: プロジェクト、python3 のパス。stdin はフックの入力）:

1. stdin の JSON から `tool_input.file_path` を読む。解析できない・文字列でない → exit 0。
2. パスが `$project/` で始まり `.md` で終わらない → exit 0。
3. 写し（このファイルと同じフォルダの `vault/check_note.py`）を読む。読めない → 「写しを読めない」を stderr に書いて exit 2。
4. Vault の点検スクリプトを、写しの長さ＋1 バイトまで読む（`/dev/zero` への symlink でもメモリを使い切らない）。読めない、または写しと違う → 「Vault の点検スクリプトが dotfiles の写しと違うため点検しない。ユーザーに、差分のレビューと写しの更新を頼む」を stderr に書いて exit 2。中身は出さない。
5. `os.execv` で `/usr/bin/sandbox-exec -f check-vault-note.sb -D HOME_DIR=… -D VAULT=… -D SELF=… -D COPY=… <python3> -I -B <このファイル> --run <プロジェクト> <ノート>` に置き換わる。
   - `HOME_DIR` は、`pwd.getpwuid(os.getuid()).pw_dir` の realpath（環境変数の `HOME` に頼らない）。
   - `VAULT` はプロジェクトの realpath、`SELF` と `COPY` はこのファイルと写しの realpath。

**Seatbelt の中の段**（`--run`）:

1. 写しを読む。
2. 新しいモジュール `__main__` を作って `sys.modules["__main__"]` に入れ、`__file__` を `$project/_System/Scripts/check_note.py`（Vault のパス）にする。点検スクリプトは `__file__` から Vault のルートを決めるため。
3. `sys.argv` を `[Vault のパス, ノート]` にし、写しのバイト列を `compile(src, <写しのパス>, "exec", dont_inherit=True)` して `exec` する。
   - traceback に出る行は写しから読まれる（Vault の点検スクリプトを読み直さない）。
   - 終了コードは点検スクリプトのもの（0・1・2）。bash が 0 以外を exit 2 にする。

点検スクリプトが 0 を返したときの警告は、stderr に出るが Claude には届かない（依頼の仕様のとおり）。

<a name="design-sb"></a>

### Seatbelt の profile `check-vault-note.sb`

```scheme
(version 1)
(allow default)
(deny network*)
(deny file-write*)
(deny file-read-data
  (subpath (param "HOME_DIR"))
  (subpath "/Volumes")
  (subpath "/private/tmp")
  (subpath "/private/var/folders"))
(allow file-read-data
  (subpath (param "VAULT"))
  (literal (param "SELF"))
  (literal (param "COPY")))
```

- 実行するのはレビュー済みの写しだけなので、守る対象は、点検スクリプトに渡るデータ（ノート・リンク先・タグの辞書）の読み込みに絞る。そのため、既定は許可にして、読み込み・書き込み・ネットワークを止める。`cc-crit.sb` は、信頼しない CLI を動かすので、既定で拒否している。今回はそこが違う。
- `file-read-data` だけを止め、メタデータ（`stat`・`readlink`）は止めない。点検スクリプトが `resolve()`・`exists()`・`is_dir()` を使うため。その結果、Vault の外のパスが存在するかどうかは分かる（最初の版と同じく受け入れる）。
- `/dev/urandom`・`/dev/random`・`/dev/zero` は止めない。最初は止めていたが、Python 3.9 が起動時のハッシュの初期化に `/dev/urandom` を読むので、Seatbelt の中で起動しなかった（2026-11-24 にユーザーのターミナルで確かめた。`_Py_HashRandomization_Init: failed to get random numbers`）。`/dev/zero` だけを止めても、`/dev/urandom` が開いているので意味が薄い。
- 拒否する場所は、Claude Code の sandbox の `denyRead` がある場所（`$HOME` と、Claude Code が使う `/private/tmp` の下）を含むように広めに取る。`denyRead` の項目を 1 つずつ写すと、設定を変えるたびに揃える手間が要るため。
- 前提: 同じ操作に複数の規則が当たるときは、後の規則が勝つ。試験の [Seatbelt の中の確認](#design-test) で確かめる（Vault は試験では `$TMPDIR` の下、つまり拒否する場所の下にあるため、この前提が崩れると点検が動かない）。

<a name="design-test"></a>

### 試験 `claude/hooks/tests/test-check-vault-note.sh`

`test-guard-additional-dirs.sh` の書き方に合わせる（`$BASH` でフックを起動する、`PASS` / `FAIL` と件数を出す、説明は英語）。フック・Python の部分・profile を一時フォルダに写し、その隣に偽の写しを、偽の Vault に同じ中身の偽の点検スクリプトを置く。本番の挙動を変える設定項目は足さない。

Claude Code の sandbox の中では `sandbox-exec` を入れ子にできない（2026-11-24 に `sandbox_apply: Operation not permitted`、rc=71 を確かめた）。そのため、試験は 2 つに分ける。

**いつでも動く確認**（Seatbelt に入る前に終わる経路）:

| 区分 | 確かめること |
| --- | --- |
| 何もしない | `.md` 以外、プロジェクトの外、接頭辞だけが同じ隣のフォルダ、`CLAUDE_PROJECT_DIR` が空・未設定、点検スクリプトがない、入力を解析できない、`file_path` が文字列でない、`tool_input` がない → exit 0、出力なし |
| 点検スクリプトがないときの判定 | 点検スクリプトのないプロジェクトを、Command Line Tools がない状態（`DEVELOPER_DIR` を空のフォルダにする）で動かしても exit 0、出力なし（`[ -f "$checker" ]` を消すと失敗する） |
| 写しと違う | Vault の点検スクリプトが写しと違う、写しがない、Vault の点検スクリプトが `/dev/zero` への symlink → exit 2、決まった文、すぐ終わる |
| Command Line Tools | `DEVELOPER_DIR` が空のフォルダ → exit 2、`xcode-select --install` を含む文 |
| 一時ファイル | カレントディレクトリと `TMPDIR` が書けなくても、写しと違う経路が exit 2 と決まった文で終わる（1 で黙って終わらない） |
| 入力 | 大きな入力を、早く終わる経路・Python の外の段・Command Line Tools がない経路で読み切る |

**Seatbelt の中の確認**（入れ子の `sandbox-exec` が失敗する環境ではスキップし、件数を出す。環境変数 `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1` のときはスキップを失敗にする。`cc-crit` の試験の前例に合わせる）:

| 区分 | 確かめること |
| --- | --- |
| 実行 | 点検スクリプトが 1 → exit 2、出力は stderr だけ。0 → exit 0。`__file__` から決めた Vault のルートと、引数（ノートのパス）が正しい |
| 読み込み | Vault の中のノートは読める。Vault の外（`$TMPDIR` の下）のファイルへの symlink のノート、`$HOME` の下に作った一時ファイルへの symlink のノート、`/dev/zero` への symlink のノートは、中身が出ない |
| 書き込み・通信 | Vault の中への書き込みと、`127.0.0.1` への接続が拒否される |
| モジュール | 点検スクリプトのフォルダと、カレントディレクトリに置いた偽の `re.py` が読み込まれない |
| 写しだけを実行 | 比べた後で Vault の点検スクリプトを別の版に差し替えても、実行されるのは写し（FIFO で、比べ終わった直後に差し替える） |

<a name="design-docs"></a>

### 文書と CI

- `claude/README.md`: フックの表の行と、「Vault のノートの点検」の節を書き直す。
  - 書くこと: 仕組み（写し・比較・Seatbelt）。
  - 写しの更新手順: 通常のターミナルで、dotfiles のルートに移動し、`cp ~/Obsidian/main/_System/Scripts/check_note.py claude/hooks/vault/check_note.py` を実行する。`git diff -- claude/hooks/vault/check_note.py` をレビューしてコミットする。レビューするのは、写した後の dotfiles の中のバイト列（sandbox から書けない）。
  - 試験の Seatbelt の部分は、sandbox の外で実行すること。
- `CLAUDE.md`（ルート）: 「規約」の試験の列挙に、`test-check-vault-note.sh` を sandbox の外でも実行することを足す（`test-cc-crit-profile.py` の書き方に合わせる）。
- `.github/workflows/ci.yaml`: Shell hook tests の手順に `CHECK_VAULT_NOTE_SEATBELT_REQUIRED: "1"` を足す。GitHub の macOS のランナーで `sandbox-exec` が動くことは、まだ確かめていない。動かなければ CI が失敗するので、そこで分かる。
- Vault の README §6.5 と AGENTS.md の承認の手順（ハッシュの更新）は、写しの更新に変わる。Vault 側の文書なので、ユーザーが直す。

<a name="design-registration"></a>

### 登録

`claude/settings.json` の登録（`462aaf9`）は変えない。

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

<a name="steps"></a>

## 手順

| # | 作業 | 確かめ方 |
| --- | --- | --- |
| 1 | 試験を書き直す | 今のフック（ハッシュの版）で、いつでも動く確認のうち、写しに関わるものが失敗する |
| 2 | Python の部分・profile・写しを足し、フックを直し、ハッシュのファイルを消す | sandbox の中で、いつでも動く確認が通り、Seatbelt の中の確認はスキップと表示される |
| 3 | ユーザーが通常のターミナルで試験を実行する | `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh` がすべて通る。本物の Vault のノートで、写しの点検結果が直接実行と同じになる |
| 4 | `claude/README.md`・`CLAUDE.md`・`ci.yaml` を直す | `check-repo.py`、`test-check-repo.py`、shellcheck、`actionlint`、既存のフックの試験が通る |
| 5 | コミット（`fix(claude): …`。ハッシュの版から写しと Seatbelt の版に変える） | `git show --stat` |
| 6 | `/review` → `/security-review` → Codex のレビューの提案 → `/crit-review` でブランチの差分 | 指摘への対応を決める |
| 7 | push・PR 作成 | `gh pr checks`（CI で Seatbelt の確認がスキップされずに通る） |
| 8 | 実機の確認（ユーザー） | Vault で新しいセッションを起動し、誤りのあるノートを Edit させて、点検の結果が Claude に届く。結果を `test-report.md` に書く |

<a name="impact"></a>

## 影響

- ユーザー設定に登録するので、すべてのプロジェクトの Edit・Write のたびに bash が 1 回動く。Vault 以外では、ファイルが 1 つあるかを見て終わる。
- Vault のノートの Edit・Write では、bash・Python・`sandbox-exec`・Python の順に動く。2026-11-24 の版の、ほぼ倍の起動時間になる見込み（測って `test-report.md` に書く）。
- `_System/Scripts/check_note.py` があるほかのプロジェクトでは、写しと比べ、違えば `.md` の編集のたびに exit 2 で知らせる（実行はしない）。

<a name="residual-risks"></a>

## 残る経路と受け入れるリスク

- Claude が Bash（`sed` など）で書き換えたノートは点検しない。matcher が Edit・Write だけのため。
- sandbox の外の段は、Vault の点検スクリプトのパスを（写しの長さ＋1 バイトまで）読む。symlink で別のファイルを指させても、分かるのは写しと同じかどうかだけ。FIFO を指させると、タイムアウト（30 秒）まで止まる。
- Seatbelt の中でも、メタデータは読めるので、Vault の外のパスが存在するかどうかは点検の結果から分かる。拒否する場所の外（`/etc` など）は読めるが、そこは Claude Code の sandbox からも読める。
- Vault の中の FIFO のノートや巨大なノートは、タイムアウトまで点検を止める。ノートやリンク先を `/dev/urandom` などへの symlink にすると、点検スクリプトがタイムアウトまでメモリを使い続ける。タイムアウトのときに、Claude Code が子のプロセスまで止めるかは確かめていない。どれも資源を使わせるだけで、中身は出ない。
- `sandbox-exec` は Apple が非推奨としているが、`cc-crit` と Claude Code の sandbox も同じ仕組みを使っている。使えなくなったときは、点検が exit 2 で止まるので気付ける。
- `DEVELOPER_DIR` やカスタムの Xcode が `$HOME` の下にあると、Python の標準ライブラリを読めずに点検が exit 2 で止まる。
- dotfiles で起動したセッションの Edit・Write ツールは、写しを書き換えられる。ユーザー設定の `Edit(~/dotfiles/claude/**)` の ask で人間の承認に回り、ほかのフックのスクリプトと同じ扱いになる。Vault で起動したセッションからは、sandbox の denyWrite と `blockWritesOutsideWorkingDirectories` で書けない。
- `MultiEdit` は今の公式ドキュメントにないが、既存の `guard-additional-dirs.sh` の登録と揃えて、matcher に残す。

<a name="rollback"></a>

## 戻し方

`claude/settings.json` から登録を外せば、次のセッションからフックは動かない。コミットを revert しても戻せる。フックはツールの実行後に動き、ファイルを書かないので、戻した後に片付けるものはない。

<a name="done"></a>

## 完了条件

- sandbox の中で、試験のいつでも動く確認と、既存のフックの試験、`check-repo.py`、`test-check-repo.py`、shellcheck、`actionlint` が通る。
- ユーザーの通常のターミナルと CI で、`CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1` の試験がすべて通る。
- 実機で、Vault のノートの誤りが Claude に届くことをユーザーが確かめる。
