---
status: done
created: 2026-11-28
---

# CI の macOS のジョブを、関係するファイルが変わったときだけ動かす

<a name="related"></a>

## 関連

- Linear: KAD-32（この作業）、KAD-34（リポジトリを非公開にする。KAD-32 が先）、KAD-39（CI の実行時間を減らす。KAD-34 の前の後続）、KAD-40（判定の回帰テストと `if:` の検査。KAD-39 の前の後続）
- 前の作業: [docs/work/20261111_ci-checks/plan.md](../20261111_ci-checks/plan.md)（`ci.yaml` の 2 ジョブを作った）

<a name="goal"></a>

## 目的

`Hook regression tests`（`hook-tests`、macos-latest）を、そのジョブのテストが読むファイルが変わったときだけ動かす。`Repository checks`（ubuntu）は今までどおり毎回動かす。

macOS のジョブは、1 回の CI の費用の約 9 割を占める（Issue の測定。2026-11-27）。公開のままでも、macOS のランナーの待ち（10〜37 分の記録）が減る。

<a name="done-criteria"></a>

## 完了の条件

Issue の条件を、確かめ方と組にして書く。

| # | 条件 | 確かめ方 |
| --- | --- | --- |
| C1 | 関係するファイルを変えない PR では、macOS のジョブが動かない。その PR はマージできる | 後片付けの PR（`docs/work` だけを変える）で、`Hook regression tests` が skipped になり、`gh pr view --json mergeStateStatus` が `CLEAN` になる |
| C2 | 関係するファイルを変える PR では、macOS のジョブが今までどおり動く | この PR（`ci.yaml` を変える）で、`Hook regression tests` が動いて通る |
| C3 | 判定に失敗したときは、macOS のジョブを動かす | 手元で、判定できない場合（基点がないなど）に `hook_tests=true` と警告が出ることを確かめる（D12）。CI では、判定のジョブそのものを `hook_tests=false` を出してから失敗させる一時的なコミットを足し、`Hook regression tests` が動くことを見る。その後、打ち消すコミットで戻す |
| C4 | main への push でも同じ判定にする | この PR のマージの push で動き（`ci.yaml` が変わる）、後片付けの PR のマージの push で skipped になる |

<a name="decisions"></a>

## 決めたこと

- D1: main への push も、PR と同じ判定にする（2026-11-28、ユーザーが選んだ）。Plan の承認の時点では、基点を直前の push（`before`）にし、「取りこぼしはない」と書いていたが、誤りだった。前の push の hook-tests が失敗・取り消し・未実行（run がない）だと、次の関係しない push は飛ばして緑になり、その変更は main で確かめられない（`/review` の敵対的レビューの指摘）。そのため D8 で、push の基点を最後に成功した run のコミットにする。ファイルの変更を伴わない壊れ方（macos-latest のイメージの更新など）には、次に関係するファイルを変えたときに気づく（[受け入れるリスク](#risks)の R2）。
- D2: 判定に失敗したときの動きは、CI でも確かめる（2026-11-28、ユーザーが選んだ）。一時的なコミットと打ち消すコミットを PR に残す。force push はしない。
- D3: 判定は、ubuntu の別のジョブ（`changes`）で行う。`hook-tests` の中で判定すると、macOS のランナーを起動した時点で 1 分ぶんの料金がかかる。`checks` ジョブの中で判定すると、`hook-tests` が `checks` の終わり（約 3 分）まで待つ。別のジョブの費用は、1 回あたり Linux の 1 分（0.006 ドル）。
- D4: 判定には外部のアクションを使わず、`git diff --quiet <基点> HEAD -- <パス>` の終了コードを使う。ファイル名を出力から読まないので、引用符で囲まれる名前（日本語や制御文字）で判定がずれない。
- D5: ワークフローの `on.*.paths` は使わない。ジョブの `if:` で飛ばす。
- D6: `concurrency` の group を、main への push ではコミットごと（`github.sha`）にする（2026-11-28、`/review` の後にユーザーが選んだ）。今までは同じ group で、続く push が前の run を取り消していた。D8 の後は、取り消されても次の push が最後の成功から比べるので抜けないが、どの push で hook-tests が壊れたかを特定できるように残す。PR は今までどおり、新しい push で古い run を取り消す。PR の run はいつも PR 全体の差分で判定するので、取り消されても抜けない。
- D7: （D13 で置き換えた）PR の基点は `github.event.pull_request.base.sha` にする（2026-11-28、`/review` の後にユーザーが選んだ）。初めは `HEAD^1`（`refs/pull/<番号>/merge` の 1 つ目の親）にしていた。`HEAD^1` は、checkout の ref を変えると直前のコミットになり、最後のコミットの差分しか見ずにテストが飛ぶ。`base.sha` との 2 つの木の比較なら、HEAD がマージ用のコミットでなくても、PR の変更は差分に入る。飛ばすのは、対象のパスが基点と同じときだけ。
- D8: main への push の基点は、最後に成功した main の push の run（`ci.yaml`）のコミット（`head_sha`）にする（2026-11-28、`/review` の 2 回目の後にユーザーが選んだ）。成功した run のコミットは、hook-tests が通ったか、対象のパスがさらに前の成功と同じだったので、確かめた状態と言える。前の push の run が失敗・取り消し・未実行でも、その変更は次の push の差分に入る（R4 も解消する）。REST API の `GET /repos/{owner}/{repo}/actions/workflows/ci.yaml/runs?branch=main&event=push&status=success&per_page=1` を、組み込みの `GITHUB_TOKEN`（`changes` ジョブだけ `actions: read`）と、ランナーに入っている `gh` で読む。一覧の並びが新しい順であることは公式の文書に書かれていないので、2026-11-28 に実際の API で確かめた。API が失敗したとき・成功した run がないときは、hook-tests を動かす（D12）。PR の基点は D7 のまま（main の先端）にする（R7）。
- D9: API の絞り込みに頼らず、jq でも `conclusion == "success"`・`event == "push"`・`head_branch == "main"` を確かめる（2026-11-28、`/review` の 3 回目の後にユーザーが選んだ）。絞り込みが効かないと、実行中のこの run（コミットが HEAD と同じ）が先頭に来て、毎回飛ばしてしまう。先頭が合わなければ、次の候補か、空（hook-tests が動く）になる。
- D10: run の再実行（`GITHUB_RUN_ATTEMPT` が 2 以上）では、判定せずに hook-tests を動かす（2026-11-28、同上）。判定し直すと、前の試行で（判定の失敗で安全側に倒れて）動いて失敗した hook-tests を飛ばし、run を緑にして、以後の基点にもしてしまう。再実行は人が頼む確認なので、費用は小さい。
- D11: 判定の回帰テストと、`hook-tests` の `needs`・`if:` を守る `check-repo.py` の検査は、この作業では入れず、KAD-40 で扱う（2026-11-28、同上）。
- D12: 判定できないとき（`gh` の失敗、基点が空、`git diff` の失敗）は、`::warning::` を出して `hook_tests=true` にし、`changes` ジョブを成功で終える（2026-11-28、Codex レビューの 1 回目の後にユーザーが選んだ）。初めは `changes` を失敗させ、`hook-tests` の `if:` で動かしていた。それだと run が失敗になり、D8 の基点（最後の成功）が進まないので、原因が続くと（成功した run の履歴が空、`ci.yaml` を改名して API が 404 になる、など）main が赤のまま抜け出せない（Codex の指摘）。想定外のイベントだけは、設定の誤りなので今までどおり失敗させる。`hook-tests` の `if:` の `!cancelled()` と `needs.changes.result == 'success'` は、`changes` そのものが失敗したとき（checkout の失敗など）のために残す。
- D13: PR の基点は、HEAD の 2 つ目の親が PR の先端（`github.event.pull_request.head.sha`）と同じとき、つまり HEAD がテスト用のマージコミットのときだけ、1 つ目の親（`HEAD^1`、実際のマージ先）にする。そうでなければ判定できない扱いにする（D12、hook-tests を動かす）（2026-11-28、Codex レビューの 2 回目の後にユーザーが選んだ）。D7 の `base.sha` は、テスト用のマージコミットの 1 つ目の親より古いことがあり、そのあいだの main の変更も差分に入って、docs だけの PR でも macOS のジョブが動く（Codex の指摘。安全側だが削減が減る）。2 つ目の親を確かめるので、D7 で `HEAD^1` をやめた理由（checkout の ref を変えると、最後のコミットだけと比べて黙って飛ぶ）も塞がる。
- D14: 判定のパスに `.gitattributes` と `claude/.gitattributes` を足す（2026-11-28、同上）。対象のパスの上の階層の `.gitattributes`（`working-tree-encoding`・`eol` など）だけを変えると、Git の中の内容が同じでも、チェックアウトでテストが読む内容が変わる（Codex の指摘）。どちらも今はない。対象のパスの中の `.gitattributes` は、もとからパスに入る。
- D15: 判定の `git diff` に `--icase-pathspecs` を付け、大文字・小文字を区別せずにパスを比べる（2026-11-28、Codex レビューの 3 回目の後）。macOS のランナーの作業領域は大小を区別しないので、`claude/Hooks/tests/test-x.sh` のように大小だけが違うパスを足すと、チェックアウトで `claude/hooks/tests/` に入り、テストの glob に拾われる。大小を区別する pathspec では、これを差分として拾えない（Codex の指摘。2026-11-28 に Git の中だけで作ったコミットで確かめた）。

<a name="spec"></a>

## GitHub の仕様（2026-11-28 に公式ドキュメントで確認）

- `if:` で飛ばしたジョブ: "A job that is skipped will report its status as "Success"." "It will not prevent a pull request from merging, even if it is a required check."（[Using conditions to control job execution](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions)）
- 必須のチェックで成功とみなす結果: "Successful check statuses are `success`, `skipped`, and `neutral`."（[Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)）
- `paths` で飛ばしたワークフロー: "checks associated with that workflow will remain in a "Pending" state." "A pull request that requires those checks to be successful will be blocked from merging."（[Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)）
- `needs` のジョブが失敗したとき: 依存するジョブは、状態の関数を使わない限り飛ばされる。同じ Troubleshooting のページは、この場合を "The dependent job is skipped and may not block merging" としている。つまり、判定のジョブが失敗しただけで必須のチェックが通りうる。そのため、`hook-tests` の `if:` に `!cancelled()` を入れる。状態の関数を入れると、既定の `success()` は付かない（"A default status check of `success()` is applied unless you include one of these functions."、[Expressions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions)）。
- `needs.<job_id>.result` は `success`・`failure`・`cancelled`・`skipped` のどれか（[Contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)）。
- `shell` を指定しない `run:` は `bash -e {0}` で動く（`bash` を指定したときは `bash --noprofile --norc -eo pipefail {0}`。[Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) の `defaults.run.shell`）。
- run の一覧の `status` は、結論（`success` など）でも絞れる（"For example, a conclusion can be success"、[Workflow runs](https://docs.github.com/en/rest/actions/workflow-runs)）。各 run のコミットは `head_sha`。`workflow_id` にはファイル名を渡せる（同じページ。抜き出しの要約で読んだ）。
- ジョブの `permissions` は、書かなかった権限を `none` にする（"all of those that are not specified are set to `none`"、Workflow syntax）。`gh` はすべての GitHub-hosted ランナーに入っていて、`GH_TOKEN` でトークンを渡す（[Using GitHub CLI in workflows](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli)）。

<a name="paths"></a>

## 関係するファイル

`hook-tests` が実行するテストと、それぞれが読むファイルを `grep` と目視で確かめた（2026-11-28）。

| パス | 読むテスト |
| --- | --- |
| `claude/hooks/`（`tests/` と `vault/` を含む） | 全テスト。フックの本体、`check-vault-note.py`・`.sb`、`vault/check_note.py` |
| `claude/bin/` | `test-cc-crit.py`・`test-cc-crit-profile.py`・`test-cc-safe-pr.py`・`test-cc-safe-push.py` |
| `claude/scripts/` | `test-settings-home-paths.py`・`test-update-skills.py`・`test-update-modern-web-guidance.py`・`test-register-mcp.py`（スクリプトを写して実行する） |
| `claude/mcp/` | `test-cc-crit.py`（`playwright.json` の `--blocked-origins`）、`test-register-mcp.py` |
| `claude/settings.json` | `test-cc-crit.py`（`denyRead` が cc-crit の対象に入っているか） |
| `.github/workflows/ci.yaml` | ジョブの定義そのもの |
| `.gitattributes`・`claude/.gitattributes` | テストは直接読まないが、チェックアウトの内容を変えうる（D14） |

`claude/scripts/` のうち、`hook-tests` が実行しないテスト（`test-skills-check.py` など。`checks` が実行する）の対象も入るが、ディレクトリで指定する方が漏れにくいので、絞らない。

直近 60 件のマージ（#162 まで）で数えると、この一覧のファイルを変えたのは 15 件（25%）だった。#163 までの 60 件では 14 件だった（R5）。

<a name="changes"></a>

## 変更するファイル

| ファイル | 変更 |
| --- | --- |
| `.github/workflows/ci.yaml` | `changes` ジョブ（`actions: read`）を足す。`hook-tests` に `needs: changes` と `if:` を足す。`concurrency` の group を、main への push ではコミットごとにする（D6） |
| `CLAUDE.md` | 規約の「これらとフック回帰テストは、PR と main への push で GitHub Actions も実行する」に、フック回帰テストは関係するファイルが変わったときだけ動くことを足す |
| `claude/README.md` | フックのテストの節の「PR と main への push では、GitHub Actions が macOS の … で同じテストを実行する」に、同じ条件（`/review` で見つかった）と、run を手で取り消した PR は再実行してからマージすること（R6）を足す |
| `docs/work/20261128_KAD-32_ci-hook-tests-on-change/plan.md` | この文書 |
| `docs/work/20261128_KAD-32_ci-hook-tests-on-change/test-report.md` | 確認の記録 |

`check-repo.py` は `ci.yaml` の `*_VERSION` の行だけを読む（`tool-versions`）ので、変えない。

<a name="workflow"></a>

## ワークフローの形

```yaml
# main への push は、コミットごとの group にして取り消し合わない。どの push の run も最後まで動かし、
# hook-tests を壊した push を特定できるようにする。
concurrency:
  group: ${{ github.workflow }}-${{ github.event_name == 'push' && github.sha || github.ref }}
  cancel-in-progress: true

jobs:
  # （checks は今のまま）

  # macOS のジョブ（hook-tests）は、テストが読むファイルが変わったときだけ動かす。
  changes:
    name: Detect hook test changes
    runs-on: ubuntu-latest
    timeout-minutes: 5
    # ジョブの permissions は、書かなかった権限を none にするので、contents も書く。
    permissions:
      contents: read
      actions: read # 最後に成功した main の push の run を読む
    outputs:
      hook_tests: ${{ steps.diff.outputs.hook_tests }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          # 基点のコミットが、浅い取得の範囲の外にありうる。履歴は小さい（パックで約 500 KiB）。
          fetch-depth: 0

      # 対象のパスが基点と同じときだけ、hook-tests を飛ばす。
      # hook-tests のテストが新しいファイルを読むようにしたら、ここのパスにも足す。チェックアウトの内容を
      # 変えうる .gitattributes（対象のパスの上の階層のもの）も含める。
      - name: Compare with the base
        id: diff
        env:
          EVENT_NAME: ${{ github.event_name }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          # 判定できないときは、hook-tests を動かして、このジョブを成功で終える。失敗させると run が成功せず、
          # push の基点（最後の成功）が進まないので、原因が続くと main が赤のまま抜け出せない。
          run_hook_tests() {
            echo "::warning::$1 hook-tests を動かす。"
            echo "hook_tests=true" >> "$GITHUB_OUTPUT"
            exit 0
          }
          # 再実行は人が頼む確認なので、判定せずに動かす。判定し直すと、前の試行で動いて失敗した hook-tests を
          # 飛ばし、run を緑にしうる。
          if [ "${GITHUB_RUN_ATTEMPT:-1}" -gt 1 ]; then
            echo "hook_tests=true" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          case "$EVENT_NAME" in
            # テスト用のマージコミット（refs/pull/<番号>/merge）は、1 つ目の親が実際のマージ先、2 つ目の親が PR の先端。
            # イベントの base.sha は 1 つ目の親とずれることがある。2 つ目の親を確かめずに HEAD^1 と比べると、
            # checkout の ref を変えたときに、最後のコミットだけと比べてしまう。
            pull_request)
              { [ -n "$HEAD_SHA" ] && [ "$(git rev-parse -q --verify 'HEAD^2' || true)" = "$HEAD_SHA" ]; } \
                || run_hook_tests "HEAD が PR のテスト用のマージコミットではない。"
              base=$(git rev-parse 'HEAD^1') ;;
            # before にすると、前の push の hook-tests が失敗・取り消し・未実行でも飛ばしてしまうので、
            # 最後に成功した main の push の run のコミットと比べる。一覧は新しい順（2026-11-28 に API で確かめた）。
            # 絞り込みが効かなかったとき（実行中のこの run が返るなど）に備えて、jq でも条件を確かめる。
            push) base=$(gh api "repos/$REPO/actions/workflows/ci.yaml/runs?branch=main&event=push&status=success&per_page=1" \
                    --jq '[.workflow_runs[] | select(.conclusion == "success" and .event == "push" and .head_branch == "main")][0].head_sha // empty') \
                    || run_hook_tests "最後に成功した main の push の run を読めない。" ;;
            *) echo "unexpected event: $EVENT_NAME" >&2; exit 1 ;;
          esac
          [ -n "$base" ] || run_hook_tests "比べる基点がない（成功した run がないなど）。"
          echo "base: $base"
          rc=0
          # macOS のランナーは大文字・小文字を区別しないので、claude/Hooks/tests/test-x.sh などもテストの glob に入る。
          git --icase-pathspecs diff --quiet "$base" HEAD -- \
            claude/hooks claude/bin claude/scripts claude/mcp claude/settings.json .github/workflows/ci.yaml \
            .gitattributes claude/.gitattributes || rc=$?
          case "$rc" in
            0) echo "hook_tests=false" >> "$GITHUB_OUTPUT" ;;
            1) echo "hook_tests=true" >> "$GITHUB_OUTPUT" ;;
            *) run_hook_tests "基点 $base と比べられない（git diff の終了コード $rc）。" ;;
          esac

  hook-tests:
    name: Hook regression tests
    needs: changes
    # if で飛ばしたジョブは Success を報告し、必須のチェックを満たす。changes が成功して false を出したときだけ飛ばす。
    # !cancelled() がないと、changes が失敗したときに飛ばされ、テストなしで必須のチェックが通る。
    if: ${{ !cancelled() && !(needs.changes.result == 'success' && needs.changes.outputs.hook_tests == 'false') }}
    runs-on: macos-latest
    # 以下は今のまま
```

- 判定の結果は「変更あり（1）」「変更なし（0）」「判定できない（それ以外）」の 3 つに分ける。判定できないときは、警告を出して `hook-tests` を動かし、ジョブは成功で終える（D12）。
- `github.event.pull_request.head.sha` と `github.repository` は、テンプレートで `run:` に埋め込まず、`env:` で渡す（zizmor の template-injection）。`actions: read` には、行末に理由を書く（zizmor の auditor の `undocumented-permissions`）。

<a name="steps"></a>

## 手順

1. `ci.yaml` を変える → actionlint・`zizmor --offline .` が通る。
2. 判定のスクリプト（`run:` の中身）を手元で過去のマージに当てる → `claude/` の関係するファイルを変えたマージで `hook_tests=true`、`docs/work` だけのマージで `false`。判定できないとき（基点がない・存在しない SHA・`gh` の失敗・HEAD がテスト用のマージコミットでない）は、終了コード 0、`hook_tests=true`、`::warning::` の 3 つがそろう（D12）。想定外のイベントでは終了コードが 0 でない。
3. `CLAUDE.md` を変える。
4. 規約の検査を実行する → `check-repo.py`・`test-check-repo.py`・shellcheck・actionlint・`zizmor --offline .` が通る。
5. `/review` でブランチの差分を見る → 指摘の採否を決め、採用したものを直す。
6. Codex レビューを提案する（設計判断を含むため。ユーザーが決める）。
7. `/crit-review` でブランチの差分を開く → `approved: true`。
8. push と PR の作成 → `gh pr checks` で C2（`Hook regression tests` が動いて通る）。
9. C3 の一時的なコミット（判定のステップの先頭で `hook_tests=false` を出してから `exit 1`）を push する → `Detect hook test changes` が失敗し、`Hook regression tests` が動く。打ち消すコミットを push する → 両方が通る。
10. マージはユーザーが行う。マージの後、main の push の CI で、`Detect hook test changes` の基点が最後に成功した main の run のコミットになり（ログで確かめる）、`Hook regression tests` が動くこと（C4 の前半）を見る。
11. 後片付けの PR（test-report の追記と `status: done`）で C1 と C4 の後半を確かめる。

<a name="risks"></a>

## 受け入れるリスク

- R1: テストが新しいファイルを読むようにして、パスの一覧に足し忘れると、そのファイルだけを変えた PR でテストが動かない。`ci.yaml` のパスの隣と `CLAUDE.md` に書いて防ぐ。検査では止めない（テストが読むファイルを静的に知る方法がない）。
- R2: macos-latest のイメージ・Homebrew の jq・git の更新など、ファイルの変更を伴わない壊れ方には、次に関係するファイルを変える PR まで気づかない（D1）。直近の割合では、4 件に 1 件の PR が該当する。
- R3: 費用の見込み。非公開にした場合、この変更だけでは Free の枠（月 12 ドル）に収まらない。KAD-34 の前に、別の手が要る。この作業の範囲外とし、KAD-39 で扱う（2026-11-28、ユーザーが提案に同意した）。見込みは[費用の見込み](#cost)にある。D6 で main への push の run が取り消されなくなるので、main の run はこれまでより少し多く最後まで動く。
- R4: （D8 で解消）main への push で run そのものがない（コミットメッセージの `[skip ci]`、GitHub がイベントを落とした場合など）と、基点が `before` のときは、その push の変更が main で確かめられなかった。D8 では、次の push が最後に成功した run から比べるので、差分に入る。
- R5: パスの一覧は「動かす側」を挙げる。足し忘れると、テストが黙って飛ぶ（R1 と同じ）。代わりに「`docs/` と `*.md` だけなら飛ばす」形にすれば、足し忘れても動く側に倒れるが、直近 60 件のマージで macOS のジョブが動く件数が 14 件から 38 件に増え、削減がほぼ消える（2026-11-28 に数えた）。採らない。
- R6: `changes` の実行中に run を取り消すと、`hook-tests` の `if:` は `!cancelled()` で偽になり、成功扱い（skipped）で終わる見込み（確かめていない）。変更前は cancelled で終わり、マージを止めていた。初めは「同じ run の `Repository checks`（必須）も取り消されてマージを止めるので、マージの守りは変わらない」と書いていたが、誤りだった。2 つのジョブは独立しているので、`Repository checks` が先に成功していれば、テストなしで必須のチェックがそろう（Codex レビューの 3 回目の指摘）。run を手で取り消せるのは書き込み権限のある人（このリポジトリではユーザーだけ）で、fork の PR の作者にはできない。新しい push で古い run が取り消される場合は、PR の先端のコミットが変わり、必須のチェックは新しい run で決まるので、当たらない。そのため、コードでは塞がず、運用で受ける。run を手で取り消した PR は、再実行してからマージする（2026-11-28、ユーザーが選んだ）。塞ぐなら、`if: always()` の集約のジョブを `Hook regression tests` の名前にし、macOS のジョブの成功か、差分がないことによる skip のときだけ成功させる形になる。
- R7: PR の基点はマージ先の main の先端（D13）なので、main の hook-tests が失敗しているあいだは、関係しない PR は飛ばして通る。変更前は、関係しない PR も赤になってマージを止めていた。そのマージの push は最後の成功から比べる（D8）ので、main は直るまで赤のまま残る。PR の基点も最後の成功にすると、関係しない PR も止まるが、API の呼び出しが PR の run にも要る。採らない。
- R8: `pull_request` の既定のイベントには、向き先の変更（`edited`）が入らない。PR を積み重ねて向き先を main に変えると、古い向き先と比べて飛ばした結果が残り、必須のチェックを満たす。このリポジトリでは PR を積み重ねることはまれで、マージの後の main への push（D8）で確かめる。`edited` を足すと、タイトルや本文の編集でも run が動くので、採らない（2026-11-28、ユーザーが選んだ）。
- R9: D8 は、一覧が新しい順であることを、公式の文書ではなく実際の API で確かめた。並びが変わって古い成功が返っても、差分が広がる側（テストを動かす側）に倒れる。`changes` が遅れて動き、HEAD より後の push の run の成功が返ることはありうる。その run は HEAD の変更を含めて確かめているので、対象のパスがそれと同じときに飛ばしても安全。
- R10: D8 の基点は run 全体の成功なので、hook-tests と関係のない `checks` が main で失敗し続けると（ツールの取得が 404 になる、など）、成功する run が出ず、基点が進まない。壊れる向きは安全側（hook-tests が動く）だが、削減の効果は消え、基点が止まったことに気づく仕組みはない。main の run が赤なのは見えるので、その修正を急ぐ運用で受ける（2026-11-28、ユーザーが選んだ）。API が失敗し続ける場合（`ci.yaml` の改名など）は、D12 で run は成功するが、毎回 hook-tests が動き、警告だけが残る。
- R11: `changes` のステップには、PR の run でも `GH_TOKEN`（`actions: read`）を渡す。PR の run では API を呼ばないが、同じジョブの中では元々使えるトークンで、権限はこのリポジトリの Actions の読み取りだけ。push のときだけ渡す式にしても守りは増えないので、そうしない（2026-11-28、同上）。

<a name="cost"></a>

## 費用の見込み

Issue の測定（1 回あたり Linux 2.83 分・macOS 3.33 分、run が月 272 回）と単価（Linux 0.006 ドル/分・macOS 0.062 ドル/分）で、非公開のリポジトリの料金として数えた。`changes` は 1 分に切り上げる。

| | 今 | この変更の後 |
| --- | --- | --- |
| `checks`（Linux） | 4.62 ドル | 4.62 ドル |
| `changes`（Linux） | なし | 1.63 ドル |
| `hook-tests`（macOS） | 56.16 ドル | 14.04 ドル |
| 合計（1 か月） | 約 61 ドル | 約 20 ドル |

- 減る額は月約 40 ドル（約 67%）。macOS のジョブだけなら 75% 減る。
- macOS のジョブが動く割合（25%）は、直近 60 件のマージで数えた。PR の run は push のたびに動くので、関係するファイルを変える PR ほど push が多ければ、割合は上がる。35% なら合計は約 26 ドル（57% 減）、50% なら約 34 ドル（44% 減）。マージの後に、実際の run で数え直せる。
- 公開のリポジトリでは料金はかからない。macOS のランナーを待つ回数が、同じ割合で減る。

<a name="cost-followups"></a>

### ほかに費用を減らす案（この作業の範囲外）

KAD-39 で、確かめる範囲を減らさない 2 つ（macOS のジョブを 2 分以内にする、`test-check-repo.py` を速くする）を先に試し、実際の割合で数え直してから、main への push の CI をやめるかを決める。

2026-11-28 の 2 回の run（`46131901228`・`46131650793`）のステップの時間を見て挙げた。額は、この変更の後の約 20 ドルからの差の見込み。

| 案 | 減る額（月） | 失うもの・注意 |
| --- | --- | --- |
| リポジトリを公開のままにする（KAD-34 の判断） | 全額 | 非公開にする理由が残る |
| main への push の CI をやめ、PR だけで動かす | 約 9.5 ドル | ruleset の strict が false なので、マージした結果そのものは確かめなくなる。並行する PR の組み合わせの壊れ方に、次の PR まで気づかない |
| macOS のジョブを 2 分以内にする（3 つのテストの群をジョブの中で並行に動かす） | 約 5.6 ドル | 今は 175〜185 秒で、切り上げで 3〜4 分になる。ログが混ざらないよう、群ごとにファイルに書いて後で出す手間が要る |
| `test-check-repo.py`（123〜137 秒）を速くし、`checks` を 1〜2 分にする | 約 1.4〜3.0 ドル | 遅い理由はまだ調べていない |
| 自分の Mac を self-hosted runner にする | 約 14 ドル | 推奨しない。PR のコード（Claude が書いたものも）が sandbox の外の手元の Mac で動く。公開のあいだは、fork の PR のコードも動きうる |

- 組み合わせの例: main への push をやめ、macOS のジョブを 2 分にすると、約 7.8 ドル。macOS のジョブを 2 分、`checks` を 1 分にするだけ（main への push は残す）だと約 11.7 ドルで、枠すれすれになる。
- 予算の上限（spending limit）を 0 ドルにすると、料金はかからないが、枠を使い切った時点で CI が動かず、必須のチェックがマージを止める。減らす案ではなく、超えたときの守り。

<a name="rollback"></a>

## ロールバック

マージコミットを `git revert -m 1` で打ち消す PR を作る。`ci.yaml` が元に戻り、`hook-tests` は毎回動く。ruleset は変えないので、戻すのはワークフローだけで済む。
