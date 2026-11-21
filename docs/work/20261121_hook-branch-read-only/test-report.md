---
status: done
created: 2026-11-21
---

# protect-main-branch の表示だけの git branch: 試験記録

<a name="related"></a>
## 関連

- [plan](plan.md)

<a name="verification"></a>
## 検証

2026-11-21、[D10](plan.md#decision-first-command) の修正の後に実行した。フックのテストは、`$TMPDIR` を cwd にして macOS の `/bin/bash` 3.2 で実行した。

| コマンド | 結果 |
| --- | --- |
| `bash claude/hooks/tests/test-protect-main-branch.sh` | 131 件成功。修正の各段で、足したテストが修正の前に失敗することを確かめた（4 件・4 件・5 件・3 件・5 件・2 件・5 件） |
| ほかのフックのテスト 5 本（validate-command、ask-gh-pr-write、gh-read-token、guard-additional-dirs、guard-playwright-mcp） | すべて成功（29・66・24・17・49 件） |
| `python3 -B .github/scripts/test-check-repo.py` | OK（83 件） |
| shellcheck（`-S warning`）、actionlint、`git diff --check`、`/bin/bash -n` | 指摘なし |
| `python3 -B .github/scripts/check-repo.py` | 今回のファイルでは失敗なし。別の作業の未追跡の文書（`docs/work/20261121_claude-clones/`）で、`local-paths` と `markdown-links` が失敗する |

<a name="hook-probes"></a>
## フックへの直接の入力

`feature/x` の一時リポジトリを cwd にした JSON を、最終のフックに与えた。

| 入力 | 終了コード |
| --- | --- |
| `git branch --show-current && git commit -m x` | 0 |
| `git branch -m main && git commit -m x` | 2 |
| `git branch --show-current \`＋改行＋`-m main && git commit -m x` | 2 |
| `` echo `git branch --show-current` && git commit -m x `` | 2（変更前と同じ） |

`/review` の攻撃者視点のレビューと Codex のレビューで挙がった入力は、変更前と最終のフックの両方に与えた。変更前は 2 のものは、最終でもすべて 2 になった。`git --git-dir .git branch -m main` と `\git branch -m main` は、変更前も最終も 0（[plan の残るリスク](plan.md#residual-risks)）。

`x<記号>y ; git branch -v && git commit -m x` の形で、記号を 1 文字ずつ試した。判定に入れた `'`・`"`・`\`・`$`・`` ` ``・`(`・`)`・`<`・`{`・`}`・`*`・`?`・`[`・`^`・`#` は 2、入れていない `~`・`=`・`%`・`!`・`]` は 0 になった。

<a name="codex-review"></a>
## Codex のレビュー

<a name="codex-review-1"></a>
### 1 回目（`codex review`）

2026-11-21 に、あなたが通常の端末で `codex review --base origin/main -c 'sandbox_mode="read-only"' -c skills.include_instructions=false` を実行した（`0353087`）。結果は Codex の記録から読んだ。

- 結果: 指摘なし（"patch is correct"、confidence 0.86）。Codex は `bash -n`・ShellCheck・`git diff --check` を実行し、成功した。読み取り専用のため、一時リポジトリを作る回帰テストは実行していない。`check-repo.py` は、差分にない未追跡の文書で失敗したと報告した（手元の結果と同じ）。
- 対応: 指摘がないので、なし。

<a name="codex-review-2"></a>
### 2 回目（challenge）

2026-11-21 に、あなたが通常の端末で `codex exec - -s read-only -c skills.include_instructions=false` を、攻撃者の視点で迂回を探すプロンプト（gstack の challenge の既定の文を下敷きにしたもの）で実行した。

- 結果: OpenAI 側の判定で拒否され、レビューは行われなかった（`ERROR: This content was flagged for possible cybersecurity risk.`、49,054 トークンを消費）。Codex の記録には最終メッセージがないので、端末の出力を貼ってもらった。
- 対応: 上限の 5 回に数える。

<a name="codex-review-3"></a>
### 3 回目（challenge、書き直したプロンプト）

2026-11-21 に、あなたが通常の端末で、同じコマンドを書き直したプロンプトで実行した（`0353087`）。攻撃者の視点という頼み方をやめ、新旧 2 版の後退を調べる形にした。結果は Codex の記録から読んだ。

- 結果: 後退が 2 種類（`VERDICT: FINDINGS`）。Codex の読み取り専用の環境では、ヒアストリングの一時ファイルを作れずに新旧とも 2 になるので、`<<<` をプロセス置換に置き換えた写しで確かめたとのこと。
  1. ブレース展開を使う関数で git を上書きする形（High、Blocks: yes）
  2. `-C`・`-c` の値のブレース展開（Medium、Blocks: yes）
- 対応: どちらも採用した。手元でも、変更前は 2、変更後は 0 になることを確かめた。同じ理由でグロブと extended_glob の記号も足した（[plan の D9](plan.md#decision-expansion)、`f9c1da5`）。

<a name="codex-review-4"></a>
### 4 回目（challenge、書き直したプロンプト）

2026-11-21 に、あなたが通常の端末で、3 回目と同じプロンプト（D9 のことを書き足したもの）で実行した（`8ec4de2`）。結果は Codex の記録から読んだ。

- 結果: 後退が 2 種類（`VERDICT: FINDINGS`）。3 回目と同じく、ヒアストリングをプロセス置換に置き換えた写しで確かめたとのこと。
  1. zsh の短い関数定義 `function git; /usr/bin/git branch -M main; git branch; unfunction git; git commit -m x`（High、Blocks: yes）。括弧・波括弧・引用符を使わないので、D6・D9 の記号に当たらない。
  2. 同じコマンドの中で `alias -g -- -v=-m --show-current=main` を定義し、次の行で `git branch -v --show-current` とする形（Medium、Blocks: no）。zsh が行ごとに読む場合だけ効き、`zsh -c` で一度に渡すと効かない（Codex の実測。`/review` のサブエージェントも、Bash ツールの実行方法では効かないと測った）。
- 手元でも、どちらもフックの判定では変更前は 2、変更後は 0 になることを確かめた。
- 対応: どちらも採用した。記号の判定に語を足すのではなく、表示だけとみなす位置を、呼び出しの先頭か `cd <path> &&` の直後に絞った（[plan の D10](plan.md#decision-first-command)）。2 つ目は Bash ツールの実行方法では効かない見込みだが、同じ変更で止まる。
