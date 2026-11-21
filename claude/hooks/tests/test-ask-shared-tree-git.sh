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

pass=0
fail=0
CFG="$T/cfg"

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

# The hook under test, with /bin/kill swapped for the fake
src=$(cat "$HOOK" 2>/dev/null)
KILL_REAL=/bin/kill
KILL_FAKE="$T/bin/kill"
substituted=${src//$KILL_REAL/$KILL_FAKE}
if [ "$substituted" = "$src" ]; then
  fail=$((fail + 1))
  echo "FAIL /bin/kill in the hook could not be replaced"
fi
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

# verdict <ask|none> <hook-input> <description>
verdict() {
  local expected="$1" input="$2" desc="$3"
  local output code actual
  output=$(CLAUDE_CONFIG_DIR="${HOOK_CFG:-$CFG}" CLAUDE_PROJECT_DIR='' TZ=Asia/Tokyo HOME="${HOOK_HOME:-$HOME}" \
    PATH="${HOOK_PATH:-$PATH}" /bin/bash "${HOOK_FILE:-$T/hook.sh}" <<<"$input" 2>/dev/null)
  code=$?
  case "$code:$output" in
    0:) actual=none ;;
    0:*'"permissionDecision": "ask"'*) actual=ask ;;
    0:*) actual=other-output ;;
    *) actual="exit-$code" ;;
  esac
  if [ "$actual" = "$expected" ]; then
    pass=$((pass + 1))
    echo "PASS [$expected] $desc"
  else
    fail=$((fail + 1))
    echo "FAIL [want $expected, got $actual] $desc"
  fi
}

# check <ask|none> <command> [cwd] [description]
check() {
  local input
  input=$(jq -n --arg cmd "$2" --arg cwd "${3:-$T/repo}" \
    '{session_id: "self-id", cwd: $cwd, tool_input: {command: $cmd}}')
  verdict "$1" "$input" "${4:-$2}"
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
  'git -C sub -c core.x=y switch main' '"git" switch main' $'git \\\nswitch main' 'cd sub && git switch main'; do
  check ask "$cmd"
done

# Not targets
for cmd in 'git commit -m x' 'git add f' 'git add src/' 'git stash list' 'git stash show' 'git status' \
  'git log' 'git diff' 'git fetch' 'git branch -a' 'git cherry-pick abc' 'git revert abc' 'git push' \
  'git worktree list' 'git rm f' 'git mv a b' 'gh pr view 1' 'echo hi' ''; do
  check none "$cmd"
done

# The tree of the hook's cwd
check ask 'git switch main' "$T/repo/sub" 'subdirectory of the same tree'
check ask 'git switch main' "$T/link" 'symlinked cwd'
check none 'git switch main' "$T/other" 'another tree'
check none 'git switch main' "$T/repo/.claude/worktrees/wt" 'worktree inside the tree'
check none 'git switch main' "$T" 'outside any repository'

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

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
