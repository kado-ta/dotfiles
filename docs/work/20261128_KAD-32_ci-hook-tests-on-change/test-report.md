---
status: in-progress
created: 2026-11-28
---

# 試験記録: CI の macOS のジョブを、関係するファイルが変わったときだけ動かす

<a name="related"></a>

## 関連

- [plan.md](plan.md)
- Linear: KAD-32

<a name="local-checks"></a>

## 手元の検査（2026-11-28）

| 検査 | コマンド | 結果 |
| --- | --- | --- |
| リポジトリの検査 | `python3 -B .github/scripts/check-repo.py` | 18 項目すべて PASS（終了コード 0） |
| 検査のテスト | `python3 -B .github/scripts/test-check-repo.py` | 164 件 OK（115.0 秒） |
| shellcheck | `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 指摘なし（終了コード 0） |
| actionlint | `actionlint` | 指摘なし（終了コード 0） |
| zizmor | `zizmor --offline .` と `zizmor --offline --persona=auditor .` | どちらも "No findings to report."（1.33.1、終了コード 0） |

- フックとラッパーは変えていないので、フック回帰テストは手元では実行していない。CI の `Hook regression tests` で実行する（[CI](#ci)）。
- zizmor の auditor は、初めは `actions: read` に理由のコメントがないこと（`undocumented-permissions`）を挙げた。行末にコメントを書いて消えた。

<a name="api"></a>

## API の確認（2026-11-28）

sandbox の中の読み取り専用の `gh` で、`changes` ジョブと同じ呼び出しを実行した。

| 呼び出し | 結果 |
| --- | --- |
| `gh api 'repos/kado-ta/dotfiles/actions/workflows/ci.yaml/runs?branch=main&event=push&status=success&per_page=5'` | 新しい順に返った（`9223cd7` 09:44、`b13f9e5` 09:34、`1dd22c4` 09:14、…）。`total_count` は 122 |
| 同じ呼び出しに `per_page=1` と `--jq '.workflow_runs[0].head_sha // empty'` | `9223cd7b24b04e3aeeee6babb95bc37f61c86433`（終了コード 0） |
| `branch=no-such-branch` で同じ呼び出し | 何も出力しない（終了コード 0） |

一覧の並びは、公式の文書（Workflow runs）の読めた範囲には書かれていない。

<a name="simulation"></a>

## 判定のスクリプトの試験（2026-11-28）

`ci.yaml` の `changes` ジョブの `run:` を、ファイルから字下げを外してそのまま抜き出し、`shell` を指定しない `run:` と同じ `bash -e`（Workflow syntax の `defaults.run.shell` の表）で実行した。リポジトリを `$TMPDIR` に一時的にクローンし、HEAD と `EVENT_NAME`・`HEAD_SHA`・`GITHUB_RUN_ATTEMPT`・`GITHUB_OUTPUT` を変えて当てた。push の場合は、`gh` を偽物に差し替えた。偽物は、API の応答の JSON に、ステップが渡した `--jq` の式を本物の `jq -r` で当てて出す（渡った引数が `ci.yaml` の URL と同じことも確かめた）。PR の場合は、HEAD をマージコミットにし、`HEAD_SHA`（`pull_request.head.sha` に当たる）には、その 2 つ目の親（PR の先端）を渡した。

| 場合 | 終了コード | 出力 | 期待 |
| --- | --- | --- | --- |
| PR #163（`bin/.Brewfile`・`ghostty/config`）。pull_request と push（最後の成功 = 1 つ前のマージ） | 0 | `hook_tests=false` | 飛ばす |
| PR #162（`docs/work` だけ）。同上 | 0 | `hook_tests=false` | 飛ばす |
| PR #161（`claude/bin/cc-crit`・`claude/hooks/tests/`・`claude/settings.json` などを変えた）。同上 | 0 | `hook_tests=true` | 動かす |
| PR #155（`claude/settings.json` を変えた）。同上 | 0 | `hook_tests=true` | 動かす |
| PR #157（`.github/scripts/` と VSCode の設定だけ）。同上 | 0 | `hook_tests=false` | 飛ばす |
| PR #153（`docs/work` だけ）。同上 | 0 | `hook_tests=false` | 飛ばす |
| #163 の push で、最後の成功が #161 より前（#161 の run が失敗した） | 0 | `hook_tests=true` | 動かす（D8） |
| #163 の push で、最後の成功が #161（#162 の run が失敗した） | 0 | `hook_tests=false` | 飛ばす（対象のパスが #161 と同じ） |
| #163 の push で、API の絞り込みが効かず、実行中のこの run（HEAD と同じコミット、結論なし）と PR の run が先頭に来た | 0 | `hook_tests=true`（基点は 3 つ前の成功） | 動かす（D9） |
| #163 の push で、API の絞り込みが効かず、実行中のこの run しか返らない | 0 | `hook_tests=true`、警告「比べる基点がない」 | 動かす（D9・D12） |
| #163 の push の再実行（2 回目の試行）。差分は関係するパスを含まない | 0 | `hook_tests=true`（`gh` を呼ばない） | 動かす（D10） |
| #163 の PR の再実行（2 回目の試行） | 0 | `hook_tests=true` | 動かす（D10） |
| push で、成功した run がない（`gh` が何も出さない） | 0 | `hook_tests=true`、警告「比べる基点がない」 | 動かす（D12） |
| push で、`gh` が失敗する | 0 | `hook_tests=true`、警告「最後に成功した main の push の run を読めない」 | 動かす（D12） |
| push で、最後の成功のコミットがクローンにない | 0 | `hook_tests=true`、警告「基点 … と比べられない（git diff の終了コード 128）」 | 動かす（D12） |
| pull_request の `head.sha` が空 | 0 | `hook_tests=true`、警告「HEAD が PR のテスト用のマージコミットではない」 | 動かす（D13・D12） |
| pull_request の `head.sha` が HEAD の 2 つ目の親と違う | 0 | `hook_tests=true`、警告「HEAD が PR のテスト用のマージコミットではない」 | 動かす（D13・D12） |
| `workflow_dispatch`（想定外のイベント） | 1 | なし | 失敗（`hook-tests` の `if:` で動かす） |
| `claude/hooks/` に日本語の名前のファイルを足したマージ | 0 | `hook_tests=true` | 動かす |
| `docs/work/` に日本語の名前のファイルを足したマージ | 0 | `hook_tests=false` | 飛ばす |
| `claude/hooks/` のフックを `claude/` の直下へ動かしたマージ | 0 | `hook_tests=true` | 動かす |
| ルートに `.gitattributes`（テストの `working-tree-encoding=UTF-16`）を足したマージ | 0 | `hook_tests=true` | 動かす（D14） |
| `claude/.gitattributes`（`eol=crlf`）を足したマージ | 0 | `hook_tests=true` | 動かす（D14） |
| `claude/Hooks/tests/test-x.sh`（大小だけが違うパス）を、Git の中だけで足したマージ | 0 | `hook_tests=true` | 動かす（D15） |
| HEAD が PR の先端（マージ用のコミットでない）。フックを変えた後に docs だけのコミットを重ねた | 0 | `hook_tests=true`、警告「HEAD が PR のテスト用のマージコミットではない」 | 動かす（D13） |
| main の 3 つ前のマージから分かれた docs だけの PR。HEAD はマージ用のコミット | 0 | `hook_tests=false`（基点はマージ先の先端） | 飛ばす（D13。3 つ前と比べていれば、#161 の変更が入って動いていた） |

- どの場合も、ログに出す `base:` の行は、渡した基点と同じだった（基点を決められない場合と再実行の場合は、その前にステップが終わるので出ない）。
- D9 の jq の式は、実際の API にも当てた。絞り込みのある呼び出しでも、絞り込みのない呼び出し（新しい 3 件。PR の run を含む）でも、`9223cd7b24b0…`（main の push の最新の成功）を返した。
- `changes` ジョブそのものが失敗した場合（想定外のイベント、checkout の失敗など）は、`hook-tests` の `if:` の `needs.changes.result == 'success'` が偽になるので、`hook-tests` が動く。`if:` の評価そのものは手元では確かめられないので、[CI](#ci) で確かめる。
- 試験は 7 回やり直した。初回は PR の基点を `HEAD^1`、push の基点を `before` にし、判定できないときはジョブを失敗させる形だった。`/review` と Codex の指摘で、`base.sha`（plan の D7）、最後の成功（D8）、jq の確認（D9）、再実行（D10）、判定できないときに成功で終える形（D12）、2 つ目の親を確かめた `HEAD^1`（D13）、`.gitattributes`（D14）、大小を区別しない比較（D15）に変えたので、そのたびに全件を取り直した。最後の結果は、gstack の QA の記録ツールのチェックポイント 018 にある。
- `--icase-pathspecs` は、Git の中だけで作ったコミットで別に確かめた（Git 2.56.1）。大小を区別する `-- claude/hooks` は `claude/Hooks/tests/test-x.sh` の追加を拾わず（終了コード 0）、`--icase-pathspecs` を付けると拾った（終了コード 1）。変更がないとき（0）と基点が壊れているとき（128）は変わらなかった。
- 大小の場合を足した最初の取り直し（チェックポイント 017）では、「main の 3 つ前のマージから分かれた docs だけの PR」が `true` になった。試験側で index を書き換えたまま作業ツリーを戻さず、前の場合の `claude/.gitattributes` が作業ツリーに残って、後の `git add -A` で入ったためだった。別の index ファイルで木を作るように試験を直し、取り直した（018）。
- 初回は、`bash --noprofile --norc -eo pipefail`（`shell: bash` を指定したときのもの）で実行していた。`bash -e` で取り直し、同じ結果を得た。
- 試験の初回は、PR 番号でマージを探す試験側の grep が、古い履歴の同じ番号の PR（#161・#155 など）にも当たり、正しく探せなかった。最初の一致を使うように直した。

<a name="review"></a>

## `/review`（gstack、2026-11-28）

- 3 回のパスで見た。1 回目と 2 回目は、差分が追跡中のファイルで 50 行未満だったので、専門のレビュワーを飛ばした。3 回目は、直した分で 58 行になったので、Testing と Maintainability の専門のレビュワーを出した。gstack の Codex のパスは `codex_reviews` が無効なので動かなかった。Claude の敵対的レビュー（サブエージェント）は、どのパスでも実行した。
- 3 回目のパスの指摘で直したので、gstack の上限（直すパスは 3 回まで）に達し、`/review` は収束を確かめないまま終えた。3 回目の直しは、判定の試験（上の表）と検査で確かめた。
- QA の煙試験（判定のスクリプトの成功と、基点がすべて 0 の失敗）と plan の手順 1・2 を、gstack の QA の記録ツールで取った。記録ツールのまとめ（1 回だけ実行できる）は 1 回目の証跡で実行してしまったので、2 回目以降の取り直しはチェックポイントとして残した。どれも期待どおりだった。

| 指摘 | 出どころ | 扱い |
| --- | --- | --- |
| `hook-tests` を条件付きで飛ばす（必須のチェックのゲートを緩める） | ゲートの走査 | 残す（KAD-32 と plan の D1〜D5 が根拠。ユーザーが選んだ） |
| 試験記録の「既定のシェル」が誤り（`shell` を指定しないときは `bash -e`） | 核のレビュー | 直した |
| main への push の run が取り消されると、関係する変更が main で確かめられない | 敵対的レビュー 1 回目 | 直した（plan の D6） |
| PR の基点が `HEAD^1` に頼っている | 敵対的レビュー 1 回目 | 直した（plan の D7） |
| `CLAUDE.md` の追記が、判定に失敗したときも動くことを書いていない | 敵対的レビュー 1 回目 | 直した |
| run のない push の変更が漏れる／一覧の足し忘れ／`changes` の実行中の取り消し | 敵対的レビュー 1 回目 | 受け入れるリスクとして plan の R4〜R6 に書いた（ユーザーが選んだ）。R4 は後で D8 により解消した |
| push の基点（`before`）で前の push の hook-tests が通っていたとは限らない | 敵対的レビュー 2 回目 | 直した（plan の D8） |
| D7 のコメントの「差分は広がる側にしか倒れない」が不正確 | 敵対的レビュー 2 回目 | 直した（「対象のパスが基点と同じときだけ飛ばす」） |
| PR の向き先を変えても再実行されない | 敵対的レビュー 2 回目 | 受け入れるリスクとして plan の R8 に書いた（ユーザーが選んだ） |
| main のブランチを作り直したときなどに `changes` が失敗する | 敵対的レビュー 2 回目 | 対応しない（安全側に倒れる意図どおりの動き。ruleset が削除と force push を止めている） |
| API の絞り込みが効かないと、実行中のこの run が返って毎回飛ばす | 敵対的レビュー 3 回目 | 直した（plan の D9） |
| 再実行で、動いて失敗した hook-tests を飛ばして緑にできる | 敵対的レビュー 3 回目 | 直した（plan の D10） |
| `checks` などが main で赤のままだと基点が進まない | 敵対的レビュー 3 回目 | 受け入れるリスクとして plan の R10 に書いた（ユーザーが選んだ） |
| PR の run のステップにも `GH_TOKEN` が渡る | 敵対的レビュー 3 回目 | 対応しない（plan の R11。ユーザーが選んだ） |
| `claude/README.md` の CI の説明が、条件付きで動くことを書いていない | Maintainability | 直した |
| 試験記録の「専門のレビュワーを飛ばした」が、3 回目のパスと食い違う | Maintainability | 直した（この節） |
| 判定の回帰テストがリポジトリにない／`if:` と `needs` を検査で守っていない | Testing | 後続の KAD-40 で扱う（plan の D11。ユーザーが選んだ） |

<a name="codex"></a>

## Codex レビュー

### 1 回目（2026-11-28T11:03:52Z、`b13f9e5` の上の未コミットの変更）

人間が通常のターミナルで `codex review --uncommitted -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を実行した。最終メッセージは `~/.codex/sessions` の記録から読んだ。

- 結論: "patch is incorrect"（確からしさ 0.98）。actionlint・`zizmor --offline`・ShellCheck は通ったが、GitHub Actions の上での実行は確かめていない、とある。
- [P2]（確からしさ 0.99）成功した run の履歴が空でも、最初の CI が成功できるようにする。API が空の一覧を正しく返しても、空の基点で `git diff` が 128 で失敗する。macOS のテストが通っても run 全体が失敗し、D8 が読む成功の履歴に入らないので、次の push でも同じ失敗が続く。API の呼び出しが成功して基点だけがないときは、`hook_tests=true` を出して `changes` を正しく終えるべき（`ci.yaml` 128〜131 行）。

| 指摘 | 採否 | 理由 |
| --- | --- | --- |
| [P2] 成功した run の履歴が空だと、`changes` が失敗し続ける | 採用（範囲を広げた。plan の D12） | 指摘どおり、run が成功できず、基点が進まない。同じ型の失敗は、`gh` の失敗（`ci.yaml` の改名で 404 になるなど）と `git diff` の失敗にもある。判定できないときはすべて、警告を出して `hook_tests=true` で成功に終える形にした（ユーザーが選んだ） |

### 2 回目（2026-11-28T11:13:57Z、`b13f9e5` の上の未コミットの変更。D12 を入れた後）

1 回目と同じコマンドを、人間が通常のターミナルで実行した。

- 結論: "patch is incorrect"（確からしさ 0.97）。actionlint・`zizmor --offline --persona=auditor`・ShellCheck は通ったが、GitHub Actions の上での実行は確かめていない、とある。
- [P2]（確からしさ 0.98）PR は実際のマージの基点と比べる。イベントの `base.sha` と、取り出したテスト用のマージコミットの 1 つ目の親は、一致しないことがある（GitHub Actions での実例として、ほかのリポジトリの Issue を挙げている）。そのあいだに main で `claude/hooks/` が変わっていると、docs だけの PR でも macOS のジョブが動く。docs だけのマージ #162 では、1 つ目の親との比較は差分なし、その 1 つ前との比較は差分ありだった。テスト用のマージコミットであることを確かめたうえで、1 つ目の親を基点にすべき（`ci.yaml` 125〜126 行）。
- [P2]（確からしさ 0.95）チェックアウトに効く Git の属性も判定に含める。ルートか `claude/` 直下の `.gitattributes` だけでテストのファイルの `working-tree-encoding` を変えると、Git の中の内容が同じでも、macOS のジョブが読む内容は変わる（`test-cc-crit.py` を UTF-16 にすると Python が読めない）。今のパスの一覧ではこれを見つけられず、hook-tests を飛ばす（`ci.yaml` 138〜139 行）。
- [P3]（確からしさ 1.0）plan の手順 2 が、基点がないときに終了コードが 0 でないことを求めていて、D12 と食い違う。警告・出力・終了コードの 3 つを確かめる書き方にすべき（`plan.md` 194 行）。

| 指摘 | 採否 | 理由 |
| --- | --- | --- |
| [P2] PR は実際のマージの基点と比べる | 採用（plan の D13） | `base.sha` が古いと、docs だけの PR でも macOS のジョブが動く（手元の試験で再現した）。HEAD の 2 つ目の親が `head.sha` と同じことを確かめてから `HEAD^1` と比べ、違えば判定できない扱い（テストを動かす）にした。D7 で心配した、checkout の ref を変えたときの抜けも塞がる（ユーザーが選んだ） |
| [P2] チェックアウトに効く `.gitattributes` も判定に含める | 採用（plan の D14） | 指摘どおり。`.gitattributes` と `claude/.gitattributes` をパスに足した。対象のパスの中のものは、もとから入る |
| [P3] plan の手順 2 が D12 と食い違う | 採用 | 手順 2 と C3 の確かめ方を、終了コード 0・`hook_tests=true`・警告の 3 つで書き直した |

### 3 回目（2026-11-28T11:43:45Z、`b13f9e5` の上の未コミットの変更。D13・D14 を入れた後）

1 回目と同じコマンドを、人間が通常のターミナルで実行した。

- 結論: "patch is incorrect"（確からしさ 0.93）。`git diff --check`・actionlint・ShellCheck・`zizmor --offline` は通ったが、GitHub Actions の上での実行は確かめていない、とある。
- [P2]（確からしさ 0.88）判定の取り消しで、必須のチェックを通さない。`Repository checks` が先に成功し、`changes` がまだ動いているときに PR の CI を取り消すと、始まっていない `Hook regression tests` が skipped になり、macOS のテストを動かさずに必須のチェックを満たしうる。plan の R6 は `Repository checks` も取り消される前提だが、2 つのジョブは独立している。差分がないことによる skip と、判定の取り消しを区別し、後者ではマージを止めるべき（`ci.yaml` 158 行）。
- [P2]（確からしさ 0.95）macOS で同じ場所に解決されるパスを判定に含める。`claude/Hooks/tests/` に `test-*.sh` を足すと、大文字・小文字を区別しない macos-latest の作業領域では、今のテストの glob に拾われる。一方、`git diff` の `claude/hooks` はこれに一致せず、PR でも main の push でもテストが飛ぶ。`--icase-pathspecs` を使うか、大小だけが違うパスをリポジトリの検査で拒むべき（`ci.yaml` 144〜146 行）。

| 指摘 | 採否 | 理由 |
| --- | --- | --- |
| [P2] 判定の取り消しで、必須のチェックを通さない | 不採用（受け入れるリスクとして plan の R6 を直した） | plan の R6 の前提（`Repository checks` も取り消される）は誤りだった。ただ、run を手で取り消せるのは書き込み権限のある人（ユーザーだけ）で、新しい push による取り消しは先端のコミットが変わるので当たらない。運用で受け、`claude/README.md` に「取り消した PR は再実行してからマージする」と書いた（ユーザーが選んだ）。塞ぐ形（集約のジョブ）は R6 に書いた |
| [P2] macOS で同じ場所に解決されるパスを判定に含める | 採用（plan の D15） | `git --icase-pathspecs diff` にした。手元で、大小を区別する比較では拾えず、付けると拾えることを確かめた |

<a name="ci"></a>

## CI

PR の作成後に追記する。
