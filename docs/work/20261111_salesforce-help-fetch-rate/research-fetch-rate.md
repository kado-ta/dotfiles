---
status: done
created: 2026-11-11
---

# Salesforce Help の WebFetch 取得成功率と、本文を読む手段の選定

<a name="result"></a>
## 結果

WebFetch で本文を読めたのは 20 件中 5 件（25%）だった。本文がないのに成功と判定した例はなかった。

本文を読めないときの手段は、現状どおり「ユーザーが browse のコマンドを実行する」（A）を採用した。Ghostty に加えて、Claude Code のプロンプトの `!` でも実行してもらえるように Skill を変更した。

<a name="method"></a>
## 測定方法

- 期間: 2026-11-09〜11。Claude Code 2.1.311 の WebFetch を、1 件ずつ直列で実行した。
- 対象: `https://help.salesforce.com/robots.txt` のサイトマップから 10 製品を選び、固定シード 20261109 の乱数で、製品ごとに子サイトマップ 1 ページと、その逐語部分の `<loc>` から 2 件を選んだ。
- URL: `<loc>` には `language` がないので `en_US` を補い、`id`、`language`、（`release`、）`type` の順に整えた。`release=264` は外していない。
- 判定: Skill `salesforce-help` の判定表に従った。目次だけのときは、ヘッダに `truncated` が出なくなるまで `offset` で読み進めた。

<a name="measurements"></a>
## 測定結果

| 製品 | id | 結果 | WebFetch 回数 | 全体の字数 |
| --- | --- | --- | --- | --- |
| platform | platform.automate_flow_ref_third_party_freshservice.htm | TOC_ONLY | 3 | 110,329 |
| platform | platform.automate_flow_ref_third_party_front.htm | TOC_ONLY | 3 | 110,764 |
| sales | sales.hvs_considerations_sales_engagements_data_360.htm | TOC_ONLY | 3 | 107,017 |
| sales | sales.hvs_engagement_work_queue.htm | TOC_ONLY | 3 | 108,220 |
| service | service.voice_health_check_policy.htm | TOC_ONLY | 3 | 109,701 |
| service | service.voice_flex_custom_username.htm | TOC_ONLY | 3 | 110,119 |
| mktg | mktg.mc_ceb_einstein_genai_in_content_builder.htm | SUCCESS | 1 | 26,604 |
| mktg | mktg.mc_ceb_create_in_app.htm | SUCCESS | 1 | 30,974 |
| commerce | commerce.rt_adv_config_data_feeds_manage_schedule.htm | TOC_ONLY | 3 | 109,002 |
| commerce | commerce.rt_adv_config_3p_int_finance_hipay.htm | TOC_ONLY | 3 | 108,924 |
| experience | experience.support_context_aware_quick_chat.htm | TOC_ONLY | 3 | 106,979 |
| experience | experience.support_context_aware_quick_chat_config.htm | TOC_ONLY | 3 | 106,524 |
| analytics | analytics.c360_a_sl_bin_create.htm | SUCCESS | 1 | 32,037 |
| analytics | analytics.c360_a_sl_biz_preferences_set.htm | SUCCESS | 1 | 31,056 |
| data | data.pi_manage_user_management_groups_view.htm | SUCCESS | 1 | 24,285 |
| data | data.pi_monitor_manage_dashboard_default_log.htm | SHELL（2,352 字） | 1 | 2,352 |
| ai | ai.agent_ref_create_bulk_update_for_sales_agreement_metrics.htm | TOC_ONLY | 3 | 108,032 |
| ai | ai.agent_ref_comms_get_group_suggestions.htm | TOC_ONLY | 3 | 107,773 |
| release-notes | release-notes.rn_data_build.htm（`release=264`） | SHELL | 1 | 146 |
| release-notes | release-notes.rn_data_govern_secure.htm（`release=264`） | SHELL | 1 | 146 |

- SUCCESS: 1 回目で見出しと本文の段落を読めた。
- TOC_ONLY: 最後まで目次だけで、`[Content truncated due to length...]` で終わった。
- SHELL: `Loading` / `Sorry to interrupt` / `CSS Error` などだけで、本文がなかった。

<a name="observations"></a>
## 観測したこと

- 成功した記事は全体が 24,285〜32,037 字、TOC_ONLY の記事は 106,524〜110,764 字だった。結果は記事ではなくガイドの目次の大きさで決まると考えられる（推測。目次の大きさは直接は測っていない）。
- `release-notes` は 2 件とも 146 字のシェルだった。
- `data.pi_monitor_manage_dashboard_default_log.htm` は、シェルに OneTrust の Cookie 同意バナーが付いて 2,352 字になった。2026-11-11 に再取得しても同じだった。
- TOC_ONLY の途中の回のヘッダは `truncated to the first N from character M`、最後の回は `shown from character M` で、`truncated` は出なかった。判定表の停止条件は機能する。
- 判定表の「全体が 150 字前後」は 2,352 字のシェルに当てはまらない。ただし、変更前の Skill を使うエージェントにこの結果を判定させるテストは 3 回とも正しく「本文を読めない」と判定したため、判定表は変えていない。
- browse で描画した `sf.flow_builder.htm` の `document.body.innerText` は 5,976 字だった（2026-11-09、Ghostty で実行）。描画後の本文には目次が入らないので、`!` で出力を会話に入れても大きくならない。
- 2026-11-11 に同じ記事を Claude Code 2.1.311 の `!` で描画した。Chromium は起動し、`document.body.innerText` は 6,004 字だった。

<a name="decision"></a>
## 判断

本文を読めないときは、A（ユーザーが browse のコマンドを実行する）を続ける。他の案は次の理由で採用しなかった。

| 案 | 内容 | 採用しなかった理由 |
| --- | --- | --- |
| B | browse を `sandbox.excludedCommands` で Sandbox の外で動かす | browse の `skill` サブコマンドは `bun run` で任意のスクリプトを実行するので、ワイルドカードで除外すると Sandbox の外でコードを動かせる。完全一致のラッパーにしても、Chromium の脆弱性とラッパーの不具合が残る |
| Playwright 案 1 | Claude の Sandbox の中で Playwright を直接動かす（`chromiumSandbox: false`） | Skill の「Bash から本文を取得しない」の例外が必要。動作も確認していない。境界は変わらないので、必要になったら最初に試す |
| Playwright 案 2 | root 所有の専用ラッパーを Sandbox の外で動かす | 守るべき条件（URL の検証、名前解決の固定、出力の上限など）が多く、保守が最も重い |
| Playwright MCP | MCP サーバーとして Claude にブラウザを操作させる | MCP サーバーは Sandbox の外でユーザーの全権限で動く。README 自身が "Playwright MCP is not a security boundary." と書き、`--allowed-origins` も境界ではない。`browser_run_code_unsafe` は RCE 相当 |

`!` のコマンドは、公式ドキュメントでは次のとおり Sandbox の外で動く。

- Sandboxing: "a command you enter at the `!` shell-mode prompt runs unsandboxed in most sessions."
- 例外は background session と、`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` を設定した Linux のセッション。v2.1.260 より前は、strict sandbox mode（`allowUnsandboxedCommands: false`）のとき `!` も Sandbox の中で動いた。

<a name="open-items"></a>
## 未解決

- background session では `!` も Sandbox の中で動くので、browse の Chromium は起動しないと考えられる（推測。未確認）。
- 判定表の「全体が 150 字前後」の文面は、2,352 字のシェルに合わせて直していない。
- `!` の出力に文字数の上限があるかは、ドキュメントに記載がない。

<a name="related"></a>
## 関連

- [前の作業: Salesforce Help の参照手段の計画と結果](../20261109_salesforce-help/plan.md)
- [Skill: salesforce-help](../../../claude/skills/salesforce-help/SKILL.md)
- [Claude Code: Sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Claude Code: Interactive mode](https://code.claude.com/docs/en/interactive-mode)
