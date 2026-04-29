# claude-code-setup プラグイン管理 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `claude-code-setup@claude-plugins-official` プラグインを `.claude/setup.sh` で冪等インストールし、`.claude/settings.json` の `enabledPlugins` で有効化を宣言する。

**Architecture:** 既存 `superpowers` プラグインのインストール／有効化と同じ二段構成（`setup.sh` のシェルブロック + `settings.json` の `enabledPlugins` エントリ）を踏襲する。共通化はしない（YAGNI）。

**Tech Stack:** Bash, `claude` CLI (`claude plugins install`), JSON (Claude Code settings)。

**Spec:** `docs/20260430_claude_code_setup_plugin/[design]_claude_code_setup_plugin.md`

**前提:**
- 現在のブランチが `feature/add_claude_code_setup` であること（`git branch --show-current` で確認）
- `claude` CLI が `PATH` 上にあり、`claude plugins list` が動作すること
- `~/.claude/settings.json` が本リポジトリの `.claude/settings.json` のシンボリックリンクであること（既に `setup.sh` 実行済み環境を想定）

---

## ファイル構成

| 種別 | パス | 責務 |
|---|---|---|
| Modify | `.claude/setup.sh` | `claude-code-setup` の冪等インストール処理を追加 |
| Modify | `.claude/settings.json` | `enabledPlugins` に `claude-code-setup@claude-plugins-official` を追加 |

テストファイルは追加しない（既存リポジトリにシェルスクリプトのテスト基盤が無く、4 行追加のためにフレームワーク導入はオーバーキル。検証は手動実行 + `claude plugins list` の出力確認で行う）。

---

### Task 1: `.claude/setup.sh` に `claude-code-setup` インストールブロックを追加

**Files:**
- Modify: `/Users/kado/dotfiles/.claude/setup.sh`（`superpowers` インストールブロック直後）

- [ ] **Step 1: 現在のブランチを確認**

Run: `git -C /Users/kado/dotfiles branch --show-current`
Expected: `feature/add_claude_code_setup`（main / master / staging では絶対に作業しない）

- [ ] **Step 2: `setup.sh` を編集**

`.claude/setup.sh` の `superpowers` インストールブロック（現状は 26-31 行目）の直後（32 行目空行の前後）に、以下のブロックを挿入する。

挿入する内容（既存スタイルと完全一致させる）:

```sh
# Install claude-code-setup
if claude plugins list 2>/dev/null | grep -q " claude-code-setup@claude-plugins-official$"; then
  echo "claude-code-setup plugin already installed, skipping"
else
  claude plugins install claude-code-setup@claude-plugins-official
fi
```

挿入後の周辺イメージ:

```sh
# Install Superpowers
if claude plugins list 2>/dev/null | grep -q " superpowers@claude-plugins-official$"; then
  echo "superpowers plugin already installed, skipping"
else
  claude plugins install superpowers@claude-plugins-official
fi

# Install claude-code-setup
if claude plugins list 2>/dev/null | grep -q " claude-code-setup@claude-plugins-official$"; then
  echo "claude-code-setup plugin already installed, skipping"
else
  claude plugins install claude-code-setup@claude-plugins-official
fi

# Install gstack
GSTACK_DIR="${CLAUDE_DIR}/skills/gstack"
```

- [ ] **Step 3: シェルスクリプトの構文チェック**

Run: `bash -n /Users/kado/dotfiles/.claude/setup.sh`
Expected: 出力なし、終了ステータス 0（構文エラーなし）

---

### Task 2: `.claude/settings.json` の `enabledPlugins` に追記

**Files:**
- Modify: `/Users/kado/dotfiles/.claude/settings.json`（`enabledPlugins` セクション、現状 194-196 行目）

- [ ] **Step 1: `enabledPlugins` を更新**

現状:

```json
"enabledPlugins": {
  "superpowers@claude-plugins-official": true
},
```

変更後:

```json
"enabledPlugins": {
  "superpowers@claude-plugins-official": true,
  "claude-code-setup@claude-plugins-official": true
},
```

注意点:
- `superpowers@claude-plugins-official` の行末に `,` が無いので、追加する際にカンマを忘れない
- 末尾の `},` はそのまま保持する

- [ ] **Step 2: JSON が有効であることを検証**

Run: `python3 -c 'import json,sys; json.load(open("/Users/kado/dotfiles/.claude/settings.json")); print("OK")'`
Expected: `OK`（パース成功）

- [ ] **Step 3: `enabledPlugins` の中身を確認**

Run: `python3 -c 'import json; print(json.load(open("/Users/kado/dotfiles/.claude/settings.json"))["enabledPlugins"])'`
Expected: `{'superpowers@claude-plugins-official': True, 'claude-code-setup@claude-plugins-official': True}`

---

### Task 3: 動作確認（実インストール）

**Files:** なし（実環境への作用のみ）

- [ ] **Step 1: 1 回目の実行 — インストールが走ることを確認**

Run: `bash /Users/kado/dotfiles/.claude/setup.sh`
Expected:
- 既存出力に加えて、`claude plugins install claude-code-setup@claude-plugins-official` 相当のインストールログが出る
- 終了ステータス 0
- `superpowers plugin already installed, skipping` は引き続き表示される
- `gstack already installed, skipping` も引き続き表示される

備考: ネットワーク接続が必要。失敗した場合はコマンド出力をそのまま確認し、`claude plugins install` を直接叩いて切り分ける。

- [ ] **Step 2: 2 回目の実行 — 冪等性を確認**

Run: `bash /Users/kado/dotfiles/.claude/setup.sh`
Expected:
- 出力に `claude-code-setup plugin already installed, skipping` が含まれる
- 終了ステータス 0
- 新たなインストールが走らない

- [ ] **Step 3: プラグインリストで有効化を確認**

Run: `claude plugins list`
Expected: 出力に以下を含む:
```
  ❯ claude-code-setup@claude-plugins-official
    Version: <version>
    Scope: user
    Status: ✔ enabled
```

`Status: ✔ enabled` の行が出ていれば OK。`disabled` の場合は `claude plugins enable claude-code-setup@claude-plugins-official` を実行し、原因（`enabledPlugins` のスペル違い等）を調査する。

---

### Task 4: 変更をコミット

**Files:** ステージングするのは Task 1 / 2 で変更した 2 ファイルのみ。

- [ ] **Step 1: 差分を確認**

Run: `git -C /Users/kado/dotfiles diff -- .claude/setup.sh .claude/settings.json`
Expected:
- `.claude/setup.sh`: `# Install claude-code-setup` ブロック（6 行）の追加のみ
- `.claude/settings.json`: `enabledPlugins` への 1 行追加（+ 既存行末カンマ追加）

無関係な変更が混じっていないことを確認する。

- [ ] **Step 2: ステージング**

Run: `git -C /Users/kado/dotfiles add .claude/setup.sh .claude/settings.json`

- [ ] **Step 3: コミット**

Run:
```bash
git -C /Users/kado/dotfiles commit -m "feat: manage claude-code-setup plugin via setup.sh and settings.json"
```

Expected: コミットが成功し、メッセージは Conventional Commits 形式（`feat:` プレフィックス）。

- [ ] **Step 4: ログを確認**

Run: `git -C /Users/kado/dotfiles log --oneline -3`
Expected:
- 最新コミット: `feat: manage claude-code-setup plugin via setup.sh and settings.json`
- その前: `docs: add design spec for claude-code-setup plugin management`

---

## Self-Review チェック結果

- **Spec coverage**:
  - 「`setup.sh` 実行時に冪等インストール」→ Task 1, 3
  - 「`enabledPlugins` で宣言的に有効化」→ Task 2
  - 「Git でレビュー可能」→ Task 4
  - 検証手順（1 回目／2 回目実行／`claude plugins list`） → Task 3
  - 設計ドキュメントの全要件をカバー
- **Placeholder scan**: TBD / TODO / "implement later" 等なし
- **Type consistency**: マーケットプレイス名 `claude-plugins-official`、プラグイン ID `claude-code-setup` を全タスクで統一

---

## 完了基準

1. `.claude/setup.sh` が冪等で `claude-code-setup` をインストールする
2. `.claude/settings.json` で `claude-code-setup@claude-plugins-official` が `true` になっている
3. `claude plugins list` で `claude-code-setup@claude-plugins-official` が `enabled` になっている
4. 上記の差分が `feature/add_claude_code_setup` ブランチに 1 コミット（`feat: …`）として記録されている
