---
status: done
created: 2026-11-23
---

# modern-web-guidance の導入と更新の自動化の試験記録

<a name="environment"></a>

## 環境

2026-11-23 に確認した。

| 項目 | 版 |
| --- | --- |
| Claude Code | 2.1.330 |
| `modern-web-guidance`（npm） | 1.0.1（`skill-version` 2026_11_10-47b4c80e） |
| SkillSpector | 2.13.6 |
| Python | 3.15.2（mise）、3.9.6（`/usr/bin/python3`） |
| Node.js | 26.13.1（mise）、npm 11.20.0 |

<a name="results"></a>

## 手順ごとの結果

[計画の「手順と確認」](plan.md#steps)の順に並べる。

| # | 確認 | 結果 | 確かめ方と観測 |
| --- | --- | --- | --- |
| 1 | 作業ブランチ | 合格 | PR #70 のマージコミット `a55bfa8` を HTTPS で取得し、そこから `feat/modern-web-guidance` を切った。`chore/mise-skillspector` との差分がないので、sandbox の中で切り替えられた |
| 2 | テストが先に失敗する | 合格 | スクリプトがない状態で、29 件すべてが失敗した |
| 3 | 更新スクリプトのテストが通る | 合格 | 30 件が、mise の Python 3.15.2 と `/usr/bin/python3` 3.9.6 の両方で通った。変異テスト（下記）も行った |
| 4 | `update-skills.sh` のテストが通る | 合格 | 先に 3 件が失敗し、実装の後に 14 件が通った。`bash -n` と `shellcheck` も通った |
| 5 | CLI が 1.0.1 で動く | 合格 | 人が通常のターミナルで `mise install 'npm:modern-web-guidance'` を実行した。sandbox の中で `DISABLE_TELEMETRY=1 modern-web-guidance --version` が `1.0.1` を返した |
| 6 | 生成したスキル | 合格 | `--out` で本物の 1.0.1 から生成した。上流の SKILL.md との差分は計画した変換だけ。`chrome-extensions` は `LICENSE.md` を除いて上流と同一。人が `--out ~/dotfiles/claude/skills` で置いたものは、scratchpad に生成したものと `diff -r` で一致した |
| 6a | SkillSpector の指摘 | 合格 | `modern-web-guidance` は上流のままで 100/100（CRITICAL、194 件）、変換後は 0/100（0 件）。`chrome-extensions` は 56/100（HIGH、6 件）で、中身は誤検知（[計画の事実](plan.md#facts)） |
| 7 | npx 系の実行が拒否される | 合格 | 5 行のとき: `npx --no-install modern-web-guidance --version`・`pnpm --version modern-web-guidance`・`npm exec --version modern-web-guidance`・`NPM_CONFIG_CACHE=/tmp/x npx --no-install modern-web-guidance --version`・`DISABLE_TELEMETRY=1 npx --no-install modern-web-guidance --version` が拒否された。7 行に広げた後: `npm --version modern-web-guidance`・`bun --version modern-web-guidance` も拒否された。対照の `pnpm --version`・`NPM_CONFIG_CACHE=/tmp/x npm --version`・`bun --version`・`npm --version` は通ったので、拒否は deny の規則によるもの |
| 8 | スキルが一覧に出て、CLI が警告なしで動く | 合格 | リンクを張った後、このセッションのスキルの一覧に 2 つとも出た。`search "light dismiss dialog" --skill-version 2026_11_10-47b4c80e` が結果を返し、stderr は空（更新を促す警告なし）。`retrieve "light-dismiss-a-dialog"` がガイドを返した |
| 9 | CI と CLAUDE.md | 合格 | `actionlint` が通った |
| 10 | 文書とスナップショット | 合格 | `/sync-skill-docs` で文書を直し、人がスナップショットを作り直した後、`mise run claude:skills-check` が `RESULT: no differences` |
| 11 | 全体の検査 | 合格 | 下記 |
| 12 | `/review` の指摘を直す | 合格 | [レビュー](#review)。直した後、本物の 1.0.1 から `--out` で生成し直したものは、置いてあるスキルと `diff -r` で一致した（検証を強くしても、生成物は変わらない）。引数なしの実行は「最新（固定している版 1.0.1）」で、何も書かなかった |

<a name="automated"></a>

## 自動の試験と検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B claude/scripts/test-update-modern-web-guidance.py`（mise と `/usr/bin/python3`） | OK（58 件。レビューの前は 30 件、1 回目の修正の後は 49 件） |
| `/usr/bin/python3 -B claude/scripts/test-update-skills.py` | OK（15 件。レビューの前は 14 件） |
| `python3 -B .github/scripts/test-check-repo.py` | OK（87 件） |
| `python3 -B claude/scripts/test-skills-check.py` | OK |
| `python3 -B .github/scripts/check-repo.py` | `modern-web-guidance` を含めて PASS。`markdown-links` だけ失敗し、原因はこの作業の対象外の未追跡のファイル（`docs/work/20261121_claude-clones/design.md` の、存在しないリンク先 3 件） |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし |
| `actionlint` | 指摘なし |

<a name="mutation"></a>

## 変異テスト

スクリプトの写しで安全装置を 1 つずつ外し、テストが失敗することを確かめた。

| 外したもの | 結果 |
| --- | --- |
| 変換の後に npx 系の実行の指示が残っていないかの検査 | 失敗した（捕まえた） |
| tarball の、通常のファイル以外の拒否 | 最初は通ってしまった。テストのシンボリックリンクが tarball の外を指していて、tarfile が別の例外で止まっていたため。リンク先を tarball の中にし、エラーの理由も確かめるように直した後は、失敗した |
| パスの検査（`..`・絶対パス） | 失敗した |
| `--skill-version` と `skill-version.txt` の照合 | 失敗した |
| `npm pack` を一時ディレクトリで実行すること | 失敗した |
| レジストリの latest が古いときに下げないこと | 失敗した |

`/review` の指摘を直した後に足した安全装置も、同じ方法で確かめた。12 件すべてで、テストが失敗した（捕まえた）。

- 正規の相対パスの検査（`//` など）
- ドットで始まる名前の拒否
- 大文字小文字・Unicode の正規化だけが違う名前の衝突の検査
- frontmatter のキーの許可リスト
- 読み込み時に実行する書き方（`` !`…` ``）の拒否
- package.json の依存の検査
- インストール時のスクリプトの検査
- npm の一時キャッシュとレジストリの指定
- 入れ替えの途中の失敗での戻し
- latest が固定した版より古いときの失敗
- `bun x`・`yarn dlx` の検出
- 引数なしで何も書かないこと

`update-skills.sh` が更新スクリプトを `-I` で呼ぶことも、写しで `-I` を外すと `test_mwg_runs_isolated` が失敗することで確かめた。

2 回目のレビューの指摘（D5）を直した後に足した安全装置も、同じ方法で確かめた。12 件すべてで、テストが失敗した（捕まえた）。

- フェンス形式（` ```! `）の拒否
- package.json の `bin` の検査
- package.json の `name` の検査
- `package/` の外のエントリーの拒否
- `binding.gyp` の拒否
- `chrome-extensions` の名前の許可リスト
- ファイルとディレクトリの名前の衝突の検査
- 行の継続をつなぐ処理
- npm の `--prefix`
- Ctrl-C での戻し
- 戻しの失敗時に写しを残すこと
- 前になかったスキルの片付け

<a name="review"></a>

## レビュー

`/review` の 1 回目は、Testing・Maintainability・Security・Performance・Simplification の 5 つの観点、攻撃者視点のレビュー、Red Team のサブエージェントで行った（State Machines の観点は、信号が権限の `deny` の一覧に反応しただけで、状態遷移がないので出さなかった。Codex の外部のレビューは、規則でユーザーが通常のターミナルで実行するので、ここでは実行していない）。CRITICAL 4 件・INFORMATIONAL 17 件の指摘を受け、ユーザーが D1〜D4 を選んだ（[計画のレビューで変えたこと](plan.md#review-changes)）。19 件を直し、2 件（上流の modern-web-guidance のスキルに増えたファイル、NOTICE）は受け入れるリスクにした。

2 回目は、直した差分を自分で読み直し、攻撃者視点のレビューを 1 つ出した。専門観点のレビューは出し直していない。8 件の指摘を受け、ユーザーが D5（すべて直す）を選んだ。直した後に、本物の 1.0.1 から `--out` で生成し直したものは、強くした検証をすべて通り、置いてあるスキルと一致した。

2 回目のサブエージェントは、自分の Bash が sandbox の外で動いていた（`$HOME` に書けた）と報告し、確かめるために `$TMPDIR` と `$HOME` に空のディレクトリを作ってすぐ消したと書いた。指示はファイルの編集を禁じていた。この実行は確かめていない。

<a name="deviations"></a>

## 計画から変えたこと

- 検証の対象を、ローカルの節を足した後の本文に広げた。最初の文面（変更の表示とローカルの節）が、npx の後に `modern-web-guidance` が続く形を含み、SkillSpector の RP1 に当たったため。文面も、この形と「npx command」という語を含まないように直した。
- 初回の取り込みは、人が通常のターミナルで `--out ~/dotfiles/claude/skills` を実行して置いた。`chrome-extensions` は 25 ファイルあり、Write ツールで置くと確認が多いため。
- `chrome-extensions` の参照ファイル（小文字の名前）を、`markdown-names` の例外にした（`check-repo.py` の `VENDORED_SKILLS`、CLAUDE.md の規約）。名前を変えると、SKILL.md からの参照が壊れるため。
- 計画で未確認としていた「deny のルールが、環境変数を前に付けた形に当たるか」は、当たることを確かめた（手順 7）。
- `/review` を受けて、`update-skills.sh` からは何も書かず、取り込みは `--apply` を明示する形に変えた。ほかの変更とあわせて [計画のレビューで変えたこと](plan.md#review-changes) に書いた。

<a name="unverified"></a>

## 確かめていないこと

- 新しい版があるときの流れ（引数なしの終了コード 3、`--out --latest`、`--apply`）。npm に 1.0.1 より新しい版がないので、本物では動かしていない。テストの偽物（`npm`・`skillspector`・`check-repo.py`）で確かめた。
- `--apply` の最後の `check-repo.py` は、PATH の `python3` で動かす。mise が効いていないターミナルで `/usr/bin/python3`（3.9）が選ばれると、tomllib がなくて失敗と表示される。
- `DISABLE_TELEMETRY=1` を付け忘れたときに、sandbox の通信制限で `play.googleapis.com` への送信が止まるか、許可を求める確認が出るか。
- 新しいセッションで、フロントエンドの作業のときに `modern-web-guidance` が実際に起動するか。
