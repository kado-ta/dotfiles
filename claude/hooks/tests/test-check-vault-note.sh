#!/usr/bin/env bash
# Regression tests for check-vault-note.sh (with check-vault-note.py and check-vault-note.sb).
# Usage: test-check-vault-note.sh [hook-path]
# The Python part and the Seatbelt profile are taken from the hook's directory.
# Cases that run the checker under sandbox-exec are skipped where sandbox-exec cannot be nested
# (inside the Claude Code sandbox); CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 turns the skip into a failure.
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SRC_HOOK="${1:-${SCRIPT_DIR}/../check-vault-note.sh}"
SRC_DIR=$(cd "$(dirname "$SRC_HOOK")" && pwd)

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-check-vault-note.XXXXXX") || {
  echo "mktemp failed" >&2
  exit 1
}
HOME_FILE=""
cleanup() {
  chmod 755 "$T/readonly" 2>/dev/null
  [ -n "$HOME_FILE" ] && rm -f "$HOME_FILE"
  rm -rf "$T"
}
trap cleanup EXIT

pass=0
fail=0
skip=0

ok() {
  pass=$((pass + 1))
  echo "PASS $1"
}

ng() {
  fail=$((fail + 1))
  echo "FAIL $1"
}

# The hook runs the approved copy next to it, so run copies of the hook files next to a test copy.
H="$T/hooks"
mkdir -p "$H/vault"
cp "$SRC_HOOK" "$H/check-vault-note.sh"
cp "$SRC_DIR/check-vault-note.py" "$SRC_DIR/check-vault-note.sb" "$H/"
HOOK="$H/check-vault-note.sh"
COPY="$H/vault/check_note.py"

# A fake Vault (the project directory) whose checker matches the copy.
V="$T/vault"
SCRIPTS="$V/_System/Scripts"
CHECKER="$SCRIPTS/check_note.py"
NOTE="$V/notes/a.md"
mkdir -p "$SCRIPTS" "$V/notes" "$T/elsewhere" "$V-other" "$T/plain/notes" "$T/nodev" "$T/outside" "$T/a/b"
printf '# INSIDE-MARKER\n' >"$NOTE"
printf 'a\n' >"$V/notes/a.txt"
printf '# a\n' >"$T/elsewhere/a.md"
printf '# a\n' >"$V-other/a.md"
printf '# a\n' >"$T/plain/notes/a.md"
printf -- '---\nsecret: OUTSIDE-SECRET\n---\n' >"$T/outside/secret.md"
REAL_V=$(cd -P "$V" && pwd)

# fake_checker <exit-code>: print a checker that finds the Vault root from __file__ (as the real
# one does), prints its arguments and the note, tries to write and to connect, and exits.
fake_checker() {
  cat <<EOF
import re
import socket
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    print("CHECKER root=" + str(root) + " argv=" + "|".join(sys.argv[1:]))
    try:
        print("NOTE:" + Path(sys.argv[1]).read_text())
    except OSError as e:
        print("NOTE-DENIED " + type(e).__name__)
    try:
        (root / "written").write_text("x")
        print("WRITE-ALLOWED")
    except OSError:
        print("WRITE-DENIED")
    try:
        socket.socket().connect(("127.0.0.1", 9))
        print("NET-ALLOWED")
    except PermissionError:
        print("NET-DENIED")
    except OSError:
        print("NET-ALLOWED")
    sys.exit($1)
EOF
}

# install <exit-code>: put the same checker in the dotfiles copy and in the Vault.
install() {
  fake_checker "$1" >"$COPY"
  rm -f "$CHECKER"
  cp "$COPY" "$CHECKER"
}

# input <name> <file_path>: write a PostToolUse input for an Edit of <file_path> to $T/<name>.json.
input() {
  printf '{"session_id":"s","hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"%s","old_string":"a","new_string":"b"},"tool_response":{"filePath":"%s"}}\n' \
    "$2" "$2" >"$T/$1.json"
}

# run <input-file> [VAR=value...]: run the hook from the Vault with CLAUDE_PROJECT_DIR=$V
# (overridable), stop it after 20 seconds, and set rc, out and err.
run() {
  local in="$1"
  shift
  rm -f "$V/written"
  (cd "$V" && env CLAUDE_PROJECT_DIR="$V" "$@" /usr/bin/perl -e 'alarm shift; exec @ARGV or die' 20 "$BASH" "$HOOK" <"$in" >"$T/out" 2>"$T/err")
  rc=$?
  out=$(<"$T/out")
  err=$(<"$T/err")
}

# quiet <desc>: the last run did nothing: exit 0, no output.
quiet() {
  if [ "$rc" = 0 ] && [ -z "$out" ] && [ -z "$err" ]; then
    ok "[0] $1"
  else
    ng "[want 0 and silence, got $rc, out='$out', err='$err'] $1"
  fi
}

# refused <desc> <stderr-fragment>: the last run exited 2 without running the checker and said <fragment>.
refused() {
  if [ "$rc" = 2 ] && [ -z "$out" ] && [[ "$err" != *CHECKER* ]] && [[ "$err" == *"$2"* ]]; then
    ok "[2] $1"
  else
    ng "[want 2, '$2' on stderr and no run, got $rc, out='$out', err='$err'] $1"
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

# --- Cases that end before Seatbelt (run everywhere) ---

# Anything that is not a Markdown note in the Vault is left alone. The checker would exit 1,
# so running it by mistake (or failing to start Seatbelt) shows up as exit 2.
install 1
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
# Without the checker check, a Mac without the Command Line Tools would warn on every edit everywhere.
run "$T/plain.json" CLAUDE_PROJECT_DIR="$T/plain" DEVELOPER_DIR="$T/nodev"
quiet 'project without the checker on a Mac without the Command Line Tools'
run "$T/broken.json"
quiet 'input that is not JSON'
run "$T/number.json"
quiet 'file_path that is not a string'
run "$T/no-input.json"
quiet 'input without tool_input'

# Only the reviewed copy in dotfiles may run; a Vault checker that differs from it stops the check.
install 0
printf '# changed\n' >>"$CHECKER"
run "$T/note.json"
refused 'Vault checker differs from the copy' 'claude/hooks/vault/check_note.py'
install 0
rm -f "$COPY"
run "$T/note.json"
refused 'no copy in dotfiles' 'claude/hooks/vault/check_note.py'

# Without the Command Line Tools, python3 cannot run; the hook says so instead.
install 0
run "$T/note.json" DEVELOPER_DIR="$T/nodev"
refused 'no Command Line Tools' 'xcode-select --install'

# The hook needs no temporary file: bash 3.2 writes here-documents to one, and when it cannot,
# the hook would end with exit 1 and silently skip the check.
mkdir -p "$T/readonly"
chmod 555 "$T/readonly"
install 0
printf '# changed\n' >>"$CHECKER"
(cd "$T/readonly" && env CLAUDE_PROJECT_DIR="$V" TMPDIR="$T/readonly" "$BASH" "$HOOK" <"$T/note.json" >"$T/out" 2>"$T/err")
rc=$?
out=$(<"$T/out")
err=$(<"$T/err")
refused 'runs without a writable temporary directory' 'claude/hooks/vault/check_note.py'
chmod 755 "$T/readonly"

# Claude Code writes the whole input; a hook that exits without reading it breaks the pipe once
# the input outgrows the buffer. Cover the early exit, the Python part and the no-tools exit.
install 0
for case in "early exit:CLAUDE_PROJECT_DIR=$T/plain" "python:CLAUDE_PROJECT_DIR=$V" "no tools:DEVELOPER_DIR=$T/nodev"; do
  head -c 300000 /dev/zero | (cd "$V" && env CLAUDE_PROJECT_DIR="$V" "${case#*:}" "$BASH" "$HOOK" >/dev/null 2>&1)
  codes=("${PIPESTATUS[@]}")
  if [ "${codes[0]}" = 0 ]; then
    ok "large input is read to the end (${case%%:*})"
  else
    ng "[want writer 0, got ${codes[0]}] large input is read to the end (${case%%:*})"
  fi
done

# --- Cases that run the checker under Seatbelt ---

if /usr/bin/sandbox-exec -p '(version 1)(allow default)' /usr/bin/true 2>/dev/null; then
  seatbelt=1
else
  seatbelt=0
  if [ "${CHECK_VAULT_NOTE_SEATBELT_REQUIRED:-}" = 1 ]; then
    ng 'sandbox-exec is required (CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1) but cannot run here'
  else
    skip=1
    echo "SKIP Seatbelt cases: sandbox-exec cannot run here (inside the Claude Code sandbox?); run this test in a normal terminal"
  fi
fi

if [ "$seatbelt" = 1 ]; then
  # An approved checker runs on the note; its report reaches Claude only through stderr and exit 2.
  install 1
  run "$T/note.json"
  if [ "$rc" = 2 ] && [ -z "$out" ] && [[ "$err" == *"CHECKER root=$REAL_V argv=$NOTE"* ]]; then
    ok '[2] checker exit 1 is reported on stderr, with the Vault root from __file__ and the note as argument'
  else
    ng "[want 2, the checker output on stderr only, got $rc, out='$out', err='$err'] checker exit 1 is reported on stderr"
  fi
  install 0
  run "$T/note.json"
  if [ "$rc" = 0 ] && [ -z "$out" ] && [[ "$err" == *"NOTE:# INSIDE-MARKER"* ]]; then
    ok '[0] checker exit 0 passes and can read the note in the Vault'
  else
    ng "[want 0 and the note read, got $rc, out='$out', err='$err'] checker exit 0 passes and can read the note in the Vault"
  fi
  if [[ "$err" == *WRITE-DENIED* ]] && [ ! -e "$V/written" ]; then
    ok 'checker cannot write in the Vault'
  else
    ng "checker cannot write in the Vault (err='$err')"
  fi
  if [[ "$err" == *NET-DENIED* ]]; then
    ok 'checker cannot connect to 127.0.0.1'
  else
    ng "checker cannot connect to 127.0.0.1 (err='$err')"
  fi

  # Notes that point outside the Vault are not read, even through the checker.
  ln -sf "$T/outside/secret.md" "$V/notes/out.md"
  input out "$V/notes/out.md"
  run "$T/out.json"
  if [[ "$err" == *"NOTE-DENIED"* ]] && [[ "$err" != *OUTSIDE-SECRET* ]]; then
    ok 'note linked to a file outside the Vault is not read'
  else
    ng "note linked to a file outside the Vault is not read (rc=$rc, err='$err')"
  fi
  HOME_FILE=$(mktemp "$HOME/.check-vault-note-test.XXXXXX") && printf '# HOME-SECRET\n' >"$HOME_FILE"
  ln -sf "$HOME_FILE" "$V/notes/home.md"
  input home "$V/notes/home.md"
  run "$T/home.json"
  if [ -n "$HOME_FILE" ] && [[ "$err" == *"NOTE-DENIED"* ]] && [[ "$err" != *HOME-SECRET* ]]; then
    ok 'note linked to a file under HOME is not read'
  else
    ng "note linked to a file under HOME is not read (rc=$rc, err='$err')"
  fi

  # The reported bypass: the Vault checker links to an approved copy two levels below $T, which
  # moves the checker's Vault root to $T, and the note links to a file there.
  install 0
  cp "$COPY" "$T/a/b/check_note.py"
  ln -sf "$T/a/b/check_note.py" "$CHECKER"
  run "$T/out.json"
  if [[ "$err" == *"CHECKER root="* ]] && [[ "$err" != *OUTSIDE-SECRET* ]]; then
    ok 'moving the Vault root with a linked checker does not expose files outside the Vault'
  else
    ng "moving the Vault root with a linked checker does not expose files outside the Vault (rc=$rc, err='$err')"
  fi
  # The same link also shows that the copy runs, not the Vault path: the linked file is outside
  # the Vault, so reading it under Seatbelt would fail.
  run "$T/note.json"
  if [ "$rc" = 0 ] && [[ "$err" == *"NOTE:# INSIDE-MARKER"* ]]; then
    ok '[0] the copy in dotfiles runs, not the file at the Vault path'
  else
    ng "[want 0 and the checker run, got $rc, err='$err'] the copy in dotfiles runs, not the file at the Vault path"
  fi

  # Modules planted next to the checker or in the working directory are not imported.
  install 0
  for dir in "$SCRIPTS" "$V"; do
    printf 'print("PLANTED re imported")\nraise SystemExit(3)\n' >"$dir/re.py"
  done
  run "$T/note.json"
  if [ "$rc" = 0 ] && [[ "$err" != *PLANTED* ]] && [[ "$err" == *CHECKER* ]]; then
    ok '[0] planted re.py is not imported'
  else
    ng "[want 0 and the checker run without the planted module, got $rc, err='$err'] planted re.py is not imported"
  fi
  rm -f "$SCRIPTS/re.py" "$V/re.py"
fi

echo "---"
echo "pass=$pass fail=$fail skip=$skip"
[ "$fail" -eq 0 ]
