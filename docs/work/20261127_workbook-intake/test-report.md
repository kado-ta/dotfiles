---
status: in-progress
created: 2026-11-27
---

# workbook-intake の導入の試験記録

<a name="related"></a>

## 関連

- ブランチ `feat/workbook-intake`
- 手順と守りの外に残るもの: [claude/README.md](../../../claude/README.md#workbook-intake)
- 設定の理由: [.claude/rules/CLAUDE_CONFIG.md](../../../.claude/rules/CLAUDE_CONFIG.md#workbook-intake)
- `~/.local/share/mise` を守らない決定: [20261119_mcp-dirs-deny-write の D5](../20261119_mcp-dirs-deny-write/plan.md#decision-node)

<a name="codex-review"></a>

## Codex のレビュー

<a name="codex-review-1"></a>

### 1 回目（2026-11-27T06:20Z、505b6b7、`codex review --base main`）

結論は "patch is incorrect"（確信度 0.97）。指摘は 4 件（P2 が 3 件、P3 が 1 件）。Codex は、回帰テストの全体と Seatbelt の実際の動きは確かめていないと書いている（一時ファイルの作成と入れ子の sandbox が制限されていたため）。

| 指摘 | 採否 | 理由・対応 |
| --- | --- | --- |
| P2: xlide が実際に使う uvx と Python（mise が入れたもの）も書き込み禁止にする | 不採用（設定は変えない）。文書は直す | 事実は正しい。uvx は `~/.local/share/mise/installs/uv/` の下にあり、xlide の仮想環境の `pyvenv.cfg` の `home` は mise の Python を指す（2026-11-27 に確かめた）。ただし、`~/.local/share/mise` を守らないことは D5 で決めて受け入れたリスクで、Playwright MCP の node と同じ。node・Python は MCP 専用ではなく、`~` で起動したセッションはほかにも sandbox の外で動く場所に書けるので、リポジトリのルートで起動し直す規則を主な守りとする。README の「uv のキャッシュと Python は、上の設定で書かせない」は誤りなので、守るものと守らないものを分けて書き直した（README と CLAUDE_CONFIG.md） |
| P2: ブックを移す前に、移行先にも拒否ルールを掛ける | 採用 | README の「受取用フォルダを変える」を、新旧の両方を守る設定をマージ → 各 Mac で反映を確かめてからブックを移す → 古いフォルダの項目を外す、の順に直した |
| P2: プラグインを入れていない Mac で、skills-check が差分を出す | 一部採用（文書だけ） | スナップショットから、プラグインのない状態を作って確かめた。`plugin removed: workbook-intake@workbook-intake` と `not installed but in SKILL_INVENTORY.md: workbook-intake` の 2 行が出る（この Mac では差分なし）。local スコープの salesforce-development も同じ扱いで、この PR より前からの性質。`skills-check.py` を直すと両方に効くので、この PR では変えない。README と SKILL_INVENTORY.md に、この 2 行は想定どおりで、項目を消さないことを書いた。`skills-check.py` の直しは Linear の KAD-37 に記録した（2026-11-27 の人間の判断） |
| P3: 受取用フォルダを変える手順に、`test-check-repo.py` の `WORKBOOK_DIR` を足す | 採用 | 2 番目の指摘の直しと合わせて、手順に足した |

<a name="codex-challenge-1"></a>

### 2 回目（2026-11-27T08:35Z、d11318d、challenge）

変更前と比べた後退と、壊れる入力・設定・手順を、全件挙げるよう頼んだ（プロンプトは Git 管理外の `.gstack/tmp/`）。指摘は 27 件（高 6、中 13、低 8）。Codex は、Seatbelt の起動が拒否され、Claude Code の実際のセッションと上流のプラグインの中身は確かめていないと書いている。

<a name="codex-challenge-1-regressions"></a>

#### 変更前と比べた後退

| 指摘 | 採否 | 理由・対応 |
| --- | --- | --- |
| 中: 古い cc-crit は、新しい設定の受取用フォルダの denyRead を覆っていないとして拒否する | 不採用（既知） | denyRead を足すたびに起きる性質で、README の「全 Mac で行うこと」で入れ直す |
| 中: uv の既定の場所に書けなくなり、`uv sync`・`uvx` などが失敗しうる | 不採用 | リポジトリのルートで起動したセッションの sandbox は、もともと書けない（allowWrite に入っていない）。変わるのは `~` で起動したセッションだけで、意図した変更 |
| 中: `~/Dev/workbook_intake` をほかの用途に使っていると、Claude から読み書きできなくなる | 採用 | 「全 Mac で行うこと」に、ほかの用途に使っていないことの確かめを足した |
| 中: 既定値を使う既存の xlide（開発用のリポジトリなど）が、ダミーを root にする | 不採用 | 意図した変更（`/review` の Security の指摘への対策）。README の「守りの外に残るもの」に書いてある |
| 中: 2.1.324 より前の Claude Code は、SHA の `ref` を読めない | 採用 | 「全 Mac で行うこと」に、`claude --version` の確かめを足した |
| 低: 全 Mac でマーケットプレイスの取得が増える。ネットワークがないときの動きは確かめていない | 不採用（記録だけ） | 取得は README に書いてある。ネットワークがないときの動きは確かめていない |
| 低: `update-skills.sh` が、このマーケットプレイスの取得に失敗すると全体が失敗する | 不採用 | ほかのマーケットプレイスと同じ性質 |

<a name="codex-challenge-1-bypass"></a>

#### 拒否が効かなくなる条件

| 指摘 | 採否 | 理由・対応 |
| --- | --- | --- |
| 高: 初めて入れるとき、拒否を確かめる前にブックを移す手順になっている | 採用 | 手順 1 ではブックを移さず、手順 5 の確かめが通った後の手順 6 で移すようにした |
| 高: 「全 Mac で行うこと」が、動いている Crit の daemon を止める更新の節を指していない | 採用 | 更新の節のとおり、開いたままのレビューを閉じてから入れ直すようにした |
| 高: 上位の設定やプロジェクトの設定で、sandbox の無効化や読み取りの許し直しがあると、Bash の拒否が外れる。検査はユーザー設定の `sandbox.enabled: false` でも通る | 一部採用 | 使うプロジェクトのセッションで `ls` が拒否されることを手順 5 で確かめ、「守りの外に残るもの」に書いた。検査が `sandbox.enabled` を見ないのは、すべての拒否に共通で、この PR より前からの性質（`check-repo.py` のどの検査も見ていない） |
| 高: `.mcp.json` 以外のスコープ（user・local など）の xlide は、手順 4 の対象外 | 採用 | 手順 5 で、`/mcp` の xlide がプラグインのものだけであることを確かめ、ほかにあれば外す |
| 高: 更新・フォルダの変更・外す手順の後に、動いているセッションを切り替える手順がない | 採用 | 3 つの手順に、そのプロジェクトのセッションをすべて閉じてから行うことを足した。`pgrep` がほかのセッションの xlide も拾う点は不採用（本物のフォルダを root にするのは、使うプロジェクトの xlide だけ） |
| 高: 受取用フォルダ自身が symlink の場合を確かめていない | 採用 | 手順 1 の確かめと「守りの外に残るもの」に、フォルダ自身を足した |
| 中: ほかの場所に同じファイルのハードリンクがあると、移しても別の名前が残る | 不採用 | 外から受け取ったブックで、ハードリンクが残る場面は考えにくい |
| 中: uv の場所が環境変数などで違う Mac では、uv の守りが当たらない | 一部採用 | 手順 1 で `uv cache dir`・`uv python dir`・`uv tool dir` を確かめる。この Mac は既定の場所だった（2026-11-27）。上流のプラグインの uv の設定や取得元は、この PR の範囲外 |

<a name="codex-challenge-1-procedures"></a>

#### 導入・更新・移行・外す手順

| 指摘 | 採否 | 理由・対応 |
| --- | --- | --- |
| 中: `--settings`・managed 設定・worktree では、local の `env` が効かないことがある | 不採用（記録だけ） | 確かめたのは 1 つの起動の形だけ。`env` が届かないときは、フックはダミーで止まり、xlide の root もダミーになるので、読めない側に倒れる |
| 中: SHA の更新の手順に、各 Mac の `git pull` がない。最後の `jq` は全プロジェクトの記録を出す | 採用 | `git pull` を足し、そのプロジェクト（`projectPath`）の記録を見るように直した |
| 中: フォルダの移行中、検査は古いフォルダの守りを求めない。空の確かめもその時点のもの | 不採用 | 移行は手で行うまれな作業で、手順の順序で守る。検査を 2 つのフォルダに対応させるのは、移行するときに要れば足す |
| 中: プラグインを外しても、手順 4 で足した `disabledMcpjsonServers` が残る | 採用 | 外す手順で、足した項目だけを消すようにした |
| 低: `cd` と `plugin install` が別の行。追跡されている `settings.local.json` は `.gitignore` では止まらない。既存の `env` へのマージ | 採用 | 1 行の `&&` にした。`git status --short --ignored` で、追跡されておらず無視されていること（`!!`）を確かめるようにした（4 つの状態の出方を一時リポジトリで確かめた）。`env` があればその中に足すと書いた |
| 低: フォルダを変える手順の対象に、`CLAUDE.md` と `CLAUDE_CONFIG.md` のパスの記述がない | 採用 | 手順 1 に足した |

<a name="codex-challenge-1-checks"></a>

#### 検査とテスト

| 指摘 | 採否 | 理由・対応 |
| --- | --- | --- |
| 中: マーケットプレイスの宣言が `null` だと、検査をすべて飛ばす | 採用 | 先に失敗するテストを書き、宣言のキーがあれば（値が `null` でも）検査を続けるように直した。宣言を消したときに検査が止まるのは意図どおり（外す手順で、先にフォルダを空にする） |
| 中: 取得元のリポジトリ、`ref` の型、ユーザー設定の `enabledPlugins` を確かめていない。`source: null` で `AttributeError` になる | 採用 | 先に失敗するテストを書き、取得元が GitHub の `kado-ta/workbook-intake` であること、`ref` が文字列の SHA であること、ユーザー設定の `enabledPlugins` で有効にしていないことを確かめるようにした。SHA がそのリポジトリに実在するかは、ネットワークを使わない検査なので確かめない |
| 低: 末尾の `/` や大文字・小文字の違いなど、同じ場所でも書き方が違うと失敗する | 不採用 | 書き方を固定する運用で、意図どおり |
| 低: Crit の大文字・小文字のテストは、区別するボリュームでは誤って失敗し、フォルダがない Mac では動かない。README のスキップの説明が古い | 一部採用 | README のスキップの説明を、偽の HOME で試す項目は動くと直した。大文字・小文字を区別するボリュームを home にする Mac は想定しない |
| 低: CI が成功しても、Seatbelt で profile を試したとは限らない | 不採用 | この PR より前からの CI の設計。profile のテストは、人間が sandbox の外で実行する決まり（`CLAUDE.md`） |
| 低: skills-check は、複数のプロジェクトの local の記録の版の混在を見逃す。更新・外す手順に、棚卸しをそろえる指示がない | 一部採用 | 更新と外す手順に `/sync-skill-docs` を足した。版の混在の見逃しは KAD-37 に書き足した |

<a name="checks"></a>

## 手元の検査

Codex の 2 回目（challenge）の指摘を直した後（2026-11-27）に実行した。検査の直し（`null` の宣言、取得元、`ref` の型、`enabledPlugins`）は、先に足したテストが 7 件失敗することを確かめてから直した。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS（`workbook-intake` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 164 件 OK |
| `/usr/bin/python3 -B claude/scripts/skills-check.py check` | 差分なし |
| `shellcheck -S warning`（追跡しているシェルスクリプト）・`actionlint`・`zizmor --offline .` | 指摘なし |

cc-crit の検査は、その前のコミット（505b6b7 まで）で実行した。`test-cc-crit.py` は OK。`test-cc-crit-profile.py` は、人間が sandbox の外で実行し、32 件 OK（スキップ 1）。Codex の 2 回の指摘の直しは、cc-crit には触れていない。
