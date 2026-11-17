#!/usr/bin/env bash
# Regression tests for guard-additional-dirs.sh.
# Usage: test-guard-additional-dirs.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../guard-additional-dirs.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-guard-additional-dirs.XXXXXX") || {
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

# The hook ignores its input, but Claude Code always sends one.
INPUT="$T/input.json"
printf '%s\n' '{"tool_name":"Write","tool_input":{"file_path":"x"}}' >"$INPUT"

# check <expected-exit> <description> <home>
check() {
  local expected="$1" desc="$2" home="$3" actual
  HOME="$home" "$BASH" "$HOOK" <"$INPUT" >/dev/null 2>"$T/err"
  actual=$?
  if [ "$actual" = "$expected" ]; then
    ok "[$expected] $desc"
  else
    ng "[want $expected, got $actual] $desc"
  fi
}

# newhome <name>: create an empty home directory and print its path.
newhome() {
  mkdir -p "$T/$1" && printf '%s\n' "$T/$1"
}

# Ordinary states pass
H=$(newhome real)
mkdir -p "$H/.gstack/projects"
check 0 'real directory' "$H"
H=$(newhome missing)
check 0 'no ~/.gstack' "$H"
H=$(newhome parent-only)
mkdir -p "$H/.gstack"
check 0 'no ~/.gstack/projects' "$H"
# $TMPDIR on macOS is under /var, itself a symlink; this case makes the link explicit.
mkdir -p "$T/home-real/.gstack/projects"
ln -s "$T/home-real" "$T/home-link"
check 0 'HOME through a symlink' "$T/home-link"

# A redirected ~/.gstack/projects is blocked
mkdir -p "$T/elsewhere"
H=$(newhome symlink)
mkdir -p "$H/.gstack"
ln -s "$T/elsewhere" "$H/.gstack/projects"
check 2 'symlink' "$H"
err=$(<"$T/err")
case "$err" in
  Blocked:*.gstack/projects*) ok 'message starts with Blocked: and names the path' ;;
  *) ng "message starts with Blocked: and names the path (got '$err')" ;;
esac
H=$(newhome dangling)
mkdir -p "$H/.gstack"
ln -s "$T/none" "$H/.gstack/projects"
check 2 'dangling symlink' "$H"
mkdir -p "$T/other/projects"
H=$(newhome parent-symlink)
ln -s "$T/other" "$H/.gstack"
check 2 'parent ~/.gstack is a symlink' "$H"
H=$(newhome file)
mkdir -p "$H/.gstack"
: >"$H/.gstack/projects"
check 2 'regular file' "$H"

# Without a usable HOME, nothing can be checked (fail closed)
check 2 'empty HOME' ''
check 2 'HOME does not exist' "$T/nonexistent"
env -u HOME "$BASH" "$HOOK" <"$INPUT" >/dev/null 2>&1
actual=$?
if [ "$actual" = 2 ]; then
  ok '[2] unset HOME'
else
  ng "[want 2, got $actual] unset HOME"
fi

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
