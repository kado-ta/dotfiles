---
status: done
created: 2026-11-14
---

# cc-crit の競合と細かな不具合を直す（実装計画）

> [!NOTE]
> 実装は superpowers:executing-plans で、タスクごとに進める。手順はチェックボックス（`- [ ]`）で追う。

- **目的:** PR #15 の後に残った cc-crit の不具合を直す。次の 3 種類がある。
  - Codex が PR #15 で指摘した 2 件（同時に動かしたときの競合）
  - 実装レビューで後回しにした指摘
  - Finish の後の案内文
- **方針:** ラッパー（`claude/bin/cc-crit`）の中だけで直す。sandbox の設定と profile の権限は変えない（M9 のテストの追加を除く）。
- **技術:** Python 3.9（CLT の python3）、`fcntl.flock`、crit 0.23.2 のグローバル設定の `prompts`
- **根拠:**
  - [20261111_crit-sandbox/design.md の 10 章](../20261111_crit-sandbox/design.md#implementation-review)（後回しにした指摘）
  - PR #15 の Codex のレビュー（3 回目）の P2 の 2 件
  - [調べたこと](#findings)

関連: PR #15、PR #18、[20261113_sandbox-escape-hardening](../20261113_sandbox-escape-hardening/plan.md)

<a name="scope"></a>

## 範囲

| # | 内容 | 対応 |
| --- | --- | --- |
| B1 | Codex 1: 2 つのレビューが同時に信頼の設定を書くと、片方の項目が消える。消えた側は、Finish から先に進めなくなる（profile の中では、信頼の画面の選択を保存できない） | B2 と同じロックで直す（[Task 1](#task-1)） |
| B2 | Codex 2: 2 つのレビューが同じ空きポートを選ぶと、後の方が起動に失敗する（crit は同じポートでしか再試行しない） | 起動が終わるまで持つ排他ロック（[Task 1](#task-1)） |
| B3 | M8: 範囲内のポートが尽きると、既存の daemon につなぎ直すだけのときも失敗する | ポートが尽きても crit を動かし、つなぎ直せなかったときだけ失敗にする（[Task 2](#task-2)） |
| B4a | M2: ブラウザで開く URL が `localhost`。`::1` の同じポートで別のものが待ち受けていると、そちらにつながりうる | `127.0.0.1` で開く（[Task 3](#task-3)） |
| B4b | M4: `denyRead` の確認で、設定ファイルが FIFO だと読み込みで止まる | 通常のファイルかを確かめてから読む（[Task 4](#task-4)） |
| B5 | M1: 1 ラウンド目の待機を止めると、daemon も止まる。コードのコメントは「残る」と書いている | 挙動は変えず、コメントとスキルの記述を直す（[Task 6](#task-6)） |
| B6 | Finish の後の案内文が「`crit comment` で返信し、`crit --session` で次のラウンドへ」と書いている。この環境ではどちらも実行できない | 専用 HOME の crit の設定で、cc-crit の手順の案内文に差し替える（[Task 5](#task-5)、D2） |
| B7 | M7（必要なものが欠けたときに依頼ファイルが残る）、連結したときの分かりにくいメッセージ | 受け入れる。どちらも、フックが先に止めるため |
| C1 | M9: profile のテストに、`~/.crit` と AWS の credentials の読み取りの拒否がない | テストを足す（[Task 7](#task-7)） |
| C2 | シンボリックリンクを含むパスで、crit と cc-crit の信頼のキーが食い違わないか | コードで確認した（[調べたこと](#findings)の 1）。E2E は行わない（D4） |
| C3 | M3（T3 の根拠の記述） | 受け入れる。影響は profile の中にとどまるため |
| — | CI の「Show interpreters」の、CLT の `ls -l`（2026-11-14 に削除を決めた） | 別のコミットで消す（[Task 8](#task-8)） |
| D | crit・git・macOS を更新したときに、profile のテストを忘れずにやり直す | mise のタスクを作る（[Task 9](#task-9)、D5） |

<a name="findings"></a>

## 調べたこと

どれも、crit のソース（`4458cce`、インストール済みの 0.23.2）と、今の `cc-crit` で確かめた。

1. **信頼のキー（C2）:**
   - crit は、作業ディレクトリを `filepath.EvalSymlinks` で解決してから使う（`internal/daemon/daemon.go:163` の `ResolvedCWD`）。
   - cc-crit は、`os.getcwd()`（物理パス）から toplevel を探し、`os.path.realpath` でキーを計算する。
   - crit には `PWD` を渡していない。どちらもリンクを解決したパスになるので、食い違わない。
2. **つなぎ直し（B3）:** crit の client は、同じ session の daemon が生きていれば、`-p` を使わずにつなぐ（`internal/session/review_cli.go:71-78`）。新しく起動するときだけ、`-p` のポートで待ち受ける。
3. **承認と daemon:** 承認されると、crit は daemon を止める（`stopDaemonOnApproval`）。ポートを使い続けるのは、承認されていないレビューの daemon。
4. **1 ラウンド目の停止（B5）:** crit の client は、自分で daemon を起動したときだけ、シグナルで daemon も止める（`review_cli.go:105-106` の `installDaemonSignalHandler`）。
5. **Host の確認（B4a）:** crit は Host がループバックかを確かめ、`127.0.0.1` も受け付ける（`internal/server/server.go:266` の `checkHost`）。
6. **案内文（B6）:**
   - Finish の後の案内文は、テンプレート `on_finish_unresolved` から作られる。テンプレートの選び方は、次の優先順になっている（`internal/prompt/render.go:28-76`）。
     1. プロジェクトの設定（信頼したときだけ）
     2. グローバルの設定の `prompts`
     3. プロジェクトの `.crit/prompts`（信頼したときだけ）
     4. グローバルの `.crit/prompts`
     5. 既定
   - cc-crit はプロジェクトを信頼しない（`defaults`）ので、ラッパーが書く専用 HOME の `.crit.config.json` の `prompts` が使われる。値は `inline:` で始めれば、その場に書ける（`internal/prompt/template.go:19`）。
   - テンプレートの変数に `session_key` があるので、`cc-crit reply` に渡す session を案内文に入れられる。
   - 既定のテンプレートは `integrations/prompts/on_finish_unresolved.md` にある。

<a name="decisions"></a>

## 決めていただきたいこと

| # | 内容 | 推奨 | 理由・トレードオフ | 決定 |
| --- | --- | --- | --- | --- |
| D1 | 実装する場所 | **worktree で行う** | main checkout では、`claude/` の Edit のたびに確認の画面が出る（ユーザー設定の `ask` の `Edit(~/dotfiles/claude/**)`）。worktree では出ない。ただし、worktree を出た後は sandbox の設定が古いまま残るので、終わったら新しいセッションに切り替える（2026-11-14 に実測） | worktree で行う |
| D2 | B6（案内文の差し替え）を入れるか | **入れる** | 変更は `write_config` に `prompts` を 1 つ足すだけ。今の案内文に従うと、Claude が `crit comment` を実行して失敗する。代わりに、crit の版が上がってテンプレートの変数が変わると、案内文が「Review finished.」だけになる（crit はテンプレートの誤りでそこに戻る）。E2E と、版を上げたときの確認で見つける | 入れる |
| D3 | ロックを待つ時間 | **30 秒** | crit の起動は 1〜2 秒。先に動いている cc-crit の crit が起動の途中で止まった場合も、30 秒で「もう一度実行して」と返す | 30 秒 |
| D4 | シンボリックリンクを含むパスの E2E（C2） | **行わない** | [調べたこと](#findings)の 1 のとおり、コードで食い違わないことを確かめた | 行わない |
| D5 | 版の更新のときに profile のテストを忘れないための mise のタスク | — | レビューで追加が決まった | 作る（[Task 9](#task-9)） |

<a name="constraints"></a>

## 守ること

- **sandbox と権限:** sandbox の設定、`permissions`、`cc-crit.sb` の許可の範囲は変えない。
- **ロックの置き場所:** `~/.cc-crit/lock` に置く。Claude の sandbox からは読めない（`denyRead`）。profile からは書けない（profile が書けるのは、`crit-home/.crit` と `tmp` だけ）。
- **ロックを daemon に引き継がない:** ロックの fd は、crit に引き継がない（`O_CLOEXEC`）。引き継ぐと、daemon が終わるまでロックが外れない。
- **コミット:** main にコミットしない。1 コミットに 1 つの論理変更を入れる。Conventional Commits の形で、タイトルは英語、本文は日本語にする。
- **反映のタイミング:** ラッパーは、人間が sudo で再インストールするまで効かない。

<a name="review-focus"></a>

## 特に確かめること

1. **ロックがいつ外れるか:** crit の出力に `Started` / `Connected` の行が出た時点で外れること。daemon が動いている間は持ち続けないこと。
2. **ロックが外れない経路がないか:** crit が `Started` も `Connected` も出さずに終わった場合と、SIGTERM の場合にも外れること。
3. **新しい案内文が使われるか:** E2E で、Finish の後の出力が新しい案内文になっていることを確かめる。テンプレートの誤りで「Review finished.」に戻っていないこと。
4. **2 つのレビューを同時に開けるか:** E2E で、2 つのレビューを同時に開き、両方が別のポートで起動し、両方の Finish が通ること。
5. **ブラウザの記憶:** URL を `127.0.0.1` に変えると、ブラウザから見て別のサイトになる。localStorage に残っていた Crit の画面の設定は引き継がれない。

---

<a name="task-0"></a>

## Task 0: 作業場所

- [ ] 1. plan が承認されたら、main checkout のブランチ `fix/cc-crit-robustness` で、この plan をコミットする（`docs: plan cc-crit robustness fixes`）。
- [ ] 2. D1 で worktree になった場合は、PR #18 と同じ手順で移る。手順は次のとおり。
  1. main checkout を `main` に戻す。
  2. EnterWorktree で worktree を作る。
  3. ブランチ名を合わせ、fast-forward する。

<a name="task-1"></a>

## Task 1: 起動が終わるまでの排他ロック（B1・B2）

**ファイル:** `claude/bin/cc-crit`、`claude/hooks/tests/test-cc-crit.py`

**作るもの:**

- `LOCK_TIMEOUT = 30`
- `acquire_lock(base: Path) -> StartLock`
  - `base / "lock"` を `O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC` で開く。
  - 自分が持つ通常のファイルで、リンクが 1 つかを確かめる。
  - `flock(LOCK_EX | LOCK_NB)` を、0.2 秒おきに `LOCK_TIMEOUT` まで試す。取れなければ `Failed("another cc-crit is starting; retry")` にする。
- `StartLock.release()` は、何度呼んでもよい。
- **持つ範囲:**
  - `execute()` では、`prepare_home` の直後に取り、`write_config` の後まで持つ。
  - `review` では、`check_ports` から、crit の出力に `STARTED` か `CONNECTED` の行が出るまで持つ。行が出ないまま crit が終わったときは、`run_review` の `finally` で外す。
  - `reply` では、`write_config` の後に外す。

**テスト:**

- `test_config_write_waits_for_the_lock`
  - テストが `home/.cc-crit/lock` を `flock` で持ち、`LOCK_TIMEOUT` を 0.3 にする。
  - 期待:
    - `review` は 1 を返し、stderr に `another cc-crit is starting` を出す。
    - crit は呼ばれない。
    - `.crit.config.json` は作られない。
- `test_lock_is_released_after_the_daemon_starts`
  - 偽の crit に、新しいモード `lockcheck` を足す。`Started` の行を出した後、`HOME` の 1 つ上の `lock` を `LOCK_NB` で取れるかを 3 秒まで試し、結果を `root/lockcheck` に書く。
  - 期待: `acquired`。ロックの fd を crit に引き継いでいないことも、これで確かめられる。
- `test_reply_releases_the_lock_before_running_crit`
  - 偽の crit の `comment` でも、同じ確認をする。
  - 期待: `acquired`。

**手順:**

- [ ] 1. 3 つのテストを書く。
- [ ] 2. `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` を実行する。
  - 期待: `test_config_write_waits_for_the_lock` が失敗する（ロックがないので、review が成功する）。
  - 残りの 2 つは、ロックがない今は通る。外し忘れたときに失敗させるための、回帰のテスト。
- [ ] 3. ロックを実装する。
- [ ] 4. テストを実行する。
  - 期待: すべて成功する。
- [ ] 5. コミットする: `fix(claude): serialize cc-crit startup with a lock`

<a name="task-2"></a>

## Task 2: ポートが尽きても、つなぎ直しはできるようにする（B3）

**ファイル:** `claude/bin/cc-crit`、`claude/hooks/tests/test-cc-crit.py`

**変更:**

- `check_ports` は、範囲内の待ち受けがすべて cc-crit の crit であることを今までどおり確かめる。
  - 空きがあれば、そのポートを返す。
  - 空きがなければ `None` を返す。
- `run_review` は、`None` のときは `PORTS[0]` を `-p` に渡す。
  - 生きている session があれば、crit はそれにつなぐ。
  - なければ、crit は使用中のポートで待ち受けに失敗して終わる。
- crit が `Started` も `Connected` も出さずに 0 以外で終わり、かつポートが尽きていたときは、`FAILED: no free port is left for cc-crit; approve or close the open reviews and retry` を出す。
  - 今の案内（`crit stop`）は、利用者の HOME の crit を指すので、cc-crit の daemon には届かない。

**テスト:**

- 今の `test_no_free_port_fails` を、次の 2 つに置き換える。
  - `test_no_free_port_still_reconnects`
    - 全ポートを登録済みにし、偽の crit をモード `connected` にする。
    - 期待: 0 を返し、crit が呼ばれる。
  - `test_no_free_port_without_a_session_explains`
    - 偽の crit に、新しいモード `fail` を足す（待ち受けの失敗を出して 1 で終わる）。
    - 期待: 1 を返し、stderr に `no free port is left` を出す。
- `test_foreign_listener_in_the_range_is_denied` は、そのまま通ること。

**手順:**

- [ ] 1. テストを書く。
- [ ] 2. テストを実行する。
  - 期待: `test_no_free_port_still_reconnects` が失敗する。
- [ ] 3. 実装する。
- [ ] 4. テストを実行する。
  - 期待: すべて成功する。
- [ ] 5. コミットする: `fix(claude): let cc-crit reconnect when every port is taken`

<a name="task-3"></a>

## Task 3: ブラウザを 127.0.0.1 で開く（B4a）

**ファイル:** `claude/bin/cc-crit`（`open_browser`）、`claude/hooks/tests/test-cc-crit.py`

**変更:** `open_browser` の URL を `http://127.0.0.1:{port}/` にする。crit の出力を読む正規表現（`localhost`）は変えない。crit は `localhost` と出力するため。

**手順:**

- [ ] 1. `BrowserTests` の、期待する URL を `127.0.0.1` に変える。
- [ ] 2. テストを実行する。
  - 期待: 2 件が失敗する。
- [ ] 3. 実装する。
- [ ] 4. テストを実行する。
  - 期待: すべて成功する。
- [ ] 5. コミットする: `fix(claude): open crit reviews on 127.0.0.1`

<a name="task-4"></a>

## Task 4: denyRead の確認で、通常のファイルだけを読む（B4b）

**ファイル:** `claude/bin/cc-crit`（`check_deny_read`）、`claude/hooks/tests/test-cc-crit.py`

**変更:**

- 設定ファイルを `O_RDONLY | O_NONBLOCK | O_CLOEXEC` で開く。
  - リンクはたどる。`~/.claude/settings.json` は dotfiles へのリンクのため。
- `fstat` で通常のファイルかを確かめ、`MAX_REQUEST` まで読む。
  - 通常のファイルでなければ、`Denied(f"cannot read the sandbox settings in {path}")` にする。
- ファイルがなければ、今までどおり飛ばす。

**テスト:**

- `test_fifo_settings_are_denied`
  - リポジトリの `.claude/settings.local.json` を `os.mkfifo` で作る。
  - `check_deny_read` を別のスレッドで呼び、5 秒以内に `Denied` で終わることを確かめる。
  - 終わらなかったときは、FIFO を書き込みで開いて、止まっているスレッドを解放する。

**手順:**

- [ ] 1. テストを書く。
- [ ] 2. テストを実行する。
  - 期待: 失敗する（5 秒以内に終わらない）。
- [ ] 3. 実装する。
- [ ] 4. テストを実行する。
  - 期待: すべて成功する。
- [ ] 5. コミットする: `fix(claude): read only regular sandbox settings files in cc-crit`

<a name="task-5"></a>

## Task 5: Finish の後の案内文を cc-crit の手順にする（B6）

**ファイル:** `claude/bin/cc-crit`（`write_config`）、`claude/hooks/tests/test-cc-crit.py`、`claude/skills/crit-review/SKILL.md`

**変更:**

- `write_config` が書く設定に、`"prompts": {"on_finish_unresolved": FINISH_PROMPT}` を足す。
- `FINISH_PROMPT` は `inline:` で始める。中身は次の 4 つを満たすようにする。
  - 既定のテンプレートの 1〜3 行目（未解決の件数と、コメントの JSON）をそのまま使う。
  - 返信の方法として、`.cc-crit-request.json` に `{"session": "{{.session_key}}", "replies": [...]}` を書き、`/usr/local/libexec/claude-crit/cc-crit reply` を単独で実行するよう案内する。
  - 次のラウンドは、同じ依頼を書き直して `cc-crit review` を単独で実行するよう案内する。
  - `crit comment` と `crit --session` には触れない。
- 承認のとき（`on_finish_approved`）は、既定のまま使う。
- `SKILL.md` の「3. 結果を読む」に、出力の案内は cc-crit の手順で書かれていることを、1 文で足す。

**テスト:**

- `test_config_replaces_the_finish_prompt`
  - review の後、`.crit.config.json` の `prompts.on_finish_unresolved` を確かめる。
  - 期待:
    - `inline:` で始まる。
    - `{{.session_key}}` と `cc-crit reply` を含む。
    - `crit comment` を含まない。

**手順:**

- [ ] 1. テストを書く。
- [ ] 2. テストを実行する。
  - 期待: 失敗する。
- [ ] 3. 実装する。
- [ ] 4. テストを実行する。
  - 期待: すべて成功する。
- [ ] 5. コミットする: `fix(claude): point crit's finish prompt at cc-crit`

テンプレートが crit で正しく描画されるかは、Go のテンプレートなので、このテストでは確かめられない。[Task 10](#task-10) の E2E で確かめる。

<a name="task-6"></a>

## Task 6: 1 ラウンド目の停止の記述を直す（B5）

**ファイル:** `claude/bin/cc-crit`（`run_review` の `finally` のコメント）、`claude/skills/crit-review/SKILL.md`（「失敗したとき」）

**変更:**

- コメントを、実際の挙動に合わせる。
  - crit の client が daemon を起動したラウンドでは、daemon も止まる。
  - つなぎ直したラウンドでは、daemon は残る。
  - コメントはレビューのファイルに残るので、もう一度 `review` を実行すれば開き直せる。
- スキルにも、同じことを 1 項目足す。

**手順:**

- [ ] 1. コメントとスキルを直す。挙動は変えない。
- [ ] 2. テストを実行する。
  - 期待: すべて成功する。
- [ ] 3. コミットする: `docs(claude): describe what stopping the first crit round does`

<a name="task-7"></a>

## Task 7: profile のテストを足す（C1）

**ファイル:** `claude/hooks/tests/test-cc-crit-profile.py`

**テスト:** どれも、既存のテストと同じく実際の HOME を使う。対象がなければスキップする。

- `test_read_real_crit_denied`: `~/.crit` の一覧を読めない。
- `test_read_aws_credentials_denied`: `~/.aws/credentials` を開けない。
- `test_read_dotfiles_aws_credentials_denied`: `~/dotfiles/aws/credentials` を開けない。

**手順:**

- [ ] 1. テストを書く。
  - sandbox の中ではスキップされるので、先に失敗させるところは見られない。今の profile ですでに拒否している規則に、テストを足すだけ。
- [ ] 2. sandbox の外での実行を、人間に依頼する。
- [ ] 3. コミットする: `test(claude): cover crit state and AWS credentials in the profile tests`

<a name="task-8"></a>

## Task 8: CI の CLT の確認を消す

**ファイル:** `.github/workflows/ci.yaml`（「Show interpreters」の、CLT の実体の `ls -l` とそのコメントの 2 行）

**手順:**

- [ ] 1. 2 行を消す。
- [ ] 2. `actionlint` を実行する。
- [ ] 3. コミットする: `ci: drop the one-off CLT path listing`
- [ ] 4. メモリ `pending-ci-clt-ls-removal` を消す。

<a name="task-9"></a>

## Task 9: profile のテストをやり直す mise のタスク（D5）

**ファイル:**

- `mise.toml`（リポジトリの保守用のタスク）
- `CLAUDE.md`（mise タスクの一覧）
- `claude/README.md`（cc-crit の「インストール」と「更新するとき」）

**作るもの:**

```toml
[tasks."crit:profile-test"]
description = "cc-crit の profile のテストを実行する（sandbox の外で。crit・git・macOS を更新したら実行する）"
run = "/usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py"
```

- タスクは、テストを実行するだけにする。テストは先頭で crit・git・macOS の版を出力するので、記録として使える。
- README の 2 か所の手順を、`mise run crit:profile-test` に変える。CLAUDE.md の一覧にも足す。

**手順:**

- [ ] 1. タスクと文書を足す。`mise.toml` は Edit ツールで変える（Bash からは書けない）。
- [ ] 2. `check-repo.py`（TOML の構文の確認を含む）を実行する。
- [ ] 3. マージした後に、人間が通常のターミナルで `mise run crit:profile-test` を実行し、テストが動くことを確かめる。
  - worktree のパスは mise に信頼されていないので、マージ前には実行できない。
- [ ] 4. コミットする: `chore(mise): add a task to rerun the cc-crit profile tests`

<a name="task-10"></a>

## Task 10: 検証の記録とレビュー

- [ ] 1. CLAUDE.md の規約の、変更時に実行するものをすべて実行する。
- [ ] 2. 人間に、ブランチの `cc-crit` を再インストールしてもらう（PR #15 と同じく、マージ前に入れる）。そのうえで、sandbox の外で profile のテストを実行してもらう。
- [ ] 3. E2E を、Claude の Bash ツールから行う。
  1. 2 つのリポジトリで、`review` を同時に開く。両方が別のポートで起動し、ブラウザが開き、両方の Finish が通ること（[特に確かめること](#review-focus)の 4）。
  2. コメントを 1 つ付けて Finish する。出力が新しい案内文になり、案内どおりの `cc-crit reply` で返信できること（同じく 3）。
- [ ] 4. `test-report.md` を書く。
- [ ] 5. Codex のレビューを受ける（`!` のコマンドを渡す。この PR では 5 回まで）。
- [ ] 6. 文書の `status` を `done` にしてコミットする。

<a name="task-11"></a>

## Task 11: push と PR

- [ ] 1. `cc-safe-push` で push し、`cc-safe-pr create` で PR を作る。`gh pr checks` で CI の結果を確かめる。
- [ ] 2. PR に「マージ後の作業」を書く。
  1. `~/dotfiles` を更新する。
  2. `cc-crit` を再インストールする（Task 10 で入れた版と同じなら不要）。
  3. `mise run crit:profile-test` を実行する（Task 9 の確認）。
  4. 新しいセッションに切り替える（D1 で worktree を使ったため）。

<a name="out-of-scope"></a>

## 範囲外

- **E（crit の上流への報告）:** この作業の後に、下書きを作る。対象は次の 4 件で、B6 の案内文の件は、この作業での調べを反映する。
  - CSP がない
  - slug が衝突する
  - 待ち受けの再試行が、同じポートでしか行われない
  - B6 の案内文
- **PR #18 の範囲外の 3 つと、worktree を出た後に sandbox の設定が古いまま残る件:** 別の作業にする。
