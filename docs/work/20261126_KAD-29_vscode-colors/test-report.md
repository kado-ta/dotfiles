---
status: in-progress
created: 2026-11-27
---

# VSCode の配色をターミナルとそろえる 試験記録

<a name="related"></a>

## 関連

- Linear: KAD-29
- 計画: [plan.md](plan.md)

<a name="automated"></a>

## 自動の検査

ブランチ `feat/KAD-29-vscode-colors` の d2d8837 で、2026-11-27 に実行した。

| 検査 | 結果 |
| --- | --- |
| 配色の検査スクリプト（下記） | PASS（42 個の色と、51 個の構文のセレクタが一致） |
| `python3 -B .github/scripts/check-repo.py` | 16 項目すべて PASS |
| `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了コード 0 |
| `actionlint` | 終了コード 0 |
| `zizmor --offline .` | 終了コード 0（No findings） |

配色の検査スクリプトは、Claude のセッションの一時ディレクトリに置き、コミットしていない。`vscode/settings.json` を JSONC として読み、次を確かめる。

- `workbench.colorTheme` が `GitHub Dark Dimmed` である。
- `workbench.colorCustomizations` と `editor.tokenColorCustomizations` のキーが `"[GitHub Dark Dimmed]"` だけである（テーマを限定しない色がない）。
- 色とセレクタが plan の「[決めたこと](plan.md#decisions)」と過不足なく一致する。

変更前の `settings.json` で FAIL（43 件）になることを確かめてから書き換えた。期待値を変えるたびにも、先に FAIL を確かめた。

<a name="visual"></a>

## 見え方の確認（ユーザーが VSCode で実施）

次の項目を示して確かめてもらった。項目ごとの結果は聞いておらず、最後に全体として「OK」の回答を受けた（2026-11-27、d2d8837）。

- エディタ: 背景の暗さ、サイドバー・パネル・タブの列の暗さ、選択と検索の一致の見分け
- 差分: 追加が青、削除が赤、ガターの追加の印が青
- エクスプローラー: 追加・未追跡のファイル名が青
- 統合ターミナル: `git diff`・`git status` の色が Ghostty と同じに見えるか、zsh-autosuggestions の候補が見分けられるか
- Claude Code 拡張のサイドバー: 差分の追加が青

確認の途中で受けた指摘と、その対応は次のとおり（詳細は plan の「[構文の色](plan.md#decision-syntax)」）。

| 指摘 | 対応 | コミット |
| --- | --- | --- |
| エディタの青系の文字色を少し暗く／Markdown などで白く表示される文字色も少し暗く | 通常の文字・2 つの青を、Ghostty の文字色と同じ量だけ暗くした | 92b105c |
| 明るい青というか水色が少し眩しい | 文字列などの水色の明るさと彩度を下げた | 0205291 |
| 明るい薄黄色も眩しい | 変数名などのオレンジを暗くし、見分けるためにキーワードの赤も暗くした | 5ece496 |
| 赤が暗くなりすぎている | キーワードの赤を少し明るく戻した | d2d8837 |

<a name="not-verified"></a>

## 確かめていないこと

- 新しい Mac で `vscode/setup.sh` が `vscode/extensions` からテーマの拡張を入れること（実行していない。拡張はこの Mac でユーザーが `code --install-extension` で入れた）。
- Markdown のプレビュー（markdown-preview-github-styles の表示）は変えておらず、確かめていない。
- 括弧の対の色（`editorBracketHighlight.*`）、テストとデバッグのアイコンの緑と赤は、plan の非目標なので確かめていない。
