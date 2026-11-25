---
status: in-progress
created: 2026-11-25
---

# 手元と CI の検査ツールの版のずれを check-repo.py で止める

関連: [gitleaks の検査の作業](../20261125_gitleaks-check/plan.md)、[zizmor を CI に組み込む作業](../20261125_zizmor-ci/plan.md#tradeoffs)（5 章「手元と CI の版がずれることがある」）

<a name="decision"></a>

## 1. 決めたこと

2026-11-25 に、ユーザーが次のように決めた。

| 項目 | 決定 |
| --- | --- |
| 方針 | ずれを検査で止める。`check-repo.py` に、PATH のツールの版と `ci.yaml` の版を比べる検査を足し、違えば FAIL にする。手元は Homebrew のまま使う |
| 対象 | shellcheck・actionlint・zizmor・gitleaks の 4 つ |

採らなかった案:

- mise で手元の版を固定する。`mise trust` のやり直しが要り、mise が sandbox の外で自動で入れる。shims が PATH で Homebrew より前にあるので、ほかのリポジトリでの挙動も確かめる必要がある。
- `ci.yaml` のコメントだけを直す。ずれに気づく仕組みが残らない。

<a name="facts"></a>

## 2. 調べたこと（事実）

- `.github/workflows/ci.yaml` の `checks` ジョブは、`env` の `<名前>_VERSION` と `<名前>_SHA256` で 4 つのツールの版を固定している。手元は `bin/.Brewfile` の Homebrew で、版を固定していない。
- `ci.yaml` の Install のステップのコメント「手元（Homebrew）と同じ版に固定し」は、CI の版を上げた時点でしか正しくない。`brew upgrade` で手元だけ上がっても、知らせる仕組みがない。
- 2026-11-25 の時点では、手元と CI の版は一致している。手元（Homebrew）の版のコマンドの出力は次のとおり。

| ツール | `ci.yaml` | コマンド | 出力 |
| --- | --- | --- | --- |
| shellcheck | `v0.11.0` | `shellcheck --version` | 4 行。2 行目が `version: 0.11.0` |
| actionlint | `1.7.12` | `actionlint --version` | 3 行。1 行目が `1.7.12`、3 行目が `built with go1.26.3 compiler for darwin/arm64` |
| zizmor | `1.33.1` | `zizmor --version` | `zizmor 1.33.1` |
| gitleaks | `8.30.1` | `gitleaks version` | `8.30.1` |

- CI で入れる Linux 用のリリースのバイナリの出力は、手元では確かめていない。PR の CI で確かめる（[4 章](#verification)）。

<a name="changes"></a>

## 3. 変更

### 3.1 `.github/scripts/check-repo.py`

`secret-content` の次に、検査 `tool-versions` を足す。

- `.github/workflows/ci.yaml` を読み、4 つの `<名前>_VERSION` の値を行の正規表現で取る（標準ライブラリに YAML の parser がないため）。ファイルがないか、キーがちょうど 1 回現れなければ FAIL にする。
- PATH のツールを `shutil.which` で探し、版のコマンド（gitleaks は `version`、ほかは `--version`）を実行する。出力の最初の `数字.数字.数字` を版とする。比べる前に、`ci.yaml` の値の先頭の `v` を外す。
- 次のときは FAIL にする（検査できないときも成功扱いにしない）。メッセージにパスは出さない（CI のログは公開される）。
  - 見つからない: `<ツール> not found (install it with brew install <ツール>)`
  - 終了コードが 0 でないか、版を読めない: `cannot read the version of <ツール>`
  - 版が違う: `<ツール> <手元の版> on PATH, but .github/workflows/ci.yaml pins <CI の版> (update <名前>_VERSION and <名前>_SHA256 together)`
- 版のコマンドがタイムアウト（10 秒）したときは、既存の `main()` の例外の扱いで FAIL になる。

### 3.2 `.github/scripts/test-check-repo.py`

- 最小構成に、4 つの版だけを書いた `.github/workflows/ci.yaml` を足す。
- `check()` は既定で、2 章の出力をまねる偽のツールを置いたディレクトリを PATH の先頭に足す。手元に入っている版に結果が左右されないようにするため。偽の gitleaks は、`version` のときだけ版を出し、ほかの引数では本物の gitleaks に渡す（`secret-content` のテストは本物で動かす）。
- 足すテスト: 版が違うと FAIL / `ci.yaml` がないと FAIL / キーがないと FAIL / キーが 2 回あると FAIL / ツールがないと FAIL / 版を読めないと FAIL / 終了コードが 0 でないと FAIL。

### 3.3 `.github/workflows/ci.yaml`

Install のステップのコメントを、事実に合わせて次のように直す。

```yaml
# 版を固定し、チェックサムを確かめてから使う。手元（Homebrew）の版と違うと check-repo.py の tool-versions が失敗するので、
# 手元が上がったら、版と SHA256 を一緒に上げる。
```

`CLAUDE.md` は変えない。失敗したときに何をすればよいかは、メッセージに出す。

<a name="verification"></a>

## 4. 検証

- `test-check-repo.py` に足すテストが、実装の前に失敗することを確かめる。実装の後に、すべて通ることを確かめる。
- `python3 -B .github/scripts/check-repo.py` が手元で `PASS tool-versions` になる。手元の版を変えずに `ci.yaml` の版だけを変えた写しで FAIL になることを、テストで確かめる。
- CLAUDE.md の規約の検査（`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・`zizmor --offline .`）。
- PR の CI の `Repository checks` で `PASS tool-versions` になる。Linux のリリースのバイナリでも版を読めることを、ここで確かめる。

<a name="tradeoffs"></a>

## 5. 残るトレードオフ

- `brew upgrade` で手元の版が上がると、CI の版と SHA256 を上げるまで、手元の `check-repo.py` が FAIL になり、関係のない作業の検査も通らない。zizmor はリリースの間隔が短いので、止まる回数が多い。
- 新しい版で検査の結果が変わると（zizmor の監査が増えるなど）、直すまで CI の版も上げられない。手元を前の版に戻す手段は、Homebrew にはない。
- 手元の版を固定するわけではない。上がったことに気づけるだけ。
