---
status: in-review
created: 2026-11-25
---

# check-repo.py で秘密情報の中身を検査する（gitleaks）

<a name="related"></a>

## 関連

- 検査スクリプト: [.github/scripts/check-repo.py](../../../.github/scripts/check-repo.py)
- CI: [.github/workflows/ci.yaml](../../../.github/workflows/ci.yaml)

<a name="intent"></a>

## 目的

公開リポジトリなのに、`check-repo.py` の `secret-files` は `aws/config`・`aws/credentials` が追跡されていないかだけを見ていて、ファイルの中身（トークン・鍵など）は見ていない。gitleaks で中身を検査し、push する前に手元で止められるようにする。

<a name="goals"></a>

## 目標と非目標

- 目標: `check-repo.py` の対象と同じファイル（git が追跡しているファイルと、無視されていない未追跡のファイル）の今の中身を gitleaks で検査し、見つかれば FAIL にする。手元と CI の両方で動く。
- 非目標: 過去の履歴の検査（ユーザーの判断。一度きりの棚卸しもしない）。`cc-safe-push` での強制。GitHub の push protection の設定。
- 失敗とみなすこと: 見つかった値が CI のログ（公開）や手元の出力に出ること。gitleaks が動かないのに PASS になること。

<a name="approaches"></a>

## 方式の比較

| 案 | 内容 | 判断 |
| --- | --- | --- |
| A | `check-repo.py` に検査を足す。手元の push 前と CI の両方で動く | 採用（ユーザーが選択。履歴は調べない） |
| B | A に加えて `cc-safe-push` でも push 前に調べる | 不採用。root 所有のラッパーの再インストールが要り、人間の push には効かない。必要になったら別の作業にする |
| C | CI だけで調べる | 不採用。CI は push の後に動くので、見つかった時点で公開済み |

全履歴を毎回調べる案は、gitleaks の分で 2〜5 秒かかる見込み（推測。今の `check-repo.py` 全体は 0.25 秒、全履歴の差分は 6.9 MB で、生成に 0.94 秒かかった）で、ユーザーが不要と判断した。

<a name="design"></a>

## 設計

1. `check-repo.py` に検査 `secret-content` を足す（`secret-files` の次）。
2. `repo_files()` のうち通常のファイルだけを一時ディレクトリに写し、そこに `gitleaks dir` をかける。symlink は写さない（公開されるのはリンク先の中身ではなくリンクの文字列なので）。
   - 理由（v8.30.1 の `cmd/directory.go`・`sources/files.go` で確認した事実）: `gitleaks dir` は 1 つのパスを受け取って `filepath.WalkDir` で全部をたどり、`.gitignore` を見ない。リポジトリのルートにかけると、`.git` と無視しているファイル（`aws/credentials` など）まで読む。読めないファイルは警告を出して飛ばす（失敗にならない）ので、sandbox の `denyRead` に当たったファイルが黙って抜ける。写す処理は Python が行うので、読めなければ例外で FAIL になる。
3. 呼び出しは、写した先を cwd にして `gitleaks dir . --no-banner --redact --report-format json --report-path <別の一時ファイル> --exit-code 42`。
   - 写した先の絶対パスを渡すと、allowlist の `paths` が絶対パスに当たり、`(?:^|/)tmp/` のような一見狭い除外で全ファイルが外れる（レビューで分かった。CI の一時ディレクトリは `/tmp`）。`.` を渡すと、`paths` はリポジトリからの相対パスに当たる。
   - 終了コード 1 は「見つかった」と「エラー」の両方に使われ、2 は Go の panic と重なるので、見つかったときを 42 に分ける。0 と 42 以外は FAIL（fail closed）。
   - 設定は、リポジトリに `.gitleaks.toml` があればそれを `--config` で渡し、なければ gitleaks の既定の設定を使う。`--config` がないと、gitleaks は設定を名前（`.gitleaks`）で探し、`.gitleaks.json` などを `.gitleaks.toml` より先に読む（実測）。環境変数 `GITLEAKS_CONFIG`・`GITLEAKS_CONFIG_TOML` は子プロセスに渡さない（手元の環境で設定が差し替わらないように）。
   - ログの色は `--no-color` では消えない（設定の読み込みのログに効かない）ので、子プロセスに `NO_COLOR=1` を渡す。
   - `.gitleaksignore` は使わない。ルートの `.gitleaksignore` を写さないので、gitleaks が読む場所（cwd と対象のルート。どちらも写した先）にない。
4. 出力は JSON の報告から `File`（リポジトリからの相対パス）・`StartLine`・`RuleID` だけを取り、`<path>:<line>: <rule>` の形で出す。`Secret`・`Match` は出さない。`--redact` は gitleaks 自身のログへの備えとして併用する。
5. gitleaks が PATH にないときは FAIL（`main()` の「検査できないときは成功扱いにしない」と同じ）。
6. 誤検知は、1 行ずつなら行末の `gitleaks:allow` コメントで、ファイル単位でまとまるなら `.gitleaks.toml`（既定のルールを継承し、パスを allowlist に入れる。`^fixtures/` のようにリポジトリからの相対パスで書く）で外す。どちらも sandbox から書けるが、PR の差分に出るのでレビューで見る。

<a name="install"></a>

### 導入

- 手元: `bin/.Brewfile` に `brew "gitleaks"` を足す（shellcheck・actionlint と同じ）。入れるまで、手元の `check-repo.py` は `secret-content` で FAIL になる。
- CI: `checks` ジョブで、shellcheck・actionlint と同じく版（Homebrew の今の版の 8.30.1）とチェックサムで固定してダウンロードする。チェックサムはリリースの checksums ファイルから取る。

<a name="tests"></a>

### テスト

`test-check-repo.py` の一時リポジトリに、次を足す。テストのファイル自身が検出されないよう、偽の秘密は文字列の連結で組み立てる（`local-paths` のテストと同じ）。

- 追跡しているファイルの秘密 → FAIL し、パスと行が出て、値は出ない。
- 未追跡で無視されていないファイルの秘密 → FAIL。
- 無視されているファイルの秘密 → PASS。
- `gitleaks:allow` の付いた行 → PASS。
- PATH に gitleaks がない → FAIL。
- レビューで足したもの: 環境変数 `GITLEAKS_CONFIG_TOML` を無視する、allowlist が相対パスに当たる（`^fixtures/` が効き、`(?:^|/)src/` では全体が外れない）、`.gitleaks.json` が設定を上書きしない、壊れた設定で `error: gitleaks exited with 1` になり色の制御文字が出ない、「見つかった」の終了コードなのに報告が空なら FAIL。

`test_clean_fixture_passes` を含めて、テストの実行に gitleaks が要るようになる。

<a name="left-to-builder"></a>

## 実装者に任せること

- 最初に、今のリポジトリに検査をかけて誤検知を数え、上の 6 の方針で外す。件数とルールを作業記録に残す（値は書かない）。
- 一時ディレクトリの作り方、gitleaks のタイムアウトの値。
- ルートの `CLAUDE.md` の「規約」に、`check-repo.py` が gitleaks を要することを 1 文足す。

<a name="residual-risks"></a>

## 残るリスク（受け入れる）

- 履歴は調べないので、まだ push していないブランチで秘密を入れてから消した場合、今のファイルの検査は通るが、push でそのコミットが公開される。
- 手元での実行は習慣に頼る。CI で見つかったときは公開済みなので、値を失効させる。
- 調べるのは作業ツリーの中身で、push で公開される HEAD や index とずれうる。秘密をコミットした後に作業ツリーだけから消した（削除は未コミット）場合や、`git add` の後に作業ツリーだけ直した場合、手元の検査は通る（レビューで分かった。ユーザーの判断で受け入れた。`local-paths` も作業ツリーだけを見ている）。
- 判定はパターンによるので、形式のない秘密（パスワードなど）は抜けうる。
- gitleaks の既定の設定が除外する種類のファイル（`.svg`・`.pdf`・ロックファイル・`vendor/`・`node_modules/` など）と、`.gitleaks.toml` 自体の中身は調べない。今のリポジトリに前者は追跡されていない。
- GitHub の push protection が有効かは、読み取り専用トークンでは確かめられなかった（403）。

<a name="verification"></a>

## 確かめ方

- `python3 -B .github/scripts/check-repo.py` と `python3 -B .github/scripts/test-check-repo.py` が通る。
- `actionlint` と shellcheck（CLAUDE.md の規約のコマンド）が通る。
- PR の CI が通る。
- 秘密情報の扱いに触れるので、`/review` の後に `/security-review` をかけ、Codex のレビューを提案する。
