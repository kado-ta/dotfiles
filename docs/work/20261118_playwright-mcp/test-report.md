---
status: in-progress
created: 2026-11-18
---

# Playwright MCP の導入の試験記録

<a name="environment"></a>
## 環境

2026-11-18 に確認した。

| 項目 | 版 |
| --- | --- |
| Claude Code | 2.1.327 |
| `@playwright/mcp` | 0.0.85（`playwright-core` 1.66.0-alpha-2026-11-09） |
| Node.js | 26.13.1（mise のグローバル設定） |
| Google Chrome | 157.0.8103.79 |

<a name="results"></a>
## 完了条件の結果

[plan の完了条件](plan.md#done)の順に並べる。

| # | 条件 | 結果 | 確かめ方と観測 |
| --- | --- | --- | --- |
| 1 | `claude mcp list` で接続済み | 合格 | `! claude mcp list` で `playwright: … - ✔ Connected` |
| 2 | user スコープ・固定した版・指定したオプション | 合格 | `! claude mcp get playwright` で `Scope: User config`、`@playwright/mcp@0.0.85 --isolated --browser chrome --output-dir <HOME>/Library/Caches/playwright-mcp`。`command` と `PATH` は mise のグローバルの Node.js の絶対パス |
| 3 | 2 回続けて登録してもエラー・重複なし | 合格 | `! /bin/bash ~/dotfiles/claude/scripts/register-mcp.sh` を 2 回。どちらも `Added stdio MCP server playwright to user config` で、`claude mcp list` の playwright は 1 つ |
| 3a | 端末以外から起動したときの PATH でも起動する | 合格 | 信頼していない `mise.toml` を置いた一時ディレクトリで、`env -i` で PATH を `/usr/bin:/bin:/usr/sbin:/sbin` にして `claude mcp list` → `✔ Connected`。確かめたのはサーバーの起動まで（Chrome の起動は 4a〜4b で確かめた） |
| 3b | 既定は headless、`PLAYWRIGHT_MCP_HEADLESS=false` でウィンドウが出る | 合格 | 4a〜4d のセッションではウィンドウが出なかった。`PLAYWRIGHT_MCP_HEADLESS=false claude` で始めたセッションで https://example.com を開くと、ウィンドウが出た |
| 4a | Salesforce Help の本文を取得できる | 合格 | 新しいセッションで `platform.automate_flow_ref_third_party_freshservice.htm` を読ませた。salesforce-help スキルが読み込まれ、`browser_navigate` → `browser_evaluate`（`document.body.innerText`）で本文を取得した。`browser_navigate` の応答は約 560 文字で、ページの構造（約 7.3KB）は出力先のファイルに書かれ、応答には入らなかった |
| 4b | 1440px と 390px のスクリーンショット | 合格 | https://login.salesforce.com/ を 1440×900 と 390×844 で撮影し、画像の中身を説明できた。保存先は `~/Library/Caches/playwright-mcp/page-<時刻>.png` |
| 4c | 出力が `git status` に出ない | 合格 | 前後の `git status --short` は同じ（もとからある 2 ファイルの変更だけ）。リポジトリのルートに `test.png` もない |
| 4d | 緩和策が効く | 合格 | `filename: "test.png"` のスクリーンショットは `guard-playwright-mcp.sh` が止めた。`browser_run_code_unsafe` は deny によってツール自体が一覧に出ず、呼べなかった |
| 5 | README に導入・更新・削除の手順 | 合格（レビュー待ち） | `claude/README.md` の [Playwright MCP](../../../claude/README.md#playwright-mcp) |

<a name="automated"></a>
## 自動の試験と検査

すべて手元で実行して通った。

| コマンド | 結果 |
| --- | --- |
| `bash claude/hooks/tests/test-guard-playwright-mcp.sh` | pass=26 fail=0 |
| `/usr/bin/python3 -B claude/scripts/test-register-mcp.py` | 15 件 OK |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS（新しい `playwright-mcp` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 75 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし |
| `actionlint` | 指摘なし |
| ほかのフックの回帰テスト（`test-*.sh` すべて） | すべて合格 |

テストは先に書き、失敗することを確かめてから実装した（フック、登録スクリプト、`check-repo.py` の検査、`paths` の追加分）。

<a name="findings"></a>
## 試験で分かったこと

- **`browser_drop` の `paths`**: 4d のセッションが、`browser_drop`（`core`）の `paths` 引数でローカルのファイルをページに渡せることを指摘した。ソースで確かめ（`browser_file_upload` と同じ `resolveClientFilename` で解決する）、フックで `paths` も止めた（`e99fc81`）。計画の時点では `filename` という名前の引数だけを探していて、見落としていた。この修正はフックの単体テストだけで確かめ、実際のセッションでは試していない。
- **`claude mcp get` の表示**: `PLAYWRIGHT_MCP_HEADLESS=${PLAYWRIGHT_MCP_HEADLESS}` と表示され、既定値の `:-true` が見えない。`~/.claude.json` の該当の値だけを読むと `${PLAYWRIGHT_MCP_HEADLESS:-true}` で保存されていた。3b のとおり、既定値は起動時に効いている。
- **deny とツールの一覧**: `permissions.deny` に入れた MCP のツールは、遅延読み込みの一覧にも出ない（`No matching deferred tools found`）。
- **headless の検出**: login.salesforce.com の宣伝の枠が、Akamai の Access Denied になった。headless のブラウザを止めたためと推測している（確かめていない）。headed で始めれば避けられる見込みで、README に書いた。
- **出力が溜まる**: スクリーンショット・ページの構造・コンソールのログが `~/Library/Caches/playwright-mcp` に溜まり続ける。`--output-max-size` は足さず（必要と分かるまでオプションを足さない方針）、いつ消してもよいと README に書いた。
- **sandbox の中のブラウザ**: Claude の Bash から Playwright で起動すると、Google Chrome は crashpad の Mach ポートの登録が拒否されて失敗し、同梱のヘッドレス Chromium は起動の直後に終了した（[plan の調査結果](plan.md#findings-sandbox)）。
- **ほかの作業の混入**: 作業中に、`claude/hooks/tests/test-guard-additional-dirs.sh` の 2 行目が、この作業と関係なく書き換えられていた（11:26。shellcheck の SC1090 で気づいた）。コミットには含めず、ユーザーが `git restore` で戻した。

<a name="unverified"></a>
## 確かめていないこと

- Claude のデスクトップアプリや、Dock から起動した VS Code から Claude Code を始めたときの動き。3a の `env -i` で、最小の PATH での起動を代わりに確かめた。
- フックの、Python が起動できないときの分岐（`/usr/bin/python3` を差し替えられないため）。入力を解釈できないときに止まることは確かめた。
- `paths` を止める修正の、実際のセッションでの動き（単体テストだけ）。
