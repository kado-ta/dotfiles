#!/bin/bash
# 作業ツリーの状態を動かす git 操作の前に、同じ作業ツリーで別の Claude セッションが動いていれば、人間の確認に回す。
# 作業の衝突を防ぐ警告で、セキュリティ境界ではない。どんな失敗でも、何も出さずに 0 で終わる（fail open）。
# sandbox の外で、モデルが決めたコマンドの文字列を入力に動くので、git を実行せず、文字列を実行・評価しない。
set -uo pipefail

# コマンドの区切り（行頭・空白・&&・||・;・|・(・`）の後の git だけを見る。
SEP='(^|[[:space:];&|(`])'
# 語の終わり。
END='([[:space:];&|)`<>]|$)'
# git とサブコマンドの間のオプション（-C <path>・-c <k=v>・--no-pager など）。
OPT='([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*'
# 同じコマンドの中の引数。
ARGS='([[:space:]]+[^[:space:];&|)`]+)*'
GIT="${SEP}git${OPT}[[:space:]]+"
# 対象は design 5.2 の表がすべて。
TARGET="${GIT}(switch|checkout|rebase|merge|pull|reset|bisect|restore|clean)${END}"
# stash は list・show を除く。サブコマンドなし（オプションだけも含む）と、そのほかのサブコマンド。
TARGET+="|${GIT}stash([[:space:]]*([;&|)\`<>]|\$)|[[:space:]]+(-|(push|pop|apply|drop|clear|save|branch|create|store)${END}))"
# add は -A・--all・-u・--update・.・:/（-vA のようにまとめた形も）。
TARGET+="|${GIT}add${ARGS}[[:space:]]+(--all|--update|\\.|:/|-[[:alnum:]]*[Au][[:alnum:]]*)${END}"
# commit は -a・--all（-am のようにまとめた形も）。
TARGET+="|${GIT}commit${ARGS}[[:space:]]+(--all|-[[:alnum:]]*a[[:alnum:]]*)${END}"
TARGET+="|${SEP}gh${OPT}[[:space:]]+pr${OPT}[[:space:]]+checkout${END}"

# 記録の列の区切り。タブは read が連続を 1 つにまとめ、空の列で位置がずれるので使わない。
US=$'\037'

# 正規化済みの $COMMAND が対象なら 0、対象外なら 1、照合に失敗したら 2 以上。
is_target() {
  local codes=(0 0)
  # 入力側と照合側の両方の失敗を検出するために PIPESTATUS を使う。-q は入力側が SIGPIPE で失敗するので使わない。
  printf '%s\n' "$COMMAND" | grep -E "$TARGET" >/dev/null || codes=("${PIPESTATUS[@]}")
  [ "${codes[0]}" -eq 0 ] || return 2
  return "${codes[1]}"
}

# ディレクトリから親へたどり、.git（ディレクトリかファイル）がある最初のディレクトリを物理パスで出す。
tree_root() {
  local d
  d=$(cd "$1" 2>/dev/null && pwd -P) || return 1
  while [ -n "$d" ]; do
    if [ -e "$d/.git" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d=${d%/*}
  done
  return 1
}

# 各記録を 1 行で出す（列は pid sessionId cwd status entrypoint startedAt procStart を US で区切る）。
# 読めない記録と、pid が整数でないか cwd がない記録は飛ばす。
read_sessions() {
  local f rec nl=$'\n'
  for f in "$1"/*.json; do
    [ -f "$f" ] || continue
    rec=
    # read は EOF で 1 を返すが、rec には中身が入る。外部コマンドを使わずに読むため read を使う。
    IFS= read -r -d '' rec 2>/dev/null <"$f"
    printf '%s\n' "${rec//$nl/ }"
  done | jq -rR '
    fromjson? | objects
    | select((.pid | type) == "number" and .pid > 0 and .pid == (.pid | floor))
    | select((.cwd | type) == "string" and .cwd != "")
    | [.pid, .sessionId, .cwd, .status, .entrypoint, .startedAt, .procStart]
    | map(if . == null then "" else tostring end | gsub("[\n\u001f]"; " "))
    | join("\u001f")'
}

is_alive() {
  /bin/kill -0 "$1" 2>/dev/null
}

main() {
  local input cwd root records matches
  IFS= read -r -d '' input || :
  # 行継続と引用符を除き、`git \<改行> switch` や `"git" switch` を同じ形にそろえる。
  # bash の ${var//…} は引用符が多いと極端に遅いので jq で行う。
  COMMAND=$(printf '%s' "$input" | jq -er '.tool_input.command | strings | gsub("\\\\\n"; "") | gsub("[\"\\x27]"; "")') || return 1
  is_target || return 1

  cwd=$(printf '%s' "$input" | jq -r '.cwd | strings') || return 1
  [ -n "$cwd" ] || cwd=${CLAUDE_PROJECT_DIR:-}
  [ -n "$cwd" ] || return 1
  root=$(tree_root "$cwd") || return 1

  records=$(read_sessions "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions") || return 1
  matches=$(printf '%s\n' "$records" | while IFS=$US read -r pid _ rcwd _ entry _ pstart; do
    # bash 3.2 は $(...) の中の case の ) を読み違えるので、[[ =~ ]] で確かめる。
    [[ $pid =~ ^[0-9]+$ ]] || continue
    [ "$(tree_root "$rcwd")" = "$root" ] || continue
    is_alive "$pid" "$pstart" || continue
    printf '%s\n' "$entry"
  done) || return 1
  [ -n "$matches" ] || return 1

  local list
  list=$(printf '%s\n' "$matches" | jq -Rrs 'split("\n") | map(select(. != "")) | join("、")') || return 1
  jq -n --arg reason "同じ作業ツリー（${root}）で、別の Claude セッションが動いています: ${list}。このコマンドは、そのセッションのブランチや未コミットの変更に影響します。そのセッションが作業中なら、終わるのを待つか、別の作業ツリーで作業してください。" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $reason}}'
}

# 本体をサブシェルで動かし、成功して出力があるときだけ出す。どの経路でも 0 で終わる。
if out=$(main 2>/dev/null) && [ -n "$out" ]; then
  printf '%s\n' "$out"
fi
exit 0
