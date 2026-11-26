---
status: in-progress
created: 2026-11-26
---

# VSCode の配色をターミナルとそろえる 実装計画

> [!NOTE]
> 実装する人へ: superpowers:executing-plans でタスクごとに進める。手順はチェックボックス（`- [ ]`）で追う。

**目的:** VSCode のテーマを GitHub Dark Dimmed に替え、PR #155 でターミナルに当てた配色（背景・追加は青・選択・カーソル・統合ターミナルの 16 色）にそろえる。

**方針:** `vscode/settings.json` の `workbench.colorCustomizations` を `"[GitHub Dark Dimmed]"` で囲み、テーマの色を上書きする。テーマの拡張は人間がターミナルで入れ、`vscode/extensions` を生成し直す。

**使うもの:** VSCode の色の設定（`workbench.colorCustomizations`）、GitHub 公式テーマの拡張 `GitHub.github-vscode-theme`（6.3.5、`@primer/primitives` 7.10.0）。

**仕様:** Linear の KAD-29 と、この文書の「[決めたこと](#decisions)」。

<a name="related"></a>

## 関連

- Linear: KAD-29
- 前の作業: PR #155（f4c8a12。Ghostty・git・Starship・Claude Code の配色）

<a name="decisions"></a>

## 決めたこと

テーマの選択はユーザーが決めた。それ以外は Claude の案で、Crit のレビューで直せる。色の比べ方は PR #155 と同じで、OKLab の色差（ΔE）、WCAG のコントラスト比、Machado 2009 の 1 型・2 型のシミュレーション（強さ 1.0）を使う。計算は背景 #181d1f に重ねた色で行った。

<a name="decision-theme"></a>

### テーマ（ユーザーが決定）

GitHub Dark Dimmed に替える。構文の色が Ghostty の 16 色と同じ primer の色から取られる（キーワードの #f47067 は ANSI の赤と同じ）ので、エディタとターミナルの色調がそろう。

- 同じ拡張の GitHub Dark Colorblind (Beta) は使わない。全体の色調が Dimmed ではなく Dark（背景 #0d1117）で、削除がオレンジになり、ANSI の緑と青が同じ色（#58a6ff）になるため。
- アイコンテーマ（catppuccin-perfect-dark）は色テーマとは別物なので、今のままにする。
- Catppuccin の拡張は消さない（戻すときは `workbench.colorTheme` を戻せば済む）。`json.schemaDownload.trustedDomains` の catppuccin の行もそのままにする。
- herdr は Ghostty の中で動き、VSCode のテーマとは関係しないので、範囲外にする。

<a name="decision-background"></a>

### 背景と明るさの順

テーマの明るさの順（サイドバー・パネルはエディタより暗い）を保つ。テーマの `canvas.default` #22272e と `canvas.inset` #1c2128 の OKLab の明るさの差（ΔL = -0.025）を #181d1f に当て、色相と彩度を保って #121719 にした。統合ターミナルの背景は、Ghostty と同じ #181d1f にする（エディタと同じく、中身の領域は #181d1f、枠は暗くする）。

| 色 | キー |
| --- | --- |
| #181d1f | `editor.background`・`tab.activeBackground`・`tab.hoverBackground`・`tab.activeBorder`・`tab.unfocusedActiveBorder`・`titleBar.activeBackground`・`activityBar.background`・`statusBar.background`・`statusBar.noFolderBackground`・`input.background`・`peekViewResult.background`・`terminal.background` |
| #121719 | `sideBar.background`・`sideBarSectionHeader.background`・`panel.background`・`editorGroupHeader.tabsBackground`・`tab.inactiveBackground`・`titleBar.inactiveBackground`・`textBlockQuote.background`・`editorOverviewRuler.border` |

テーマの `theme.js` で `canvas.default`・`canvas.inset`・`scale.black`・`scale.gray[9]` を使うキーがこれですべて。ポップアップ（`canvas.overlay` #2d333b）は明るいままでよい。

<a name="decision-foreground"></a>

### 文字色

- 統合ターミナルの文字色は Ghostty と同じ #9aa7b4 にする。
- VSCode のターミナルには太字の色の設定がない。既定の色の太字は #9aa7b4 のまま太くなる（Ghostty は #adbac7）。
- 当初は、エディタの文字色をテーマの #adbac7 のままにする案だった。Task 4 の確認で、ユーザーが「エディタの青系の文字色」と「マークダウン等で白く表示される文字色」を少し暗くするよう依頼したので、次の「[構文の色](#decision-syntax)」のとおり変えた。

<a name="decision-syntax"></a>

### 構文の色（Task 4 での依頼）

テーマの白（#adbac7）・2 つの青・オレンジ・キーワードの赤を、#155 で Ghostty の文字色を下げたのと同じ量（OKLab の明るさで -0.0606。色相と彩度は保つ）だけ暗くする。`editor.foreground` は `workbench.colorCustomizations` に、構文の色は `editor.tokenColorCustomizations` の `"[GitHub Dark Dimmed]"` の `textMateRules` に置く。

| テーマ | 新しい色 | 対象 |
| --- | --- | --- |
| #adbac7 | #9aa7b4 | `editor.foreground` と、`meta.block`・`variable.other`・`markup.italic` など 12 個のセレクタ |
| #6cb6ff | #59a3ea | `constant`・`entity`・`support`・`markup.heading` など 17 個のセレクタ |
| #96d0ff | #86b5dd | `string`・`string.regexp`・`string.other.link` など 9 個のセレクタ |
| #f69d50 | #e18a3b | `variable`・`entity.name`・Markdown の箇条書きの記号など 7 個のセレクタ |
| #f47067 | #e7645c | `keyword`・`storage`・`constant.character` など 6 個のセレクタ |

- セレクタは、拡張の `themes/dark-dimmed.json` の `tokenColors` を順に見て、最終的にその色になるものだけを取った。同じセレクタが後のルールで別の色に上書きされるもの（`entity.name.constant` の青、`string.regexp constant.character.escape` の青）は、元の色のセレクタに入れない。セレクタをテーマと同じ文字列にするので、どのトークンにどのルールが当たるかは変わらない。
- 太字（`markup.bold`）は、Ghostty の `bold-color` と同じく #adbac7 のまま、通常の文字より少し明るく残す。
- #cdd9e5 は改行コードの表示（赤い背景の上）にしか使われないので、変えない。
- 文字列などの水色は、同じ量だけ下げた #83bceb でも眩しいと指摘があったので、明るさを L 0.773 から 0.754 に下げ、彩度を 15% 下げた（0.090 → 0.077）#86b5dd にした。彩度を下げたのは、PR #155 で目立ち方を決めていたのが明るさより彩度だったため。3 つの見え方のうち最小の色差は、通常の文字 0.057、定数 0.067、関数（#dcbdfb）0.062（#83bceb では 0.038）、Markdown の太字（#adbac7）0.045（同 0.054）。
- 変数名などのオレンジ（#f69d50）は、赤と緑を見分けにくい見え方では明るい薄黄色に見え、眩しいと指摘があった。オレンジとキーワードの赤（#f47067）の違いは、その見え方では主に明るさ（L 0.772 と 0.702）なので、オレンジだけを同じ量だけ下げると最小の色差が 0.081 から 0.043 に縮む（彩度も下げると 0.007）。そのため、キーワードの赤も暗くする。最初は同じ量だけ下げた #df5d55（L 0.642）にしたが、暗くなりすぎたと指摘があったので、色相と彩度を保って L 0.665 に戻した #e7645c にした（背景とのコントラスト 5.16）。これより明るくするとオレンジに、ピンク寄りにするとコメントの灰色に近づく。オレンジとの最小の色差は 0.062、コメントとは 0.075。オレンジとタグの緑（#8ddb8c）の差は 0.068 から 0.115 に広がる。
- 通常の文字とコメント（#768390）の色差は 0.179 から 0.118 に縮む（コントラストは 6.94 と 4.39）。
- 選択範囲の上のコントラストは、通常の文字 3.63（元 4.51）、文字列 4.10、定数 3.33、変数名 3.35、キーワード 2.70。検索の一致（#805400）の上では、通常の文字 2.69、定数 2.46 に下がる。

<a name="decision-diff"></a>

### 差分・ガター・git の色

テーマの割り当て（行 = scale[5] の 15%、文字 = scale[3] の 30%、ガター = scale[4] の 40%）を保ち、緑の scale を青の scale に替える。削除（赤）と変更（黄）はテーマのまま。

| キー | テーマ | 新しい色 |
| --- | --- | --- |
| `diffEditor.insertedLineBackground` | #347d3926 | #316dca26 |
| `diffEditor.insertedTextBackground` | #57ab5a4d | #539bf54d |
| `editorGutter.addedBackground` | #46954a66 | #4184e466 |
| `gitDecoration.addedResourceForeground` | #57ab5a | #539bf5 |
| `gitDecoration.untrackedResourceForeground` | #57ab5a | #539bf5 |
| `chat.linesAddedForeground` | #54B054（VSCode の既定） | #539bf5 |

- 追加と削除の色差（ΔE、通常 / 1 型 / 2 型）: 文字の背景はテーマの緑 0.095 / 0.036 / 0.009 から、青 0.101 / 0.073 / 0.083 になる。行の背景は 0.049 / 0.022 / 0.002 から 0.053 / 0.041 / 0.043 になる。
- 追加の文字の背景の上の文字（#adbac7）のコントラストは 5.13（削除は 5.26）。
- ミニマップ（`minimapGutter.addedBackground`）と概要ルーラー（`editorOverviewRuler.addedForeground`）はガターの色から、差分のガターと概要ルーラー（`diffEditorGutter.*`・`diffEditorOverview.*`）は差分の背景から決まるので、上書きしない（VSCode のソースの `quickDiff.ts`・`editorColors.ts` で確認）。
- エクスプローラーの追加の色は、明るい青 #6cb6ff（git の CLI の追加の色）ではなく #539bf5 にする。#6cb6ff は通常のファイル名（#adbac7）との色差が 0.109 / 0.087 / 0.111 で、#539bf5（0.162 / 0.140 / 0.175）より見分けにくい。
- Claude Code 拡張のサイドバーの差分は、`--vscode-diffEditor-*` の色で表示される（拡張 2.1.332 の webview の CSS で確認）。成功の色にも `gitDecoration.addedResourceForeground` が使われる。
- `chat.linesAddedForeground` は、VSCode のチャットとエージェントのセッションの「+N −M」の表示の色。

<a name="decision-terminal"></a>

### 統合ターミナル

VSCode 版のテーマの 16 色は、Ghostty の同名テーマと 5 色違うので、その 5 色を Ghostty の値にする。残りの 11 色は同じ。

| キー | VSCode のテーマ | Ghostty（新しい色） |
| --- | --- | --- |
| `terminal.ansiBlack` | #22272e | #545d68 |
| `terminal.ansiBrightBlack` | #2d333b | #636e7b |
| `terminal.ansiCyan` | #76e3ea | #39c5cf |
| `terminal.ansiBrightCyan` | #b3f0ff | #56d4dd |
| `terminal.ansiBrightWhite` | #909dab | #cdd9e5 |

ほかに、`terminal.foreground` #9aa7b4、`terminal.selectionBackground` #1a4d74、`terminal.selectionForeground` #f4f7fa、`terminalCursor.foreground` #3fade5、`terminalCursor.background` #181d1f（ブロックカーソルの下の文字の色。Ghostty の `cursor-text = cell-background` に当たる）を置く。

- `terminal.ansiGreen` は Ghostty と同じ緑のままにする。git と Starship は PR #155 で緑を使わなくなっている。
- `terminal.integrated.minimumContrastRatio`（既定 4.5）は設定しない（今と同じ）。背景とのコントラストが 4.5 に届かない黒（2.55）・明るい黒（3.28）と、zsh-autosuggestions の候補の色（`fg=242`）は、VSCode が明るくして表示する。Ghostty より少し明るく見えるが、読みやすさを優先する。

<a name="decision-selection"></a>

### カーソル・選択・検索

今の `workbench.colorCustomizations` の 4 つの色は、テーマを限定せずに置かれている。これを `"[GitHub Dark Dimmed]"` の中に移し、次のように替える。

| キー | 今 | 新しい色 | 理由 |
| --- | --- | --- | --- |
| `editorCursor.foreground` | （テーマ #539bf5） | #3fade5 | Ghostty のカーソルと同じ |
| `editor.selectionBackground` | #5e8881 | #1a4d74 | Ghostty の選択と同じ。今の色の上では、新しいテーマのコメント（1.02）とキーワード（1.38）がほぼ読めない。#1a4d74 では 2.30 と 3.12、通常の文字は 4.51 |
| `editor.selectionHighlightBackground` | #3d4242d0 | #3d4242d0（そのまま） | 灰色で、選択と見分けられる（色差 0.094 以上） |
| `editor.findMatchBackground` | #5691b3 | #805400 | 今の色の上では構文がほぼ読めない（通常の文字 1.74）。青の選択と見分けるため黄にする（選択との色差 0.165 以上、通常の文字 3.33） |
| `editor.findMatchHighlightBackground` | #3b5768d0 | #ae7c1466 | 今の色は新しい選択の色と近い（色差 0.044〜0.050）。黄にすると 0.140 以上、通常の文字 4.84 |

<a name="non-goals"></a>

## 非目標

- 構文の色の色相（キーワードの赤とタグの緑など）。意味の対になる色ではないので変えない（明るさは「[構文の色](#decision-syntax)」で一部を下げた）。
- `editorBracketHighlight.*`（ブラケットの対の色。2 段目が緑、4 段目が赤）、`testing.iconPassed`、デバッグ・シンボルのアイコンの緑と赤。必要になったら後続で扱う。
- herdr の配色、フォント、Cursor（`setup.sh` で無効にしている）。

<a name="global-constraints"></a>

## 全体の制約

- 色の上書きは、すべて `workbench.colorCustomizations` と `editor.tokenColorCustomizations` の `"[GitHub Dark Dimmed]"` の中に置く。テーマを限定しない色を残さない。
- テーマ名は拡張の `package.json` の `label` と同じ `GitHub Dark Dimmed` にする（1 文字でも違うと、上書きが黙って効かない）。
- `vscode/extensions` は `mise run vscode:ext:list` で生成し、手で編集しない（`vscode/README.md`）。
- `vscode/` は sandbox から書けない（`.claude/settings.json` の denyWrite）。`settings.json` は Edit ツールで書き（確認が出る）、拡張の導入と `vscode/extensions` の生成は人間がターミナルで行う。
- `~/Library/Application Support/Code/User/settings.json` は `~/dotfiles/vscode/settings.json` へのリンクなので、`~/dotfiles` の作業ツリーの変更は、そのまま VSCode に効く。作業は worktree ではなく `~/dotfiles` の作業ブランチで行う（見え方をその場で確かめるため）。
- 既存のコメントとインデント（4 スペース）の書き方に合わせる。

<a name="review-focus"></a>

## レビューで見ること

1. テーマ名の綴りが違うと、上書きが一つも効かない。Task 3 の検査スクリプトでキー名を確かめ、Task 4 で背景が #181d1f になっていることを目で確かめる。
2. 拡張を入れる前に設定が効くと、VSCode は既定のテーマで表示する。Task 2（拡張の導入）を Task 3 より先に行う。新しい Mac では `setup.sh` が `vscode/extensions` から入れる。
3. Claude Code 拡張のサイドバーの差分が青になること。Task 4 で確かめる。
4. 統合ターミナルの暗い灰色（zsh-autosuggestions の候補、git の `brightblack`）が、入力した文字と見分けられること。Task 4 で確かめる。
5. `code --list-extensions` の結果に、この作業と関係のない拡張の差（入れた・消した拡張）が混ざること。Task 2 で差分を確かめ、混ざっていたら報告して扱いを決める。

---

<a name="task-1"></a>

### Task 1: 作業ブランチと plan

**ファイル:**

- 作成: `docs/work/20261126_KAD-29_vscode-colors/plan.md`（この文書）

- [ ] **Step 1:** `~/dotfiles` が main で、作業ツリーがきれいなことを確かめる（`git -C ~/dotfiles status --short --branch`）。
- [ ] **Step 2:** `git switch -c feat/KAD-29-vscode-colors`（`git commit` とは別の Bash 呼び出しにする）。
- [ ] **Step 3:** plan の `status` を `in-progress` にして、コミットする。

```bash
git add docs/work/20261126_KAD-29_vscode-colors/plan.md
git commit -m "docs: add plan for aligning VSCode colors with the terminal (KAD-29)"
```

<a name="task-2"></a>

### Task 2: テーマの拡張を入れる（人間がターミナルで行う）

**ファイル:**

- 変更: `vscode/extensions`（生成）

- [ ] **Step 1:** 人間に通常のターミナルで次を実行してもらう。

```bash
code --install-extension GitHub.github-vscode-theme
cd ~/dotfiles && mise run vscode:ext:list
```

- [ ] **Step 2:** `git -C ~/dotfiles diff vscode/extensions` を確かめる。期待: `+github.github-vscode-theme` の 1 行だけ。ほかの行が変わっていたら、報告して扱いを決める。

<a name="task-3"></a>

### Task 3: 配色の設定

**ファイル:**

- 変更: `vscode/settings.json:2-8`（`workbench.colorTheme` と `workbench.colorCustomizations`）
- 検査: `<scratchpad>/check_vscode_colors.py`（コミットしない）

- [ ] **Step 1: 検査スクリプトを書く**

`check_vscode_colors.py <settings.json のパス>` は、JSONC（`//` のコメントと末尾のカンマ）を読み、次を確かめる。

- `workbench.colorTheme == "GitHub Dark Dimmed"`
- `workbench.colorCustomizations` のキーが `"[GitHub Dark Dimmed]"` だけである（テーマを限定しない色がない）
- その中身が「[決めたこと](#decisions)」の表のキーと色に完全に一致する（41 個。過不足があれば、キーごとに表示して失敗する）
- Task 4 の依頼の後: `editor.foreground` を加えて 42 個。`editor.tokenColorCustomizations` のキーが `"[GitHub Dark Dimmed]"` だけで、`textMateRules` のセレクタと色が「[構文の色](#decision-syntax)」の 51 個に完全に一致する

- [ ] **Step 2:** `python3 -I <scratchpad>/check_vscode_colors.py ~/dotfiles/vscode/settings.json` を実行する。期待: FAIL（テーマが Catppuccin Mocha）。
- [ ] **Step 3:** `vscode/settings.json` の 2〜8 行を Edit ツールで書き換える。グループごと（背景・文字とカーソル・選択と検索・差分と git・統合ターミナル）に 1 行のコメントを付ける。
- [ ] **Step 4:** Step 2 のコマンドを実行する。期待: PASS。
- [ ] **Step 5:** リポジトリの検査を実行する。期待: すべて成功。

```bash
python3 -B .github/scripts/check-repo.py
python3 -B .github/scripts/test-check-repo.py
```

- [ ] **Step 6:** コミットする。

```bash
git add vscode/settings.json vscode/extensions
git commit -m "feat(vscode): switch to GitHub Dark Dimmed with the terminal's colors"
```

<a name="task-4"></a>

### Task 4: 見え方の確認（人間が VSCode で行う）

**ファイル:**

- 作成: `docs/work/20261126_KAD-29_vscode-colors/test-report.md`

- [ ] **Step 1:** 人間に VSCode で次を確かめてもらう。
  - エディタ: 背景が Ghostty と同じ暗さで、サイドバー・パネル・タブの列がそれより少し暗い。選択と検索の一致が見分けられ、選択の上の文字が読める。
  - 差分: ソース管理で変更のあるファイルを開き、追加が青、削除が赤。ガターの追加の印が青。
  - エクスプローラー: 追加・未追跡のファイル名が青。
  - 統合ターミナル: `git diff` と `git status` の色が Ghostty と同じに見える。zsh-autosuggestions の候補が入力した文字と見分けられる。
  - Claude Code 拡張のサイドバー: 差分の追加が青。
- [ ] **Step 2:** 色を直す指摘があれば、「[決めたこと](#decisions)」の表と検査スクリプトの期待値を一緒に直し、Task 3 の Step 3〜6 をやり直す。
- [ ] **Step 3:** 確かめた項目と結果、実行したコマンドを `test-report.md` に書き、コミットする。

<a name="task-5"></a>

### Task 5: レビューと PR

- [ ] **Step 1:** `/review` でブランチの差分をレビューし、指摘の採否を決める。
- [ ] **Step 2:** plan の `status` を `done` にする。
- [ ] **Step 3:** `/crit-review` でブランチの差分を開き、`approved: true` を受けてから、`cc-safe-push` と `cc-safe-pr create` で PR を作る。
- [ ] **Step 4:** `gh pr checks` で CI の結果を確かめる。

<a name="rollback"></a>

## ロールバック

PR のコミットを revert する。すぐ戻すだけなら、`vscode/settings.json` の `workbench.colorTheme` を `Catppuccin Mocha` に戻せば、`"[GitHub Dark Dimmed]"` の上書きは効かなくなる（Catppuccin の拡張は残している）。ただし、前の選択と検索の色（テーマを限定しない 4 つ）は戻らない。
