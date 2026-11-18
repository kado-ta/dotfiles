#!/usr/bin/env bash
# Regression tests for guard-playwright-mcp.sh.
# Usage: test-guard-playwright-mcp.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../guard-playwright-mcp.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-guard-playwright-mcp.XXXXXX") || {
  echo "mktemp failed" >&2
  exit 1
}
trap 'rm -rf "$T"' EXIT

pass=0
fail=0

ok() {
  pass=$((pass + 1))
  echo "PASS $1"
}

ng() {
  fail=$((fail + 1))
  echo "FAIL $1"
}

# check <expected-exit> <description> <input-json>
check() {
  local expected="$1" desc="$2" input="$3" actual
  printf '%s\n' "$input" >"$T/input.json"
  "$BASH" "$HOOK" <"$T/input.json" >/dev/null 2>"$T/err"
  actual=$?
  if [ "$actual" = "$expected" ]; then
    ok "[$expected] $desc"
  else
    ng "[want $expected, got $actual] $desc"
  fi
}

shot='"tool_name":"mcp__playwright__browser_take_screenshot"'

# Calls without filename pass
check 0 'screenshot without filename' "{${shot},\"tool_input\":{\"type\":\"png\",\"fullPage\":true}}"
check 0 'navigate' '{"tool_name":"mcp__playwright__browser_navigate","tool_input":{"url":"https://example.com"}}'
check 0 'tool without arguments' '{"tool_name":"mcp__playwright__browser_close","tool_input":{}}'
# Only the tool's own argument counts; a form field labelled "filename" is page data.
check 0 'nested key named filename' '{"tool_name":"mcp__playwright__browser_fill_form","tool_input":{"fields":[{"name":"filename","filename":"x"}]}}'
# Claude Code writes the whole input; a hook that exits without reading it breaks the pipe once the input outgrows the buffer.
{
  printf '%s' '{"tool_name":"mcp__playwright__browser_type","tool_input":{"text":"'
  head -c 300000 /dev/zero | tr '\0' a
  printf '%s\n' '"}}'
} >"$T/big.json"
"$BASH" "$HOOK" <"$T/big.json" >/dev/null 2>&1
actual=$?
if [ "$actual" = 0 ]; then
  ok '[0] large input is read to the end'
else
  ng "[want 0, got $actual] large input is read to the end"
fi

# filename is blocked, whatever its value
check 2 'screenshot with filename' "{${shot},\"tool_input\":{\"filename\":\"login-1440.png\"}}"
err=$(<"$T/err")
case "$err" in
  Blocked:*filename*) ok 'message starts with Blocked: and names the argument' ;;
  *) ng "message starts with Blocked: and names the argument (got '$err')" ;;
esac
check 2 'evaluate result written to settings' '{"tool_name":"mcp__playwright__browser_evaluate","tool_input":{"function":"() => ({})","filename":".claude/settings.json"}}'
check 2 'snapshot to a path outside the output directory' '{"tool_name":"mcp__playwright__browser_snapshot","tool_input":{"filename":"../x.md"}}'
check 2 'empty filename' "{${shot},\"tool_input\":{\"filename\":\"\"}}"
check 2 'null filename' "{${shot},\"tool_input\":{\"filename\":null}}"
# The model chooses the value, possibly under a page's influence, so the block reason must not repeat it.
check 2 'filename with planted text' "{${shot},\"tool_input\":{\"filename\":\"PLANTED-TEXT.png\"}}"
err=$(<"$T/err")
case "$err" in
  *PLANTED-TEXT*) ng "message repeats the filename (got '$err')" ;;
  *) ok 'message does not repeat the filename' ;;
esac

# Input that cannot be checked is blocked (fail closed)
check 2 'invalid JSON' '{"tool_name":'
check 2 'empty input' ''
check 2 'no tool_input' '{"tool_name":"mcp__playwright__browser_close"}'
check 2 'tool_input is not an object' '{"tool_name":"mcp__playwright__browser_close","tool_input":"filename"}'
check 2 'top level is not an object' '["tool_input"]'

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
