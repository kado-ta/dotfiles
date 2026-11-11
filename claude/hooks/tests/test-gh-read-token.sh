#!/usr/bin/env bash
# Regression tests for gh-read-token.sh.
# Usage: test-gh-read-token.sh [hook-path]
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../gh-read-token.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-gh-read-token.XXXXXX") || {
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

# The hook reads tokens from $HOME/.config/cc-gh-read, and the installed line runs it from $HOME/.claude/hooks.
export HOME="$T/home"
TOKENS="$HOME/.config/cc-gh-read"
mkdir -p "$TOKENS" "$HOME/.claude/hooks"
cp "$HOOK" "$HOME/.claude/hooks/gh-read-token.sh"
KADO=github_pat_kadota_0123456789abcdef
ORG=github_pat_org_0123456789abcdef
printf '%s\n' "$KADO" >"$TOKENS/kado-ta.token"
printf '%s\n' "$ORG" >"$TOKENS/exampleorg.token"

# repo <dir> [origin-url]
repo() {
  mkdir -p "$1"
  git -C "$1" init -q
  [ -z "${2:-}" ] || git -C "$1" remote add origin "$2"
}

# token <expected> <dir> <description>
token() {
  local expected="$1" dir="$2" desc="$3" actual code
  actual=$(cd "$dir" && "$BASH" "$HOOK" 2>&1)
  code=$?
  if [ "$code" = 0 ] && [ "$actual" = "$expected" ]; then
    ok "$desc"
  else
    ng "$desc (exit $code, got '$actual')"
  fi
}

# The token of the owner of origin is printed
repo "$T/kado" git@github.com:kado-ta/dotfiles.git
token "$KADO" "$T/kado" 'scp-style SSH origin'
mkdir -p "$T/kado/sub/dir"
token "$KADO" "$T/kado/sub/dir" 'subdirectory'
repo "$T/org" https://github.com/ExampleOrg/example.git
token "$ORG" "$T/org" 'HTTPS origin, owner in mixed case'
repo "$T/sshurl" ssh://git@github.com/kado-ta/example.git
token "$KADO" "$T/sshurl" 'ssh:// origin'
repo "$T/noext" https://github.com/kado-ta/example
token "$KADO" "$T/noext" 'origin without .git'

# Anything else prints nothing, so gh stays unauthenticated (fail closed)
repo "$T/other" git@github.com:someone/example.git
token '' "$T/other" 'owner without a token'
repo "$T/gitlab" git@gitlab.com:kado-ta/example.git
token '' "$T/gitlab" 'another host'
repo "$T/lookalike-ssh" git@github.com.evil.example:kado-ta/example.git
token '' "$T/lookalike-ssh" 'look-alike SSH host'
repo "$T/lookalike-https" https://github.com.evil.example/kado-ta/example.git
token '' "$T/lookalike-https" 'look-alike HTTPS host'
repo "$T/traversal" git@github.com:../example.git
token '' "$T/traversal" 'owner with a path traversal'
repo "$T/encoded" https://github.com/kado-ta%2F..%2Fx/example.git
token '' "$T/encoded" 'owner with encoded characters'
repo "$T/localpath" kado-ta/example
token '' "$T/localpath" 'local path origin'
printf '%s\n' "$KADO" >"$TOKENS/kado.ta.token"
repo "$T/dotted" git@github.com:kado.ta/example.git
token '' "$T/dotted" 'owner with characters GitHub does not allow'
repo "$T/noorigin"
token '' "$T/noorigin" 'repository without origin'
mkdir -p "$T/plain"
token '' "$T/plain" 'not a repository'

# Token files that are not plain token text are ignored
ln -s "$TOKENS/kado-ta.token" "$TOKENS/linked.token"
repo "$T/linked" git@github.com:linked/example.git
token '' "$T/linked" 'symlinked token file'
printf 'bad token\nX-Evil: 1\n' >"$TOKENS/broken.token"
repo "$T/broken" git@github.com:broken/example.git
token '' "$T/broken" 'token file with other text'
: >"$TOKENS/empty.token"
repo "$T/empty" git@github.com:empty/example.git
token '' "$T/empty" 'empty token file'

# install appends the line once and keeps what other hooks wrote
env_file="$T/env"
printf 'export OTHER=1\n' >"$env_file"
CLAUDE_ENV_FILE="$env_file" "$BASH" "$HOOK" install
code1=$?
CLAUDE_ENV_FILE="$env_file" "$BASH" "$HOOK" install
code2=$?
if [ "$code1" = 0 ] && [ "$code2" = 0 ] && [ "$(grep -c 'gh-read-token.sh' "$env_file")" = 1 ] && grep -qx 'export OTHER=1' "$env_file"; then
  ok 'install appends the line once'
else
  ng 'install appends the line once'
fi

if (unset CLAUDE_ENV_FILE; "$BASH" "$HOOK" install); then
  ok 'install without CLAUDE_ENV_FILE does nothing'
else
  ng 'install without CLAUDE_ENV_FILE does nothing'
fi

# The installed line picks the token for the directory each command runs in
# envtoken <expected> <dir> <description>
envtoken() {
  local actual
  actual=$(cd "$2" && env -i HOME="$HOME" PATH="$PATH" GH_TOKEN=inherited "$BASH" -c ". '$env_file'; printf '%s' \"\$GH_TOKEN\"")
  if [ "$actual" = "$1" ]; then
    ok "$3"
  else
    ng "$3 (got '$actual')"
  fi
}
envtoken "$KADO" "$T/kado" 'env line: kado-ta repository'
envtoken "$ORG" "$T/org" 'env line: another owner'
envtoken '' "$T/other" 'env line: no token replaces an inherited GH_TOKEN with empty'

# gh falls back to these when GH_TOKEN is empty, so the line drops them
actual=$(cd "$T/other" && env -i HOME="$HOME" PATH="$PATH" GITHUB_TOKEN=w GH_ENTERPRISE_TOKEN=w GITHUB_ENTERPRISE_TOKEN=w \
  "$BASH" -c ". '$env_file'; printf '%s|%s|%s' \"\${GITHUB_TOKEN-unset}\" \"\${GH_ENTERPRISE_TOKEN-unset}\" \"\${GITHUB_ENTERPRISE_TOKEN-unset}\"")
if [ "$actual" = 'unset|unset|unset' ]; then
  ok 'env line: other GitHub tokens are unset'
else
  ng "env line: other GitHub tokens are unset (got '$actual')"
fi

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
