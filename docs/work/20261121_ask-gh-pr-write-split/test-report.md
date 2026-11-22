---
status: done
created: 2026-11-21
---

<a name="title"></a>

# ask-gh-pr-write.sh の正規化の高速化 試験記録

関連: [PR #59 の試験記録](../20261121_shared-tree-git-hook/test-report.md)（同じ正規化を `ask-shared-tree-git.sh` で split と join に替えた作業）

`claude/hooks/ask-gh-pr-write.sh` の、行継続と引用符を除く正規化を、jq の `gsub` から `split` と `join` に替えた。式は `ask-shared-tree-git.sh` と同じにした。計測と検査は、Claude Code の sandbox の中で、worktree（`perf/ask-gh-pr-write-split`）のフックに対して行った。jq は 1.8.2（mise の installs のパス）、bash は `/bin/bash` 3.2。

<a name="automated"></a>

## 1. 自動のテストと検査

フックのテストは、書き込める cwd（`$TMPDIR`）から絶対パスで実行した。

| コマンド | 結果 |
| --- | --- |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | pass=131 fail=0 |
| `bash claude/hooks/tests/test-validate-command.sh` | pass=29 fail=0 |
| `bash claude/hooks/tests/test-ask-gh-pr-write.sh` | pass=69 fail=0（コメントを直した後にも実行して同じ） |
| `bash claude/hooks/tests/test-ask-shared-tree-git.sh` | pass=111 fail=0 |
| `bash claude/hooks/tests/test-gh-read-token.sh` | pass=24 fail=0 |
| `bash claude/hooks/tests/test-guard-additional-dirs.sh` | pass=17 fail=0 |
| `bash claude/hooks/tests/test-guard-playwright-mcp.sh` | pass=49 fail=0 |
| `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| `python3 -B .github/scripts/test-check-repo.py` | Ran 83 tests、OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 出力なし、終了コード 0 |
| `actionlint` | 出力なし、終了コード 0 |

`test-ask-gh-pr-write.sh` の fail closed のケース（読めない入力 5 件、壊れた jq、jq がない、grep が壊れている 2 件、パイプの入力側の失敗）は、すべて block のまま。入力側の失敗のテストが置き換える `printf '%s\n' "$COMMAND"` の行は変えていない。

<a name="speed"></a>

## 2. 速さ

フック単体を、`echo "a" ` を繰り返した入力で 3 回ずつ実行した（`time`、`TIMEFORMAT=%R`）。

| 入力 | 修正の前（`gsub`） | 修正の後（`split` と `join`） |
| --- | --- | --- |
| 3,000 回（27,000 バイト、引用符 6,000 個） | 0.348 / 0.371 / 0.378 s | 0.024 / 0.024 / 0.024 s |
| 15,000 回（135,000 バイト、引用符 30,000 個） | 8.548 / 8.174 / 7.672 s | 0.069 / 0.074 / 0.072 s |

テストの新しいケース（15,000 回、上限 3 s）の計測値は、修正の前が 8.010 s（FAIL）、修正の後が 0.117〜0.126 s。

<a name="gsub-scaling"></a>

### 2.1 gsub が遅くなる条件

修正の前の jq の式だけを、長さと引用符の数を分けて測った。引用符がなければ 135 KB でも速く、引用符の数が同じでも長さが倍になると時間が増える。時間は「一致の数 × 入力の長さ」に比例して伸びる見込み（4 点からの推定）。

| 入力 | バイト数 | 時間 |
| --- | --- | --- |
| 引用符 30,000 個 | 135,000 | 8.236 s |
| 引用符なし | 135,000 | 0.013 s |
| 引用符 15,000 個 | 67,500 | 2.141 s |
| 引用符 15,000 個と、引用符のない 67,500 バイト | 135,000 | 3.284 s |

<a name="join-scaling"></a>

### 2.2 join の伸び方（レビューで分かったこと）

`/review` の adversarial の指摘を受けて、`a"` を繰り返した入力で jq の式だけを測った。`join("")` も入力の長さの 2 乗で伸びる。各段を `add // ""` にすると線形になり、出力は 4 つの大きさすべてで `cmp` で一致した。

| 入力 | `join("")` | `add // ""` |
| --- | --- | --- |
| 135 KB | 0.074 s | 0.016 s |
| 500 KB | 0.631 s | 0.049 s |
| 1,000 KB | 1.970 s | 0.090 s |
| 2,000 KB | 7.197 s | 0.166 s |

サブエージェントの計測では、フック全体で 3 MB が 15.6 s、約 4 MB で 30 s の timeout を超える。式を変えるかどうかは [5 章](#review) のとおり、変えないことにした。

<a name="red-and-mutation"></a>

## 3. 先に失敗するテストと変異

新しいテストを足した時点で、修正の前の実装に対して実行し、`FAIL longer command took 8.010s`（pass=67 fail=1）を確かめてから修正した。

修正の後、フックの写しの正規化を壊して、テストが FAIL に転じることを確かめた。

| 変異 | FAIL になったケース |
| --- | --- |
| 式を `gsub` に戻す | longer command（8.451 s） |
| 行継続の `split` と `join` を除く | line continuation の 3 件 |
| 二重引用符の `split` と `join` を除く | quoted command、quoted subcommand、quotes inside a word |
| 単引用符の `split` と `join` を除く | single quotes inside a word、known miss: env -S |
| `split("\\\n")` を `split("\\n")` にする | line continuation の 3 件 |

単引用符の変異は、初めは「known miss: env -S」が ask に変わることでしか検出できなかった。そのため「single quotes inside a word」（`gh pr mer''ge 1` が ask になる）を足した。

<a name="equivalence"></a>

## 4. 出力の同一性

修正の前と後の jq の式に同じ入力を与え、出力を比べた。

- ランダムな 50,000 件と境界の 9 件（引用符、バックスラッシュ、改行、`\`＋改行、空白、マルチバイト文字を含む、長さ 0〜40）で、不一致は 0 件。
- 長い入力 2 件（`echo "a" ` の 15,000 回と、`echo 'a' \`＋改行の 15,000 回）で、`-r` の出力がバイト単位で同じ（105,001 バイト）。
- adversarial のサブエージェントも、境界の 8 件で、jq 1.8.2 と `/usr/bin/jq` 1.7.1-apple の両方で一致を確かめた。

<a name="review"></a>

## 5. レビュー（`/review`）

gstack の `/review` で、ブランチの差分（21 行）をレビューした。差分が 50 行未満なので、specialist は起動されなかった。

| 指摘 | 出どころ | 対応 |
| --- | --- | --- |
| `join("")` も長さの 2 乗で伸び、約 4 MB で timeout する | adversarial（Claude のサブエージェント） | 自分でも計測して再現した（[2.2](#join-scaling)）。式は依頼の指定どおりで `ask-shared-tree-git.sh` と同じにしたいので、変えないことをユーザーが選んだ。コメントに伸び方と上限を書いた |
| 計時テストは引用符の多い形しか測らず、`join` への逆戻りを検出しない | adversarial | `join` を使う方針なので対象外。`gsub` への逆戻りは検出できる（[3 章](#red-and-mutation)） |
| jq 1.6 以前で確かめていない | adversarial | 手元にない。1.8.2 と 1.7.1-apple では確かめた。CI の jq の版は固定していない |

探索的な QA（smoke）として、フックを 3 回実行した。`gh pr mer''ge 1` は exit 0 で ask になり、135 KB のコマンドは exit 0・出力なしで 76 ms で終わり、command が null の入力は exit 2 になった。

Codex のレビューは実行していない（規則により、人間の通常のターミナルで実行する）。

<a name="residual-risks"></a>

## 6. 残るリスクとロールバック

- 約 4 MB 以上のコマンドでは、`join` のためにフックが 30 s の timeout を超え、その Bash の呼び出しがブロックされる（fail closed なので、検出漏れにはならない）。macOS の ARG_MAX は 1 MB なので、それより大きいコマンドはそもそも実行できない見込み。ただし、Claude Code がコマンドを argv で渡すかは確かめていない。両方のフックを `add // ""` に替えるなら、別の作業にする。
- jq 1.6 以前での出力の一致は確かめていない。
- ロールバック: このフックは `~/.claude/hooks` から `~/dotfiles` の本体を参照し、呼び出しのたびに読み込まれる。壊れて Bash が止まったときは、Claude からは直せないので、人間が通常のターミナルで `git -C ~/dotfiles restore --source=27dd738 claude/hooks/ask-gh-pr-write.sh` を実行すると、すぐに前の版に戻る。その後、revert の PR を作る。

<a name="changes-from-request"></a>

## 7. 依頼からの変更

- テストに「single quotes inside a word」を足した（[3 章](#red-and-mutation) の変異の結果による）。
- コメントに、`join` の伸び方と上限の 1 行を足した（[5 章](#review) の対応）。
- 依頼にあったコメントの「引用符の数に対して 2 乗」は、計測（[2.1](#gsub-scaling)）に合わせて「一致の数と入力の長さの積」と書いた。
