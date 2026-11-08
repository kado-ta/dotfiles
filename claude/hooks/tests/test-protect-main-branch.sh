#!/usr/bin/env bash
# Regression tests for protect-main-branch.sh.
# Usage: test-protect-main-branch.sh [hook-path]
# shellcheck disable=SC2016 # commands with unexpanded variables are test input
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
HOOK="${1:-${SCRIPT_DIR}/../protect-main-branch.sh}"

# Use an explicit template: plain `mktemp -d` ignores TMPDIR on macOS.
T=$(mktemp -d "${TMPDIR:-/tmp}/test-protect-main-branch.XXXXXX") || {
  echo "mktemp failed" >&2
  exit 1
}
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
  HOME="$T" PATH="${HOOK_PATH:-$PATH}" "$BASH" "$HOOK" <<<"$input" >/dev/null 2>&1
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
check 2 "$FEAT" 'git switch -c y && git commit -m x' 'branch creation and commit in one command on feature branch'
check 2 "$FEAT" 'git checkout main && git commit -m x' 'switching branches before a commit in the same call'
check 0 "$FEAT" 'git commit -m x && git switch main' 'switching branches after a commit'
check 2 "$FEAT" 'git rebase feature/x main && git commit -m x' 'rebase before a commit in the same call'
check 0 "$FEAT" 'git commit -m x && git rebase main' 'rebase after a commit'

# 同名のタグがあると symbolic-ref --short は heads/main を返す
TAGGED="$T/tagged-repo"
git init -q -b main "$TAGGED"
git -C "$TAGGED" -c user.name=t -c user.email=t@example.com -c commit.gpgsign=false commit -q --allow-empty -m init
git -C "$TAGGED" tag main
check 2 "$TAGGED" 'git commit -m x' 'commit on main with a tag of the same name'

# 大文字・小文字を区別しないファイルシステムでは、refs/heads/MAIN も main と同じファイルを更新する
UPPER="$T/upper-repo"
git init -q -b main "$UPPER"
git -C "$UPPER" symbolic-ref HEAD refs/heads/MAIN
check 2 "$UPPER" 'git commit -m x' 'commit with HEAD on a case variant of main'

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

# Separators without surrounding spaces
check 2 "$FEAT" 'git checkout main&&git commit -m x' 'switching branches before a commit without spaces around &&'
check 2 "$FEAT" 'git checkout main;git commit -m x' 'switching branches before a commit without spaces around ;'
check 2 "$FEAT" "cd $MAIN&&git commit -m x" 'cd to main repo without spaces around &&'
check 0 "$FEAT" "cd $FEAT&&git commit -m x" 'cd to feature repo without spaces around &&'
check 0 "$FEAT" 'git commit -m x&&git switch main' 'switching branches after a commit without spaces'
check 0 "$FEAT" 'git commit -m "a;b&&c" 2>&1' 'separators inside a message and a redirect'

# -C on another git command does not apply to the commit
check 0 "$FEAT" "git -C $MAIN status && git commit -m x" '-C on preceding non-commit git'
check 2 "$MAIN" "git -C $FEAT status && git commit -m x" '-C on preceding non-commit git (main cwd)'
check 0 "$FEAT" 'git -C "$REPO" status && git commit -m x' 'unresolvable -C on non-commit git'

# Every commit is checked, not only the first one
check 2 "$FEAT" "git commit -m x; git -C $MAIN commit -m y" 'second commit to main repo'

# Commits through git aliases are checked too
git -C "$MAIN" config alias.cm commit
git -C "$MAIN" config alias.sc '!git commit'
git -C "$MAIN" config alias.st status
git -C "$FEAT" config alias.cm commit
check 2 "$MAIN" 'git cm -m x' 'alias of commit on main'
check 2 "$MAIN" 'git sc -m x' 'shell alias of commit on main'
check 2 "$MAIN" 'git -c alias.c=commit c -m x' 'alias given with -c on main'
check 2 "$FEAT" "git -C $MAIN cm -m x" 'alias of commit to main repo'
check 0 "$FEAT" 'git cm -m x' 'alias of commit on feature branch'
check 0 "$MAIN" 'git st' 'alias of a non-commit command on main'
# Aliases are looked up in the repository the command runs in
git -C "$MAIN" config alias.mainonly commit
check 2 "$FEAT" "git -C $MAIN mainonly -m x" 'alias defined only in the target repository'
check 2 "$FEAT" 'git -C "$REPO" mainonly -m x' 'possible alias in an unresolvable repository'
check 0 "$FEAT" 'git -C "$REPO" status' 'built-in command in an unresolvable repository'
# Aliases of aliases are followed, and alias names are case-insensitive
git -C "$MAIN" config alias.outer inner
git -C "$MAIN" config alias.inner commit
git -C "$MAIN" config alias.loopa loopb
git -C "$MAIN" config alias.loopb loopa
git -C "$MAIN" config alias.st2 st
check 2 "$MAIN" 'git -c alias.inner2=commit -c alias.outer2=inner2 outer2 -m x' 'alias chain given with -c'
check 2 "$MAIN" 'git outer -m x' 'alias chain in the config'
check 2 "$MAIN" 'git loopa' 'alias loop is treated as a commit'
check 0 "$MAIN" 'git st2' 'alias chain to a non-commit command'
check 2 "$MAIN" 'git CM -m x' 'alias name in upper case'
check 2 "$MAIN" "git -c 'alias.qc=commit' qc -m x" 'quoted -c alias'
git -C "$MAIN" config alias.addcm '!git add -A && git commit'
check 2 "$MAIN" 'git addcm -m x' 'shell alias is treated as a commit'
git -C "$FEAT" config alias.co checkout
check 2 "$FEAT" 'git co main && git commit -m x' 'alias of checkout before a commit'
check 2 "$FEAT" 'git -c alias.rb=rebase rb feature/x main && git commit -m x' 'alias of rebase before a commit'
# Aliases starting with an option cannot be analyzed, so they are treated as commits
git -C "$MAIN" config alias.optcm '-c user.name=x commit'
check 2 "$MAIN" 'git optcm -m x' 'alias starting with an option'
check 2 "$MAIN" 'git -c "alias.oc=-c user.name=x commit" oc -m y' 'double-quoted -c alias with spaces'
check 2 "$MAIN" "git -c 'alias.oc=-c user.name=x commit' oc -m y" 'single-quoted -c alias with spaces'
check 0 "$FEAT" 'git -c "alias.oc=-c user.name=x commit" oc -m y' 'quoted -c alias with spaces on feature branch'
check 2 "$FEAT" "git -c \"user.name=a b\" -C $MAIN commit -m x" 'quoted -c value with spaces before -C'

# Misparsed context never skips the cwd check
check 2 "$MAIN" '(git commit -m x)' 'commit at the start of a subshell'
check 2 "$MAIN" '`git commit -m x`' 'commit in backticks'
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

# A broken or missing jq blocks every command, because it cannot be inspected (fail closed)
BROKEN_JQ="$T/broken-jq"
NO_JQ="$T/no-jq"
BROKEN_CAT="$T/broken-cat"
mkdir -p "$BROKEN_JQ" "$NO_JQ" "$BROKEN_CAT"
printf '#!/bin/sh\nexit 1\n' >"$BROKEN_JQ/jq"
printf '#!/bin/sh\nexit 1\n' >"$BROKEN_CAT/cat"
chmod +x "$BROKEN_JQ/jq" "$BROKEN_CAT/cat"
for tool in cat git grep; do
  ln -s "$(command -v "$tool")" "$NO_JQ/$tool"
done

HOOK_PATH="$BROKEN_JQ:$PATH" check 2 "$MAIN" 'git commit -m x' 'broken jq: commit on main'
HOOK_PATH="$BROKEN_JQ:$PATH" check 2 "$FEAT" 'git commit -m x' 'broken jq: commit on feature branch'
HOOK_PATH="$BROKEN_JQ:$PATH" check 2 "$FEAT" 'git status' 'broken jq: non-commit command'
HOOK_PATH="$NO_JQ" check 2 "$MAIN" 'git commit -m x' 'missing jq: commit on main'
HOOK_PATH="$NO_JQ" check 2 "$FEAT" 'git status' 'missing jq: non-commit command'

# Other unexpected failures are blocked too, not only jq
HOOK_PATH="$BROKEN_CAT:$PATH" check 2 "$FEAT" 'git status' 'broken cat: stdin cannot be read'
# A failing grep or sed is not taken as "no commit"
BROKEN_GREP="$T/broken-grep"
BROKEN_SED="$T/broken-sed"
mkdir -p "$BROKEN_GREP" "$BROKEN_SED"
printf '#!/bin/sh\nexit 2\n' >"$BROKEN_GREP/grep"
printf '#!/bin/sh\nexit 1\n' >"$BROKEN_SED/sed"
chmod +x "$BROKEN_GREP/grep" "$BROKEN_SED/sed"
HOOK_PATH="$BROKEN_GREP:$PATH" check 2 "$MAIN" 'git commit -m x' 'broken grep: commit on main'
HOOK_PATH="$BROKEN_GREP:$PATH" check 2 "$FEAT" 'git status' 'broken grep: non-commit command'
HOOK_PATH="$BROKEN_SED:$PATH" check 2 "$FEAT" "git -C $MAIN commit -m x" 'broken sed: commit to main repo'
# A failing git is not taken as "not on a protected branch", but a detached HEAD is not a branch
BROKEN_GIT="$T/broken-git"
DETACHED="$T/detached-repo"
mkdir -p "$BROKEN_GIT"
printf '#!/bin/sh\nexit 128\n' >"$BROKEN_GIT/git"
chmod +x "$BROKEN_GIT/git"
git init -q -b main "$DETACHED"
git -C "$DETACHED" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m init
git -C "$DETACHED" switch -q --detach
HOOK_PATH="$BROKEN_GIT:$PATH" check 2 "$MAIN" 'git commit -m x' 'broken git: commit on main'
HOOK_PATH="$BROKEN_GIT:$PATH" check 2 "$FEAT" 'git commit -m x' 'broken git: commit on feature branch'
check 0 "$DETACHED" 'git commit -m x' 'commit on a detached HEAD'

# The block message tells how to recover
message=$(HOME="$T" PATH="$BROKEN_JQ:$PATH" "$BASH" "$HOOK" <<<'{}' 2>&1 >/dev/null)
if [[ "$message" == *'mise trust'* ]]; then
  pass=$((pass + 1))
  echo "PASS block message mentions the recovery"
else
  fail=$((fail + 1))
  echo "FAIL block message mentions the recovery: $message"
fi

# Creating a branch in the same command does not help on main, and the message says so
# check_hint <expected: yes|no> <command> [description]
check_hint() {
  local expected="$1" cmd="$2" desc="${3:-$2}" input message actual=no
  input=$(jq -n --arg cmd "$cmd" --arg cwd "$MAIN" '{tool_input: {command: $cmd}, cwd: $cwd}')
  message=$(HOME="$T" "$BASH" "$HOOK" <<<"$input" 2>&1 >/dev/null)
  [[ "$message" == *'別の Bash 呼び出し'* ]] && actual=yes
  if [ "$actual" = "$expected" ]; then
    pass=$((pass + 1))
    echo "PASS [hint $expected] $desc"
  else
    fail=$((fail + 1))
    echo "FAIL [want hint $expected, got $actual] $desc"
  fi
}
check_hint yes 'git switch -c x && git commit -m x'
check_hint yes 'git checkout -b x; git commit -m x'
check_hint yes "git -C $MAIN switch --create x"$'\n'"git -C $MAIN commit -m x" 'switch --create with -C on a previous line'
check_hint no 'git commit -m x'

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
