---
status: in-progress
created: 2026-11-21
---

# 同じ作業ツリーの別セッションを知らせるフック 試験記録

関連: [design.md](design.md)、[plan.md](plan.md)

<a name="automated"></a>

## 1. 自動のテストと検査

Claude Code の sandbox の中で、worktree（`feat/shared-tree-git-hook`）で実行した。フックのテストは、書き込める cwd（`$TMPDIR`）から絶対パスで実行した。表は `/review` の修正の後の結果。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | Ran 83 tests、OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 出力なし、終了コード 0 |
| `actionlint` | 出力なし、終了コード 0 |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | pass=94 fail=0 |
| `bash claude/hooks/tests/test-validate-command.sh` | pass=29 fail=0 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | pass=66 fail=0 |
| `bash claude/hooks/tests/test-ask-shared-tree-git.sh` | pass=106 fail=0（`SKIP real ps`） |
| `bash claude/hooks/tests/test-gh-read-token.sh` | pass=24 fail=0 |
| `bash claude/hooks/tests/test-guard-additional-dirs.sh` | pass=17 fail=0 |
| `bash claude/hooks/tests/test-guard-playwright-mcp.sh` | pass=49 fail=0 |

人間が普段の端末（sandbox の外）で `bash claude/hooks/tests/test-ask-shared-tree-git.sh` を実行した結果は pass=94 fail=0 で、`SKIP` は出なかった（`/review` の修正の前のテスト）。実物の ps・kill を使う 3 件（生きているセッション、テストのシェル＝フックの祖先、終了したセッション）も通った。

テストが変更を検出できることは、フックの写しに変異を入れて確かめた。対象の照合・ツリーの比較・`TZ=UTC`・空白の正規化・祖先の除外・`sessionId` の除外・件数の上限・ps の失敗の扱い・`CLAUDE_PROJECT_DIR` への切り替え・stash のオプション・commit の `-a` の範囲を、それぞれ外すか広げると FAIL になる。`exit 0` を `exit 2` にすると全件 FAIL になる。

<a name="speed"></a>

## 2. 速さ

sandbox の中で、`/bin/kill`・`/bin/ps` を偽物に置き換えたフックを 20 回ずつ動かした（`/review` の修正の後）。

| 入力 | 1 回あたり |
| --- | --- |
| `git status`（対象外） | 18.5 ms |
| `git switch main`（対象。同じツリーの記録 60 件、うち生きているのは 1 件） | 720.5 ms |
| 引用符 3 万個の約 135 KB の対象外のコマンド（テストの 1 回） | 0.16 s（修正の前の jq の `gsub` では 8.3 s） |

- 対象のコマンドは、記録ごとに `tree_root` のサブシェルがかかり、同じツリーの記録には `kill` の起動もかかる。sandbox の中はプロセスの起動が遅めに出る。
- 2026-11-21 の `~/.claude/sessions` の記録は 23〜29 件で、最古は 11/16 だった。終了したセッションの記録が際限なく増える様子はない。

<a name="manual"></a>

## 3. 手動の確認（design 5.9）

worktree の `.claude/settings.local.json` にだけフックを登録し、worktree で起動したセッションで確かめた。確認はどれも拒否し、ブランチは動かしていない。`/review` の修正の前のフックで確かめた（修正は照合・正規化・文面の組み立てで、生死の確認と自分の除外は変えていない）。

| 項目 | CLI | VS Code（拡張機能のパネル） | desktop app |
| --- | --- | --- | --- |
| 1. 記録の `procStart` と `TZ=UTC LC_ALL=C /bin/ps -o lstart=` の一致 | 21 件すべて一致 | 3 件すべて一致 | 2 件すべて一致 |
| 2. 自分を別のセッションとして数えない | OK | OK | OK |
| 3. `/clear` の後・`--resume`（開き直し）の後も数えない | OK | OK | OK |
| 4. 別のセッションがあると確認が出て、文面に載る | OK | OK | OK |
| 5. auto mode で、allow の `Bash(git checkout *)` に当たる `git checkout -b` でも確認が出る | OK | OK | OK |

- 1 は、生きているすべてのセッション（起動元とディレクトリを問わず 26 件）を、普段の端末で比べた。空白の正規化の後で、すべて一致した。
- 2〜5 は、このとき worktree にいた別の CLI のセッション（実装を進めたセッション）を「別のセッション」として使い、文面にそのセッションだけが載り、確認したセッション自身が載らないことを見た。
- `--resume` の後の CLI のセッションで `git switch -c tmp/hook-check` を実行したときの文面:

  ```text
  同じ作業ツリー（~/dotfiles/.claude/worktrees/shared-tree-git-hook）で、別の Claude セッションが動いています: CLI（idle、11/21 16:00 開始）、VS Code（waiting、11/21 16:15 開始）、desktop app（waiting、11/21 16:19 開始）。このコマンドは、そのセッションのブランチや未コミットの変更に影響します。そのセッションが作業中なら、終わるのを待つか、別の作業ツリーで作業してください。
  ```

  同じ worktree の VS Code と desktop app のセッションが見え、確認したセッション自身（16:09 開始の CLI）は載っていない。`~/dotfiles` で動いていたセッション（CLI・desktop app）は載っておらず、`claude -w` の worktree が別の作業ツリーとして扱われている（5.9 の 4 の後半）。
- 2・3 で、どちらの仕組み（`sessionId` の一致か、祖先の pid か）で除外されたかは区別していない。

<a name="observations"></a>

## 4. 気づいたこと

- **再開しても `sessionId` は変わらなかった。** 実装を進めた CLI のセッションは、途中で再開されて pid が変わった（74325 → 64014）が、記録の `sessionId` は再開の前と同じだった。
- **閉じたセッションの記録は消えていた。** 確認に使った VS Code のセッションを閉じた後、その記録は `~/.claude/sessions` になかった。design の C3 は「終了したセッションの記録も残る」としているが、少なくともこの終わり方では消えた。残る記録がどの終わり方のものかは確かめていない。どちらでも、フックは生死を `kill -0` と `procStart` で確かめるので、判定は変わらない。
- **フックのファイルの構文エラーで Bash が止まった。** `settings.local.json` のフックは、このセッションにも読み込まれていた。修正の途中でフックに構文エラーがあったあいだ、bash が終了コード 2 で終わり、このセッションの Bash の呼び出しがブロックされた。登録に `|| true` を付けて防いだ（[5 章](#review)）。

<a name="review"></a>

## 5. レビュー（`/review`）

gstack の `/review` で、ブランチの差分をレビューした。専門のレビュアー（Testing・Maintainability・Security・Simplification）・Red Team・Claude の adversarial のサブエージェントと、QA の probe を使った。Codex の pass は、ユーザーの規則（Bash から実行しない）に従って飛ばした。

| 指摘 | 出どころ | 対応 |
| --- | --- | --- |
| `git stash 2>&1`（リダイレクトが続く素の stash）が対象にならない | QA の probe、adversarial | 直した（テストを先に書いて失敗を確かめた） |
| `git commit -m x .`・`-- :/` が対象外で、`git add .` とつり合わない | Red Team | 直した（design 5.2 にも追加） |
| 生きている pid で ps が失敗する場合、`CLAUDE_PROJECT_DIR` への切り替え、stash の `-u`、`commit --amend` のテストがない | Testing | テストを足した（変異で FAIL に転じることを確かめた） |
| 記録が多いときのテストが 1 秒単位で、遅い CI で落ちうる | 親、Testing | bash の `time` で 1 ミリ秒単位に測るようにした（上限 2 秒は同じ） |
| 引用符を除く jq の `gsub` が入力の 2 乗で遅く、すべての Bash の呼び出しで走る | adversarial、Red Team | `split` と `join` に替え、長いコマンドのテストを足した。同じ式の `ask-gh-pr-write.sh` は差分の外なので、別の作業で提案する |
| 件数の上限 5 が 3 箇所に数値のまま | Maintainability | 定数 `MAX_LISTED` にした |
| ps・kill の絶対パスの理由のコメントが、PATH の jq・grep と矛盾する | adversarial、Red Team | コメントを実態に合わせ、design 6 に grep も書いた |
| フックのファイルに構文エラーがあると、全セッションの Bash が止まる | 修正中に実際に発生 | 登録に `\|\| true` を付けた（design 5.1・5.6） |
| `is_target` の 1/2 の区別が使われていない、`format_reason` の列を手で分けている | Simplification（任意） | 適用した |
| worktree をまたいで共有される stash、引用符の中の語による誤検知、同じ会話の同時の再開、相手の `/add-dir`・`cd` の先 | adversarial、Red Team | 人間の判断で、design 6 に受け入れたリスクとして書いた。誤検知はテストに「known false positive」として書いた |
| 記録を調べる順序（終了したセッションの記録にも先に `cd` する） | adversarial、Red Team | 人間の判断で直さない（今は記録の大半が生きていて、順序を変えると対象のコマンドのたびの実行が増える） |
| 大文字小文字の違うパス、`procStart` の意味の変化、書きかけの記録 | adversarial | 直さない（入力と記録の cwd はどちらも getcwd 由来で綴りがそろう。後の 2 つは design 6 と 5.6 で受け入れ済み） |

QA の probe（成功の経路、`git stash 2>&1`、300 KB の入力で書き手が SIGPIPE を受けないこと、plan の検査コマンド）は、修正の後に取り直して合格した。修正の前に取った対照の probe（素の `git stash`）は取り直していないので、QA の判定は「inconclusive」のまま。同じ内容は回帰テストの `git stash` の行で確かめている。

<a name="plan-changes"></a>

## 6. plan からの変更

| plan の記述 | 実装 | 理由 |
| --- | --- | --- |
| Task 0 Step 3: design と plan を Read と Write で写す | `cp -p` で写し、design の関連リンク（未コミットの claude-clones の design）をコード表記にした | バイト単位で同じに写すため。リンク先がないと check-repo の markdown-links が失敗するため |
| `read_sessions` は TSV を出す | 列を US（`\037`）で区切る | bash の `read` はタブを空白として扱い、空の列で位置がずれるため |
| `is_target` は 0・1・2 以上を返す | `/review` で関数をやめ、`main` の中の grep 1 行にした | 呼び出し側は 0 以外をすべて同じに扱うため |
| `format_reason <root> <件数> <一覧の各行>` | `format_reason <root>` で、標準入力の `live_others` の出力を `read` で読む | here-string を使わず、件数は中で数えるため |
| Task 2 のテスト `home as ~` は `HOME="$T"` で動かす | `HOME` を `$T` の物理パスにした。`physical path` のテストは `HOME=/nonexistent-home` で動かした | ルートは物理パスで比べるので、`/tmp` → `/private/tmp` の symlink を含む `HOME` では `~` にならないため |
| Task 2 のテスト `a"b` は、リポジトリの中の記録の cwd を `a"b` にする | ツリーのルート自体を `a"b` にした | 文面に出るのはルートだけで、記録の cwd では引用符が出力に現れないため |
| Task 2 Step 5（普段の端末でのテスト）は Task 2 の中で頼む | Task 3 の人間の作業とまとめて頼んだ | 依頼を 1 回にまとめるため |
| Task 3 Step 8 は 1 つのコミット | 登録と文書のコミットと、試験記録のコミットに分けた | 手動の確認で別のセッションが worktree で動くあいだ、未コミットの変更を残さないため |
| 最後のレビューは superpowers の code-reviewer | gstack の `/review` だけにした | ユーザーの skill-routing の規則（同じ差分にレビューを重ねない）に従うため |
