---
status: done
created: 2026-11-11
---

# CI の追加: 試験記録

関連: [計画書](plan.md)、[PR #11](https://github.com/kado-ta/dotfiles/pull/11)

<a name="local"></a>

## 手元での実行

macOS（`/bin/bash` 3.2.57、`/usr/bin/python3` 3.9.6）で、CI と同じコマンドを実行した。`check-repo.py` とそのテストは mise の python3（3.15）で実行した。

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/test-check-repo.py` | 25 件 OK（レビュー対応前は 22 件） |
| `python3 -B .github/scripts/check-repo.py` | 7 項目すべて PASS（未追跡の計画書を含めても PASS） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning`（v0.11.0） | 0 件（Task 1 の修正前は SC2046 が 9 件） |
| `actionlint` | 0 件 |
| `/bin/bash claude/hooks/tests/test-*.sh` | ask-gh-pr-write 66/0、gh-read-token 24/0、protect-main-branch 94/0、validate-command 13/0（pass/fail） |
| `/usr/bin/python3 -B claude/hooks/tests/test-*.py` | cc-safe-pr、cc-safe-push ともに OK |

TDD の確認:

- `test-check-repo.py` は、`check-repo.py` がない状態で 22 件すべて失敗することを確かめてから実装した。
- レビュー対応の 2 件（`test_untracked_file_with_user_path_fails`、`test_nested_fence_keeps_checking`）は、修正前に失敗することを確かめた。`test_ignored_file_with_user_path_passes` は `--exclude-standard` の回帰を防ぐテストで、修正前から成功する。

<a name="github-actions"></a>

## GitHub Actions

run 42986033272（コミット `b19a22c`、2026-11-11）。結論は success で、警告・エラーの注記は 0 件。

| ジョブ | 所要時間 | 結果 |
| --- | --- | --- |
| Repository checks（ubuntu-latest） | 9 秒 | shellcheck と actionlint のチェックサムが一致（`OK`）。`check-repo.py` は 7 項目 PASS、テスト 25 件 OK、shellcheck と actionlint は 0 件 |
| Hook regression tests（macos-latest） | 1 分 35 秒 | `GNU bash, version 3.2.57(1)-release (arm64-apple-darwin25)`、`Python 3.9.6`。jq と git は `/opt/homebrew/bin`。シェルのテストは手元と同じ件数ですべて成功、Python のテストは 73 件と 49 件で OK |

Actions の設定（ユーザーが有効化した後の `gh api repos/kado-ta/dotfiles/actions/permissions`）: `enabled: true`、`allowed_actions: selected`、`sha_pinning_required: true`。許可する Action の内訳は管理者権限が要るので取得していないが、`actions/checkout` が動いたので GitHub 製の Action は許可されている。

<a name="review-focus"></a>

## Review Focus の確認結果

1. スラッグ: 全角括弧・インラインコード・スラッシュを含む見出しと同名の見出しは、テストで成功を確認した。それ以外の近似の食い違いは、見送った Minor にある。
2. パーセントエンコード: パスはテストで、日本語の fragment はレビュワーが成功を確認した。
3. `claude/settings.json` がない: hook-scripts と push-permissions が FAIL になることを、テストで確認した。
4. macOS ランナーのインタプリタ: 上の表のとおり、本番と同じ版だった。
5. `test-ask-gh-pr-write.sh` の時間計測: CI で `PASS long command took 1s`（閾値 10 秒）。

<a name="review"></a>

## レビュー

新しいレビュワー（別のコンテキスト）がブランチ全体を確認し、判定は With fixes（Critical 0、Important 1、Minor 12）だった。

修正したもの（コミット `0c844e5`）:

- 手元の実行で、未追跡のファイルを検査していなかった（Important）。CI は push の後に動くので、ユーザー名を含むパスを公開前に防げるのは手元の実行だけ。
- 入れ子の Markdown フェンスで、その後の行を黙って検査しなくなっていた。レビュワーは Minor としたが、検査が黙って止まるのは fail-open なので Important として直した。

見送った Minor（別の作業の候補）:

- hook-scripts が、解釈できない形のコマンド（`${HOME}`、`/usr/bin/env bash`、`bash -e`、`zsh`）を黙って飛ばす
- 「Show interpreters」の `command -v jq git` は、jq がなくても成功する（jq がないと回帰テスト自体が失敗するので実害はない）
- GitHub では有効なリンク（`.`、ルート基準の `/`、`?plain=1`、インデントしたコードブロックの中）が FAIL する
- スラッグの近似（`_強調_`、見出しの中の HTML、連番の衝突）
- local-paths の誤検出（`/Users/` の下の共有フォルダ `Shared`、`/home/` を含む URL）。この試験記録でも、例として書いたパスが検出された
- push-permissions が、`cc-safe` を含まない allow の拡大（`claude-push/*` など）を見ない
- テストの抜け（`aws/credentials` そのもの、別ファイルのアンカー、`$HOME` 形式、statusLine の実行権限、git の失敗）
- git が失敗したときに stderr を出さない
- `cancel-in-progress` が main への push にも効く。1 つのステップが失敗すると後続のステップを実行しない
- CLAUDE.md に、`check-repo.py` には Python 3.11 以上が必要と書いていない
- `check-repo.py` に型ヒントがない

<a name="rulings"></a>

## 作業中の判断

- worktree を分けず、元のチェックアウトの `ci/add-checks` ブランチで作業した。
- `mise/setup.sh` は sandbox で sed の書き込みが拒否されたので、Edit ツールで同じ 1 行を直した。
- テストの補助関数は `run()` ではなく `check()` とした（`unittest.TestCase.run` を上書きしないため）。
- `test_tracked_aws_credentials_fails` は `aws/config` で検査した（このセッションの sandbox は `**/credentials` の読み取りを拒否するため）。
- `main()` は検査ごとに例外を FAIL にする（fail closed）。
- CLAUDE.md の「規約」の「フック回帰テストのみ」も、CI と矛盾しないよう書き換えた。
- PR を作る前にブランチ全体のレビューを行い、指摘の修正を PR 前に入れた。
- Actions が有効かを確かめる前に push と PR を行った。PR 作成時は Actions が無効でチェックが動かなかったので、有効化した後、計画書のコミットの push で CI を起動した。

<a name="notes"></a>

## 気づいた点

- sandbox の中で `gh run view --log` を実行すると、キャッシュ（`~/.cache/gh`）に書けずに失敗する。`XDG_CACHE_HOME` を `$TMPDIR` 配下に向けると取得できた。
- 作業ツリーの `claude/settings.json` の変更（`~/.crit` の書き込み許可など）はユーザーのもので、このブランチのコミットには含めていない。
