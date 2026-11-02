---
name: commit-staged-pr
description: Use when the user asks to commit only the currently staged git changes and open a pull request while they push the branch themselves (e.g. 「ステージの変更をコミットして PR を作成して。プッシュはこちらで対応します」).
---

# Commit Staged Changes and Open a PR

ステージ済みの変更だけをコミットし、ユーザーが push した後に PR を作る。PR はリモートにブランチがないと作れないため、作業は push を挟んだ 2 フェーズになる。

起動時にステージ済みの変更がなく、現在のブランチが push 済みで open な PR がない場合は、[フェーズ 2](#phase-2) から始める。どちらにも当てはまらない場合は、状況を伝えて止まる。

<a name="phase-1"></a>
## フェーズ 1: ブランチ作成とコミット

1. 状態を把握する。

   ```sh
   git status --short --branch
   git diff --cached --stat && git diff --cached
   git log --oneline -10
   git branch -a --sort=-committerdate | head -20
   gh repo view --json defaultBranchRef -q .defaultBranchRef.name
   ```

2. ステージにシークレット（`.env`、認証情報、`*.tfstate` など）が含まれていたら、コミットせずに止めて確認する。
3. ブランチを決める。現在のブランチの PR は `gh pr list --head <branch> --state all --json number,state,url` で調べる。`gh` が失敗して default branch や PR の有無が分からないときは、推測で進めずに確認する。表は上から順に判定し、最初に当てはまる行に従う。

   | 現在のブランチ | 対応 | PR の base |
   |---|---|---|
   | detached HEAD | 確認する | — |
   | default branch / main / master / staging | `git switch -c <new>` | 現在のブランチ |
   | open な PR がある | 既存 PR に追加するか、新ブランチにするかを確認する | — |
   | PR がなく、ステージの変更がブランチの目的に沿う | そのまま使う | default branch |
   | ステージの変更がブランチの目的と無関係、または PR が merged / closed | `git fetch origin <base>` → `git switch --no-track -c <new> origin/<base>` | default branch |

   - ブランチの目的は、ブランチ名と `git log origin/<base>..HEAD` のコミットから判断する。
   - `--no-track` は、`origin/<base>` を upstream にして引数なしの `git push` が base に向かうのを防ぐため。
   - 切り替え時に git がローカル変更の上書きを理由に拒否したら、stash せずに止めて確認する。
   - ブランチ名は既存ブランチの命名慣習に合わせる。

4. コミットする。
   - ステージに複数の論理変更が混在する場合は、分割案を示して確認する。ステージの組み替えは了承を得てから行う。
   - `git add`・`-a`・パス指定なしで `git commit` する。メッセージはリポジトリの慣習（なければ Conventional Commits）に従う。
   - フックで失敗したら、`--no-verify` で回避せず、内容を報告して止める。
   - `git log -1 --stat` と `git status --short` で、コミット内容と、ステージ外の変更が残っていることを確認する。

5. push を依頼して止まる。次を伝え、push 完了の連絡を待つ。
   - ブランチ名と push コマンド（`git push -u origin <branch>`）。ブランチを切り替えた場合は、元のブランチ名と切り替えた理由
   - コミットと、コミットしなかった未ステージ・未追跡のファイル
   - PR の base・タイトル・本文の案（`.github/pull_request_template.md` などのテンプレートがあれば従う）

<a name="phase-2"></a>
## フェーズ 2: PR 作成（push 完了の連絡後）

1. `git ls-remote --heads origin <branch>` の SHA が `git rev-parse HEAD` と一致することを確認する。一致しなければ、その旨を伝えて止まる。
2. 同じ head の open な PR があれば、その URL を伝えて終了する。`gh` が失敗して確認できなければ、作成に進まずに確認する。
3. PR を作る。base・タイトル・本文はフェーズ 1 で示した案を使う。フェーズ 2 から始めた場合は、案を示して確認してから作る。本文は一時ファイルに書く。

   ```sh
   gh pr create --base <base> --head <branch> --title "<title>" --body-file <file>
   ```

4. `gh pr checks <number>` の結果を伝える。

<a name="do-not"></a>
## やらないこと

| 操作 | 理由 |
|---|---|
| `git push`、`--head` なしの `gh pr create`、`gh pr create --dry-run` | gh は未 push のブランチを push しようとする（`--dry-run` でも push しうる） |
| `git add`、`git commit -a`、了承なしのステージ組み替え | ステージの内容がユーザーの意図 |
| `git stash`、`--no-verify`、フックの回避 | 未コミット変更の消失や安全装置の無効化につながる |
