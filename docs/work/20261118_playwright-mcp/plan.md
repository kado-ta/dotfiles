---
status: in-progress
created: 2026-11-18
---

# Playwright MCP の導入

<a name="goal"></a>
## 目的

Playwright MCP（`@playwright/mcp`）を Claude Code の user スコープに登録し、定義と手順を dotfiles で再現できるようにする。用途は次の 3 つ。

1. Salesforce Experience Cloud サイトのログイン画面（公開ページ）の調査。複数の画面幅のスクリーンショットと、スタイル値・要素寸法の取得
2. Salesforce Help など、JS で描画される文書の取得
3. フロントエンド開発での画面の確認

2026-11-11 の調査で Playwright MCP は不採用にした（[research-fetch-rate.md の判断](../20261111_salesforce-help-fetch-rate/research-fetch-rate.md#decision)）。この作業では、その判断を、緩和策を付けて覆す。

<a name="related"></a>
## 関連

- [前の判断: Salesforce Help の WebFetch 取得成功率と、本文を読む手段の選定](../20261111_salesforce-help-fetch-rate/research-fetch-rate.md)
- [Claude Code 設定の設計メモ](../../../.claude/rules/CLAUDE_CONFIG.md)
- [Skill: salesforce-help](../../../claude/skills/salesforce-help/SKILL.md)

<a name="findings"></a>
## 調査結果

2026-11-18 に確認した。

<a name="findings-package"></a>
### パッケージ

- 最新版は `0.0.85`（2026-11-09 公開）。`playwright-core` `1.66.0-alpha-2026-11-09` を同梱する。
- 既定のブラウザは、インストール済みの Google Chrome（`chromium` の `chrome` チャネル）。macOS では headed（ウィンドウを表示する）。`--browser chromium` は `chrome-for-testing` を使い、別にダウンロードが要る。
- 既定の出力先は、ワークスペースのルート（MCP のクライアントが渡すルート。なければ起動時のカレントディレクトリ）の `.playwright-mcp/`。
- ファイルの読み書きは、Playwright MCP 自身の検査で、ワークスペースのルートと出力先の中に限られる。OS の境界ではない。`file://` への移動は既定で拒否する。
- `browser_run_code_unsafe` は capability が `core` で、常に有効になる。`--caps` では外せない（`filteredTools` は `core` で始まる capability を必ず含む）。説明文は "RCE-equivalent"。
- `filename` 引数を持つ `core` のツールは、`browser_snapshot`・`browser_console_messages`・`browser_evaluate`・`browser_find`・`browser_network_requests`・`browser_network_request`・`browser_take_screenshot`・`browser_run_code_unsafe`（読み込み）。相対パスはワークスペースのルートを基準にする。`browser_evaluate` は、戻り値が JSON にできれば JSON で書く。
- `browser_file_upload` は、ワークスペースのルートの中のファイルをページに渡せる。

<a name="findings-sandbox"></a>
### sandbox との関係

- MCP サーバーは Claude Code が起動し、Bash の sandbox の外でユーザーの権限で動く（前の調査の結論。今回は測り直していない）。sandbox の denyWrite・denyRead、Edit・Write の規則、ネットワークのプロキシは効かない。
- Claude の Bash（sandbox の中）から Playwright でブラウザを起動すると、Google Chrome は crashpad の Mach ポートの登録が `Permission denied` で失敗し、同梱のヘッドレス Chromium は起動の直後に終了した。プロジェクトに入れた Playwright のテストを、Claude は sandbox の中で実行できない。

<a name="findings-node"></a>
### Node.js と npx

- Node.js は mise のグローバル設定（`node = "26.13.1"`）で入れている。端末では `.zshrc` の `mise activate zsh` が、インストール先の `bin` を PATH に入れる。
- mise の shim は、信頼していない mise の設定があるディレクトリで失敗する（`Config files in … are not trusted`）。paranoid では、設定を変えるたびに信頼が外れる。
- 端末以外（Claude のデスクトップアプリ、Dock から起動した VS Code）から Claude Code を起動したときの PATH は確認していない。

<a name="findings-cli"></a>
### Claude Code の CLI

- `claude mcp add-json -s user <name> <json>` で user スコープに登録する。`claude mcp remove -s user <name>` で消す。
- `claude/mcp.json`（`{"mcpServers": {}}`）を `~/.claude/mcp.json` にリンクしているが、user スコープの登録は `~/.claude.json` に入る。`~/.claude/mcp.json` が読まれるかは確認していない。

<a name="decisions"></a>
## 判断

<a name="decision-adopt"></a>
### D1. 緩和策を付けて導入する

前の判断の理由（sandbox の外で動く、`browser_run_code_unsafe` が RCE 相当）は今も当てはまる。用途 3 の localhost の確認と、対話的な調査は、sandbox の中ではできない（[sandbox との関係](#findings-sandbox)）。そのため、次の緩和策を付けて導入する。

| 対象 | 緩和策 | 理由 |
| --- | --- | --- |
| `browser_run_code_unsafe` | `permissions.deny` | Node のプロセスで任意のコードが動く。オプションでは外せない |
| `browser_file_upload` | `permissions.deny` | sandbox の denyRead の外で、`.env*` などをページに送れる。今の用途で使わない |
| `filename` 引数 | PreToolUse フックで、`filename` を含む `mcp__playwright__*` の呼び出しを拒否する | プロジェクトの中の任意のパス（`.claude/settings.json`・`.git/config` など）に書ける。`browser_evaluate` は任意の JSON を書けるので、hooks を書き込めば次のセッションで sandbox の外でコードが動く見込み |
| 設定の消失 | `check-repo.py` で、deny の 2 つとフックの登録（`onFailure: block`）を確かめる | `guard-additional-dirs.sh` と同じ扱い |

`filename` を拒否すると、スクリーンショットなどは出力先に自動の名前（`page-<時刻>.png` など）で保存される。スナップショットや `browser_evaluate` の結果は、ファイルではなく応答で返る。

<a name="decision-browser"></a>
### D2. ブラウザはインストール済みの Google Chrome（`--browser chrome`）

- ダウンロードが要らない。sandbox でネットワークが止められる手順がない。
- Google Chrome の自動更新で、セキュリティ修正が MCP の更新を待たずに入る。同梱の Chromium は、MCP を更新するまで古いまま残る。
- 用途 1 は実際の利用者の表示を見るので、Chrome のほうが近い。
- 既定値と同じだが、版を上げて既定が変わったときに気づけるよう明示する。
- 欠点: Chrome の版が Playwright の想定より新しくなり、動かなくなることがある。そのときは MCP を更新する。

<a name="decision-headless"></a>
### D2a. 既定は headless にし、見たいときだけウィンドウを表示する

- 定義の `env` に `"PLAYWRIGHT_MCP_HEADLESS": "${PLAYWRIGHT_MCP_HEADLESS:-true}"` を書く。`--headless` 引数は付けない（引数は環境変数より優先され、切り替えられなくなる）。
- ふだんは headless で動く。ブラウザを見たいときは、`PLAYWRIGHT_MCP_HEADLESS=false claude` でセッションを始める。
- 根拠（事実）: Playwright MCP は `PLAYWRIGHT_MCP_HEADLESS` を `true`・`1`・`false`・`0` で解釈し、引数の設定を環境変数の後に重ねる（`coreBundle.js` の `configFromEnv`・`resolveCLIConfigForMCP`）。Claude Code は MCP の定義の `command`・`args`・`env`・`url`・`headers` で `${VAR:-default}` を展開する（[MCP のドキュメント](https://code.claude.com/docs/en/mcp)）。
- 未確認: `claude mcp add-json --scope user` で登録した定義でも展開されるかは、ドキュメントに明記がない。[完了条件](#done)の 3b で確かめる。展開されないと、値が解釈できず headed になる（表示されるだけで、安全側の問題はない）。
- 注意: `PLAYWRIGHT_MCP_HEADLESS=`（空）は既定値ではなく空に展開され、headed になる。
- headless では、ビューポートの既定が 1280×720 になり、1 時間使わないとブラウザが閉じる（次の呼び出しで起動し直す。`--isolated` なので状態は残らない）。

<a name="decision-output"></a>
### D3. 出力先は `~/Library/Caches/playwright-mcp`（`--output-dir`）

- どのリポジトリにも出力しないので、グローバル gitignore を変えずに済む。`~/.config/git/ignore` は dotfiles で管理していない。
- sandbox から書けない場所なので、sandbox の中のコマンドが symlink を仕込んで出力を別の場所に向けることができない。
- 全プロジェクトで共有する。自動の名前は時刻を含むので、並行したセッションでもぶつからない見込み。

<a name="decision-node"></a>
### D4. npx は登録するときに絶対パスで固定する

定義ファイルに `${NODE_BIN}` と `${HOME}` を書き、登録スクリプトが実際のパスに置き換える。それ以外の `${...}`（[D2a](#decision-headless) の `PLAYWRIGHT_MCP_HEADLESS`）は置き換えずに残し、Claude Code が起動時に展開する。`NODE_BIN` は、ホームで `mise where node` を実行して得たグローバルの Node.js の `bin`。

- `command` は `${NODE_BIN}/npx` にする。npx と、npx が起動する `playwright-mcp` は `#!/usr/bin/env node` で始まるので、`env.PATH` も `${NODE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin` に固定する。
- 端末以外から起動したときの PATH と、プロジェクトの mise の設定（版の違いと、信頼していないときの shim の失敗）の影響を受けない。
- 公開リポジトリにユーザー名を入れない。
- 欠点: Node.js を更新したら、登録スクリプトを再実行する（README に書く）。

<a name="decision-register"></a>
### D5. 登録は「消してから足す」で冪等にする

`claude/scripts/register-mcp.sh` は、`claude/mcp/*.json` のファイルごとに、`claude mcp remove -s user <name>`（ないときの失敗は無視）→ `claude mcp add-json -s user <name> <json>` を実行する。何度実行しても登録は 1 つで、定義を変えれば置き換わる。`~/.claude.json` は CLI だけが書き、直接は編集しない。`claude/setup.sh` からも呼ぶ。

<a name="decision-routing"></a>
### D6. 使い分け

`claude/CLAUDE.md` の Tools 節を次の内容にする。

> Claude がブラウザを操作して調べるとき（公開ページのスクリーンショット・スタイル値、JS で描画される文書、ローカルの画面の確認）は Playwright MCP を使う。繰り返す確認は、そのプロジェクトの `@playwright/test` にテストとして書き、実行は人間（端末・`!`）か CI に任せる（sandbox の中ではブラウザが起動しない）。プロジェクトに Playwright がなければ、導入は提案に留める。gstack のスキル（`/qa` など）の中の browse は、スキルの手順に従う。

salesforce-help スキルの「本文を読めないとき」は、Playwright MCP で開いて `browser_evaluate`（`filename` なし）で `document.body.innerText` を読む手順にし、Playwright MCP が使えないときだけ、今の `!` での browse を使う。棚卸し（`SKILL_INVENTORY.md`）と早見表（`SKILL_CHEATSHEET.md`）のブラウザの行も合わせる。

<a name="decision-risks"></a>
### D7. 受け入れるリスク

- ページの内容によるプロンプトインジェクション。外部のページを読む方法なら、どれでも残る。
- ブラウザの通信がプロキシを通らない。WebFetch のドメイン許可の運用の外になる。用途 3 の localhost の確認には、この性質が要る。`--allowed-origins` は境界ではないので付けない。
- 出力先の自動の名前のファイルは、symlink の先が仕込まれていても、名前を選べないので意味のあるファイルを上書きできない見込み。

<a name="changes"></a>
## 変更するファイル

| ファイル | 変更 |
| --- | --- |
| `claude/mcp/playwright.json` | 新規。定義（`${HOME}`・`${NODE_BIN}` を含む） |
| `claude/scripts/register-mcp.sh` | 新規。登録スクリプト |
| `claude/scripts/test-register-mcp.py` | 新規。`claude`・`mise` の偽物で、置き換え（ほかの `${...}` は残す）・呼び出しの順番・失敗を確かめる |
| `claude/setup.sh` | `register-mcp.sh` を呼ぶ |
| `claude/hooks/guard-playwright-mcp.sh` | 新規。`filename` を含む呼び出しを拒否する。入力を解釈できないときも拒否する |
| `claude/hooks/tests/test-guard-playwright-mcp.sh` | 新規。回帰テスト |
| `.github/scripts/check-repo.py`・`test-check-repo.py` | deny の 2 つとフックの登録を確かめる |
| `.github/workflows/ci.yaml` | `test-register-mcp.py` を足す（フックのテストは glob で入る） |
| `claude/README.md` | セットアップの一覧、Playwright MCP の導入・更新・削除の手順、ウィンドウを表示する起動の仕方、フックの表とテストの一覧 |
| `CLAUDE.md`（ルート） | テストの一覧と、禁止事項（deny とフックを外さない） |
| `.claude/rules/CLAUDE_CONFIG.md` | 緩和策の設計理由 |
| `claude/CLAUDE.md` | Tools 節（[D6](#decision-routing)） |
| `claude/skills/salesforce-help/SKILL.md` | 本文を読めないときの手順 |
| `claude/SKILL_INVENTORY.md`・`claude/SKILL_CHEATSHEET.md` | ブラウザの行 |
| `claude/settings.json` | deny の 2 つとフックの登録。**あなたが編集する**（下記） |

`claude/settings.json` に足す内容:

```json
"deny": [
  "mcp__playwright__browser_run_code_unsafe",
  "mcp__playwright__browser_file_upload"
]
```

```json
{
  "matcher": "mcp__playwright__.*",
  "hooks": [
    {
      "type": "command",
      "command": "/bin/bash ~/.claude/hooks/guard-playwright-mcp.sh",
      "timeout": 10,
      "onFailure": "block"
    }
  ]
}
```

`claude/mcp/playwright.json`:

```json
{
  "type": "stdio",
  "command": "${NODE_BIN}/npx",
  "args": [
    "-y",
    "@playwright/mcp@0.0.85",
    "--isolated",
    "--browser",
    "chrome",
    "--output-dir",
    "${HOME}/Library/Caches/playwright-mcp"
  ],
  "env": {
    "PATH": "${NODE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin",
    "PLAYWRIGHT_MCP_HEADLESS": "${PLAYWRIGHT_MCP_HEADLESS:-true}"
  }
}
```

<a name="steps"></a>
## 手順

ブランチ `feat/playwright-mcp` を切る。dotfiles の作業ツリーはほかのセッションと共有しているので、コミットの前に毎回ブランチを確かめる。`main` の未コミットの変更（`biome/biome.jsonc`・`claude/settings.json`）はコミットに含めない。

1. フック: テストを先に書いて失敗を確かめ、`guard-playwright-mcp.sh` を書いて通す。→ `bash claude/hooks/tests/test-guard-playwright-mcp.sh`
2. 登録スクリプト: テストを先に書き、`register-mcp.sh` と `playwright.json` を書いて通す。`setup.sh` から呼ぶ。→ `/usr/bin/python3 -B claude/scripts/test-register-mcp.py`
3. **あなた**: `claude/settings.json` に deny とフックを足す。
4. `check-repo.py` の検査とテストを足す。→ `python3 -B .github/scripts/check-repo.py`・`python3 -B .github/scripts/test-check-repo.py`
5. README・ルートの CLAUDE.md・`CLAUDE_CONFIG.md`・CI を更新する。→ shellcheck・actionlint・`check-repo.py`
6. 使い分け: `claude/CLAUDE.md`・salesforce-help・棚卸し・早見表を更新する。→ `check-repo.py`（リンク）
7. **あなた**: 登録と動作確認（[完了条件](#done)）。新しいセッションが要る。
8. `/review` → `/security-review` → 指摘を直す → `test-report.md` を書く → `/crit-review` で差分を開く → push・PR。Codex レビューは、あなたの端末で実行する。

コミットは 1 論理変更ごとに分ける（フック、登録、settings と検査、使い分け、作業文書）。

<a name="done"></a>
## 完了条件と確かめ方

| # | 条件 | 確かめ方 | 実行する人 |
| --- | --- | --- | --- |
| 1 | `claude mcp list` で playwright が接続済み | `! claude mcp list` | あなた |
| 2 | user スコープ・`0.0.85`・指定したオプション | `! claude mcp get playwright` | あなた |
| 3 | 2 回続けて登録しても、エラーも重複も出ない | `! /bin/bash ~/dotfiles/claude/scripts/register-mcp.sh` を 2 回、その後 2 | あなた |
| 3a | 端末以外から起動したときの PATH でも起動する | 信頼していない mise の設定があるディレクトリで、`env -i` で PATH を `/usr/bin:/bin:/usr/sbin:/sbin` にして `claude mcp list` | あなた |
| 3b | 既定は headless、`PLAYWRIGHT_MCP_HEADLESS=false` でウィンドウが出る | 4b のセッションでウィンドウが出ないこと。別に `PLAYWRIGHT_MCP_HEADLESS=false claude` で始めたセッションで、ページを開くとウィンドウが出ること | あなた（新しいセッション） |
| 4a | Salesforce Help の本文を取得できる | 新しいセッションで、WebFetch では目次だけになる記事（`platform.automate_flow_ref_third_party_freshservice.htm`）を読ませる。salesforce-help スキルが Playwright MCP に回すことも見る。応答の大きさも記録する | あなた（新しいセッション） |
| 4b | 1440px と 390px のスクリーンショットを撮って確認できる | 同じセッションで `browser_resize` と `browser_take_screenshot` | あなた（新しいセッション） |
| 4c | 出力が `git status` に出ない | 4b の後に `git status`。出力が `~/Library/Caches/playwright-mcp` にあること | あなた（新しいセッション） |
| 4d | 緩和策が効く | `filename` 付きのスクリーンショットと、`browser_run_code_unsafe` を頼んで、拒否されること | あなた（新しいセッション） |
| 5 | README に導入・更新・削除の手順がある | 差分のレビュー | Claude・あなた |
| — | テスト・検査が通る | フックと登録スクリプトのテスト、`check-repo.py`、`test-check-repo.py`、shellcheck、actionlint | Claude |

4a〜4d の新しいセッションで使う依頼文は、手順 7 で渡す。

<a name="rollback"></a>
## ロールバック

1. `claude mcp remove -s user playwright`
2. `claude/settings.json` の deny とフックの登録を消し、`check-repo.py` の検査を戻す（ブランチのコミットを revert する）。
3. `~/Library/Caches/playwright-mcp` と、必要なら `~/.npm/_npx` の該当のキャッシュを消す。

<a name="out-of-scope"></a>
## 範囲外と提案

- 個別のプロジェクトへの `@playwright/test` の導入、`@playwright/cli` の導入。
- Codex: `codex/config.base.toml` に `[mcp_servers.playwright]` を足せば同じサーバーを使える見込み。Codex に MCP のツールごとの無効化があるか、sandbox との関係はどうかを確かめてから、別の作業で提案する。
- `claude/mcp.json` と `~/.claude/mcp.json` のリンク: 読まれていなければ、別の作業で削除を提案する。今回は触らない。

<a name="open-questions"></a>
## 確認したいこと

1. `main` の `claude/settings.json` の未コミットの変更（`defaultMode` の移動と `switchModelsOnFlag` の追加）を、どう扱いますか。手順 3 の変更と同じファイルなので、混ざらないよう、先に別のコミットにするか、片付けてから手順 3 に進みたいです。
2. 4a で Salesforce Help の応答（`browser_navigate` が返すスナップショット）が大きすぎたときは、`--snapshot-mode none` を足すかを、測った結果で相談します。
