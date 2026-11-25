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

| 対象の check-repo.py | コマンド | 結果 |
| --- | --- | --- |
| 変更前（main） | `python3 -B test-check-repo.py`（変更後のテストを、main の `check-repo.py` と同じディレクトリに写して実行） | 117 件のうち、足した 7 件だけが FAIL（検査がないので終了コード 0 になる）。ほかの 110 件は OK |
| 変更後 | `python3 -B .github/scripts/test-check-repo.py` | 117 件 OK（54.7 秒） |

<a name="local-checks"></a>

## 3. 手元の検査

| コマンド | 終了コード | 結果 |
| --- | --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 0 | 15 項目すべて PASS（`tool-versions` を含む） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 0 | 指摘なし |
| `actionlint` | 0 | 指摘なし |
| `zizmor --offline .`（キャッシュは一時ディレクトリ） | 0 | `No findings to report.` |
| `check-repo.py <写し>`（`ci.yaml` の gitleaks を 8.30.0、shellcheck を v0.10.0 にした写し。手元の本物のツールで実行） | 1 | `FAIL tool-versions`。shellcheck と gitleaks の 2 行が、手元の版・CI の版・上げるキーを出した。ほかの 2 つは出ない |

<a name="test-speed"></a>

## 4. テストの所要時間

偽のツールを最初はテストごとに作っていて、テスト 3 件が 0.9 秒から 2.6 秒になった（117 件では 65 秒から 109 秒）。CPU 時間はほぼ変わらず、待ち時間が増えていた。

- 事実: 新しく作った sh スクリプトを直接起動すると、初回は 0.11〜0.31 秒、2 回目以降は 0.02〜0.03 秒だった。`/bin/sh <スクリプト>` で起動すると、初回でも 0.02 秒だった（2026-11-25 に測った）。
- 推測: 初めて実行するファイルを macOS が調べる時間。確かめていない。
- 対応: 偽のツールはクラスで 1 回だけ作り、差し替えるテストだけ、そのツールだけを置いた別のディレクトリを PATH の先頭に足す。117 件で 54.7 秒になった。

<a name="ci"></a>

## 5. GitHub Actions

PR の CI の結果を、ここに書く。
