---
status: done
created: 2026-11-18
---

# mise の paranoid と gstack の置き場所のフックの確認記録

[plan.md](plan.md) の Task 6 の記録。設計は [design.md](design.md) にある。

<a name="automated"></a>

## 1. 自動の検査

2026-11-18 に、Task 5 のコミット（文書）の後で実行した。

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

<a name="review"></a>

## 4. /review

2026-11-18 に実行した。専門の担当 5 つ（Testing・Maintainability・Security・Performance・Simplification）、反対の立場の担当、Red Team が読み、私が中心の確認をした。Codex は使っていない（Task 7 で人間が実行する）。

| 指摘 | 出どころ | 対応 |
| --- | --- | --- |
| グローバルの CLAUDE.md から消した、git が途中で止まったときの注意書きは、ほかのリポジトリでもまだ要る（`.env*`・lock ファイル・`.claude/settings.json`） | 中心・反対・Red Team | 一般的な形で残し、`!` を頼む前に変わるファイルを確かめる手順を足した |
| git を経由する経路は、すべてのリポジトリの `.env*`・`.claude/settings.json`・`.mcp.json` にも当てはまる | Red Team | design の非目標 1 と 7 章を直し、次の作業の範囲を広げた |
| フックが入力を読まずに終わり、大きな入力で書き手が SIGPIPE で切られる | 反対 | 入力を読み捨てる。テストで 141 から 0 になることを確かめた |
| フックの拒否の理由に、仕込んだ側が決められるパスが入る | 反対 | 固定の文にした。仕込んだ文字列が出ないことをテストで確かめた |
| ガードのコマンドを別のフックに差し替えても、検査が通る | Testing | テストを足した |
| `~` で起動したセッションでは、Write ツールで信頼の記録に書ける | Red Team | `Edit(~/.local/state/mise/**)` を deny、`Edit(~/dotfiles/mise/**)` を ask で足した |
| 「差分を確かめて mise trust」は守れない。拒否のメッセージは確かめずに trust するよう促す | 反対・Red Team | 「ファイル全体と読み込む env ファイルを確かめ、ファイルを指定して」にそろえた（フック 2 つとテストを含む） |
| 「mise がルートの設定を自動で信頼する」という古い説明が 3 か所 | 中心 | 直した。dotfiles の `mise.toml` は人間が信頼し直した |
| フックの表に新しいフックがない | Maintainability | 足した |
| 戻す順番、切り替えた後の再起動、B2 の受け入れ理由、`_.path`、`mise.lock` と provenance | 反対・Red Team | design に書いた |
| 確認記録の日付 | 中心 | 直した |
| matcher が Edit・Write・MultiEdit・NotebookEdit だけ | 反対 | 直していない（判断）。Artifact の既定の外への保存は人間に確認がある。`*` にすると、すべてのツールを止めることになる |
| `trusted_config_paths` を足されても、`mise-paranoid` が通る | Security（確信度 4） | 直していない。今その設定はない |

直した後に、自動の検査を記録し直した（2026-11-18）。

| 検査 | 結果 |
| --- | --- |
| `check-repo.py` | 10 項目すべて PASS |
| `test-check-repo.py` | 69 件 OK |
| フックのテスト 5 本 | 失敗 0（`test-guard-additional-dirs.sh` は 17 件） |
| `test-update-skills.py` | OK |
| shellcheck・actionlint | 出力なし |

<a name="codex"></a>

## 5. Codex のレビュー

2026-11-18 に、人間が普段の端末で `codex review --base origin/main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を実行した。Claude Code の `!` からは、codex の app-server の起動が `Operation not permitted` で失敗した（`!` 自体は sandbox の外で動いていることを、`~/.ssh/config` を開けることで確かめた。原因は調べていない）。

- 結果: 直すべき新しい不具合はない。
- Codex が実行したもの: `check-repo.py`（10 項目）、shellcheck、actionlint、`git diff --check`、新しいフックが普段の HOME で通し、空の HOME で止めること。
- Codex が実行しなかったもの: 一時ファイルを作る回帰テストと、実際のセッションでの確認（読み取り専用のため）。どちらも 1・2・4 章で実行した。

<a name="unverified"></a>

## 6. 確かめられなかったこと

- **フックが実際のセッションで呼ばれていること:** 確かめるセッションの記録には、SessionStart のフックの記録だけがあり、PreToolUse のフックの跡はなかった。出力のないフックは記録されないと考える（推測）。分かっているのは次のこと。
  - 読み込まれている（事実）: 新しいセッションの `/hooks` に、PreToolUse の `[User] /bin/bash ~/.claude/hooks/guard-additional-dirs.sh`（`Edit|Write|MultiEdit|NotebookEdit`）が表示された（2026-11-18）。
  - 登録は `check-repo.py` で確かめた。書き方は、すでに動いている `ask-gh-pr-write.sh` と同じ（`/bin/bash`・`timeout`・`onFailure`）。
  - 拒否の動きは、本物の `~/.gstack/projects` を差し替えずに確かめる方法がないので、自動テストだけで確かめた。
