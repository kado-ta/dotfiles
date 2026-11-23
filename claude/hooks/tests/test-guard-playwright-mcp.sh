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
# Dropping text is how drag-and-drop UIs are tested; only files on disk are blocked.
check 0 'drop with data only' '{"tool_name":"mcp__playwright__browser_drop","tool_input":{"target":"e1","data":{"text/plain":"hello"}}}'
# A cookie path is a URL path, not a file.
check 0 'cookie path' '{"tool_name":"mcp__playwright__browser_cookie_list","tool_input":{"path":"/"}}'
check 0 'local dev server' '{"tool_name":"mcp__playwright__browser_navigate","tool_input":{"url":"http://localhost:3000/"}}'
check 0 'port just below the Crit range' '{"tool_name":"mcp__playwright__browser_navigate","tool_input":{"url":"http://localhost:47809/"}}'
check 0 'port just above the Crit range' '{"tool_name":"mcp__playwright__browser_navigate","tool_input":{"url":"http://localhost:47830/"}}'

# Claude Code writes the whole input through a pipe; a hook that exits without reading it
# makes the writer fail (SIGPIPE) once the input outgrows the buffer. A file redirect would not show that.
# pipe_check <expected-hook-exit> <description> <input-file>
pipe_check() {
  local expected="$1" desc="$2" file="$3" codes
  cat "$file" | "$BASH" "$HOOK" >/dev/null 2>&1
  codes=("${PIPESTATUS[@]}")
  if [ "${codes[0]}" = 0 ] && [ "${codes[1]}" = "$expected" ]; then
    ok "[$expected] $desc"
  else
    ng "[want writer 0 and hook $expected, got ${codes[0]} and ${codes[1]}] $desc"
  fi
}
# big_input <file> <json-prefix>: write the prefix, 300KB of padding and the closing.
big_input() {
  {
    printf '%s' "$2"
    head -c 300000 /dev/zero | tr '\0' a
    printf '%s\n' '"}}'
  } >"$1"
}
big_input "$T/big.json" '{"tool_name":"mcp__playwright__browser_type","tool_input":{"text":"'
pipe_check 0 'large input is read to the end' "$T/big.json"
big_input "$T/big-block.json" "{${shot},\"tool_input\":{\"filename\":\"x.png\",\"pad\":\""
pipe_check 2 'large blocked input is read to the end' "$T/big-block.json"

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

# paths hands local files to the page (browser_drop is in core; browser_file_upload is also denied in settings.json)
check 2 'drop with paths' '{"tool_name":"mcp__playwright__browser_drop","tool_input":{"target":"e1","paths":["/Users/example/.env"]}}'
err=$(<"$T/err")
case "$err" in
  Blocked:*paths*) ok 'message starts with Blocked: and names paths' ;;
  *) ng "message starts with Blocked: and names paths (got '$err')" ;;
esac
case "$err" in
  *.env*) ng "message repeats the paths (got '$err')" ;;
  *) ok 'message does not repeat the paths' ;;
esac
check 2 'drop with paths and data' '{"tool_name":"mcp__playwright__browser_drop","tool_input":{"target":"e1","paths":["a.txt"],"data":{"text/plain":"x"}}}'
check 2 'file upload with paths' '{"tool_name":"mcp__playwright__browser_file_upload","tool_input":{"paths":["a.txt"]}}'
check 2 'empty paths' '{"tool_name":"mcp__playwright__browser_drop","tool_input":{"target":"e1","paths":[]}}'

# cc-crit's Crit waits on 47810-47829; opening it would let the model press Finish Review itself.
nav='"tool_name":"mcp__playwright__browser_navigate"'
check 2 'Crit on localhost' "{${nav},\"tool_input\":{\"url\":\"http://localhost:47812/\"}}"
err=$(<"$T/err")
case "$err" in
  Blocked:*Crit*) ok 'message starts with Blocked: and names Crit' ;;
  *) ng "message starts with Blocked: and names Crit (got '$err')" ;;
esac
check 2 'Crit without a scheme' "{${nav},\"tool_input\":{\"url\":\"127.0.0.1:47829\"}}"
check 2 'Crit port on another host name' "{${nav},\"tool_input\":{\"url\":\"http://localhost.example:47810/\"}}"
check 2 'Crit port after a backslash' "{${nav},\"tool_input\":{\"url\":\"http://127.0.0.1:47820\\\\@example.com/\"}}"
check 2 'Crit port in a new tab' '{"tool_name":"mcp__playwright__browser_tabs","tool_input":{"action":"new","url":"http://[::1]:47820"}}'
# The WHATWG URL parser (Chrome, Node) drops leading zeros in the port and removes TAB, LF and CR.
check 2 'Crit port with leading zeros' "{${nav},\"tool_input\":{\"url\":\"http://127.0.0.1:00047810/\"}}"
check 2 'Crit port split by a tab' "{${nav},\"tool_input\":{\"url\":\"http://localhost:478\\t10/\"}}"
check 2 'Crit port split by a line feed' "{${nav},\"tool_input\":{\"url\":\"http://localhost:47\\n810/\"}}"
check 2 'Crit port split by a carriage return' "{${nav},\"tool_input\":{\"url\":\"http://localhost:4781\\r0/\"}}"
check 0 'zeros before another port' "{${nav},\"tool_input\":{\"url\":\"http://localhost:0003000/\"}}"

# file: URLs read local files outside the sandbox. Playwright MCP refuses them only when Node can parse the URL,
# so forms like file://localhost:/ would reach the browser. The hook refuses every file: scheme, after the same
# clean-up the WHATWG parser does (leading C0 controls and spaces, and TAB, LF, CR anywhere).
check 2 'file URL' "{${nav},\"tool_input\":{\"url\":\"file:///etc/hosts\"}}"
err=$(<"$T/err")
case "$err" in
  Blocked:*file:*) ok 'message starts with Blocked: and names file:' ;;
  *) ng "message starts with Blocked: and names file: (got '$err')" ;;
esac
check 2 'file URL in upper case' "{${nav},\"tool_input\":{\"url\":\"FILE:///etc/hosts\"}}"
check 2 'file URL that Node cannot parse' "{${nav},\"tool_input\":{\"url\":\"file://localhost:/etc/hosts\"}}"
check 2 'file URL after a space and a control character' "{${nav},\"tool_input\":{\"url\":\" \\u0001file:///etc/hosts\"}}"
check 2 'file scheme split by a tab' "{${nav},\"tool_input\":{\"url\":\"fi\\tle:///etc/hosts\"}}"
check 2 'file URL in a new tab' '{"tool_name":"mcp__playwright__browser_tabs","tool_input":{"action":"new","url":"file:///etc/hosts"}}'
check 0 'file: later in the URL' "{${nav},\"tool_input\":{\"url\":\"https://example.com/?u=file:///etc/hosts\"}}"

# Input that cannot be checked is blocked (fail closed)
check 2 'invalid JSON' '{"tool_name":'
check 2 'empty input' ''
check 2 'no tool_input' '{"tool_name":"mcp__playwright__browser_close"}'
check 2 'tool_input is not an object' '{"tool_name":"mcp__playwright__browser_close","tool_input":"filename"}'
check 2 'top level is not an object' '["tool_input"]'

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
