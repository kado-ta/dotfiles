---
status: in-progress
created: 2026-11-26
---

# 試験記録: 参考にした dotfiles の規則の取り込み

関連: [plan](plan.md)

<a name="checks"></a>

## 1. 手元の確認

2026-11-26 に、`/review` の指摘を直した後の HEAD（cf894e3）で実行した。plan の [4 章](plan.md#verification) の確認に、`SKILL_ROUTING.md` を読む `skills-check.py` を足した。

| 確かめること | コマンド | 結果 |
| --- | --- | --- |
| `claude/CLAUDE.md` の実効行数 | plan の 4 章のコマンド | 79（80 以内） |
| リポジトリの検査 | `python3 -B .github/scripts/check-repo.py` | 16 項目すべて PASS |
| 検査のテスト | `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| シェルスクリプト | `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | 終了コード 0、出力なし |
| GitHub Actions | `actionlint`、`zizmor --offline .` | 終了コード 0。zizmor は `No findings to report.` |
| スキルの文書の照合 | `/usr/bin/python3 -B claude/scripts/skills-check.py check` | 終了コード 1、2 件の違い。どちらもこの差分の外（[3 章](#out-of-scope)） |

`skills-check.py` は、同じ日の修正前（08341d8）には `RESULT: no differences` だった。その後、セッションの途中で個人スキル `pm-assist` が入った。

<a name="review"></a>

## 2. `/review` の結果

gstack の `/review` を 08341d8 に対して実行した。差分は 169 行で、Testing・Maintainability・Simplification の専門レビュワーと、Claude の敵対的レビューを動かした。Codex の受け持ちは、gstack の設定（`codex_reviews` が disabled）で動いていない。

| 出どころ | 指摘 | 対応 |
| --- | --- | --- |
| 自分の確認、敵対的レビュー | Verification の「応答が空」が、成功すると何も出さないコマンドまで障害として扱える | 直した（c4e8c28）。「出るはずの出力がない」に絞った |
| 敵対的レビュー | 空や壊れた応答の後に、状態を変える操作（`cc-safe-pr` など）を再実行できる | 直した（c4e8c28）。再実行の前に結果を確かめる |
| 敵対的レビュー | 「自分での実行」が、決まった手順（Codex の結果の貼り付けを頼む）とぶつかる | 直した（c4e8c28）。決まった手順に従う |
| Maintainability、敵対的レビュー | ターンの末尾の規則がサブエージェントの報告にも当たり、gstack の `/review` のように形式を決めた依頼が崩れる | 直した（cf894e3）。ユーザーに返すターンに絞り、サブエージェントの報告と、新しい情報のない待機中の発言を除いた |
| 敵対的レビュー | plan の事実の誤り 4 件（候補 1 と組み込みの指示の重なり、引用の出典、80 行の計算、試験記録の置き場所） | 直した（8bdf20b） |

文面を変える 3 件（c4e8c28 と cf894e3）は、ユーザーが 2026-11-26 に承認した。

直さなかった指摘と理由:

- 軽い質問のターンにも 3 つの欄が付く: 欄を置く対象はユーザーが決めた。待機中の発言だけは除いた。
- `codex/AGENTS.md` 148 行は、軽い指摘を挙げるよう積極的には求めていない: 決めた範囲（「重大な」を外す）のとおり。`codex review` で `~/.codex/AGENTS.md` が効くかは確かめていない。
- 1 行を長くして 80 行の目標を満たしている: 同じ節の既存の行を言い換えて行数を増やさない、とユーザーが指示した。
- challenge で全件を求めると、指摘の量が増える: ユーザーが決めた。

gstack の手順は、修正の後にもう一度レビューして差分が変わらないこと（収束）を確かめる。ここでは `SKILL_ROUTING.md` の Exit criteria（指摘への対応が決まったら終える）に従い、2 回目のレビューはしていない。gstack の記録では `converged: false`。

<a name="out-of-scope"></a>

## 3. 範囲外で見つけたこと

- `skills-check.py` の 2 件の違いは、個人スキル `pm-assist` がスナップショットと `SKILL_INVENTORY.md` にないこと。このブランチはスキルのファイルもスナップショットも変えていない。`/sync-skill-docs` で合わせる。

<a name="ci"></a>

## 4. CI

PR を作った後に追記する。
