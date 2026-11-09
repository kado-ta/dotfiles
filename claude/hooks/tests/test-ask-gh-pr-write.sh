#!/usr/bin/env bash
# Regression tests for ask-gh-pr-write.sh.
# Usage: test-ask-gh-pr-write.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../ask-gh-pr-write.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-ask-gh-pr-write.XXXXXX") || {
  echo "mktemp failed" >&2
  exit 1
}
trap 'rm -rf "$T"' EXIT

pass=0
fail=0

# verdict <ask|none|block> <hook-input> <description>
verdict() {
  local expected="$1" input="$2" desc="$3"
  local output code actual
  output=$(PATH="${HOOK_PATH:-$PATH}" "$BASH" "${HOOK_FILE:-$HOOK}" <<<"$input" 2>/dev/null)
  code=$?
  case "$code:$output" in
    0:) actual=none ;;
    0:*'"permissionDecision": "ask"'*) actual=ask ;;
    2:*) actual=block ;;
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

# check <ask|none|block> <command> [description]
check() {
  local input
  input=$(jq -n --arg cmd "$2" '{tool_input: {command: $cmd}}')
  verdict "$1" "$input" "${3:-$2}"
}

# Pull request writes and gh api need a human, however they are spelled
check ask 'gh pr create --title x'
check ask 'gh pr new'
check ask 'gh pr edit 1 --title x'
check ask 'gh pr merge 1'
check ask 'gh pr close 1'
check ask 'gh pr ready 1'
check ask 'gh pr reopen 1'
check ask 'gh pr revert 1'
check ask 'gh pr update-branch 1'
check ask 'gh pr lock 1'
check ask 'gh pr unlock 1'
check ask 'gh pr review 1 --approve'
check ask 'gh pr comment 1 --body x'
check ask 'gh pr -R o/r merge 1'
check ask 'gh -R o/r pr close 1'
check ask 'gh --repo o/r pr merge 1'
check ask 'gh pr --repo=o/r edit 1'
check ask '/opt/homebrew/bin/gh pr merge 1'
check ask 'env GH_REPO=o/r gh pr create'
check ask 'command gh pr merge 1'
check ask "bash -c 'gh pr ready 1'"
check ask 'cd sub && gh pr merge 1' 'after another command'
check ask 'gh api user'
check ask 'gh api repos/o/r/pulls/1/merge -X PUT'
check ask '"gh" pr merge 1' 'quoted command'
check ask 'gh "pr" merge 1' 'quoted subcommand'
check ask 'gh pr mer""ge 1' 'quotes inside a word'
check ask $'gh pr \\\nmerge 1' 'line continuation between words'
check ask $'gh pr mer\\\nge 1' 'line continuation inside a word'
check ask $'gh \\\npr merge 1' 'line continuation after gh'

# Reads and the wrappers are left to the normal permission flow
check none 'gh pr view 1'
check none 'gh pr checks 1'
check none 'gh pr list'
check none 'gh pr diff 1'
check none 'gh pr status'
check none 'gh repo view'
check none 'gh auth status'
check none 'git log'
check none '/usr/local/libexec/claude-push/cc-safe-push'
check none '/usr/local/libexec/claude-push/cc-safe-pr create'
check none '/usr/local/libexec/claude-push/cc-safe-pr edit'
check none 'my-gh pr merge 1' 'another program whose name ends in gh'
check none 'gh pr merges' 'a verb only as a prefix'
check none ''

# Known misses: this hook is not a security boundary
check none 'gh pr $X 1' 'known miss: variable'
check none $'gh pr $\'merge\' 1' 'known miss: ANSI-C quoting'
check none '$(which gh) pr merge 1' 'known miss: command substitution'
check none 'eval "$X"' 'known miss: eval'
check none 'gh m 1' 'known miss: gh alias'
check none "env -S'gh pr merge 1'" 'known miss: env -S'
check none 'python3 -c "import os; os.system(chr(103)+chr(104))"' 'known miss: built by a program'

# Known false positives: these only add a confirmation
check ask 'git commit -m "docs: gh pr create usage"' 'known false positive: commit message'
check ask 'grep "gh api" .' 'known false positive: grep'
check ask 'echo gh pr merge' 'known false positive: echo'

# Commands that cannot be read are blocked
verdict block '{"tool_input":{"command":null}}' 'null command'
verdict block '{"tool_input":{"command":1}}' 'non-string command'
verdict block '{"tool_input":{}}' 'missing command'
verdict block '' 'empty input'
verdict block 'not json' 'invalid JSON'

# A broken or missing tool blocks every command, because it cannot be inspected (fail closed)
BROKEN_JQ="$T/broken-jq"
NO_JQ="$T/no-jq"
BROKEN_GREP="$T/broken-grep"
mkdir -p "$BROKEN_JQ" "$NO_JQ" "$BROKEN_GREP"
printf '#!/bin/sh\nexit 1\n' >"$BROKEN_JQ/jq"
printf '#!/bin/sh\nexit 2\n' >"$BROKEN_GREP/grep"
chmod +x "$BROKEN_JQ/jq" "$BROKEN_GREP/grep"
ln -s "$(command -v grep)" "$NO_JQ/grep"

HOOK_PATH="$BROKEN_JQ:$PATH" check block 'git status' 'broken jq'
HOOK_PATH="$NO_JQ" check block 'git status' 'missing jq'
HOOK_PATH="$BROKEN_GREP:$PATH" check block 'gh pr merge 1' 'broken grep: a write'
HOOK_PATH="$BROKEN_GREP:$PATH" check block 'git status' 'broken grep: ordinary command'

# A failure on the input side of the pipe is not read as "no match"
src=$(<"$HOOK")
broken=${src/printf \'%s\\n\' \"\$COMMAND\"/false}
if [ "$broken" = "$src" ]; then
  fail=$((fail + 1))
  echo "FAIL the input side of the pipe could not be replaced"
else
  printf '%s\n' "$broken" >"$T/broken-input.sh"
  HOOK_FILE="$T/broken-input.sh" check block 'gh pr merge 1' 'failure on the input side of the pipe'
fi

# A long command with many quotes does not hit the hook timeout
long=$(printf 'echo "a" %.0s' $(seq 1 3000))
start=$SECONDS
check none "$long" 'long command with many quotes'
elapsed=$((SECONDS - start))
if [ "$elapsed" -lt 10 ]; then
  pass=$((pass + 1))
  echo "PASS long command took ${elapsed}s"
else
  fail=$((fail + 1))
  echo "FAIL long command took ${elapsed}s"
fi

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
