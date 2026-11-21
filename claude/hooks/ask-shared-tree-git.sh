#!/bin/bash
# 作業ツリーの状態を動かす git 操作の前に、同じ作業ツリーで別の Claude セッションが動いていれば、人間の確認に回す。
# 作業の衝突を防ぐ警告で、セキュリティ境界ではない。どんな失敗でも、何も出さずに 0 で終わる（fail open）。
# sandbox の外で、モデルが決めたコマンドの文字列を入力に動くので、git を実行せず、文字列を実行・評価しない。
# ps と kill は絶対パスで使う（PATH に sandbox から書ける場所があっても、sandbox の外で動かさないため）。
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

# 記録の procStart の形（Sat Nov 21 04:58:51 2026）。
PROC_START='^[A-Z][a-z]{2} [A-Z][a-z]{2} +[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}$'

# 列の区切り。タブは read が連続を 1 つにまとめ、空の列で位置がずれるので使わない。
US=$'\037'
NL=$'\n'

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
  local f rec
  for f in "$1"/*.json; do
    [ -f "$f" ] || continue
    rec=
    # read は EOF で 1 を返すが、rec には中身が入る。外部コマンドを使わずに読むため read を使う。
    IFS= read -r -d '' rec 2>/dev/null <"$f"
    printf '%s\n' "${rec//$NL/ }"
  done | jq -rR '
    fromjson? | objects
    | select((.pid | type) == "number" and .pid > 0 and .pid == (.pid | floor))
    | select((.cwd | type) == "string" and .cwd != "")
    | [.pid, .sessionId, .cwd, .status, .entrypoint, .startedAt, .procStart]
    | map(if . == null then "" else tostring end | gsub("[\n\u001f]"; " "))
    | join("\u001f")'
}

# 連続する空白を 1 つにし、前後の空白を除く（1 桁の日の「Nov  1」と「Nov 1」をそろえる）。
squeeze() {
  local IFS=$' \t\n'
  set -f
  # shellcheck disable=SC2086 # 単語分割で空白をそろえる
  set -- $1
  printf '%s' "$*"
}

# kill -0 が成功し、procStart（UTC）が ps の開始時刻と一致すれば生きているとみなす（番号の再利用を除く）。
# procStart がないか形に合わなければ、kill -0 だけで判断する（形式が変わったときに、黙るより確認を増やす）。
is_alive() {
  local want now
  /bin/kill -0 "$1" 2>/dev/null || return 1
  want=$(squeeze "$2")
  [[ $want =~ $PROC_START ]] || return 0
  now=$(TZ=UTC LC_ALL=C /bin/ps -o lstart= -p "$1" 2>/dev/null) || return 1
  [ "$(squeeze "$now")" = "$want" ]
}

# フック自身から 1 までたどった祖先の pid を、空白で区切って出す（最大 32 段）。ps が失敗したら、そこまでを出す。
ancestor_pids() {
  local pid=$$ ppid i=0 list=""
  while [ "$i" -lt 32 ]; do
    ppid=$(/bin/ps -o ppid= -p "$pid" 2>/dev/null) || break
    ppid=${ppid//[[:space:]]/}
    [[ $ppid =~ ^[0-9]+$ ]] || break
    list+=" $ppid"
    [ "$ppid" -gt 1 ] || break
    pid=$ppid
    i=$((i + 1))
  done
  printf '%s ' "$list"
}

# 記録の行（標準入力）のうち、同じ作業ツリーで生きている別のセッションを、entrypoint status startedAt の行で出す。
# 記録の sessionId が自分のものか、pid がフックの祖先なら、自分のセッションとして除く。
live_others() {
  local root=$1 self=$2 ancestors="" looked=""
  local pid sid rcwd status entry started pstart
  while IFS=$US read -r pid sid rcwd status entry started pstart; do
    [[ $pid =~ ^[0-9]+$ ]] || continue
    [ -z "$self" ] || [ "$sid" != "$self" ] || continue
    [ "$(tree_root "$rcwd")" = "$root" ] || continue
    is_alive "$pid" "$pstart" || continue
    # 祖先は、候補が見つかったときに 1 回だけ求める。
    if [ -z "$looked" ]; then
      ancestors=" $(ancestor_pids) "
      looked=1
    fi
    [[ $ancestors == *" $pid "* ]] && continue
    printf '%s\n' "$entry$US$status$US$started"
  done
}

label() {
  case $1 in
    cli) printf 'CLI' ;;
    claude-vscode) printf 'VS Code' ;;
    claude-desktop) printf 'desktop app' ;;
    *) printf '%s' "$1" ;;
  esac
}

# format_reason <root> <live_others の出力>: 確認の文面を出す。セッションは 5 件まで書き、残りは件数にする。
format_reason() {
  local root=$1 rest=$2$NL line entry status started parts t item list="" count=0 tilde='~'
  while [ -n "$rest" ]; do
    line=${rest%%"$NL"*}
    rest=${rest#*"$NL"}
    [ -n "$line" ] || continue
    count=$((count + 1))
    [ "$count" -le 5 ] || continue
    entry=${line%%"$US"*}
    line=${line#*"$US"}
    status=${line%%"$US"*}
    started=${line#*"$US"}
    parts=$status
    if [[ $started =~ ^[0-9]+$ ]] && t=$(/bin/date -r "$((started / 1000))" '+%m/%d %H:%M' 2>/dev/null); then
      parts+="${parts:+、}$t 開始"
    fi
    item=$(label "$entry")
    # bash 3.2 は、変数の直後の全角文字のバイトを変数名の続きと読むので、波括弧で区切る。
    [ -z "$parts" ] || item+="（${parts}）"
    list+="${list:+、}$item"
  done
  [ "$count" -le 5 ] || list+="、ほか $((count - 5)) 件"
  if [ -n "${HOME:-}" ] && [ "$HOME" != / ]; then
    case $root in "$HOME" | "$HOME"/*) root=$tilde${root#"$HOME"} ;; esac
  fi
  printf '%s' "同じ作業ツリー（${root}）で、別の Claude セッションが動いています: ${list}。このコマンドは、そのセッションのブランチや未コミットの変更に影響します。そのセッションが作業中なら、終わるのを待つか、別の作業ツリーで作業してください。"
}

main() {
  local input meta cwd self root records matches reason
  IFS= read -r -d '' input || :
  # 行継続と引用符を除き、`git \<改行> switch` や `"git" switch` を同じ形にそろえる。
  # bash の ${var//…} は引用符が多いと極端に遅いので jq で行う。
  COMMAND=$(printf '%s' "$input" | jq -er '.tool_input.command | strings | gsub("\\\\\n"; "") | gsub("[\"\\x27]"; "")') || return 1
  is_target || return 1

  meta=$(printf '%s' "$input" | jq -r '[.cwd, .session_id]
    | map(if type == "string" then gsub("[\n\u001f]"; " ") else "" end) | join("\u001f")') || return 1
  cwd=${meta%%"$US"*}
  self=${meta#*"$US"}
  [ -n "$cwd" ] || cwd=${CLAUDE_PROJECT_DIR:-}
  [ -n "$cwd" ] || return 1
  root=$(tree_root "$cwd") || return 1

  records=$(read_sessions "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions") || return 1
  matches=$(printf '%s\n' "$records" | live_others "$root" "$self") || return 1
  [ -n "$matches" ] || return 1
  reason=$(format_reason "$root" "$matches") || return 1
  jq -n --arg reason "$reason" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $reason}}'
}

# 本体をサブシェルで動かし、成功して出力があるときだけ出す。どの経路でも 0 で終わる。
if out=$(main 2>/dev/null) && [ -n "$out" ]; then
  printf '%s\n' "$out"
fi
exit 0
