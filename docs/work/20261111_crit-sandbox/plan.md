---
status: done
created: 2026-11-12
---

# cc-crit の実装計画

> **実装する人へ:** タスクごとに、テスト → 実装 → 検証 → コミットの順で進める。チェックボックス（`- [ ]`）で進み具合を記録する。

**目的:** Claude の Bash ツールから、sandbox を全体では緩めずに Crit の対話レビューを開けるようにする。

**構成:** root 所有の Python ラッパー `cc-crit`（`review` / `reply`）を `excludedCommands` の完全一致で sandbox の外で動かし、crit は Crit 専用の Seatbelt profile と専用の HOME の中で動かす。

**使うもの:** `/usr/bin/python3`（標準ライブラリだけ）、`sandbox-exec`（SBPL）、crit 0.23.2、Homebrew の git 2.56.0、macOS 26.7.1。

**設計:** [design.md](design.md)（承認済み、2026-11-12）。この計画は設計の 4〜8 章を実装する。

## 関連

- 設計: [design.md](design.md)
- 検証記録: [test-report.md](test-report.md)
- 手本にする既存のラッパー: `claude/bin/cc-safe-pr`、`claude/hooks/tests/test-cc-safe-pr.py`

<a name="constraints"></a>

## 全体の制約

- 作業ブランチは `feat/cc-crit`（`main` から切る）。`claude/settings.json` にある無関係な `credentials.envVars` の整形の差分は、どのコミットにも含めない。
- ラッパーは `#!/usr/bin/python3 -I` で標準ライブラリだけを使い、`sys.dont_write_bytecode = True` にする。`cc-safe-pr` と同じく、メッセージは英語、コメントは日本語にする。
- 終了コード: 0 成功、1 失敗、2 拒否（`cc-safe-*` と同じ）。
- **ラッパー自身は git を実行しない。** git を実行するのは、Crit 専用 profile の中の crit だけにする。
- インストール先: `/usr/local/libexec/claude-crit/cc-crit`（root:wheel 0755）と `cc-crit.sb`（root:wheel 0644）。
- 許可するコマンドは完全一致の 2 つだけ: `/usr/local/libexec/claude-crit/cc-crit review`、`/usr/local/libexec/claude-crit/cc-crit reply`。
- 専用 HOME は `~/.cc-crit/crit-home`（0700）。ポートの範囲は 47800〜47819。
- 依頼ファイルは `.cc-crit-request.json`。上限: 512 KiB、`files` は 20 件、`replies` は 50 件、`body` は 65536 文字。
- 実行ファイル: crit は `/opt/homebrew/bin/crit`、git は `/opt/homebrew/bin/git`、`/usr/bin/sandbox-exec`、`/usr/bin/open`。
- **Claude の sandbox の中からは profile を試せない**（入れ子の `sandbox-exec` は `sandbox_apply: Operation not permitted`【実測】）。profile のテストは、人間が `!` で実行する。
- profile を通すために、ワイルドカードの bind や広い mach-lookup が必要になったら、実装を止めて設計を見直す（[design.md の 4.4](design.md#profile)）。

<a name="review-focus"></a>

## 特に確かめること

テストが漏れやすく、実際に使うと踏みやすい入力と状態。どれも、担当するタスクのテストに含める。

1. リポジトリのサブディレクトリや git worktree（`.git` がファイル）から実行する → git を使わずに toplevel を見つけ、同じように動く（タスク 2）
2. 2 ラウンド目以降で、同じレビューの daemon がすでに動いている → ブラウザを二重に開かず、Finish まで待つ（タスク 3）
3. 専用 HOME に古い session ファイルが残り、その PID は死んでいて、ポートを別のプロセスが使っている → 範囲内の待ち受けとして拒否する（タスク 3）
4. 依頼ファイルの重複キー、BOM、不正な UTF-8、前回の残り → 拒否し、依頼ファイルは必ず消える（タスク 2）
5. Claude がバックグラウンドの実行を止める（SIGTERM） → crit の client は止まり、ブラウザは開かない。daemon は次のラウンドのために残る（タスク 3）

---

### タスク 0: 設計と検証記録のコミット

**ファイル:** `docs/work/20261111_crit-sandbox/{design,test-report,plan}.md`

- [ ] `git switch -c feat/cc-crit`（`git commit` とは別の Bash 呼び出しにする）
- [ ] `design.md` の `status` を `in-progress` にする
- [ ] `python3 -B .github/scripts/check-repo.py` が全項目 PASS
- [ ] コミット: `docs: add cc-crit design, plan and test report`

### タスク 1: Crit 専用 profile

**ファイル:**
- 作成: `claude/bin/cc-crit.sb`
- 作成: `claude/hooks/tests/test-cc-crit-profile.py`

**提供するもの:** profile は `-D` で 3 つの値を受け取る。`HOME_REAL`（ユーザーの本当の HOME）、`CRIT_HOME`（専用 HOME）、`PRIVATE_TMP`（専用の一時ディレクトリ）。

- [ ] **テストを書く。** `test-cc-crit-profile.py` は、`claude/bin/cc-crit.sb` を `(import ...)` し、探査用の `/usr/bin/python3` の実行だけを足したテスト用 profile を一時ファイルに作り、その中で探査を実行する。本番の profile には、python の実行を許可しない。
  - 先に `sandbox-exec -p '(version 1)(allow default)' /usr/bin/true` を試し、失敗したら（Claude の sandbox の中）`skipTest` する。`/opt/homebrew/bin/crit` がない環境（CI）でも `skipTest` する。
  - 許可されること:
    - 一時 git リポジトリで `crit --no-open -p 47800 -o $CRIT_HOME/.crit <file>` の daemon が起動し、テストのプロセス（profile の外）から `/api/health` が `{"status":"ok"}` を返す
    - 終わったら `crit stop` で止める
  - 拒否されること（探査で `PermissionError` か exit が 0 以外）:
    - 外部への接続: `1.1.1.1:443`
    - 待ち受け: `0.0.0.0:47801`、`[::]:47801`、`[::1]:47801`、`127.0.0.1:47900`（範囲外）
    - 範囲外の localhost への接続: テストのプロセスが開いた `127.0.0.1` の範囲外のポート
    - 書き込み: `$HOME_REAL/.crit/x`、`$HOME_REAL/x`、`$CRIT_HOME/.crit.config.json`
    - 読み取り: `$HOME_REAL/.ssh/config`（存在するときだけ）
    - `/usr/bin/open https://example.com`、`/usr/bin/osascript -e 'return 1'`
- [ ] **人間が実行して、失敗を確認する:** `! /usr/bin/python3 -B claude/hooks/tests/test-cc-crit-profile.py`（profile がまだないので失敗する）
- [ ] **`cc-crit.sb` を書く。** `(version 1)(deny default)` に、[design.md の 4.4](design.md#profile) の表の範囲だけを許可する。
  - ネットワーク: 47800〜47819 の各ポートについて、`(local ip "localhost:N")` の bind / inbound と `(remote ip "localhost:N")` の outbound を列挙する。
  - 実行: crit の実体（`/opt/homebrew/Cellar/crit/0.23.2/bin/crit`）と git の実体、`git` が呼ぶ `libexec/git-core` 配下。
  - 書き込み: `CRIT_HOME` の `.crit` 配下、`PRIVATE_TMP`、`/dev/null`。
  - 読み取り: 全体を許可し、`HOME_REAL` の `.ssh`、`.aws`、`Library/Keychains`、`.crit` などを拒否する（`claude/settings.json` の `sandbox.filesystem.denyRead` と `permissions.deny` の `Read(...)` に相当するもの）。
- [ ] **人間が実行して、全件 PASS を確認する。** 失敗したら、拒否されたものを足すか、テストの期待を見直す。足すたびに、それが制約に反しないかを確かめる。
- [ ] 版の記録: crit・git・macOS の版をテストの出力に表示する（[design.md の 8 章](design.md#verification)の 6）
- [ ] コミット: `feat(cc-crit): add the Crit-only sandbox profile`

### タスク 2: 依頼の読み込みと検証

**ファイル:**
- 作成: `claude/bin/cc-crit`（定数と、以下の関数）
- 作成: `claude/hooks/tests/test-cc-crit.py`（`cc-safe-pr` のテストと同じく `SourceFileLoader` で読み込む）

**提供するもの:**
- `claim_request() -> bytes`、`read_claimed(path: str) -> bytes`: `cc-safe-pr` と同じ契約。固定名を一意の名前に rename し、`O_NOFOLLOW | O_NONBLOCK` で開き、通常ファイル・所有者・`st_nlink == 1`・サイズを確かめ、必ず消す。ディレクトリが違い、`cc-safe-pr` を import すると信頼の範囲が広がるので、関数は写す。
- `parse_request(raw: bytes, op: str) -> dict[str, Any]`
  - `review` → `{"files": [str, ...]}`（省略時は `[]`）
  - `reply` → `{"session": str, "replies": [{"reply_to": str, "body": str}, ...]}`
  - 未知のキー、重複キー、型違い、空の `replies`、上限超え、`session` が `[0-9a-f]{12}` でない、`reply_to` が `c_[0-9a-f]{6,16}` でない、制御文字を含む `body`（改行とタブは許す）は `Denied`
- `find_toplevel(cwd: Path) -> Path`: 上にたどって、最初に `.git`（ディレクトリかファイル）がある場所を返す。なければ `Denied`
- `resolve_files(files: list[str], cwd: Path, top: Path) -> list[str]`: 各要素を `realpath` で解決し、`top` の配下の通常ファイルの絶対パスを返す。`-` で始まるもの、`top` の外、通常ファイルでないもの、`.git` の中は `Denied`

- [ ] テストを書く。`review` と `reply` の正常系と、上の拒否の各条件。特に次のもの:
  - 「特に確かめること」の 1（サブディレクトリ、`.git` がファイルの worktree）
  - 「特に確かめること」の 4（重複キー、BOM、不正な UTF-8、前回の残り。拒否しても依頼ファイルが消えること）
  - シンボリックリンクで `top` の外を指すファイル
- [ ] `/usr/bin/python3 -B claude/hooks/tests/test-cc-crit.py` が失敗する
- [ ] 実装する
- [ ] 同じコマンドで全件 PASS
- [ ] コミット: `feat(cc-crit): parse and validate review and reply requests`

### タスク 3: crit の起動・ブラウザ・返信

**ファイル:** 変更 `claude/bin/cc-crit`、`claude/hooks/tests/test-cc-crit.py`

**使うもの:** タスク 1 の profile の `-D` の 3 つの値、タスク 2 の関数

**提供するもの:**
- `prepare_home(home_real: Path) -> Path`: `~/.cc-crit/crit-home` と `.crit` を 0700 で作り、どの段もシンボリックリンクでなく、自分の所有であることを確かめる。作れなければ（Claude の sandbox の中で動いた場合）、`cc-crit を単独で実行して、sandbox の外で動かすこと` を案内して `EXIT_FAILED`（`cc-safe-push` の `762ffc3` と同じ）
- `repo_root_hash(project_dir: Path) -> str`: `"sha256:" + sha256(realpath).hexdigest()`（crit の `RepoRootHash` と同じ）
- `write_config(crit_home: Path, project_dir: Path, author: str) -> None`: `.crit.config.json` を `O_NOFOLLOW` で書き直す。内容は `host` 127.0.0.1、`no_update_check`、`no_integration_check`、`author`（`pwd` から得たログイン名）、`trusted_project_prompts` に `{repo_root_hash: {"mode": "defaults"}}`
- `crit_env(crit_home: Path) -> dict[str, str]`: [design.md の 4.3](design.md#design) の許可リストどおり
- `check_deny_read(home_real: Path, top: Path) -> None`: `~/.claude/settings.json`、`<top>/.claude/settings.json`、`<top>/.claude/settings.local.json` の `sandbox.filesystem.denyRead` を読む。各項目が、profile で拒否しているパスの一覧（定数 `COVERED_DENY_READ`。`cc-crit.sb` と同じ内容）に文字列として含まれなければ `Denied`。設定ファイルが読めない、または JSON として壊れているときも `Denied`
- `check_ports(registry: Path) -> int`: 範囲内の各ポートに `127.0.0.1` で接続を試し、つながったポートが専用 HOME の `sessions/*.json` に生きた PID で記録されていなければ `Denied`。空いているポートを 1 つ返す
- `run_review(files: list[str], cwd: Path) -> int`: profile の中で crit を起動し、出力をそのまま流す。`Started crit daemon at http://localhost:<port> (session <id>, PID <pid>)` の行を見たら `verify_endpoint` を通してから開く。`Connected to …` の行では、`/api/health` の `browser_clients` が `false` のときだけ開く。crit の終了コードを返す
- `verify_endpoint(registry: Path, port: int, pid: int) -> bool`: ポートが範囲内で、session ファイルの `port` と `pid` が一致し、`/api/health` が `ok`
- `run_reply(request: dict[str, Any], cwd: Path) -> int`: profile の中で `crit comment --session <id> --json --author 'Claude Code'` を実行し、標準入力には `reply_to` と `body` だけの配列を渡す
- `main() -> int`: 引数がちょうど 1 つで `review` か `reply` でなければ `EXIT_DENIED`。`sandbox-exec`、profile、crit のどれかがなければ、crit を起動せずに `EXIT_DENIED`（T10、fail closed）

- [ ] テストを書く。`sandbox-exec` と crit は、引数と環境変数を記録する偽の実行ファイルに差し替える（定数を `mock.patch`）。
  - 引数と環境変数が固定どおり（`GIT_CONFIG_GLOBAL=/dev/null` など。`GH_TOKEN` などが渡らない）
  - 設定ファイルの信頼のキーと値。`.crit.config.json` がシンボリックリンクなら拒否する
  - `check_ports`: 範囲内に記録のない待ち受けがあれば拒否する（「特に確かめること」の 3）
  - `check_deny_read`: プロジェクトの設定に、`COVERED_DENY_READ` にない `denyRead` があれば拒否する。設定ファイルが壊れていても拒否する
  - fail closed: `sandbox-exec`、profile、crit のどれかを存在しないパスに差し替えると、偽の crit が呼ばれずに `EXIT_DENIED`
  - 「特に確かめること」の 2: `Connected to …` の行で、`browser_clients` が `true` なら開かない
  - 「特に確かめること」の 5: SIGTERM で client の子プロセスを止め、`open` を呼ばない
  - `reply` の標準入力に `reply_to` と `body` 以外が入らない
- [ ] 失敗を確認 → 実装 → 全件 PASS
- [ ] コミット: `feat(cc-crit): run crit in its profile, open the browser and post replies`

### タスク 4: 設定・フック・リポジトリの検査

**ファイル:**
- 変更: `claude/settings.json`
  - `permissions.allow`: 2 つのコマンドと `Edit(**/.cc-crit-request.json)`
  - `sandbox.excludedCommands`: 2 つのコマンド
- 変更: `claude/hooks/validate-command.sh`、`claude/hooks/tests/test-validate-command.sh`
- 変更: `.github/scripts/check-repo.py`、`.github/scripts/test-check-repo.py`

- [ ] テストを書く。
  - `test-validate-command.sh`: 2 つのコマンドの単独実行は 0、`; echo` や `cd … &&` を付けたもの、引数の違うもの、サブコマンドなしは 2
  - `test-check-repo.py`:
    - `WRAPPER_COMMANDS` に 2 つを足したフィクスチャが PASS する
    - `Bash(/usr/local/libexec/claude-crit/cc-crit *)` を足すと FAIL する
    - 未知のラッパー（`Bash(/usr/local/libexec/claude-*/…)`）を足すと FAIL する
- [ ] 失敗を確認する
- [ ] 実装する。
  - `validate-command.sh`: `claude-crit` のパスも、`cc-safe-*` と同じ `case` で完全一致以外をブロックする
  - `check-repo.py`: 実際の値の抜き出しを `"cc-safe" in rule` から `/usr/local/libexec/claude-` で始まる `Bash(...)` に変える
  - `settings.json`: 変更には承認が要る（`ask` のルール）
- [ ] 全件 PASS を確認する。実行するもの: `bash claude/hooks/tests/test-validate-command.sh`、`python3 -B .github/scripts/test-check-repo.py`、`python3 -B .github/scripts/check-repo.py`
- [ ] `settings.json` は、この作業の差分だけをステージする（`git diff` から作った差分を `git apply --cached` で当てる）
- [ ] コミット: `feat(cc-crit): allow the exact cc-crit commands and guard chained runs`

### タスク 5: スキルと文書

**ファイル:**
- 作成: `claude/skills/crit-review/SKILL.md`
- 変更: `claude/README.md`（`cc-crit` の節。使い方、インストール、更新、アンインストール）、`CLAUDE.md`（Claude Code 設定の節と、規約のテストの一覧）

- [ ] `SKILL.md` に書く手順:
  1. `.cc-crit-request.json` を Write ツールで書く
  2. `/usr/local/libexec/claude-crit/cc-crit review` を単独で、`run_in_background: true`、`timeout: 86400000` で実行する
  3. 出力を読む
  4. 返信は `cc-crit reply` で行う
  5. 再実行で次のラウンドに進む
  - 禁止事項: `crit` を直接実行しない、`--resolve` しない、ほかのコマンドと連結しない
- [ ] README のインストール手順（人間が通常のターミナルで実行する）:

  ```sh
  sudo install -d -o root -g wheel -m 0755 /usr/local/libexec/claude-crit
  sudo install -o root -g wheel -m 0755 claude/bin/cc-crit /usr/local/libexec/claude-crit/cc-crit
  sudo install -o root -g wheel -m 0644 claude/bin/cc-crit.sb /usr/local/libexec/claude-crit/cc-crit.sb
  grep -qxF '.cc-crit-request.json' ~/.config/git/ignore || echo '.cc-crit-request.json' >> ~/.config/git/ignore
  ```

- [ ] 検査を実行する: `check-repo.py`（markdown-links を含む）、shellcheck、actionlint
- [ ] コミット: `docs(cc-crit): add the crit-review skill and install steps`

### タスク 6: インストールと端から端までの検証（人間と一緒に行う）

- [ ] 人間がタスク 5 のインストール手順を実行し、`claude/setup.sh` でスキルのリンクを作る（Claude Code のセッションをすべて閉じた、通常のターミナルで）
- [ ] [design.md の 8 章](design.md#verification)の 2〜5 を行う。
  - 2: `/crit-review` でファイルと差分をレビューし、コメント → Finish → `cc-crit reply` → 再実行 → 承認まで通す
  - 3: タスク 1 のテスト
  - 4: `.crit/hooks` を置いたリポジトリ
  - 5: 異常終了
- [ ] 結果を `test-report.md` に書き、`design.md` と `test-report.md` の `status` を `done` にする
- [ ] ブランチ全体のレビューを行う（新しいレビュアーと Codex。Codex はこのタスクの 3 回目）
- [ ] コミット: `docs: record cc-crit verification`
- [ ] push と PR の作成は、ユーザーの指示を待つ
