#!/bin/bash
# Playwright MCP のツールの呼び出しで、ローカルのファイルを指す filename・paths 引数を止める。
# filename の相対パスはワークスペースのルート（プロジェクト）を基準に解決され、その中のどこにでも書ける
# （.claude/settings.json・.git/config など）。browser_evaluate は戻り値を JSON で書くので、任意の JSON も書ける。
# paths は、そのファイルをページに渡す（browser_drop は既定で有効。browser_file_upload は settings.json でも deny）。
# MCP サーバーは sandbox の外で動くので、sandbox の denyWrite・denyRead も Edit・Write の規則も効かない。
# filename がなければ、スクリーンショットなどは --output-dir に自動の名前で保存され、スナップショットや
# 評価の結果は応答で返る。browser_drop は data（テキスト）なら使える。
# url 引数が cc-crit の Crit のポート（47810〜47829）を指す呼び出しも止める。ブラウザは sandbox の外で localhost に
# 届くので、開けばモデルが Finish Review を押して人間の承認を偽造できる。移す前の範囲の 47800〜47809 も止める。
# このフック・入れた cc-crit・MCP の定義は更新の時期がずれるので、古い cc-crit の Crit も開かせないため
# （docs/work/20261124_cc-crit-port-range/plan.md）。URL は解析せず、TAB・LF・CR を取り除いて
# （WHATWG の URL の解析器が取り除くため）、文字列に :47800〜:47829（ポートの先頭のゼロも含む）があれば止める。
# JS やリンクでの移動は、定義の --blocked-origins が、正規化された後の URL で止める。
# url 引数が file: で始まる呼び出しも止める。Playwright MCP は file: を拒否するが、Node が URL を解析できる
# ときだけなので（file://localhost:/… などは素通りする）、ブラウザ経由で sandbox の denyRead の外のファイルを
# 読めないよう、ここでも止める。WHATWG の解析器と同じく、先頭の制御文字・空白と TAB・LF・CR を取り除いて見る。
# 経緯は docs/work/20261118_playwright-mcp/plan.md の D1。
# 入力を解釈できないときも止める（fail closed）。macOS の /bin/bash 3.2 と /usr/bin/python3 で動かす。
set -u

# 入力は Python が最後まで読む。読まずに終わると、パイプの容量を超える入力で Claude Code 側の書き込みが失敗する。
# 理由は固定の文だけにする。引数の値はページの影響を受けたモデルが決めうるので、Claude に渡さない。
/usr/bin/python3 -I -B -c '
import json
import re
import sys

try:
    tool_input = json.load(sys.stdin)["tool_input"]
except Exception:
    tool_input = None
if not isinstance(tool_input, dict):
    print("Blocked: the Playwright MCP tool input could not be checked.", file=sys.stderr)
    sys.exit(2)
if "filename" in tool_input:
    print("Blocked: Playwright MCP calls must not pass filename, because the server writes it relative to the project root outside the sandbox. Omit filename: screenshots are saved to the output directory with automatic names, and snapshots and evaluation results are returned in the response.", file=sys.stderr)
    sys.exit(2)
if "paths" in tool_input:
    print("Blocked: Playwright MCP calls must not pass paths, because the server reads those local files outside the sandbox and hands them to the page. To test drag and drop, drop text with data instead.", file=sys.stderr)
    sys.exit(2)
url = tool_input.get("url")
url = re.sub(r"[\t\n\r]", "", url).lstrip("".join(map(chr, range(0x21)))) if isinstance(url, str) else ""
if re.match(r"file:", url, re.IGNORECASE):
    print("Blocked: Playwright MCP must not open file: URLs, because the browser runs outside the sandbox and could read files the sandbox protects.", file=sys.stderr)
    sys.exit(2)
if re.search(r":0*478[0-2][0-9](?![0-9])", url):
    print("Blocked: Playwright MCP must not open ports 47800-47829, where Crit waits for the human review. Approvals in Crit must come from the human.", file=sys.stderr)
    sys.exit(2)
'
status=$?
[ "$status" -eq 0 ] && exit 0
# Python が起動できなかったときなど。残りの入力を読み捨ててから止める。
if [ "$status" -ne 2 ]; then
  cat >/dev/null
  echo "Blocked: the Playwright MCP tool input could not be checked (python exited with ${status})." >&2
fi
exit 2
