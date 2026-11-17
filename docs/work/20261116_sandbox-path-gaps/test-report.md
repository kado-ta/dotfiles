---
status: in-progress
created: 2026-11-18
---

# mise の paranoid と gstack の置き場所のフックの確認記録

[plan.md](plan.md) の Task 6 の記録。設計は [design.md](design.md) にある。

<a name="automated"></a>

## 1. 自動の検査

2026-11-17 に、Task 5 のコミット（文書）の後で実行した。

| 検査 | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 10 項目すべて PASS（`mise-paranoid` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 66 件 OK（変更前は 58 件） |
| `test-protect-main-branch.sh` | 94 件 PASS、失敗 0 |
| `test-validate-command.sh` | 29 件 PASS、失敗 0 |
| `test-ask-gh-pr-write.sh` | 66 件 PASS、失敗 0 |
| `test-gh-read-token.sh` | 24 件 PASS、失敗 0 |
| `test-guard-additional-dirs.sh`（新規） | 12 件 PASS、失敗 0 |
| shellcheck（`-S warning`）・actionlint | 出力なし、終了コード 0 |

フックのテストは、`$TMPDIR` をカレントディレクトリにして、`/bin/bash` と絶対パスで実行した。

<a name="sessions"></a>

## 2. 新しいセッションでの確認

2026-11-18 に、人間が変更後の設定でセッションを起動し、ダミーで確かめた。確かめるセッションには、ダミーのほかは編集しないよう伝えた。mise は 2026.11.9 になっていた（design の C5 の時点では 2026.11.8）。

<a name="v1"></a>

### 2.1 V1: paranoid

ダミーは `tmp/paranoid-probe/mise.toml`（`[env]` に `CC_PARANOID_PROBE = "1"`）。

| # | 誰が・どこで | 操作 | 結果 |
| --- | --- | --- | --- |
| V1-1 | dotfiles のセッションの Bash | そのディレクトリで `mise env` | `Config files in …/mise.toml are not trusted.` 終了コード 1 |
| V1-2 | 同上 | そのディレクトリで `command -v jq && jq --version` | mise のインストール先の jq（shim ではない）、`jq-1.8.2`、終了コード 0 |
| V1-3 | 同上 | `mise trust mise.toml` | `failed to ln -sf … ~/.local/state/mise/trusted-configs/…`、`Operation not permitted`、終了コード 1 |
| V1-4 | 人間の端末（mise を有効にしたシェル） | 信頼する前に cd | `mise WARN … is not trusted`、値は空 |
| V1-5 | 同上 | `mise trust` してから cd し直す | 値は `1` |
| V1-6 | 同上 | 中身を `"2"` に変えてから cd し直す | `mise WARN … is not trusted`、値は空 |

- 信頼されていない設定は、端末のないコマンドでは止まり、cd では警告が出て読み飛ばされた（事実）。
- 中身を変えると、信頼は外れた（事実。V1-6）。
- Claude の Bash からは、信頼の記録に書けなかった（事実。V1-3）。確かめるセッションは、グローバルの CLAUDE.md の「自分で `mise trust` を実行しない」に反して実行したが、ダミーに対する明示の依頼だった。

<a name="v2"></a>

### 2.2 V2: denyWrite

| # | 誰が・どこで | 操作 | 結果 |
| --- | --- | --- | --- |
| V2-1 | dotfiles のセッションの Bash | `tmp/paranoid-probe/mise.toml` を作る | 終了コード 0（mise の 10 項目の denyWrite が外れた） |
| V2-2 | `~/.config` で起動したセッションの Bash | `touch ~/.config/mise/cc-probe` | `Operation not permitted`、終了コード 1 |

<a name="v3"></a>

### 2.3 V3: フック

| # | 操作 | 結果 |
| --- | --- | --- |
| V3-1 | Write ツールで `tmp/v3-write.txt` を作り、Edit ツールで書き換える | どちらも成功 |
| V3-2 | Write ツールで `~/.gstack/projects/cc-guard-probe.txt` を作る | 成功 |

本物の `~/.gstack/projects` は差し替えていない。拒否の動きは、1 章の自動テストで確かめた。

<a name="review-focus"></a>

## 3. plan の「特に確かめること」

1. **`HOME` の途中の symlink:** 誤検知しない（テストの「HOME through a symlink」。`$TMPDIR` が `/var` の下なので、ほかのケースも同じ条件で通った）。
2. **先のない symlink と通常のファイル:** どちらも拒否する（テスト）。
3. **paranoid の値の形:** 文字列と、片方だけのリストを通さない（`test_partial_paranoid_fails`）。
4. **信頼されていない設定のあるディレクトリの Bash:** この環境では、jq は mise の shim ではなくインストール先に解決され、信頼されていない設定のあるディレクトリでも動いた（V1-2）。そのため、フックが jq で止まることはなかった。PATH で jq が shim に解決される環境では止まりうる（推測）。そのときは、ルートの CLAUDE.md の今の案内（`mise trust`）で戻す。
5. **フックを登録した後の普段の書き込み:** 通った（V3）。

<a name="unverified"></a>

## 4. 確かめられなかったこと

- **フックが実際のセッションで呼ばれていること:** 確かめるセッションの記録には、SessionStart のフックの記録だけがあり、PreToolUse のフックの跡はなかった。出力のないフックは記録されないと考える（推測）。分かっているのは次のこと。
  - 読み込まれている（事実）: 新しいセッションの `/hooks` に、PreToolUse の `[User] /bin/bash ~/.claude/hooks/guard-additional-dirs.sh`（`Edit|Write|MultiEdit|NotebookEdit`）が表示された（2026-11-18）。
  - 登録は `check-repo.py` で確かめた。書き方は、すでに動いている `ask-gh-pr-write.sh` と同じ（`/bin/bash`・`timeout`・`onFailure`）。
  - 拒否の動きは、本物の `~/.gstack/projects` を差し替えずに確かめる方法がないので、自動テストだけで確かめた。
