---
status: in-progress
created: 2026-11-18
---

# git を経由した書き換えの守りの実装計画

> **エージェント向け:** superpowers:subagent-driven-development（推奨）か superpowers:executing-plans で、タスクごとに実装する。手順は `- [ ]` で進み具合を記録する。

**目的:** 人間の zsh の `git` と `claude -w` が、sandbox の外で自動で読み込まれたり動いたりするファイルを書く前に、root 所有の確認コマンドで確かめる。

**作り:** 確認コマンド `cc-checkout-guard`（Python の 1 ファイル）が、`check`・`verify`・`worktree-create`・`status` の 4 つの動きを持つ。`bin/.zshrc` の `git` 関数が `check` と `verify` を呼び、`claude/settings.json` の `WorktreeCreate` フックが `worktree-create` を呼ぶ。`check-repo.py` が、これらと mise の設定が崩れていないことを確かめる。

**技術:** Python 3（標準ライブラリだけ）、zsh 5.9、git（確認コマンドは CLT の 2.54.0、人間は Homebrew の 2.56.1）、Claude Code の `WorktreeCreate` フック。

**設計:** [design.md](design.md)（2026-11-18 に Crit で承認）。調査は [research-git-route.md](research-git-route.md)。

関連: [前回の plan](../20261116_sandbox-path-gaps/plan.md)

<a name="constraints"></a>

## 全体の制約

すべてのタスクに当てはまる。値は design から写した。

- 新しいファイルの名前に「git」を入れない（design の C3。worktree を守るフックが、テストの実行を止めるため）。
- 置き場所は `/usr/local/libexec/claude-guard/cc-checkout-guard`。リポジトリの元は `claude/bin/cc-checkout-guard`（モード 100755）。
- shebang は `#!/usr/bin/env -i /Library/Developer/CommandLineTools/usr/bin/python3 -I`。標準ライブラリだけを使う。
- モジュールの読み込みで副作用を起こさない。`check-repo.py` が Linux の CI でこのファイルを import して定数を読むため。`ctypes` での問い合わせは関数の中で行う。
- 確かめるときの git は `/Library/Developer/CommandLineTools/usr/bin/git` だけを使う。毎回、次の形で動かす。
  - 引数: `-C <dir>`、人間が渡した `-c`、`-c core.fsmonitor=false`、`-c core.hooksPath=/dev/null`、`--no-pager`。人間の `-c` より後に置き、こちらの値を勝たせる。
  - diff 系には `--no-ext-diff --no-textconv --ignore-submodules=all --no-renames` を付ける。
  - 環境: `HOME`（`pwd` のデータベースから）、`PATH=/usr/bin:/bin`、`LC_ALL=C`、`GIT_CONFIG_NOSYSTEM=1`、`GIT_TERMINAL_PROMPT=0`、`GIT_OPTIONAL_LOCKS=0`、`GIT_NO_LAZY_FETCH=1`。
  - 出力は bytes で受け、`os.fsdecode` で文字列にする（`text=True` にしない。cc-safe-push と同じ理由）。
- `GIT_NO_REPLACE_OBJECTS` は設定しない。replace の ref を、書く git と同じく効かせる（design 6.4）。
- y/N を飛ばす環境変数やオプションは作らない。既定は N。
- 失敗したら止める（fail closed）。例外はすべて、終了コード 1 と理由のメッセージにする。
- `SANDBOX_RUNTIME` などの環境変数で、sandbox の中かを判断しない（design の C4）。
- 終了コード: `0` 許可、`1` 止める、`3` 先に fetch が要る（`pull` だけ）。
- 人間に見せる文は日本語で、下の「メッセージ」の文をそのまま使う。リポジトリのファイルの中身は、差分として見せるとき以外は出さない。

**対象の一覧**（design 6.2。定数の値）

```python
PROTECTED_DIRS = (".claude", ".vscode", ".idea")        # パスのどこかの階層の名前
PROTECTED_NAMES = (".mcp.json", "mise.lock")             # ファイル名
PROTECTED_PREFIXES = (".env",)                           # ファイル名の先頭
DOTFILES_PROTECTED = (                                   # check-repo.py の PROJECT_DENY_WRITE と同じ文字列
    "./claude", "./zsh", "./config", "./mise", "./mise.toml", "./ghostty", "./vscode", "./bin",
    "./codex", "./biome", "./obsidian", "./aws", "./init.command", "./setup.command", "./CLAUDE.md",
    "./.claude/rules",
)
DANGEROUS_ATTRS = ("filter", "working-tree-encoding", "ident")
```

- 照らし合わせは、Unicode の NFC と `str.casefold()` を通してから行う。
- `DOTFILES_PROTECTED` が当たるのは、作業ツリーのルートの実パスが `realpath(~/dotfiles)` と一致するときだけ。各項目は、その項目と同じパスか、その下のパスに当たる。

**メッセージ**（`{}` は埋める値）

| 定数 | 文 |
| --- | --- |
| `MSG_UNSUPPORTED` | `cc-checkout-guard: この git の呼び出しは確かめられないので止めました（{reason}）。自動で読み込まれるファイルが変わらないことを自分で確かめてから、command git で実行してください。` |
| `MSG_CHANGES` | `cc-checkout-guard: 次のファイルは sandbox の外で自動で読み込まれたり動いたりします。この操作で変わります。` |
| `MSG_ASK` | `続けますか？ [y/N]: ` |
| `MSG_DECLINED` | `cc-checkout-guard: 止めました。` |
| `MSG_NO_TTY` | `cc-checkout-guard: ここでは確認できないので止めました。普段の端末で、差分を確かめてから次を実行してください:` の次の行に `  {command}` |
| `MSG_DANGER` | `cc-checkout-guard: {path} が{kind}になるので止めました。中身を確かめてください。`（`kind` は `symlink`・`submodule（gitlink）`・`書くときに中身を変える属性（{attr}）`） |
| `MSG_ERROR` | `cc-checkout-guard: 確かめる途中で失敗したので止めました（{reason}）。` |
| `MSG_VERIFY` | `cc-checkout-guard: 警告: 確かめた後に、次のファイルが確認と違う中身で書かれました。動いている Claude Code のセッションを止めて、中身を確かめてください。` |

<a name="review-focus"></a>

## 特に確かめること

どのタスクのテストも、そのままでは確かめない入力や状態のうち、使う人に効きやすい順に並べる。それぞれのテストか確認の手順を、担当のタスクに入れた。

1. **人間の端末（Ghostty・VS Code の統合ターミナル）で、`in_sandbox()` が偽になること。** 真になると、確認が黙って素通りする。Task 9 の手順 2 で、人間の端末ごとに `status` を実行して確かめる。
2. **`git status` と補完が遅くならないこと。** すべての呼び出しで Python が起動する。Task 9 の手順 5 で測る。1 回あたりの増分が 100 ミリ秒を超えたら、人間に報告して対処を相談する。
3. **サブディレクトリから打った相対パスの pathspec と、`-C`。** 確認コマンドは、git と同じディレクトリから計算する。Task 2 の `test_pathspec_relative_to_subdirectory`。
4. **衝突するマージ。** `merge-tree` が終了コード 1 を返しても止まらずに、衝突の印を含む中身を見せる。Task 3 の `test_conflicting_merge_still_checked`。
5. **コミットのないリポジトリ（unborn）と detached HEAD。** HEAD が解決できないときは、空の tree として扱う。Task 2 の `test_unborn_and_detached_head`。

<a name="files"></a>

## ファイル

| ファイル | 変更 | 役割 |
| --- | --- | --- |
| `claude/bin/cc-checkout-guard` | 新規 | 確認コマンド（Task 1〜4） |
| `claude/hooks/tests/test-cc-checkout-guard.py` | 新規 | 確認コマンドのテスト（Task 1〜4） |
| `bin/.zshrc` | 変更 | `git` 関数（Task 5） |
| `claude/hooks/tests/test-checkout-function.py` | 新規 | 関数のテスト（Task 5） |
| `claude/settings.json` | 変更（人間が当てる） | `WorktreeCreate` フック、`Edit(**/mise.lock)` の追加、`Edit(/etc/**)` の削除（Task 6） |
| `.github/scripts/check-repo.py`・`test-check-repo.py` | 変更 | 検査（Task 7） |
| `claude/CLAUDE.md`・`CLAUDE.md`・`claude/README.md`・`.claude/rules/CLAUDE_CONFIG.md` | 変更 | 文書（Task 8） |
| `docs/work/20261118_git-route-writes/test-report.md` | 新規 | 確認の記録（Task 9） |

CI は、`claude/hooks/tests/test-*.py` をすべて実行するので、ワークフローは変えない。

---

<a name="task-1"></a>

### Task 1: 確認コマンドの土台

対象の判定、呼び出しの読み取り、sandbox の判定、入口を作る。作業ツリーに書くサブコマンドは、この時点ではすべて「確かめられない形」で止まる。

**Files:**

- Create: `claude/bin/cc-checkout-guard`
- Create: `claude/hooks/tests/test-cc-checkout-guard.py`（読み込み方は `test-cc-safe-push.py` と同じく `SourceFileLoader`。テストの git は PATH の `git`）

**Interfaces（Produces）:**

- 定数: 上の「対象の一覧」、`GIT`、`GUARD_PATH = "/usr/local/libexec/claude-guard/cc-checkout-guard"`、`EXIT_ALLOW = 0`・`EXIT_STOP = 1`・`EXIT_FETCH = 3`、メッセージの定数。
- `READ_ONLY: frozenset[str]`: 作業ツリーに書かないサブコマンド。`add archive blame branch bundle cat-file check-attr check-ignore check-mailmap check-ref-format cherry clone commit commit-graph commit-tree config count-objects describe diff diff-files diff-index diff-tree fetch for-each-ref format-patch fsck gc grep hash-object help init log ls-files ls-remote ls-tree maintenance merge-base merge-tree mktag mktree name-rev notes prune push range-diff reflog remote repack replace rev-list rev-parse shortlog show show-branch show-ref status symbolic-ref tag update-index update-ref var verify-commit verify-pack verify-tag version whatchanged write-tree`。
- `ALLOWED_GIT_ENV: frozenset[str]`: 人間の環境にあってよい `GIT_` の名前。`GIT_EDITOR GIT_SEQUENCE_EDITOR GIT_PAGER GIT_SSH GIT_SSH_COMMAND GIT_ASKPASS GIT_TERMINAL_PROMPT GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_COMMITTER_DATE GIT_MERGE_AUTOEDIT GIT_PROGRESS_DELAY`。
- `class GuardError(Exception)`: 確かめられない、または失敗した。`str(e)` が理由。
- `class FetchFirst(Exception)`: `argv: list[str]`（先に実行する git の引数）。
- `@dataclass(frozen=True) class Invocation`: `cwd: Path`（`-C` を当てた後）、`root: Path | None`（作業ツリーのルート。リポジトリの外なら `None`）、`globals: tuple[str, ...]`（人間が渡した全体のオプションの並び。`!` の表示と fetch に使う）、`config: tuple[str, ...]`（`-c` の値）、`sub: str`（alias を展開した後。なければ `""`）、`args: tuple[str, ...]`、`argv: tuple[str, ...]`（元の引数）、`start: Path`（呼ばれたときのカレントディレクトリ）。
- `HANDLERS: dict[str, Callable[[Invocation, bool], Plan]]`: Task 2・3 が足す。第 2 引数は `after_fetch`。
- `user_home() -> Path`
- `in_sandbox() -> bool`: `/usr/lib/libSystem.B.dylib` の `sandbox_check(getpid(), NULL, 0)` が 1 なら真。例外は偽。
- `is_protected(root: Path, rel: str, home: Path) -> bool`
- `run_git(cwd: Path, *args: str, config: Sequence[str] = (), stdin: bytes | None = None, ok: Sequence[int] = (0,)) -> bytes`: 終了コードが `ok` になければ `GuardError("git <最初の引数> が失敗しました")`。stderr はメッセージに入れない。
- `parse(start: Path, argv: Sequence[str], git_env: Sequence[str], home: Path) -> Invocation`
- `check(argv, *, start: Path, git_env: Sequence[str], after_fetch: bool, home: Path, stdin: TextIO, stderr: TextIO, tty: bool) -> tuple[int, str]`: 終了コードと、標準出力に出す文字列（許可したときの状態の JSON か、fetch の引数の NUL 区切り）。
- `main(argv: list[str]) -> int`: `check [--after-fetch] [--git-env NAMES] -- <git の引数>`・`verify <状態>`・`worktree-create`・`status`。`status` は `sandbox: yes` か `sandbox: no` を出して 0 で終わる。それ以外の形は 1。

**`parse` の決まり**

- 全体のオプション:
  - `-C <path>`（くり返し可。順に当てる）と `-c <k=v>` を読む。`--no-pager`・`-p`・`--paginate`・`--no-optional-locks` は読み飛ばす。
  - `-c alias.*` と、上のほかの全体のオプション（`--git-dir`・`--work-tree`・`--namespace`・`--bare`・`--exec-path`・`--literal-pathspecs`・`--no-replace-objects`・`--config-env` など）は `GuardError`。
  - `--version`・`--help`・`-h` だけなら、`sub = ""`。
- `git_env` に `ALLOWED_GIT_ENV` にない名前があれば `GuardError`。
- alias は、`sub` が `READ_ONLY` にも `HANDLERS` にもないときだけ調べる（git も組み込みのコマンドを優先する）。`run_git(cwd, "config", "--get", f"alias.{name}")` で読み、`shlex.split` して展開する。5 段まで。それを超えるか、`!` で始まる alias は `GuardError`。alias でもなければ、そのまま `sub` にする（`check` の 4 で止まる）。
- `root` は `rev-parse --show-toplevel` から求める。失敗したら `None`。

**`check` の流れ（この Task の分）**

1. `in_sandbox()` が真なら `(0, "")`。
2. `parse` する。`GuardError` なら `MSG_UNSUPPORTED` を出して `(1, "")`。
3. 次のときは `(0, "")`。`sub` が `""` か `READ_ONLY` にある。`args` に `-h` か `--help` がある。`root` が `None`。
4. `sub` が `HANDLERS` にあれば、Task 2 の流れへ進む。なければ、`MSG_UNSUPPORTED`（理由は「{sub} は確かめられません」）を出して `(1, "")`。
5. 予期しない例外は `MSG_ERROR` を出して `(1, "")`。

**テスト**（Base は一時ディレクトリにリポジトリを作り、`guard.in_sandbox` を偽に差し替える）

| テスト | 確かめること |
| --- | --- |
| `test_protected_paths` | `.claude/settings.json`・`a/.Claude/Settings.json`・`.claude`・`.env`・`sub/.ENV.local`・`.mcp.json`・`.vscode/tasks.json`・`.idea/workspace.xml`・`x/mise.lock` が真。`src/main.py`・`docs/claude/x.md`・`environment.txt`・`mise.lock.bak` が偽 |
| `test_dotfiles_paths_only_in_main_checkout` | `home/dotfiles` をルートにすると、`claude/settings.json`・`bin/.zshrc`・`mise.toml`・`.claude/rules/a.md`・`CLAUDE.md` が真、`docs/x.md` が偽。`home/dotfiles/.claude/worktrees/x` と `home/other` では `claude/settings.json` が偽 |
| `test_parse_global_options` | `-C sub status` の `cwd` が `sub`。`-c merge.conflictStyle=diff3 status` の `config` に値が入る。`--git-dir=x status` と `-c alias.s=switch s` は `GuardError` |
| `test_alias_expansion` | `alias.sw=switch` で `sw x` の `sub` が `switch`。2 段の alias も展開する。`alias.x="!sh -c true"` と、自分を指す alias は `GuardError` |
| `test_git_env` | `("GIT_EDITOR",)` は通る。`("GIT_DIR",)` と `("GIT_CONFIG_COUNT",)` は `check` が `(1, "")` |
| `test_read_only_and_help_allow` | `status`・`log`・`diff`・`fetch`・`switch -h`・`switch --help`・`--version` が `(0, "")` |
| `test_outside_repository_allows` | リポジトリの外での `clone a b` と `switch x` が `(0, "")` |
| `test_unknown_subcommand_stops` | `rebase main` が `(1, "")`。stderr に `確かめられない` と `command git` がある |
| `test_in_sandbox_allows_everything` | `in_sandbox` を真にすると、`rebase main` が `(0, "")` |
| `test_sandbox_env_is_ignored` | `SANDBOX_RUNTIME=1` を環境に入れても、`in_sandbox()` の値が変わらない |
| `test_status_mode` | `main(["status"])` が `sandbox: no` を出して 0 |
| `test_errors_fail_closed` | `run_git` が `OSError` を投げると、`check` が `(1, "")` で、stderr に `止めました` がある |

- [ ] **Step 1:** 人間に `! env | grep -E '^GIT_' | cut -d= -f1` を頼み、`!` の環境にある `GIT_` の名前を記録する。`ALLOWED_GIT_ENV` にない名前があれば、実装の前に人間に伝える。そのままだと、`!` のすべての書き込みの操作が止まるためである。
- [ ] **Step 2:** 上のテストを書く。
- [ ] **Step 3:** `/usr/bin/python3 -B claude/hooks/tests/test-cc-checkout-guard.py` を実行し、失敗することを確かめる（モジュールがない）。
- [ ] **Step 4:** 上の Interfaces と決まりのとおりに実装する。ファイルのモードは 100755 にする。
- [ ] **Step 5:** 同じコマンドで、すべて通ることを確かめる。
- [ ] **Step 6:** `/verify` を実行してから、2 つのファイルをコミットする。メッセージは `feat(claude): add the checkout guard skeleton`。

<a name="task-2"></a>

### Task 2: tree と index から書く操作

`switch`・`checkout`・`restore`・`checkout-index`・`reset` の計算、危ない形の検出、差分の表示、確認、`verify` を作る。

**Interfaces**

- Consumes: Task 1 のすべて。
- Produces:
  - `@dataclass(frozen=True) class Entry`: `mode: str`（`"100644"`・`"100755"`・`"120000"`・`"160000"`・`"040000"`）、`oid: str`。
  - `@dataclass(frozen=True) class Change`: `path: str`（ルートからの相対パス）、`old: Entry | None`、`new: Entry | None`（`None` は無い・削除）。
  - `@dataclass(frozen=True) class Plan`: `root: Path`（書かれる作業ツリー）、`changes: tuple[Change, ...]`、`sources: tuple[str, ...]`（属性を確かめる tree の oid。index なら `":index"`）、`fresh: bool = False`（新しいディレクトリに書くとき。Task 3）。
  - `disk_entry(root: Path, rel: str) -> Entry | None`: `lstat` で調べる。通常のファイルは `hash-object --no-filters`、symlink はリンク先の文字列を `hash-object --stdin` で、ディレクトリは `Entry("040000", "")`。
  - `tree_entries(cwd: Path, treeish: str) -> dict[str, Entry]`（`ls-tree -r -z --full-tree`）、`index_entries(cwd: Path) -> dict[str, Entry]`（`ls-files -s -z`。対象のパスに stage 1〜3 があれば `GuardError`）。
  - `changed_paths(inv: Invocation, *diff_args: str) -> list[str]`: `diff --name-only -z` を `inv.cwd` で実行し、ルートからの相対パスで返す。
  - `danger(plan: Plan, inv: Invocation) -> str | None`: 止める理由（`MSG_DANGER` の文）か `None`。
  - `render(plan: Plan) -> str`: 変わるファイルの一覧と差分。
  - `state_of(plan: Plan, inv: Invocation) -> str`、`verify(state: str, stderr: TextIO) -> int`。

**計算の決まり**（`HEAD` が解決できないときは、空の tree として扱う）

| 呼び出し | 書く元 | 候補にするパス |
| --- | --- | --- |
| `switch [opts] [<target>]`、`checkout [opts] <commit>`（`--` がなく、位置引数が 1 つで、コミットに解決できるか、`refs/remotes/*/<x>` にちょうど 1 つ当たる） | target の tree。`-c`・`-C`・`-b`・`-B` で位置引数がなければ `HEAD` | `diff HEAD T` のパス。`-f`・`--force`・`--discard-changes` があれば、`diff T`（作業ツリーとの差）のパスも足す |
| `checkout [<tree-ish>] -- <pathspec>`、`--` のない checkout で上に当たらないもの | `<tree-ish>` があればその tree、なければ index | tree なら `diff T -- <pathspec>`、index なら `diff -- <pathspec>`。checkout の tree からは削除しない |
| `restore [opts] <pathspec>` | `--source`・`-s` の tree。なければ index。`--staged` と `--worktree` の両方なら `HEAD` | 同上。tree から restore するときは、tree にないパスを削除とする。`--staged` だけなら `(0, "")` |
| `checkout-index [-a] [-f] [-q] [-u] [<path>...]` | index | `diff --` のパス（`-a` なら全体） |
| `reset --hard`・`--merge`・`--keep [<commit>]` | `<commit>` か `HEAD` の tree | `diff T` のパス。ほかの reset は `(0, "")` |

- 許可するオプション:
  - `switch`: `-q --quiet -f --force --discard-changes --detach -d --no-track --guess --no-guess --progress --no-progress --ignore-other-worktrees -t --track`。値を取るものは `-c -C -b -B` と `--track=<x>`。
  - `checkout`: 上に加えて `--no-overlay`・`--overlay`。
  - `restore`: `-s --source -W --worktree -S --staged -q --quiet --overlay --no-overlay --ignore-unmerged --progress --no-progress`。
- それ以外のオプションと、短いオプションのまとめ書き（`-qf`）は `GuardError`。
- 候補にしたパスのうち、`is_protected` が真のものだけを `Change` にする。`old` は `disk_entry`、`new` は書く元の entry（なければ `None`）。`old == new` のものは除く。
- `danger`: 次のどれかなら止める。
  - `new.mode` が `120000` か `160000`。
  - 対象のパスの、ルートの下の親ディレクトリのどれかが、今 symlink である。
  - `check-attr -z <DANGEROUS_ATTRS> -- <paths>` で、`unspecified`・`unset` 以外の値がある。作業ツリーの属性と、`sources` の各 tree の属性（`--source=<tree>`。index なら `--cached`）の両方を調べる。
- `render`: 1 行目は `MSG_CHANGES`。続けてパスごとに、`変更`・`追加`・`削除`・`モードの変更（{old}→{new}）` の印とパスを出す。そのあとに `difflib.unified_diff` の差分を出す。
  - 古い中身はディスクから読む。新しい中身は `cat-file blob <oid>`（フィルタなし）で読む。
  - UTF-8 として読めないか、NUL を含むときは `（バイナリ）` とだけ出す。差分は省略しない。
- `check` の続き:
  - `danger` があれば、その文を出して `(1, "")`。確認を求めない。
  - 変わるものがなければ、何も出さずに `(0, state)`。
  - 変わるものがあれば、次のとおりにする。
    - `tty` のとき: `render` と `MSG_ASK` を stderr に出し、`stdin` から 1 行読む。`y` か `yes`（大文字と小文字を区別しない）なら `(0, state)`。それ以外か EOF なら `MSG_DECLINED` を出して `(1, "")`。
    - `tty` でないとき: 一覧と `MSG_NO_TTY` を出して `(1, "")`。表示するコマンドは `git -C <start> <argv>` で、どの語も `shlex.quote` する。
- 状態の JSON: `{"root": "<絶対パス>", "expect": {"<相対パス>": [<旧>, <新>]}}`。各 entry は `[mode, oid]` か `null` で書く。
  - 対象には、変わるファイルと、index にある対象のファイル（変わらないもの。旧と新が同じ）を入れる。
  - `fresh` のときの旧は `null`。
- `verify`: 各パスの今の `disk_entry` が、旧か新のどちらかと一致すればよい（git が途中で止まった場合も、旧のままなら通す）。一致しないパスがあれば、`MSG_VERIFY` とそのパスを出して 1 を返す。

**テスト**（fixture: `main` に `.claude/settings.json`＝`{"v": 1}` と `README.md`＝`a`。`feature` は両方を変える（`{"v": 2}`）。`docs` は `README.md` だけを変える）

| テスト | 確かめること |
| --- | --- |
| `test_switch_without_protected_change_allows` | `switch docs` が `(0, state)` で、stderr が空 |
| `test_switch_stops_without_tty` | `switch feature` が `(1, "")`。stderr に `.claude/settings.json` と `git -C` がある |
| `test_switch_asks_on_tty` | 答え `y` で `(0, state)`。状態の新の oid が `rev-parse feature:.claude/settings.json` と一致する。stderr に `-{"v": 1}` と `+{"v": 2}` がある。答え `""`・`n`・EOF は `(1, "")` |
| `test_checkout_forms` | `co feature`（alias）は止まる。`checkout feature -- README.md` は通る。`checkout feature -- .claude` は止まる |
| `test_index_only_change_is_caught` | `update-index --cacheinfo` で `{"v": 9}` を index に入れると、`restore .claude/settings.json`・`checkout -- .claude/settings.json`・`checkout-index -f -a` が止まり、差分に `{"v": 9}` が出る。`restore --staged .claude/settings.json` は `(0, "")` |
| `test_reset_hard_to_moved_branch` | `update-ref refs/heads/main feature` の後の `reset --hard` が止まる |
| `test_replace_ref_content_is_shown` | `replace <feature の settings の blob> <{"evil": 1} の blob>` の後、`switch feature` の差分に `"evil"` が出る |
| `test_symlink_and_gitlink_stop_without_asking` | settings を symlink にしたブランチと、`.claude/hooks` を gitlink にしたブランチへの `switch` が、答え `y` でも `(1, "")` で、`MSG_ASK` を出さない |
| `test_dangerous_attributes_stop` | `.git/info/attributes` の `.claude/** filter=lfs` と、feature の `.gitattributes` の `working-tree-encoding=UTF-16` で止まる |
| `test_deletion_is_shown` | settings を消したブランチへの `switch` が止まり、`削除` が出る |
| `test_pathspec_relative_to_subdirectory` | index を変えた後、`sub/` から `restore ../.claude/settings.json` を打つと止まる。`-C sub restore ../.claude/settings.json` も同じ |
| `test_unborn_and_detached_head` | コミットのないリポジトリで、ほかから取り込んだ `feature` への `checkout` が止まる。detached HEAD からの `switch feature` も止まる |
| `test_verify` | 承認した状態で、新の中身なら 0、旧のままなら 0、ほかの中身なら 1 で `MSG_VERIFY`。変わらないはずの対象を書き換えても 1 |
| `test_does_not_run_configured_programs` | リポジトリの設定の `core.fsmonitor`・`core.pager`・`diff.external`・textconv（`.gitattributes` の `* diff=x`）が canary を作るようにしても、`switch`・`restore`・`reset --hard` の確認の後に canary がない |
| `test_bang_message_quotes_arguments` | 空白を含むディレクトリから、tty なしで `restore -- .claude/settings.json` を打つと、表示に `git -C '<そのディレクトリ>' restore -- .claude/settings.json` が出る |
| `test_prompt_through_pty` | `pty.fork()` の子で `main(["check", "--", "switch", "feature"])` を動かす（`in_sandbox` は偽に差し替える）。`y` を書き込むと終了コード 0、`n` なら 1。`main` が `sys.stdin.isatty()` で端末を判定していることを確かめる |

- [ ] **Step 1:** テストを書き、実行して失敗することを確かめる。
- [ ] **Step 2:** 実装し、`/usr/bin/python3 -B claude/hooks/tests/test-cc-checkout-guard.py` がすべて通ることを確かめる。
- [ ] **Step 3:** `/verify` を実行してから、2 つのファイルをコミットする。メッセージは `feat(claude): check tree and index checkouts against protected files`。

<a name="task-3"></a>

### Task 3: 取り込む操作と、その他の書き込み

**Interfaces**

- Consumes: Task 1・2 のすべて。
- Produces: `HANDLERS` の `merge`・`pull`・`stash`・`cherry-pick`・`revert`・`rm`・`clean`・`mv`・`worktree`。`compare_with_main(main_root: Path, cwd: Path, treeish: str) -> list[Change]`（Task 4 も使う）。

**計算の決まり**

| 呼び出し | 計算 |
| --- | --- |
| `merge [opts] <commit>`（位置引数はちょうど 1 つ） | `merge-tree --write-tree HEAD <commit>` の 1 行目を結果の tree R とする（終了コード 0 と 1 を受け入れる）。候補は `diff HEAD R`。`sources` は R と `<commit>`。許可するオプションは `-q --quiet --ff --no-ff --ff-only --no-edit --edit -m --squash --no-commit --commit --stat --no-stat --log --no-log --no-verify --progress --no-progress` |
| `merge --abort` | `HEAD` の tree に戻す。候補は `diff HEAD` |
| `merge --continue`・`--quit` | `(0, "")` |
| `pull [opts]`（位置引数なし） | `after_fetch` でなければ `FetchFirst(globals + ["fetch", <branch.<b>.remote>])` を投げ、`check` は `(3, NUL 区切りの引数)` を返す。`after_fetch` なら、`@{upstream}` を `<commit>` とする merge として計算する。`pull.rebase` か `branch.<b>.rebase` が真なら `GuardError`。許可するオプションは `--ff-only --ff --no-ff --no-rebase -q --quiet -v --verbose --no-edit --stat --no-stat` |
| `stash`・`stash push [-q] [-m <msg>] [-u] [-k]`（pathspec なし） | 候補は `diff HEAD`（`HEAD` に戻る）。`-u`・`--include-untracked` があれば、`ls-files --others --exclude-standard` の対象のファイルを削除の候補に足す |
| `stash apply`・`stash pop [-q] [--index] [<stash>]` | s は `<stash>` か `stash@{0}`。R は `merge-tree --write-tree --merge-base=<s>^1 HEAD <s>`。候補は `diff HEAD R`。`<s>^3` があれば、その tree の対象のファイルを追加の候補に足す |
| `stash list`・`show`・`drop`・`clear`・`create`・`store` | `(0, "")`。ほかの `stash` は `GuardError` |
| `cherry-pick [-n] [-x] [--no-edit] [-e] [-s] <commit>` | `merge-tree --write-tree --merge-base=<c>^ HEAD <c>`。範囲（`..` を含む）、マージコミット、`--continue`・`--skip`・`--abort`・`--quit` は `GuardError` |
| `revert`（同じオプション） | `merge-tree --write-tree --merge-base=<c> HEAD <c>^` |
| `rm [-r] [-f] [-q] [--ignore-unmatch] [--] <pathspec>` | `ls-files -z -- <pathspec>` の対象のファイルを削除の候補にする。`--cached` か `-n` があれば `(0, "")` |
| `clean` | `-n`・`--dry-run` があれば `(0, "")`。`-i` は `GuardError`。ほかは、同じ引数から `-f`・`--force` を除いて `--dry-run` を付けて実行する。`Would remove <path>` の対象のファイルを削除の候補にする |
| `mv` | 位置引数のどれか（移動先のディレクトリの中の行き先を含む）が対象なら `GuardError`。ほかは `(0, "")` |
| `worktree add [opts] <path> [<commit>]` | T は `<commit>`。なければ、`-b`・`-B` があるときは `HEAD`、ないときは `<path>` の最後の名前のローカルのブランチ、それもなければ `HEAD`。`Plan(root=<path の絶対パス>, changes=compare_with_main(...), fresh=True)`。`--orphan` は `GuardError`、`--no-checkout` は `(0, "")` |
| `worktree list`・`prune`・`lock`・`unlock`・`remove`・`move`・`repair` | `(0, "")` |

- `compare_with_main` は、すべてのリポジトリ向けの対象（`DOTFILES_PROTECTED` を除く）について、`treeish` の tree と、元のチェックアウトの index のパスを合わせて調べる。旧は元のチェックアウトの `disk_entry`、新は tree の entry とし、違うものを返す。元のチェックアウトのルートは `rev-parse --path-format=absolute --git-common-dir` の親とする。
- 対象のファイルが変わる取り込みでは、`check` が `(3, ...)` を返したあと、関数が fetch してから `--after-fetch` で呼び直す（Task 5）。

**テスト**

| テスト | 確かめること |
| --- | --- |
| `test_merge` | `merge docs` は `(0, state)`、`merge feature` は止まる |
| `test_conflicting_merge_still_checked` | main で settings を `{"v": 3}` にした後の `merge feature` が止まり、答え `n` の差分に `<<<<<<<` が出る |
| `test_merge_abort` | 作業ツリーの settings を書き換えた後の `merge --abort` が止まる |
| `test_pull_fetch_protocol` | 一時ディレクトリの bare リポジトリを origin にする。別の clone から settings を変えて push した後、`pull` は `(3, "fetch\0origin")`。実際に fetch した後の `after_fetch` では止まる。README だけの変更なら `(0, state)` |
| `test_pull_unsupported_forms` | `pull origin main` と、`pull.rebase=true` での `pull` が `(1, "")` |
| `test_stash` | settings を書き換えた後の `stash` は止まる。settings の変更を含む stash の `stash pop` は止まる。`.env.local` を含む `stash -u` の `pop` は止まる。`stash list` は `(0, "")` |
| `test_cherry_pick_and_revert` | `cherry-pick feature` は止まる、`cherry-pick docs` は通る、`revert <settings を変えたコミット>` は止まる、`cherry-pick main..feature` は `(1, "")` |
| `test_rm_clean_mv` | `rm .claude/settings.json` は止まる、`rm --cached .claude/settings.json` は通る。未追跡の `.env.local` があるときの `clean -fdx` は止まり、`clean -n` は通る。`mv README.md .claude/x.md` は `(1, "")`、`mv README.md R.md` は通る |
| `test_worktree_add_compares_with_main_checkout` | `worktree add ../wt feature` は止まる。`worktree add ../wt2 docs` は `(0, state)` で、状態の `root` が `wt2` になる。`worktree list` は `(0, "")` |

- [ ] **Step 1:** テストを書き、失敗することを確かめる。
- [ ] **Step 2:** 実装し、テストがすべて通ることを確かめる。
- [ ] **Step 3:** `/verify` を実行してからコミットする。メッセージは `feat(claude): check merges, stashes and picks against protected files`。

<a name="task-4"></a>

### Task 4: `claude -w` のフック（`worktree-create`）

**Interfaces**

- Consumes: `compare_with_main`、`disk_entry`、`danger` の symlink の判定、`run_git`。
- Produces: `worktree_create(payload: Mapping[str, object], *, stdout: TextIO, stderr: TextIO) -> int`。`main` の `worktree-create` は、標準入力の JSON をこれに渡す。`NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")`。

**流れ**（design 6.6。fetch はしない）

1. `name` が `NAME` に合わなければ 1。`cwd` から元のチェックアウトのルートを求める。共通の gitdir の名前が `.git` でなければ（bare）1。
2. 置き場所は `<ルート>/.claude/worktrees/<name>`。`.claude` と `.claude/worktrees` のどちらかが symlink なら 1。
3. 置き場所が `worktree list --porcelain` にあれば、そのパスを出して 0。ディレクトリだけがあれば 1。
4. 作成元は、`refs/remotes/origin/HEAD^{commit}` が解決できればそれ、できなければ `HEAD^{commit}`。どちらもなければ 1。
5. `compare_with_main` で作成元の tree を比べる。違いがあれば、作らずに 7 へ。
6. `worktree add -b worktree-<name> <置き場所> <作成元>` で作る。
   - このときだけ、`PATH` に `/opt/homebrew/bin` を足す。グローバルの設定の `filter.lfs` が `git-lfs` を呼ぶためである。
   - 作った後、新しい worktree と元のチェックアウトで、すべてのリポジトリ向けの対象のファイルを `disk_entry` で比べる。対象は、どちらかの index にあるパスとする。対象のパスか、その親が symlink かどうかも調べる。
   - 違いがあれば、`worktree remove --force <置き場所>` と `branch -D worktree-<name>` で片付けてから 7 へ。
7. 違ったファイルの一覧と、design 6.6 の手順 6 の案内のうち当てはまる 1 つを出して、1 を返す。案内の判断の順は、次のとおり。
   1. 元のチェックアウトのブランチの名前が、`origin/HEAD` の指すブランチの名前と違う。
   2. `status --porcelain -- <違ったパス>` が空でない。
   3. 元のチェックアウトの `HEAD` が、作成元と違う。
   4. それ以外（差し替えのおそれ）。
8. 成功したら、置き場所の絶対パスを標準出力の最後の行に出して 0 を返す。

**テスト**（fixture: 一時ディレクトリの bare を origin として clone した元のチェックアウト。`origin/HEAD` は `main`）

| テスト | 確かめること |
| --- | --- |
| `test_create_matches_main_checkout` | 0。最後の行が置き場所。ブランチ `worktree-x` がある。settings が元のチェックアウトと同じ |
| `test_tampered_origin_head_is_rejected` | `refs/remotes/origin/evil` を feature に向け、`origin/HEAD` をそこへ向けると 1。置き場所もブランチも残らない。stderr に `.claude/settings.json` がある |
| `test_replaced_blob_is_caught_after_checkout` | 元のチェックアウトを書いた後に、main の settings の blob を replace で差し替えると、作った後の比較で 1 になり、片付けられる |
| `test_bad_names_are_rejected` | `""`・`../x`・`.x`・`a/b`・65 文字が 1 で、何も作らない |
| `test_existing_worktree_returns_path` | 2 回目の呼び出しも 0 で、同じパスを返す |
| `test_guidance_for_other_branch` | 元のチェックアウトを feature にすると 1 で、ブランチの案内が出る |
| `test_no_origin_uses_head` | origin のないリポジトリで 0 |

- [ ] **Step 1:** テストを書き、失敗することを確かめる。
- [ ] **Step 2:** 実装し、テストがすべて通ることを確かめる。
- [ ] **Step 3:** `/verify` を実行してからコミットする。メッセージは `feat(claude): create claude -w worktrees through the checkout guard`。

<a name="task-5"></a>

### Task 5: zsh の `git` 関数

**Files:**

- Modify: `bin/.zshrc`（最後の `eval "$(mise activate zsh)"` の後に足す）
- Create: `claude/hooks/tests/test-checkout-function.py`

**足すもの**（印の行は、テストと check-repo が使う）

```zsh
########################################
# git を経由した書き換えの確認（cc-checkout-guard）
########################################
# >>> cc-checkout-guard
git() {
  local guard=/usr/local/libexec/claude-guard/cc-checkout-guard
  if [[ ! -x $guard ]]; then
    print -u2 "git: $guard がありません。~/dotfiles/claude/README.md の手順でインストールしてください。確かめずに実行するときは command git を使います。"
    return 1
  fi
  local genv=${(j:,:)${(M)${(k)parameters[(R)*export*]}:#GIT_*}}
  local state rc
  state=$("$guard" check --git-env "$genv" -- "$@")
  rc=$?
  if (( rc == 3 )); then
    command git "${(0@)state}" || return
    state=$("$guard" check --after-fetch --git-env "$genv" -- "$@")
    rc=$?
  fi
  (( rc == 0 )) || return $rc
  command git "$@"
  rc=$?
  if [[ -n $state ]]; then
    "$guard" verify "$state" || return 1
  fi
  return $rc
}
# <<< cc-checkout-guard
```

**テスト**

テストは、印のあいだを取り出し、`guard=` の値を一時ディレクトリの偽の確認コマンドに置き換えて、`/bin/zsh -f` で読み込む。`PATH` の先頭には、引数を記録する偽の `git` を置く。偽の確認コマンドは、環境変数で決めた終了コードと出力を返し、呼ばれた引数を記録する。

| テスト | 確かめること |
| --- | --- |
| `test_stops_when_check_fails` | check が 1 なら、関数は 1 を返し、偽の git は呼ばれない |
| `test_runs_git_and_verify` | check が `STATE` を出して 0 なら、git が `switch x` で呼ばれ、続けて `verify STATE` が呼ばれる。返す値は git の終了コード（5） |
| `test_no_verify_without_state` | check の出力が空なら、verify は呼ばれない |
| `test_fetch_protocol` | 1 回目の check が `fetch\0origin` を出して 3 なら、`git fetch origin` が呼ばれ、続けて `check --after-fetch` と `git pull` が呼ばれる |
| `test_verify_failure_returns_nonzero` | verify が 1 なら、git が 0 でも関数は 1 |
| `test_missing_guard` | 確認コマンドがなければ 1 で、stderr に `README.md` があり、git は呼ばれない |
| `test_git_env_names` | export した `GIT_FOO` だけが `--git-env` に渡る。export していない `GIT_BAR` は渡らない |
| `test_sandbox_runtime_does_not_skip` | `SANDBOX_RUNTIME=1` でも check が呼ばれ、1 なら git は呼ばれない |
| `test_block_is_after_mise` | `bin/.zshrc` で、印の始まりが `eval "$(mise activate zsh)"` より後にある |

- [ ] **Step 1:** テストを書き、失敗することを確かめる（印がない）。
- [ ] **Step 2:** `bin/.zshrc` に足す（Edit ツール。プロジェクトの ask で確認が出る）。
- [ ] **Step 3:** `/usr/bin/python3 -B claude/hooks/tests/test-checkout-function.py` がすべて通ることを確かめる。
- [ ] **Step 4:** `/verify` を実行してからコミットする。メッセージは `feat(zsh): route git through the checkout guard`。

<a name="task-6"></a>

### Task 6: ユーザー設定の変更（人間が当てる）

design の C2 のため、Claude は差分のファイルを用意し、人間が当てる。

design 6.12 では check-repo の検査が先だが、この plan では設定を先にする。検査を先に入れると、そのコミットでは実物のリポジトリの検査が失敗し、CI が落ちるためである。

- [ ] **Step 1:** `tmp/claude-settings-guard.patch` を書く。中身は 2 つ。
  - `permissions.deny` の `"Edit(**/.env*)"` の次の行に `"Edit(**/mise.lock)"` を足す。
  - `hooks` に `"WorktreeCreate": [{"hooks": [{"type": "command", "command": "/usr/local/libexec/claude-guard/cc-checkout-guard worktree-create", "timeout": 60}]}]` を足す。
- [ ] **Step 2:** 人間に `! patch -p1 < tmp/claude-settings-guard.patch` を頼む（worktree の中で実行する。worktree の `claude/settings.json` は、まだどこからも使われていない。design の C1）。
- [ ] **Step 3:** `python3 -B .github/scripts/check-repo.py` が PASS することを確かめ、`claude/settings.json` をコミットする。メッセージは `feat(claude): register the checkout guard for claude -w and deny Edit to mise.lock`。
- [ ] **Step 4:** `tmp/claude-settings-etc.patch`（`"Edit(/etc/**)",` の行を消す）を書き、Step 2・3 と同じように当ててコミットする。メッセージは `fix(claude): drop the Edit(/etc/**) deny that pointed under ~/.claude`。本文に理由（design 6.9）を書く。

<a name="task-7"></a>

### Task 7: `check-repo.py` の検査

**Files:** Modify `.github/scripts/check-repo.py`、`.github/scripts/test-check-repo.py`

**足す定数**

```python
CHECKOUT_GUARD = "claude/bin/cc-checkout-guard"
CHECKOUT_GUARD_COMMAND = "/usr/local/libexec/claude-guard/cc-checkout-guard worktree-create"
ZSHRC = "bin/.zshrc"
ZSHRC_BLOCK = ("# >>> cc-checkout-guard", "git() {", "local guard=/usr/local/libexec/claude-guard/cc-checkout-guard", "# <<< cc-checkout-guard")
ZSHRC_AFTER = 'eval "$(mise activate zsh)"'
GUARD_REQUIRED_DIRS = (".claude", ".vscode", ".idea")
GUARD_REQUIRED_NAMES = (".mcp.json", "mise.lock")
GUARD_REQUIRED_PREFIXES = (".env",)
MISE_LOCK_DENY = ("Edit(**/mise.lock)",)
MISE_ENV_FORBIDDEN = ("MISE_TRUSTED_CONFIG_PATHS", "MISE_PARANOID")
MISE_ENV_FILES = ("bin/.zshrc", "bin/.zprofile", "mise/mise_config.toml")  # ほかに zsh/*.zsh
```

**検査**

- 新しい検査 `checkout-guard`（`CHECKS` の `mise-paranoid` の次）:
  - `CHECKOUT_GUARD` を `SourceFileLoader` で読み込む（読み込めなければ失敗）。`PROJECT_DENY_WRITE` のすべてが `DOTFILES_PROTECTED` にあることと、3 つの `GUARD_REQUIRED_*` が対応する定数に含まれることを確かめる。
  - `claude/settings.json` の `hooks.WorktreeCreate` にあるコマンドの並びが、`[CHECKOUT_GUARD_COMMAND]` とちょうど一致する。
  - `ZSHRC` に `ZSHRC_BLOCK` の 4 行がこの順にあり、最初の行が `ZSHRC_AFTER` より後にある。
- `edit-permissions`: `MISE_LOCK_DENY` が `permissions.deny` にあることを足す。
- `mise-paranoid`:
  - グローバルの設定の `[settings]` に `trusted_config_paths` があれば、値によらず失敗にする。
  - `MISE_ENV_FILES` と `zsh/*.zsh` のどこかに `MISE_ENV_FORBIDDEN` の名前があれば、失敗にする。

**テスト**（fixture に、定数だけを持つ偽の `claude/bin/cc-checkout-guard`、印のある `bin/.zshrc`、フックと deny を足した設定を加える）

| テスト | 確かめること |
| --- | --- |
| `test_checkout_guard_missing_dotfiles_entry_fails` | `DOTFILES_PROTECTED` から `./zsh` を除くと `FAIL checkout-guard` |
| `test_checkout_guard_missing_general_pattern_fails` | `.vscode`・`mise.lock`・`.env` をそれぞれ除くと失敗する |
| `test_worktree_create_hook_fails_when_changed` | フックがない、別のコマンド、2 つあるのどれも失敗する |
| `test_zshrc_block_fails_when_missing_or_early` | 印がない、または mise の行より前にあると失敗する |
| `test_missing_mise_lock_deny_fails` | `Edit(**/mise.lock)` を除くと `FAIL edit-permissions` |
| `test_trusted_config_paths_fails` | `trusted_config_paths = []` と `["~/Dev"]` のどちらも `FAIL mise-paranoid` |
| `test_mise_env_override_fails` | `bin/.zshrc` の `export MISE_PARANOID=0` と、`zsh/x.zsh` の `MISE_TRUSTED_CONFIG_PATHS` が失敗する |

- [ ] **Step 1:** テストを書き、`python3 -B .github/scripts/test-check-repo.py` で失敗することを確かめる。
- [ ] **Step 2:** 実装し、`test-check-repo.py` と `check-repo.py`（実物のリポジトリ）がどちらも通ることを確かめる。
- [ ] **Step 3:** `/verify` を実行してからコミットする。メッセージは `feat(ci): check the checkout guard, its hook and mise trust overrides`。

<a name="task-8"></a>

### Task 8: 文書

- [ ] **Step 1: `claude/CLAUDE.md`（グローバル）の Safety。** 「sandbox の中の git が … 途中で止まったら」の項目の最後に、次を足す。

  > 人間の zsh の `git` は、それらのファイルが変わる操作を `!` では止める（cc-checkout-guard）。含まれるときは、`!` ではなく普段の端末で打つ `git -C <パス> …` を示す。`command git`・`\git`・絶対パスの git を頼まない。

- [ ] **Step 2: リポジトリの `CLAUDE.md`。**
  - 「sandbox と権限の禁止事項」に 2 項目を足す。
    - `bin/.zshrc` の `git` 関数、`claude/settings.json` の `WorktreeCreate` フック、`Edit(**/mise.lock)` の deny を外さない（`checkout-guard`・`edit-permissions` が失敗する）。
    - mise の `trusted_config_paths` と、シェルの設定の `MISE_TRUSTED_CONFIG_PATHS`・`MISE_PARANOID` を足さない（`mise-paranoid` が失敗する）。
  - 規約のテストの行に、次を足す。`claude/bin/cc-checkout-guard` か `bin/.zshrc` の関数を変更したら、`/usr/bin/python3 -B claude/hooks/tests/test-cc-checkout-guard.py` と `/usr/bin/python3 -B claude/hooks/tests/test-checkout-function.py` を実行する。
  - 「git push」の節の後に、短い節「git の確認（cc-checkout-guard）」を足す。何をするか、変えたら再インストールすること、README へのリンク。
- [ ] **Step 3: `claude/README.md`。** cc-safe-push の節と同じ形で、`<a name="cc-checkout-guard-install"></a>` の節を足す。中身は次の 3 つ。
  - インストール: `sudo install -d -o root -g wheel -m 0755 /usr/local/libexec/claude-guard` と `sudo install -o root -g wheel -m 0755 claude/bin/cc-checkout-guard /usr/local/libexec/claude-guard/cc-checkout-guard`。
  - 動き（普段の端末、`!`、sandbox、`claude -w`）。
  - 戻し方（design 6.14 の順）。
- [ ] **Step 4: `.claude/rules/CLAUDE_CONFIG.md`。** `<a name="cc-checkout-guard"></a>` の節を足し、理由を短く書く。
  - root 所有に置き、一覧を中に持つ理由。
  - sandbox の中かどうかを環境変数で判断しない理由。
  - `claude -w` で、元のチェックアウトと比べる理由。
  - 入れ子のリポジトリの経路は、次の作業にしたこと。
- [ ] **Step 5:** `python3 -B .github/scripts/check-repo.py` が PASS することを確かめる（リンクとアンカー）。
- [ ] **Step 6:** 4 つのファイルをコミットする（文書だけなので `/verify` は不要）。メッセージは `docs: describe the checkout guard`。

<a name="task-9"></a>

### Task 9: インストールと確認（人間と一緒に）

- [ ] **Step 1: インストール。** 人間に、普段の端末で、worktree をカレントディレクトリにして、README の 2 行を実行してもらう。
- [ ] **Step 2: sandbox の判定。** 次の 3 つの場所で `/usr/local/libexec/claude-guard/cc-checkout-guard status` を実行し、結果を記録する。
  - Claude の Bash ツール（`sandbox: yes` になるはず）。
  - 人間の `!`（`sandbox: no` になるはず）。
  - 人間の Ghostty と VS Code の統合ターミナル（どちらも `sandbox: no` になるはず）。
- [ ] **Step 3: 関数の試し。** 人間が実行するスクリプト `tmp/guard-trial.sh` を書く。中身は、一時ディレクトリにダミーのリポジトリを作るものとする（`tmp/r2-git-hooks.sh` と同じ作り）。人間は普段の端末で、関数を読み込んでから試す（`source <(sed -n '/^# >>> cc-checkout-guard/,/^# <<< cc-checkout-guard/p' <worktree>/bin/.zshrc)`）。
  - 確認が出て、N で止まり、y で切り替わる。
  - `!` に相当する形として、`! /bin/zsh -c '<読み込み>; cd <ダミー> && git switch feature'` が止まる。`SANDBOX_RUNTIME=1` を付けても止まる。
  - Bash ツールで同じ形を実行すると、確かめずに通る。
- [ ] **Step 4: `claude -w` の試し。** ダミーのリポジトリのプロジェクト設定に、同じ `WorktreeCreate` フックを登録する。人間がそこで `claude -w probe` を実行し、worktree ができることを確かめる。続けて、`origin/HEAD` を差し替えた状態で、失敗して何も残らないことを確かめる。
- [ ] **Step 5: 速さ。** 普段の端末で関数を読み込み、`~/dotfiles` で `time (repeat 20 git status >/dev/null)` と `time (repeat 20 command git status >/dev/null)` を比べる。1 回あたりの増分を記録する。
- [ ] **Step 6: 記録。** `test-report.md` に次を書く。
  - 自動の検査の結果。コマンドは、`test-cc-checkout-guard.py`・`test-checkout-function.py`・ほかのフックのテスト 5 本・`test-cc-safe-push.py`・`test-cc-safe-pr.py`・`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint。
  - Step 2〜5 の結果。
  - マージの後に人間が確かめること。新しい zsh で `whence -w git` が関数になること、`~/dotfiles` での `claude -w`、Bash ツールの git。
- [ ] **Step 7:** `test-report.md` をコミットする。メッセージは `docs: record the checkout guard checks`。

<a name="after"></a>

## 実装の後

ルートの CLAUDE.md とグローバルの規則の順に進める。

1. `/review`
2. `/security-review`
3. Codex のレビュー（人間が普段の端末で実行する）
4. Crit でブランチの差分を確かめる
5. `cc-safe-push`
6. `cc-safe-pr create`
7. `gh pr checks`

マージは人間が行う。マージの前に、Task 9 の Step 1 のインストールが済んでいること（design 6.12）。完了したら、design・plan・research の `status` を `done` にする。
