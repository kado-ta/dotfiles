---
name: commit-staged-pr
description: Use when the user asks to commit only the currently staged git changes and open a pull request (e.g. 「ステージの変更をコミットして PR を作成して」「プッシュはこちらで対応します」).
---

# Commit Staged Changes and Open a PR

ステージ済みの変更だけをコミットし、`cc-safe-push` で push して PR を作る。push の前に、確認スキルの提案と、Crit での人間のレビューを行う。`cc-safe-push` が拒否したり失敗したりしたときと、ユーザーが自分で push すると言っているときは、ユーザーの push を待つ。PR はリモートにブランチがないと作れないため、作業は push を挟んだ 2 フェーズになる。

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

5. push の前に確認する。ユーザーが自分で push すると言っているときも、push を依頼する前に行う。
   - **確認スキル**: 手順 4 でコミットした差分が下の表に当てはまるときは、当てはまるスキルから下の条件で使えないものを除き、表の上から順に最大 2 つ、理由を 1 行ずつ添えて提案し、実行するかをユーザーに選んでもらう。当てはまらないときと、不要と言われたときは、何も実行せずに Crit に進む。提案と実行は 1 回の作業で 1 回だけにする。

     | 差分の内容 | 提案するスキル |
     |---|---|
     | 認証・権限・シークレットの扱い・インフラ・依存の追加 | `/cso --diff` |
     | 画面（コンポーネント・CSS・テンプレート） | `/qa`、`/design-review` |
     | 性能に効く変更（クエリ・バンドル・画像） | `/benchmark --diff` |

     <!--
       TODO: 下記は、別タスクとして対応し、解決する必要がある。
       Sandbox の中で確認スキルが動かない:
       - /qa・/design-review・/benchmark のブラウザ（gstack の browse）は localhost で待ち受けますが、
         sandbox では許可されておらず、除外コマンドにも入っていません。Aside も入っていません。
       - /cso の保存先 ~/.gstack/security/cso は、書き込みの許可（~/.gstack/projects だけ）の外にあります。
       - グローバル CLAUDE.md で使うと決めている /qa と /browse にも同じ影響があります。
     -->

     - `/qa`・`/design-review`・`/benchmark` は動いているアプリを使う。sandbox の中ではサーバーを起動できないので、ユーザーに起動してもらう必要があると添えて提案する。`/benchmark --diff` は、変更前の baseline がないと絶対値しか出せず、回帰を検出できないことも添える。
     - `/qa` と `/design-review` は、作業ツリーがクリーンでないと止まり、全部コミットするか stash するかを聞いてくる。提案の前と実行の直前に `git status --porcelain` を確かめ、空でなければ提案も実行もせず、未コミットの変更が残っているので使えないと伝える。
     - スキルが修正をコミットしたら、そのコミットも今回のコミットとして扱う。
     - スキルがコミットせずに作業ツリーに残した変更があれば、内容を伝え、コミットするかを確認する。コミットするときは、ステージはユーザーに任せ、ステージし直したと連絡を受けてから手順 4 でコミットする。
     - スキルが最後まで動かなかったとき（blocked・not assessed など）と、直さずに残した指摘があるときは、Crit に進まずに伝え、どうするかを確認する。`/cso --diff` は未ステージ・未追跡のファイルも検査するので、そのファイルへの指摘は PR に含まれないことも添える。進めると言われたら Crit に進む。直すときは、直した後のステージはユーザーに任せ、ステージし直したと連絡を受けてから手順 4 でコミットし、Crit に進む。
   - **Crit**: `/crit-review` の手順で、ブランチの差分（依頼ファイル `{}`）を開く。`approved: true` が返るまで手順 6 に進まない。承認されたら `git rev-parse HEAD` を控える。
     - Crit の差分は default branch との merge-base から作業ツリーまでなので、PR に含めない変更も入る。未ステージ・未追跡のファイルがあるときと、PR の base が default branch でないときは、開く前にそのことを伝える。
     - コメントに沿って修正したら、ステージはユーザーに任せ、ステージし直したと連絡を受けてから手順 4 でコミットし、Crit を開き直す。

6. push する。ユーザーが自分で push すると言っているときは、実行せずに下の依頼に進む。対象リポジトリに移動してから、次のコマンドを引数なし・単独で実行する（ほかのコマンドと連結すると sandbox の中で失敗する）。

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
3. PR を作る。Crit で承認したときに控えた HEAD が `git rev-parse HEAD` と一致しないとき（フェーズ 2 から始めた場合を含む）は、先にフェーズ 1 の手順 5 の Crit を開き、`approved: true` を得る（確認スキルは提案しない）。Crit のコメントで修正したら、ステージはユーザーに任せ、ステージし直したと連絡を受けてから[フェーズ 1](#phase-1) の手順 4 でコミットし、Crit を開き直してから手順 6 に進む。ユーザーが push した場合は、フェーズ 1 で示した案を使う。`cc-safe-push` で push した場合は、ここで案を作る（`.github/pull_request_template.md` などのテンプレートがあれば従う）。フェーズ 2 から始めた場合は、案を示して確認してから作る。カレントディレクトリに `.cc-pr-request.json` を書き、そのディレクトリで次のコマンドを単独で実行する（ほかのコマンドと連結すると sandbox の中で失敗する）。

   ```json
   { "version": 1, "op": "create", "head": "<branch>", "title": "<title>", "body": "<body>", "base": "<base>" }
   ```

   ```sh
   /usr/local/libexec/claude-push/cc-safe-pr create
   ```

   | 結果 | 対応 |
   |---|---|
   | 成功（終了コード 0） | `CREATED:` の行の URL を使って次に進む |
   | 拒否（2）で、許可リストにないリポジトリ | 本文と `gh pr create --base <base> --head <branch> --title "<title>" --body-file <file>` を示して止まり、人間に自分の端末で実行してもらう（sandbox 内の `gh` は書き込めない） |
   | そのほかの拒否（2）、失敗（1） | 理由を伝えて止まる |
   | 要確認（3） | 再実行せず、`gh pr list --head <branch> --state all` で状態を確認して伝える |

4. `gh pr checks <number>` の結果を伝える。`cc-safe-push` で push した場合は、コミットと、コミットしなかった未ステージ・未追跡のファイルも伝える。ブランチを切り替えた場合は、元のブランチ名と切り替えた理由も伝える。

<a name="do-not"></a>
## やらないこと

| 操作 | 理由 |
|---|---|
| `git push`、`--head` なしの `gh pr create`、`gh pr create --dry-run` | gh は未 push のブランチを push しようとする（`--dry-run` でも push しうる） |
| `git add`、`git commit -a`、了承なしのステージ組み替え（手順 5 で承認したスキルが、自分の修正をコミットするのは除く） | ステージの内容がユーザーの意図 |
| `git stash`、`--no-verify`、フックの回避 | 未コミット変更の消失や安全装置の無効化につながる |
| `/document-release` など、自前で `git push` や `gh pr edit` を実行するスキル | `cc-safe-push`・`cc-safe-pr` を通らない push と PR 編集になる（deny ルールや 403 で失敗する） |
