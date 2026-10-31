# Obsidian CSS スニペット（Typora 風表示）

Obsidian 標準の Markdown / Mermaid の表示が読みづらいため、Typora に近い見た目にする CSS スニペット。ライトモードは Typora の **GitHub** テーマ、ダークモードは **Night** テーマに合わせる。

- [ファイル構成](#files)
- [適用方法](#setup)
- [前提となる Obsidian の設定](#prerequisites)
- [動作確認](#verify)
- [カスタマイズ](#customize)
- [既知の制約](#limitations)
- [参考](#references)

<a name="files"></a>
## ファイル構成

| ファイル | 役割 |
|---|---|
| `typora-like.css` | 本文（見出し・表・引用・コード・リンクなど）を Typora GitHub / Night 風にする |
| `typora-mermaid.css` | Mermaid 図を Typora 相当の配色にし、初期表示で図全体が表示領域に収まるようにする |

- 2 つのスニペットは独立しており、個別に ON/OFF できる。
- ライト / ダークの切り替えは Obsidian 本体の設定に従い、CSS が自動で追従する。
- Mermaid 図の拡大・縮小・パン・全画面表示は CSS では実現できないため、コミュニティプラグイン **Mermaid Kit** を併用する。

<a name="setup"></a>
## 適用方法

`../setup.sh` が、このディレクトリを `~/Obsidian/main/.obsidian/snippets` にシンボリックリンクする。スニペットの有効化は `../appearance.json`（`enabledCssSnippets`）、Mermaid Kit の有効化は `../community-plugins.json` で管理している。

1. Obsidian を閉じた状態で `../setup.sh` を実行する。
2. Obsidian を起動し、`Settings → Appearance → CSS snippets` で `typora-like` と `typora-mermaid` が ON になっていることを確認する。
3. `Settings → Community plugins` から **Mermaid Kit** をインストールする（プラグイン本体は dotfiles で管理していない）。

> [!WARNING]
> `setup.sh` は、Vault に実ディレクトリの `.obsidian/snippets/` があると削除してからシンボリックリンクに置き換える。Vault 側にだけ置いたスニペットがある場合は、先にこのディレクトリへ移す。

スニペットを編集したら、`Settings → Appearance → CSS snippets` の再読み込みアイコンで反映する。

<a name="prerequisites"></a>
## 前提となる Obsidian の設定

| 設定箇所 | 設定値 | 理由 |
|---|---|---|
| `Appearance → Themes` | Default | スニペットは Default テーマの CSS 変数を上書きする前提のため。コミュニティテーマとは変数が競合する |
| `Appearance → Font`（Text font / Monospace font） | 空欄 | 指定があるとスニペットのフォント指定より優先されるため |
| `Appearance → Font size` | 16（既定） | Typora の基準文字サイズに合わせるため |
| `Editor → Readable line length` | ON（既定） | 本文の最大幅を Typora の本文幅に合わせるため |
| `Mermaid Kit → Match diagrams to the theme` | ON（既定） | OFF にするとスニペットで配色していない要素が Mermaid 既定のライト配色になり、ダークモードで浮いて見えるため |

対象環境:

| 項目 | 内容 |
|---|---|
| Obsidian | デスクトップ版 1.14 系（同梱 Mermaid 11.13.0） |
| Mermaid Kit | 1.1.2 |
| 対象ビュー | Reading view は全面対応。Live Preview は一部（CSS 変数・見出し下線・字間・インラインコード・表）のみ |
| フォント | `Open Sans` が未インストールの場合は Helvetica Neue / ヒラギノ等で表示される |

> [!WARNING]
> **Obsidian 1.15 以降では `typora-mermaid.css` の配色が効かない**
> 1.15 は Mermaid の代わりに独自ライブラリ Pele で図を描画し、要素のクラス名と配色の指定方法（`--mermaid-*` 変数）が変わる。1.15 に上げたら `typora-mermaid.css` を OFF にし、配色を作り直す。`typora-like.css` は Mermaid に依存しない。

<a name="verify"></a>
## 動作確認

確認用ノートの内容は元ノートの「動作確認」にある。ライト / ダーク、Reading view / Live Preview それぞれで次を確認する。

- ライトモードで h1 / h2 に下線があり、表が全周罫線＋偶数行ストライプになっている
- ダークモードで背景が `#363B40`、本文が `#b8bfc6`、リンクに下線がある
- Mermaid のノード色がライトは薄紫（`#ECECFF`）、ダークは薄青（`#BDD5EA`）で、ダークモードで暗く反転していない
- `classDef` / `style` で色を指定したノードは、その指定が優先されている
- 縦長の図がウィンドウ高の 72% 以内に収まる（Mermaid Kit 使用時はヘッダーの Fit ボタンで全体表示できる）
- `Ctrl/Cmd + ホイール` で図を拡大・縮小でき、通常のホイールではページがスクロールする

<a name="customize"></a>
## カスタマイズ

| やりたいこと | 変更箇所 |
|---|---|
| Mermaid の配色を変える | `typora-mermaid.css` の「1. Palette」の `--tm-*` 変数 |
| 小さい Mermaid 図も上限まで拡大する（Mermaid Kit 非使用時のみ） | ノートの frontmatter に `cssclasses: mermaid-fill` を追加 |
| Mermaid 図の初期表示の高さ上限を変える（Mermaid Kit 非使用時のみ） | `typora-mermaid.css` の `--tm-fit-max-height`（既定 `72vh`） |
| 本文幅を変える | `typora-like.css` の `--file-line-width`（メディアクエリ内も含む） |
| フォントを変える | `typora-like.css` の `--font-text-theme` / `--font-monospace-theme` / `--h1-font` など |

Mermaid Kit 使用時は SVG が Kit の要素内に移るため、`mermaid-fill` と `--tm-fit-max-height` は効かず、図のサイズは Kit が制御する。

<a name="limitations"></a>
## 既知の制約

- Night テーマのコードブロックのシンタックスカラーは移植しておらず、Obsidian 既定の配色のまま。
- Mermaid の配色対象は flowchart / sequence / gantt / class / state / ER。pie / mindmap / timeline / journey などは未対応。
- Night の Mermaid 配色のうち、Typora の `night/mermaid.dark.css` に定義がない要素（シーケンス図のアクティベーションなど）は推測で補っている。CSS 内で `/* * */` を付けた変数が該当する。
- Live Preview ではコードブロックの枠線や見出しのマージンなど、一部の装飾が反映されない。

<a name="references"></a>
## 参考

- 元ノート: `~/Obsidian/main/30_Knowledge/Tools/Obsidian-Typoraスタイルのセットアップ.md`（手順・設計メモ・トラブルシューティングの詳細）
- Obsidian CSS variables: [Headings](https://docs.obsidian.md/Reference/CSS+variables/Editor/Headings) / [Table](https://docs.obsidian.md/Reference/CSS+variables/Editor/Table)
- [Mermaid Kit](https://community.obsidian.md/plugins/mermaid-kit)
- [Typora Night の Mermaid 配色](https://github.com/typora/typora-default-themes/blob/master/themes/night/mermaid.dark.css)
