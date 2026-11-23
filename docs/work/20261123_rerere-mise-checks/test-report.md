---
status: in-progress
created: 2026-11-23
---

# 試験記録: git の rerere を止め、mise の信頼の経路を check-repo.py で確かめる

関連: [plan.md](plan.md)

<a name="commands"></a>

## 確認コマンド

最後に実行したのは、レビューの修正の後（`6c18297` と、plan の記述の直し）。

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

まだ実行していない。

<a name="follow-ups"></a>

## 後続の候補

- sheldon の env-zsh が、ディレクトリを移るたびに作業ディレクトリの `.env` を読み込む。sandbox の外のシェルで、環境変数（`MISE_*`・`GIT_CONFIG_*`）を設定でき、任意のコードも動きうる。プラグインの本体を読んで確かめたのはサブエージェントだけで、このセッションでは読めなかった。
- グローバルの設定や信頼の記録の場所を変える `MISE_*` の環境変数（`MISE_GLOBAL_CONFIG_FILE`・`MISE_CONFIG_DIR`・`MISE_STATE_DIR` など）を調べて、検査に足す。
- git を環境変数（`GIT_CONFIG_GLOBAL`・`GIT_CONFIG_COUNT`）や alias の `-c` で動かす経路と、`.git/worktrees/*/config.worktree`（`extensions.worktreeConfig` があるときだけ効く）。
