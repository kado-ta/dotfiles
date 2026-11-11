#!/usr/bin/env bash
# Regression tests for validate-command.sh.
# Usage: test-validate-command.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../validate-command.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-validate-command.XXXXXX") || {
  echo "mktemp failed" >&2
  exit 1
}
trap 'rm -rf "$T"' EXIT

pass=0
fail=0

# check <expected-exit> <command> [description]
check() {
  local expected="$1" cmd="$2" desc="${3:-$2}"
  local input actual
  input=$(jq -n --arg cmd "$cmd" '{tool_input: {command: $cmd}}')
  PATH="${HOOK_PATH:-$PATH}" "$BASH" "$HOOK" <<<"$input" >/dev/null 2>&1
  actual=$?
  if [ "$actual" = "$expected" ]; then
    pass=$((pass + 1))
    echo "PASS [$expected] $desc"
  else
    fail=$((fail + 1))
    echo "FAIL [want $expected, got $actual] $desc"
  fi
}

# Ordinary commands pass
check 0 'git status'
check 0 'ls -la'

# rm -rf is blocked
check 2 'rm -rf /tmp/x'

# Access to the production environment is blocked
check 2 'aws s3 ls --profile prod'
check 2 'ssh app-prd-1'
check 0 'echo prdx' 'prd inside a longer word'

# Read-only SF queries are allowed as a single simple command only
check 0 'sf devops pipeline list --target-org prod-hub'
check 2 'sf devops pipeline list --target-org prod-hub; ls' 'chained after an allowed command'

# cc-safe-push / cc-safe-pr run outside the sandbox only when they match sandbox.excludedCommands exactly
check 0 '/usr/local/libexec/claude-push/cc-safe-push'
check 0 '/usr/local/libexec/claude-push/cc-safe-pr create'
check 0 '/usr/local/libexec/claude-push/cc-safe-pr edit'
check 2 '/usr/local/libexec/claude-push/cc-safe-push; echo "push_exit=$?"' 'cc-safe-push with a command after it'
check 2 'cd /tmp && /usr/local/libexec/claude-push/cc-safe-push' 'cc-safe-push after cd'
check 2 '/usr/local/libexec/claude-push/cc-safe-push origin main' 'cc-safe-push with arguments'
check 2 '/usr/local/libexec/claude-push/cc-safe-pr create && echo done' 'cc-safe-pr with a command after it'
check 2 '/usr/local/libexec/claude-push/cc-safe-pr' 'cc-safe-pr without a subcommand'
check 0 '/usr/bin/python3 -B claude/hooks/tests/test-cc-safe-push.py' 'the wrapper tests'

# A broken or missing jq blocks every command, because it cannot be inspected (fail closed)
BROKEN_JQ="$T/broken-jq"
NO_JQ="$T/no-jq"
mkdir -p "$BROKEN_JQ" "$NO_JQ"
printf '#!/bin/sh\nexit 1\n' >"$BROKEN_JQ/jq"
chmod +x "$BROKEN_JQ/jq"
ln -s "$(command -v grep)" "$NO_JQ/grep"

HOOK_PATH="$BROKEN_JQ:$PATH" check 2 'git status' 'broken jq: ordinary command'
HOOK_PATH="$BROKEN_JQ:$PATH" check 2 'rm -rf /tmp/x' 'broken jq: rm -rf'
HOOK_PATH="$NO_JQ" check 2 'git status' 'missing jq: ordinary command'
HOOK_PATH="$NO_JQ" check 2 'rm -rf /tmp/x' 'missing jq: rm -rf'

# The block message tells how to recover
message=$(PATH="$BROKEN_JQ:$PATH" "$BASH" "$HOOK" <<<'{}' 2>&1 >/dev/null)
if [[ "$message" == *'mise trust'* ]]; then
  pass=$((pass + 1))
  echo "PASS block message mentions the recovery"
else
  fail=$((fail + 1))
  echo "FAIL block message mentions the recovery: $message"
fi

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
