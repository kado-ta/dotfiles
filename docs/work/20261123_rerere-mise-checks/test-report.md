---
status: done
created: 2026-11-23
---

# 試験記録: git の rerere を止め、mise の信頼の経路を check-repo.py で確かめる

関連: [plan.md](plan.md)

<a name="commands"></a>

## 確認コマンド

最後に実行したのは、Codex の challenge への対応の後（理由のコメントと文書の直し）。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 12 項目すべて PASS（`mise-paranoid`・`rerere` を含む） |
| `python3 -B .github/scripts/test-check-repo.py` | 89 件 OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了コード 0 |
| `actionlint` | 終了コード 0 |
| `git config --file bin/.gitconfig --type=bool --get rerere.enabled` | `false` |

<a name="tdd"></a>

## テストを先に書いた記録

| 段階 | 失敗を確かめたテスト | 失敗の理由 | 実装の後 |
| --- | --- | --- | --- |
| rerere | `test_gitconfig_rerere_not_false_fails` の 6 件 | 検査がなく、終了コード 0 | OK。実リポジトリは `bin/.gitconfig` を変えるまで `FAIL rerere` だけ |
| mise | `test_trusted_config_paths_fails` の 2 件、`test_mise_env_override_fails` の 4 件 | 検査がなく、終了コード 0 | OK |
| レビューの修正 | `test_gitconfig_include_after_rerere_fails` の 2 件、`test_mise_env_override_fails` の `bin/.zshenv`・`config/sheldon/plugins.toml` | 検査が通ってしまう | OK |

`test_gitconfig_rerere_false_forms_pass` と `test_gitconfig_include_before_rerere_passes` は、検査が厳しすぎないことを確かめるテストなので、実装の前から通る。

<a name="smoke"></a>

## 動作確認（`/review` の Step 4.7）

証跡は Git の管理外の `.gstack/tmp/qa-reports/run-20261123T090238Z/` にある。判定は pass。

| 確認 | コマンド | 期待 | 結果 |
| --- | --- | --- | --- |
| C1 | `python3 -B .github/scripts/check-repo.py <worktree>` | 終了コード 0、`PASS rerere`・`PASS mise-paranoid` | 期待どおり（capture 004） |
| C2 | `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=rerere.enabled GIT_CONFIG_VALUE_0=false` を付けて、`[rerere]` を外した写しで実行 | 終了コード 1、`FAIL rerere` | 期待どおり（capture 005）。環境変数の git の設定では通らない |
| テスト | `python3 -B .github/scripts/test-check-repo.py` | 89 件 OK | 期待どおり（capture 006） |

<a name="review"></a>

## `/review` の結果

担当: Testing・Maintainability・Security・Performance・Simplification の専門家と、Claude の adversarial のサブエージェント。Codex のパスは、規則（Bash から Codex を動かさない）に従って省いた。

| 指摘 | 出どころ | 対応 |
| --- | --- | --- |
| `[rerere]` より後ろに include を足すと、検査は通るのに rerere が有効に戻る（`--file` は include をたどらない） | Testing・Security・adversarial | 直した（D1。人間の判断）。最後の `rerere.enabled` より後ろに `include.path`・`includeif.*.path` があれば失敗にする |
| 環境変数名を探すファイルの一覧が足りない（`bin/link.sh` が `bin/.??*` をリンクする。sheldon の `inline` が zsh の起動で動く） | Maintainability・Testing・Security・adversarial | 直した（D2。人間の判断）。`bin/.z*` と `config/sheldon/plugins.toml` を足した |
| CLAUDE_CONFIG.md が、場所を変える `MISE_*` の環境変数を残る経路として書いていない | Security | 文書に書いた。検査に足すのは後続の候補 |
| plan に業務のパスを書いていた | 中心のレビュー | plan から外した |
| 「`.git/config` は sandbox が止める」の記述に、submodule の設定の例外がない | adversarial | 文書に書いた |
| `MISE_YES`・`settings.yes` を禁止していない | adversarial | 取り下げた。paranoid の `config` は信頼の確認の `--yes` を外す（mise の文書。Security の専門家もソースで確かめた） |
| sheldon の env-zsh が、作業ディレクトリの `.env` を読み込む | adversarial | この PR より前からある。別の課題にする（下の後続の候補） |
| git を環境変数や alias の `-c` で動かす経路、すでにある `rr-cache` が残る | adversarial | plan の「影響」に書いた |

<a name="security-review"></a>

## `/security-review` の結果

確信度の高い脆弱性はなかった。新しい git の呼び出しは引数のリストで渡し、シェルを使わない。`git config --file` は include・fsmonitor・hooks を動かさない。CI は `pull_request` で動き、`pull_request_target` ではない。検査は一致した変数の名前だけを出し、ファイルの中身を出さない。

<a name="codex"></a>

## Codex のレビュー

このタスクで 2 回（上限は 5 回）。人間が通常のターミナルで実行し、結果は `~/.codex/sessions` の記録から読んだ。

| 回 | 日時（UTC） | 対象 | コマンド | 結果 |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-23 09:40 | `219930c` | `codex review --base main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` | 指摘なし。「patch is correct」（確信度 0.9）。`check-repo.py` の 12 項目、shellcheck、actionlint は成功し、`rerere.enabled` が `false` であることも確かめた |
| 2 | 2026-11-23 10:00 | `0717532` | `codex exec - -s read-only -c skills.include_instructions=false`（challenge。プロンプトは変更前と比べた後退と、検査を誤らせる入力を聞く形） | 下の表 |

1 回目の採否: 指摘がないので、直すものはない。Codex は、読み取り専用の sandbox で一時ディレクトリを作れず、`test-check-repo.py` を実行できなかった。テストは、このセッションで実行して OK を確かめている（[確認コマンド](#commands)）。

2 回目（challenge）の採否:

| 指摘 | 採否 | 理由 |
| --- | --- | --- |
| `check_rerere` が PASS なのに実効値が true になる入力は、見つからない | — | 確かめた結果として残す |
| 実効値が false でも、後ろに無害な include（`path = /dev/null`、一致しない `includeIf`）があると FAIL になる | 不採用 | 意図した保守的な判定。文書にも「後ろに include を置かない」と書いている |
| `MISE_"PARANOID"=0` のように引用符で区切る、sheldon の TOML のエスケープ（`P`）で書く、検査の対象外のファイルを source する、で検査を抜けられる | 文書だけ採用 | 文字列の一致で判定する方式の限界。変更前の検査でも同じく抜けられる。CLAUDE_CONFIG.md の残る経路に書き、PR のレビューで見ることにした |
| 普段の操作の変化（rerere が止まる、`unset MISE_PARANOID` も FAIL になる、空の `trusted_config_paths` も FAIL になる、など） | 不採用 | どれも意図した変化か、まれな書き方 |
| 「空の `trusted_config_paths` でも、パスで信頼する経路を開く」という理由が誤り | 理由を直した | mise v2026.11.12 の `src/config/config_file/mod.rs`（`trusted_config_path_matches`）で確かめた。リストの要素に `.any()` を当てるので、空のリストは何も信頼しない。キーごと禁じる扱いは変えない（D3。2026-11-23、人間の判断） |
| CLAUDE.md の「後ろに `[include]` を置かない」は、検査の実装（`include.path` のキーの位置を見る）と言葉がずれる | 採用 | CLAUDE.md を「include（`include.path`・`includeif.*.path`）を置かない」に直した |

<a name="follow-ups"></a>

## 後続の候補

- sheldon の env-zsh が、ディレクトリを移るたびに作業ディレクトリの `.env` を読み込む。sandbox の外のシェルで、環境変数（`MISE_*`・`GIT_CONFIG_*`）を設定でき、任意のコードも動きうる。プラグインの本体を読んで確かめたのはサブエージェントだけで、このセッションでは読めなかった。[Issue #78](https://github.com/kado-ta/dotfiles/issues/78) にした。
- グローバルの設定や信頼の記録の場所を変える `MISE_*` の環境変数（`MISE_GLOBAL_CONFIG_FILE`・`MISE_CONFIG_DIR`・`MISE_STATE_DIR` など）を調べて、検査に足す。
- git を環境変数（`GIT_CONFIG_GLOBAL`・`GIT_CONFIG_COUNT`）や alias の `-c` で動かす経路と、`.git/worktrees/*/config.worktree`（`extensions.worktreeConfig` があるときだけ効く）。
