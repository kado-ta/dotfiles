# Codex 設定の dotfiles 管理

## 目次

- [概要](#overview)
- [ディレクトリ構成](#directory-structure)
- [セットアップ（setup.sh）](#setup)
- [指示ファイル：AGENTS.md と developer_instructions](#instructions)
- [コマンド（zsh エイリアス）](#commands)
- [初期移行](#migration)
- [日常運用](#operations)
- [マージ仕様](#merge-spec)
- [既知の制約](#limitations)
- [バックアップ・復元](#backup)
- [トラブルシューティング](#troubleshooting)
- [セキュリティ上の注意](#security)
- [今後の改善候補](#future-work)
- [参考資料](#references)

<a name="overview"></a>
## 概要

Codex のユーザー設定 `~/.codex/config.toml` は、モデルや MCP の設定に加えて、プロジェクトの信頼設定（`[projects."..."]`）などを Codex 自身が更新する。そのまま Git 管理すると、プロジェクトを信頼するたびに差分が発生し、端末固有のパスまで Git に混入する。

このディレクトリでは、**Git 管理する共通設定**と **Codex が読み書きする実ファイル**を分離する。

- `~/.codex/config.toml`：Codex が実際に利用・更新する設定（Git 管理しない）。
- `~/.codex/config.local.toml`：端末固有の設定（Git 管理しない）。
- **`./config.base.toml`**：複数端末で共有したい設定の管理元。
- `./sync.py`：共通設定・端末固有設定を実ファイルへ反映する。
- `./import.py`：実ファイルで変更された設定を、確認のうえ共通設定へ取り込む。

**基本原則：自動的な双方向同期は行わない。** 通常は `sync`、Codex アプリ側の変更を共有したいときだけ `import` を実行する。

<a name="directory-structure"></a>
## ディレクトリ構成

```text
~/dotfiles/
├── .codex/                         # Git 管理
│   ├── README.md
│   ├── AGENTS.md                   # グローバル指示（~/.codex/AGENTS.md へリンク）
│   ├── config.base.toml            # 共通設定
│   ├── setup.sh                    # 初回セットアップ
│   ├── sync.py                     # base/local → config
│   └── import.py                   # config → base（明示的な操作）
└── zsh/
    └── alias.zsh                   # codex-config-sync / codex-config-import を定義

~/.codex/                           # Codex のユーザーデータ（CODEX_HOME）
├── AGENTS.md                       # → ~/dotfiles/.codex/AGENTS.md（シンボリックリンク）
├── config.toml                     # Codex の実設定（通常ファイル・Git 管理しない）
├── config.local.toml               # 端末固有設定（任意・Git 管理しない）
├── auth.json                       # 認証情報（Git 管理しない）
└── ...
```

### `.codex/` 内のファイル

| ファイル | 役割 | `~/.codex/` への反映方法 |
| --- | --- | --- |
| `README.md` | このドキュメント | なし |
| `AGENTS.md` | Codex のグローバル指示（ロール・回答方針・出力フォーマットなど） | `setup.sh` がシンボリックリンクを作成 |
| `config.base.toml` | 複数端末で共有する Codex 設定（モデル・`developer_instructions`・プラグイン・MCP など） | `sync.py` が `config.toml` へマージ |
| `setup.sh` | `AGENTS.md` のリンク作成と Understand Anything スキルのインストール | — |
| `sync.py` | `config.base.toml` + `config.local.toml` → `config.toml` | — |
| `import.py` | `config.toml` の変更を選択的に `config.base.toml` へ取り込む | — |

> **重要**
>
> `~/.codex/config.toml` は**通常ファイル**にする。`~/dotfiles/.codex/config.base.toml` や別の Git 追跡ファイルへのシンボリックリンクにしない。また、`~/.codex/` ディレクトリ全体を `~/dotfiles/.codex/` へのシンボリックリンクにしない。
>
> `~/dotfiles/.codex/` は dotfiles リポジトリ内の格納場所であり、Codex がプロジェクトごとに読み込む `<repository>/.codex/config.toml` とは役割が異なる。

### ファイルと変更権限

| ファイル | 主な変更者 | Git 管理 | 備考 |
| --- | --- | --- | --- |
| `~/dotfiles/.codex/AGENTS.md` | 人 | する | `~/.codex/AGENTS.md` からリンクされる |
| `~/dotfiles/.codex/config.base.toml` | 人（編集・import） | する | `[projects]` は記述しない |
| `~/dotfiles/.codex/sync.py` | 人 | する | Codex 設定反映スクリプト |
| `~/dotfiles/.codex/import.py` | 人 | する | Codex 設定取込スクリプト |
| `~/.codex/config.local.toml` | 人 | しない | 必要な端末だけ作成 |
| `~/.codex/config.toml` | Codex / sync.py | しない | `[projects]` を保持 |
| `~/.codex/auth.json` | Codex | しない | **絶対に Git へ追加しない** |

<a name="setup"></a>
## セットアップ（setup.sh）

### 前提条件

- macOS（`setup.sh` は macOS 以外では終了する）。
- `uv` が利用可能であること（`mise` 管理の場合は `uv --version` が成功すること）。
- Python 3.11 以上と `tomlkit` を使用する。いずれも `uv` が取得するため、個別の `pip install` や `.venv` 作成は不要。初回はネットワークが必要な場合がある。
- `zsh/alias.zsh` が読み込まれていること（Sheldon が `~/dotfiles/zsh/*.zsh` を読み込む）。

### `setup.sh` が行うこと

1. macOS であることを確認する。
2. `~/.codex/` がなければ作成する。
3. `~/dotfiles/.codex/AGENTS.md` を `~/.codex/AGENTS.md` へシンボリックリンクする（`ln -snfv`）。
4. Understand Anything スキルを Codex 向けにインストールする（GitHub の `install.sh` を `curl | bash` で実行）。

**`setup.sh` は `config.toml` を作成・変更しない。** 設定の反映は後述の `codex-config-sync` で行う。

### 実行手順

```bash
# 1. AGENTS.md のリンクとスキルのインストール
~/dotfiles/.codex/setup.sh

# 2. エイリアスを読み込む（新しいシェルを開いてもよい）
exec zsh

# 3. 既存の ~/.codex/config.toml がある場合は「初期移行」の手順を先に行う

# 4. 共通設定を ~/.codex/config.toml へ反映する
codex-config-sync --dry-run
codex-config-sync
```

`setup.sh` は何度実行してもよい（リンクは `ln -snfv` で張り直す）。ただしスキルのインストールは毎回リモートの最新版を取得する。

<a name="instructions"></a>
## 指示ファイル：AGENTS.md と developer_instructions

Codex への常設の指示は 2 か所で管理している。

| 観点 | `AGENTS.md` | `config.base.toml` の `developer_instructions` |
| --- | --- | --- |
| 実体 | `~/dotfiles/.codex/AGENTS.md`（Markdown） | `config.base.toml` 内の TOML 複数行文字列 |
| Codex への渡り方 | `~/.codex/AGENTS.md`（`CODEX_HOME` 直下）をグローバル指示として読み込む | 設定値として、セッションに developer instructions として注入される |
| 反映方法 | シンボリックリンクなので、**編集後に Codex を再起動するだけ** | **`codex-config-sync` が必要**（`config.toml` へマージされて初めて有効） |
| プロジェクトの `AGENTS.md` との関係 | プロジェクトルートから現在ディレクトリまでの `AGENTS.md` と連結され、**現在ディレクトリに近いファイルが優先**される | プロジェクトの `AGENTS.md` とは独立して常に注入される |
| サイズ | `project_doc_max_bytes`（既定 32 KiB）を超えると以降が読み込まれない | 明示的な上限はないが、毎セッションのコンテキストを消費する |
| 置き換え | `~/.codex/AGENTS.override.md` があればそちらが優先される | 端末ごとに変えたい場合は `config.local.toml` で上書きできる |

### 使い分け

- **`developer_instructions`**：どのリポジトリでも必ず守らせたい、短く安定した**行動ルール**を書く。
  - 例：思考は英語・出力は日本語、セーフティルール、テストポリシー、変更報告フォーマット、Git/GitHub ルール、判断優先順位、Claude Code との連携役割（レビュアー・コンサルタントとしての振る舞い）。
  - Claude Code の `~/.claude/CLAUDE.md` に相当する内容を Codex 向けに置く場所。
- **`AGENTS.md`**：Codex の**人格・回答スタイル・汎用的な作業方針**を書く。
  - 例：ロール（CTO・テックリード視点のカウンターパート）、情報の検証方針、分析・意思決定支援の進め方、出力フォーマット、Markdown リンク規約。
  - 分量が多く、頻繁に推敲する内容に向く（sync 不要で反映できるため）。
- **プロジェクト固有のルール**はどちらにも書かず、各リポジトリの `AGENTS.md` に書く。

### 編集時の注意

- 同じ規則を両方に書かない。現在は「日本語で出力する」「テスト未実行を成功扱いしない」などが重複しているため、変更時はもう一方との整合を確認する。
- 両者が矛盾すると、どちらが優先されるかの挙動に依存することになる。矛盾させないことを前提に運用する。
- `developer_instructions` を Codex アプリ側で変更した場合も、`codex-config-import --key developer_instructions --apply` で取り込める。

<a name="commands"></a>
## コマンド（zsh エイリアス）

`zsh/alias.zsh` に以下のエイリアスを定義している。Sheldon 経由で読み込まれるため、追加・変更後は新しいシェルを開くか `exec zsh` を実行する。

```zsh
alias codex-config-sync='uv run --no-project --with "tomlkit>=0.13,<1" python "$HOME/dotfiles/.codex/sync.py"'
alias codex-config-import='uv run --no-project --with "tomlkit>=0.13,<1" python "$HOME/dotfiles/.codex/import.py"'
```

| エイリアス | 実行内容 | 主なオプション |
| --- | --- | --- |
| `codex-config-sync` | `sync.py`：base/local を `~/.codex/config.toml` へ反映 | `--dry-run` |
| `codex-config-import` | `import.py`：`config.toml` の変更を `config.base.toml` へ取り込む | `--key <KEY>`（複数可）、`--all-managed`、`--apply` |

- `--no-project`：カレントディレクトリの `pyproject.toml` を無視して実行する。
- `--with "tomlkit>=0.13,<1"`：`python <script>` 形式で実行するとスクリプト先頭の PEP 723 メタデータが読まれないため、依存関係を明示している。
- エイリアスを使わない場合は、PEP 723 メタデータを利用して直接実行できる。

  ```bash
  uv run --no-project "$HOME/dotfiles/.codex/sync.py" --dry-run
  ```

### チートシート

| 目的 | コマンド | 書き込み先 |
| --- | --- | --- |
| 共通・端末設定の反映差分を確認 | `codex-config-sync --dry-run` | なし |
| 共通・端末設定を Codex に反映 | `codex-config-sync` | `~/.codex/config.toml` |
| Codex 側の変更候補を確認 | `codex-config-import` | なし |
| 1 項目を共通設定へ取り込む | `codex-config-import --key model_reasoning_effort --apply` | `config.base.toml` |
| 複数項目を取り込む | `codex-config-import --key model --key model_reasoning_effort --apply` | `config.base.toml` |
| Git 管理済み項目を一括で取り込む | `codex-config-import --all-managed --apply` | `config.base.toml` |
| 新しい項目を明示的に取り込む | `codex-config-import --key features.some_flag --apply` | `config.base.toml` |
| 取り込み後の Git 差分を確認 | `git -C "$HOME/dotfiles" diff -- .codex/config.base.toml` | なし |

`features.some_flag` は指定方法を示す**仮のキー名**であり、実際に利用できる Codex 設定であることを意味しない。

`--apply` を付けなければ `import.py` はプレビューのみ。`sync.py` では `--dry-run` がプレビューに相当する。

<a name="migration"></a>
## 初期移行

既存の `~/.codex/config.toml` がある端末で、この仕組みへ移行するときの手順。新規環境では手順 3 以降のみでよい。

**Codex Desktop App と Codex CLI を終了してから実施する。** 既存の信頼設定を失わないことを最優先する。

### 1. 既存設定のバックアップ

```bash
cp -L "$HOME/.codex/config.toml" \
  "$HOME/.codex/config.toml.pre-dotfiles.bak"
chmod 600 "$HOME/.codex/config.toml.pre-dotfiles.bak"
```

### 2. `config.toml` を通常ファイルにする

まず確認する。

```bash
ls -l "$HOME/.codex/config.toml"
```

シンボリックリンクの場合**のみ**、リンク先の内容をコピーして置き換える。

```bash
cp -L "$HOME/.codex/config.toml" \
  "$HOME/.codex/config.toml.detached"

rm "$HOME/.codex/config.toml"
mv "$HOME/.codex/config.toml.detached" "$HOME/.codex/config.toml"
chmod 600 "$HOME/.codex/config.toml"
```

Stow / chezmoi などでリンクを自動作成している場合、その設定からも `config.toml` を除外する。**再デプロイでリンクが復活しないようにすること。**

### 3. 共通設定・端末固有設定を用意する

`~/dotfiles/.codex/config.base.toml` に、共有したい設定だけを記述する。

```toml
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
```

`[projects]`、認証情報、ローカルだけで使う MCP 設定は含めない。ホームディレクトリ配下のパスは `~/` で記述する（`sync.py` が実行環境の絶対パスへ展開する）。値やキーの有効性は使用中の Codex バージョンの公式設定リファレンスで確認する。

端末固有の上書きが必要な場合のみ `~/.codex/config.local.toml` を作成する。

```toml
model_reasoning_effort = "xhigh"
```

### 4. Dry Run で確認し、同期する

```bash
codex-config-sync --dry-run
codex-config-sync
```

差分のなかで、既存の `[projects."..."]` が削除されないことを確認する。`sync.py` は更新前に `~/.codex/config.toml.backup-<timestamp>` を作成する。

### 5. Git の追跡範囲を確認する

`config.toml` や、その一時バックアップを dotfiles リポジトリに置いた場合は、追跡されていないことを確認する。

```bash
git -C "$HOME/dotfiles" ls-files -- .codex/config.toml
git -C "$HOME/dotfiles" status --short -- .codex/
```

必要に応じて dotfiles リポジトリ直下の `.gitignore` に追加する。

```gitignore
/.codex/config.toml
/.codex/config.toml.bak
/.codex/config.local.toml
```

`.gitignore` は**既に追跡されているファイルには効かない**（`git rm --cached` が必要）。また、過去のコミットに残った信頼設定や秘密情報も削除されないため、公開履歴への混入があれば別途対処が必要。

コミットするのは `README.md`、`AGENTS.md`、`config.base.toml`、`setup.sh`、`sync.py`、`import.py` などの共有ファイルだけ。

<a name="operations"></a>
## 日常運用

### A. Codex が新しい `[projects]` を追加した

**何もしなくてよい。** `~/.codex/config.toml` は Git 管理対象外なので、信頼設定の追加だけで Git 差分は発生しない。次回 `sync.py` を実行しても、既存の `[projects]` は保持する設計。

```toml
[projects."/Users/example/Dev/my-project"]
trust_level = "trusted"
```

### B. 共通設定（`developer_instructions` を含む）を変更した

1. `~/dotfiles/.codex/config.base.toml` を編集する。
2. Codex を終了する。
3. `codex-config-sync --dry-run` で確認する。
4. `codex-config-sync` で反映する。
5. `git diff` で確認し、必要に応じてコミットする。

```bash
codex-config-sync --dry-run
codex-config-sync
git -C "$HOME/dotfiles" diff -- .codex/config.base.toml
```

### C. `AGENTS.md` を変更した

`~/dotfiles/.codex/AGENTS.md` を編集し、Codex を再起動する。シンボリックリンク経由で読み込まれるため、`sync` は不要。

### D. Codex Desktop App / CLI で共通設定を変更した

`config.toml` を編集しただけでは **`config.base.toml` に自動反映されない**。

1. Codex を終了する。
2. **先に `sync` を実行しない。** アプリ側の変更が base の値で上書きされることがある。
3. `codex-config-import` で候補を確認する。
4. `--key ... --apply` で共有したいキーだけ取り込む。
5. Git の差分をレビューしてコミットする。

```bash
codex-config-import
codex-config-import --key model_reasoning_effort --apply

git -C "$HOME/dotfiles" diff -- .codex/config.base.toml
```

`--all-managed --apply` は一括取り込みのため、共有設定の未反映変更がないことを確認できた場合だけ使用する。

### E. 端末固有設定を変更した

`~/.codex/config.local.toml` を編集し、`codex-config-sync --dry-run` → `codex-config-sync` を実行する。local は base より優先され、Git にコミットしない。

### F. 別の Mac に展開する

1. dotfiles をクローンし、`uv` と `zsh/alias.zsh` を使える状態にする。
2. [セットアップ（setup.sh）](#setup) の手順を実行する。
3. 信頼設定はその Mac の Codex 側で個別に設定する。

端末 A の `[projects]` は端末 B へ自動同期されない。

<a name="merge-spec"></a>
## マージ仕様

### sync.py：base/local → config

既存の `config.toml` を保持したうえで設定値を再帰的に上書きする。

**優先順位（高 → 低）**

1. `config.local.toml`
2. `config.base.toml`
3. 既存の `config.toml`

**例外：** `[projects]` は base/local に記述を禁止し（記述するとエラー）、既存の `config.toml` の値を維持する。

| 変更 | `sync.py` の動作 |
| --- | --- |
| base にあるキーを更新 | 実ファイルへ反映 |
| local にあるキーを更新 | base より優先して反映 |
| Codex が `[projects]` を追加 | 保持 |
| base/local にない未知のキー | 既存値を保持 |
| base からキーを削除 | **既存の実ファイルからは削除しない** |
| base の文字列中の `~/` | 実行環境のホームディレクトリの絶対パスへ展開 |

### import.py：config → base

`config.base.toml` に既に存在する**設定項目単位**の差分を候補として表示する。`--key` を指定すると、存在しない新規項目も明示的に追加できる。base に未登録の項目は「Git 管理されていない設定」として一覧表示する。

取り込む文字列中のホームディレクトリの絶対パスは `~` に置き換える。

常に除外するもの：

- `[projects]` 配下の信頼設定
- `config.local.toml` が管理する項目
- 機密性の高いキー（`secret` / `password` / `token` / `api_key` / `private_key` を含むキー名、および `env` / `headers` / `http_headers` / `env_http_headers` / `authorization`）
  - base に既に存在していても import では更新されない。必要なら `config.base.toml` を直接編集する。
- テーブル全体（項目単位でのみ取り込む）
- `config.toml` に存在しない項目（削除としては反映しない）

**注意：** 保護ルールはキー名に基づくヒューリスティックであり、秘密情報の完全な検出はできない。特に MCP の `command`、`args`、URL などの**値**に秘密情報や端末固有のパスが埋め込まれる場合がある。取り込み後は必ず Git 差分を確認する。

<a name="limitations"></a>
## 既知の制約

1. **双方向の自動同期はしない。** `sync` と `import` は明示的に実行する。
2. **3-way merge は未実装。** 前回同期時点のスナップショットを持たず、base と config の差から「どちらが先に変更されたか」を判断できない。未同期の base 更新がある状態で import すると変更を巻き戻すおそれがある。
3. **削除を伝播しない。** base からの削除も、config からの削除も相手側へ自動反映しない。不要になった項目は両方から明示的に削除するか、スクリプトを拡張する。
4. **同時書き込みの完全な競合防止は未実装。** 読み込み後の変更は検出して中止するが、Codex の設定更新と `--apply` / `sync` が重ならないよう、アプリ・CLI を終了してから実行する。
5. **TOML のコメント・書式は可能な範囲で保持。** `tomlkit` を利用するが、すべての書式差分が不変であることは保証しない。
6. **新しい Codex 設定の互換性は別途確認する。** TOML として妥当でも、Codex の設定キーとして有効とは限らない。
7. **自動テストはない。** 個々の環境・Codex バージョンに対する回帰テストは未整備。

<a name="backup"></a>
## バックアップ・復元

| 操作 | バックアップ先 |
| --- | --- |
| 初期移行 | `~/.codex/config.toml.pre-dotfiles.bak` |
| `sync.py` による更新 | `~/.codex/config.toml.backup-<timestamp>` |
| `import.py --apply` | `~/.codex/config-import-backups/config.base-<timestamp>.toml` |

バックアップの一覧：

```bash
ls -l "$HOME/.codex"/config.toml.backup-* 2>/dev/null
ls -l "$HOME/.codex/config-import-backups/" 2>/dev/null
```

実ファイルを戻す例（**Codex 終了後**）：

```bash
cp "$HOME/.codex/config.toml.pre-dotfiles.bak" \
   "$HOME/.codex/config.toml"
chmod 600 "$HOME/.codex/config.toml"
```

インポート後の共通設定は Git 履歴からも復元できる。バックアップには端末固有情報や秘密情報が含まれる可能性があるため、共有・Git 管理しない。

<a name="troubleshooting"></a>
## トラブルシューティング

**`codex-config-sync: command not found`**

- `zsh/alias.zsh` が読み込まれていない。新しいシェルを開くか `exec zsh` を実行する。

**`ModuleNotFoundError: No module named 'tomlkit'`**

- `python <script>` 形式で実行すると PEP 723 メタデータが読まれない。エイリアスを使うか、`uv run --no-project <script.py>` で直接実行する。

**`config.toml がシンボリックリンクです`**

- `sync.py` はリンクを更新しない設計。[初期移行](#migration) の手順に従って通常ファイル化する。
- Stow / chezmoi 等の管理設定も見直す。

**`config.base.toml に [projects] を記述しないでください`**

- base/local から `[projects]` を削除する。信頼設定は `config.toml` だけで管理する。

**base の変更が config に反映されない**

- `config.local.toml` に同じ設定がないか確認する（local 優先）。
- `codex-config-sync --dry-run` を確認する。

**`AGENTS.md` の変更が反映されない**

- Codex を再起動する（指示は起動時に読み込まれる）。
- `ls -l ~/.codex/AGENTS.md` でリンク先を確認し、必要なら `setup.sh` を再実行する。
- `~/.codex/AGENTS.override.md` が存在すると、そちらが優先される。

**Codex アプリで変更した設定が元に戻った**

- `sync.py` が `config.base.toml` / `config.local.toml` の値を優先するため。
- Codex 側の変更を共通設定に取り込みたい場合は、次回の `sync` より**前に** `codex-config-import` を実行する。

**`codex-config-import` で新規項目が反映されない**

- 新規キーは自動インポートされない。`--key path.to.key --apply` を明示する。
- local 管理・保護対象・存在しないキー・テーブル全体は除外される。

**`CODEX_HOME` をカスタマイズしている**

- 両スクリプトは `CODEX_HOME` が定義されていれば、そのディレクトリ内の `config.toml` / `config.local.toml` を使用する。
- `CODEX_HOME` によって **実ファイル側** のパスが変わる。`config.base.toml` はスクリプトの配置先を基準にする。
- `setup.sh` は `~/.codex` 固定でリンクを作成する点に注意する。

<a name="security"></a>
## セキュリティ上の注意

- `auth.json`、API キー、アクセストークン、秘密鍵を Git に登録しない。
- 信頼設定は端末ローカルの状態として扱い、機械的に全プロジェクトを信頼済みにしない。
- Git への `add` / `commit` の前に `git diff --staged` で値を確認する。
- 端末固有パスや MCP サーバーの引数、環境変数の値も点検する。
- バックアップや `config.local.toml` には、適切なアクセス権を設定する。
- `setup.sh` はリモートのインストールスクリプトを `curl | bash` で実行する。取得元を変更する場合は内容を確認する。
- 組織のセキュリティ要件に関わる場合は、専門家への確認が必要。

<a name="future-work"></a>
## 今後の改善候補

- 前回同期状態をローカルに保持した **3-way merge** と競合検出。
- base から削除されたキーの同期反映（明示承認付き）。
- dry-run を利用した自動テスト／サンプル TOML の回帰テスト。
- `import.py` のキー名・値に対する機密情報検査の強化。
- 不要バックアップの世代管理。

<a name="references"></a>
## 参考資料

- [OpenAI Codex: Configuration Reference](https://developers.openai.com/codex/config-reference)
- [OpenAI Codex: Config Basics](https://developers.openai.com/codex/config-basic)
- [OpenAI Codex: AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [uv: Running scripts / Inline script metadata](https://docs.astral.sh/uv/guides/scripts/)
- [PEP 723: Inline script metadata](https://peps.python.org/pep-0723/)
- [tomlkit: GitHub](https://github.com/python-poetry/tomlkit)
- [Git: gitignore](https://git-scm.com/docs/gitignore)
