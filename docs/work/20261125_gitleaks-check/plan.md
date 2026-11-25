---
status: in-review
created: 2026-11-25
---

# check-repo.py の gitleaks 検査 実装計画

> **エージェント向け:** 必須のサブスキル: superpowers:subagent-driven-development（推奨）か superpowers:executing-plans で、タスクごとに実装する。手順は `- [ ]` のチェックボックスで追う。

**目的:** `check-repo.py` に検査 `secret-content` を足し、対象ファイルの今の中身を gitleaks で調べて、見つかれば FAIL にする。

**構成:** `repo_files()` の通常ファイルを一時ディレクトリに写し、`gitleaks dir` を JSON の報告付きで実行する。報告からパス・行・ルールだけを出す。CI は、shellcheck・actionlint と同じく版とチェックサムで固定した gitleaks を入れる。

**使うもの:** Python 3.11 以上（`tomllib` のため PATH の `python3`）、unittest、gitleaks 8.30.1、GitHub Actions。

**設計:** [design.md](design.md)（承認済み。2026-11-25 の Crit で `approved: true`）

<a name="global-constraints"></a>

## 全体の制約

- 対象は今のファイルだけで、履歴は調べない（ユーザーの判断）。
- 見つかった値（`Secret`・`Match`）は、どの出力にも出さない。CI のログは公開される。
- 検査できないとき（gitleaks がない・0 と 2 以外の終了コード・報告が読めない）は FAIL にする。
- 依存は gitleaks だけ。Python の追加パッケージは使わない。
- gitleaks の版は 8.30.1。CI の `linux_x64` の tar.gz の SHA256 は `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`（GitHub のリリース資産の digest。checksums ファイルと照合してから使う）。
- テストのファイルに秘密の形の文字列を直接書かない。連結で組み立てる。
- コミットは Conventional Commits。タイトルは英語、本文は日本語。

<a name="verified-facts"></a>

## 確かめた gitleaks の仕様（v8.30.1 のソース）

- `dir` は 1 つのパスを `filepath.WalkDir` でたどり、`.gitignore` を見ない。読めないファイルは警告を出して飛ばす。symlink は `--follow-symlinks` がなければ飛ばす。
- 終了コード: 見つからなければ 0、見つかれば `--exit-code` の値、エラー（部分的な走査を含む）は 1。
- 設定の優先順: `--config` → `GITLEAKS_CONFIG` → `GITLEAKS_CONFIG_TOML` → 対象のパスの `.gitleaks.toml` → 既定の設定。
- `.gitleaksignore` は、`-i`（既定はカレントディレクトリ）と、対象のパスの直下の両方から読む。
- allowlist の `paths` の正規表現は、走査したときのパス（一時ディレクトリの絶対パス）に当てる。`^fixtures/` のように行頭で固定すると当たらないので、`(?:^|/)fixtures/` のように書く。
- 報告の JSON は Finding の配列で、項目は `RuleID`・`StartLine`・`File`・`Secret`・`Match` など。見つからなければ `[]`。
- 既定のルール `github-pat` は `ghp_[0-9a-zA-Z]{36}`（entropy 3）。

<a name="review-focus"></a>

## 見落としやすい入力（Review Focus）

1. 見つかった値が出力に混ざる → パス・行・ルールだけが出る（Task 1 の `test_secret_in_tracked_file_fails` で値が出ないことを確かめる）。
2. リポジトリの外を指す symlink → リンク先は公開されないので調べない（`test_symlink_is_not_followed`）。
3. 手元の環境に `GITLEAKS_CONFIG` がある → 無視して、リポジトリの設定か既定の設定を使う（`test_gitleaks_config_env_is_ignored`）。
4. 空白や日本語を含むパス → そのままのパスで報告する（`test_path_with_space_and_japanese_is_reported`）。
5. `.gitleaks.toml` の allowlist → 一時ディレクトリの絶対パスに当てても効く（`test_repo_gitleaks_config_allowlist_passes`）。

---

<a name="prerequisite"></a>

### 準備（人間）

- [ ] 通常のターミナルで `brew install gitleaks` を実行する（sandbox の中からは Homebrew に書けない）。
- [ ] `gitleaks version` が `8.30.1` を返すことを確かめる。
- [ ] ブランチの名前を変える: `git -C <worktree の絶対パス> branch -m worktree-add-gitleaks feat/gitleaks-check`（sandbox の中では `could not lock config file` で終了コード 128 になるが、名前は変わる）。

<a name="task-1"></a>

### Task 1: 検査 `secret-content`

**Files:**
- Modify: `.github/scripts/check-repo.py`（`check_secret_files` の後に関数、`CHECKS` の `secret-files` の次に登録）
- Test: `.github/scripts/test-check-repo.py`
- Modify: `bin/.Brewfile`（`git-filter-repo` と `gnupg` の間に `brew "gitleaks"          # Detect secrets in the repository files (check-repo.py)`。コメントの列はほかの行にそろえる）
- Modify: `CLAUDE.md`（「規約」の `check-repo.py` の段落に、`secret-content` が gitleaks を要し、`bin/.Brewfile` で入れることを 1 文足す）
- Create（誤検知があれば）: `.gitleaks.toml`
- Create: `docs/work/20261125_gitleaks-check/test-report.md`

**Interfaces:**
- Produces: `check_secret_content(root: Path) -> list[str]`。エラーの各行は `<repo 相対パス>:<StartLine>: <RuleID>`（パスの順に並べる）。gitleaks がないときは `gitleaks not found (install it with brew install gitleaks)`、終了コードが 0 と 2 以外なら `error: gitleaks exited with <code>` に続けて stderr の行。
- Produces: 検査名 `secret-content`（出力は `PASS secret-content` / `FAIL secret-content`）。
- Produces: 定数 `GITLEAKS_TIMEOUT = 120`（秒。`subprocess.run` の `timeout`。超えたら例外になり、`main()` が FAIL にする）。

- [ ] **Step 1: 失敗するテストを書く**

`test-check-repo.py` のモジュールの先頭に `FAKE_PAT = "ghp_" + "Zq8rT2vX9wL4mN7pK3sB6dF1gH5jC0yE8uA2"` を置く（後半は 36 文字）。`check()` に `env=None` を足して `subprocess.run` に渡し、`assert_fails` にも `env=None` を足して `check(env)` に渡す。テスト:

```python
def test_secret_in_tracked_file_fails(self):
    self.write("notes/token.txt", FAKE_PAT + "\n")
    self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")
    _, out = self.check()
    self.assertNotIn(FAKE_PAT[4:], out)

def test_secret_in_untracked_file_fails(self):
    self.write("notes/token.txt", FAKE_PAT + "\n", add=False)
    self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")

def test_secret_in_ignored_file_passes(self):
    self.write(".gitignore", "ignored.txt\n")
    self.write("ignored.txt", FAKE_PAT + "\n", add=False)
    self.assert_passes()

def test_gitleaks_allow_comment_passes(self):
    self.write("notes/token.txt", FAKE_PAT + "  # gitleaks:allow\n")
    self.assert_passes()

def test_symlink_is_not_followed(self):
    outside = tempfile.TemporaryDirectory(prefix="check-repo-outside-")
    self.addCleanup(outside.cleanup)
    target = Path(outside.name) / "token.txt"
    target.write_text(FAKE_PAT + "\n", encoding="utf-8")
    (self.root / "link.txt").symlink_to(target)
    self.assert_passes()

def test_path_with_space_and_japanese_is_reported(self):
    self.write("docs/日本語 メモ.txt", FAKE_PAT + "\n")
    self.assert_fails("FAIL secret-content", "docs/日本語 メモ.txt:1: github-pat")

def test_gitleaks_config_env_is_ignored(self):
    # 手元の環境変数で github-pat を外されても、検査は既定の設定で動く。
    conf = self.root.parent / f"{self.root.name}-env.toml"
    conf.write_text('[extend]\nuseDefault = true\ndisabledRules = ["github-pat"]\n', encoding="utf-8")
    self.addCleanup(conf.unlink)
    self.write("notes/token.txt", FAKE_PAT + "\n")
    self.assert_fails("notes/token.txt:1: github-pat", env={**os.environ, "GITLEAKS_CONFIG": str(conf)})

def test_repo_gitleaks_config_allowlist_passes(self):
    self.write(".gitleaks.toml", "[extend]\nuseDefault = true\n\n[[allowlists]]\npaths = ['''(?:^|/)fixtures/''']\n")
    self.write("fixtures/token.txt", FAKE_PAT + "\n")
    self.assert_passes()

def test_missing_gitleaks_fails(self):
    path = "/usr/bin:/bin"
    self.assertIsNone(shutil.which("gitleaks", path=path))
    self.assert_fails("FAIL secret-content", "gitleaks not found", env={**os.environ, "PATH": path})
```

`import os`・`import shutil` を足す。

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `python3 -B .github/scripts/test-check-repo.py`
Expected: 上の 9 件のうち、FAIL を期待する 5 件（`test_secret_in_tracked_file_fails`・`test_secret_in_untracked_file_fails`・`test_path_with_space_and_japanese_is_reported`・`test_gitleaks_config_env_is_ignored`・`test_missing_gitleaks_fails`）が、終了コード 0 で失敗する。PASS を期待する 4 件は、検査がまだないので通る（実装の後に、検査が動いたうえで通ることを Step 4 で確かめる）。

- [ ] **Step 3: `check_secret_content(root)` を実装する**

1. `shutil.which("gitleaks")` が None なら、上の not found の 1 行を返す。
2. `tempfile.TemporaryDirectory(prefix="check-repo-gitleaks-")` の中に、`resolve()` した `src/` と `report.json` を置く。
3. `repo_files(root)` のうち、`is_symlink()` でなく `is_file()` のものを `src/<rel>` に `shutil.copyfile` で写す。ルートの `.gitleaksignore` は写さない（gitleaks が対象のパスの直下から読むため）。
4. `[exe, "dir", str(src), "--no-banner", "--redact", "--report-format", "json", "--report-path", str(report), "--exit-code", "2"]` を、`src/.gitleaks.toml` があれば `--config` を付けて、`cwd=` 一時ディレクトリ、環境変数から `GITLEAKS_CONFIG`・`GITLEAKS_CONFIG_TOML` を除いた `env`、`timeout=GITLEAKS_TIMEOUT` で実行する。
5. 終了コードが 0 と 2 以外なら、エラーの行を返す。2 なのに報告が空でもエラーにする。
6. 報告の各 Finding を `Path(File).relative_to(src)` にして、`<rel>:<StartLine>: <RuleID>` の行にする。`relative_to` が失敗したら例外のままにする（`main()` が FAIL にする）。

関数の上のコメントに、写す理由（`dir` は `.gitignore` を見ず、読めないファイルを黙って飛ばす）と、allowlist の `paths` は絶対パスに当たることを書く。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `python3 -B .github/scripts/test-check-repo.py`
Expected: `OK`（93 + 9 = 102 件）。実行時間を記録する（足す前は 93 件で 32 秒）。

- [ ] **Step 5: 今のリポジトリにかけて誤検知を外す**

Run: `python3 -B .github/scripts/check-repo.py`
Expected: すべて PASS。`secret-content` が FAIL なら、各行を見て、本物なら止めてユーザーに伝える（値を失効させる必要がある）。誤検知なら、1 行ずつは行末の `gitleaks:allow`、ファイル単位でまとまるなら `.gitleaks.toml`（`[extend] useDefault = true` と `(?:^|/)` で始まる `paths`）で外す。件数・ルール・外し方を `test-report.md` に書く（値は書かない）。`check-repo.py` の実行時間も記録する（足す前は 0.25 秒）。

- [ ] **Step 6: Brewfile と CLAUDE.md を直し、リポジトリの検査を通す**

Run: `python3 -B .github/scripts/check-repo.py` と、CLAUDE.md の規約の shellcheck のコマンド
Expected: すべて PASS、shellcheck は出力なし。

- [ ] **Step 7: コミット**

```bash
git add .github/scripts/check-repo.py .github/scripts/test-check-repo.py bin/.Brewfile CLAUDE.md docs/work/20261125_gitleaks-check/
git commit  # feat(check-repo): scan repository file contents with gitleaks
```

`.gitleaks.toml` を作ったら一緒に add する。

<a name="task-2"></a>

### Task 2: CI に gitleaks を入れる

**Files:**
- Modify: `.github/workflows/ci.yaml`（`checks` ジョブ）

**Interfaces:**
- Consumes: Task 1 の `secret-content`（`Repository checks` と `Tests for repository checks` の 2 つのステップが PATH の gitleaks を使う）。

- [ ] **Step 1: 版とチェックサムを確かめる**

`gitleaks_8.30.1_checksums.txt` の `gitleaks_8.30.1_linux_x64.tar.gz` の行が、全体の制約の SHA256 と一致することを確かめる（`gh release download v8.30.1 -R gitleaks/gitleaks -p 'gitleaks_8.30.1_checksums.txt' -O -`。sandbox で取れなければ、ユーザーに実行を頼む）。

- [ ] **Step 2: ジョブを直す**

`env` に `GITLEAKS_VERSION: 8.30.1` と `GITLEAKS_SHA256: <上の値>` を足す。ステップ名を `Install shellcheck, actionlint and gitleaks` にし、actionlint と同じ形で `https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz` を取得、`sha256sum -c -` で照合、`tar -xzf gitleaks.tar.gz -C "$bin" gitleaks` で展開する。上のコメント「手元（Homebrew）と同じ版に固定し」はそのまま当てはまる。

- [ ] **Step 3: 検査する**

Run: `actionlint` と `python3 -B .github/scripts/check-repo.py`
Expected: actionlint は出力なし、check-repo はすべて PASS。

- [ ] **Step 4: コミット**

```bash
git add .github/workflows/ci.yaml
git commit  # ci: install gitleaks for the repository checks
```

<a name="finish"></a>

### 仕上げ

- [ ] `/review` をかけ、指摘を直す。
- [ ] 秘密情報の扱いに触れるので `/security-review` をかけ、Codex のレビュー（通常のターミナルで `codex review`）を提案する。
- [ ] `design.md` と `plan.md` の `status` を `done` にする。`test-report.md` に実行したコマンドと結果をまとめる。
- [ ] `/crit-review` でブランチの差分を開き、`approved: true` を確かめてから、`cc-safe-push` で push し、`cc-safe-pr create` で PR を作る。
- [ ] `gh pr checks` で CI が通ることを確かめる。
