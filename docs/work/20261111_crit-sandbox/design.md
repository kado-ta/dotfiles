---
status: in-progress
created: 2026-11-11
---

# Claude Code の sandbox 内から Crit を使うための設計

根拠の表記: 【実測】このセッションで確認 / 【公式】公式ドキュメント / 【コード】ソース（crit v0.23.2、sandbox-runtime `f7a0f19`） / 【推測】 / 【未確認】

## 関連

- 検証記録: [test-report.md](test-report.md)
- 既存のラッパー: [claude/README.md の cc-safe-push](../../../claude/README.md#cc-safe-push-install)、[cc-safe-pr](../../../claude/README.md#cc-safe-pr)

<a name="conclusion"></a>

## 1. 結論

- **Plan Mode の設計レビュー**は、Crit プラグインの hook（`PermissionRequest` → `crit plan-hook`）で動く。hook は sandbox の外で動くため【公式】、設定の変更は要らない【実測】。
- **sandbox から `~/.crit` には一切書き込ませない。** sandbox の外で動く crit（plan-hook と、人間が端末で実行する crit）は `~/.crit` の内容を信頼するので、sandbox から書けると、sandbox を抜ける経路になるうえ、レビューや承認を改ざんされる（[3.2](#shared-state)）。作業中に一度 `allowWrite` へ `~/.crit` を足したが、元に戻した。
- **実装レビュー（Claude が crit を起動する経路）**は、root 所有のラッパー `cc-crit` を新設し、Crit 専用の Seatbelt profile の中で crit を動かす。保存領域（HOME）は plan-hook と分ける。`allowLocalBinding` は有効にしない。ラッパーは未実装で、この文書の承認後に実装する。

<a name="current-state"></a>

## 2. 経路ごとの現状

| 経路 | 実行場所 | 状態 |
| --- | --- | --- |
| Plan Mode（`crit plan-hook`） | sandbox の外（hook） | 動く【実測】。起動・コメントの受け取り・承認まで確認済み |
| `crit comments`（一覧） | sandbox の中 | 動く（読み取りだけ） |
| `crit comment`（返信・追加） | sandbox の中 | 動かない。`~/.crit` に書けないため。Plan Mode ではもともと plan ファイル以外への書き込みが禁じられている |
| `/crit`（`crit <file>` / `crit`） | sandbox の中 | 動かない【実測】。`sessions/` に書けず、仮に書けても `127.0.0.1` で待ち受けられない。原因を示して exit 1 で止まる |

<a name="root-cause"></a>

## 3. 根本原因と、見つかったリスク

### 3.1 `/crit` が起動できない原因

crit はクライアントが daemon（`crit _serve`）を子プロセスとして起動し、`127.0.0.1:<port>` の HTTP で通信する【コード】`internal/daemon/daemon.go`, `cmd/crit/cli_serve.go`。sandbox 内では次の 2 つで止まる。

1. `~/.crit/sessions/` への書き込み（lock・log・session ファイル）が拒否される【実測】
2. 書き込みを許可しても、`listen tcp 127.0.0.1:0: bind: operation not permitted` で止まる【実測】

ブラウザの自動起動（`open <url>`）は待ち受けを始めた後に非同期で実行され、失敗しても daemon のログに警告を出すだけで止まらない【コード】`cli_serve.go:222`, `internal/browser/browser.go`。`--no-open` はブラウザの起動だけを止め、待ち受けは止めない。

<a name="shared-state"></a>

### 3.2 sandbox の外の crit が信頼する `~/.crit` に書かせてはいけない

sandbox の外で動く crit（plan-hook の daemon、人間が端末で実行する crit）は、`~/.crit` の次の内容を信頼する【コード】。

| 場所 | sandbox から書けたときの影響 |
| --- | --- |
| `hooks/on_finish_*.sh` | レビュー完了時に、信頼判定なしで実行される（`internal/hooks/resolve.go:140`） |
| `prompts/on_finish_*.md`、`custom.css` | Claude に返す指示文と、レビュー画面の表示を差し替えられる |
| `plans/<slug>/current.md`、`vNNN.md` | plan-hook は `os.WriteFile` でここに書くので、シンボリックリンクをたどる（`internal/session/plans.go:52-65`）。リンク先（`~/.zshrc` など）に plan 本文を書かせられる |
| `plans/<slug>/.crit/review.json`、`reviews/<key>/review.json` | 人間を名乗るコメントを足したり、人間のコメントを解決済みにしたりできる。承認の判定は「未解決が 0 件」だけ（`internal/server/server.go:2591`）。plan-hook の結果は Claude にとって「ユーザーのフィードバック」として届く |
| `plans/<slug>/current.md` | 人間に見せる plan を差し替えられる。plan-hook が承認するのは、最初に受け取った ExitPlanMode の入力で、画面に出した内容との一致は確かめない（`internal/session/plan_cli.go:235-258`） |
| `sessions/<key>.json` | 接続先（`host`）をそのまま使う（`daemon.go:145`）。plan-hook のクライアントを攻撃者のサーバーに向け、承認や指示文を偽造できる |

このため、`sandbox.filesystem.allowWrite` には `~/.crit` 配下を一切入れない【実測】（[test-report.md](test-report.md#revert)）。

プロジェクト側の設定の扱い【コード】`internal/config/config.go:359-377`, `internal/prompt/trust.go`:

- `.crit.config.json` の `open_cmd`・`agent_cmd`・`host`・`public_url` は、プロジェクトから読まない（グローバル設定 `~/.crit.config.json` だけ）。
- `.crit/hooks/*.sh` と `.crit/prompts/` は、`~/.crit.config.json` の信頼判定を通ったときだけ使う。ただし、信頼の種類が `always` だと、内容が変わっても信頼は失効しない。リポジトリは sandbox から書けるので、**どのリポジトリにも `always` の信頼を与えない**（現在、`~/.crit.config.json` は存在しない【実測】）。

### 3.3 `allowLocalBinding` を採らない理由

Claude Code 2.1.311 の Seatbelt 規則は次のとおり【コード】【実測】（バイナリ内の文字列で確認）。

```text
(allow network-bind (local ip "*:*"))        ; 全インターフェースで待ち受け
(allow network-inbound (local ip "*:*"))
(allow network-outbound (remote ip "localhost:*"))   ; localhost の全ポートへ接続（proxy を通らない）
```

公式ドキュメントは「待ち受けと localhost への接続を許可する」とだけ書いているが、bind の範囲はそれより広い。この端末では次のことが分かっている。

- localhost では、Lima、ポート転送された DB と Redis（5434, 6379 など）、VS Code、Obsidian、Circleback、ほかの Claude セッションの proxy が待ち受けている【実測】。ファイアウォールの設定に関係なく、`allowLocalBinding` を有効にすると、sandbox 内のコマンドがこれらに proxy を通らずに接続できる。
- macOS のアプリケーションファイアウォールは、2026-11-11 のレビュー中に人間が有効にした（それまでは無効だったと人間が報告）。
  - 2026-11-12 に sandbox の外で確認した状態【実測】: ファイアウォールは有効（State = 1）。「署名されたソフトウェアの受信を自動で許可」は、Apple 製とダウンロードした署名済みの両方とも有効。
  - sandbox の中で `socketfilterfw --getglobalstate` を実行すると、有効にした後も「disabled」と返る【実測】。sandbox の中からは実際の状態を読めない。
  - 署名済みのプログラムの受信は自動で許可されるので、ファイアウォールが有効でも、`/usr/bin/python3` のような署名済みのプログラムが 0.0.0.0 で待ち受けると LAN から届く【推測】。

設定は sandbox 内のすべてのコマンドに効くので、Crit のために全体を緩めることになる。Lima の VM を経由してホストに書き込めるかは、鍵を確認する操作が拒否されたため【未確認】。

<a name="design"></a>

## 4. 設計: `cc-crit`

### 4.1 構成

```text
Claude（Bash ツール）
  └─ /usr/local/libexec/claude-crit/cc-crit review|reply   root 所有。excludedCommands の完全一致で sandbox の外
       ├─ .cc-crit-request.json を読んで検証し、削除する
       ├─ 専用の HOME（~/.cc-crit/crit-home）と、空いているポートを専用の範囲から用意する
       ├─ review: sandbox-exec -f cc-crit.sb crit --no-open -p <port> -o <専用 HOME>/.crit [files…]
       │  reply:  sandbox-exec -f cc-crit.sb crit comment --session <id> --json --author 'Claude Code'
       │     └─ crit の client → daemon（_serve）→ git     すべて Crit 専用 profile の中
       └─ review のとき: 専用 HOME の session ファイルで実際の接続先を確かめてから /usr/bin/open で開く
```

- `cc-safe-pr` と同じく、サブコマンドだけの完全一致（`cc-crit review` と `cc-crit reply`）で allow と `excludedCommands` に入れ、入力は作業ディレクトリの依頼ファイルで渡す。`excludedCommands` に `*` を書かずに済む【公式】。
- インストール先は専用のディレクトリ `/usr/local/libexec/claude-crit/` にする（7 章の 3）。
- ラッパー本体と profile（`cc-crit.sb`）は root 所有でインストールし、Claude からは書き換えられないようにする。
- **専用の HOME で、plan-hook と保存領域を分ける。** cc-crit の crit は `~/.cc-crit/crit-home/.crit` に session・レビューを置き、plan-hook が使う `~/.crit` には触れない。専用 HOME の内容を信頼するのは、Crit 専用 profile の中で動く cc-crit の daemon だけになる。レビュー結果は Bash ツールの出力として Claude に届き、hook の「ユーザーのフィードバック」にはならない。

### 4.2 入力（`.cc-crit-request.json`）

```json
{ "files": ["docs/work/x/plan.md"] }
```

`cc-crit reply` の依頼（7 章の 4）:

```json
{ "session": "d58eb1c63694", "replies": [{ "reply_to": "c_73f150", "body": "3.3 を更新しました。" }] }
```

- `reply` が受け付けるのは、既存のコメントへの返信（`reply_to` と `body`）だけ。新しいコメントの追加、解決済みへの変更、author の指定はできない。author はラッパーが `Claude Code` に固定する。
- これで、Claude の sandbox からレビューのデータに直接書く経路がなくなり、人間のコメントの偽造や、解決済みにしての承認の偽造ができない。

- `files` を省くか空にすると、ブランチの差分をレビューする（引数なしの `crit`）。
- 依頼ファイルは `cc-safe-pr` と同じく、`O_NOFOLLOW | O_NONBLOCK` で開き、`fstat` で通常ファイル・所有者・サイズ・`st_nlink == 1` を確かめ、読んだ後に削除する（`claude/bin/cc-safe-pr:160` 付近）。
- 各パスは `realpath` で解決し、通常ファイルで、作業ディレクトリの git toplevel の配下にあること。`-` で始まるもの、未知のキー、上限（例: 20）を超える数は拒否する。
- 検証の後で crit が開くまでにファイルが差し替えられる可能性は残る。その場合も、crit が読めるのは Crit 専用 profile が許す範囲だけになる（[5.2](#threats) の T2）。

### 4.3 crit に渡すもの

- 引数は固定: `--no-open -p <port> -o <専用 HOME>/.crit` とファイルだけ。`--host`、`--public-url`、`--pr` / `--mr` / `--range`、`share` 系は渡さない。
- 環境変数は許可リスト方式で、値はラッパーが決める。
  - `HOME` は専用 HOME。元の値は UID から取得し、呼び出し元の環境変数は使わない。
  - `PATH` は固定。`LANG`、`USER` も渡す。
  - `CRIT_NO_UPDATE_CHECK=1` を設定する。
  - git のグローバル設定とシステム設定を読ませない: `GIT_CONFIG_GLOBAL=/dev/null`、`GIT_CONFIG_NOSYSTEM=1`。これで、ユーザーの `~/.gitconfig` にある git-lfs のフィルターなどのドライバーが、リポジトリの `.gitattributes` から使われなくなる。
  - 加えて `GIT_CONFIG_COUNT` で `core.fsmonitor=false`、`core.hooksPath=/dev/null` を与える。
  - `CRIT_*`、それ以外の `GIT_*`、`GH_*`、トークン類、`SSH_AUTH_SOCK` は渡さない。
- 専用 HOME の `.crit.config.json`（crit にとってのグローバル設定）は、ラッパーが起動のたびに固定の内容で書き直す。Crit 専用 profile からも Claude の sandbox からも書けない場所に置き、ラッパーは `O_NOFOLLOW` で書く。
- **プロジェクトの信頼を `defaults` に固定する。**
  - 背景: レビュー対象のリポジトリに `.crit/hooks`、`.crit/prompts`、プロジェクトの `.crit.config.json` の `hooks` / `prompts` があると、crit は Finish のときに信頼の選択を求め、結果をグローバル設定に保存する【コード】`internal/prompt/trust.go` の `EvaluateTrust`、`SaveTrustChoice`。専用 HOME の設定は profile から書けないので、選択を保存できず、Finish が失敗するか止まるおそれがある【未確認】。
  - 対策: ラッパーは設定の `trusted_project_prompts` に、crit を起動するディレクトリの信頼を `defaults`（プロジェクトの hooks と prompts を使わない）として先に書いておく。
    - キー: `"sha256:"` と、crit の作業ディレクトリを `realpath` で解決したパスの SHA-256 の 16 進。crit の `RepoRootHash` と同じ計算で、crit は daemon の作業ディレクトリを `EvalSymlinks` したものを使う【コード】`internal/daemon/daemon.go:163`、`internal/server/daemon_bootstrap.go:12`。
    - 値: `{"mode": "defaults"}`
  - 効果: `cc-crit` は、プロジェクトの hooks と prompts を一切使わない。「どのリポジトリにも `always` の信頼を与えない」という運用（[3.2](#shared-state)）より強い。
- プロジェクトの `.crit.config.json` は crit が読むが、影響するのはレビュー対象の選び方（`base_branch`、`vcs` など）までで、profile の外には出られない【推測】。

<a name="profile"></a>

### 4.4 Crit 専用 profile（`cc-crit.sb`）

既定は拒否（`deny default`）とし、crit と git が動くのに必要なものだけを許可する。

| 種類 | 許可する範囲 |
| --- | --- |
| 書き込み | 専用 HOME の `.crit` 配下と、ラッパーが作る専用の一時ディレクトリだけ。`~/.crit` は書けない |
| 読み取り | 全体。ただし、Claude の `sandbox.filesystem.denyRead` に相当するパスと `~/Library/Keychains`、`~/.crit` は拒否する |
| ネットワーク | `localhost` の専用ポート範囲（例: 47800〜47819）での bind・inbound・outbound だけ。外部への通信はすべて拒否 |
| プロセス | `crit` と `git`（とその内部ツール）の実行 |
| mach-lookup | 動作に必要な最小限。LaunchServices と Apple Events は拒否 |

- 専用ポート範囲で待ち受けているのは、cc-crit の daemon だけである必要がある。ラッパーは、範囲内の待ち受けのうち、専用 HOME の session ファイルに記録されていないものが 1 つでもあれば、実行を拒否する。
- `denyRead` との対応: ラッパーは実行時にユーザー設定とプロジェクト設定の `denyRead` を読み、profile の固定の拒否リストで覆えないものがあれば、実行を拒否する。
- profile の各規則は、実装時に crit と git を実際に動かして必要最小限まで詰める。互換性のために、ワイルドカードの bind や広い mach-lookup を足す必要が出たら、この設計を見直す。

<a name="security-review"></a>

## 5. セキュリティレビュー

### 5.1 守るもの

sandbox の外への書き込みとコード実行、機密ファイル（`denyRead`）、外部への通信の許可リスト、localhost のサービス、LAN への露出、plan の承認の正しさ、Claude に返る指示文の正しさ。

<a name="threats"></a>

### 5.2 脅威と対策

| # | 脅威 | 対策 | 残るリスク |
| --- | --- | --- | --- |
| T1 | ラッパー経由で任意のコマンドを実行する | 引数なしの完全一致。依頼ファイルは厳格な形式で検証する。crit の引数と環境変数を固定する | なし【推測】 |
| T2 | crit や git に機密ファイルを読ませる | profile で `denyRead` 相当を拒否する。ファイルは git toplevel の配下に限る。`denyRead` を覆えない設定なら実行を拒否する | 検証後の差し替え。読めるのは profile が許す範囲まで |
| T3 | リポジトリの設定で git にコードを実行させる | `.git/config` と `.git/hooks` は sandbox から書けない【実測】。グローバル設定とシステム設定を読ませないので、`.gitattributes` から使えるドライバーがない | 実行されても profile の中に閉じ、専用 HOME の外に書けない |
| T4 | 外部へ持ち出す | profile で外部への通信をすべて拒否する。更新確認は止める | ブラウザ経由（[5.3](#residual)） |
| T5 | LAN に露出する | bind は `localhost` の専用範囲だけ。`--host` と `CRIT_HOST` は渡さず、専用 HOME の設定で host を固定する | なし |
| T6 | localhost のほかのサービスに接続する | outbound は専用範囲だけ。範囲内に cc-crit 以外の待ち受けがあれば実行を拒否する | なし【推測】 |
| T7 | `~/.crit` のグローバル設定（hooks・prompts・custom.css）を書き換える | Claude の sandbox からも profile からも書けない | なし |
| T8 | session ファイルを偽造して、sandbox の外の plan-hook を別のサーバーに向ける | plan-hook の `~/.crit/sessions` には、Claude の sandbox からも profile からも書けない。cc-crit の session は専用 HOME に分ける | なし |
| T9 | ブラウザが別のサービスを開く | 選んだポートではなく、専用 HOME の session ファイルにある実際の接続先を `/api/health` で確かめてから開く | なし |
| T10 | `sandbox-exec` が将来の macOS で使えなくなる、または規則が想定と違う形で受理される | 失敗したら実行を拒否する（fail closed）。アドレスの表し方ごとの拒否を検証項目にする（[8 章](#verification)） | 動かなくなる。安全側に倒れる |
| T11 | リポジトリの `.crit/hooks` などで、レビュー完了時にコマンドを実行させる。または、信頼の選択を保存できずに Finish が止まる | ラッパーが専用 HOME の設定で、そのディレクトリの信頼を `defaults` に固定する（4.3）。設定ファイルは profile からも Claude の sandbox からも書けない | crit の版が変わってキーの計算や形式が変わると、信頼の選択を求める状態に戻る。その場合も、hooks は profile の中で動く |

<a name="residual"></a>

### 5.3 cc-crit では解決しない、既存の経路のリスク

- **ブラウザ経由の持ち出し:** crit の画面は、Markdown 内の `http(s)` の画像をそのまま描画し、CSP もない【コード】`web/app.js:1381-1386`。Claude が sandbox 内で読めたデータを画像 URL に埋め込んだ Markdown をレビューすると、人間のブラウザがそれを取得する。plan-hook と人間が実行する crit も同じで、エージェントが書いた内容をブラウザで見る仕組みに共通の問題。crit 本体に CSP を足すよう、上流に提案する。
- **Claude のファイルツールによる `~/.crit` の改ざん:** Edit・Write ツールは sandbox の外で動き、許可は permission ルールと auto mode の判定で決まる。`permissions.deny` に `Edit(~/.crit/**)` と `Edit(~/.crit.config.json)` を足すことを提案する（この文書の範囲外）。
- **plan の slug の衝突:** plan-hook の session key は cwd を含まず、slug（見出しと日付から作る）だけで決まる【コード】`internal/session/plans.go:29-33`。同じ日に同じ見出しの plan を別のセッションで出すと、レビューが混ざる。crit の設計上の問題として上流に報告する。
- **Plan Mode での返信:** crit は「`crit comment` で返信してから ExitPlanMode を呼ぶ」よう指示するが、Claude Code の Plan Mode は plan ファイル以外への書き込みを禁じ、sandbox からも `~/.crit` に書けない。返信は省かれる（plan の修正自体は次の版として反映される）。承認したときにレビューのファイルを消すかどうかは、`cleanup_on_approve`（プロジェクトの設定で変えられる）による。

<a name="changes"></a>

## 6. 変更するファイル（実装時）

| ファイル | 内容 |
| --- | --- |
| `claude/bin/cc-crit` | ラッパー本体（Python、`cc-safe-pr` に合わせる） |
| `claude/bin/cc-crit.sb` | Crit 専用 profile |
| `claude/settings.json` | `permissions.allow` と `sandbox.excludedCommands` に `/usr/local/libexec/claude-crit/cc-crit review` と `… reply` を追加。依頼ファイルを書けるように `Edit(**/.cc-crit-request.json)` も追加 |
| `claude/hooks/validate-command.sh` | `cc-safe-*` と同じく、`cc-crit` も単独の完全一致以外をブロックする |
| `.github/scripts/check-repo.py` | `WRAPPER_COMMANDS` に追加する。今は実際の値を `"cc-safe" in rule` で抜き出しているので、抜き出し方も変え、未知のラッパーを拒否する |
| `.github/scripts/test-check-repo.py` | 上の検査の回帰テスト |
| `claude/hooks/tests/test-cc-crit.py` | 依頼ファイルの検証、環境変数、専用 HOME、ポートの選択と接続先の確認、fail closed のテスト |
| `claude/README.md` | 使い方とインストール手順 |
| `claude/skills/crit-review/SKILL.md` | 個人スキル `/crit-review`。`cc-crit` で対話レビューを回す手順（[7 章](#open-questions)で決定） |

<a name="open-questions"></a>

## 7. 決めること

1. Claude への指示の方法: **個人スキル `/crit-review` を作る（2026-11-11 に決定）。** `cc-crit` を使うので、ラッパーと一緒に実装する。プラグインの `/crit` は残るが、sandbox 内では原因を示して止まる。グローバル CLAUDE.md に書く案は、プラグインの `/crit` のスキルの指示と競合するので採らない。
2. ブラウザの自動起動: **ラッパーが開く（2026-11-12 に決定）。** 実際の接続先を確かめてから開く（T9）。
3. インストール先: **専用のディレクトリ `/usr/local/libexec/claude-crit/`（2026-11-12 に決定）。** 名前と用途を一致させる。インストール手順と `excludedCommands` の項目は `cc-safe-*` と別になる。
4. Claude の返信: **ラッパー経由（`cc-crit reply`、2026-11-12 に決定）。** Claude の sandbox からは専用 HOME にも書かせない（4.2）。

<a name="verification"></a>

## 8. 検証（実装時）

1. `test-cc-crit.py`、`check-repo.py`、`test-check-repo.py`、shellcheck、actionlint
2. インストール後、Claude の Bash ツールから `cc-crit` でファイルと差分のレビューを開き、コメント → Finish → 再実行 → 承認まで通す
3. profile の拒否の確認: crit の子プロセスから次の操作がすべて失敗すること
   - 外部への接続
   - 待ち受け: `127.0.0.1`、`::1`、IPv4-mapped、`0.0.0.0`、`::`、LAN のアドレス、範囲外のポート
   - 接続: 範囲外の localhost のポート
   - 書き込み: `~/.crit` と専用 HOME の外
4. 信頼の固定（T11）: `.crit/hooks` を置いたリポジトリで、Finish が止まらず、hook も実行されないこと
   - テスト用のリポジトリに `.crit/hooks/on_finish_approved.sh` と `on_finish_unresolved.sh` を置く。中身は、実行されたら一時ディレクトリに印のファイルを作るだけにする
   - `cc-crit` でレビューを開き、コメントなし（approved）とコメントあり（unresolved）の両方で Finish を押す
   - どちらも、信頼の選択を求められずに Finish が終わり、印のファイルが作られないこと
5. 異常終了: daemon を止めてからの再実行、依頼ファイルが不正なとき、範囲内に cc-crit 以外の待ち受けがあるときの拒否
6. 対応する macOS・crit・git の版を記録し、版が変わったら 3 と 4 をやり直す

<a name="codex-review"></a>

## 9. Codex レビューの反映

`codex review --uncommitted`（1 回目）は指摘なし。`codex exec` による challenge（2 回目、2026-11-11）の指摘と判断は次のとおり。主な主張はソースで確かめた。

| # | 指摘 | 判断 | 理由と反映先 |
| --- | --- | --- | --- |
| 1 | P1: `plans/` のリンクを sandbox の外の plan-hook がたどる | 採用 | `plans.go:52-65` で確認。`allowWrite` から外した（[3.2](#shared-state)） |
| 2 | P1: 人間名義のコメントや解決状態を偽造できる | 採用 | `server.go:2591` で確認。同上 |
| 3 | P1: 承認が画面の plan と結び付いていない | 採用（一部） | sandbox からの経路は塞いだ。ファイルツールの経路は `permissions.deny` を提案。slug の衝突は上流に報告（[5.3](#residual)） |
| 4 | P1: git の設定経由のコード実行と session の偽造が連鎖する | 採用 | 専用 HOME と、git のグローバル・システム設定の無効化（4.1、4.3） |
| 5 | P1: 専用ポート範囲から sandbox の外の daemon に届く | 採用（変更） | 範囲内は cc-crit の daemon だけに限る（4.4）。ポートを 1 つに絞る案は、daemon の再利用と両立しないので採らない |
| 6 | P1: ブラウザが許可リスト外への通信経路になる | 採用（残存リスクとして） | `app.js:1381` で確認。plan-hook にも共通し、crit 本体でしか直せない。上流に CSP を提案（[5.3](#residual)） |
| 7 | P2: 検証後の差し替え（TOCTOU） | 採用（一部） | 依頼ファイルは `cc-safe-pr` と同じ検査にする。crit の読み直しは profile の範囲に収まるので、スナップショットは採らない（ライブ更新が使えなくなるため） |
| 8 | P2: 選んだポートと実際の daemon が一致しない | 採用 | 専用 HOME の session ファイルで接続先を確かめてから開く（T9） |
| 9 | P2: プロジェクト設定と `HOME` で実効設定が変わる | 採用（一部） | `HOME` と `-o` はラッパーが決める。`base_branch` などは対象の選び方だけで、profile の外には出ない |
| 10 | P2: `denyRead` の一致を CI だけでは保証できない | 採用 | 実行時に設定を読み、覆えなければ拒否する（4.4） |
| 11 | P2: deny-default の profile が成り立つ条件と、アドレスごとの保証 | 採用 | 検証項目と版の記録（8 章） |
| 12 | P2: check-repo.py の抜き出しが `cc-safe` 前提 | 採用 | `check-repo.py:151` で確認。6 章に反映 |
| 13 | P3: 3.2 と 5.3 の記述の一般化 | 採用 | `open_cmd` などはプロジェクトから読まない、信頼の `always`、`cleanup_on_approve` を書き分けた（3.2、5.3） |
