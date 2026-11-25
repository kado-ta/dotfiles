---
status: in-progress
created: 2026-11-25
---

# 試験記録: 検査ツールの版のずれの検査

関連: [plan](plan.md)

<a name="environment"></a>

## 1. 環境

- macOS（Claude Code の sandbox の中）、PATH の `python3`（3.15.2）。
- 手元のツール（Homebrew）: shellcheck 0.11.0、actionlint 1.7.12、zizmor 1.33.1、gitleaks 8.30.1。

<a name="tdd"></a>

## 2. 実装の前後

| 対象 | コマンド | 結果 |
| --- | --- | --- |
| 変更前の `check-repo.py`（main） | `python3 -B test-check-repo.py`（最初の 7 件を足したテストを、main の `check-repo.py` と同じディレクトリに写して実行） | 117 件のうち、足した 7 件だけが FAIL（検査がないので終了コード 0 になる）。ほかの 110 件は OK |
| 最初の実装（9e728c8） | `python3 -B .github/scripts/test-check-repo.py` | 117 件 OK（54.7 秒） |
| 最初の実装（9e728c8） | レビューで足した 4 件だけを実行 | 4 件とも FAIL。案内が `update … together` のまま（2 件）、`error: TimeoutExpired: Command '['<パス>/zizmor', …` と `error: OSError: [Errno 8] Exec format error: '<パス>/shellcheck'` が出る（2 件） |
| レビューの後 | `python3 -B .github/scripts/test-check-repo.py` | 120 件 OK（72 秒。タイムアウトのテストが 10 秒かかる） |

<a name="local-checks"></a>

## 3. 手元の検査

レビューの後の作業ツリーで実行した。

| コマンド | 終了コード | 結果 |
| --- | --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 0 | 15 項目すべて PASS（`tool-versions` を含む） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 0 | 指摘なし |
| `actionlint` | 0 | 指摘なし |
| `zizmor --offline .`（キャッシュは一時ディレクトリ） | 0 | `No findings to report.` |

最初の実装（9e728c8）で、次も確かめた。

| 確かめたこと | 終了コード | 結果 |
| --- | --- | --- |
| `ci.yaml` の gitleaks を 8.30.0、shellcheck を v0.10.0 にした写しで、手元の本物のツールで実行 | 1 | `FAIL tool-versions`。shellcheck と gitleaks の 2 行だけが出た |
| `git archive 9e728c8` を展開して `git add` した写しで実行 | 0 | 15 項目すべて PASS |
| main（1dd6739、PR #128 を含む）と `git merge-tree` で合わせた木の写しで、`check-repo.py` と `test-check-repo.py` を実行 | 0 / 0 | 15 項目すべて PASS / 119 件 OK |
| 応答しない zizmor（`exec sleep 30`）を PATH の先頭に置いて実行 | 1 | `error: TimeoutExpired: Command '['<パス>/zizmor', '--version']' timed out after 10 seconds` の 1 行だけ。ツールのパスが出て、後ろの gitleaks を調べていない（[5 章](#review) の D1） |

<a name="test-speed"></a>

## 4. テストの所要時間

偽のツールを最初はテストごとに作っていて、テスト 3 件が 0.9 秒から 2.6 秒になった（117 件では 65 秒から 109 秒）。CPU 時間はほぼ変わらず、待ち時間が増えていた。

- 事実: 新しく作った sh スクリプトを直接起動すると、初回は 0.11〜0.31 秒、2 回目以降は 0.02〜0.03 秒だった。`/bin/sh <スクリプト>` で起動すると、初回でも 0.02 秒だった（2026-11-25 に測った）。
- 推測: 初めて実行するファイルを macOS が調べる時間。確かめていない。
- 対応: 偽のツールはクラスで 1 回だけ作り、差し替えるテストだけ、そのツールだけを置いた別のディレクトリを PATH の先頭に足す。117 件で 54.7 秒になった。

<a name="review"></a>

## 5. レビューの指摘と対応

2026-11-25 に gstack の `/review` を 9e728c8 に対して実行した。

- 視点: スペシャリスト 5 つ（testing・maintainability・security・performance・simplification）、Red Team、Claude の敵対的レビュー。
- Codex: `codex_reviews` が無効なので実行していない。
- 採否: ユーザーが D1〜D4 を決めた。

| ID | 指摘 | 出どころ | 対応 |
| --- | --- | --- | --- |
| D1 | 版のコマンドのタイムアウトと OSError が `main()` まで抜け、ツールのパスを出し、残りのツールを調べない | maintainability・security・testing・敵対的レビュー | 直した。ループの中で捕まえて `cannot read the version of <ツール>` にする。テストを 2 件足した |
| D2 | 手元が CI より古いときも「CI の版を上げる」と案内し、従うと CI の版を下げる | maintainability | 直した。版を数の組で比べ、古ければ `run brew upgrade <ツール>` と案内する。両方の向きのテストを置いた |
| D3 | SHA256 の取り方と、版上げを別の PR にすることが、どこにも書かれていない。関係のない作業の途中で、確かめていない値に上げる流れになりうる | Red Team・敵対的レビュー | 直した。`ci.yaml` のコメントに書き、メッセージに `in a separate PR` を足した |
| D4 | (1) 出力の最初の `x.y.z` を版とみなすので、ラッパーが先に別の版を出すと誤って PASS になる。(2) 環境のずれと中身の失敗が同じ終了コード 1 になり、読み飛ばす癖がつく | 敵対的レビュー | 見送った。(1) 今の 4 つの出力では起きない（2 章の偽のツールと、手元の本物で確かめた）。(2) 各 FAIL の行に検査の名前が出る。終了コードを変えると CI などの扱いも変わる。ラッパーや shim でツールを入れるようになったら見直す |

指摘から外したもの（ユーザーに尋ねていない）:

- 引用符や行末のコメントを付けた `ci.yaml` の値は、本当の原因と違うメッセージで FAIL になる（testing・敵対的レビュー）。入力は自分たちの `ci.yaml` に限られ、どちらも失敗の側に倒れる。
- 手元の検査は、コミットではなく作業ツリーの `ci.yaml` を読む（Red Team）。`check-repo.py` は、git add 前のファイルも含めて作業ツリーを調べる設計（docstring）で、ほかの検査と同じ。
- `ci.yaml` に足した新しい `*_VERSION` が対象から外れる。版のコマンドを `cwd` なしで動かす（敵対的レビュー）。どちらも、今は起きる経路がない。
- `CLAUDE.md` が、check-repo.py に要るツールとして gitleaks だけを挙げている（敵対的レビュー）。Plan の 3.3 で、変えないと決めた。
- CI の `tool-versions` は、固定した版を入れて調べるので、必ず PASS になる（Red Team）。確かめられるのは、リリースのバイナリの版の出力を読めることだけ（plan の 4 章のとおり）。

同じ形の既存の箇所: `secret-content` の gitleaks の実行（`GITLEAKS_TIMEOUT = 120`）も、タイムアウトすると `main()` がコマンドのパスを出す。この作業の前からある挙動で、変えていない。

<a name="ci"></a>

## 6. GitHub Actions

PR の CI の結果を、ここに書く。
