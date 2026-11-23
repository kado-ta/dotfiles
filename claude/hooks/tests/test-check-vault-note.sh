#!/usr/bin/env bash
# Regression tests for check-vault-note.sh.
# Usage: test-check-vault-note.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SRC_HOOK="${1:-${SCRIPT_DIR}/../check-vault-note.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-check-vault-note.XXXXXX") || {
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

# The hook reads the approved hash from its own directory, so run a copy next to a test hash.
mkdir -p "$T/hooks"
cp "$SRC_HOOK" "$T/hooks/check-vault-note.sh"
HOOK="$T/hooks/check-vault-note.sh"
HASH="$T/hooks/check-vault-note.sha256"

# A fake Vault (the project directory) with a fake checker.
V="$T/vault"
SCRIPTS="$V/_System/Scripts"
CHECKER="$SCRIPTS/check_note.py"
NOTE="$V/notes/a.md"
mkdir -p "$SCRIPTS" "$V/notes" "$T/elsewhere" "$V-other" "$T/plain/notes" "$T/nodev"
printf '# a\n' >"$NOTE"
printf 'a\n' >"$V/notes/a.txt"
printf '# a\n' >"$T/elsewhere/a.md"
printf '# a\n' >"$V-other/a.md"
printf '# a\n' >"$T/plain/notes/a.md"

# fake_checker <marker> <exit-code>: print a checker that finds the Vault root from __file__ (as the
# real one does), writes its arguments to <root>/<marker>, prints a line on stdout and exits.
fake_checker() {
  cat <<EOF
import re
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    (root / "$1").write_text("\\n".join(sys.argv[1:]) + "\\n")
    print("CHECKER-OUT " + sys.argv[1])
    sys.exit($2)
EOF
}

# approve <exit-code>: install a checker that exits with <exit-code> and record its hash as approved.
approve() {
  fake_checker ran "$1" >"$CHECKER"
  shasum -a 256 "$CHECKER" | cut -d' ' -f1 >"$HASH"
}

# input <name> <file_path>: write a PostToolUse input for an Edit of <file_path> to $T/<name>.json.
input() {
  printf '{"session_id":"s","hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"%s","old_string":"a","new_string":"b"},"tool_response":{"filePath":"%s"}}\n' \
    "$2" "$2" >"$T/$1.json"
}

# run <input-file> [VAR=value...]: run the hook from the Vault with CLAUDE_PROJECT_DIR=$V
# (overridable) and set rc, out and err.
run() {
  local in="$1"
  shift
  rm -f "$V/ran" "$V/evil" "$T/planted"
  (cd "$V" && env CLAUDE_PROJECT_DIR="$V" "$@" "$BASH" "$HOOK" <"$in" >"$T/out" 2>"$T/err")
  rc=$?
  out=$(<"$T/out")
  err=$(<"$T/err")
}

# quiet <desc>: the last run did nothing: exit 0, no output, checker not run.
quiet() {
  if [ "$rc" = 0 ] && [ -z "$out" ] && [ -z "$err" ] && [ ! -e "$V/ran" ]; then
    ok "[0] $1"
  else
    ng "[want 0 and silence, got $rc, out='$out', err='$err', ran=$([ -e "$V/ran" ] && echo yes || echo no)] $1"
  fi
}

# refused <desc> <stderr-fragment>: the last run exited 2 without running the checker and said <fragment>.
refused() {
  if [ "$rc" = 2 ] && [ -z "$out" ] && [ ! -e "$V/ran" ] && [[ "$err" == *"$2"* ]]; then
    ok "[2] $1"
  else
    ng "[want 2, '$2' on stderr and no run, got $rc, out='$out', err='$err', ran=$([ -e "$V/ran" ] && echo yes || echo no)] $1"
  fi
}

input note "$NOTE"
input txt "$V/notes/a.txt"
input outside "$T/elsewhere/a.md"
input sibling "$V-other/a.md"
input plain "$T/plain/notes/a.md"
printf 'not json\n' >"$T/broken.json"
printf '{"tool_name":"Edit","tool_input":{"file_path":7}}\n' >"$T/number.json"
printf '{"tool_name":"Edit"}\n' >"$T/no-input.json"

# Anything that is not a Markdown note in the Vault is left alone. The checker would exit 1,
# so running it by mistake shows up as exit 2 and a marker.
approve 1
run "$T/txt.json"
quiet 'not a .md file'
run "$T/outside.json"
quiet '.md outside the project'
run "$T/sibling.json"
quiet '.md in a sibling directory that shares the prefix'
run "$T/note.json" CLAUDE_PROJECT_DIR=
quiet 'empty CLAUDE_PROJECT_DIR'
(cd "$V" && env -u CLAUDE_PROJECT_DIR "$BASH" "$HOOK" <"$T/note.json" >"$T/out" 2>"$T/err")
rc=$?
out=$(<"$T/out")
err=$(<"$T/err")
quiet 'unset CLAUDE_PROJECT_DIR'
run "$T/plain.json" CLAUDE_PROJECT_DIR="$T/plain"
quiet 'project without the checker'
run "$T/broken.json"
quiet 'input that is not JSON'
run "$T/number.json"
quiet 'file_path that is not a string'
run "$T/no-input.json"
quiet 'input without tool_input'

# A checker that does not match the approved hash is never run.
approve 0
printf '%064d\n' 0 >"$HASH"
run "$T/note.json"
refused 'checker differs from the approved hash' 'check-vault-note.sha256'
rm -f "$HASH"
run "$T/note.json"
refused 'no hash file' 'check-vault-note.sha256'
: >"$HASH"
run "$T/note.json"
refused 'empty hash file' 'check-vault-note.sha256'

# An approved checker runs on the note; its report reaches Claude only through stderr and exit 2.
approve 1
run "$T/note.json"
if [ "$rc" = 2 ] && [ -z "$out" ] && [[ "$err" == *"CHECKER-OUT $NOTE"* ]]; then
  ok '[2] checker exit 1 is reported on stderr'
else
  ng "[want 2 and the checker output on stderr only, got $rc, out='$out', err='$err'] checker exit 1 is reported on stderr"
fi
approve 2
run "$T/note.json"
if [ "$rc" = 2 ] && [[ "$err" == *"CHECKER-OUT"* ]]; then
  ok '[2] checker usage error (exit 2) is reported'
else
  ng "[want 2, got $rc, err='$err'] checker usage error (exit 2) is reported"
fi
approve 0
run "$T/note.json"
if [ "$rc" = 0 ] && [ -z "$out" ]; then
  ok '[0] checker exit 0 passes'
else
  ng "[want 0 and no stdout, got $rc, out='$out', err='$err'] checker exit 0 passes"
fi
# The checker finds the Vault root from __file__ and gets the note as its only argument.
if [ -f "$V/ran" ] && [ "$(<"$V/ran")" = "$NOTE" ]; then
  ok 'checker sees its real path and the note path'
else
  ng "checker sees its real path and the note path (marker: $(cat "$V/ran" 2>/dev/null || echo none))"
fi

# The hook needs no temporary file: bash 3.2 writes here-documents to one, and when it cannot,
# the hook would end with exit 1 and silently skip the check. Run from a read-only directory
# that is also TMPDIR (only the sandbox also stops /tmp, so CI cannot catch a regression).
mkdir -p "$T/readonly"
chmod 555 "$T/readonly"
approve 1
rm -f "$V/ran"
(cd "$T/readonly" && env CLAUDE_PROJECT_DIR="$V" TMPDIR="$T/readonly" "$BASH" "$HOOK" <"$T/note.json" >"$T/out" 2>"$T/err")
rc=$?
err=$(<"$T/err")
if [ "$rc" = 2 ] && [[ "$err" == *"CHECKER-OUT $NOTE"* ]]; then
  ok '[2] runs without a writable temporary directory'
else
  ng "[want 2 and the checker output, got $rc, err='$err'] runs without a writable temporary directory"
fi
chmod 755 "$T/readonly"

# Modules planted next to the checker or in the working directory are not imported.
for dir in "$SCRIPTS" "$V"; do
  printf 'open("%s", "w").close()\nraise SystemExit("planted re imported")\n' "$T/planted" >"$dir/re.py"
done
approve 0
run "$T/note.json"
if [ "$rc" = 0 ] && [ ! -e "$T/planted" ] && [ -f "$V/ran" ]; then
  ok '[0] planted re.py is not imported'
else
  ng "[want 0, the checker run and no planted import, got $rc, err='$err', planted=$([ -e "$T/planted" ] && echo yes || echo no)] planted re.py is not imported"
fi
rm -f "$SCRIPTS/re.py" "$V/re.py"

# Swapping the checker between the approved version and another one never runs the other one:
# the hook must run the same bytes it hashed. A pass can miss a race, but a failure is real.
approve 0
fake_checker ran 0 >"$T/good.py"
fake_checker evil 0 >"$T/evil.py"
(
  while :; do
    cp "$T/good.py" "$SCRIPTS/.swap" && mv -f "$SCRIPTS/.swap" "$CHECKER"
    cp "$T/evil.py" "$SCRIPTS/.swap" && mv -f "$SCRIPTS/.swap" "$CHECKER"
  done
) &
swapper=$!
evil=0
for _ in $(seq 1 40); do
  run "$T/note.json"
  [ -e "$V/evil" ] && evil=$((evil + 1))
done
kill "$swapper" 2>/dev/null
wait "$swapper" 2>/dev/null
if [ "$evil" = 0 ]; then
  ok 'swapped-in checker never runs'
else
  ng "swapped-in checker never runs (ran $evil of 40 times)"
fi

# Without the Command Line Tools, /usr/bin/python3 cannot run; the hook says so instead.
approve 0
run "$T/note.json" DEVELOPER_DIR="$T/nodev"
refused 'no Command Line Tools' 'xcode-select --install'

# Claude Code writes the whole input; a hook that exits without reading it breaks the pipe once
# the input outgrows the buffer. Cover the early exit, the Python path and the no-tools exit.
approve 0
for case in "early exit:CLAUDE_PROJECT_DIR=$T/plain" "python:CLAUDE_PROJECT_DIR=$V" "no tools:DEVELOPER_DIR=$T/nodev"; do
  head -c 300000 /dev/zero | (cd "$V" && env CLAUDE_PROJECT_DIR="$V" "${case#*:}" "$BASH" "$HOOK" >/dev/null 2>&1)
  codes=("${PIPESTATUS[@]}")
  if [ "${codes[0]}" = 0 ]; then
    ok "large input is read to the end (${case%%:*})"
  else
    ng "[want writer 0, got ${codes[0]}] large input is read to the end (${case%%:*})"
  fi
done

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
