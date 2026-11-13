---
name: crit-review
description: Use when the user invokes /crit-review or asks to review a file or the branch diff with Crit from Claude Code (e.g. 「crit でレビューしたい」「/crit-review docs/work/x/plan.md」). Runs Crit through the root-owned cc-crit wrapper, because crit itself cannot write ~/.crit or listen on localhost inside the sandbox.
---

# Crit でレビューする（cc-crit）

`crit` を直接実行しない。sandbox の中の crit は `~/.crit` に書けず、localhost でも待ち受けられないので、必ず失敗する。Crit の対話レビューは、root 所有のラッパー `cc-crit` で開く。ラッパーは Crit 専用の Seatbelt profile と専用の HOME の中で crit を動かし、ブラウザも開く。

Plan Mode の plan のレビューは、Crit プラグインの hook が ExitPlanMode のときに行う。そのときはこのスキルを使わない。

<a name="request"></a>

## 1. 依頼ファイルを書く

作業ディレクトリ（git リポジトリの中）に、Write ツールで `.cc-crit-request.json` を書く。依頼ファイルは実行のたびに消えるので、毎回書く。

- ファイルをレビューする: `{"files": ["docs/work/x/plan.md"]}`。リポジトリの中の通常ファイルを 20 件まで。
- ブランチの差分をレビューする: `{}`

<a name="review"></a>

## 2. レビューを開いて待つ

次のコマンドを、ほかのコマンドと連結せず単独で、`run_in_background: true` と `timeout: 86400000` を付けて実行する。前後に `cd`、`;`、`&&`、`echo` などを付けると sandbox の中で動いて失敗する。

```sh
/usr/local/libexec/claude-crit/cc-crit review
```

ラッパーがブラウザを開く。出力にある `http://localhost:<port>` を伝え、「コメントを付けて Finish Review を押してください」とだけ言う。完了の通知が来るまで先に進まない。レビューのファイルを先に読まない。

<a name="read"></a>

## 3. 結果を読む

出力に従う。`approved: true` ならレビューは承認された。コメントが返ったら、指摘に沿ってファイルを直す。出力にある `session <id>`（12 桁の 16 進）を控える。`~/.cc-crit` の中は読めない（読ませない設定になっている）ので、レビューの内容は出力だけから読む。コメントが残ったときの出力の案内は、cc-crit が crit の設定で差し替えたもので、4・5 の手順を指している。

<a name="reply"></a>

## 4. 返信する

`.cc-crit-request.json` に返信を書き、次のコマンドを単独で実行する。

```json
{"session": "<id>", "replies": [{"reply_to": "c_73f150", "body": "何をしたか"}]}
```

```sh
/usr/local/libexec/claude-crit/cc-crit reply
```

- 受け付けるのは、既存のコメントへの返信（`reply_to` と `body`）だけ。`reply_to` は、行・ファイルへのコメントなら `c_`、レビュー全体へのコメントなら `r_` で始まる ID。新しいコメントの追加、解決済みへの変更、author の指定はできない。解決するかどうかはレビュアーが決める。
- 返信の内容はチャットに書かない。レビュアーは Crit で読む。
- `crit comment` を直接実行しない。

<a name="next-round"></a>

## 5. 次のラウンド

1 の依頼ファイルを同じ内容で書き直し、2 をもう一度実行する。同じ daemon につながり、次の Finish Review まで待つ。コメントなしで Finish されたら終わり。

<a name="failures"></a>

## 失敗したとき

- 終了コード 2（`DENIED`）: 理由を読んで伝える。依頼ファイルの形式、リポジトリの外のファイル、範囲内のポートを crit 以外が使っている、`denyRead` を `cc-crit.sb` が覆っていない、`cc-crit` がインストールされていない、などがある。再実行するときは依頼ファイルを書き直す。
- 終了コード 1（`FAILED`）で `run cc-crit alone` と出た: 連結や前置きがあって sandbox の中で動いた。単独で実行し直す。
- `cc-crit` がない: インストールは dotfiles の `claude/README.md` の cc-crit の節にあり、人間が `sudo` で行う。
