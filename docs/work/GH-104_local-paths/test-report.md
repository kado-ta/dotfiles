---
status: in-progress
created: 2026-11-26
---

# 試験記録: check-repo.py の消したファイル・誤検知・例外のパス

関連: [Issue #104](https://github.com/kado-ta/dotfiles/issues/104)、[PR #136](https://github.com/kado-ta/dotfiles/pull/136)、[PR #134 のレビューのコメント](https://github.com/kado-ta/dotfiles/pull/134#issuecomment-7174894953)

plan は書いていない。方針は Issue #104 と、作業中にユーザーが選んだ答え（[2 章](#decisions)）で決めた。

<a name="environment"></a>

## 1. 環境

- macOS（Claude Code の sandbox の中）、PATH の `python3`（3.15.2）、gitleaks 8.30.1。
- worktree のブランチ `fix/GH-104-local-paths` で作業した。

<a name="decisions"></a>

## 2. ユーザーが決めたこと

| ID | 問い | 決定 |
| --- | --- | --- |
| 方針 1 | パスの途中の `/home/`・`/Users/` を、どこまで検出の対象から外すか | シェルの変数の直後だけ外す。Issue の案（直前が行頭・空白・引用符などのときだけ当てる）は、`file:///Users/<名前>` や `/Volumes/Backup/Users/<名前>` を見逃すので採らない |
| 方針 2 | `main()` が例外のメッセージをそのまま出す件 | ルートを `.` にし、それでもユーザー名を含むパスが残れば型の名前だけを出す |
| D1 | 作業ツリーで消したが index に残るファイル（[6 章](#review)） | local-paths は相対パスで FAIL にする。中身を読むほかの検査は飛ばす。名前を見る検査（secret-files・markdown-names）は調べる |
| D2 | 変数の直後を外す範囲 | 変数の直後の除外は残し、実行しているユーザーのログイン名は常に止める |
| D3 | 変数の直後の一致が次の階層まで読み進める | 直す（名前を先読みにする） |
| D4 | ルートがユーザーのディレクトリの下にある場合のテスト | 足す |

<a name="tdd"></a>

## 3. 実装の前後

どの段階も、足したテストを実装の前に実行し、失敗することを確かめてから実装した。

| 段階 | 実装の前 | 実装の後 |
| --- | --- | --- |
| 最初の 3 コミット（84b419d・a31c428・1fee430） | 5 件が FAIL。消したファイルで local-paths・syntax・markdown-links・link-guard が FAIL し、`/Users/Shared` などを誤検知し、例外のメッセージに一時ディレクトリの絶対パスが出た | 144 件 OK |
| /review の後（aa47778・3d23e99・fe2d21b） | 7 件が FAIL（D1・D2・D3・lstat の権限・markdown-names）。D4 のテストは今の実装では通るので、判定の順を崩した写し（置き換えの前のメッセージでユーザー名を判定する）で実行し、2 件とも FAIL することを確かめた | 147 件 OK |
| Codex の 1 回目の後 | HEAD のテストを `LOGNAME=alice` で実行すると `test_non_user_paths_pass` が FAIL。C1〜C3 の 3 件が FAIL | 147 件 OK。`LOGNAME=alice` でも OK |

- `CalledProcessError` のメッセージを全文で確かめたテストは、Python 3.15 の書式（コマンドを引用符で囲まない）に合わずに失敗した。ルートが `.` になった部分だけを確かめるように直した。
- コミットを分けるときは、各コミットの index の中身を一時ディレクトリに書き出してテストを実行し、それぞれ OK だった（140・142・144・146・147・147 件）。

<a name="local-checks"></a>

## 4. 手元の検査

Codex の指摘を直した後の作業ツリーで実行した。

| コマンド | 終了コード | 結果 |
| --- | --- | --- |
| `python3 -B .github/scripts/test-check-repo.py` | 0 | 147 件 OK（95 秒） |
| `LOGNAME=alice python3 -B .github/scripts/test-check-repo.py -k non_user_paths` | 0 | OK |
| `python3 -B .github/scripts/check-repo.py` | 0 | 16 項目すべて PASS |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 0 | 指摘なし |
| `actionlint` | 0 | 指摘なし |
| `zizmor --offline .` | 0 | `No findings to report.` |

<a name="smoke"></a>

## 5. smoke

/review の手順（Step 4.7）で、`check-repo.py` を直接動かして確かめた。一時ディレクトリにリポジトリを作り、worktree の中の Git 管理外の `tmp/` に置いた symlink をルートとして渡した。手元でルートがホームの下にある状態と同じ形にするため。gstack の証拠の記録（`gstack-qa-evidence`）は権限で拒否されるので使わず、コマンドの出力をそのまま確かめた。

| ID | 内容 | 結果 |
| --- | --- | --- |
| P1 | 作業ツリーで `check-repo.py` | 16 項目すべて PASS |
| P2 | 追跡したファイルを作業ツリーだけで消し、権限 0 の `.json` を置く | 例外のメッセージは `./x.json`・`./claude/settings.json` のような相対の形。出力にホームのパスと一時ディレクトリのパスは 0 回 |
| P3 | P2 から権限 0 の `.json` を除き、`$T/home/…`・`/Users/Shared/…`・`/Volumes/Backup/Users/<名前>/…` の 3 行を書く | local-paths は、消したファイルと 3 行目だけを FAIL にした。syntax と markdown は PASS。ホームと一時ディレクトリのパスは 0 回 |

P2 と P3 は、/review の指摘を直した後と、Codex の指摘を直した後にも実行し、同じ結果だった。

<a name="review"></a>

## 6. /review の指摘と対応

2026-11-26 に gstack の `/review` を 1fee430 に対して実行した。

- 視点: スペシャリスト 5 つ（testing・maintainability・security・performance・simplification）と、Claude の敵対的レビュー。Red Team は起動の条件（差分が 200 行を超えるか、スペシャリストが CRITICAL を出す）に当たらなかった。
- Codex: `codex_reviews` が無効なので、/review の中では実行していない。
- 直した後に /review のやり直しはしていない（SKILL_ROUTING の「指摘への対応が決まったら終える」）。

| 指摘 | 出どころ | 対応 |
| --- | --- | --- |
| `git add` の後に作業ツリーだけで消したファイルを、local-paths・markdown-names が黙って通す。変更前は例外で FAIL していた | 敵対的レビュー・security・maintainability | D1 のとおり直した（aa47778） |
| `os.path.lexists` は権限のエラーでも偽を返し、調べられないファイルを消えたとみなす | 敵対的レビュー | 消えたとみなすのを ENOENT・ENOTDIR のときだけにした（aa47778）。この直し方には [8.1](#codex-1) の C3 の誤りが残っていた |
| 変数の直後の一致が名前の階層まで読み進め、`$X/home/Users/<名前>` の `/Users/<名前>` を調べない | security | D3 のとおり直した（3d23e99） |
| 変数の直後の除外が `$BACKUP/Users/<名前>` も外す | 敵対的レビュー | D2 のとおり直した（3d23e99） |
| ルートがユーザーのディレクトリの下にある場合のテストがない | testing | D4 のとおり直した（fe2d21b） |
| `path =os.pathsep.join(` の空白落ち、docstring 2 か所の古さ | core・testing・maintainability・敵対的レビュー | 直した（aa47778・fe2d21b） |

直さなかったもの:

- 例外のメッセージの置き換えは、パスの区切りを見ない（敵対的レビュー）。ルートが `/` などのときだけ問題になり、そうしたルートは git リポジトリではないので、先に `git ls-files` で失敗する。
- CI では、ルートの外の runner のホームの下のパスを含むメッセージが、型の名前だけになる（敵対的レビュー）。隠す側に倒れるので変えない。
- 大文字小文字の違う `/users/<名前>` と、`-Users-<名前>-` の形を検出しない（敵対的レビュー）。この差分の前からある検出漏れ。
- 新しいテストが subTest ごとに `check-repo.py` を起動する（performance）。約 2.5 秒で、同じ書き方がほかに 30 か所以上ある。
- secret-content（gitleaks）は、作業ツリーで消したファイルと、権限で調べられないファイルを調べない。変更前からの挙動で、作業ツリーだけを見る方針は [gitleaks の設計](../20261125_gitleaks-check/design.md) で受け入れ済み。

<a name="ci"></a>

## 7. GitHub Actions

[PR #136](https://github.com/kado-ta/dotfiles/pull/136) の fe2d21b の CI（run 45734709835）で、2 つのジョブ（Repository checks・Hook regression tests）がどちらも成功した。Codex の指摘を直したコミットの CI は、push の後に確かめる。

<a name="codex"></a>

## 8. Codex のレビュー

<a name="codex-1"></a>

### 8.1 1 回目（fe2d21b）

2026-11-26 に、ユーザーが通常のターミナルで `codex review --base main` を実行した。結果は `~/.codex/sessions` の記録の最終メッセージから読んだ。判定は `patch is incorrect`（確信度 0.99）で、指摘は 4 件。Codex は、読み取り専用の環境で一時ディレクトリを作れず、テストは実行していないと書いている。

| ID | 優先度 | 指摘 | 確かめたこと | 対応 |
| --- | --- | --- | --- | --- |
| C1 | P2 | ディレクトリ名に `$` を含む `/Volumes/$Archive/Users/<名前>` を、変数で始まるパスとみなして見逃す | 正しい。`$` の直前が `/` でも、変数として扱っていた | 採用。変数の除外を、直前が `/` や名前の文字（英数字・`_`・`.`・`-`）でない `$` に限った |
| C2 | P2 | `Shared` の除外が `/home` の下の `Shared` にも効く | 正しい。macOS の共有フォルダのための除外で、Linux の側を緩める理由はない | 採用。`/Users/Shared` だけを外す。定数は main の `PLACEHOLDER_USERS` に戻した |
| C3 | P2 | 検索権限のないディレクトリの下に追跡したファイルがあると、`repo_files()` の `lstat()` が `PermissionError` を投げ、そのファイルを読まない link-guard まで例外で落ちる | 正しい。ENOENT・ENOTDIR 以外の OSError を投げたままにしていた。コメント（「残して、読む検査で失敗させる」）と食い違い、/review の後に足したテストも、読む段階ではなく一覧を作る段階の例外で FAIL していた | 採用。そうしたファイルは一覧に残す。テストに、同じ状態で link-guard がほかのスクリプトの違反を出すことを足した |
| C4 | P3 | `test_non_user_paths_pass` が実行環境のログイン名を引き継ぎ、`LOGNAME=alice` の環境では失敗する | 正しい。HEAD のテストを `LOGNAME=alice` で実行すると FAIL した | 採用。テストのサブプロセスの `LOGNAME` を固定した |

Codex のレビューは、この作業で 1 回目（上限は 5 回）。
