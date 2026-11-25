---
status: in-progress
created: 2026-11-25
---

# dotfiles の CI に zizmor を組み込む

関連: [GitHub Actions のセキュリティツールの評価](../20261125_gha-security-tools/research-gha-security-tools.md)（案とトレードオフは 7 章）、[CI の追加の計画書](../20261111_ci-checks/plan.md)

<a name="decision"></a>

## 1. 決めたこと

2026-11-25 に、評価の 7 章の案から始めるとユーザーが決めた。

| 項目 | 決定 |
| --- | --- |
| 版 | 1.33.1。手元の Homebrew と同じで、2026-11-22 に出た最新の版 |
| 取得 | 既存の Install のステップで、GitHub Releases の `zizmor-x86_64-unknown-linux-gnu.tar.gz` を取得し、sha256 を照合する（shellcheck・actionlint と同じ形） |
| 動作モード | `--offline`。将来ステップにトークンを渡しても、オンラインにならないようにする |
| 判定 | regular（既定のまま。`--persona` は付けない） |
| 出力 | `--format=github` |
| 対象 | リポジトリのルート（`.`） |

<a name="facts"></a>

## 2. 調べたこと（事実）

出典: zizmorcore/zizmor の v1.33.1 の `docs/usage.md`・`.github/workflows/release-binaries.yml`・`support/archive-release.sh`。

- sha256 `3e6a301c7a820a2501915f5a9de8c0486da82bdec7965f068477538a98743d43` は、GitHub API が返すリリースのアセットの `digest`（2026-11-25 に取得）。手元で tarball を取得して計算しようとしたが、Claude Code の auto mode が拒否したので計算していない。一致は CI の `sha256sum -c` が確かめる。
- tarball の中身は `zizmor` の 1 ファイルだけ。`support/archive-release.sh` が `tar -czf … -C <dir> zizmor` で作る。
- Linux 用のバイナリは ubuntu-22.04 でビルドしている。リリースには `actions/attest` で attestation を付けている。CI では attestation を検証しない。
- `--format=github` でも、指摘があれば終了コード 11〜14 で失敗する。11 以上を使わないのは `--no-exit-codes`、`--format=sarif`、`--fix` ですべて直したときだけ。
- 1 つのステップで注釈として表示されるのは 10 件まで。それより後の指摘はログにだけ出る。
- 入力を 1 つも集められないと、終了コード 3 で失敗する。
- `.` を渡すと、Git のルートとして入力を集める（v1.32.0 から）。今の対象は `.github/workflows/ci.yaml` だけ。Dependabot の設定や action を足すと、自動で対象に入る。

<a name="changes"></a>

## 3. 変更

`.github/workflows/ci.yaml` の `checks` ジョブだけを変える。

- `env` に `ZIZMOR_VERSION` と `ZIZMOR_SHA256` を足す。
- Install のステップで zizmor を取得・照合・展開する。ステップ名を `Install shellcheck, actionlint and zizmor` にする。
- actionlint の後に `zizmor --offline --format=github .` のステップを足す。

<a name="verification"></a>

## 4. 検証

<a name="verification-local"></a>

### 4.1 手元での実行

2026-11-25 に、Claude Code の sandbox の中で実行した。zizmor は 1.33.1（Homebrew）。キャッシュは `--cache-dir` で一時ディレクトリにした。

| コマンド | 対象 | 終了コード | 結果 |
| --- | --- | --- | --- |
| `actionlint` | 変更後 | 0 | 指摘なし |
| `zizmor --offline --format=github .` | 変更後 | 0 | 注釈なし。集めた入力は `.github/workflows/ci.yaml` だけ |
| `zizmor --offline --pedantic .` | 変更後 | 0 | 指摘なし（`No findings to report.`） |
| `zizmor --offline --format=github <dir>` | 危ない書き方の例（下記） | 14 | `::error` 3 件（dangerous-triggers・template-injection・unpinned-uses）、`::warning` 2 件（artipacked・excessive-permissions） |
| `python3 -B .github/scripts/check-repo.py`（3.15.2） | 変更後（この文書を含む） | 0 | 13 項目すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 変更後 | 0 | 93 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 変更後 | 0 | 指摘なし |

危ない書き方の例は、一時ディレクトリに置いたワークフローで、`pull_request_target`、SHA で固定しない `actions/checkout@v4`、`run` の中の `${{ github.event.pull_request.title }}` を含む。

<a name="verification-online"></a>

### 4.2 オンラインの監査

2026-11-25 に、ユーザーが通常のターミナルで `GH_TOKEN="$(gh auth token)" zizmor .github/workflows/ci.yaml` を実行し、指摘は 0 件だった。対象は変更前の `ci.yaml`。評価の 6 章では「未実施」のままになっている（`status: done` なので書き換えない）。

- 推測: この変更は `uses:` を増やしていないので、オンラインの 4 つの監査（impostor-commit・known-vulnerable-actions・ref-confusion・stale-action-refs）の結果は変わらない。変更後には実行していない。

<a name="verification-ci"></a>

### 4.3 GitHub Actions

PR の CI の結果を書く。

<a name="tradeoffs"></a>

## 5. 残るトレードオフ

- 版を上げるたびに、版と sha256 を手で更新する。zizmor はリリースの間隔が短く、Homebrew の版が先に上がるので、手元と CI の版がずれることがある。
- 版を上げると、増えた監査で CI が落ちることがある。
- オンラインでしか動かない 4 つの監査は、CI では動かない。要るときは、通常のターミナルで手元から実行する。
