---
name: commit-staged-pr
description: Use when the user asks to commit only the currently staged git changes and open a pull request (e.g. 「ステージの変更をコミットして PR を作成して」「プッシュはこちらで対応します」).
---

# Commit Staged Changes and Open a PR

ステージ済みの変更だけをコミットし、`cc-safe-push` で push して PR を作る。`cc-safe-push` が拒否したり失敗したりしたときと、ユーザーが自分で push すると言っているときは、ユーザーの push を待つ。PR はリモートにブランチがないと作れないため、作業は push を挟んだ 2 フェーズになる。

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
   | ステージの変更がブランチの目的と無関係、または PR が merged / closed | `origin/<base>` が最新であることを確認してから `git switch --no-track -c <new> origin/<base>` | default branch |

   - `origin/<base>` が最新であることは、`gh api 'repos/{owner}/{repo}/git/ref/heads/<base>' --jq .object.sha` が `git rev-parse origin/<base>` と一致することで確認する（`git fetch` は sandbox の中で SSH が失敗する）。一致しなければ、ユーザーに `git fetch origin <base>` を依頼して止まる。
   - ブランチの目的は、ブランチ名と `git log origin/<base>..HEAD` のコミットから判断する。
   - `--no-track` は、`origin/<base>` を upstream にして引数なしの `git push` が base に向かうのを防ぐため。
   - 切り替え時に git がローカル変更の上書きを理由に拒否したら、stash せずに止めて確認する。
   - ブランチ名は既存ブランチの命名慣習に合わせる。

4. コミットする。
   - ステージに複数の論理変更が混在する場合は、分割案を示して確認する。ステージの組み替えは了承を得てから行う。
   - `git add`・`-a`・パス指定なしで `git commit` する。メッセージはリポジトリの慣習（なければ Conventional Commits）に従う。
   - フックで失敗したら、`--no-verify` で回避せず、内容を報告して止める。
   - `git log -1 --stat` と `git status --short` で、コミット内容と、ステージ外の変更が残っていることを確認する。

5. push する。ユーザーが自分で push すると言っているときは、実行せずに下の依頼に進む。対象リポジトリに移動してから、次のコマンドを引数なし・単独で実行する（ほかのコマンドと連結すると sandbox の中で失敗する）。

   ```sh
   /usr/local/libexec/claude-push/cc-safe-push
   ```

   | 結果 | 対応 |
   |---|---|
   | 成功（終了コード 0） | [フェーズ 2](#phase-2) に進む |
   | 拒否（2）または失敗（1） | 別の方法で push せず、理由を添えて下の依頼に進む |

   push を依頼するときは、次を伝えて止まり、push 完了の連絡を待つ。
   - ブランチ名と push コマンド（`git push -u origin <branch>`）。ブランチを切り替えた場合は、元のブランチ名と切り替えた理由
   - コミットと、コミットしなかった未ステージ・未追跡のファイル
   - PR の base・タイトル・本文の案（`.github/pull_request_template.md` などのテンプレートがあれば従う）

<a name="phase-2"></a>
## フェーズ 2: PR 作成（push の完了後）

1. リモートのブランチが `HEAD` と一致することを確認する。一致しなければ、その旨を伝えて止まる。
   - `cc-safe-push` で push した場合は、`PUSHED:` の行の SHA が `git rev-parse --short=12 HEAD` と一致すること
   - ユーザーが push した場合は、`gh api 'repos/{owner}/{repo}/git/ref/heads/<branch>' --jq .object.sha` が `git rev-parse HEAD` と一致すること（`git ls-remote` は sandbox の中で SSH が失敗する）
2. 同じ head の open な PR があれば、その URL を伝えて終了する。`gh` が失敗して確認できなければ、作成に進まずに確認する。
3. PR を作る。ユーザーが push した場合は、フェーズ 1 で示した案を使う。`cc-safe-push` で push した場合は、ここで案を作る（`.github/pull_request_template.md` などのテンプレートがあれば従う）。フェーズ 2 から始めた場合は、案を示して確認してから作る。カレントディレクトリに `.cc-pr-request.json` を書き、そのディレクトリで次のコマンドを単独で実行する（ほかのコマンドと連結すると sandbox の中で失敗する）。

   ```json
   { "version": 1, "op": "create", "head": "<branch>", "title": "<title>", "body": "<body>", "base": "<base>" }
   ```

   ```sh
   /usr/local/libexec/claude-push/cc-safe-pr create
   ```

   | 結果 | 対応 |
   |---|---|
   | 成功（終了コード 0） | `CREATED:` の行の URL を使って次に進む |
   | 拒否（2）で、許可リストにないリポジトリ | 本文を一時ファイルに書き、`gh pr create --base <base> --head <branch> --title "<title>" --body-file <file>` を実行する（人間の承認が必要） |
   | そのほかの拒否（2）、失敗（1） | 理由を伝えて止まる |
   | 要確認（3） | 再実行せず、`gh pr list --head <branch> --state all` で状態を確認して伝える |

4. `gh pr checks <number>` の結果を伝える。`cc-safe-push` で push した場合は、コミットと、コミットしなかった未ステージ・未追跡のファイルも伝える。ブランチを切り替えた場合は、元のブランチ名と切り替えた理由も伝える。

<a name="do-not"></a>
## やらないこと

| 操作 | 理由 |
|---|---|
| `git push`、`--head` なしの `gh pr create`、`gh pr create --dry-run` | gh は未 push のブランチを push しようとする（`--dry-run` でも push しうる） |
| `git add`、`git commit -a`、了承なしのステージ組み替え | ステージの内容がユーザーの意図 |
| `git stash`、`--no-verify`、フックの回避 | 未コミット変更の消失や安全装置の無効化につながる |
