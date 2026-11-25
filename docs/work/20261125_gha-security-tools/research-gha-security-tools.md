---
status: done
created: 2026-11-25
---

# GitHub Actions のセキュリティツールの評価（zizmor と pinact）

GitHub Actions のワークフローを点検するツールとして、zizmor と pinact を手元に入れるかを調べた。2026-11-25 にユーザーと方針を決め、zizmor だけを `bin/.Brewfile` に足した。dotfiles の CI に zizmor を組み込むかは決めていない。

関連: [CI の追加の計画書](../20261111_ci-checks/plan.md)（SHA 固定・`persist-credentials`・`permissions` は 56〜57 行、Dependabot を対象外にしたのは 36 行）

<a name="purpose"></a>

## 1. 目的

- 業務リポジトリのワークフロー（デプロイ用の Actions、本番の Environment）を、手元で静的に点検できるようにする。
- action の固定（SHA と版コメント）を保つための道具が要るかを決める。
- dotfiles の CI の今の設定に、見落としがないかを確かめる。

<a name="decision"></a>

## 2. 決めたこと

| 項目 | 決定 |
| --- | --- |
| zizmor | 入れる。`bin/.Brewfile` に足す |
| pinact | 入れない。Brewfile にも足さない（理由は [4.2](#why-not-pinact)、もう一度検討する条件は [4.3](#pinact-revisit)） |
| dotfiles の CI への zizmor の組み込み | まだ決めていない。この作業ではしない（[7 章](#open-questions)） |

<a name="facts"></a>

## 3. 調査で分かったこと（事実）

<a name="facts-dotfiles-ci"></a>

### 3.1 dotfiles の CI

- `.github/workflows/ci.yaml` は手で安全側に設定してある。action は SHA と版コメントで固定し、`persist-credentials: false`、`permissions: contents: read` にしている。[計画書](../20261111_ci-checks/plan.md)の 56〜57 行で決めた。
- Dependabot は、同じ計画書の 36 行で対象外にした。
- 使っている action は `actions/checkout` だけ（2 か所）。固定している `3d3c42e5aac5ba805825da76410c181273ba90b1` は、最新リリース v7.0.1 のタグと一致する（2026-11-25 に `gh api` で照合）。
- `check-repo.py` はワークフローを検査しない。actionlint は、SHA 固定・`persist-credentials`・`permissions` の広さを見ない。

<a name="facts-homebrew"></a>

### 3.2 Homebrew

- homebrew/core に、zizmor 1.33.1 と pinact 5.0.2 がある（2026-11-25 時点）。

<a name="facts-lockfile"></a>

### 3.3 GitHub Actions の workflow lockfile

出典: docs.github.com の `actions/concepts/security/workflow-dependency-lockfiles` と `actions/how-tos/secure-your-work/lock-workflow-dependencies`。

- 2026-10-28 に GA になった。
- ファイルは `.github/workflows/actions.lock` で、`gh actions-lock` 拡張で作る。
- Free プランでも使える。github/docs の `data/features/actions-workflow-lockfiles.yml` が `fpt: '*'`、`ghec: '*'`。
- lockfile に載せたワークフローでは SHA 固定は不要、と GitHub は書いている。間接的に使われる action まで固定し、Dependabot が lockfile も更新する。
- reusable workflow の呼び出し、composite action の定義（`action.yml`）、Docker イメージは固定しない。

<a name="facts-zizmor"></a>

### 3.4 zizmor

出典: github.com/zizmorcore/zizmor の `docs/usage.md`・`docs/audits.md`・`docs/release-notes.md`。

- 既定はオフラインで動く。`GH_TOKEN`・`GITHUB_TOKEN`・`ZIZMOR_GITHUB_TOKEN` があるとオンラインになる。オンラインでしか動かない監査は impostor-commit・known-vulnerable-actions・ref-confusion・stale-action-refs の 4 つ。
- `unpinned-uses` は v1.20.0 から、すべての action に SHA 固定を求める。`ref-version-mismatch` は版コメントと SHA の食い違いを見る。
- キャッシュの既定の置き場所は `~/.cache/zizmor`。`--cache-dir` で変えられる。
- Linux 用のバイナリ（`zizmor-x86_64-unknown-linux-gnu.tar.gz`）が GitHub Releases にある。CI に入れるなら、shellcheck・actionlint と同じく版と sha256 を固定して取得できる。
- リリースの間隔が短い。2026-10-15 の 1.31.0 から 2026-11-22 の 1.33.1 まで出ており、1.33.0 で監査 dangerous-checkout が増えた。
- lockfile への対応は 1.32.0 からで、まだ実験的。

<a name="facts-pinact"></a>

### 3.5 pinact

出典: github.com/suzuki-shunsuke/pinact の README と `docs/workflow_lockfile.md`。

- できることは、SHA への書き換え、版コメントの検証、版の更新（`--update`。公開から一定日数たった版だけを選べる）。
- タグを SHA に変えるのに GitHub API を使う（トークンは `GITHUB_TOKEN`・キーリング・ghtkn から読む）。API を使わない検査は `--no-api`。
- v5 は lockfile を認識する。lockfile に載った action には触らず、reusable workflow と `action.yml` だけを固定する。

<a name="judgement"></a>

## 4. 判断

<a name="why-zizmor"></a>

### 4.1 zizmor を入れる理由

- 業務リポジトリ（デプロイ用の Actions、本番の Environment）で、secrets-outside-env・excessive-permissions・dangerous-triggers・template-injection などを点検できる。
- 静的解析だけで、対象のコードは実行しない。

<a name="why-not-pinact"></a>

### 4.2 pinact を入れない理由

- dotfiles には直す対象がない（action は 1 つで、固定済みで最新）。
- 固定漏れの検出は zizmor（unpinned-uses・ref-version-mismatch）で足りる。
- 業務リポジトリの固定の方式は、先に lockfile と Dependabot の組み合わせを検討する。Dependabot の更新待ち期間（cooldown）の設定漏れは、zizmor の dependabot-cooldown が見る。

<a name="pinact-revisit"></a>

### 4.3 pinact をもう一度検討する条件

- 業務リポジトリで reusable workflow や composite action が多く、lockfile で覆えない部分を手で固定するとき。
- lockfile を使わずに、たくさんの action をまとめて固定・更新したいとき。

<a name="assumptions"></a>

## 5. 推測

- lockfile は GA から 4 週間で、zizmor の対応もまだ実験的。業務リポジトリでは、まず 1 リポジトリで試してから広げる。

<a name="local-run"></a>

## 6. 手元での zizmor の実行結果

2026-11-25 に、Claude Code の sandbox の中で実行した。zizmor は 1.33.1（Homebrew の bottle `zizmor--1.33.1.arm64_tahoe`）。対象は `.github/workflows/ci.yaml`（main の c409485 と同じ中身）。

| 判定 | コマンド | 終了コード | 結果 |
| --- | --- | --- | --- |
| regular（オフライン） | `zizmor --offline --cache-dir "$TMPDIR/zizmor-cache" .github/workflows/ci.yaml` | 0 | 指摘なし（`No findings to report.`） |
| pedantic（オフライン） | `zizmor --offline --pedantic --cache-dir "$TMPDIR/zizmor-cache" .github/workflows/ci.yaml` | 0 | 指摘なし（`No findings to report.`） |
| オンラインの監査 | `GH_TOKEN="$(gh auth token)" zizmor --cache-dir "$TMPDIR/zizmor-cache" .github/workflows/ci.yaml` | — | 未実施 |

- pedantic で undocumented-permissions が出る、という前のセッションの推測は外れた。`ci.yaml` の `permissions` は `contents: read` だけで、説明のコメントはない。この書き方で指摘が出ない理由は確かめていない（`docs/audits.md` を読み直していない）。
- オンラインの監査は、実行しようとしたコマンドを Claude Code の権限が拒否したので、実行していない。拒否の後に別の方法は試していない。
  - 引き継ぎの案は `--gh-token "$(gh auth token)"` だったが、トークンをコマンドライン引数に出さないために、環境変数 `GH_TOKEN` で渡す形にした。
  - impostor-commit・known-vulnerable-actions・ref-confusion・stale-action-refs の 4 つは、まだ見ていない。

<a name="open-questions"></a>

## 7. 決まっていないこと

dotfiles の CI に zizmor を組み込むか。組み込むなら別の作業（別の PR）にする。

- 案: 既存の Install のステップに、zizmor の版と sha256 を足す。`--offline` と regular の判定で実行し、`--format=github` で出力する。
- トレードオフ:
  - 管理する版と sha256 が 1 組増える。
  - zizmor の版を上げると、増えた監査で CI が落ちることがある。
  - `--offline` にすると、オンラインでしか動かない 4 つの監査は CI でも動かない。
