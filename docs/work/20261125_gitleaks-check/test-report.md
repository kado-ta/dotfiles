---
status: done
created: 2026-11-25
---

# 試験記録: check-repo.py の gitleaks 検査

<a name="related"></a>

## 関連

- [design.md](design.md)
- [plan.md](plan.md)

<a name="environment"></a>

## 環境

- macOS（Claude Code の sandbox の中）、gitleaks 8.30.1（Homebrew）、PATH の `python3`。

<a name="task-1"></a>

## Task 1: 検査 `secret-content`

<a name="tdd"></a>

### テストの失敗と成功

| 段階 | コマンド | 結果 |
| --- | --- | --- |
| 実装前 | `python3 -B .github/scripts/test-check-repo.py` | 102 件中 5 件が失敗（FAIL を期待する 5 件が終了コード 0）。34.7 秒 |
| 実装後 | 同上 | 102 件すべて OK。41.0 秒（足す前は 93 件で 32.1 秒） |

<a name="mutation"></a>

### テストが誤りを捕まえるかの確認

検査スクリプトの写しをわざと壊し、対応するテストを実行した（本物のファイルは変えていない）。

| 壊し方 | テスト | 結果 |
| --- | --- | --- |
| 環境変数 `GITLEAKS_CONFIG` を除かない | `test_gitleaks_config_env_is_ignored` | 失敗した（捕まえた） |
| symlink を写す | `test_symlink_is_not_followed` | 失敗した（捕まえた） |
| 出力に `Match` を足す | `test_secret_in_tracked_file_fails` | 通った。`--redact` で報告の値が伏せられるため |
| 出力に `Secret` を足す | 同上 | 通った。理由は同上 |
| `--redact` を外し、出力に `Secret` を足す | 同上 | 失敗した（捕まえた） |
| `--config` を渡さない | `test_repo_gitleaks_config_allowlist_passes` | 通った。gitleaks が対象のパスの `.gitleaks.toml` を自分で読むため |

値を伏せる守りは 2 重（`--redact` と、出力に値を出さないこと）で、両方を外すとテストが失敗する。

<a name="real-repo"></a>

### 今のリポジトリへの実行

| 確認 | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS。`secret-content` の見つかった件数は 0。0.49 秒（足す前は 0.25 秒） |
| 調べた範囲 | 239 ファイル、2,575,880 バイトを写し、gitleaks は約 2.57 MB を 71.6 ミリ秒で調べた |
| 未追跡の偽の秘密（`canary-gitleaks.txt`）を置いて実行 | `FAIL secret-content` と `canary-gitleaks.txt:1: github-pat`。値は出力に出なかった。ファイルは同じスクリプトで消した |

誤検知が 0 件だったので、`.gitleaks.toml` と `gitleaks:allow` は使っていない。

<a name="task-2"></a>

## Task 2: CI に gitleaks を入れる

| 確認 | 結果 |
| --- | --- |
| `gitleaks_8.30.1_checksums.txt` の `linux_x64` の行 | CI に書いた SHA256 と一致 |
| tar.gz を取得して照合・一覧 | `shasum -a 256 -c` が OK、アーカイブのルートに `gitleaks` がある |
| `actionlint` | 出力なし |

<a name="review"></a>

## `/review` の指摘と修正

専門レビュー 5 件（テスト・保守性・セキュリティ・性能・単純化）と敵対的レビューを実行した。保守性・性能・単純化は指摘なし。Codex のパスは gstack の設定（`codex_reviews` が無効）で実行していない。

| 指摘 | 扱い |
| --- | --- |
| allowlist の `paths` が一時ディレクトリの絶対パスに当たり、`(?:^|/)src/`・`(?:^|/)tmp/` のような除外で全ファイルが外れる（セキュリティと敵対的レビューが独立に検出） | 修正。写した先を cwd にして `.` を調べる |
| `GITLEAKS_CONFIG_TOML` を除く処理のテストがない | テストを追加 |
| `--config` を外すと `.gitleaks.json` が `.gitleaks.toml` より先に読まれ、秘密を見逃す（実測）のに、テストがない | テストと理由のコメントを追加 |
| 「見つかった」の終了コード 2 が Go の panic と重なる。0 と 2 以外の分岐のテストがない。stderr に色の制御文字が出る | 終了コードを 42 に変更し、`NO_COLOR=1` を渡す（`--no-color` では設定の読み込みのログの色が消えないことを実測）。テストを 2 件追加 |
| 通常のファイルがないと写した先が作られず gitleaks が失敗する | 写した先をループの前に作る |
| 作業ツリーと HEAD・index のずれ、既定の除外の種類、`.gitleaks.toml` の中身 | ユーザーの判断で受け入れ、design.md の残るリスクに追記 |

修正の検証:

| 確認 | 結果 |
| --- | --- |
| 修正前に足したテストを実行 | 107 件中 4 件が失敗（相対パスの 2 件・色・終了コード） |
| 修正後 | 107 件すべて OK（45.1 秒） |
| 守りを外した写しで各テストを実行（`GITLEAKS_CONFIG_TOML` を除かない、`--config` を渡さない、絶対パスを渡す、`NO_COLOR` を外す、報告が空の分岐を消す） | 5 件ともテストが失敗した（捕まえた） |
| 絶対パスと相対パスで、今のリポジトリを調べたバイト数 | どちらも 2,577,698 バイト。検査の範囲は変わっていない |

`/review` は修正を入れたパスで終え、修正後に全体をもう一度見直すパスは回していない（記録は `converged:false`）。Red Team は起動条件（差分 200 行超）に当たったが、差分の大半が作業文書でコードは 116 行のため、起動していない。

<a name="security-review"></a>

## `/security-review`

修正後のブランチ（41fd11a）に実行した。信頼度 8 以上の指摘はなかった。

<a name="merge-main"></a>

## main の取り込み

main（#115〜#120）を取り込んだ。#119（CI に zizmor を追加）と `.github/workflows/ci.yaml` が衝突したので、両方の版の定義と取得の手順を残した。マージは sandbox の中では `claude/` などへの書き込みで止まるため、ユーザーが通常のターミナルで実行し、衝突の解決とコミットを Claude が行った。

| 確認（マージ後） | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 107 件 OK |
| `claude/scripts/test-skills-check.py`・`test-skill-usage.py`・`test-trust-audit.py` | すべて OK |
| `actionlint` | 出力なし |
| `zizmor --offline .` | 指摘なし |
| shellcheck（CLAUDE.md の規約のコマンド） | 出力なし |

<a name="codex"></a>

## Codex のレビュー

PR #123 のマージ後に、ユーザーが通常のターミナルで実行した。結果は Codex の記録（`last_agent_message`）から読んだ。

<a name="codex-1"></a>

### 1 回目: `codex review --base 305dba0`（2026-11-25、66fad2a）

総評は「patch is incorrect」。Codex は `git diff --check`・構文解析・shellcheck・actionlint・zizmor を実行して指摘なし、回帰テストは読み取り専用のため未実行。

| 指摘 | 優先度 | 内容 |
| --- | --- | --- |
| 1 | P2 | 0 と 42 以外で終わったときに gitleaks の stderr をそのまま出すので、`.gitleaks.toml` の構文エラーや不正な正規表現に含まれる値が CI のログに出る（`--redact` でも残ることを Codex が確認） |
| 2 | P2 | 途中のディレクトリが symlink だと、リポジトリの外のファイルを写して調べる（`is_symlink()` は最後の要素だけを見る） |
| 3 | P3 | gitleaks が PATH の相対ディレクトリにあると、`shutil.which()` が相対パスを返し、`cwd` を変えた後に起動できない |
| 4 | P3 | gitleaks がないときのテストが、`/usr/bin`・`/bin` に gitleaks がある環境では前提の確認で失敗する |

<a name="codex-2"></a>

### 2 回目: challenge（`codex exec`、2026-11-25、66fad2a）

依頼文は Git の管理外の `.gstack/tmp/codex-challenge.md`（変更前と比べて期待どおりに働かない入力を、リポジトリのスクリプトを実行せずに挙げる依頼）。結果はコードからの予測で、Codex は検証していない。

| 指摘 | 優先度 | 内容 |
| --- | --- | --- |
| C1 | P1 | 見つかった値がファイル名や `.gitleaks.toml` のルール ID に入っていると、`File`・`RuleID` は伏せられないので出力に出る |
| C2 | P1 | `.gitleaks.toml` の `[extend] path` に書いたユーザー名入りの絶対パスが、gitleaks のエラー（stderr）経由で出る |
| C3 | P1 | `[extend] useDefault = true` もルールもない `.gitleaks.toml`（`title` だけなど）だと、既定のルールが使われず、全件を見逃して PASS する |
| C4 | P1 | 大文字小文字を区別しない macOS の一時ディレクトリでは、写した `.GITLEAKSIGNORE` を gitleaks が `.gitleaksignore` として読み、相対パスの fingerprint で検出を外す |
| C5 | P2 | `git()` が `text=True` で読むので、ファイル名の CR が LF に変わり、別のファイルを調べる |
| C6 | P2 | 大文字小文字だけが違う 2 つのファイルが、大文字小文字を区別しない一時ディレクトリで上書きされる |
| C7 | P2 | ルートの `.gitleaksignore` 自体の中身は調べない |
| C8 | P2 | 1 行が 10 万バイトを超えると、gitleaks の分割の境界をまたぐ値を見逃す |

<a name="codex-decisions"></a>

### 採否（ユーザーの判断）

| 指摘 | 採否 | 理由 |
| --- | --- | --- |
| 1 回目の 2、C3、C4 | 採用 | 下の「Codex の指摘への修正」で直した |
| 1 回目の 1、C1、C2 | 不採用 | 出るのはファイル名・`.gitleaks.toml` の中身など、push した時点でリポジトリで公開済みのもので、CI のログに出ても新しい漏れにならない。手元の出力は公開されない。stderr は CI で gitleaks が動かない理由を調べる手がかりになる |
| 1 回目の 3 | 不採用 | PATH に相対ディレクトリを入れることはまれで、起きても FAIL になる |
| 1 回目の 4 | 不採用 | 前提を `assertIsNone` で明示しているので、理由の分かる失敗になる。CI と手元の Mac には当てはまらない |
| C5 | 不採用 | CR を含む名前が 1 つだけなら `local-paths` がファイルを開けずに FAIL する。黙って通るのは、CR と LF だけが違う名前が並ぶ場合だけ |
| C6 | 不採用 | worktree が大文字小文字を区別しないボリュームにあり、大文字小文字だけが違う 2 つのファイルを並べて置けない |
| C7、C8 | 受け入れる | 下の「増えた受け入れリスク」に書いた |

<a name="codex-fixes"></a>

### Codex の指摘への修正

設計書（`done`）は編集せず、変えた振る舞いをここに書く。

- 実体のパスがリポジトリの外にあるファイル（途中のディレクトリが symlink のもの）は写さない（1 回目の 2）。
- ルートの `.gitleaksignore` は、大文字小文字を区別せずに写さない（C4）。
- `.gitleaks.toml` に `[extend] useDefault = true` がなければ `.gitleaks.toml: [extend] useDefault = true is required` で FAIL にする。TOML として読めない設定は gitleaks に渡し、gitleaks のエラーで FAIL にする（C3）。

| 確認 | 結果 |
| --- | --- |
| 修正前に足したテスト 3 件（`test_file_under_symlinked_dir_is_not_copied`・`test_gitleaks_toml_without_default_rules_fails`・`test_uppercase_gitleaksignore_does_not_suppress`）を実行 | 3 件とも失敗した。C3 と C4 は Codex の予測どおり、秘密を見逃して PASS した（C4 は macOS の一時ディレクトリで再現） |
| 修正後の `python3 -B .github/scripts/test-check-repo.py` | 110 件すべて OK（42.9 秒） |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS |
| 作業ツリーに偽の秘密を置いて実行 | `FAIL secret-content`、値は出力に出ない |
| shellcheck・actionlint | 出力なし |

symlink のテストでは、既存の `local-paths` も symlink 先のディレクトリを開けずに FAIL した（`IsADirectoryError`）。今回の範囲外なので直していない。

<a name="accepted-risks"></a>

### 増えた受け入れリスク

[design.md](design.md#residual-risks) の「残るリスク」に加えて、次を受け入れる。

- ルートの `.gitleaksignore` 自体の中身は調べない（C7）。
- 1 行が 10 万バイトを超えると、gitleaks の分割の境界をまたぐ値を見逃しうる（C8。gitleaks 8.30.1 の制約）。
- 見つかった値がファイル名や `.gitleaks.toml` のルール ID に入っていると、出力に出る（C1）。gitleaks が 0 と 42 以外で終わったときの stderr に、`.gitleaks.toml` の中身が出うる（1 回目の 1、C2）。どちらも公開済みのリポジトリの中身で、新しい漏れではない。

<a name="ci"></a>

## PR の CI

| PR | 結果 |
| --- | --- |
| [#123](https://github.com/kado-ta/dotfiles/pull/123)（66fad2a） | Repository checks: pass（1 分 17 秒）、Hook regression tests: pass（2 分 55 秒） |

PR を作った直後は、main が進んで PR が衝突していたため、CI が始まらなかった（`gh pr checks` は「no checks reported」）。main（305dba0）を取り込み、`CLAUDE.md` の衝突を解決して push した後に実行された。
