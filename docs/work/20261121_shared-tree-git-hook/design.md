---
status: done
created: 2026-11-21
---

# 同じ作業ツリーの別セッションを、git 操作の前に知らせるフック

Claude が作業ツリーの状態を動かす git 操作（ブランチの切り替えなど）を実行する直前に、同じ作業ツリーで別の Claude セッションが動いていれば、人間の確認に回す。PreToolUse（Bash）のフックとして、すべてのリポジトリで働く。

関連: Claude 専用のクローンの design（draft。未コミットのため `docs/work/20261121_claude-clones/design.md` と書く）

<a name="intent"></a>

## 1. 目的と背景

- **起きた事故（2026-11-16）。** どちらも、`~/dotfiles` を共有する 2 つのセッションの間で起きた。
  - 別のセッションが途中で `git switch -c` した。自分のコミットが相手のブランチに入り、`cc-safe-push` で公開リポジトリに push された。
  - 別のセッションが編集している最中に、自分がブランチを切り替えた。sandbox が一部のファイルを書き換えられず、切り替えが途中で止まった。復旧のときに、相手の編集中のファイルを元に戻す一覧に入れてしまった（sandbox が拒否したので消えなかった）。
- **今の対策は、Claude が覚えていることに頼っている。** 自動メモリの「コミットと push の前に、別の Bash 呼び出しでブランチを確かめる」だけで、自分のコミットの前しか見ない。相手が切り替える側では何も起きない。
- **今も並行して使っている。** 2026-11-21 の `~/.claude/sessions` には、`~/dotfiles` に 4 件（CLI 2・VS Code 1・desktop app 1）、`~/Dev/ksc/sf_hpf_metadata` に 5 件、`~/Obsidian/main` に 6 件の記録がある（終了したセッションの記録も含みうる）。
- **クローン運用の判断とは独立している。** 判定を「同じ作業ツリーで、別のセッションが動いているか」にするので、今の運用（`~/dotfiles` の共有）でも、クローン運用（同じクローンで 2 つ起動した場合）でも同じに働く。クローン運用の主な目的は git の経路を断つこと（セキュリティ）で、このフックはその代わりにならない。

<a name="goals"></a>

## 2. 目標・非目標・反目標

**目標**

- **G1（確認）:** [5.2](#design-targets) の操作の前に、同じ作業ツリーで生きている別の Claude セッションがあれば、auto mode でも人間の確認に回す。
- **G2（判断の材料）:** 確認の文面から、どのセッションか（起動元・状態・開始時刻・場所）が分かり、承認するかを決められる。
- **G3（速さ）:** 対象外のコマンドに足す処理を、`ask-gh-pr-write.sh` と同じ程度（jq と grep を 1 回ずつ）にする。
- **G4（範囲）:** ユーザー設定のフックとして、すべてのリポジトリで働く。

**非目標**

- 人間が端末や IDE で行う git 操作と、Claude 以外のエージェント（Codex など）。
- `git -C <別の場所>` や `cd` の先のツリー。フックの入力の `cwd` のツリーだけを見る。
- エイリアス、スクリプト・mise タスク・make の中の git。
- セキュリティの境界。迂回できてよい。
- 単独の `git commit` の検査。間違ったブランチへのコミットは、その手前の切り替えで止める。
- herdr との連携。Codex も見たくなったら、後で herdr の `agent list` を足す。

**反目標**（技術的に動いても、こうなったら失敗）

- 並行作業をしていないときに確認が出る。
- 確認が頻繁に出て、人間が中身を読まずに承認するようになる。
- フックの不具合で Bash が止まる。
- 自分自身のセッションを「別のセッション」と数える。

<a name="constraints"></a>

## 3. 制約

- **C1（設定ファイル）:** Claude は `claude/settings.json` を編集できない（`blockWritesOutsideWorkingDirectories`）。登録の変更は Claude が用意し、人間が当てる。
- **C2（sandbox の外で動く）:** フックは sandbox の外で、モデルが決めたコマンドの文字列を入力に動く。コマンドの中身を実行・評価しない。git も実行しない（index を読む git は `core.fsmonitor` を起動しうる。[CLAUDE_CONFIG.md](../../../.claude/rules/CLAUDE_CONFIG.md#cc-safe-pr)）。
- **C3（セッションの記録は非公開の形式）:** `~/.claude/sessions/<pid>.json` は Claude Code が書く非公開の形式で、更新で変わりうる。2026-11-21 の時点の項目は次のとおり。
  - `pid`（数値）、`sessionId`、`cwd`、`status`（`busy`・`idle`・`waiting`）、`procStart`（`Sat Nov 21 04:58:51 2026` の形）、`entrypoint`（`cli`・`claude-vscode`・`claude-desktop`）、`kind`（`interactive`）、`startedAt`・`updatedAt`（ミリ秒の UNIX 時刻）など。
  - `procStart` は **UTC** で書かれている。cli・claude-vscode・claude-desktop の 6 件で、`startedAt` を UTC に直した時刻との差が 0〜4 秒だった（手元の時刻 JST とは 9 時間ずれる）。macOS の `ps -o lstart=` は手元のタイムゾーンで出すので、そのまま比べると一致しない。
  - `sessionId` は、フックの入力の `session_id`（会話のセッション ID）と同じ値だった（desktop app のこのセッションで確認）。
  - 終了したセッションの記録も残る。
  - 同じディレクトリに `<pid>.<hash>.key`（パーミッション 600）がある。読まない。
  - sandbox からも Edit・Write ツールからも、このディレクトリには書けない。
- **C4（プロセスの確認）:** sandbox の中では `ps` を実行できない（`operation not permitted`）。フックは sandbox の外なので使える。
- **C5（テストの実行環境）:** `HOME` を変えると、mise の shim の jq が失敗する。テストは記録の場所を `CLAUDE_CONFIG_DIR` で差し替える。ヒアストリングを使うテストは、書き込める cwd（`$TMPDIR`）から実行する。

<a name="approaches"></a>

## 4. 案と選んだもの

**確認を出す条件**（人間が選んだ）

| 案 | 内容 | 評価 |
| --- | --- | --- |
| 1. 操作で絞る | 作業ツリーの状態を動かす操作だけを対象にし、生きている別のセッションが 1 つでもあれば必ず確認する。単独の `commit` は対象外 | **採用。** 2 件の事故はどちらもブランチを動かす操作で起きた。対象の操作はタスクの始めにほぼ 1 回なので、確認がめったに出ず、出たときに読む価値がある |
| 2. 状態で絞る | `commit` も含めて対象を広くし、相手が `busy`・`waiting` のときだけ確認する | 不採用。作業を終えて「コミットしますか？」と聞いたまま止まっているセッションは `idle` になり、その未コミットの変更を見逃す。この状態は今の運用でよく起きる |
| 3. すべて確認 | 対象を広くし、生きている別のセッションがあれば必ず確認する | 不採用。並行作業のあいだはコミットのたびに確認が出て、形だけの承認になる |

**セッションの見つけ方**（私の判断）

| 案 | 評価 |
| --- | --- |
| `~/.claude/sessions` の記録 | **採用。** CLI・VS Code・desktop app のすべてが見える。代わりに非公開の形式に頼る（[6 章](#accepted-risks)） |
| herdr の `agent list` | 不採用。herdr の中で起動したエージェントしか見えない。desktop app と VS Code のセッションが見えない |
| 両方 | 不採用。今は Codex を見る必要がなく、手間だけが増える |

**フックが失敗したとき**（私の判断）: 何も出さずに通す（fail open）。`validate-command.sh` と `protect-main-branch.sh` は fail closed だが、このフックは作業の衝突を防ぐ警告で、セキュリティの守りではない。不具合で全部の Bash が止まるほうが困る。

<a name="design"></a>

## 5. 設計

<a name="design-files"></a>

### 5.1 置き場所と登録

- フック: `claude/hooks/ask-shared-tree-git.sh`（`ask-gh-pr-write.sh` と同じく、確認に回すフックなので `ask-` で始める）。
- 登録（人間が `claude/settings.json` に当てる）: `PreToolUse` の `ask-gh-pr-write.sh` の項目の次に足す。

  ```json
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "/bin/bash ~/.claude/hooks/ask-shared-tree-git.sh || true",
        "timeout": 10
      }
    ]
  }
  ```

  `onFailure` は付けない（fail open。[5.6](#design-failure)）。`|| true` は `/review` で足した（[5.6](#design-failure)）。
- 確認には `permissionDecision: "ask"` を使う。`ask-gh-pr-write.sh` は、`permissions.allow` の `Bash(gh *)` に当たるコマンドも、この仕組みで auto mode でも人間の確認に回している。`Bash(git checkout *)` も allow にあるが、同じに働く見込み（[5.9](#design-manual) で確かめる）。

<a name="design-targets"></a>

### 5.2 対象の操作

コマンドの文字列を、`ask-gh-pr-write.sh` と同じく jq で正規化してから（行継続と引用符を除く）、grep で照合する。`git` とサブコマンドの間のオプション（`-C <path>`・`-c <k=v>`・`--no-pager` など）を許す。コマンドの区切り（行頭・空白・`&&`・`||`・`;`・`|`・`(`・`` ` ``）の後に現れるものを対象にする。

この表を対象のすべてとする。表にない操作は対象外である。

| 区分 | 対象 |
| --- | --- |
| ブランチと HEAD を動かす | `git switch`、`git checkout`（すべての形）、`git rebase`、`git merge`、`git pull`、`git reset`、`git bisect` |
| 未コミットの変更を消す・動かす | `git stash`（`list`・`show` を除く）、`git restore`、`git clean` |
| 他人の変更を混ぜる | `git add` の `-A`・`--all`・`-u`・`--update`・`.`・`:/`、`git commit` の `-a`・`--all`（`-am` のようにまとめた形も）とパス指定の `.`・`:/`（`/review` で追加） |
| ブランチを動かす gh | `gh pr checkout` |

対象外の例: 単独の `git commit`、ファイルやディレクトリを指定した `git add`、`git rm`・`git mv`・`git apply`・`git am`、`fetch`・`status`・`log`・`diff`・`branch`・`cherry-pick`・`revert`・`worktree`・`push`。

- ディレクトリを指定した `git add <dir>` は、別のセッションの変更を混ぜうるが、対象にしない（私の判断）。ファイルとディレクトリを文字列では見分けられず、`git add` をすべて対象にすると、コミットのたびに確認が出て案 3 と同じになる（[6 章](#accepted-risks)）。

誤検知の影響は、別のセッションがあるときに確認が 1 回増えるだけ。対象の操作でなければ、セッションの記録を読まずに終える。

<a name="design-tree"></a>

### 5.3 同じ作業ツリーの判定

- 作業ツリーのルートは、ディレクトリから親へたどり、`.git`（ディレクトリかファイル）が最初に見つかったディレクトリとする。git は実行しない（C2）。見つからなければ、リポジトリの外なので何もしない。
- フックの側は、入力の `.cwd` から決める（なければ `CLAUDE_PROJECT_DIR`）。
- 別のセッションの側は、記録の `cwd` から決める。
- 両方のルートを物理パス（symlink を解決した形）で比べ、同じなら同じ作業ツリーとする。
- worktree（`.claude/worktrees/<name>`）と submodule は、自分の `.git` ファイルを持つので、別の作業ツリーになる。入れ子の場所にあっても数えない。

<a name="design-sessions"></a>

### 5.4 生きている別のセッション

- `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/*.json` だけを読む（`*.key` は読まない）。ディレクトリがなければ何もしない。
- 読めない記録と、`pid`（整数）・`cwd` のない記録は飛ばす。
- **生きているか:** `kill -0 <pid>` が成功し、かつ `TZ=UTC LC_ALL=C /bin/ps -o lstart= -p <pid>` の値が `procStart` と一致すれば、生きているとみなす。番号が別のプロセスに再利用された記録を除くため。
  - `procStart` は UTC なので（C3）、`ps` にも `TZ=UTC` を付ける。
  - 比べる前に、両方の連続する空白を 1 つにし、前後の空白を除く。1 桁の日（`Nov  1` と `Nov 1`）の違いをなくすため。
  - `procStart` がない記録と、`Sat Nov 21 04:58:51 2026` の形（曜日・月・日・時刻・年）に合わない記録は、`kill -0` だけで判断する（私の判断）。形式が変わったときに、黙るより確認が増えるほうを選ぶ。
- **自分を除く:** 記録の `pid` がフックの祖先のプロセス（`/bin/ps -o ppid=` で 1 までたどる）なら除く。記録の `sessionId` が入力の `session_id` と同じものも除く。
- 状態（`busy`・`idle`・`waiting`）と `kind` は問わない（案 1）。
- `ps` と `kill` は絶対パスか組み込みのものを使う。PATH の `ps` は使わない（sandbox から書ける場所が PATH に入っていても、sandbox の外で動かないようにする）。

<a name="design-message"></a>

### 5.5 確認の文面

`permissionDecisionReason` に、次の形で書く。

```text
同じ作業ツリー（~/dotfiles）で、別の Claude セッションが動いています: CLI（busy、11/21 14:02 開始）、VS Code（idle、11/21 09:40 開始）。このコマンドは、そのセッションのブランチや未コミットの変更に影響します。そのセッションが作業中なら、終わるのを待つか、別の作業ツリーで作業してください。
```

- 起動元は `cli` → CLI、`claude-vscode` → VS Code、`claude-desktop` → desktop app と書き、それ以外はそのまま書く。
- 開始時刻は `startedAt` を手元の時刻で書く。
- パスは `$HOME` を `~` に置き換える。
- セッションが多いときは 5 件まで書き、残りは「ほか N 件」とする。
- JSON は jq の `--arg` で組み立てる。記録の `cwd` に引用符などがあっても、出力の JSON が壊れないようにする。

<a name="design-failure"></a>

### 5.6 失敗したとき

- 本体をサブシェルで実行し、どんな失敗でも何も出さずに終了コード 0 で終える。終了コード 2（ブロック）は使わない。
- jq がない・壊れている、記録のディレクトリがない、`ps` が失敗する、などの場合も同じ。
- フックのファイル自体に構文エラーがあると、bash は本体を動かす前に終了コード 2 で終わり、Claude Code はそれをブロックとして扱う（実装中に、編集の途中のフックで、このセッションの Bash がすべて止まった）。登録のコマンドに `|| true` を付け、この場合も 0 で終える。

<a name="design-speed"></a>

### 5.7 速さ

- 対象外のコマンド: jq（コマンドの取り出しと正規化）と grep を 1 回ずつ。
- 対象のコマンド: すべての記録を読む jq を 1 回と、同じ作業ツリーの記録ごとに `ps`。
- 実装者は、対象外と対象の両方の所要時間を測って `test-report.md` に書く。

<a name="design-tests"></a>

### 5.8 テスト

`claude/hooks/tests/test-ask-shared-tree-git.sh` を作る。CI は `claude/hooks/tests/test-*.sh` をすべて実行するので、CI の変更は要らない。

- **照合:** 5.2 の各対象で確認が出る。対象外で何も出ない。引用符・行継続・`git -C x -c k=v switch` の形。`git stash list` と `git add <file>` と `git commit -m` は対象外。`git commit -am` と `gh pr checkout` は対象。
- **作業ツリー:** 記録がない、別の作業ツリーにある、ツリーの中の worktree にある場合は何も出ない。同じツリーのサブディレクトリにある場合は確認が出る。
- **生死と自分:** 終了したプロセスの記録、`procStart` が合わない記録、`sessionId` が自分と同じ記録、`pid` がフックの祖先の記録では何も出ない。
- **失敗:** 壊れた JSON の記録は飛ばす。PATH に jq がない、記録のディレクトリがない場合は、何も出さずに 0 で終わる。
- **文面:** 起動元の表記、状態、`~` のパスを含む。`cwd` に引用符を含む記録でも、出力が正しい JSON になる。
- **タイムゾーン:** 生きている記録の `procStart` は、実際の記録と同じく `TZ=UTC LC_ALL=C /bin/ps -o lstart=` で作る。フックは `TZ=Asia/Tokyo` を付けて実行する。CI の runner は UTC なので、こうしないとタイムゾーンの誤りを見逃す。1 桁の日の空白の違いも、正規化の関数のテストで確かめる。
- **sandbox の中:** `ps` を使う場合（生きている記録が要るもの）は、sandbox の中では SKIP と表示して飛ばす（C4）。CI（macOS の runner）と普段の端末では実行する。生きているプロセスには、テストが起動した `sleep` を使う。

<a name="design-manual"></a>

### 5.9 手動の確認（sandbox の外）

1. CLI・VS Code・desktop app の各セッションで、記録の `procStart` が `TZ=UTC LC_ALL=C /bin/ps -o lstart= -p <pid>` と（空白の正規化の後で）一致する。
2. CLI・VS Code・desktop app で、フックのプロセスが Claude のプロセスの子孫である（自分を除く処理が働く）。
3. `/clear` と `--resume` の後も、自分が別のセッションとして数えられない。
4. `~/dotfiles` で 2 つのセッションを起動し、片方の `git switch` で確認が出て、文面にもう片方が書かれる。`claude -w` の worktree の中では確認が出ない。
5. auto mode の CLI・VS Code・desktop app で、`Bash(git checkout *)` が allow にあっても確認が出る。

確かめた結果で、次のように進める（私の判断）。

- 1〜3 がどれかの起動元で失敗したら、直してから PR を出す。自分を誤って数えると、対象の操作のたびに確認が出るので、知っていて出すことはしない。
- 5 が失敗したら（allow が ask より勝つ場合）、deny（ブロックして理由を返す）には変えない。deny にすると人間が承認する手段がなくなり、G1 の性質が変わる。作業を止めて、人間と相談する。

<a name="design-docs"></a>

### 5.10 文書の更新

- `claude/README.md`: フックの表に 1 行足し、テストのコマンドの一覧に足す。
- `claude/SKILL_INVENTORY.md`: PreToolUse（Bash）の行に足す。
- `CLAUDE.md`: 「規約」のフックのテストの一覧に足す。
- マージの後: 自動メモリの shared-worktree-branch-switch に、このフックがあることを書く。

<a name="accepted-risks"></a>

## 6. 受け入れたリスク

- **記録の形式の変更。** Claude Code の更新で `~/.claude/sessions` の形式や場所が変わると、fail open なので、何も言わずに警告が止まる。気づく手段は、5.9 の 4 を更新の後に試すことだけ。
- **開いたままのセッション。** 作業していなくても、生きていれば確認が出る。案 1 の意図どおりで、不要なセッションを閉じてもらう。
- **非目標の経路。** 人間の git、Codex、`git -C` の先、エイリアスやスクリプトの中の git は見ない。
- **ディレクトリを指定した `git add`。** 別のセッションの変更を混ぜうるが、対象にしない（[5.2](#design-targets)）。
- **人が見ていないセッション。** `claude -p`・スケジュールタスク・バックグラウンドのセッションには承認する人がいないので、確認は拒否として扱われる見込み。同じ作業ツリーに別のセッションがあると、その中の対象の操作は止まる。2026-11-21 の時点で、人が見ていない Claude に git 操作を自動でさせる仕組みはない（人間に確認した）ので、特別な扱いは設けない。そうした仕組みを作るときに見直す。
- **PATH の jq と grep。** 既存のフックと同じく、jq と grep は PATH から使う。jq が先に動くので、grep だけを絶対パスにしても守りは増えない。
- 次の 4 つは `/review` で見つかり、人間が受け入れた（2026-11-21）。どれも、同じ作業ツリーに別のセッションがいるときだけの話である。
  - **worktree をまたいで共有される stash。** stash のスタック（`refs/stash`）はリポジトリ全体で共有されるが、このフックは作業ツリーのルートで比べる。そのため、worktree のセッションの `git stash pop`・`drop`・`clear` が、本体のツリーのセッションが積んだ stash を取り出したり消したりしても、確認は出ない。本体での `git clean -ffdx` が入れ子の worktree を消す場合も同じ。直すなら、stash の操作だけ、`.git` ファイルの `gitdir:` と `commondir` をファイルとして読み、共通の git ディレクトリで比べる（git は実行しない）。
  - **引用符と heredoc の中の語による誤検知。** 引用符を除いてから照合するので、コミットメッセージ・grep のパターン・heredoc の本文に対象の語があっても確認が出る。テストに「known false positive」として書いた。同じ理由で、空白を含む値を引用符で囲んだオプション（`git -c user.name="A B" switch main`）の後ろの操作は見逃す（Codex のレビューで見つかった。テストに「known miss」として書いた）。直すなら、引用符を 1 文字ずつ読んで語の切れ目を保つ処理に正規化を書き直す（`bash -c "git switch x"` は当たらなくなる）。
  - **同じ会話の同時の再開。** 記録の `sessionId` が自分と同じものを除くので、生きているセッションの会話を別の端末やアプリで同時に `--resume` すると、互いに見えない。
  - **相手のセッションの `/add-dir` と `cd` の先。** 相手の側は記録の `cwd`（起動した場所）だけで判断する。相手が `/add-dir` で足したディレクトリや `cd` の先で編集していても見えない。

<a name="rollout"></a>

## 7. 進め方

- 実装は `claude -w` の worktree で行う。今の `~/dotfiles` には、別の作業の未コミットの変更がある。
- 規模の見込み: フック 100〜150 行、テスト 150〜250 行。
- 戻し方: `claude/settings.json` の登録を外す。
- 次は writing-plans で `plan.md` を書く。

<a name="left-to-builder"></a>

## 8. 実装者に任せること

- 正規表現の具体的な形と、jq と bash の処理の分け方。
- 文面の細かい言い回しと、時刻の書式。
- テストの補助関数の作り方。
