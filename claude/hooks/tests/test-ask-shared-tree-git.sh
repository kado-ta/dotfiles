#!/usr/bin/env bash
# Regression tests for ask-shared-tree-git.sh.
# Usage: test-ask-shared-tree-git.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../ask-shared-tree-git.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-ask-shared-tree-git.XXXXXX") || {
  echo "mktemp failed" >&2
  exit 1
}
trap 'rm -rf "$T"' EXIT
# The physical path, as the hook reports it
TP=$(cd "$T" && pwd -P)

pass=0
fail=0
CFG="$T/cfg"

ok() {
  pass=$((pass + 1))
  echo "PASS $1"
}
ng() {
  fail=$((fail + 1))
  echo "FAIL $1"
}

# Trees: a repository, a worktree inside it, another repository, and a symlink to the first
mkdir -p "$T/repo/.git" "$T/repo/sub" "$T/repo/.claude/worktrees/wt" "$T/other/.git" "$T/bin"
echo 'gitdir: elsewhere' >"$T/repo/.claude/worktrees/wt/.git"
ln -s "$T/repo" "$T/link"

# Fake kill: "-0 <pid>" succeeds while $T/alive/<pid> exists.
cat >"$T/bin/kill" <<EOF
#!/bin/sh
[ "\$1" = -0 ] && [ -e "$T/alive/\$2" ]
EOF
# Fake ps: "-o lstart= -p <pid>" prints the registered start time in the caller's TZ,
# "-o ppid= -p <pid>" prints the registered parent ($T/ppid/default, then 1, when none is registered).
cat >"$T/bin/ps" <<EOF
#!/bin/sh
[ "\$1" = -o ] && [ "\$3" = -p ] || exit 2
case "\$2" in
  lstart=)
    [ -f "$T/start/\$4" ] || exit 1
    /bin/date -r "\$(/bin/cat "$T/start/\$4")" '+%a %b %e %H:%M:%S %Y' ;;
  ppid=)
    if [ -f "$T/ppid/\$4" ]; then /bin/cat "$T/ppid/\$4"
    elif [ -f "$T/ppid/default" ]; then /bin/cat "$T/ppid/default"
    else echo 1; fi ;;
  *) exit 2 ;;
esac
EOF
chmod +x "$T/bin/kill" "$T/bin/ps"

# The hook under test, with /bin/kill and /bin/ps swapped for the fakes
src=$(cat "$HOOK" 2>/dev/null)
KILL_REAL=/bin/kill
KILL_FAKE="$T/bin/kill"
PS_REAL=/bin/ps
PS_FAKE="$T/bin/ps"
step=${src//$KILL_REAL/$KILL_FAKE}
[ "$step" != "$src" ] || ng "/bin/kill in the hook could not be replaced"
substituted=${step//$PS_REAL/$PS_FAKE}
[ "$substituted" != "$step" ] || ng "/bin/ps in the hook could not be replaced"
printf '%s\n' "$substituted" >"$T/hook.sh"

# reset: forget every session record and every fake process
reset() {
  rm -rf "$CFG/sessions" "$T/alive" "$T/start" "$T/ppid"
  mkdir -p "$CFG/sessions" "$T/alive" "$T/start" "$T/ppid"
}

# record <pid> <cwd> [status] [entrypoint] [sessionId] [procStart|-] [startedAt]
# Writes a one-line record without a trailing newline, like Claude Code does. "-" leaves procStart out.
record() {
  printf '%s' "$(jq -nc --argjson pid "$1" --arg cwd "$2" --arg status "${3:-idle}" --arg entry "${4:-cli}" \
    --arg sid "${5:-other-$1}" --arg ps "${6:--}" --argjson started "${7:-1795237132160}" \
    '{pid: $pid, sessionId: $sid, cwd: $cwd, startedAt: $started, kind: "interactive",
      entrypoint: $entry, status: $status} + (if $ps == "-" then {} else {procStart: $ps} end)')" \
    >"$CFG/sessions/$1.json"
}

# alive <pid> [epoch]: the fake kill sees the pid, and the fake ps reports it started at epoch
alive() {
  : >"$T/alive/$1"
  if [ $# -ge 2 ]; then echo "$2" >"$T/start/$1"; fi
}

# input_for <command> [cwd]
input_for() {
  jq -n --arg cmd "$1" --arg cwd "${2:-$T/repo}" \
    '{session_id: "self-id", cwd: $cwd, tool_input: {command: $cmd}}'
}

# invoke <hook-input>: runs the hook under test and sets OUT and CODE
invoke() {
  OUT=$(CLAUDE_CONFIG_DIR="${HOOK_CFG:-$CFG}" CLAUDE_PROJECT_DIR="${HOOK_PROJECT_DIR:-}" TZ=Asia/Tokyo HOME="${HOOK_HOME:-$HOME}" \
    PATH="${HOOK_PATH:-$PATH}" /bin/bash "${HOOK_FILE:-$T/hook.sh}" <<<"$1" 2>/dev/null)
  CODE=$?
}

# verdict <ask|none> <hook-input> <description>
verdict() {
  local actual
  invoke "$2"
  case "$CODE:$OUT" in
    0:) actual=none ;;
    0:*'"permissionDecision": "ask"'*) actual=ask ;;
    0:*) actual=other-output ;;
    *) actual="exit-$CODE" ;;
  esac
  if [ "$actual" = "$1" ]; then
    ok "[$1] $3"
  else
    ng "[want $1, got $actual] $3"
  fi
}

# check <ask|none> <command> [cwd] [description]
check() {
  verdict "$1" "$(input_for "$2" "${3:-}")" "${4:-$2}"
}

# reason [cwd]: the permissionDecisionReason for 'git switch main' (empty when the hook does not ask)
reason() {
  invoke "$(input_for 'git switch main' "${1:-}")"
  printf '%s' "$OUT" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty' 2>/dev/null
}

# expect_in <description> <text> <substring>
expect_in() {
  case "$2" in
    *"$3"*) ok "$1" ;;
    *) ng "$1: '$3' not in '$2'" ;;
  esac
}

# expect_count <description> <text> <substring> <count>
expect_count() {
  local rest=${2//"$3"/}
  local n=$(((${#2} - ${#rest}) / ${#3}))
  if [ "$n" -eq "$4" ]; then
    ok "$1"
  else
    ng "$1: '$3' appears $n times, want $4, in '$2'"
  fi
}

# Another live session shares the tree
reset
record 5001 "$T/repo"
alive 5001

# Targets ask when another live session shares the tree
for cmd in 'git switch main' 'git switch -c feat/x' 'git checkout main' 'git checkout -b x' \
  'git checkout -- f' 'git rebase main' 'git merge x' 'git pull' 'git reset --hard' 'git reset HEAD~1' \
  'git bisect start' 'git stash' 'git stash push -m x' 'git stash pop' 'git restore f' 'git clean -fd' \
  'git add -A' 'git add --all' 'git add -u' 'git add --update' 'git add .' 'git add :/' \
  'git commit -a -m x' 'git commit -am x' 'git commit --all -m x' 'gh pr checkout 12' \
  'git -C sub -c core.x=y switch main' '"git" switch main' $'git \\\nswitch main' 'cd sub && git switch main' \
  'git stash 2>&1' 'git stash >/dev/null' 'git stash -u' 'git stash --include-untracked' \
  'git commit -m x .' 'git commit -m x -- :/'; do
  check ask "$cmd"
done

# Not targets
for cmd in 'git commit -m x' 'git add f' 'git add src/' 'git stash list' 'git stash show' 'git status' \
  'git log' 'git diff' 'git fetch' 'git branch -a' 'git cherry-pick abc' 'git revert abc' 'git push' \
  'git worktree list' 'git rm f' 'git mv a b' 'gh pr view 1' 'echo hi' '' \
  'git commit --amend --no-edit' 'git commit -m x f'; do
  check none "$cmd"
done

# Known false positives (design 6): quotes are removed before matching, so words inside them count
check ask 'git commit -m "docs: explain git reset usage"' '' 'known false positive: commit message'
check ask "grep -rn 'git checkout' claude/" '' 'known false positive: grep pattern'

# A long command with many quotes stays far below the 10 s hook timeout (a quadratic gsub took about 7 s here)
long=$(printf 'echo "a" %.0s' $(seq 1 15000))
TIMEFORMAT=%R
{ time check none "$long" '' 'long command with many quotes'; } 2>"$T/long-command.time"
elapsed=$(<"$T/long-command.time")
if awk -v e="$elapsed" 'BEGIN { exit !(e < 3) }'; then
  ok "long command took ${elapsed}s"
else
  ng "long command took ${elapsed}s"
fi

# The tree of the hook's cwd
check ask 'git switch main' "$T/repo/sub" 'subdirectory of the same tree'
check ask 'git switch main' "$T/link" 'symlinked cwd'
check none 'git switch main' "$T/other" 'another tree'
check none 'git switch main' "$T/repo/.claude/worktrees/wt" 'worktree inside the tree'
check none 'git switch main' "$T" 'outside any repository'
no_cwd=$(jq -nc '{session_id: "self-id", tool_input: {command: "git switch main"}}')
HOOK_PROJECT_DIR="$T/repo" verdict ask "$no_cwd" 'no cwd falls back to CLAUDE_PROJECT_DIR'
verdict none "$no_cwd" 'no cwd and no CLAUDE_PROJECT_DIR'

# The records decide
reset
check none 'git switch main' '' 'no records at all'

reset
record 5001 "$T/other"
alive 5001
check none 'git switch main' '' 'only a session in another tree'

reset
record 5001 "$T/repo/.claude/worktrees/wt"
alive 5001
check none 'git switch main' '' 'only a session in a worktree inside the tree'

reset
record 5001 "$T/link"
alive 5001
check ask 'git switch main' '' 'symlinked record cwd'

reset
record 5002 "$T/repo"
check none 'git switch main' '' 'only a dead session'

reset
record 5000 "$T/repo/gone"
alive 5000
check none 'git switch main' '' 'only a session whose cwd no longer exists'
record 5001 "$T/repo"
alive 5001
check ask 'git switch main' '' 'deleted cwd'

reset
printf '{not json' >"$CFG/sessions/0000.json"
record 5001 "$T/repo"
alive 5001
check ask 'git switch main' '' 'malformed record skipped'

reset
printf '%s' "$(jq -nc --arg cwd "$T/repo" '{sessionId: "a", cwd: $cwd}')" >"$CFG/sessions/5004.json"
printf '%s' "$(jq -nc --arg cwd "$T/repo" '{pid: "5005", sessionId: "b", cwd: $cwd}')" >"$CFG/sessions/5005.json"
printf '%s' "$(jq -nc '{pid: 5006, sessionId: "c"}')" >"$CFG/sessions/5006.json"
alive 5004
alive 5005
alive 5006
check none 'git switch main' '' 'records without an integer pid or a cwd are skipped'

# Fail open: every failure exits 0 with no output
reset
record 5001 "$T/repo"
alive 5001
NO_JQ="$T/no-jq"
BROKEN_JQ="$T/broken-jq"
mkdir -p "$NO_JQ" "$BROKEN_JQ"
ln -s "$(command -v grep)" "$NO_JQ/grep"
printf '#!/bin/sh\nexit 1\n' >"$BROKEN_JQ/jq"
chmod +x "$BROKEN_JQ/jq"
HOOK_PATH="$NO_JQ" check none 'git switch main' '' 'missing jq'
HOOK_PATH="$BROKEN_JQ:$PATH" check none 'git switch main' '' 'broken jq'
HOOK_CFG="$T/nowhere" check none 'git switch main' '' 'missing sessions directory'
verdict none 'not json' 'invalid JSON'
verdict none '' 'empty input'
verdict none "$(jq -nc --arg cwd "$T/repo" '{cwd: $cwd, tool_input: {command: null}}')" 'null command'
verdict none "$(jq -nc --arg cwd "$T/repo" '{cwd: $cwd, tool_input: {command: 1}}')" 'non-string command'
verdict none "$(jq -nc --arg cwd "$T/repo" '{cwd: $cwd, tool_input: {}}')" 'missing command'

# Liveness: procStart (UTC) is compared with ps, so a pid reused by another process is not counted
EPOCH=1795237131  # 2026-11-21 04:58:51 UTC
EPOCH1=1793491200 # 2026-11-01 00:00:00 UTC, a Sunday
# proc <epoch>: procStart as Claude Code writes it
proc() { TZ=UTC LC_ALL=C /bin/date -r "$1" '+%a %b %e %H:%M:%S %Y'; }

reset
record 5001 "$T/repo" idle cli other-5001 "$(proc "$EPOCH")"
alive 5001 "$EPOCH"
check ask 'git switch main' '' 'procStart matches in UTC'
alive 5001 $((EPOCH + 60))
check none 'git switch main' '' 'pid reused'
record 5001 "$T/repo" idle cli other-5001 garbage
check ask 'git switch main' '' 'unknown procStart format falls back to kill -0'
record 5001 "$T/repo" idle cli other-5001 'Sun Nov 1 00:00:00 2026'
alive 5001 "$EPOCH1"
check ask 'git switch main' '' 'single-digit day'

reset
record 5001 "$T/repo" idle cli other-5001 "$(proc "$EPOCH")"
alive 5001
check none 'git switch main' '' 'ps fails for a live pid'

# Self: the calling session is not another session
reset
record 5001 "$T/repo" idle cli self-id
alive 5001
check none 'git switch main' '' 'same sessionId'

reset
echo 4242 >"$T/ppid/default"
echo 1 >"$T/ppid/4242"
record 4242 "$T/repo"
alive 4242
check none 'git switch main' '' 'ancestor pid'
record 5001 "$T/repo"
alive 5001
check ask 'git switch main' '' 'ancestor pid plus another live session'
expect_count 'the reason lists only the other session' "$(reason)" '開始）' 1

# Reason text
reset
record 5001 "$T/repo" busy cli
record 5002 "$T/repo" idle claude-vscode
record 5003 "$T/repo" waiting claude-desktop
record 5004 "$T/repo" idle cursor
alive 5001
alive 5002
alive 5003
alive 5004
text=$(HOOK_HOME=/nonexistent-home reason)
expect_in 'CLI label' "$text" 'CLI（busy、'
expect_in 'VS Code label' "$text" 'VS Code（idle、'
expect_in 'desktop app label' "$text" 'desktop app（waiting、'
expect_in 'unknown entrypoint as is' "$text" 'cursor（idle、'
expect_in 'start time in the local time zone' "$text" '11/21 13:58 開始'
expect_in 'physical path outside home' "$text" "同じ作業ツリー（$TP/repo）"
expect_in 'home as ~' "$(HOOK_HOME="$TP" reason)" '同じ作業ツリー（~/repo）'

reset
for pid in 5001 5002 5003 5004 5005 5006 5007; do
  record "$pid" "$T/repo"
  alive "$pid"
done
text=$(reason)
expect_count 'at most five sessions listed' "$text" '開始）' 5
expect_in 'the rest counted' "$text" '、ほか 2 件'

reset
mkdir -p "$T/a\"b/.git"
record 5001 "$T/a\"b"
alive 5001
invoke "$(input_for 'git switch main' "$T/a\"b")"
if printf '%s' "$OUT" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("a\"b")' >/dev/null 2>&1; then
  ok 'a quote in the path keeps the output valid JSON'
else
  ng "a quote in the path keeps the output valid JSON: $OUT"
fi

# Many records: dead sessions left behind do not slow the hook down
reset
for pid in $(seq 6000 6059); do record "$pid" "$T/repo"; done
record 5001 "$T/repo"
alive 5001
# time measures the check in this shell to the millisecond; SECONDS has 1 s steps and could read 2 s for 1.01 s
TIMEFORMAT=%R
{ time check ask 'git switch main' '' 'many records'; } 2>"$T/many-records.time"
elapsed=$(<"$T/many-records.time")
if awk -v e="$elapsed" 'BEGIN { exit !(e < 2) }'; then
  ok "many records took ${elapsed}s"
else
  ng "many records took ${elapsed}s"
fi

# Real ps and kill, with the hook itself (ps is not permitted inside the Claude Code sandbox)
if ! /bin/ps -p $$ >/dev/null 2>&1; then
  echo "SKIP real ps"
else
  sleep 60 &
  spid=$!
  reset
  record "$spid" "$T/repo" idle cli x "$(TZ=UTC LC_ALL=C /bin/ps -o lstart= -p "$spid")"
  HOOK_FILE="$HOOK" check ask 'git switch main' '' 'real ps: a live session'
  reset
  record $$ "$T/repo" idle cli x "$(TZ=UTC LC_ALL=C /bin/ps -o lstart= -p $$)"
  HOOK_FILE="$HOOK" check none 'git switch main' '' 'real ps: the test shell, an ancestor of the hook'
  reset
  record "$spid" "$T/repo" idle cli x "$(TZ=UTC LC_ALL=C /bin/ps -o lstart= -p "$spid")"
  kill "$spid"
  wait "$spid" 2>/dev/null
  HOOK_FILE="$HOOK" check none 'git switch main' '' 'real ps: the session ended'
fi

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
