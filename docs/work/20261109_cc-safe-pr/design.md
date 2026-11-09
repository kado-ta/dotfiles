---
status: done
created: 2026-11-09
---

# Claude Code の PR 作成・編集を条件付き自動承認する仕組みの設計

根拠の表記: 【実測】このセッションで確認 / 【公式】公式ドキュメント / 【コード】ソース / 【推測】 / 【未確認】

## 1. 結論

**root 所有のラッパー `cc-safe-pr` を新設し、`cc-safe-push` と同じ「引数固定の完全一致 allow + `excludedCommands`」で動かす。** 入力は作業ディレクトリの固定 JSON ファイルで渡し、GitHub には `gh pr` を使わず REST API を標準ライブラリで直接呼ぶ。`cc-safe-push` は 1 行も変えず、インストール済みのものを読み込んで判定を再利用する。

```text
/usr/local/libexec/claude-push/cc-safe-pr create   # .cc-pr-request.json を読んで PR を作る
/usr/local/libexec/claude-push/cc-safe-pr edit     # 同じファイルを読んで PR の title/body を変える
```

候補案から変える点と理由:

| 候補案 | 変更 | 理由 |
| --- | --- | --- |
| PreToolUse Hook で認可 | 認可には使わない | フックの `allow` では `ask` ルールを上書きできず、失敗時は既定で通過する【公式】 |
| ラッパーから `gh pr` を実行 | REST 直呼び。`gh` は `gh auth token` だけ | 暗黙の push / fork、cwd の git 読み取り、環境変数の影響を丸ごと消せる |
| `gh` はサンドボックス外 | 誤り。`gh` エントリは削除 | `excludedCommands` の `gh` は引数なしの完全一致【公式】。`gh` はサンドボックス内で動いている【実測】 |
| マージは自動承認しない | **追加対策が必要** | 現行の `ask` は `gh pr -R x merge 1` と `gh pr new` で迂回できる【実測】 |

> [!WARNING]
> **この設計（Phase 1）は「通常運用での確実な承認フロー」を作るものであり、Claude を敵対者とみなしたときの境界ではない。** `repo` スコープのトークンがサンドボックス内から Keychain 経由で読め【実測】、`api.github.com` にも到達できるため、悪意あるコードはマージも含めて API を直接呼べる。この穴は Permission / Hook では塞げない。塞ぐには [12 章](#residual) の Phase 2 と GitHub 側のルールセットが必要。

**要件の定義（2026-11-09 にユーザーが決定）**: 「未許可リポジトリは人間の承認が必須」「マージ・クローズは自動承認しない」は、**Claude が通常使うコマンド表記について**成立させる。意図的な迂回（`python` での API 直呼び、変数展開など）は Phase 1 の対象外とし、資格情報の隔離は別タスクで扱う。

<a name="boundary"></a>

### 保証できる範囲の分離

| 層 | 保証すること | 保証しないこと |
| --- | --- | --- |
| `cc-safe-pr`（root 所有、外部プロセス） | 実行された場合の操作先・操作種別・入力の検証 | ラッパーを通らない操作 |
| Permission `ask` / Hook `ask` | Claude が普通に書くコマンドに人間の承認を要求する | 別の形での呼び出し（公式が「セキュリティ境界ではない」と明言） |
| Sandbox（Seatbelt） | ファイル書き込みと接続先の制限、`.git/config` と hooks の保護 | `*.github.com` への API 呼び出し、Keychain の読み出し |
| GitHub 側（トークン権限・ルールセット） | **唯一の強制力**。権限のない操作はサーバーが拒否する | 現状のトークンは `repo` で全権。ルールセットも未確認 |

## 2. 現状調査

| 対象 | 結果 |
| --- | --- |
| バージョン | Claude Code 2.1.311 / gh 2.103.3 / `/usr/bin/git` 2.54.0 / `/usr/bin/python3` 3.9.6（LibreSSL 2.8.3）/ codex-cli 0.167.0【実測】 |
| ローカルと GitHub | `HEAD`（`34d51c0`）と GitHub の最新マージコミットが一致し、`origin/main` との差もなし。追跡ファイルの差はない。未追跡の `claude/skills/obsidian-portable-markdown/` のみ【実測】 |
| インストール済みラッパー | `cmp` で `claude/bin/cc-safe-push` と完全一致。`/usr/local/libexec/claude-push/` と `/usr/local/etc/claude-push/` は `root:wheel` で 0755【実測】 |
| 許可リスト | `kado-ta/dotfiles` と 組織のリポジトリ の 2 件。スキーマは `version` + `allowList[{gitCommonDir, github}]` の厳密一致（`cc-safe-push:133,139`） |
| gh 認証 | `kado-ta`、keyring 保存、スコープ `gist, read:org, repo`。`gh` の実体はユーザー所有（root 所有ではない）【実測】 |
| テスト | `test-cc-safe-push.py` は `SourceFileLoader` で読み込み、`policy.evaluate(cwd, config)` を直接検証する形式 |

**調査で判明した問題（既存）**

| # | 内容 | 根拠 |
| --- | --- | --- |
| F1 | `excludedCommands` の `"gh"` は `gh` 単独にしか一致せず、実質無効。`gh pr …` はサンドボックス内で動く | 【公式】`docker` は引数なしの `docker` のみに一致 |
| F2 | サンドボックス内の `gh` は Keychain のトークンで API に到達できる。`env -i` でも同様 | 【実測】`SANDBOX_RUNTIME=1` の環境で `gh auth status` がスコープまで取得 |
| F3 | `gh pr new`（`create` の別名）は `Bash(gh pr create*)` に一致しない | 【実測】`gh pr create --help` の ALIASES |
| F4 | `gh pr -R x …` と `gh -R x pr …` はどちらも通る。`Bash(gh pr merge*)` に一致せず、`Bash(gh *)` に一致して承認なしで動く | 【実測】`list` で構文を確認（`merge` は未実行）【公式】優先順位 |
| F5 | `gh pr ready / reopen / revert / update-branch / lock` は `ask` になく、承認なしで動く | `settings.json:158-174` |
| F6 | `autoAllowBashIfSandboxed` は既定 `true`。`Bash(gh *)` を allow から外しても、サンドボックス内では承認は増えない。効くのは `ask` / `deny` とフックだけ | 【公式】 |
| F7 | `validate-command.sh` は本文の `prod` にも反応するため、`gh pr create --title "...prod..."` はブロックされる。JSON 方式では起きない | `validate-command.sh:25` |

## 3. 公式仕様

| 項目 | 仕様 | 出典 |
| --- | --- | --- |
| 優先順位 | "Rules are evaluated in order: deny, then ask, then allow."。より具体的な allow があっても ask が勝つ | [permissions](https://code.claude.com/docs/en/permissions) |
| 一致の形式 | "A rule with no `*` matches one exact command." | 同上 |
| 複合コマンド | 区切りは `&&` `\|\|` `;` `\|` `\|&` `&` と改行。ask / deny はサブシェルやコマンド置換の中でも一致する | 同上 |
| 環境変数の前置 | "A deny or ask rule matches past any leading assignment"。allow は既知の安全な変数のみ | 同上 |
| ルールの限界 | "a deny or ask rule covers the invocation Claude usually produces and isn't a security boundary around the program." | 同上 |
| auto mode の ask | "Ask rules that match on a command's content, such as `Bash(git push *)`, fall back to a permission prompt" | [permission-modes](https://code.claude.com/docs/en/permission-modes) |
| フックの allow と ask | "a matching ask rule still prompts even when the hook returned `\"allow\"` or `\"ask\"`." | [permissions](https://code.claude.com/docs/en/permissions) |
| auto mode のフック ask | "a PreToolUse hook's `\"ask\"` normally sends the tool call to the permission prompt, and the classifier doesn't decide it." | [hooks](https://code.claude.com/docs/en/hooks) |
| 複数フック | `deny` > `defer` > `ask` > `allow` | 同上 |
| フックの失敗 | タイムアウトやエラーでは "The action goes ahead"。`onFailure: "block"` で変更できる（2.1.295+。本体に実装あり【実測】） | 同上 |
| `excludedCommands` | "`docker` matches only `docker` with no arguments."。全コマンドの一致が必要。"a redirect to a file, a `cd`, or a command substitution such as `$(...)` keeps the whole call sandboxed."。`/usr/local/bin/docker` は `docker` に一致しない | [sandboxing](https://code.claude.com/docs/en/sandboxing) |
| 除外コマンドの権限 | 通常の権限フローを通る。allow に一致すれば承認なし。"An excluded command runs with your full access." | 同上 |
| `allowUnsandboxedCommands: false` | `dangerouslyDisableSandbox` を無視し、除外コマンド以外はサンドボックス内で動く | 同上 |
| `failIfUnavailable: true` | サンドボックスを使えないときは起動を拒否する | 同上 |
| 保護パス | 作業ディレクトリの `.git` の `hooks` と `config`、`.gitconfig`、シェル設定など | 同上 |
| Go 製 CLI の TLS | "Tools such as `gh`... may fail TLS verification under Seatbelt."。本環境は `enableWeakerNetworkIsolation: true` で動作【実測】 | 同上 |
| `gh pr create --head` | "Use `--head` to explicitly skip any forking or pushing behavior." | [gh_pr_create](https://cli.github.com/manual/gh_pr_create) |
| `--repo` の解決 | `--repo` > `GH_REPO` > git remote（`repo_override.go` v2.103.3） | 【コード】 |
| URL セレクタ | `gh pr edit <URL>` は `--repo` より URL を優先する（`edit.go`, `finder.go`） | 【コード】 |
| トークン保存 | macOS は go-keyring 経由で `/usr/bin/security find-generic-password` を呼ぶ | 【コード】`keyring_darwin.go` |
| REST | `POST /repos/{o}/{r}/pulls`（`head`, `base`, `title`）/ `PATCH .../pulls/{n}`（`title`, `body`, `state`, `base`）。`state: closed` は PATCH で可能 | [pulls](https://docs.github.com/en/rest/pulls/pulls) |

## 4. 設計案の比較

### 4.1 認可方式

| 案 | セキュリティ | 既存への影響 | 実装量 | 判定 |
| --- | --- | --- | --- | --- |
| 1. 独立ラッパーが `cc-safe-push` を読み込む | ◎ 判定は 1 か所 | **なし** | 小 | **採用** |
| 2. 共通モジュールを抽出 | ◎ | `cc-safe-push` の改修と再検証が必要 | 中 | 不採用（「push の維持が最優先」に反する） |
| 3. 判定ロジックをコピー | △ 二重実装がずれる | なし | 中 | 不採用 |
| 4. Hook のみ | × シェル文字列の解析に依存し、既定で fail-open。`ask` も上書き不可 | 大 | 小 | 不採用 |

案 1 のリスクは `cc-safe-push` の内部 API（`evaluate`, `Decision`, `user_home`）への依存。読み込みに失敗すれば拒否になり、回帰テストでも検出する。

### 4.2 入力方式

| 観点 | JSON ファイル | CLI 引数 |
| --- | --- | --- |
| 権限ルール | 完全一致で済む | ワイルドカードが必要。`$()` が許可側に効くかは【公式に記載なし】 |
| シェル解釈 | なし | 本文のバッククォートや `$` でコマンド実行の危険 |
| 改行 | 問題なし | 改行はコマンド区切り扱い |
| フック誤検知 | なし（F7 を解消） | 本文の `prod` でブロック |
| 欠点 | ファイルの安全な読み取りと、1 回限りの確保が必要（7 章） | — |

**JSON ファイルを採用する。** 配置は**カレントディレクトリ直下の固定名**（`.cc-pr-request.json`）。`$TMPDIR` はセッション間で共有され、別リポジトリの依頼を誤って消費しうるので使わない。

### 4.3 GitHub の呼び出し方

| 観点 | `gh pr create/edit` | REST 直呼び（`http.client`） |
| --- | --- | --- |
| 暗黙の push / fork | `--head` が必須 | 構造上なし |
| cwd の git 読み取り、`GH_*`、エイリアス | 影響を受ける | 受けない |
| 実行するバイナリ | ユーザー所有の `gh` で本処理 | トークン取得のみ |
| 結果の判定 | stdout とエラー文の解釈 | ステータスと JSON で正確に判定 |
| コスト | 少ない | 約 40 行 |

**REST を採用する。** `http.client` はプロキシ環境変数を読まず、`cafile` を明示すれば `SSL_CERT_FILE` も影響しない。

### 4.4 認証

SSH（1Password）は `git push` 専用で PR API には使えない。PR には別の API 認証が必要。

| 方式 | 最小権限 | 運用 | サンドボックスからの到達 | 判定 |
| --- | --- | --- | --- | --- |
| 既存 `gh auth`（`repo`） | × 全リポジトリに全権 | 追加作業なし | 到達可能（現状） | **Phase 1** |
| Fine-grained PAT | ○ リポジトリと権限を限定。`Pull requests: write` のみならマージ不可の見込み【未確認: 要約経由】 | 期限更新。組織リポジトリは承認が必要な場合あり | `denyRead` のファイルに置けば遮断可能 | Phase 2 |
| GitHub App | ◎ 1 時間トークン、bot 名義 | 秘密鍵管理、JWT に外部依存 | 同上 | 現時点では過剰 |

> [!IMPORTANT]
> PAT を追加しても、`repo` スコープの既存トークンがサンドボックスから読める限り最小権限にはならない。PAT の効果は Keychain の遮断とセットで初めて得られる。

root 所有の `gh` は不要。`/opt/homebrew` はサンドボックスから書けず、書ける主体はすでにトークンにも到達できるため、root 化で防げる脅威が増えない。

## 5. 最終アーキテクチャ

```text
Claude ── Write ──> ./.cc-pr-request.json
Claude ── Bash（単独・完全一致）──> cc-safe-pr create|edit     ← allow + excludedCommands
                                     │（sandbox 外、root 所有、python -I）
       ├─ cc-safe-push の evaluate(cwd)  ……許可リスト / common dir / origin / 保護ブランチ
       ├─ 依頼ファイルを原子的に確保して読み、すぐ消す（1 回限り）→ スキーマ検証
       ├─ gh auth token（最小環境、cwd=/）
       └─ GET で事前検証 → 監査ログ → POST / PATCH → 応答を検証 → 監査ログ

未許可リポジトリ: ラッパーが exit 2 → Claude が gh pr create → ask ルール → 人間の承認
```

## 6. Permission / Hook / Sandbox の設定案

`claude/settings.json`:

```diff
 "allow": [
   "Bash(/usr/local/libexec/claude-push/cc-safe-push)",
+  "Bash(/usr/local/libexec/claude-push/cc-safe-pr create)",
+  "Bash(/usr/local/libexec/claude-push/cc-safe-pr edit)",
+  "Edit(**/.cc-pr-request.json)",
 "deny": [
+  "Bash(gh auth token*)",
+  "Bash(gh auth status*--show-token*)",
+  "Bash(gh auth status* -t*)",
+  "Bash(gh auth git-credential*)",
+  "Edit(~/Library/Logs/cc-safe-pr/**)",
 "PreToolUse": [
+  { "matcher": "Bash", "hooks": [{ "type": "command",
+      "command": "~/.claude/hooks/ask-gh-pr-write.sh", "timeout": 30, "onFailure": "block" }] },
 "PostToolUse": … test("gh pr create") → test("gh pr create|cc-safe-pr create")
 "excludedCommands": [
-  "gh",
   "/usr/local/libexec/claude-push/cc-safe-push",
+  "/usr/local/libexec/claude-push/cc-safe-pr create",
+  "/usr/local/libexec/claude-push/cc-safe-pr edit"
```

既存の `Bash(gh pr create*)` などの `ask` はそのまま残す（未許可リポジトリの承認経路）。`Bash(gh *)` の allow は既存ポリシーなので変えない（F6 のとおり外しても効果がない）。

**追加する deny の意図**: `gh auth` の 4 行は、Claude の Bash ツールからトークンの値を表示させる直接の手段を塞ぐ。

| ルール | 塞ぐもの |
| --- | --- |
| `Bash(gh auth token*)` | トークンを標準出力に出す |
| `Bash(gh auth status*--show-token*)`、`Bash(gh auth status* -t*)` | `gh auth status` の表示にトークンを含める |
| `Bash(gh auth git-credential*)` | Git の認証情報ヘルパーからトークンを取り出す |

`gh` がトークンを使って API を呼ぶこと自体は止めない（止めると `gh pr view` も動かない）。`/usr/bin/security` や Python で Keychain を読む経路も残るので、セキュリティ境界ではない（F2）。ラッパーが内部で実行する `gh auth token` は Bash ツールを通らないので、この deny の影響を受けない。

`claude/hooks/ask-gh-pr-write.sh`（表記ゆれを人間の承認に回す。境界ではない）:

**役割**: Claude の Bash ツール呼び出しのたびに実行され、コマンドに「`gh` による PR の書き込み」か「`gh api`」が含まれていれば、人間の承認画面を出すよう Claude Code に伝える。それ以外は何も返さず、通常の権限判定に任せる。

**必要な理由**: `permissions.ask` はコマンドの書き出しの形でしか一致しない。`gh pr new`、`gh pr -R x merge 1`、`/opt/homebrew/bin/gh pr create`、`env GH_REPO=x gh pr create` は一致せず、承認なしで動くか、auto mode の分類器の判断になる。フックの `ask` は分類器を通らず承認画面に進む【公式】ので、「未許可リポジトリは人間が承認する」という要件を、こうした表記でも満たせる。

**処理の流れ**:

1. `set -euo pipefail` と `trap` で、途中の失敗をすべて exit 2（ブロック）にする。
2. `jq` で標準入力の JSON から `.tool_input.command` を取り出す。文字列でなければ失敗にする。同時に、行継続（バックスラッシュ + 改行）と引用符を取り除き、`"gh" pr merge` や改行で分割した表記を `gh pr merge` と同じ形にする。
3. `grep -E` で次の並びを探す。
   - `gh` という語（`/opt/homebrew/bin/gh` は対象、`my-gh` や `cc-safe-pr` は対象外）
   - `-R x` などのオプション（0 個以上）
   - `pr`、オプション（0 個以上）、書き込みの動詞（`create`, `new`, `edit`, `merge`, `close`, `ready`, `reopen`, `revert`, `update-branch`, `lock`, `unlock`, `review`, `comment`）。または `api`
4. 結果に応じて動作する。

| grep の結果 | フックの動作 | Claude Code の動作 |
| --- | --- | --- |
| 一致 | `permissionDecision: "ask"` の JSON を出力して exit 0 | 承認画面を表示する |
| 不一致 | 何も出力せず exit 0 | 通常の権限判定（`gh pr view` はこれまでどおり） |
| grep や jq の失敗 | exit 2 | そのコマンドをブロックする |

**しないこと**: 許可リストは見ない（判定はラッパーの役割）。`allow` は返さない（フックで承認を省略できる経路を作らない）。`cc-safe-pr` のコマンドは `gh` の語を含まないので反応しない。

```bash
#!/bin/bash
# gh の PR 書き込みと API 呼び出しの表記ゆれを、auto mode でも人間の承認に回す。
# 別の形で呼ばれれば素通りするので、セキュリティ境界ではない。誤検知は確認が増えるだけ。
set -euo pipefail
# 途中の失敗は exit 2 にそろえ、onFailure の設定に依存せずブロックする。
trap 'exit 2' ERR
# 行継続と引用符を除き、`gh pr \<改行> merge` や `"gh" pr merge` を同じ形にそろえる。
# bash の ${var//…} は引用符が多いと極端に遅く、長いコマンドがタイムアウトでブロックされるので jq で行う。
COMMAND=$(jq -er '.tool_input.command | strings | gsub("\\\\\n"; "") | gsub("[\"\\x27]"; "")') || {
  echo "Blocked: jq failed, so this command cannot be checked." >&2
  exit 2
}
OPT='([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*'
GH="(^|[^[:alnum:]_.-])gh${OPT}[[:space:]]+"
VERB='(create|new|edit|merge|close|ready|reopen|revert|update-branch|lock|unlock|review|comment)'
codes=(0 0)
# 入力側と照合側の両方の失敗を検出するために PIPESTATUS を使う。-q は入力側が SIGPIPE で失敗するので使わない。
printf '%s\n' "$COMMAND" | grep -E "${GH}(pr${OPT}[[:space:]]+${VERB}|api)([^[:alnum:]-]|\$)" >/dev/null || codes=("${PIPESTATUS[@]}")
[ "${codes[0]}" -eq 0 ] && [ "${codes[1]}" -le 1 ] || exit 2
if [ "${codes[1]}" -eq 0 ]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask",
          permissionDecisionReason: "gh の PR 書き込みは人間の承認が必要です"}}'
fi
```

検証: 上記の本文を bash 3.2 で実行し、`ask` 13 件と無出力 7 件が期待どおり。`command` が null・キーなし、空の stdin、不正 JSON は exit 2。入力側と照合側それぞれの故障注入も exit 2。引用符を含む 27KB のコマンドは 2 秒【実測】。`trap ERR` は `set +e` の下でも発火するので、一致なしを失敗と誤認しないよう `||` の形にしている。

既知の挙動（テストで固定する）: `$(which gh)`、変数展開、`eval`、gh エイリアス、`env -S'gh pr merge 1'`、`gh pr $'merge' 1` は見逃す。`git commit -m "…gh pr create…"`、`grep "gh api"`、`echo gh pr merge` は誤検知になる（確認が増えるだけ）。

> [!NOTE]
> `jq` の式では単一引用符を `\\x27`（正規表現のエスケープ）で表す。Unicode エスケープで書くと、ツール経由の受け渡しで単一引用符そのものに変換され、シェルの引用が閉じて式が壊れた【実測】。

**環境ごとの動作**

| 環境 | 許可リポジトリ（ラッパー） | 未許可リポジトリ（`gh pr …`） |
| --- | --- | --- |
| Sandbox ON + auto | 承認なし | ask → 人間の承認 |
| Sandbox OFF + auto | 承認なし（allow が効く） | 同上 |
| default | 承認なし | 承認あり |
| plan | `useAutoModeDuringPlan` が有効なら分類器が審査。allow 一致時の扱いは【未確認】 | 同左 |
| dontAsk | 承認なし | `ask` に一致した呼び出しは拒否される【公式】 |

## 7. ラッパーの詳細設計

**呼び出し**: 引数は `create` か `edit` のどちらか 1 つだけ。カレントディレクトリに `.cc-pr-request.json` を置き、そのディレクトリで単独実行する。`cd … &&` を付けるとサンドボックス内に留まるので、監査ログを開けずに拒否される。

**終了コード**: `0` 成功 / `1` 失敗（変更なし）/ `2` 拒否 / `3` 要確認（送信後の切断、5xx、応答の検証不一致。PR が作成・変更されている可能性があり、分かる場合は URL を表示する）。

> [!IMPORTANT]
> **不変条件: ラッパーは `evaluate()` の外で git を実行しない。** `git ls-files` など index を読むコマンドは `core.fsmonitor` を起動し、`core.hooksPath=/dev/null` では止まらない【実測】。`.git` ファイルを差し替える競合や `config.worktree` を使うと、サンドボックス外で任意コードが動く可能性がある【未検証】。`evaluate()` が使う git では、設定 27 件を注入しても外部プログラムは起動しなかった【実測】。

**依頼ファイル**:

```json
{ "version": 1, "op": "create", "head": "feature/x", "title": "fix: …", "body": "…", "base": "main", "draft": false }
{ "version": 1, "op": "edit", "head": "feature/x", "number": 123, "title": "…", "body": "…" }
```

- `head` は必須。`evaluate()` が返した現在のブランチと一致しなければ拒否する（依頼を書いたあとにブランチを切り替えた場合の取り違えを防ぐ）。

- 未知のキー、重複キー、`op` と引数の不一致は拒否する。`base` は省略時にリポジトリの既定ブランチを使う。`edit` は `title` か `body` の少なくとも一方が必須。
- `number` は `bool` を除く正の整数。`title` は制御文字なし、1〜256 文字。`body` は NUL なし、65536 文字以下（上限値は【推測】。超過はサーバーが最終判定）。
- `base` は `cc-safe-push:171` と同じ文法。`draft` は `bool` のみ。`NaN` / `Infinity` は `parse_constant` で拒否する。

**読み取り**（サンドボックス外で動くため、機密ファイルの読み出し経路にしない）:

```python
def claim_request() -> bytes:
    # 固定名を一意の名前へ rename して確保する。同時実行や、あとから書かれた依頼を取り違えない。
    # rename はリンクをたどらない。依頼は 1 回限りで、読んだらすぐ消す。
    claimed = f"{REQUEST}.{uuid.uuid4().hex}"
    os.rename(REQUEST, claimed)
    try:
        fd = os.open(claimed, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            st = os.fstat(fd)
            # ハードリンクで sandbox から読めないファイルを指せないように nlink も見る。
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1:
                raise policy.PolicyError("request must be a regular file you own, with one link")
            if st.st_size > MAX_REQUEST:
                raise policy.PolicyError("request is too large")
            return os.read(fd, MAX_REQUEST + 1)
        finally:
            os.close(fd)
    finally:
        os.unlink(claimed)
```

**`evaluate()` が allow を返したあとで確保する**（未許可リポジトリの依頼ファイルには触れない）。内容は 1 回だけ読んでメモリで扱う（読み取り後の差し替えは影響しない）。拒否や失敗のあとに再実行するときは、依頼ファイルを書き直す。パースやスキーマのエラーは固定文言にし、ファイルの内容を出力しない。誤コミットの防止はグローバルの ignore に任せ、ラッパーでは確認しない（上記の不変条件のため）。

**再利用**:

```python
sys.dont_write_bytecode = True

def load_push_policy():
    # 同じ root 所有ディレクトリの cc-safe-push を読み込み、判定を 1 か所に保つ。
    loader = SourceFileLoader("cc_safe_push", str(Path(__file__).resolve().with_name("cc-safe-push")))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module
```

**API 呼び出し**:

```python
def api(token, method, path, payload=None):
    ctx = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    # http.client はプロキシの環境変数を読まず、リダイレクトも追わない。
    conn = http.client.HTTPSConnection("api.github.com", 443, context=ctx, timeout=30)
    ...
```

ヘッダーは `Authorization`、`Accept: application/vnd.github+json`、`X-GitHub-Api-Version: 2026-03-10`、`User-Agent: cc-safe-pr`（ない要求は GitHub が拒否する【公式】）。3xx はすべて失敗扱い（リポジトリの改名を見逃さない）。`full_name` は厳密に比較するので、許可リストの表記が GitHub の正規表記と違うと push は通り PR だけ拒否される。README と拒否メッセージに書く。

トークンは絶対パス `/opt/homebrew/bin/gh` で `auth token --hostname github.com` を環境 `{HOME, PATH=/usr/bin:/bin, LC_ALL=C}`、cwd `/` で実行して取得し、形式を確認してヘッダーにのみ使う（`gh` は `PATH` にないので絶対パスが必須【実測】）。

**事前検証**:

| 手順 | create | edit |
| --- | --- | --- |
| 共通 | `evaluate(cwd)` が allow（許可リスト、origin、保護ブランチ、detached HEAD） | 同左 |
| 1 | `GET /repos/{slug}`: `full_name == slug`、`archived == false` | `GET /user` で `login` を取得 |
| 2 | `GET .../git/ref/heads/{branch}`: 存在し、SHA がローカル HEAD と一致（なければ「先に push」で拒否） | `GET .../pulls/{n}`: `base.repo.full_name == slug`、`head.repo.full_name == slug`（fork と削除済みを拒否）、`state == open`、`merged == false`、`head.ref == 現在のブランチ`、`user.login == login` |
| 3 | `base != head`。`GET .../pulls?head=owner:branch&base=X&state=open` に既存があれば URL を示して拒否 | — |
| 送信 | `POST`（`title, head, base, body, draft` のみ） | `PATCH`（`title, body` のみ。`state` と `base` は送らない） |
| 応答検証 | 201、`head.sha == ローカル SHA`、`head.ref`、`base.ref`、`base.repo.full_name` を照合 | 200、`number`、`state == open`、`merged == false`、`base.repo.full_name`、`head.ref` を照合 |

`create` はリモートの SHA 確認後に branch が動く競合が残るため、応答の `head.sha` で再確認する。不一致は PR が作成済みなので exit 3 とし、URL を表示する。

`.git/HEAD` はサンドボックスから書ける【実測】ので、`head.ref == 現在のブランチ` は誤操作の防止であり、敵対的な場合の条件は「許可リストの slug、同一リポジトリ、open、本人作成」の 4 つ。`open` は PATCH 直前の確認で、GitHub に条件付き更新の手段がないので競合は残る。応答で再確認し、不一致は exit 3 にする。

**重複実行**: `create` は事前検索とサーバーの 422 で二重作成を防ぐ（実 GitHub での並行実行は未検証）。`edit` は同じ内容なら冪等。そのため専用の重複排除は作らない（exit 3 のあとに再実行しても重複は起きないが、運用手順では再実行せず状態を確認する）。`request_id` は実行ごとの UUID で、ログの突合だけに使う。

**出力**: 成功は stdout に `CREATED: <URL>` / `EDITED: <URL>`。exit 3 の URL は stderr に出し、PostToolUse の「PR が作成されました」と混同させない。

## 8. セキュリティレビュー結果

**操作先のすり替え**

| 脅威 | 経路 | 影響 | 防御 | 残余 |
| --- | --- | --- | --- | --- |
| `--repo` / `-R` / URL / 番号 | 引数や依頼に含める | 別リポジトリの操作 | 引数は固定。依頼に repo と URL の項目なし。番号は `head.ref` と `base.repo` で照合 | なし |
| `GH_REPO` / `GH_HOST` / `GH_TOKEN` | 環境変数 | 操作先・認証の差し替え | `gh pr` を実行せず、`gh auth token` は最小環境。API ホストは定数 | なし |
| `GIT_DIR` / `GIT_CONFIG_*` | 環境変数 | リポジトリ判定の偽装 | `clean_env`（既存） | なし |
| `origin` の書き換え | `.git/config` | 別リポジトリへの送信 | `.git/config` は保護パス【公式】。不一致は拒否し、操作先は常に許可リストの slug | なし |
| worktree / symlink / 相対パス | `.git` ファイルで許可リポジトリを指す | 他ディレクトリから許可リポジトリを操作 | `git-common-dir` の実パスで判定。ブランチと SHA は偽装できるが、操作先は許可リストの slug に固定され、SHA はリモートと照合する | 低: 許可リポジトリへの通常操作と同じ範囲 |
| fork / head / base | `owner:branch`、fork PR | 他者ブランチの取り込み | `head` は現在のブランチ名のみ。fork PR は拒否 | なし |

**コマンド実行の迂回**

| 脅威 | 経路 | 防御 | 残余 |
| --- | --- | --- | --- |
| `merge` / `close` / `ready` | `gh pr …` | ラッパーに機能なし。`ask` とフック | **中**: 別形式の呼び出しは止まらない |
| `&&`、`;`、`$()` | 連結 | 完全一致にならず allow も除外も外れる【公式】 | なし |
| `env` / `command` / 絶対パス / 引用符 / 行継続 | 別形式の `gh` | フックが `ask` に回す | 中: gh エイリアス、変数展開、`eval`、`python` は回避可能（エイリアス設定ファイルはサンドボックスから書けない） |
| `python` / `node` で API 直呼び | Keychain のトークン | **防げない**（F2） | **高**: Phase 2 で対処 |
| ラッパー / 許可リストの改ざん | ファイル書き換え | root 所有。親ディレクトリも確認 | なし |
| 依頼ファイルの symlink / ハードリンク | 機密の読み出し | `O_NOFOLLOW`、`nlink == 1`、スキーマ検証、固定エラー文 | なし |
| TOCTOU / 取り違え | 読み取り後の差し替え、同時実行、ブランチ切り替え | `rename` で原子的に確保し 1 回だけ読む。`head` を照合。判定に使った SHA と応答を照合 | 低: `edit` の `open` は競合が残る |
| サンドボックス外での任意コード実行 | ラッパー経由、`core.fsmonitor` | `python -I`、git は `evaluate()` 内のみ（7 章の不変条件）、`gh auth token` は最小環境 | 低: `gh` はユーザー所有 |
| トークン漏洩 | ログ / エラー出力 | 出力せず、stderr も捨てる。`gh auth` の表示系は deny（迂回可能で境界ではない） | **高**: F2 は残る |
| PR 作成による CI 起動 | `pull_request` ワークフロー | GitHub 側の設定 | 中: push より影響が広がる |

## 9. テスト仕様

**単体**（`claude/hooks/tests/test-cc-safe-pr.py`。`test-cc-safe-push.py` と同じ形式で HTTP 層をモック）

| 区分 | ケース | 期待 |
| --- | --- | --- |
| 正常 | 許可リポジトリで create / edit、サブディレクトリ、別 worktree | 0、送信内容が仕様どおり |
| 判定 | 未許可 clone、同一リポジトリの別 clone | 2、API 呼び出しなし |
| 判定 | detached HEAD、保護ブランチ、origin 変更、複数 URL | 2 |
| 引数 | 引数なし、`--repo x`、`create extra`、`merge`、`close` | 2、依頼を読まない |
| 環境 | `GH_REPO` `GH_HOST` `GH_TOKEN` `GIT_DIR` `HTTPS_PROXY` `SSL_CERT_FILE` `PATH` を設定 | 影響なし |
| 依頼 | symlink、ハードリンク、FIFO、ディレクトリ、他者所有、サイズ超過、不正 JSON、未知キー、重複キー、`op` 不一致、`head` 不一致・欠落、`number: true`、`draft` の型不正、`NaN`、制御文字 | 2、内容を出力しない |
| 依頼の確保 | 同時実行（2 回目は依頼なしで拒否）、確保後に書かれた依頼が消えない、読み取り後に依頼が残らない、未許可リポジトリでは依頼に触れない、symlink はリンク自体だけが消えてリンク先は無傷 | 確認 |
| 実行禁止 | リポジトリ設定の `core.fsmonitor` などのマーカーが、ラッパーの全経路で実行されない。`.git` ファイルと `commondir` の差し替え | マーカーなし、操作先は許可リストの slug |
| create | 未 push、SHA 不一致、`base == head`、既存 PR、`archived`、`full_name` 違い | 2 |
| edit | fork PR、`head.repo: null`、別ブランチの PR、closed、merged、他人の PR、番号なし | 2 |
| API | 事前 GET の 403/404、3xx、不正 JSON、タイムアウト、TLS エラー | 1、送信なし |
| API | POST/PATCH の 403/404/422 | 1 |
| API | POST/PATCH のタイムアウト、切断、5xx、2xx なのに応答が不正 | 3 |
| 応答 | create の `head.sha` 不一致、edit の `state` / `merged` / repo / `head` 不一致 | 3、URL を表示 |
| 認証 | `gh` 不在、失敗、タイムアウト、不正な形式。`argv[0]` が絶対パス | 1、送信なし |
| ログ | 書き込み不可、ログが symlink | 2、送信なし |
| ログ | 本文・タイトル・トークンが含まれない、ローテーション | 確認 |
| 読み込み | `cc-safe-push` がない | 2 |
| 終了 | 送信後の SIGTERM | 3 |

**Hook**（`test-ask-gh-pr-write.sh`）: `gh pr create` / `new` / `merge`、`gh pr -R x merge 1`、`gh -R x pr close 1`、`gh pr --repo=x edit 1`、`/opt/homebrew/bin/gh pr merge 1`、`env GH_REPO=x gh pr create`、`bash -c 'gh pr ready 1'`、`"gh" pr merge 1`、`gh pr mer""ge 1`、行継続、`gh api user` は `ask`。`gh pr view 1`、`gh pr checks 1`、`gh pr list`、`git log`、`cc-safe-pr create` は無出力。jq の失敗、入力側と照合側それぞれの失敗（故障注入）、`command` が null・非文字列、空の stdin は exit 2。不一致が exit 0 であること。引用符を含む 10KB 以上のコマンドがタイムアウトしないこと。6 章で挙げた見逃しと誤検知を既知の挙動として固定する。

**回帰**: `test-cc-safe-push.py`、`test-protect-main-branch.sh`、`test-validate-command.sh` がすべて通ること。`cmp` で `cc-safe-push` の無変更を確認する。

**統合**: インストール後、許可リストの実物で未 push ブランチの拒否を確認する（書き込みなし）。

**E2E（実 GitHub。使い捨ての非公開リポジトリのみ。実施は別途承認後）**

| # | 手順 | 期待 |
| --- | --- | --- |
| E1 | TLS 確認: 通常ターミナルで `api.github.com` に `/etc/ssl/cert.pem` で接続 | 200。失敗なら 4.3 を見直す |
| E2 | `cc-safe-push` → `cc-safe-pr create` | 無承認で PR 作成、ログに `X-GitHub-Request-Id` |
| E3 | `cc-safe-pr edit` | title/body のみ変更 |
| E4 | 依頼ファイルを書き直して、同じ create を再実行 | 2、既存 URL を表示 |

**人間の UI 確認（Sandbox ON + auto mode で実施）**

| # | 手順 | 期待 |
| --- | --- | --- |
| M1 | 許可リポジトリで `cc-safe-pr create` | 承認画面が**出ない** |
| M2 | 未許可リポジトリで `cc-safe-pr create` | exit 2、書き込みなし |
| M3 | 未許可リポジトリで `gh pr create …` | 承認画面が**出る**（拒否を選ぶ） |
| M4 | `gh pr new`、`gh pr -R o/r merge 1`、`gh -R o/r pr close 1`、`/opt/homebrew/bin/gh pr create`、`env GH_REPO=o/r gh pr create` | それぞれ承認画面が**出る**（拒否を選ぶ） |
| M5 | `cd sub && cc-safe-pr create` | サンドボックス内のため exit 2 |
| M6 | `gh` を除外から外した後の `gh pr view` `gh pr checks` | 動作する |
| M7 | `/sandbox` で OFF にして M1、M3 | M1 承認なし、M3 承認あり |
| M8 | default モードで M1、M3 | 同上 |
| M9 | `claude --settings` でフックを `false` に差し替え | Bash がブロックされる（`onFailure: block`） |
| M10 | plan モードで `cc-safe-pr create` | 実際の挙動を記録する（U6） |
| M11 | 設定とフックの適用後に、許可リポジトリの使い捨てブランチで `cc-safe-push` を実行 | 承認なしで push が成功する（新しいフックが push の実行経路を止めていない）。`test-cc-safe-push.py` はこの経路を通らないので、手動で確認する |

## 10. 監査ログ・運用・ロールバック

**ログ**: `~/Library/Logs/cc-safe-pr/audit.jsonl`（0600、ディレクトリ 0700）。

```json
{"ts":"…","request_id":"…","op":"create","phase":"result","outcome":"success","reason":"","repo":"o/r","branch":"b","local_sha":"…","remote_sha":"…","pr_number":12,"pr_url":"…","http_status":201,"github_request_id":"…","title_len":30,"body_len":512,"request_sha256":"…","wrapper_sha256":"…"}
```

- `phase`: `decision`（allow / deny）と `result`（success / failed / unknown）。
- トークン、title、body は記録しない（長さとハッシュのみ）。
- **送信前にログを書けなければ拒否する**。送信後の書き込み失敗は結果を優先し、警告を出す。
- ローテーション: 起動時に 5 MiB を超えていれば `audit.jsonl.1` に置き換える（1 世代）。
- **改ざん耐性の限界**: ユーザー所有なので、サンドボックスと `Edit` の deny で Claude の書き込みは止まるが、人間やサンドボックス外のプロセスには無力。証跡の最終的な正は GitHub 側。
- **突合**: PR の timeline と `X-GitHub-Request-Id`。組織の監査ログは Owner のみ閲覧可、個人の security log に PR 単位のイベントがあるかは【未確認】。

**`claude/CLAUDE.md` の運用指示**:

```markdown
- PR の作成・編集は、カレントディレクトリに `.cc-pr-request.json` を書き、そのディレクトリで
  `/usr/local/libexec/claude-push/cc-safe-pr create`（または `edit`）を単独で実行する。
- 拒否（2）や失敗（1）なら理由を伝える。未許可リポジトリでは `gh pr create --head <branch>` を提案してよい（人間の承認が必要）。依頼ファイルは実行のたびに消えるので、再実行するときは書き直す。
- 要確認（3）なら再実行せず、`create` は `gh pr list`、`edit` は `gh pr view <番号>` で状態を確認して伝える。マージ・クローズはしない。
```

**インストール**（通常のターミナルで、人間が実行）:

```sh
cd ~/dotfiles
sudo install -o root -g wheel -m 0755 claude/bin/cc-safe-pr /usr/local/libexec/claude-push/cc-safe-pr
# 依頼ファイルをグローバルの ignore に追加する（すでに書かれていれば何もしない）
grep -qxF '.cc-pr-request.json' ~/.config/git/ignore || echo '.cc-pr-request.json' >> ~/.config/git/ignore
```

依頼ファイルはラッパーが読むとすぐに消えるが、未許可リポジトリで拒否された場合や、ラッパーを実行しなかった場合は残る。残ったファイルを `git add -A` で誤ってコミットしないための設定で、どのリポジトリにも効く。`core.excludesFile` は未設定なので、Git の既定である `~/.config/git/ignore` が使われる【実測】。`grep` のオプションは `-q`（出力なし）、`-x`（行全体が一致）、`-F`（固定文字列）で、一致する行がないときだけ `||` の右側の `echo` が 1 行追記する。

**更新**: `install` を再実行。**`cc-safe-push` を更新するときは `cc-safe-pr` のテストも実行する。**

**ロールバック**: `settings.json` の差分を戻し、`sudo rm /usr/local/libexec/claude-push/cc-safe-pr` を実行する。`cc-safe-push` と許可リストは変更していないので影響なし。

## 11. 既存ファイルへの変更予定

| ファイル | 種別 | 内容 |
| --- | --- | --- |
| `claude/bin/cc-safe-pr` | 新規 | ラッパー本体 |
| `claude/hooks/ask-gh-pr-write.sh` | 新規 | 表記ゆれを `ask` に回すフック |
| `claude/hooks/tests/test-cc-safe-pr.py` | 新規 | 単体テスト |
| `claude/hooks/tests/test-ask-gh-pr-write.sh` | 新規 | フックテスト |
| `claude/settings.json` | 変更 | 6 章の差分（承認プロンプトが出る）。作業開始後に入ったユーザーの未コミット変更（`autoMode` の追加など）は、この作業のコミットに含めない |
| `claude/CLAUDE.md` | 変更 | PR 手順 |
| `claude/skills/commit-staged-pr/SKILL.md` | 変更 | PR 作成手順をラッパーに |
| `claude/README.md`、`CLAUDE.md` | 変更 | 説明、テストコマンド |
| `docs/work/20261109_cc-safe-pr/design.md` | 新規 | 本設計 |
| `claude/bin/cc-safe-push`、許可リスト | **変更なし** | — |

<a name="residual"></a>

## 12. 残余リスクと未確認事項

**残余リスク**

| # | リスク | 重大度 | 対処 |
| --- | --- | --- | --- |
| R1 | サンドボックス内から `repo` トークンに到達でき、マージを含む API を直接呼べる | **高** | Phase 2 |
| R2 | Permission / Hook は別形式の呼び出しを止められない | 中 | R1 を解消すれば実害は消える |
| R3 | 自動 PR が `pull_request` CI、CODEOWNERS 通知、メンションを発生させる。許可リストに組織リポジトリ（組織のリポジトリ）がある | 中 | Actions の承認設定を確認。許可リストの見直し |
| R4 | 許可済みリポジトリで、インジェクションされた内容の PR を無承認で作れる | 中 | 自動承認の受容範囲。マージは人間 |
| R5 | `Pull requests: write` は PR のクローズも可能 | 低 | Phase 2 でも残る |
| R6 | REST のバージョン廃止 | 低 | E2E で検知 |

**Phase 2（別タスクの提案）**: ① `sandbox.filesystem.denyRead` に `~/Library/Keychains` を加えたときに `gh auth status` が失敗するか確認する。② 効果があれば、ラッパー用に PR 専用の fine-grained PAT を、`sandbox.filesystem.denyRead` と `Read` / `Edit` の deny の両方で保護した場所に置き（Read・Edit ツールはサンドボックスの外で動き、現在は `Read` が広く allow されている）、サンドボックス内の `gh` には読み取り専用トークンを渡す。`Pull requests: write` には close も含まれるので、PAT だけではクローズを分離できない。③ 重要リポジトリにはルールセット（必須レビュー、バイパスなし）を設定する。**③ だけはトークンの漏洩にも効く唯一の強制力。**

**未確認事項**

| # | 内容 | 確認方法 |
| --- | --- | --- |
| U1 | `/usr/bin/python3` と `/etc/ssl/cert.pem` で `api.github.com` の TLS 検証が通るか。CA の読み込みは成功（128 件）。sandbox 内の接続テストは auto mode の分類器に拒否されたが、通常のターミナルでの E1 で 200 を確認した（2026-11-09、確認済み） | E1 |
| U2 | `excludedCommands` の完全一致の実動作（本体の照合部は特定できず、公式のみ） | M5、M6 |
| U3 | auto mode で `ask` が実際に承認画面になるか（公式のみ） | M3、M4 |
| U4 | サンドボックス外のプロセスから Keychain を読めるか（内側では成功） | E2 |
| U5 | Fine-grained PAT のマージ権限が `Contents: write` か（Codex が公式で確認と報告。本セッションでは要約経由のみ） | Phase 2 で再確認 |
| U6 | plan モードで allow に一致したラッパーの扱い | M10 |
| U7 | `~/Library/Keychains` の `denyRead` の効果 | Phase 2 ① |
| U8 | もう 1 件の許可リポジトリの `extensions.worktreeConfig` の設定（レビューの範囲外。ラッパーが index を読まないので影響はない見込み） | `git -C <clone> config --local --get extensions.worktreeConfig` |
| U9 | 別モデル（Codex）によるレビュー（サンドボックス内で実行不可） | 実装計画 0、8 |

## 実装計画

作業ブランチ `feat/cc-safe-pr`。GitHub への書き込み（push / PR）はこの計画に含めず、別途指示を受ける。

| # | step | verify |
| --- | --- | --- |
| 0 | ユーザーが[Codex レビューのコマンド](#codex-review-command)を実行し、Claude が採否を整理して設計に反映 | Critical / High が解消している |
| 1 | 回帰テストのベースラインを取る | 3 テストが通る |
| 2 | ユーザーが E1 を実行（1 行） | 200。失敗なら 4.3 を再検討 |
| 3 | `test-cc-safe-pr.py` を先に書く（TDD） | 失敗する |
| 4 | `claude/bin/cc-safe-pr` を実装 | 単体テストが通る |
| 5 | フックとテストを追加 | フックテストが通る |
| 6 | `settings.json`、`CLAUDE.md`、スキル、README を更新 | JSON が有効、内部リンクが解決 |
| 7 | 全テスト再実行、`cc-safe-push` の無変更を確認 | 全成功、`git diff` に出ない |
| 8 | ユーザーが通常のターミナルで Codex を実行して実装の差分をレビューし、Claude が採否を整理して修正、再テスト | Critical / High なし |
| 9 | ユーザーがインストールし、M1〜M11 と E2〜E4 を実施 | 期待どおり |

コミット分割: ① ラッパーとテスト ② フックとテスト ③ 設定とドキュメント。`claude/settings.json` にあるユーザーの未コミット変更は含めない（先にコミットしてもらうか、自分の差分だけを `git apply --cached` でステージする）。

## 独立レビューの結果

**Claude のサンドボックス内では Codex CLI を実行できなかった**（その後、ユーザーが通常のターミナルで実行した。結果は本章の末尾）。`codex exec -s read-only --ephemeral` はサンドボックス内で `failed to initialize in-process app-server client: Operation not permitted (os error 1)` により終了した。指示どおりサンドボックスは無効化していない。代替として、文脈を共有しない別のエージェントが設計と実コードを検証した。**同じ Claude なので、別モデルによる検証にはなっていない。**

<a name="codex-review-command"></a>

### Codex レビューの実行コマンド

Claude Code のサンドボックスでは動かないので、**通常のターミナルで人間が実行する**。読み取り専用（`-s read-only`）、セッション保存なし（`--ephemeral`）。結果は本設計の隣のファイルに保存され、Claude が読み取って採否を整理する。

```sh
cd ~/dotfiles
codex exec --ephemeral -s read-only --color never \
  -o ~/.claude/plans/generic-imagining-seal.codex-review.md - <<'EOF'
あなたは独立したセキュリティレビュアーです。別の担当者が書いた設計の誤りを見つけることが仕事です。結果は日本語で書いてください。

## 対象
設計: ~/.claude/plans/generic-imagining-seal.md
目的: macOS の Claude Code で、許可済み GitHub リポジトリに限り PR の作成・編集を人間の承認なしで実行する。未許可リポジトリは人間の承認が必須。マージとクローズは自動承認しない。既存の git push 自動化（cc-safe-push）を壊さないことが最優先。

実物を根拠にしてください: claude/bin/cc-safe-push、claude/settings.json、claude/hooks/validate-command.sh、claude/hooks/protect-main-branch.sh、claude/hooks/tests/test-cc-safe-push.py、claude/README.md。gh の挙動は gh の --help で確認できます。

設計末尾の「独立レビューの結果」は別のレビュアーの所見です。正しいとは限らないので、採否も含めて検証してください。

## 禁止事項
ファイルの変更、GitHub への書き込み（gh pr create/edit/merge、gh api の書き込みなど）、git push、gh auth token の実行、認証情報やトークンの読み取り・出力はしないでください。

## レビュー観点
1. Permission / Hook の仕様誤認
2. Allowlist の認可バイパス
3. Shell Injection
4. Sandbox からの権限昇格（ラッパーは Sandbox 外で動く）
5. GitHub CLI / REST API の予期しない副作用
6. worktree と Git 状態の競合
7. レースコンディション
8. 認証情報の漏洩
9. fail-open
10. 不十分なテスト
11. 既存 push 自動化への影響

## 報告形式
指摘ごとに、重大度（Critical / High / Medium / Low）、該当箇所、具体的な攻撃や失敗のシナリオ、修正案を書き、検証済みか未検証かを区別してください。根拠のない指摘は含めないでください。問題が見つからなかった観点は、その旨を一言書いてください。
EOF
```

### 別エージェントのレビュー結果

判定: Critical 0 / High 1 / Medium 3 / Low 7。ラッパー内部で許可リスト外のリポジトリに到達する経路はなし（システム全体の保証ではない）。

| ID | 重大度 | 指摘 | 判定 | 対応 |
| --- | --- | --- | --- | --- |
| H1 | High | `git ls-files` が `core.fsmonitor` を起動し、サンドボックス外で任意コードが動く | **採用** | 追跡チェックを削除し、7 章に不変条件を追加 |
| M1 | Medium | 作成後の不一致が exit 1（変更なし）になる | **採用** | exit 3 に統一し URL を表示 |
| M2 | Medium | `PATH` に `gh` がなく必ず失敗する | **採用** | 絶対パスにする |
| M3 | Medium | `gh auth status -t` と `git-credential` で deny を迂回できる | **採用** | deny を追加し、境界ではないと明記 |
| L1 | Low | フックが fail-open（here-string、grep 失敗） | **採用** | 再レビューの N2、N5 と合わせて対応 |
| L2 | Low | 正規表現の見逃しと誤検知 | **一部採用** | 引用符と行継続は正規化。変数展開や `eval` は境界ではないので追わない |
| L3 | Low | plan モードの記述が誤り | **採用** | 表を修正し、M10 を追加 |
| L4 | Low | `timeout: 5` は短い | **採用** | 30 秒 |
| L5 | Low | `full_name` の大文字小文字 | **採用** | 厳密比較のまま文書化 |
| L6 | Low | `User-Agent` が必須 | **採用** | ヘッダーを明記 |
| L7 | Low | `draft` の型未定義 | **採用** | `bool` のみ、`parse_constant` |
| — | — | ignore の設定を `setup.sh` に含める | **不採用** | 誤コミット防止のみの補助。push と同じく手動インストール手順に書く |

**再レビュー（同じレビュアーが差分を確認）**: Critical 0 / High 1 / Low 9。H1 の修正は十分（`evaluate()` 内の git で外部プログラムの起動なし）。二重作成の経路は見つからず（実 GitHub では未検証）。前回の判定に誤りなし。

| ID | 重大度 | 指摘 | 判定 | 対応 |
| --- | --- | --- | --- | --- |
| N1 | High | 引用符除去が遅く、約 9KB 超のコマンドがタイムアウトでブロックされる | **採用** | 正規化を jq に移動。13.5KB で 1 秒を確認 |
| N2 | Low | 途中の失敗が exit 2 にならない | **採用** | `trap 'exit 2' ERR` |
| N3 | Low | `command` が null などで素通り | **採用** | `jq -er … strings` |
| N4 | Low | 語の途中の行継続を見逃す | **採用** | 空白でなく削除に変更 |
| N5 | Low | here-string の容量超過で `ask` が出ない | **採用** | プロセス置換 |
| N6 | Low | 除去で増えた見逃し | **採用** | 既知の挙動としてテストで固定 |
| N7 | Low | 「再実行も安全」と「再実行しない」が矛盾して読める | **採用** | 7 章の記述を統一 |
| N8 | Low | 201 の応答が不正でも exit 1 に読める | **採用** | 2xx の不正は exit 3 と明記 |
| N9 | Low | `edit` の確認方法、exit 3 の URL の出力先 | **採用** | `gh pr view`、stderr に出力 |
| N10 | Low | 章をまたいだ食い違い 5 件 | **採用** | すべて修正 |

### Codex レビューの結果（1 回目 / 上限 5 回）

判定: Critical 0 / High 2 / Medium 3 / Low 1。実行は通常のターミナル（結果: `~/.claude/plans/generic-imagining-seal.codex-review.md`）。REST ラッパーの方針、Shell Injection、許可リストの扱い（ラッパー内部）は問題なしと評価された。

| # | 重大度 | 指摘 | 判定 | 対応 |
| --- | --- | --- | --- | --- |
| 1 | High | Phase 1 は「未許可リポジトリの人間承認」「マージ禁止」を保証しない | **採用（要件の再定義）** | ユーザーが Phase 1 を選択。1 章に要件の定義を明記 |
| 2 | High | Phase 2 の `denyRead` は Read ツールからの読み取りを防げない | **採用** | Phase 2 に `Read` / `Edit` の deny を追加。Phase 1 には影響しない |
| 3 | Medium | 固定の依頼ファイルで別の依頼を取り違える | **一部採用** | `rename` で確保する 1 回限りの方式に変更し、`head` を照合。**SHA は不採用**: 送信前にリモートと照合しており、依頼作成後のコミットは push 済みでなければ拒否される |
| 4 | Medium | `edit` の `open` は事前確認にすぎない | **採用** | 応答の `state` などを照合して不一致は exit 3。「境界」の表現を修正 |
| 5 | Medium | push の回帰試験がフック経由の実行経路を見ていない | **一部採用** | M11 を追加。**push の除外は不採用**: 既存の 2 フックも全 Bash に同じ失敗モードを持ち、新フックだけ除外しても可用性はほぼ変わらない |
| 6 | Low | プロセス置換の入力側の失敗が fail-open | **採用** | `PIPESTATUS` に変更し、故障注入で確認 |
| — | — | 「許可リスト外への経路なし」「二重作成なし」の表現が強すぎる | **採用** | 範囲を限定する表現に修正 |

### Codex レビューの結果（2 回目 / 上限 5 回。実装の差分が対象）

判定: Critical 0 / High 0 / Medium 1 / Low 1。

| # | 重大度 | 指摘 | 判定 | 対応 |
| --- | --- | --- | --- | --- |
| 1 | Medium | `os.write` の部分書き込みを確認しておらず、記録が欠けても送信する | **一部採用** | 全バイトを書くまで繰り返し、進捗なしはエラーにする。送信前は拒否、送信後は警告。**途中で切れた行の修復は不採用**: 書き込みが失敗する状況でしか起きず、そのときは送信しないため |
| 2 | Low | 想定外の 2xx が exit 1（変更なし）になる | **採用** | すべての 2xx と 5xx を exit 3 にする |
