---
status: done
created: 2026-11-09
---

# Salesforce Help の参照手段の計画と結果

<a name="result"></a>
## 結果

Salesforce Help の本文を取得する専用 CLI は中止し、WebFetch の使い方と判定をまとめた Skill `salesforce-help` だけを導入した。

CLI は「HTML 全文を GET すれば本文を抽出できる」ことを前提にしていたが、実機検証でこの前提が成り立たなかった。

<a name="step0"></a>
## 実機検証（Step 0）

`https://help.salesforce.com/s/articleView?id=sf.flow_builder.htm&language=en_US&type=5` の結果を比較した。

| クライアント | User-Agent | Accept-Encoding | Accept | 結果 |
| --- | --- | --- | --- | --- |
| curl | `Claude-User (...)` | gzip | `text/markdown, text/html, */*` | 本文あり（HTML 2,972,720 字） |
| Python 標準ライブラリ | `sf-help-fetch/1 (...)` | identity | `text/html` | 本文なし |
| Python 標準ライブラリ | `sf-help-fetch/1 (...)` | gzip | `text/html` | 本文なし |
| Python 標準ライブラリ | `sf-help-fetch/1 (...)` | gzip | `text/markdown, text/html, */*` | 本文なし |
| Python 標準ライブラリ | `sf-help-fetch-bot/1 (...)` | gzip | `text/html` | 本文なし |

- Sandbox 内の Python 標準ライブラリから `help.salesforce.com` に届き、許可外の `example.com` は遮断された。
- 本文なしの応答は、JS でしか本文が出ない形の HTML と同じサイズ（gzip で 51,067 バイト）だった。
- `Claude-User` を名乗る方法は、User-Agent の偽装にあたるため採用しなかった。

<a name="decisions"></a>
## 判断

- 全文をローカルに保存しない（読んで理解できれば足りる）。
- User-Agent を偽装しない。
- `curl` / `wget` の deny を別の手段で迂回しない。
- 目次の大きいガイドの本文は、人間が Ghostty で headless Chromium を実行して取得する。

<a name="open-items"></a>
## 未解決

- User-Agent で応答が変わる理由（HTTP/2 と TLS の違いは除外できていない）
- `Accept-Encoding: identity` で一部の応答が `IncompleteRead` になった理由
- `release=` 付き URL の描画後の本文

<a name="related"></a>
## 関連

- [Skill: salesforce-help](../../../claude/skills/salesforce-help/SKILL.md)
