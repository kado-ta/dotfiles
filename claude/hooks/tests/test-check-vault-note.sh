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
SHARED_FILE=""
cleanup() {
  chmod 755 "$T/readonly" 2>/dev/null
  [ -n "$HOME_FILE" ] && rm -f "$HOME_FILE"
  [ -n "$SHARED_FILE" ] && rm -f "$SHARED_FILE"
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

# The hook only checks the Vault at $HOME/Obsidian/main, so the hook gets a test HOME.
TEST_HOME="$T/home"
V="$TEST_HOME/Obsidian/main"
SCRIPTS="$V/_System/Scripts"
CHECKER="$SCRIPTS/check_note.py"
NOTE="$V/notes/a.md"
OTHER="$T/other"
mkdir -p "$SCRIPTS" "$V/notes" "$T/elsewhere" "$V-other" "$T/plain/notes" "$T/nodev" "$T/outside" "$T/a/b" \
  "$OTHER/_System/Scripts" "$OTHER/notes" "$T/pp" "$V/secrets" "$V/keys" "$T/badhooks/vault"
printf '# INSIDE-MARKER\n' >"$NOTE"
printf 'a\n' >"$V/notes/a.txt"
printf 'VAULT-TXT-SECRET\n' >"$V/notes/secret.txt"
printf '# VAULT-SECRETS-MD\n' >"$V/secrets/s.md"
printf '# VAULT-KEY-MD\n' >"$V/keys/id_rsa.md"
printf '# a\n' >"$T/elsewhere/a.md"
printf '# a\n' >"$V-other/a.md"
printf '# a\n' >"$T/plain/notes/a.md"
printf '# a\n' >"$OTHER/notes/a.md"
printf -- '---\nsecret: OUTSIDE-SECRET\n---\n' >"$T/outside/secret.md"
printf 'print("PLANTED re imported")\nraise SystemExit(3)\n' >"$T/pp/re.py"
REAL_V=$(cd -P "$V" && pwd)

# fake_checker <exit-code>: print a checker that finds the Vault root from __file__ (as the real
# one does), prints its arguments and the note, tries to write, connect, fork and exec, prints a
# message with a newline and an escape character in it, and exits. A note whose name starts with
# "raw" is read without catching errors.
fake_checker() {
  cat <<EOF
import os
import re
import socket
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    print("CHECKER root=" + str(root) + " argv=" + "|".join(sys.argv[1:]))
    note = Path(sys.argv[1])
    if note.name.startswith("raw"):
        print("RAW:" + note.read_text())
    try:
        print("NOTE:" + note.read_text())
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
    try:
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        print("FORK-ALLOWED")
    except OSError:
        print("FORK-DENIED")
    print("MULTI-A\nINJECTED-LINE\x1b[31m")
    print("# HEADING-LIKE")
    try:
        os.execv("/usr/bin/true", ["true"])
    except OSError:
        print("EXEC-DENIED")
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

# run <input-file> [VAR=value...]: run the hook from the Vault with CLAUDE_PROJECT_DIR=$V and
# HOME=$TEST_HOME (both overridable), stop it after 20 seconds, and set rc, out and err.
run() {
  local in="$1"
  shift
  rm -f "$V/written"
  (cd "$V" && env CLAUDE_PROJECT_DIR="$V" HOME="$TEST_HOME" "$@" /usr/bin/perl -e 'alarm shift; exec @ARGV or die' 20 "$BASH" "$HOOK" <"$in" >"$T/out" 2>"$T/err")
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
  if [ "$rc" = 2 ] && [ -z "$out" ] && [[ "$err" != *CHECKER* ]] && [[ "$err" != *PLANTED* ]] && [[ "$err" == *"$2"* ]]; then
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
input other "$OTHER/notes/a.md"
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
(cd "$V" && env -u CLAUDE_PROJECT_DIR HOME="$TEST_HOME" "$BASH" "$HOOK" <"$T/note.json" >"$T/out" 2>"$T/err")
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

# Only the Vault at $HOME/Obsidian/main is checked. Any project can hold a copy of the public
# checker, and Seatbelt lets the checker read inside the project it is given.
install 1
cp "$COPY" "$OTHER/_System/Scripts/check_note.py"
run "$T/other.json" CLAUDE_PROJECT_DIR="$OTHER"
quiet 'project with the checker that is not the configured Vault'
run "$T/note.json" HOME=
quiet 'empty HOME'

# Only the reviewed copy in dotfiles may run; a Vault checker that differs from it stops the check.
install 0
printf '# changed\n' >>"$CHECKER"
run "$T/note.json"
refused 'Vault checker differs from the copy' 'claude/hooks/vault/check_note.py'
run "$T/note.json" CLAUDE_PROJECT_DIR="$V/"
refused 'CLAUDE_PROJECT_DIR with a trailing slash' 'claude/hooks/vault/check_note.py'
# -I keeps PYTHONPATH (and the script and working directories) off sys.path.
run "$T/note.json" PYTHONPATH="$T/pp"
refused 'PYTHONPATH is ignored before Seatbelt' 'claude/hooks/vault/check_note.py'
install 0
rm -f "$COPY"
run "$T/note.json"
refused 'no copy in dotfiles' 'claude/hooks/vault/check_note.py'

# The checker finds the Vault root from __file__, so a Vault checker that is a link to an identical
# file elsewhere would move that root and silently skip every note. The hook refuses such a checker.
install 0
cp "$COPY" "$T/a/b/check_note.py"
ln -sf "$T/a/b/check_note.py" "$CHECKER"
run "$T/note.json"
refused 'Vault checker that is a link to an identical file elsewhere' 'symlink'

# In the Vault, a missing checker is reported (it can vanish, or not be synced to this machine),
# while other projects without a checker stay silent (the cases above).
install 0
rm -f "$CHECKER"
run "$T/note.json"
refused 'Vault without the checker' 'syncUnderscoreItems'
mkdir "$CHECKER"
run "$T/note.json"
refused 'Vault checker that is a directory' 'syncUnderscoreItems'
rmdir "$CHECKER"
run "$T/note.json" DEVELOPER_DIR="$T/nodev"
refused 'Vault without the checker on a Mac without the Command Line Tools' 'xcode-select --install'
head -c 300000 /dev/zero | (cd "$V" && env CLAUDE_PROJECT_DIR="$V" HOME="$TEST_HOME" "$BASH" "$HOOK" >/dev/null 2>&1)
codes=("${PIPESTATUS[@]}")
if [ "${codes[0]}" = 0 ]; then
  ok 'large input is read to the end (Vault without the checker)'
else
  ng "[want writer 0, got ${codes[0]}] large input is read to the end (Vault without the checker)"
fi

# A profile that sandbox-exec cannot use stops the check with exit 2 instead of passing silently.
install 0
cp "$HOOK" "$H/check-vault-note.py" "$T/badhooks/"
cp "$COPY" "$T/badhooks/vault/check_note.py"
printf '(version 1)\n(this is not a valid rule\n' >"$T/badhooks/check-vault-note.sb"
(cd "$V" && env CLAUDE_PROJECT_DIR="$V" HOME="$TEST_HOME" "$BASH" "$T/badhooks/check-vault-note.sh" <"$T/note.json" >"$T/out" 2>"$T/err")
rc=$?
err=$(<"$T/err")
if [ "$rc" = 2 ] && [[ "$err" != *CHECKER* ]]; then
  ok '[2] a profile that sandbox-exec rejects ends with exit 2'
else
  ng "[want 2 and no run, got $rc, err='$err'] a profile that sandbox-exec rejects ends with exit 2"
fi

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
(cd "$T/readonly" && env CLAUDE_PROJECT_DIR="$V" HOME="$TEST_HOME" TMPDIR="$T/readonly" "$BASH" "$HOOK" <"$T/note.json" >"$T/out" 2>"$T/err")
rc=$?
out=$(<"$T/out")
err=$(<"$T/err")
refused 'runs without a writable temporary directory' 'claude/hooks/vault/check_note.py'
chmod 755 "$T/readonly"

# Claude Code writes the whole input; a hook that exits without reading it breaks the pipe once
# the input outgrows the buffer. Cover the early exit, the Python part and the no-tools exit.
install 0
for case in "early exit:CLAUDE_PROJECT_DIR=$T/plain" "python:CLAUDE_PROJECT_DIR=$V" "no tools:DEVELOPER_DIR=$T/nodev"; do
  head -c 300000 /dev/zero | (cd "$V" && env CLAUDE_PROJECT_DIR="$V" HOME="$TEST_HOME" "${case#*:}" "$BASH" "$HOOK" >/dev/null 2>&1)
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

# no_secret <desc> <marker>: the last run did not read the note and did not print <marker>.
no_secret() {
  if [[ "$err" == *NOTE-DENIED* ]] && [[ "$err" != *"$2"* ]]; then
    ok "$1"
  else
    ng "$1 (rc=$rc, err='$err')"
  fi
}

if [ "$seatbelt" = 1 ]; then
  # An approved checker runs on the note; its report reaches Claude only through stderr and exit 2.
  install 1
  run "$T/note.json"
  if [ "$rc" = 2 ] && [ -z "$out" ] && [[ "$err" == *"CHECKER root=$REAL_V argv=$NOTE"* ]]; then
    ok '[2] checker exit 1 is reported on stderr, with the Vault root from __file__ and the note as argument'
  else
    ng "[want 2, the checker output on stderr only, got $rc, out='$out', err='$err'] checker exit 1 is reported on stderr"
  fi
  # The Vault checker is a .py file, which Seatbelt does not let the checker read, so a run here
  # also shows that the copy in dotfiles runs, not the file at the Vault path.
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
  if [[ "$err" == *FORK-DENIED* ]] && [[ "$err" == *EXEC-DENIED* ]]; then
    ok 'checker cannot fork or run another program'
  else
    ng "checker cannot fork or run another program (err='$err')"
  fi

  # Output reaches Claude as hook feedback, so each message stays on one line, with control
  # characters escaped, under a header that marks it as data.
  esc=$(printf '\033')
  injected=0
  while IFS= read -r line; do
    [ "$line" = 'INJECTED-LINE' ] && injected=1
  done <<<"$err"
  if [[ "$err" == *'MULTI-A\nINJECTED-LINE'* ]] && [ "$injected" = 0 ] && [[ "$err" != *"$esc"* ]] && [[ "$err" == *点検スクリプトの出力* ]]; then
    ok 'checker output keeps one line per message, escapes control characters and has a header'
  else
    ng "checker output keeps one line per message, escapes control characters and has a header (err='$err')"
  fi
  # Every message line starts with a fixed mark, so a quoted "# ..." cannot become a heading.
  heading=0
  while IFS= read -r line; do
    case "$line" in '#'*) heading=1 ;; esac
  done <<<"$err"
  if [[ "$err" == *'- # HEADING-LIKE'* ]] && [ "$heading" = 0 ]; then
    ok 'no output line starts with #'
  else
    ng "no output line starts with # (err='$err')"
  fi

  # Notes that point outside the Vault, or at files in the Vault that are not .md, are not read.
  ln -sf "$T/outside/secret.md" "$V/notes/out.md"
  input out "$V/notes/out.md"
  run "$T/out.json"
  no_secret 'note linked to a file outside the Vault is not read' OUTSIDE-SECRET
  ln -sf "$V/notes/secret.txt" "$V/notes/txt.md"
  input txtlink "$V/notes/txt.md"
  run "$T/txtlink.json"
  no_secret 'note linked to a file in the Vault that is not .md is not read' VAULT-TXT-SECRET
  # .md files in the Vault under names the sandbox's denyRead covers are not read either.
  ln -sf "$V/secrets/s.md" "$V/notes/sec.md"
  input sec "$V/notes/sec.md"
  run "$T/sec.json"
  no_secret 'note linked to a .md under secrets/ in the Vault is not read' VAULT-SECRETS-MD
  ln -sf "$V/keys/id_rsa.md" "$V/notes/key.md"
  input key "$V/notes/key.md"
  run "$T/key.json"
  no_secret 'note linked to an id_rsa*.md in the Vault is not read' VAULT-KEY-MD
  # Plugin folders hold credentials. Claude Code's sandbox cannot create a .obsidian folder anywhere,
  # so this fixture is made only here, where the test runs outside that sandbox.
  mkdir -p "$V/.obsidian/plugins/p"
  printf '# VAULT-PLUGIN-MD\n' >"$V/.obsidian/plugins/p/README.md"
  ln -sf "$V/.obsidian/plugins/p/README.md" "$V/notes/plugin.md"
  input plugin "$V/notes/plugin.md"
  run "$T/plugin.json"
  no_secret 'note linked to a .md under .obsidian/plugins/ in the Vault is not read' VAULT-PLUGIN-MD
  # Files outside $HOME and the temporary directories are not read either (reads are denied by default).
  # The shared folder of all users is writable by everyone. (The path is split so that the repository
  # check does not take "Shared" for a user name.)
  users_dir=/Users
  SHARED_FILE=$(mktemp "$users_dir/Shared/.check-vault-note-test.XXXXXX") && printf '# SHARED-SECRET\n' >"$SHARED_FILE"
  ln -sf "$SHARED_FILE" "$V/notes/shared.md"
  input shared "$V/notes/shared.md"
  run "$T/shared.json"
  if [ -n "$SHARED_FILE" ]; then
    no_secret 'note linked to a file in the shared folder of all users is not read' SHARED-SECRET
  else
    ng 'note linked to a file in the shared folder of all users is not read (could not create the file)'
  fi
  HOME_FILE=$(mktemp "$HOME/.check-vault-note-test.XXXXXX") && printf '# HOME-SECRET\n' >"$HOME_FILE"
  ln -sf "$HOME_FILE" "$V/notes/home.md"
  input home "$V/notes/home.md"
  run "$T/home.json"
  no_secret 'note linked to a file under HOME is not read' HOME-SECRET
  # The same file through other names: the firmlink of the data volume, and another letter case.
  ln -sf "/System/Volumes/Data$HOME_FILE" "$V/notes/firmlink.md"
  input firmlink "$V/notes/firmlink.md"
  run "$T/firmlink.json"
  no_secret 'note linked to a file under HOME through /System/Volumes/Data is not read' HOME-SECRET
  ln -sf "$(printf '%s' "$HOME_FILE" | tr '[:lower:]' '[:upper:]')" "$V/notes/case.md"
  input case "$V/notes/case.md"
  run "$T/case.json"
  no_secret 'note linked to a file under HOME in another letter case is not read' HOME-SECRET

  # A read that Seatbelt denies ends the check with a fixed message, not a traceback.
  ln -sf "$T/outside/secret.md" "$V/notes/raw.md"
  input raw "$V/notes/raw.md"
  run "$T/raw.json"
  if [ "$rc" = 2 ] && [[ "$err" == *読めない* ]] && [[ "$err" != *Traceback* ]] && [[ "$err" != *OUTSIDE-SECRET* ]]; then
    ok '[2] a denied read is reported with a fixed message'
  else
    ng "[want 2 and a fixed message, got $rc, err='$err'] a denied read is reported with a fixed message"
  fi

  # Modules planted on PYTHONPATH, next to the checker or in the working directory are not imported.
  install 0
  for dir in "$SCRIPTS" "$V"; do
    cp "$T/pp/re.py" "$dir/re.py"
  done
  run "$T/note.json" PYTHONPATH="$T/pp"
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
