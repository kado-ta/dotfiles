---
status: done
created: 2026-11-24
---

# modern-web-guidance 1.0.2 の取り込みと npm 12 への対応の試験記録

関連: [前の作業の試験記録](../20261123_modern-web-guidance/test-report.md)

<a name="environment"></a>

## 環境

2026-11-24 に確認した。

| 項目 | 版 |
| --- | --- |
| `modern-web-guidance`（npm） | 1.0.1 → 1.0.2（`skill-version` 2026_11_10-47b4c80e → 2026_11_16-268fb9ea） |
| SkillSpector | 2.13.6 |
| Python | 3.15.2（mise）、3.9.6（`/usr/bin/python3`） |
| Node.js | 26.13.1（mise）、npm 12.2.3 |

<a name="cause"></a>

## 不具合と原因

`update-modern-web-guidance.py --apply` が「npm pack の出力を読めない」で失敗した（何も書いていない）。

npm 12.2.3 の `npm pack --json` は、配列ではなく、パッケージ名をキーにしたオブジェクト（`{"modern-web-guidance": {"filename": …}}`）を返す。手元の npm のソースで確かめた。`lib/utils/tar.js` の `logTar` が `{ [tar.name]: tarball }` を出力のバッファに積み、`lib/utils/display.js` がそれをオブジェクトとして結合する。前の作業の時点の npm 11.20.0 は配列を返していた。Node は 26.13.1 のままで、npm だけが上がっていた。

スクリプトは、配列ならその先頭の要素から、オブジェクトならパッケージ名のキーから `filename` を読むようにした（`ee09a57`）。

<a name="results"></a>

## 手順ごとの結果

| # | 確認 | 結果 | 確かめ方と観測 |
| --- | --- | --- | --- |
| 1 | 再現テストが先に失敗する | 合格 | テストの偽の npm を npm 12 の形にすると、修正前のスクリプトで、ユーザーの環境と同じ「npm pack の出力を読めない」で失敗した |
| 2 | 更新スクリプトのテストが通る | 合格 | `test-update-modern-web-guidance.py` の 71 件が、mise の Python 3.15.2 と `/usr/bin/python3` 3.9.6 の両方で通った。npm 11 の形を確かめるテストを足した |
| 3 | 本物の npm 12 で動く | 合格 | 人が通常のターミナルで `--out /tmp/mwg-1.0.2 --latest` を実行し、1.0.2 のスキルが書けた（sandbox の中の `npm pack` は権限で拒否された） |
| 4 | 1.0.1 からの差分 | 合格 | `chrome-extensions` は `diff -r` で差分がない。`modern-web-guidance` の SKILL.md は 3 か所だけ（生成元の版、`--skill-version`、分野の例への `js` の追加） |
| 5 | `--apply` | 合格 | 人が通常のターミナルで実行した。変わったのは SKILL.md と `mise/mise_config.toml` の固定版だけで、手順 3 の生成物と `diff -r` で一致した |
| 6 | リポジトリの検査 | 合格 | `check-repo.py` の 13 項目すべてが通った（修正の後と取り込みの後の 2 回） |

<a name="skillspector"></a>

## skillspector の指摘

`skillspector scan claude/skills/chrome-extensions --no-llm` は、score 56・HIGH・DO_NOT_INSTALL・6 件を返した。`modern-web-guidance` は 0 件（LOW・SAFE）。`chrome-extensions` は 1.0.1 から変わっていないので、前の取り込みのときも同じ判定だった見込み（前の試験記録には結果がない）。

6 件とも、ドキュメントの文面とコード例に反応した誤検知と判断した。根拠がはっきりしているので、LLM での検査（`SKILLSPECTOR_PROVIDER=claude_cli`）は使っていない。次の更新では、同じ `match_fingerprint` の指摘は確かめ直さず、増えた指摘だけを見る。

| ID | 重大度 | 場所 | 中身と判断 | `match_fingerprint` |
| --- | --- | --- | --- | --- |
| AE1 | HIGH | `SKILL.md:486`（`references/extensions/omnibox.md` を指す行） | 参照先を最後まで解析できなかった。`omnibox.md:42` の JS のテンプレートリテラル `${encodeURIComponent(text)}` を、シェルの展開として読めなかったため。skillspector 自身も、解析しきれないことは悪意の証拠ではないとしている | `7d839e13f77baca74f54e0496e491240fc23127286d7d5d3fe95c71a6dc3936e` |
| PE3 | HIGH | `references/webstore/review-checklist.md:119` | `zip -x ".env"`。拡張機能の zip から `.env` を除く手順で、読んではいない | `933e7e6dda63d615cb9ac0846682521855cd79c351e84f3fa87d934c18b752db` |
| E1 | MEDIUM | `references/extensions/api-calling.md:10`・`:33`（2 件） | CORS の説明の例の `api.openweathermap.org` | `051d07189350b8008346d950151378c60613dc4d69da905b9d9e6e15e1c266ff` |
| EA1 | MEDIUM | `references/extensions/csp-sandbox.md:38` | 「execute arbitrary code」という文。ユーザーのコードは sandbox のページで隔離して動かす、という説明 | `bd2dc2dc849f8a256d1fa8549a57b86bd4ac8644140b6892116b8b7622ddcc56` |
| E1 | MEDIUM | `references/extensions/permissions.md:10` | manifest の例の `https://api.example.com/*` | `88f1946300c8ae45d5ea7e81f2b6d4309a13082e928b6f7d1215d273945a1431` |

解析は 26 個のうち 24 個が最後まで済み、2 個が部分的だった。解析が止まった 2 か所（`SKILL.md` の 248〜272 行のタブ録画の JS の例と、上の `omnibox.md:42`）は、手で読んで問題がないことを確かめた。参照先が見つからないという記録が 48 件あるが、コード例の中のファイル名（`manifest.json`・`icon.png`・`sandbox.html` など）をスキルのファイルとして探したもの。

<a name="unverified"></a>

## 確かめていないこと

- 1.0.2 の CLI は入れていない。PR のマージの後に、人が通常のターミナルで `mise install` を実行する。CLI と SKILL.md の `--skill-version` の組み合わせは、そのときに確かめる。
- 指摘の箇所と解析が止まった箇所のほかは、`chrome-extensions` の 24 ファイルを読み直していない。
- sandbox の中では skillspector が起動しない。denyRead の `**/credentials` が、依存する Anthropic SDK の `site-packages/anthropic/lib/credentials` に当たるため（`ls` が `Operation not permitted` で失敗する）。前の作業の [plan.md](../20261123_modern-web-guidance/plan.md) の比較表は、`--no-llm` は sandbox の中でも動くとしていて、今の状態と食い違う。更新スクリプトの検査は sandbox の外で動くので、影響はない。上の指摘は、人が通常のターミナルで JSON に書き出したものを読んだ。
