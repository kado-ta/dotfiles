---
status: done
created: 2026-11-13
---

# sandbox の外で実行されるものを守る（実装計画）

> [!NOTE]
> 実装は superpowers:executing-plans で、タスクごとに進める。手順はチェックボックス（`- [ ]`）で追う。

- **目的:** Claude の sandbox から書けて、後で sandbox の外で実行・読み込まれるものを塞ぐ。対象は次の 3 つ。
  - dotfiles がリンクしている設定
  - ラッパーのインタプリタ
  - Lima の鍵
- **方針:** 守り方は今の方法に合わせる。
  - Bash は `sandbox.filesystem.denyWrite` / `denyRead` で守る。
  - Edit・Write ツールは `permissions.ask` / `deny` で守る。
  - 規則が消されないように、`check-repo.py` の定数で検査する。
  - ラッパーは、xcrun と呼び出し元の環境変数の影響を受けない形で起動する。
- **技術:** Claude Code の設定（JSON）、Python 3.9（CLT の python3）、Seatbelt profile
- **根拠:** [research-sandbox-escape.md](research-sandbox-escape.md)

関連: PR #15、[20261111_crit-sandbox/design.md](../20261111_crit-sandbox/design.md)

<a name="decisions"></a>

## 決めていただきたいこと

| # | 内容 | 推奨 | 理由・トレードオフ | 決定 |
| --- | --- | --- | --- | --- |
| D1 | ラッパーを起動するインタプリタ | **CLT の実体を、`env -i` を付けて直接起動する**（`#!/usr/bin/env -i /Library/Developer/CommandLineTools/usr/bin/python3 -I`）。`cc-safe-push` の git も CLT の実体にする | xcrun を通らなくなるので、`DEVELOPER_DIR`・`TOOLCHAINS`・xcrun のキャッシュのどれでも、実行されるプログラムを変えられない（[research 5.4](research-sandbox-escape.md#risk-xcrun-cache)）。代わりに、CLT を消すとラッパーが動かなくなる（拒否側に倒れる）。CI の runner にそのパスがないと、CI のテストが失敗する（[特に確かめること](#review-focus)の 5）。もう 1 つの案は shim のまま `env -i` を付け、キャッシュへの Edit を `permissions.deny` で拒否するもの。ただし、キャッシュの場所の推測と、Edit の規則の両方に頼ることになる | 推奨案で進める |
| D2 | dotfiles の `CLAUDE.md` を Task 1 に含めるか | **含める**（`./CLAUDE.md` と `Edit(/CLAUDE.md)`） | sandbox から書けることを実測した。書いた内容は、次のセッションでは指示として読まれる。Edit ツールで変えるときは、承認の画面で差分を見られる。代わりに、CLAUDE.md を変える PR のたびに承認が要る | 含める |
| D3 | Docker のソケットに接続できないことを確かめる方法 | **auto mode を一時的に外して（Shift+Tab）、確認の画面で 1 回だけ承認する** | 許可をもらった後も拒否された（後に、原因は auto mode ではなく、`permissions.deny` の `Bash(curl *)` だと分かった）。`!` で実行すると sandbox の中で動くかどうかを私は確かめていないので、測定にならないおそれがある。確かめない場合は、コード（sandbox-runtime）を根拠にして、Task 5 の検査だけを入れる | 推奨のとおり。Task 5 の手順 7 で、auto mode を外してもらってから実行する |
| D4 | 実装を worktree で行うか | **worktree で行う** | `claude/settings.json` は、`~/.claude/settings.json` の実体。main checkout で編集すると、作業途中の状態が、動いているすべてのセッションにすぐ効く。たとえば Task 4 の途中では、インストール済みの cc-crit が拒否側に倒れる。worktree を使うには、明示の指示が要る | worktree で行う（[Task 0](#task-0)） |
| D5 | GitHub Actions（[research 5.2](research-sandbox-escape.md#risk-actions)） | **この PR には入れず、別の作業にする** | 対策は 2 つある。1 つは GitHub 側の設定（main の ruleset、workflow の既定の権限、secrets を environment に置く）の確認で、これは人間が行う。もう 1 つは、`.github/workflows/` を変えるコミットの push を `cc-safe-push` で拒否することで、これはラッパーの変更になる | 別の作業にする |

<a name="constraints"></a>

## 守ること

- **sandbox の設定:** `sandbox.enabled: true`、`failIfUnavailable: true`、`allowUnsandboxedCommands: false` は変えない。
- **既存の制限:** `denyRead`・ネットワークの制限・権限は緩めない。項目を置き換えるときは、元の範囲を含める（例: `./config/sheldon` を `./config` にする）。
- **コミット:**
  - main にコミットしない。`git switch -c` と `git commit` は別の呼び出しにする。
  - 1 コミットに 1 つの論理変更を入れる。Conventional Commits の形で、タイトルは英語、本文は日本語にする。
  - gstack が書き換える `claude/settings.json` のパスの差分は、コミットしない。
- **反映のタイミング:** ラッパーと profile は、人間が sudo で再インストールするまで効かない。`claude/settings.json` と `.claude/settings.json` は、Edit ツールで変える（Bash からは書けない）。

<a name="review-focus"></a>

## 特に確かめること

1. **shebang の引数の分け方:** macOS が `#!/usr/bin/env -i <python> -I` を 3 つの引数に分けて `env` に渡すか。1 つにまとめると起動しない。Task 3 のテストで確かめる。
2. **空の環境変数での出力:** 環境変数が空（ロケールが C）の Python 3.9 で、日本語のメッセージを出せるか。Task 3 のテストで、日本語を含む拒否のメッセージを確かめる。
3. **マージ後の切り替え:** `~/dotfiles` を更新してから cc-crit を再インストールするまでの間、cc-crit は拒否する。設定の `denyRead` が profile で覆われていないため。PR の「マージ後の作業」に順番を書く。
4. **書けなくなるもの:** `./config`・`./vscode` などを `denyWrite` に入れると、Claude が mise のタスク（`sf:plugins`、`vscode:ext:list` など）で書き出していたものは失敗する。人間が実行する。
5. **CI の runner:** macOS の runner に、CLT の python3 と git の実体があるか（D1 の推奨案の場合）。
   - **あなたの Mac:** 両方あることを実測した。影響はない。
   - **今のテストのほとんど:** ラッパーを `/usr/bin/python3` からモジュールとして読み込むので、shebang の python3 のパスには左右されない。
   - **git を実行するテスト:** `cc-safe-push` の `evaluate()` などは、モジュールの `GIT` で git を実行する。CLT の git がないと、`test-cc-safe-push.py` と `test-cc-safe-pr.py` の多くが `FileNotFoundError` で失敗する。shebang を通す新しいテストも失敗する。
   - **パスがないときの影響:** 守りが緩むことはない（失敗するだけ）。ただし、CI で回帰を見つけられなくなる。
   - **確かめ方:** Task 3 で、CI の「Show interpreters」に 2 つの実体の `ls -l` を足し、最初の push で有無を確かめる。
   - **なかった場合:** 次のどちらにするかを相談する。
     - CI でだけ、テストの中で `GIT` を `/usr/bin/git` に差し替え、shebang のテストをスキップする（CI のテストの忠実さが少し下がる）。
     - D1 をもう 1 つの案に変える。

---

<a name="task-0"></a>

## Task 0: worktree に移る（D4）

この plan と調査の記録は、main checkout の作業ブランチ `fix/sandbox-escape-hardening` で書いた。Crit のレビューは、リポジトリのパスごとに session が分かれる。そのため、plan が承認されるまでは main checkout で続ける。

- [ ] 1. plan が承認されたら、main checkout で、この 2 つの文書をコミットする: `docs: plan sandbox escape hardening`
- [ ] 2. main checkout を `main` に戻す。そのうえで、`fix/sandbox-escape-hardening` を `.claude/worktrees/` に worktree として作り、EnterWorktree の `path` で移る。
- [ ] 3. worktree で、`check-repo.py` とテストが通ることを確かめてから、Task 1 に進む。

<a name="task-1"></a>

## Task 1: dotfiles の、sandbox の外で使われるファイルを守る（A4）

**ファイル:**

- `.claude/settings.json`
- `.github/scripts/check-repo.py`（`PROJECT_ASK`・`PROJECT_DENY_WRITE`、50〜68 行）
- `.github/scripts/test-check-repo.py`（同じ名前の定数、25〜45 行）

**変更後の一覧:**

`denyWrite` と `ask` の項目は、1 対 1 で対応させる。

| `denyWrite` | `ask` | 変更 |
| --- | --- | --- |
| `./claude` | （ユーザー設定の `Edit(~/dotfiles/claude/**)`） | そのまま |
| `./zsh` | `Edit(/zsh/**)` | そのまま |
| `./config` | `Edit(/config/**)` | `config/sheldon`・`config/starship` から広げる |
| `./mise`・`./mise.toml` | `Edit(/mise/**)`・`Edit(/mise.toml)` | そのまま |
| `./ghostty` | `Edit(/ghostty/**)` | `ghostty/config` から広げる |
| `./vscode` | `Edit(/vscode/**)` | `vscode/tasks.json` から広げる |
| `./bin`・`./codex`・`./biome`・`./obsidian`・`./aws` | `Edit(/bin/**)` など、同じ 5 つ | 追加 |
| `./init.command`・`./setup.command` | `Edit(/init.command)`・`Edit(/setup.command)` | 追加 |
| `./CLAUDE.md` | `Edit(/CLAUDE.md)` | 追加（D2） |

**手順:**

- [ ] 1. `check-repo.py` と `test-check-repo.py` の `PROJECT_ASK`・`PROJECT_DENY_WRITE` を、上の一覧に変える。
- [ ] 2. `python3 -B .github/scripts/check-repo.py` を実行する。
  - 期待: `project-permissions` が失敗し、`.claude/settings.json` に `./bin` などがないと報告する。
- [ ] 3. `.claude/settings.json` を、Edit ツールで上の一覧に変える。
- [ ] 4. `check-repo.py` と `test-check-repo.py` を実行する。
  - 期待: どちらも成功する。
- [ ] 5. 書き込みを確かめる。対象は、[research の 3 章](research-sandbox-escape.md#write-probe)で「書ける」だった 11 個と、`aws/config`・`setup.command`。方法は調査と同じで、書き込みモードで開くだけにする。
  - 期待: すべて拒否される。
  - 新しい設定がセッションに読み込まれていない場合（D4 の worktree など）は、マージした後に main checkout で確かめ、test-report に書く。
- [ ] 6. コミットする: `fix(claude): deny sandbox writes to dotfiles used outside the sandbox`

<a name="task-2"></a>

## Task 2: Crit の状態を Edit・Write ツールから守る（A2）

**ファイル:**

- `claude/settings.json`（`permissions.deny`）
- `check-repo.py` と `test-check-repo.py` の `CRIT_DENY`

**追加する規則:**

- `Edit(~/.crit/**)`
- `Edit(~/.crit.config.json)`
- `Edit(~/.cc-crit/**)`

理由: sandbox の外で動く crit（plan-hook と、人間が実行する crit）は、`~/.crit` の hooks・prompts・レビューを信頼する。Edit・Write ツールは sandbox を通らない。

**手順:**

- [ ] 1. 2 つのファイルの `CRIT_DENY` に、3 つの規則を足す。
- [ ] 2. `check-repo.py` を実行する。
  - 期待: `claude/settings.json: permissions.deny lacks Edit(~/.crit/**)` などで失敗する。
- [ ] 3. `claude/settings.json` に、Edit ツールで 3 つの規則を足す。
- [ ] 4. `check-repo.py` と `test-check-repo.py` を実行する。
  - 期待: 成功する。
- [ ] 5. コミットする: `fix(claude): deny edits to the crit state from file tools`

<a name="task-3"></a>

## Task 3: ラッパーを xcrun と環境変数から切り離す（A1）

**ファイル:**

- `claude/bin/cc-safe-push`（shebang と `GIT`）
- `claude/bin/cc-safe-pr`（shebang）
- `claude/bin/cc-crit`（shebang）
- `claude/hooks/tests/test-cc-safe-push.py`
- `claude/hooks/tests/test-cc-safe-pr.py`
- `claude/hooks/tests/test-cc-crit.py`
- `claude/README.md`（インストール手順の前提に、CLT を書く）
- `.github/workflows/ci.yaml`（「Show interpreters」に、CLT の python3 と git の実体の `ls -l` を足す。[特に確かめること](#review-focus)の 5）

**変更後（D1 の推奨案）:**

- shebang: `#!/usr/bin/env -i /Library/Developer/CommandLineTools/usr/bin/python3 -I`
- `cc-safe-push` の `GIT`: `/Library/Developer/CommandLineTools/usr/bin/git`

**テスト（3 本のテストのそれぞれに足す）:**

- `test_shebang_clears_env_and_skips_xcrun`
  - ラッパーの 1 行目が、上の shebang と一致することを確かめる。
- `test_ignores_caller_developer_dir`
  - 一時ディレクトリで、ラッパーのファイルを直接実行する（shebang を通す）。環境変数には `DEVELOPER_DIR=/nonexistent` と `PATH=/usr/bin:/bin` だけを渡す。
  - 期待:
    - 終了コードが 2。
    - stderr に、今のテストが使っている拒否のメッセージ（日本語）がある。
    - stderr に `xcrun` がない。

**手順:**

- [ ] 1. 2 つのテストを書く。
- [ ] 2. 3 本のテストを実行する（`/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py` など）。
  - 期待: 新しいテストが失敗する。shebang が一致せず、`xcrun: error: missing DEVELOPER_DIR path` で止まるため。
- [ ] 3. shebang と `GIT` を変える。
- [ ] 4. 3 本のテストを実行する。
  - 期待: すべて成功する。
  - 引数が分けられずに失敗した場合は、Review Focus 1 の結果として止まり、別の案（例: 小さな起動用のファイル）を相談する。
- [ ] 5. コミットする: `fix(claude): run the wrappers without xcrun or the caller environment`
- [ ] 6. 人間の作業: マージした後に、3 本を sudo で再インストールする（[claude/README.md](../../../claude/README.md#cc-safe-push-install) の手順）。

<a name="task-4"></a>

## Task 4: Lima の鍵を読ませない（A3）

**ファイル:**

- `claude/settings.json`（`sandbox.filesystem.denyRead` と `permissions.deny`）
- `claude/bin/cc-crit`（`COVERED_DENY_READ`）
- `claude/bin/cc-crit.sb`
- `check-repo.py`（新しい定数 `LIMA_DENY_READ`）と `test-check-repo.py`
- `claude/hooks/tests/test-cc-crit-profile.py`

**追加する規則:**

- `denyRead`:
  - `~/.colima/_lima/_config`
  - `~/.lima/_config`
- `permissions.deny`:
  - `Read(~/.colima/_lima/_config/**)`
  - `Read(~/.lima/_config/**)`
- `cc-crit.sb`: どちらにも、次の形で `; denyRead:` の行と拒否の規則を足す。

  ```scheme
  ; denyRead: ~/.colima/_lima/_config
  (deny file-read* (subpath (home-path "/.colima/_lima/_config")))
  ```

**手順:**

- [ ] 1. `check-repo.py` に、`LIMA_DENY_READ` と、その検査を足す。`test-check-repo.py` の、検査が通る設定の例も合わせる。
- [ ] 2. `check-repo.py` を実行する。
  - 期待: `sandbox.filesystem.denyRead lacks ~/.colima/_lima/_config` で失敗する。
- [ ] 3. `claude/settings.json` を、Edit ツールで変える。
- [ ] 4. `test-cc-crit.py` を実行する。
  - 期待: 設定の `denyRead` が `COVERED_DENY_READ` で覆われていないので、照合のテストが失敗する。照合のテストがなければ、先に足す。
- [ ] 5. `COVERED_DENY_READ` と `cc-crit.sb` を変える。
- [ ] 6. `test-cc-crit.py`・`check-repo.py`・`test-check-repo.py` を実行する。
  - 期待: すべて成功する。
- [ ] 7. `test-cc-crit-profile.py` に、偽の HOME の `.colima/_lima/_config/user` を読めないことを確かめるテストを足す。
  - sandbox の中ではスキップされる。人間が sandbox の外で実行する。
- [ ] 8. コミットする: `fix(claude): deny reading the Lima SSH keys from the sandbox`
  - 設定と profile は、同じコミットに入れる。設定だけが先に入った状態をブランチに残さないため。

<a name="task-5"></a>

## Task 5: unix ソケットと localhost を開けたら CI で失敗させる

**ファイル:**

- `check-repo.py`
- `test-check-repo.py`
- `CLAUDE.md`（cc-crit の節の、`allowLocalBinding` を使わない理由の隣）

**テスト:** `test_rejects_unix_socket_and_local_binding`

`claude/settings.json` が次のどれかを含むとき、エラーになることを確かめる。

- `sandbox.network.allowUnixSockets` が空でない
- `allowAllUnixSockets: true`
- `allowLocalBinding: true`

**CLAUDE.md に書く理由:** Colima は、既定で `$HOME` を書き込み可能でマウントする。Docker のソケットに届くと、`$HOME` のどこにでも書ける。

**手順:**

- [ ] 1. テストを書く。
- [ ] 2. テストを実行する。
  - 期待: 失敗する。
- [ ] 3. 検査を足す。
- [ ] 4. テストを実行する。
  - 期待: 成功する。
- [ ] 5. 今の設定で `check-repo.py` を実行する。
  - 期待: 成功する。
- [ ] 6. コミットする: `ci: fail when the sandbox opens unix sockets or local binding`
- [ ] 7. D3 で確かめることになった場合は、ソケットへの接続を 1 回試し、結果を test-report に書く。

<a name="task-6"></a>

## Task 6: 検証の記録とレビュー

- [ ] 1. CLAUDE.md の規約の、変更時に実行するものをすべて実行する。
  - フックの回帰テスト 4 本
  - ラッパーのテスト 3 本
  - `check-repo.py`、`test-check-repo.py`
  - shellcheck、actionlint
- [ ] 2. `test-report.md` を書く。実行したコマンドと結果、確かめられなかったことを書く。
- [ ] 3. Codex のレビューを受ける。`!` のコマンドを渡す。この PR では 5 回までにする。
- [ ] 4. 指摘への対応を、採用・不採用とその理由に分けて整理する。
- [ ] 5. 文書の `status` を `done` にしてコミットする。

<a name="task-7"></a>

## Task 7: push と PR

- [ ] 1. `cc-safe-push` で push し、`cc-safe-pr create` で PR を作る。`gh pr checks` で CI の結果を確かめる。
- [ ] 2. PR の「マージ後の作業」に、次の順番を書く。
  1. `~/dotfiles` を更新する。
  2. 3 本のラッパーを再インストールする。
  3. sandbox の外で `test-cc-crit-profile.py` を実行する。

<a name="out-of-scope"></a>

## 範囲外（別の作業にする）

- **GitHub Actions:** D5 を参照。
- **ほかのリポジトリの CLAUDE.md・AGENTS.md:** 別のタスクで調べてから、対策が要るかを決める（レビューで決定）。
  - 調べること: ユーザー設定の規則で、全リポジトリの承認がどれだけ増えるか。`denyWrite` に `**/CLAUDE.md` のような形を書いたときの動き。
- **ほかのリポジトリの git フックなどへの、Edit・Write ツールからの書き込み:** 別のタスクとして進める（レビューで決定）。
  - 対象は `.git/hooks`、`.vscode`、`.mcp.json`。
  - Bash からは sandbox-runtime が守っている。Edit・Write ツールで拒否しているのは `.git/config` だけ。
