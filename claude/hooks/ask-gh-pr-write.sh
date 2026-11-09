#!/bin/bash
# gh の PR 書き込みと API 呼び出しの表記ゆれを、auto mode でも人間の承認に回す。
# 別の形で呼ばれれば素通りするので、セキュリティ境界ではない。誤検知は確認が増えるだけ。
set -euo pipefail
# 途中の失敗は exit 2 にそろえ、onFailure の設定に依存せずブロックする。
trap 'exit 2' ERR
# 行継続と引用符を除き、`gh pr \<改行> merge` や `"gh" pr merge` を同じ形にそろえる。
# bash の ${var//…} は引用符が多いと極端に遅く、長いコマンドがタイムアウトでブロックされるので jq で行う。
COMMAND=$(jq -er '.tool_input.command | strings | gsub("\\\\\n"; "") | gsub("[\"\\x27]"; "")') || {
  echo "Blocked: jq failed, so this command cannot be checked." >&2
  exit 2
}
OPT='([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*'
GH="(^|[^[:alnum:]_.-])gh${OPT}[[:space:]]+"
VERB='(create|new|edit|merge|close|ready|reopen|revert|update-branch|lock|unlock|review|comment)'
codes=(0 0)
# 入力側と照合側の両方の失敗を検出するために PIPESTATUS を使う。-q は入力側が SIGPIPE で失敗するので使わない。
printf '%s\n' "$COMMAND" | grep -E "${GH}(pr${OPT}[[:space:]]+${VERB}|api)([^[:alnum:]-]|\$)" >/dev/null || codes=("${PIPESTATUS[@]}")
[ "${codes[0]}" -eq 0 ] && [ "${codes[1]}" -le 1 ] || exit 2
if [ "${codes[1]}" -eq 0 ]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask",
          permissionDecisionReason: "gh の PR 書き込みは人間の承認が必要です"}}'
fi
