# herdr チートシート

herdr の主なキーと、[config.toml](config.toml) で足した prefix なしのキー（直接キー）の早見表。既定のキーは herdr 0.9.5 の公式ドキュメント（[Keyboard](https://herdr.dev/tui/docs/keyboard/)・[Config reference](https://herdr.dev/tui/docs/config-reference/)）に基づく。構成は [Herdr cheatsheet](https://cheatsheets.namaraii.com/herdr.html) を参考にした。

- prefix は既定の `ctrl+b`。`prefix+c` は、`ctrl+b` を押してから `c` を押す。
- 直接キーの `option` は**左**の Option で押す（Ghostty の `macos-option-as-alt = left` のため）。config.toml では `alt` と書く。
- `cmd+option+h` は、macOS の設定で Ghostty の「Hide Others」を別のキーに付け替えないと herdr に届かない。手順は config.toml のコメントにある。
- 日本語入力のままでも prefix のキーが効く。prefix を押しているあいだだけ英字の配列に切り替わる（`experimental.switch_ascii_input_source_in_prefix`）。macOS の入力ソースに英字の配列（U.S. など）を入れておく必要がある。ATOK の英字モードは切り替え先にならない。
- 直接キーを変えたら、この表も合わせて直す。

<a name="toc"></a>

## 目次

- [基本操作](#basics)
- [ワークスペース操作](#workspaces)
- [エージェント操作](#agents)
- [タブ操作](#tabs)
- [ペイン操作](#panes)
- [コピーモード](#copy-mode)

<a name="basics"></a>

## 基本操作

<a name="launch"></a>

### 起動と再接続

| 操作 | コマンド・キー |
| --- | --- |
| 起動、または再接続 | `herdr` |
| detach（サーバーとエージェントは動き続ける） | `prefix+q` |
| サーバーを止める | `herdr server stop` |
| ヘルプ | `prefix+?` |

<a name="config"></a>

### 設定の確認と反映

| 操作 | コマンド・キー |
| --- | --- |
| 設定ファイルを検証する | `herdr config check` |
| 設定を読み込み直す | `prefix+shift+r` または `herdr server reload-config` |

<a name="workspaces"></a>

## ワークスペース操作

| 操作 | prefix のキー |
| --- | --- |
| 一覧を開いて切り替える | `prefix+w` |
| 移動先を選ぶ（Goto picker） | `prefix+g` |
| 新しいワークスペース | `prefix+shift+n` |
| 新しい worktree | `prefix+shift+g` |
| ワークスペースの名前を変える | `prefix+shift+w` |
| ワークスペースを閉じる（確認が出る） | `prefix+shift+d` |
| サイドバーの表示を切り替える | `prefix+b` |

<a name="agents"></a>

## エージェント操作

| 操作 | 直接キー | prefix のキー |
| --- | --- | --- |
| サイドバーの次のエージェントへ | `cmd+ctrl+j` | なし |
| サイドバーの前のエージェントへ | `cmd+ctrl+k` | なし |

<a name="tabs"></a>

## タブ操作

| 操作 | 直接キー | prefix のキー |
| --- | --- | --- |
| 新しいタブ | `cmd+option+t` | `prefix+c` |
| 次のタブへ | `cmd+option+]` | `prefix+n` |
| 前のタブへ | `cmd+option+[` | `prefix+p` |

| 操作 | prefix のキー |
| --- | --- |
| 1〜9 番目のタブへ | `prefix+1` 〜 `prefix+9` |
| タブの名前を変える | `prefix+shift+t` |
| タブを閉じる | `prefix+shift+x` |

新しいタブを作ると、名前を聞かれる（`ui.prompt_new_tab_name` の既定が `true`）。

<a name="panes"></a>

## ペイン操作

| 操作 | 直接キー | prefix のキー |
| --- | --- | --- |
| 左・下・上・右のペインへ移動 | `cmd+option+h` / `j` / `k` / `l` | `prefix+h` / `j` / `k` / `l` |
| 直前のペインに戻る | `cmd+option+o` | なし |
| 次のペインへ | `cmd+ctrl+]` | `prefix+tab` |
| 前のペインへ | `cmd+ctrl+[` | `prefix+shift+tab` |
| 右に分割 | `cmd+option+v` | `prefix+v` |
| 下に分割 | `cmd+option+minus` | `prefix+minus` |
| ペインを閉じる | `cmd+option+x` | `prefix+x` |
| ズーム（今のペインをタブ全体に広げる。もう一度押すと戻る） | `cmd+option+z` | `prefix+z` |

| 操作 | prefix のキー |
| --- | --- |
| 左・下・上・右のペインと入れ替え | `prefix+shift+h` / `j` / `k` / `l` |
| リサイズモード | `prefix+r` |
| ペインの名前を変える | `prefix+shift+p` |
| スクロールバックを編集 | `prefix+e` |
| 通知の対象を開く | `prefix+o` |
| 一時的なシェルをポップアップで開く（`exit` で閉じる） | `prefix+t` |

<a name="copy-mode"></a>

## コピーモード

`prefix+[` で、フォーカスしているペインのコピーモードに入る。

| 操作 | キー |
| --- | --- |
| 移動 | `h` / `j` / `k` / `l` |
| 単語単位で移動 | `w` / `b` / `e`（big-word は `W` / `B` / `E`） |
| 段落・ブロック単位で移動 | `{` / `}` |
| 画面単位で移動 | `PageUp` / `PageDown`、`ctrl+f`、`ctrl+u` / `ctrl+d` |
| 前方・後方に検索 | `/` / `?` |
| 同じ方向・逆方向にもう一度検索 | `n` / `N` |
| 選択を始める | `v` または `Space` |
| コピーする | `y` または `Enter` |
| コピーせずに終わる | `q` または `Esc` |

- 既定の prefix では、`ctrl+b` はページを戻さずに prefix として働く。
- 検索は、大文字を含まなければ大文字と小文字を区別しない。
- `Esc` は、選択や検索があれば先にそれを消し、もう一度押すと終わる。
