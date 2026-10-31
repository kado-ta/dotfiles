# Obsidian 設定の dotfiles 管理

## 目次

- [概要](#overview)
- [ディレクトリ構成](#directory-structure)
- [セットアップ](#setup)
- [管理している設定](#managed-settings)
- [管理対象外のファイル](#unmanaged-files)
- [日常運用](#operations)
- [既知の制約・注意点](#limitations)
- [関連ドキュメント](#related-docs)

<a name="overview"></a>
## 概要

このディレクトリでは、Obsidian の Vault 設定ディレクトリ（`.obsidian/`）のうち、端末間で揃えたい**設定ファイルと CSS スニペット**を管理する。対象 Vault は `~/Obsidian/main/`。

- `setup.sh` が、このディレクトリの設定ファイルと `snippets/` を `~/Obsidian/main/.obsidian/` にシンボリックリンクする。
- コミュニティプラグインは有効化リストだけを管理し、プラグイン本体と各プラグインの設定（`plugins/*/data.json`）は管理しない。
- ノート・添付ファイルは別の仕組みで扱う。端末間同期は Remotely Save + Cloudflare R2、バックアップは obsidian-git + GitHub で行い、`.obsidian/` はどちらの対象にもしない（[SYNC_BACKUP.md](SYNC_BACKUP.md) 参照）。

<a name="directory-structure"></a>
## ディレクトリ構成

```text
~/dotfiles/.obsidian/
├── README.md
├── SYNC_BACKUP.md            # Vault の端末間同期・バックアップの方針と手順
├── setup.sh                  # 設定ファイルと snippets/ を Vault へシンボリックリンクする
├── app.json                  # ファイルとリンク
├── appearance.json           # 有効にする CSS スニペット
├── community-plugins.json    # 有効にするコミュニティプラグイン
├── core-plugins.json         # コアプラグインの ON/OFF
├── graph.json                # グラフビューの表示設定
├── hotkeys.json              # ホットキー
└── snippets/                 # Typora 風表示の CSS スニペット
    ├── README.md
    ├── typora-like.css
    └── typora-mermaid.css
```

`setup.sh` 実行後の Vault 側は次のようになる。

```text
~/Obsidian/main/.obsidian/
├── app.json -> ~/dotfiles/.obsidian/app.json
├── appearance.json -> ~/dotfiles/.obsidian/appearance.json
├── community-plugins.json -> ~/dotfiles/.obsidian/community-plugins.json
├── core-plugins.json -> ~/dotfiles/.obsidian/core-plugins.json
├── graph.json -> ~/dotfiles/.obsidian/graph.json
├── hotkeys.json -> ~/dotfiles/.obsidian/hotkeys.json
├── snippets -> ~/dotfiles/.obsidian/snippets
├── plugins/                  # 管理対象外
├── workspace.json            # 管理対象外
└── ...
```

<a name="setup"></a>
## セットアップ

<a name="setup-prerequisites"></a>
### 前提条件

- macOS（`setup.sh` は macOS 以外では終了する）。
- Obsidian がインストール済みであること（`.bin/.Brewfile` の `cask "obsidian"`）。
- `~/Obsidian/main/` に Vault を作成済みで、`~/Obsidian/main/.obsidian/` が存在すること。`setup.sh` はディレクトリを作成しないため、存在しないとリンクの作成に失敗して終了する。

<a name="setup-steps"></a>
### 手順

1. Obsidian を閉じる。
2. `setup.sh` を実行する。何度実行してもよい。

   ```bash
   ~/dotfiles/.obsidian/setup.sh
   ```

3. Obsidian を起動し、`Settings → Community plugins → Browse` から [コミュニティプラグイン](#community-plugins) をインストールする。
4. 各プラグインを設定する。
   - Remotely Save / Git: [SYNC_BACKUP.md](SYNC_BACKUP.md)
   - CSS スニペットと Mermaid Kit: [snippets/README.md の適用方法](snippets/README.md#setup)

新しい端末で Vault の同期・バックアップまで含めて用意する場合は、[SYNC_BACKUP.md の新しい端末のセットアップ手順](SYNC_BACKUP.md#new-device) に従う（その手順 2 でこのスクリプトを実行する）。

> [!WARNING]
> `setup.sh` は、Vault 側の既存の設定ファイルを確認なしでシンボリックリンクに置き換える（`ln -snf`）。`snippets/` が実ディレクトリの場合は `rm -rf` で削除してからリンクする。Vault 側の設定やスニペットに残したい内容がある場合は、実行前にこのディレクトリへ反映する。

<a name="managed-settings"></a>
## 管理している設定

<a name="app-json"></a>
### `app.json`: ファイルとリンク

| キー | 値 | 設定画面（`Settings → Files and links`） | 内容 |
|---|---|---|---|
| `useMarkdownLinks` | `true` | `Use [[Wikilinks]]`: OFF | 内部リンクを Wikilink（`[[...]]`）ではなく Markdown リンク（`[表示名](パス.md)`）で作成する |
| `newLinkFormat` | `"relative"` | New link format: Relative path to file | 新しく作るリンクのパスを、リンク元ノートからの相対パスにする |
| `alwaysUpdateLinks` | `true` | Automatically update internal links: ON | ファイルの移動・リネーム時に、確認なしで内部リンクを更新する |

`useMarkdownLinks` と `newLinkFormat` は、ノートを GitHub・Typora でも同じように読めるようにするための設定（[MARKDOWN.md](../.claude/rules/MARKDOWN.md) の方針に合わせている）。相対パスにするのは、GitHub・Typora がリンクをリンク元ファイルからの相対パスとして解決するため。

<a name="appearance-json"></a>
### `appearance.json`: 外観

`enabledCssSnippets` で `typora-like` と `typora-mermaid` を有効にする。

テーマとフォントは指定せず、既定（Default テーマ・フォント指定なし）のままにしている。CSS スニペットはこの状態を前提にしている（[前提となる Obsidian の設定](snippets/README.md#prerequisites) 参照）。

<a name="community-plugins"></a>
### `community-plugins.json`: コミュニティプラグイン

有効にするプラグインの ID を列挙する。プラグイン本体は管理しないため、端末ごとにインストールする（未インストールのプラグインは有効にならない）。

| ID | プラグイン名 | 用途 |
|---|---|---|
| `remotely-save` | Remotely Save | Cloudflare R2 経由の端末間同期（[SYNC_BACKUP.md](SYNC_BACKUP.md#sync)） |
| `obsidian-git` | Git | GitHub へのバックアップ（[SYNC_BACKUP.md](SYNC_BACKUP.md#backup)） |
| `mermaid-kit` | Mermaid Kit | Mermaid 図の拡大・縮小・パン・全画面表示（[snippets/README.md](snippets/README.md)） |
| `html-viewer` | HTML Viewer | Vault 内の `.html` ファイルをサンドボックス内で表示する |

<a name="core-plugins-json"></a>
### `core-plugins.json`: コアプラグイン

コアプラグインごとの ON/OFF を持つ。OFF にしているのは次のプラグインで、それ以外はすべて ON。

| ID | 設定画面での名前 |
|---|---|
| `footnotes` | Footnotes view |
| `slash-command` | Slash commands |
| `zk-prefixer` | Unique note creator |
| `random-note` | Random note |
| `slides` | Slides |
| `audio-recorder` | Audio recorder |
| `workspaces` | Workspaces |
| `publish` | Publish |
| `sync` | Sync |
| `webviewer` | Web viewer |

`sync`（Obsidian Sync）を OFF にしているのは、端末間同期を Remotely Save に一本化しているため（[SYNC_BACKUP.md](SYNC_BACKUP.md#policy) 参照）。

<a name="graph-json"></a>
### `graph.json`: グラフビュー

グラフビューのフィルタ・表示・力学の設定。タグと添付ファイルを表示せず、孤立ノードを表示し、矢印を表示しない。リンク距離は `250`。

<a name="hotkeys-json"></a>
### `hotkeys.json`: ホットキー

既定から変更したホットキーだけを持つ。

| キー | コマンド |
|---|---|
| `⌥⌘T` | Open in default app（現在のファイルを OS の既定アプリで開く） |

<a name="snippets-dir"></a>
### `snippets/`: CSS スニペット

Obsidian の本文と Mermaid 図を Typora 風（ライトは GitHub テーマ、ダークは Night テーマ相当）に表示する `typora-like.css` と `typora-mermaid.css`。詳細は [snippets/README.md](snippets/README.md) を参照。

<a name="unmanaged-files"></a>
## 管理対象外のファイル

`setup.sh` がリンクしないファイルは Vault 側にだけ保存され、他の端末には反映されない（Remotely Save の Sync Config Dir は無効で、Vault の `.gitignore` でも `.obsidian/` を除外しているため。[SYNC_BACKUP.md](SYNC_BACKUP.md#policy) 参照）。

| ファイル | 内容・扱い |
|---|---|
| `plugins/` | コミュニティプラグイン本体と各プラグインの設定（`data.json`）。Remotely Save の `data.json` には R2 の認証情報が含まれるため、dotfiles に入れない。端末ごとにインストール・設定する |
| `workspace.json` | 開いているタブ・ペインの配置など、端末ごとに変わる状態 |
| `themes/` | コミュニティテーマ。CSS スニペットは Default テーマを前提とするため使わない |
| 上記以外（`daily-notes.json` など） | UI で設定すると Vault 側に作られる。端末間で揃えたい場合は [設定ファイルを管理対象に加える](#add-managed-file) |

<a name="operations"></a>
## 日常運用

<a name="change-settings"></a>
### Obsidian の UI で設定を変更した

リンク済みのファイルは、Obsidian がリンク先（このディレクトリのファイル）を直接書き換える。変更後は差分を確認してコミットする。

```bash
git -C ~/dotfiles diff -- .obsidian/
```

<a name="edit-snippets"></a>
### CSS スニペットを編集した

`Settings → Appearance → CSS snippets` の再読み込みアイコンで反映する（[snippets/README.md](snippets/README.md#setup) 参照）。

<a name="add-managed-file"></a>
### 設定ファイルを管理対象に加える

1. Obsidian を閉じ、Vault の `.obsidian/` から対象ファイルをこのディレクトリへコピーする。
2. `setup.sh` に `ln -snfv` の行を追加し、実行する。
3. この README の [ディレクトリ構成](#directory-structure) と [管理している設定](#managed-settings) を更新する。

認証情報を含むファイル（`plugins/*/data.json` など）は加えない。

<a name="other-vaults"></a>
### 他の Vault に設定を反映する

`setup.sh` は `~/Obsidian/main/` だけを対象とする。他の Vault には、このディレクトリのファイルをその Vault の `.obsidian/` へコピーする。

<a name="limitations"></a>
## 既知の制約・注意点

1. **対象 Vault のパスは固定。** `setup.sh` の `OBSIDIAN_DIR`（`~/Obsidian/main/.obsidian`）に直書きしている。
2. **プラグインのバージョンと設定は端末間で自動的に揃わない。** プラグイン本体と `data.json` を管理しないため、端末ごとに更新・設定する。
3. **自動テストはない。** 変更後は Obsidian で表示と設定画面を確認する。

<a name="related-docs"></a>
## 関連ドキュメント

- [SYNC_BACKUP.md](SYNC_BACKUP.md): Vault の端末間同期（Remotely Save + Cloudflare R2）と Git/GitHub によるバックアップ
- [snippets/README.md](snippets/README.md): Typora 風表示の CSS スニペット
- [.claude/rules/MARKDOWN.md](../.claude/rules/MARKDOWN.md): Markdown の記法ルール
