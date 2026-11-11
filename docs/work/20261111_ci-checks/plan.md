---
status: done
created: 2026-11-11
---

# CI の追加: フック回帰テストとリポジトリの検査 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PR と main への push で、Claude Code の安全装置の回帰テストと、公開リポジトリとして守る不変条件・静的解析を GitHub Actions で実行する。

**Architecture:** ワークフロー `ci.yaml` に 2 ジョブを置く。`hook-tests`（macos-latest）は既存の回帰テスト 6 本を本番と同じ `/bin/bash`・`/usr/bin/python3` で実行する。`checks`（ubuntu-latest）は新設の `check-repo.py`（標準ライブラリだけ）とそのテスト、shellcheck、actionlint を実行する。既存の `main.yaml` は削除する。

**Tech Stack:** GitHub Actions、bash、Python 3.11 以上の標準ライブラリ（unittest、json、tomllib）、shellcheck v0.11.0、actionlint v1.7.12

**Spec:** 独立した仕様書はない。会話での提案と決定事項を [背景と決定事項](#background) に記す。

根拠の表記: 【実測】このセッションで確認 / 【推測】 / 【未確認】

関連: [20261109_cc-safe-pr](../20261109_cc-safe-pr/design.md)、[20261109_gh-token-isolation](../20261109_gh-token-isolation/plan.md)

<a name="background"></a>

## 背景と決定事項

- 既存の `.github/workflows/main.yaml` は `./init.command`（xcode-select、Homebrew、chsh）を流すだけで、回帰テストを実行していない。API 上は `active` だが、実行履歴は 0 件【実測】。
- 回帰テスト 6 本は手元で全件成功し、合計約 70 秒【実測】。
- 本番のインタプリタは `/bin/bash` 3.2.57 と `/usr/bin/python3` 3.9.6【実測】。
- `shellcheck -S warning`（v0.11.0）の警告は SC2046 の 9 件だけで、フックは 0 件【実測】。
- 追跡ファイルの `/Users/<名前>` は、プレースホルダーの 2 件（`codex/README.md:319`、`claude/hooks/tests/test-cc-safe-push.py:269`）だけ【実測】。
- Markdown の内部リンク 122 件は、試作した検査ですべて解決できた【実測】。
- **ユーザーの決定（2026-11-11）:** 提案の P1 と P2 を入れる。`main.yaml` は削除する。

**完了の定義:** PR 上で `checks` と `hook-tests` が成功し、`hook-tests` のログで `/bin/bash` 3.2 と `/usr/bin/python3` 3.9 を使ったことを確認できる。`check-repo.py` の各検査は、違反を入れたフィクスチャで失敗することをテストで確認している。

**対象外:** link スクリプトの冪等性テスト、`codex/sync.py` のテスト、zsh の構文チェック、Dependabot による Actions の更新、ブランチ保護の必須チェックの設定。

<a name="prerequisites"></a>

## 前提（ユーザー作業）

リポジトリで Actions が有効であること。実行履歴が 0 件なので、無効の可能性がある【推測】。確認には管理者権限が要り、sandbox 内の読み取り専用トークンでは 403 になる【実測】。

```sh
env -u GH_TOKEN gh api repos/kado-ta/dotfiles/actions/permissions
```

`enabled` が `true` で、`allowed_actions` が `all`（または `selected` で GitHub 製の Actions を許可）であること。

<a name="global-constraints"></a>

## Global Constraints

- `check-repo.py` は Python 3.11 以上の標準ライブラリだけを使う（`tomllib` のため）。依存は追加しない。
- 回帰テストは macos-latest で、`/bin/bash` と `/usr/bin/python3 -B` を明示して実行する。PATH 上の `bash` / `python3` は使わない。
- Actions はフル SHA で固定する: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`（v7.0.1）。`persist-credentials: false` にする。
- ワークフローの `permissions` は `contents: read` だけにする。
- shellcheck は v0.11.0 に固定する（`shellcheck-v0.11.0.linux.x86_64.tar.xz`、sha256 `8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198`）。手元の Homebrew 版と同じ版。
- actionlint は v1.7.12 に固定する（`actionlint_1.7.12_linux_amd64.tar.gz`、sha256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`）。
- 追跡ファイル（検査スクリプト、テスト、試験記録を含む）に実在のユーザー名と、それを含む絶対パスを書かない。テストで違反パスが必要なときは、文字列の連結で組み立てる。
- スクリプトのファイル名は kebab-case にする。
- `claude/hooks/`、`claude/bin/`、`claude/settings.json` は変更しない。
- 1 コミット = 1 論理変更。Conventional Commits で、タイトルは英語、本文は日本語。末尾に `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` を付ける。

<a name="file-structure"></a>

## ファイル構成

| ファイル | 変更 | 責務 |
| --- | --- | --- |
| `.github/scripts/check-repo.py` | 新規 | 不変条件・構文・Markdown の検査。違反があれば終了コード 1 |
| `.github/scripts/test-check-repo.py` | 新規 | 一時リポジトリのフィクスチャで、各検査の成功と失敗を確かめる unittest |
| `.github/workflows/ci.yaml` | 新規 | `checks`（ubuntu）と `hook-tests`（macOS）の 2 ジョブ |
| `.github/workflows/main.yaml` | 削除 | |
| `aws/link.sh` ほか計 9 ファイル | 修正 | shellcheck SC2046 の解消（Task 1） |
| `CLAUDE.md`、`claude/README.md` | 修正 | CI と検査スクリプトの説明 |
| `docs/work/20261111_ci-checks/plan.md`、`test-report.md` | 新規 | 本書と試験記録 |

## Review Focus

1. 見出しのスラッグが GitHub と食い違う（全角括弧・インラインコード・スラッシュを含む見出し、同名の見出し）。GitHub で正しく飛べるリンクは成功すること。→ Task 2 `test_slug_matches_github`
2. パーセントエンコードしたリンク（`%20` など）。存在するファイルを指すなら成功すること。→ Task 2 `test_percent_encoded_link`
3. `claude/settings.json` がない・読めない。検査を成功扱いにせず失敗すること（fail closed）。→ Task 2 `test_missing_settings_fails`
4. macOS ランナーの `/usr/bin/python3` が 3.9 でない、または `jq` がない。→ 自動テストはない。Task 3 の「Show interpreters」ステップでログに残し、Task 4 で確認する。
5. `claude/hooks/tests/test-ask-gh-pr-write.sh:147` の「10 秒未満」の時間計測が、遅いランナーで落ちる。→ 自動テストはない。Task 4 で 1 回目の結果を確認する。落ちても本計画では閾値を変えず、別の作業として扱う。

---

### Task 1: shellcheck の既存警告を解消する

**Files:**

- Modify: `aws/link.sh:3`、`bin/link.sh:8`、`biome/setup.sh:10`、`codex/setup.sh:10`、`config/link.sh:11`、`ghostty/link.sh:8`、`init.command:4`、`mise/setup.sh:11`、`vscode/setup.sh:8`

- [ ] **Step 1: 警告を確認する**

  Run: `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning -f gcc`

  Expected: 上の 9 箇所の SC2046 だけが出る（計 9 件）。

- [ ] **Step 2: 引用符を付ける**

  `$(cd $(dirname $0) && pwd)` を `$(cd "$(dirname "$0")" && pwd)` にする。`init.command:4` は `"$(basename $(pwd))"` を `"$(basename "$(pwd)")"` にする。ほかの行は変えない。

- [ ] **Step 3: 警告がなくなったことを確認する**

  Run: Step 1 のコマンドと、9 ファイルそれぞれへの `bash -n`

  Expected: shellcheck は出力なし・終了コード 0。`bash -n` はすべて成功。

- [ ] **Step 4: コミットする**

  `fix: quote command substitutions flagged by shellcheck`。本文: パスに空白を含むと分割される。CI で shellcheck を有効にする前に解消する。

### Task 2: リポジトリの検査スクリプト

**Files:**

- Create: `.github/scripts/check-repo.py`
- Test: `.github/scripts/test-check-repo.py`

**Interfaces:**

- Produces: `python3 -B .github/scripts/check-repo.py [ROOT]`。ROOT を省略したときは、スクリプトから見たリポジトリのルート（`Path(__file__).resolve().parents[2]`）を対象にする。
  - 検査ごとに `PASS <name>` か `FAIL <name>` を出し、失敗ならエラーを 1 行ずつ `  <file>:<line>: <message>`（行がないものは `  <file>: <message>`）で続ける。
  - 1 件でも失敗すれば終了コード 1、すべて成功なら 0。
- 検査関数はすべて `def check_<name>(root: Path) -> list[str]`（エラーメッセージのリスト）。入口は `def main(argv: list[str]) -> int`。
- 追跡ファイルの一覧は `git -C ROOT ls-files -z` で得る（index を読むので、テストは `git add` だけでよい）。`git` が失敗したら例外にして終了コード 1 にする。

| name | 失敗する条件 | 定数 |
| --- | --- | --- |
| `local-paths` | 追跡中のテキストファイルに `/(Users\|home)/<名前>`（名前は `[A-Za-z0-9._-]+`）があり、名前がプレースホルダーでない。UTF-8 で読めないファイルは飛ばす | `PLACEHOLDER_USERS = {"example", "some"}` |
| `secret-files` | 次のファイルを追跡している | `FORBIDDEN_FILES = ("aws/config", "aws/credentials")` |
| `hook-scripts` | `claude/settings.json` を読めない。または、`hooks.<event>[].hooks[].command` と `statusLine.command` のうち `.claude/` を含むものを `shlex.split` し、先頭（インタプリタなら 2 番目）のトークンが `~/.claude/` か `$HOME/.claude/` で始まり、その残りが `hooks/` か `scripts/` で始まるものについて、`claude/<残り>` を追跡していない。先頭がインタプリタでない（直接実行する）のに、git のモードが `100755` でない | `INTERPRETERS = {"bash", "/bin/bash", "sh", "/bin/sh"}` |
| `push-permissions` | `claude/settings.json` を読めない。`permissions.allow` のうち `cc-safe` を含む項目が、`WRAPPER_COMMANDS` を `Bash(...)` で囲んだ 3 つと一致しない。`sandbox.excludedCommands` が `WRAPPER_COMMANDS` と一致しない（順不同）。`permissions.deny` が `DENY_PUSH` の一部を含まない | `WRAPPER_COMMANDS = ("/usr/local/libexec/claude-push/cc-safe-push", "/usr/local/libexec/claude-push/cc-safe-pr create", "/usr/local/libexec/claude-push/cc-safe-pr edit")`、`DENY_PUSH = ("Bash(git push)", "Bash(git push *)", "Bash(git -C * push *)", "Bash(git -c * push *)")` |
| `syntax` | 追跡中の `*.json`（`JSONC_FILES` を除く）を `json` で、`*.toml` を `tomllib` で読めない | `JSONC_FILES = {"vscode/settings.json", "vscode/keybindings.json"}` |
| `markdown-names` | `docs/` 以外の `*.md` で、拡張子を除いた名前が `^[A-Z_]+$` に一致しない | |
| `markdown-links` | 下の規則 | |

`push-permissions` を完全一致にする理由: `excludedCommands` と cc-safe の allow は sandbox と権限の境界なので、広げるときは検査の定数も一緒に変える（2 か所の変更をレビューで見る）。

`markdown-links` の規則:

- 対象は追跡中の `*.md`。フェンス（```` ``` ```` か `~~~` で始まる行）の中と、インラインコードの中は無視する。
- `](target)` の target のうち、スキーム付き（`^[a-z][a-z0-9+.-]*:`）は対象外。`#` で path と fragment に分ける。path は `urllib.parse.unquote` してから、リンク元のディレクトリを基準に解決する（空ならリンク元のファイル自身）。存在しなければエラー。
- fragment があり、リンク先が `.md` なら、そのファイルのアンカーに含まれること。アンカーは `<a name="…">` / `<a id="…">` の値と、見出しのスラッグ。
- スラッグ（GitHub の規則）: 見出しのテキストの `[text](url)` を `text` に置き換え、小文字にし、`[^\w\- ]` を削除し、空白を 1 文字ずつ `-` に置き換える。同じスラッグの 2 回目以降には `-1`、`-2` を付ける。
- 同じファイル内で `<a name>` / `<a id>` の値が重複したらエラー。

- [ ] **Step 1: テストを書く**

  `setUp` で一時ディレクトリに `git init` し、すべての検査を通る最小構成を `git add` する。ヘルパーは `write(rel: str, text: str, mode: int = 0o644)`（書いて `git add`）と `run() -> tuple[int, str]`（`[sys.executable, "-B", SCRIPT, root]` を `subprocess` で実行し、終了コードと stdout を返す）。

  最小構成:

  - `claude/settings.json`: `hooks.PreToolUse[0].hooks` に `~/.claude/hooks/direct.sh` と `/bin/bash ~/.claude/hooks/viabash.sh`。`statusLine.command` に `~/.claude/scripts/status.sh`。`permissions.allow` に `WRAPPER_COMMANDS` の 3 つの `Bash(...)`、`permissions.deny` に `DENY_PUSH`、`sandbox.excludedCommands` に `WRAPPER_COMMANDS`
  - `claude/hooks/direct.sh`（0o755）、`claude/hooks/viabash.sh`（0o644）、`claude/scripts/status.sh`（0o755）
  - `README.md`: 見出し `## Foo Bar` と、リンク `[x](#foo-bar)`

  | テスト | フィクスチャへの変更 | 期待 |
  | --- | --- | --- |
  | `test_clean_fixture_passes` | なし | 0。出力に `FAIL` がない |
  | `test_real_user_path_fails` | `notes.txt` に `"/Users/" + "alice/x"` | 1。`FAIL local-paths` と `notes.txt:1:` |
  | `test_placeholder_user_path_passes` | `notes.txt` に `/Users/example/x` と `/Users/some one/x` | 0 |
  | `test_tracked_aws_credentials_fails` | `aws/credentials` を追加 | 1。`FAIL secret-files` |
  | `test_direct_hook_without_exec_bit_fails` | `direct.sh` を 0o644 で書き直す | 1。`FAIL hook-scripts` と `claude/hooks/direct.sh` |
  | `test_missing_hook_fails` | `git rm --cached` で `viabash.sh` を外す | 1。`FAIL hook-scripts` |
  | `test_missing_settings_fails` | `git rm --cached` で `claude/settings.json` を外し、ファイルも消す | 1。`FAIL hook-scripts` と `FAIL push-permissions` |
  | `test_extra_excluded_command_fails` | `excludedCommands` に `git` を追加 | 1。`FAIL push-permissions` |
  | `test_broader_wrapper_allow_fails` | allow に `Bash(/usr/local/libexec/claude-push/cc-safe-pr *)` を追加 | 1。`FAIL push-permissions` |
  | `test_missing_push_deny_fails` | deny から `Bash(git -C * push *)` を削除 | 1。`FAIL push-permissions` |
  | `test_invalid_json_fails` | `x.json` に `{,}` | 1。`FAIL syntax` と `x.json` |
  | `test_invalid_toml_fails` | `x.toml` に `a =` | 1。`FAIL syntax` と `x.toml` |
  | `test_jsonc_file_skipped` | `vscode/settings.json` にコメント付きの JSON | 0 |
  | `test_lowercase_markdown_name_fails` | `notes.md` を追加 | 1。`FAIL markdown-names` |
  | `test_docs_markdown_name_passes` | `docs/work/x/plan.md` を追加 | 0 |
  | `test_missing_link_target_fails` | `README.md` に `[x](NOPE.md)` | 1。`FAIL markdown-links` と `README.md:` |
  | `test_missing_anchor_fails` | `README.md` に `[x](#nope)` | 1。`FAIL markdown-links` |
  | `test_link_in_code_ignored` | フェンスの中と、インラインコードの中に `[x](NOPE.md)` | 0 |
  | `test_explicit_anchor_passes` | `<a name="setup"></a>`、見出し `## セットアップ`、リンク `[x](#setup)` | 0 |
  | `test_duplicate_explicit_anchor_fails` | `<a name="setup"></a>` を 2 つ | 1。`FAIL markdown-links` |
  | `test_slug_matches_github` | 全角括弧の中にインラインコード `claude/` を含む見出し「Claude Code 設定（…）」とリンク `[x](#claude-code-設定claude)`。2 つ目の `## Foo Bar` とリンク `[y](#foo-bar-1)` | 0 |
  | `test_percent_encoded_link` | `docs/a b.md` を追加し、`README.md` に `[x](docs/a%20b.md)` | 0 |

- [ ] **Step 2: テストが失敗することを確認する**

  Run: `python3 -B .github/scripts/test-check-repo.py`

  Expected: `check-repo.py` がないため全件失敗する。

- [ ] **Step 3: `check-repo.py` を実装する**

  上の Interfaces と表のとおり。検査は表の順に実行し、1 つが失敗しても残りを実行する。

- [ ] **Step 4: テストと実リポジトリの検査が通ることを確認する**

  Run: `python3 -B .github/scripts/test-check-repo.py` と `python3 -B .github/scripts/check-repo.py`

  Expected: テストは全件 OK。実リポジトリは 7 件すべて `PASS`、終了コード 0。

- [ ] **Step 5: コミットする**

  `ci: add repository invariant checks`。本文に、各検査が防ぐもの（ユーザー名の露出、認証情報の追跡、フックの実行権限の欠落による fail-open、push の権限境界の拡大、設定ファイルの構文、Markdown の規約）を書く。

### Task 3: ワークフローを追加し、main.yaml を削除する

**Files:**

- Create: `.github/workflows/ci.yaml`
- Delete: `.github/workflows/main.yaml`
- Modify: `CLAUDE.md`（冒頭の「このリポジトリについて」と、「規約」の最初の項目）、`claude/README.md:36-45`

**Interfaces:**

- Consumes: Task 2 の `check-repo.py` の CLI。Task 1 で shellcheck の警告が 0 件になっていること。

- [ ] **Step 1: `ci.yaml` を書く**

  ```yaml
  name: CI

  on:
    pull_request:
    push:
      branches: [main]

  permissions:
    contents: read

  concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    checks:
      name: Repository checks
      runs-on: ubuntu-latest
      timeout-minutes: 5
      env:
        SHELLCHECK_VERSION: v0.11.0
        SHELLCHECK_SHA256: 8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198
        ACTIONLINT_VERSION: 1.7.12
        ACTIONLINT_SHA256: 8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false

        # 手元（Homebrew）と同じ版に固定し、チェックサムを確かめてから使う。
        - name: Install shellcheck and actionlint
          run: |
            bin="$RUNNER_TEMP/bin"
            mkdir -p "$bin"
            cd "$RUNNER_TEMP"
            curl -fsSLo shellcheck.tar.xz "https://github.com/koalaman/shellcheck/releases/download/${SHELLCHECK_VERSION}/shellcheck-${SHELLCHECK_VERSION}.linux.x86_64.tar.xz"
            echo "${SHELLCHECK_SHA256}  shellcheck.tar.xz" | sha256sum -c -
            tar -xJf shellcheck.tar.xz
            mv "shellcheck-${SHELLCHECK_VERSION}/shellcheck" "$bin/"
            curl -fsSLo actionlint.tar.gz "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
            echo "${ACTIONLINT_SHA256}  actionlint.tar.gz" | sha256sum -c -
            tar -xzf actionlint.tar.gz -C "$bin" actionlint
            echo "$bin" >> "$GITHUB_PATH"

        - name: Repository checks
          run: python3 -B .github/scripts/check-repo.py

        - name: Tests for repository checks
          run: python3 -B .github/scripts/test-check-repo.py

        # herdr-agent-state.sh は herdr が生成・上書きするので対象外。
        - name: shellcheck
          run: git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning

        - name: actionlint
          run: actionlint

    hook-tests:
      name: Hook regression tests
      runs-on: macos-latest
      timeout-minutes: 10
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            persist-credentials: false

        # 本番と同じインタプリタで動いたことをログに残す。
        - name: Show interpreters
          run: |
            /bin/bash --version | head -n 1
            /usr/bin/python3 --version
            command -v jq git

        # テストは "$BASH" でフックを起動するので、本番と同じ /bin/bash で実行する。
        - name: Shell hook tests
          run: |
            rc=0
            for t in claude/hooks/tests/test-*.sh; do
              echo "== $t"
              /bin/bash "$t" || rc=1
            done
            exit "$rc"

        - name: Python wrapper tests
          run: |
            rc=0
            for t in claude/hooks/tests/test-*.py; do
              echo "== $t"
              /usr/bin/python3 -B "$t" || rc=1
            done
            exit "$rc"
  ```

- [ ] **Step 2: actionlint を通す**

  Run: `actionlint`

  Expected: 出力なし・終了コード 0。

- [ ] **Step 3: `main.yaml` を削除する**

  Run: `git rm .github/workflows/main.yaml`

- [ ] **Step 4: ドキュメントを更新する**

  - `CLAUDE.md` 冒頭の「テストはフックの回帰テストのみ。」を、「テストはフックの回帰テストと、リポジトリの検査（`.github/scripts/check-repo.py`）。PR と main への push で GitHub Actions（`.github/workflows/ci.yaml`）が実行する。」にする。
  - `CLAUDE.md` の「規約」の最初の項目に、`python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、Task 1 Step 1 の shellcheck のコマンド（`-f gcc` なし）、`actionlint` を、手元での確認方法として追記する。
  - `claude/README.md` の回帰テストのコマンドの直後に、「PR と main への push では、GitHub Actions が macOS の `/bin/bash` と `/usr/bin/python3` で同じテストを実行する。」を追記する。

- [ ] **Step 5: CI と同じコマンドを手元ですべて実行する**

  Run:

  ```sh
  python3 -B .github/scripts/check-repo.py
  python3 -B .github/scripts/test-check-repo.py
  git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning
  actionlint
  for t in claude/hooks/tests/test-*.sh; do /bin/bash "$t" >/dev/null || echo "FAILED $t"; done
  for t in claude/hooks/tests/test-*.py; do /usr/bin/python3 -B "$t" 2>/dev/null || echo "FAILED $t"; done
  ```

  Expected: すべて成功し、`FAILED` は出ない。

- [ ] **Step 6: コミットする**

  `ci: run hook tests and repository checks on GitHub Actions`。本文に、`main.yaml` を削除した理由（環境全体のセットアップは遅く不安定で、回帰テストを実行していなかった）と、macOS で本番のインタプリタを使う理由を書く。

### Task 4: PR と CI の結果を確認して記録する

**Files:**

- Create: `docs/work/20261111_ci-checks/test-report.md`
- Modify: `docs/work/20261111_ci-checks/plan.md`（`status`）

- [ ] **Step 1: 前提を確認する**

  [前提（ユーザー作業）](#prerequisites) の Actions の有効化を、ユーザーが確認済みであること。

- [ ] **Step 2: push と PR を作成する**

  `/usr/local/libexec/claude-push/cc-safe-push` を実行し、`.cc-pr-request.json` を書いて `/usr/local/libexec/claude-push/cc-safe-pr create` を実行する。

- [ ] **Step 3: CI の結果を確認する**

  Run: `gh pr checks <番号> --watch` と `gh run view <run-id> --log`

  Expected: `Repository checks` と `Hook regression tests` が pass。ログに `GNU bash, version 3.2.57` と `Python 3.9.` がある。[Review Focus](#review-focus) の 4 と 5 の結果も確かめる。

- [ ] **Step 4: 記録してコミットする**

  `test-report.md` に、手元と CI で実行したコマンド・結果・所要時間を書く（ユーザー名を含むパスは書かない）。`plan.md` の `status` を `done` にする。`docs: record CI checks plan and verification` でコミットし、`cc-safe-push` で push して、CI が再び通ることを確認する。
