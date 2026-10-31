#!/usr/bin/env bash
# Regression tests for protect-main-branch.sh.
# Usage: test-protect-main-branch.sh [hook-path]
# shellcheck disable=SC2016 # commands with unexpanded variables are test input
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../protect-main-branch.sh}"

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
MAIN="$T/main-repo"
FEAT="$T/feat-repo"

git init -q -b main "$MAIN"
git init -q -b main "$FEAT"
git -C "$FEAT" switch -q -c feature/x

pass=0
fail=0

# check <expected-exit> <cwd> <command> [description]
check() {
  local expected="$1" cwd="$2" cmd="$3" desc="${4:-$3}"
  local input actual
  input=$(jq -n --arg cmd "$cmd" --arg cwd "$cwd" '{tool_input: {command: $cmd}, cwd: $cwd}')
  HOME="$T" bash "$HOOK" <<<"$input" >/dev/null 2>&1
  actual=$?
  if [ "$actual" = "$expected" ]; then
    pass=$((pass + 1))
    echo "PASS [$expected] $desc"
  else
    fail=$((fail + 1))
    echo "FAIL [want $expected, got $actual] $desc"
  fi
}

# Commit in the hook's cwd
check 0 "$FEAT" 'git commit -m x' 'commit in cwd on feature branch'
check 2 "$MAIN" 'git commit -m x' 'commit in cwd on main'
check 0 "$MAIN" 'git status' 'non-commit command'

# git -C selects the repository
check 2 "$MAIN" "git -C $FEAT commit -m x" '-C to feature repo from main cwd (cwd is still checked)'
check 2 "$FEAT" "git -C $MAIN commit -m x" '-C to main repo from feature cwd'
check 2 "$T" 'git -C main-repo commit -m x' 'relative -C to main repo'
check 0 "$T" 'git -C feat-repo commit -m x' 'relative -C to feature repo'
check 2 "$FEAT" 'git -C ~/main-repo commit -m x' 'tilde -C to main repo'
check 2 "$FEAT" "git -C '$MAIN' commit -m x" 'single-quoted -C path'
check 2 "$FEAT" "git -C \"$MAIN\" commit -m x" 'double-quoted -C path'
check 2 "$FEAT" "git -C $T -C main-repo commit -m x" 'multiple -C are cumulative'
check 2 "$FEAT" "git -c user.name=x -C $MAIN commit -m x" '-c before -C'

# cd before the commit selects the repository
check 2 "$MAIN" "cd $FEAT && git commit -m x" 'cd to feature repo from main cwd (cwd is still checked)'
check 2 "$FEAT" "cd $MAIN && git commit -m x" 'cd to main repo from feature cwd'
check 2 "$FEAT" "cd $MAIN; git commit -m x" 'cd with semicolon'
check 2 "$FEAT" "cd $MAIN"$'\n'"git commit -m x" 'cd on a previous line'
check 2 "$FEAT" "(cd $MAIN && git commit)" 'cd in a subshell'
check 2 "$FEAT" "cd $MAIN && git commit; echo done" 'commit followed by semicolon'

# -C on another git command does not apply to the commit
check 0 "$FEAT" "git -C $MAIN status && git commit -m x" '-C on preceding non-commit git'
check 2 "$MAIN" "git -C $FEAT status && git commit -m x" '-C on preceding non-commit git (main cwd)'
check 0 "$FEAT" 'git -C "$REPO" status && git commit -m x' 'unresolvable -C on non-commit git'

# Every commit is checked, not only the first one
check 2 "$FEAT" "git commit -m x; git -C $MAIN commit -m y" 'second commit to main repo'

# Misparsed context never skips the cwd check
check 2 "$MAIN" "git -C $FEAT commit -m x; git commit -m y" 'commit in main cwd after -C commit'
check 2 "$MAIN" "(cd $FEAT && true); git commit -m x" 'cd in a finished subshell'
check 2 "$MAIN" "true || cd $FEAT; git commit -m x" 'cd in a skipped branch'
check 2 "$MAIN" "cd $FEAT | true; git commit -m x" 'cd in a pipeline'
check 2 "$MAIN" "echo \"Run git -C $FEAT commit -m x\"; git commit -m x" 'git commit text in a preceding argument'
check 2 "$MAIN" "git -C $FEAT --git-dir=$MAIN/.git --work-tree=$MAIN commit -m x" '--git-dir with -C'

# An early match on a long command does not fail open (SIGPIPE under pipefail)
check 2 "$MAIN" "git commit -m x"$'\n'"# $(printf '%0300000d' 0)" 'long line after commit'

# Text after `commit` (the message) does not change the repository
check 0 "$FEAT" "git commit -m \"cd $MAIN && git -C $MAIN commit\"" 'paths inside commit message'
check 0 "$FEAT" "git commit -m \"\$(cat <<'EOF'"$'\n'"feat: x"$'\n\n'"cd $MAIN"$'\n'"EOF"$'\n'")\"" 'heredoc commit message'

# Heredocs and `<<` do not hide a commit
check 2 "$FEAT" "cat > /dev/null <<EOF"$'\n'"text"$'\n'"EOF"$'\n'"git -C $MAIN commit -m x" 'commit after a heredoc'
check 2 "$FEAT" "grep -q x <<<\"\$v\"; git -C $MAIN commit -m x" 'here-string is not a heredoc'
check 2 "$FEAT" "printf '%s\n' \"<<EOF\""$'\n'"git -C $MAIN commit -m x" '<< in a string'
check 2 "$FEAT" "cat <<EOF ; git -C $MAIN commit -m x"$'\n'"text"$'\n'"EOF" 'commit on the heredoc start line'
check 2 "$FEAT" "cat <<EOF"$'\n'"\$( git -C $MAIN commit -m x )"$'\n'"EOF" 'command substitution in an unquoted heredoc'

# Unresolvable repository is blocked (fail closed)
check 2 "$FEAT" 'git -C "$REPO" commit -m x' 'variable in -C'
check 2 "$FEAT" 'cd "$REPO" && git commit -m x' 'variable in cd'
check 2 "$FEAT" "git -C $T/missing commit -m x" 'nonexistent -C directory'

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
