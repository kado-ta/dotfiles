# Design: claude-code-setup プラグインの管理

- 作成日: 2026-04-30
- 対象ブランチ: feature/add_claude_code_setup
- ステータス: ドラフト

## 背景

Anthropic 公式 Marketplace `claude-plugins-official` にある `claude-code-setup` プラグインを、このリポジトリで配布管理対象に加えたい。
本リポジトリの `.claude/setup.sh` は既に同じ Marketplace の `superpowers` を冪等インストールしており、`.claude/settings.json` の `enabledPlugins` で有効化を記録している。
同等のパターンを使い、新しいマシンでも `setup.sh` を 1 回流せば `claude-code-setup` がインストール済み・有効状態で再現できるようにする。

## ゴール

- `setup.sh` を実行すると `claude-code-setup@claude-plugins-official` が自動でインストールされ、有効化されている。
- すでにインストール済みの環境では再インストールを行わない（冪等）。
- 設定の真実は `.claude/settings.json` および `.claude/setup.sh` に集約され、Git でレビュー可能。

## 非ゴール

- `superpowers` インストール処理の共通化／関数化。
- 別 Marketplace の追加。
- `claude-code-setup` プラグイン自体の機能追加・改変。
- README への利用方法の詳細追記（既存方針と同じく `setup.sh` の中身が一次資料）。

## 採用案: A — `superpowers` パターンを踏襲

`.claude/setup.sh` 内の `superpowers` インストールブロックの直後に、同じ書式の冪等インストールブロックを追加し、`.claude/settings.json` の `enabledPlugins` にエントリを 1 行加える。

### 変更点

#### 1. `.claude/setup.sh`

`superpowers` インストールブロックの直下に以下を追加する:

```sh
# Install claude-code-setup
if claude plugins list 2>/dev/null | grep -q " claude-code-setup@claude-plugins-official$"; then
  echo "claude-code-setup plugin already installed, skipping"
else
  claude plugins install claude-code-setup@claude-plugins-official
fi
```

`grep -q " claude-code-setup@claude-plugins-official$"` の先頭スペースは、`claude plugins list` 出力が `❯ <name>@<marketplace>` の形式で、名前の前にスペースが入るため必要。末尾 `$` は将来同名プレフィックス（例: `claude-code-setup-extra`）と衝突しないために付ける（既存 `superpowers` 行と同方針）。

#### 2. `.claude/settings.json`

`enabledPlugins` に 1 行追加する:

```json
"enabledPlugins": {
  "superpowers@claude-plugins-official": true,
  "claude-code-setup@claude-plugins-official": true
}
```

### 不採用案

- **B. インストール処理の共通関数化**: `install_plugin <name>` をシェル関数化して `superpowers` も置き換える。プラグインが 3 つ以上に増えた段階で再考する。今は 2 つで早期抽象化となり、既存ブロックも触るため最小差分原則に反する。
- **C. プラグイン名の配列＋ループ**: `for plugin in "${plugins[@]}"; do …` パターン。最も拡張性が高いが、要素 2 個では明確にオーバーキル。

## 影響範囲

- 影響先は Claude Code 環境のみ（シェル設定や Brew 等は無関係）。
- 既存ユーザーの `~/.claude/settings.json` は `setup.sh` 実行時にシンボリックリンクで本リポジトリの `settings.json` を指しているため、`enabledPlugins` 追記は次回 Claude Code 起動時から反映される。
- `claude-code-setup` プラグインは「読み取り専用で codebase を分析し提案を返す」ものなので、ファイル書き換えなどの副作用はない。

## 検証

1. `.claude/setup.sh` を 1 回実行
   - 期待: `claude-code-setup` のインストールが走り、終了ステータス 0
2. もう一度 `.claude/setup.sh` を実行
   - 期待: `claude-code-setup plugin already installed, skipping` が出力される（冪等）
3. `claude plugins list` で `claude-code-setup@claude-plugins-official` が `Status: ✔ enabled` になっていることを確認
4. `.claude/settings.json` が JSON Schema (`https://json.schemastore.org/claude-code-settings.json`) に違反しないことを確認

## オープン項目

なし。
