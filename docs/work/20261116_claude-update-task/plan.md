---
status: in-progress
created: 2026-11-16
---

# スキル・プラグインをまとめて更新するタスクの実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** gstack・Claude Code のプラグイン・crit の CLI を `mise run claude:update` で一度に更新し、gstack が `claude/settings.json` に書く絶対パスを `~/` に戻す。

**Architecture:** 絶対パスの書き換えは独立した Python スクリプト（`claude/scripts/settings-home-paths.py`）にする。更新タスクのシェルスクリプト（`claude/scripts/update-skills.sh`）と `claude/setup.sh` が、gstack の setup が終わった後にこれを呼ぶ。更新タスクは途中で失敗しても残りの手順を続け、最後に失敗した手順の一覧と `/sync-skill-docs` の案内を表示する。

**Tech Stack:** `/bin/bash`（macOS では 3.2）、`/usr/bin/python3`（標準ライブラリだけ）、unittest、mise

**Spec:** 別の設計書はない。このチャットでユーザーが決めたこと（[決定事項](#decisions)）を仕様とする。

<a name="related"></a>

## 関連

- gstack のフックを外した経緯と更新時の注意: [SKILL_INVENTORY.md の提供元ごとの注意](../../../claude/SKILL_INVENTORY.md#upgrade-source)
- 更新後に文書を直す仕組み: [スキル・プラグインの更新に文書を追従させる仕組み](../20261116_skill-docs-sync/plan.md)

<a name="facts"></a>

## 前提（事実）

- gstack の setup は、フックのコマンドを `$HOME/.claude/skills/gstack/<相対パス>` の絶対パスで登録する（`~/.claude/skills/gstack/setup` の `_hook_command_path`）。
- setup は毎回 `gstack-settings-hook prune-stale --repoint <canonical>` を実行する。このときコマンドの文字列をそのまま `stat` するので（`gsIsAlive`）、`~/...` は「存在しないファイル」と判定され、絶対パスに書き戻される。実際に、11/13 のバックアップで `~/` だった timeline-stop-hook が、11/14 には絶対パスになっていた。一度直しただけでは元に戻るので、更新のたびに直す必要がある。
- gstack は書き込むたびに、実体のファイル（`~/.claude/settings.json` のリンク先 `claude/settings.json`）の隣に `settings.json.bak.*` を作る。これは `.gitignore` の `*.bak*` で除外されている。
- 今は gstack のフックを 1 つも登録していない（plan-tune・timeline・ceo-review-gate はすべて off）。書き換えが効くのは、gstack が新しいフックを既定で on にしたときと、フックを残すと決めたとき。
- 直近の更新は `! ~/.claude/skills/gstack/bin/gstack-upgrade` で行われた。`!` は Bash ツールを通らないので、PostToolUse や Stop のフックでは捕まえられない。gstack-upgrade にも、後処理を差し込む仕組みはない。
- user スコープのプラグインは 6 つある（claude-code-setup、crit、pstack、ruby-lsp、superpowers、understand-anything）。salesforce-development は別のリポジトリの local スコープで、2 件出る。`claude plugin list --json` は、`id` と `scope` を持つオブジェクトの配列を返す。
- `claude plugin update` は、マーケットプレイスが宣言したコマンドが変わると確認を求める。TTY がなく `-y` もなければ拒否する。
- `check-repo.py` の `hook-scripts` は、`.claude/hooks/` か `.claude/scripts/` を含むコマンドだけを調べるので、`~/.claude/skills/gstack/...` は対象外。`local-paths` は `/Users/<実在の名前>` を拒否する。

<a name="decisions"></a>

## 決定事項

- タスク名は `claude:update` とし、リポジトリの `mise.toml` に置く。`/sync-skill-docs` は dotfiles の project スキルなので、dotfiles で実行する。sandbox の中からは `~/.claude` と Homebrew に書けないので、端末か Claude Code の `!` で実行する。
- 順番: gstack-upgrade → 絶対パスの書き換え → マーケットプレイスの更新 → user スコープのプラグインの更新 → `brew upgrade crit` → `mise run crit:profile-test` → 失敗した手順の一覧と案内。
- `/sync-skill-docs` は自動では起動しない。案内を表示して止める。
- 書き換えでは `"command": "<HOME>/` を `"command": "~/` にする。gstack 以外が書いた絶対パスも対象にする（どれも公開できないため）。`$HOME` ではなく `~` にするのは、settings.json のほかのフックに合わせるため。`~` はダブルクォートの中では展開されないが、gstack がパスを引用符で囲むのは空白や記号を含むときだけで、ホームのパスには当てはまらない。
- `claude/setup.sh` でも、gstack の setup の直後に書き換えを実行する。
- `claude plugin update` に `-y` は付けない。インストールコマンドが変わったときに、人が見ないまま受け入れないようにするため。
- 実行は Native（このセッションで実装し、最後に 1 回まとめてレビューする）を推奨する。タスクは 2 つだけで、互いに使うのは Task 1 の CLI だけだから。

<a name="out-of-scope"></a>

## やらないこと

- Claude Code のフック（ConfigChange など）で自動的に書き換えること。gstack の書き込みの途中で書き換えると、gstack の検査（settings changed during mutation）に引っかかって登録が失敗する。
- Claude Code 本体と、crit 以外の Homebrew パッケージの更新。
- `/sync-skill-docs` の説明文（frontmatter）の変更。変えるとスナップショットのハッシュが変わってしまう。本文だけを直す。

## Global Constraints

- シェルスクリプトは macOS の `/bin/bash` 3.2 で動くこと。`set -u` と空の配列を組み合わせない（3.2 では未定義の変数として止まる）。
- Python は `/usr/bin/python3 -B` で動かし、標準ライブラリだけを使う。
- テストのファイルに実在のユーザー名を含むパスを書かない（`check-repo.py` の `local-paths` に引っかかる）。`/Users/example` を使うか、`"/Users/" + "example2"` のように文字列を連結する。
- コメントと出力は日本語、識別子は英語で書く。

## Review Focus

1. `~/.claude/settings.json` は dotfiles へのシンボリックリンクなので、リンクを残してリンク先だけを書き換えること。リンクを通常のファイルに置き換えてしまうと、以後の設定変更が dotfiles に入らなくなる。→ Task 1 の `test_main_keeps_symlink_and_mode`
2. 書き換えるものがないときはファイルを書かないこと。書くと、Claude Code が設定を読み込み直してしまう。→ Task 1 の `test_main_without_change_does_not_write`
3. 途中の手順（gstack の失敗、ネットワークの切断など）が失敗しても、書き換えと残りの更新を実行し、終了コード 1 と失敗した手順の一覧を出すこと。→ Task 2 の `test_failure_continues_and_reports`
4. local スコープのプラグイン（別のリポジトリの salesforce-development、2 件の重複）は更新しないこと。→ Task 2 の `test_updates_only_user_scope_plugins`
5. 先頭の文字列がホームのパスと一致するだけの、別のユーザーのパス（ホームが `/Users/example` のとき、`example` の後に文字が続くもの）は書き換えないこと。→ Task 1 の `test_other_user_prefix_is_kept`

---

<a name="task-1"></a>

### Task 1: settings.json のコマンドの絶対パスを `~/` に戻すスクリプト

**Files:**

- Create: `claude/scripts/settings-home-paths.py`
- Create: `claude/scripts/test-settings-home-paths.py`
- Modify: `claude/setup.sh`（gstack の `./setup` を実行する行の直後）
- Modify: `.github/workflows/ci.yaml`（`Tests for skill doc scripts` の step）
- Modify: `CLAUDE.md`（規約の「`claude/scripts/skills-check.py` か …を変更したら」の文）

**Interfaces:**

- Produces:
  - `to_home_relative(text: str, home: str) -> tuple[str, int]`: 置き換えた後の文字列と、置き換えた件数を返す。
  - CLI `/usr/bin/python3 -B claude/scripts/settings-home-paths.py`（引数なし）: 終了コードは 0。書き換えたときだけ `settings-home-paths: <N> 件のコマンドを ~/ に戻した（<実体のパス>）` を出力する。

- [ ] **Step 1: 失敗するテストを書く**

  test-skills-check.py と同じく、冒頭の docstring に目的と実行方法を書く。`to_home_relative` は、ファイル名にハイフンがあるので `importlib.util` で読み込む。

  ```python
  def test_rewrites_home_command(self):
      text = '"command": "/Users/example/.claude/skills/gstack/hosts/claude/hooks/x",'
      self.assertEqual(to_home_relative(text, "/Users/example"),
                       ('"command": "~/.claude/skills/gstack/hosts/claude/hooks/x",', 1))

  def test_keeps_non_command_and_relative(self):
      text = ('"Read(/Users/example/a)",\n'
              '"command": "~/.claude/hooks/v.sh",\n'
              '"command": "bash \\"$HOME/.claude/hooks/h.sh\\" session",')
      self.assertEqual(to_home_relative(text, "/Users/example"), (text, 0))

  def test_other_user_prefix_is_kept(self):
      text = '"command": "/Users/' + 'example2/x",'
      self.assertEqual(to_home_relative(text, "/Users/example"), (text, 0))

  def test_main_keeps_symlink_and_mode(self):
      # HOME=<tmp>。<tmp>/dotfiles/claude/settings.json（0o644）に f'"command": "{tmp}/.claude/skills/gstack/bin/x"'
      # <tmp>/.claude/settings.json は ../dotfiles/claude/settings.json へのリンク。スクリプトをサブプロセスで実行する。
      self.assertTrue(link.is_symlink())
      self.assertEqual(os.readlink(link), "../dotfiles/claude/settings.json")
      self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', target.read_text())
      self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
      self.assertEqual(result.returncode, 0)
      self.assertIn("1 件", result.stdout)

  def test_main_without_change_does_not_write(self):
      # 絶対パスのない settings.json で実行する。
      self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns))
      self.assertEqual(result.stdout, "")
      self.assertEqual(result.returncode, 0)
  ```

- [ ] **Step 2: テストが失敗することを確かめる**

  実行: `python3 -B claude/scripts/test-settings-home-paths.py`
  期待: スクリプトがないので失敗する。

- [ ] **Step 3: `settings-home-paths.py` を実装する**

  - `to_home_relative` は、`'"command": "' + home + '/'` を `'"command": "~/'` に置き換える単純な文字列置換にする。件数は置換の前に数える。JSON を読み込んで書き直すと書式が変わるおそれがあるので、文字列のまま扱う。
  - `main() -> int` は、`Path.home() / ".claude" / "settings.json"` を `resolve()` して実体のパスを得る（gstack も実体のパスに書く）。件数が 0 なら何も書かずに 0 を返す。書き換えるときは、同じディレクトリに `tempfile.NamedTemporaryFile(delete=False)` で書いてから、元の mode を `os.chmod` で写し、`os.replace` で置き換える。

- [ ] **Step 4: テストが通ることを確かめる**

  実行: `python3 -B claude/scripts/test-settings-home-paths.py`
  期待: 5 件すべて OK

- [ ] **Step 5: `claude/setup.sh` から呼ぶ**

  `(cd "${GSTACK_DIR}" && ./setup ...)` の次の行に、既存のコメントの書き方に合わせて「setup はフックを絶対パスで登録するので `~/` に戻す」という趣旨のコメントを付け、`/usr/bin/python3 -B "${SCRIPT_DIR}/scripts/settings-home-paths.py"` を足す。`settings.json` のリンクは 34 行目で先に張られている。

- [ ] **Step 6: CI と CLAUDE.md に足す**

  - `ci.yaml` の `Tests for skill doc scripts` に `python3 -B claude/scripts/test-settings-home-paths.py` を足す。
  - `CLAUDE.md` の規約の文を「`claude/scripts/skills-check.py`・`claude/scripts/skill-usage.py`・`claude/scripts/settings-home-paths.py` を変更したら、それぞれの `test-*.py` を実行する」の形にする。

- [ ] **Step 7: 検証**

  実行（すべて新しいシェルで）:

  ```bash
  python3 -B claude/scripts/test-settings-home-paths.py
  python3 -B .github/scripts/check-repo.py
  python3 -B .github/scripts/test-check-repo.py
  git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning
  actionlint
  ```

  期待: すべて終了コード 0。新しいファイルは `git add` の前でも `check-repo.py` の対象になる。

- [ ] **Step 8: コミット**

  `feat(claude): rewrite absolute home paths in settings.json hook commands to ~/`

<a name="task-2"></a>

### Task 2: 更新タスク `claude:update` と文書

**Files:**

- Create: `claude/scripts/update-skills.sh`
- Create: `claude/scripts/test-update-skills.py`
- Modify: `mise.toml`（`claude:skill-usage` の後に `claude:update` を足す）
- Modify: `.github/workflows/ci.yaml`（Task 1 と同じ step）
- Modify: `CLAUDE.md`（Task 1 で直した文に `update-skills.sh` を足す）
- Modify: `claude/SKILL_INVENTORY.md`（提供元の表の gstack の「更新」、[共通の手順](../../../claude/SKILL_INVENTORY.md#upgrade-common)、[提供元ごとの注意](../../../claude/SKILL_INVENTORY.md#upgrade-source)の gstack と crit の行）
- Modify: `claude/README.md`（17 行目の「gstack は `gstack-upgrade` で更新する」）
- Modify: `.claude/skills/sync-skill-docs/SKILL.md`（10 行目の本文だけ。sandbox の中の Bash からは書けないので Edit ツールで直す）

**Interfaces:**

- Consumes: Task 1 の CLI `/usr/bin/python3 -B claude/scripts/settings-home-paths.py`
- Produces:
  - `/bin/bash claude/scripts/update-skills.sh`（引数なし）: 終了コードは、すべて成功なら 0、どれかが失敗したら 1。
  - 出力は次のとおり。
    - 手順ごとに `==> <手順名>`。手順名は `gstack`・`settings-home-paths`・`marketplaces`・`plugin-list`・`<プラグインの id>`・`crit-cli`・`crit-profile-test`。
    - 失敗があれば `失敗した手順: <手順名を空白区切り>`。
    - 最後に必ず `次に、dotfiles の Claude Code で /sync-skill-docs を実行する。更新したプラグインは、Claude Code を再起動すると読み込まれる。`
  - mise タスク `claude:update`（`run = "/bin/bash claude/scripts/update-skills.sh"`）

- [ ] **Step 1: 失敗するテストを書く**

  偽の HOME と、偽のコマンドを置いた PATH で、スクリプトを `/bin/bash` のサブプロセスとして実行する。

  - `<HOME>/.claude/settings.json` には、`"command": "<HOME>/.claude/skills/gstack/bin/x"` を入れる。
  - `<HOME>/.claude/skills/gstack/bin/gstack-upgrade` は、`gstack-upgrade` をログに書き、環境変数 `STUB_GSTACK_RC`（既定は 0）で終了する。
  - `<stub>/claude`・`<stub>/brew`・`<stub>/mise` は、受け取った引数をログに 1 行ずつ書く。`claude plugin list --json` には `[{"id":"a@m","scope":"user"},{"id":"s@m","scope":"local"},{"id":"b@m","scope":"user"},{"id":"s@m","scope":"local"}]` を返す。
  - PATH は `<stub>:/usr/bin:/bin` にする。

  ```python
  def test_runs_steps_in_order(self):
      self.assertEqual(result.returncode, 0)
      self.assertEqual(log, ["gstack-upgrade",
                             "claude plugin marketplace update",
                             "claude plugin list --json",
                             "claude plugin update a@m --scope user",
                             "claude plugin update b@m --scope user",
                             "brew upgrade crit",
                             "mise run crit:profile-test"])
      self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', settings.read_text())
      self.assertTrue(result.stdout.rstrip().endswith("Claude Code を再起動すると読み込まれる。"))

  def test_updates_only_user_scope_plugins(self):
      self.assertFalse(any("s@m" in line for line in log))

  def test_failure_continues_and_reports(self):
      # STUB_GSTACK_RC=1
      self.assertEqual(result.returncode, 1)
      self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', settings.read_text())
      self.assertEqual(log[-1], "mise run crit:profile-test")
      self.assertIn("失敗した手順: gstack", result.stdout)
  ```

- [ ] **Step 2: テストが失敗することを確かめる**

  実行: `python3 -B claude/scripts/test-update-skills.py`
  期待: スクリプトがないので失敗する。

- [ ] **Step 3: `update-skills.sh` を実装する**

  - 冒頭のコメントに、目的、sandbox の外で実行する理由、`-y` を付けない理由を書く。
  - 失敗は空白区切りの文字列に足していく（配列と `set -u` は使わない）。手順を実行する関数は、`==> <手順名>` を出力してからコマンドを実行し、失敗したら手順名を記録して先に進む。
  - 書き換え（`settings-home-paths`）は gstack の結果に関係なく実行する。setup は途中で失敗しても、すでに書き込んでいることがあるため。
  - プラグインの一覧は `claude plugin list --json` を `/usr/bin/python3 -c` で読み、`scope == "user"` の `id` を、出てきた順に重複を除いて取り出す。jq は使わない（mise の shim に解決されると、HOME を変えたテストが失敗するため）。一覧が取れなければ `plugin-list` を失敗として記録し、プラグインの更新は飛ばす。
  - 書き換えのスクリプトは、`update-skills.sh` からの相対パスで指定する（`$(dirname "$0")`）。

- [ ] **Step 4: テストが通ることを確かめる**

  実行: `python3 -B claude/scripts/test-update-skills.py`
  期待: 3 件すべて OK

- [ ] **Step 5: mise のタスクを足す**

  ```toml
  # スキル・プラグインをまとめて更新する。sandbox の中からは ~/.claude と Homebrew に書けないので、端末か Claude Code の ! で実行する。
  # 終わったら /sync-skill-docs で文書を直す。
  [tasks."claude:update"]
  description = "gstack・プラグイン・crit の CLI を更新し、gstack が settings.json に書いた絶対パスを ~/ に戻す（端末か Claude Code の ! で実行する）"
  run = "/bin/bash claude/scripts/update-skills.sh"
  ```

- [ ] **Step 6: CI・CLAUDE.md・文書を直す**

  - `ci.yaml` に `python3 -B claude/scripts/test-update-skills.py` を足す。`CLAUDE.md` の文に `claude/scripts/update-skills.sh` を足す。
  - `SKILL_INVENTORY.md`:
    - 提供元の表の gstack の「更新」を `` `mise run claude:update`（sandbox の外） `` にする。
    - 表の下に「プラグインも `mise run claude:update` でまとめて更新できる」という 1 行を足す。
    - 共通の手順の先頭に、`! mise run claude:update` を実行する手順を足す。
    - 提供元ごとの注意の gstack の行に、次の 2 点を足す。
      - タスクは setup が書いた絶対パスを `~/` に戻す。
      - `/gstack-upgrade` で更新したときは、後で `! /usr/bin/python3 -B claude/scripts/settings-home-paths.py` を実行する。
    - crit の行に「`crit:profile-test` はタスクが実行する」を足す。
  - `claude/README.md` の 17 行目を、「スキル・プラグイン・crit の CLI は `mise run claude:update` でまとめて更新する（sandbox の外）。gstack の確認だけなら `gstack-upgrade --check`」の趣旨に直す。
  - `sync-skill-docs/SKILL.md` の 10 行目を「更新そのもの（`mise run claude:update`、`/gstack-upgrade`、`claude plugin update`）は行わない。」にする。

- [ ] **Step 7: 検証**

  実行（すべて新しいシェルで）:

  ```bash
  python3 -B claude/scripts/test-update-skills.py
  python3 -B claude/scripts/test-settings-home-paths.py
  mise run claude:skills-check
  python3 -B .github/scripts/check-repo.py
  python3 -B .github/scripts/test-check-repo.py
  git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning
  actionlint
  ```

  期待: `claude:skills-check` は終了コード 0（説明文を変えていないため）。ほかもすべて 0。

- [ ] **Step 8: コミット**

  `feat(claude): add mise task to update skills, plugins and the crit CLI`

<a name="acceptance"></a>

## 実機での確認と完了の条件

Claude は sandbox の外でコマンドを実行できないので、次の 1 と 2 はユーザーに頼む。

1. dotfiles の Claude Code で `! mise run claude:update` を実行する。各手順の `==>` の後に失敗が出ないこと（出たら、その出力をもとに直す）。
2. `git diff claude/settings.json` に `/Users/` がないこと。gstack がフックを登録していれば、`~/.claude/skills/gstack/...` になっていること。
3. 案内に従って `/sync-skill-docs` を実行する（文書の修正はそのスキルの範囲）。
4. PR の前に `/review` を実行し、指摘を直した後にブランチの差分を `/crit-review` で開く。`approved: true` が返ってから push と PR の作成を行う。

<a name="rollback"></a>

## ロールバック

- 変更は追加だけ（新しいスクリプト 2 つ、テスト 2 つ、mise のタスク 1 つ、setup.sh の 1 行、文書）なので、コミットを revert すれば元に戻る。
- 書き換えたのはコマンドの先頭の `<HOME>/` だけなので、意味は変わらない。settings.json を戻したいときは、gstack が作った `claude/settings.json.bak.*` か、git の履歴から戻す。
