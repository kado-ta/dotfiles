---
status: in-progress
created: 2026-11-24
---

# Vault のノートを点検するフック 試験記録

関連: [plan.md](plan.md)

<a name="summary"></a>

## 概要

`claude/hooks/check-vault-note.sh` と、その Python の部分・Seatbelt の profile・試験の確認の記録。Claude Code の sandbox の中では `sandbox-exec` を入れ子にできない（2026-11-24 に `sandbox_apply: Operation not permitted`、rc=71 を確かめた）。そのため、Seatbelt の中の確認と本物の Vault での確認は、ユーザーが通常のターミナルで実行した。

<a name="tests"></a>

## 試験の結果

Codex のレビューへの対応（`5af70d3` の次のコミット）の時点の結果。

| 実行した場所 | コマンド | 結果 |
| --- | --- | --- |
| Claude Code の sandbox | `bash claude/hooks/tests/test-check-vault-note.sh` | pass=23 fail=0 skip=1（Seatbelt の中の確認はスキップ） |
| ユーザーのターミナル | `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh` | pass=40 fail=0 skip=0（共有フォルダの確認のパスの書き方と名前を、`check-repo.py` の誤検知を避けるために変える前の版） |
| Claude Code の sandbox | 既存のフックの試験 7 本 | すべて fail=0 |
| Claude Code の sandbox | `python3 -B .github/scripts/check-repo.py`、`python3 -B .github/scripts/test-check-repo.py`、shellcheck、`actionlint` | すべて通過 |

<a name="real-vault"></a>

## 本物の Vault での確認

ユーザーのターミナルで、`~/Obsidian/main` の `01_Inbox`・`10_Projects`・`30_Knowledge`・`50_Journal` の先頭 80 件のノート（`/usr/bin/find` の順）に対してフックを動かした。誤りになったのは次の 4 件（exit 2）で、traceback などの異常な出力はなかった。

- `01_Inbox/Captures/SF-IdPとSAML-Relayのログイン連携設定.md`
- `01_Inbox/AI_Drafts/salesforce-api-integration-user.md`
- `01_Inbox/AI_Drafts/モノリス・マイクロサービスの比較とアーキテクチャ選定戦略.md`
- `01_Inbox/AI_Drafts/Colima+DockerCLIセットアップ.md`

同じ 80 件を、Claude Code の sandbox の中で点検スクリプトを直接実行して確かめると、誤りになるノートは同じ 4 件だった。`5af70d3` と、Codex のレビューへの対応（読み込みを既定で拒否にした profile）の後にも同じ確認をして、どちらも同じ 4 件だった。対応の後の確認では、出力が見出しと `- ` で始まる行になっていることも、1 件のノートで見た。

<a name="mutations"></a>

## 壊した写しでの確認

試験が実装の壊れ方を捉えるかを、一時フォルダに写して壊したフックで確かめた（写しはコミットしていない）。

- 最初の版（SHA-256 の照合）: 依頼の方式（`shasum` で照合した後にファイルを読み直して実行）では、入れ替えの試験で、書き換えた版が 40 回中 5 回実行された。`-I` を外す・stderr への振り替えを外す・接頭辞の `/` を外す・入力を読み切らない・照合を外す、のどれも試験が失敗した。
- 写しと Seatbelt の版（sandbox の中で確かめられる部分）: 点検スクリプトがあるかの判定を外す・写しとの比較を外す・接頭辞の `/` を外す・入力を読み切らない、のどれも試験が失敗した。`-I` を外す変更と、末尾の `/` を取り除く処理を外す変更は、2 回目のレビューの Testing の担当が、捉えられないことを見つけた。そのため、`PYTHONPATH` と末尾の `/` の試験を足した。

<a name="findings"></a>

## 途中で分かったこと

- bash 3.2 の here document は一時ファイルに書く。書けない場所では、変数が空のまま 1 で終わり、点検が黙って止まった（sandbox の中で Vault をカレントディレクトリにしたときに再現）。単一引用符の文字列にして直し、書けない一時ディレクトリの試験を足した。
- Seatbelt の profile で `/dev/urandom` の読み込みを止めると、Python 3.9 が起動しない（`_Py_HashRandomization_Init: failed to get random numbers`）。止めないことにした。
- Seatbelt の読み込みを既定で拒否にすると、ルートのディレクトリ（`/`）も読めなくなり、プロセスの起動時に libignition が `/` を開けず、メッセージなしの `Abort trap: 6` で止まった。macOS 同梱の `/System/Library/Sandbox/Profiles/dyld-support.sb` に合わせて、`(literal "/")` を許した。この間に実行した本物の Vault の確認では、80 件すべてが exit 2 になった（中断も exit 2 に変わるため）。`Abort` も数えるようにして確かめ直した。
- この環境の Bash ツールの `find` は、Claude Code のシェルのスナップショットのシェル関数で、出力の順が `/usr/bin/find` と違う。そのため、`find … | head -80` で選ばれるノートが、ユーザーのターミナルとこちらで違った。
- 2026-11-24 01:38 に、共有の作業ツリーが別の操作で `main` に切り替えられた。ユーザーが通常のターミナルで、このブランチへの切り替えと rebase を行った。

<a name="codex"></a>

## Codex のレビュー

2 回分の採否は、2026-11-24 にユーザーが確定した（すべて推奨案。直し方は [plan.md の Codex のレビューを受けた変更](plan.md#review-changes-codex)）。1 タスクあたり 5 回までの上限のうち、2 回を使った。

<a name="codex-1"></a>

### 1 回目: `codex review --base main`（2026-11-24、`5af70d3`）

総評: `patch is incorrect`（確度 0.97）。Seatbelt の実行時の確認は、Codex の環境で `sandbox-exec` が拒否されたため行っていない。`check-repo.py`・shellcheck・`actionlint` は通ったとのこと。

| # | 優先度 | 指摘 | 採否 | 理由 |
| --- | --- | --- | --- | --- |
| 1 | P1 | Vault の中の `secrets/`・`credentials/` などの `.md` は、ユーザー設定の Read の deny では読めないが、Seatbelt は Vault の `.md` を一律で読ませる（`check-vault-note.sb` 38-39 行） | 採る | 今の Vault には該当する `.md` は 0 件（`/usr/bin/find` で確かめた）。ただ、profile の許可から deny のパターンに当たるパスを外すだけで、設定との食い違いがなくなる |
| 2 | P2 | Vault の外の `.md`（`/Users` の下の共有フォルダなど、Seatbelt で拒否しない場所）へのアンカー付きのリンクで、リンク先の本文が読まれる | 採らない | エージェントの sandbox からも読める場所なので、新たに漏れる内容はない。止めると、そうしたリンクのあるノートが毎回「点検できない」になる |
| 3 | P2 | Vault の点検スクリプトが、同じ中身の別の場所のファイルへの symlink だと、比較は通るが、点検スクリプトが `__file__` から決める Vault のルートがずれ、正しいノートを「Vault の外」として黙って点検しない | 採る | 中身が漏れる穴ではないが、エージェントが点検を黙って止められる。外の段で、点検スクリプトの realpath が `<Vault の realpath>/_System/Scripts/check_note.py` でなければ exit 2 にする |
| 4 | P2 | `#<!-- コメント --> 見出し` の行で、点検スクリプトが `AttributeError` で止まる（`check_note.py` 327-328 行） | この PR の外 | Vault の点検スクリプトの不具合。写しはバイト単位の写しなので、Vault 側で直し、写しの更新手順で取り込む。今は、フックが「例外で止まった」と知らせる |
| 5 | P2 | 引用の中のフェンス付きコードを認識せず、コード例の `[[example]]` を Wikilink として誤報する（`check_note.py` 293-301 行） | この PR の外 | 4 と同じ |
| 6 | P3 | Command Line Tools がない端末では、`.md` 以外の編集や、点検スクリプトのあるほかのプロジェクトでも、`xcode-select --install` を促す（`check-vault-note.sh` 27-31 行） | 採らない | plan.md の受け入れたリスクに書いてある。直すには bash 側にも Vault の固定の判定を重ねて書く必要があり、判定が 2 か所になる |

<a name="codex-2"></a>

### 2 回目: challenge（`codex exec`、2026-11-24、`5af70d3`）

プロンプトは `.gstack/tmp/codex-challenge-vault-note.md`（Git の管理外）。守るべき 3 つの不変条件を壊す具体的な入力を、変更前との比較で挙げるよう頼んだ。3 つは、エージェントのコードを動かさないこと、sandbox で読めない内容を渡さないこと、出力の構造を壊させないこと。総評は `VERDICT: FINDINGS`。

Codex の確認では、profile の書き方（`require-all` と `regex`、`(target same-sandbox)`）は意図どおりに解釈され、終了コードが 0 に化ける経路はなかった。

| # | 重さ | 指摘 | 採否 | 理由 |
| --- | --- | --- | --- | --- |
| 1 | Medium | profile は既定で読み込みを許すので、`$HOME`・一時ディレクトリの外にある、sandbox が名前のパターンで拒否するファイル（共有フォルダの `*.pem` など）を、Vault の中の `.md` という名前の symlink 経由で、リンク先として読ませられる。アンカーの有無と、UTF-8 でないバイトの値が出る | 採る | 読み込み（`file-read-data`）を既定で拒否にし、Python の起動に要るシステムの場所・Vault の `.md`・`SELF`・`COPY` だけを許す。1 回目の #2 もこれで塞がる |
| 2 | High（条件付き） | `DEVELOPER_DIR` が書ける場所を指していると、そこの python3 を実行する。`-I` でもシステムの `site` の初期化は残る | 一部採る | `DEVELOPER_DIR` は Claude Code から渡る環境変数で、エージェントは変えられない。`xcode-select -s` は root が要るので、この部分は採らない。`-S` を両方の段に足す（標準ライブラリしか使わない） |
| 3 | Low | 出力の行が `# ` で始まると、Markdown の見出しとして解釈されうる | 採る | 各行の先頭に決まった印（`- `）を付ける |
| 4 | Low | Vault の点検スクリプトを保護されたファイルへの symlink にすると、そのファイルが公開済みの写しと一致するかが分かる | 採らない | 分かるのは、公開済みのバイト列と一致するかの 1 ビットだけ。1 回目の #3 の対策で、さらに狭まる |
| 試験 | — | 外のファイルの試験が、もともと拒否する場所にしかない。Seatbelt を起動できないときに exit 2 になるかを確かめていない | 採る | `/Users` の下の共有フォルダ（誰でも書ける）に一時ファイルを置く試験と、壊れた profile で exit 2 になる試験を足す |

<a name="real-machine"></a>

## 実機の確認

2026-11-24 に、ユーザーが Vault で Claude Code を起動して確かめ、完了と報告した（`5af70d3`。出力の詳細は共有されていない）。
