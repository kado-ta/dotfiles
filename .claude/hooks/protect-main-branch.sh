#!/bin/bash
# Prevent git commit on main/master/staging branch.
# Used as a Claude Code PreToolUse hook for the Bash tool.
# Exit code 2 blocks the tool execution and shows stderr to Claude.

set -euo pipefail

if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only check git commit commands (including `git -C <path> commit` form)
# Use a here-string, not a pipe: `grep -q` exits on the first match, and the writer's SIGPIPE
# would fail the pipeline under pipefail and skip the check.
if ! grep -qE '(^|\s|&&|\||\;)git(\s+\S+)*\s+commit(\s|$|[;&|)])' <<<"$COMMAND"; then
  exit 0
fi

# Determine the working directory from hook input, fallback to CLAUDE_PROJECT_DIR
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CWD="${CWD:-${CLAUDE_PROJECT_DIR:-}}"

if [ -z "$CWD" ]; then
  exit 0
fi

block_unresolved() {
  echo "BLOCKED: Cannot resolve the repository of git commit ('$1'). Use a literal path without variables or spaces." >&2
  exit 2
}

# Resolve a path token from the command against a base directory.
# Fails if the token cannot be resolved statically (variables, quotes, missing dir).
resolve_path() {
  local base="$1" path="$2"
  case "$path" in
    \'*\' | \"*\") path="${path:1:${#path}-2}" ;;
  esac
  # shellcheck disable=SC2088 # match a literal tilde from the command text
  case "$path" in
    '' | -* | *\$* | *\`* | *\'* | *\"*) return 1 ;;
    '~') path="$HOME" ;;
    '~/'*) path="$HOME/${path#\~/}" ;;
  esac
  case "$path" in
    /*) ;;
    *) path="$base/$path" ;;
  esac
  [ -d "$path" ] || return 1
  echo "$path"
}

# Resolve the repository of every git commit invocation from the `cd <dir>` commands
# before it and its `-C <dir>` options. Tokens are split on whitespace, so this is a heuristic.
set -f
# shellcheck disable=SC2206
TOKENS=(${COMMAND//$'\n'/ ; })
set +f
CD_PATHS=()
C_PATHS=()
TARGETS=()
COMMAND_START=1
i=0
while [ "$i" -lt "${#TOKENS[@]}" ]; do
  token="${TOKENS[$i]#(}"
  case "$token" in
    '&&' | '||' | ';' | '|' | '&')
      COMMAND_START=1
      i=$((i + 1))
      continue
      ;;
  esac
  if [ "$token" = "cd" ] && [ "$COMMAND_START" -eq 1 ]; then
    path="${TOKENS[$((i + 1))]:-}"
    path="${path%)}"
    COMMAND_START=0
    case "$path" in *';') COMMAND_START=1 ;; esac
    CD_PATHS+=("${path%;}")
    i=$((i + 2))
    continue
  fi
  COMMAND_START=0
  case "$token" in *';') COMMAND_START=1 ;; esac
  i=$((i + 1))
  [ "$token" = "git" ] || continue

  C_PATHS=()
  while [ "$i" -lt "${#TOKENS[@]}" ]; do
    case "${TOKENS[$i]}" in
      -C)
        C_PATHS+=("${TOKENS[$((i + 1))]:-}")
        i=$((i + 2))
        ;;
      -c) i=$((i + 2)) ;;
      -*) i=$((i + 1)) ;;
      *) break ;;
    esac
  done
  subcommand="${TOKENS[$i]:-}"
  subcommand="${subcommand%;}"
  [ "${subcommand%)}" = "commit" ] || continue

  target="$CWD"
  for path in ${CD_PATHS[@]+"${CD_PATHS[@]}"}; do
    target=$(resolve_path "$target" "$path") || block_unresolved "cd $path"
  done
  for path in ${C_PATHS[@]+"${C_PATHS[@]}"}; do
    target=$(resolve_path "$target" "$path") || block_unresolved "-C $path"
  done
  TARGETS+=("$target")
done

# The hook's cwd is always checked in addition to the resolved targets, so a misparsed
# command can only add blocks, never skip the check that applies without parsing.
for target in "$CWD" ${TARGETS[@]+"${TARGETS[@]}"}; do
  BRANCH=$(git -C "$target" symbolic-ref --short HEAD 2>/dev/null || true)
  if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ] || [ "$BRANCH" = "staging" ]; then
    echo "BLOCKED: Direct commit to '$BRANCH' branch is not allowed ($target). Create a feature branch first." >&2
    exit 2
  fi
done

exit 0
