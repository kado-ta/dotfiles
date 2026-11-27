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

<a name="checks"></a>

## 手元の検査

Codex の指摘を直した後（2026-11-27）に実行した。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS（`workbook-intake` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 162 件 OK |
| `/usr/bin/python3 -B claude/scripts/skills-check.py check` | 差分なし |
| `shellcheck -S warning`（追跡しているシェルスクリプト）・`actionlint`・`zizmor --offline .` | 指摘なし |

cc-crit の検査は、その前のコミット（505b6b7 まで）で実行した。`test-cc-crit.py` は OK。`test-cc-crit-profile.py` は、人間が sandbox の外で実行し、32 件 OK（スキップ 1）。Codex の指摘の直しは文書だけで、cc-crit には触れていない。
