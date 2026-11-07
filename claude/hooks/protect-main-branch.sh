#!/bin/bash
# main / master / staging ブランチへの git commit を防ぐ。
# Claude Code の Bash ツール用の PreToolUse フックとして使う。
# 終了コード 2 を返すとツールの実行がブロックされ、stderr の内容が Claude に表示される。

set -euo pipefail

# `set -e` のもとで想定外の失敗（jq が壊れているなど）が起きると終了コード 1 で終わる。1 ではツールが
# ブロックされず、検査が飛ばされてしまう。そのため代わりにブロックする（fail closed）。
trap 'echo "BLOCKED: This hook failed, so the command cannot be checked. If jq is failing, restart Claude Code, or run mise trust if this directory has an untrusted mise.toml." >&2; exit 2' ERR

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# git commit コマンドだけを検査する（`git -C <path> commit` の形も含む）
# パイプではなくヒアストリングを使う。`grep -q` は最初の一致で終了するため、書き込み側が SIGPIPE を受けて
# pipefail のもとでパイプラインが失敗し、検査が飛ばされてしまう。
if ! grep -qE '(^|\s|&&|\||\;)git(\s+\S+)*\s+commit(\s|$|[;&|)])' <<<"$COMMAND"; then
  exit 0
fi

# 作業ディレクトリをフックの入力から決める。なければ CLAUDE_PROJECT_DIR を使う
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CWD="${CWD:-${CLAUDE_PROJECT_DIR:-}}"

if [ -z "$CWD" ]; then
  exit 0
fi

block_unresolved() {
  echo "BLOCKED: Cannot resolve the repository of git commit ('$1'). Use a literal path without variables or spaces." >&2
  exit 2
}

# コマンド中のパスのトークンを、基準ディレクトリからの相対で解決する。
# 静的に解決できない場合（変数・クォート・存在しないディレクトリ）は失敗する。
resolve_path() {
  local base="$1" path="$2"
  case "$path" in
    \'*\' | \"*\") path="${path:1:${#path}-2}" ;;
  esac
  # shellcheck disable=SC2088 # コマンドの文字列中のチルダを文字どおりに照合する
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

# すべての git commit の呼び出しについて、それより前の `cd <dir>` コマンドと、その呼び出しの
# `-C <dir>` オプションからリポジトリを解決する。トークンは空白で区切るだけなので、ヒューリスティックである。
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

# 解決した対象に加えて、フックの cwd も常に検査する。これにより、コマンドを誤って解析しても
# ブロックが増えるだけで、解析なしで適用される検査が飛ばされることはない。
for target in "$CWD" ${TARGETS[@]+"${TARGETS[@]}"}; do
  BRANCH=$(git -C "$target" symbolic-ref --short HEAD 2>/dev/null || true)
  if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ] || [ "$BRANCH" = "staging" ]; then
    echo "BLOCKED: Direct commit to '$BRANCH' branch is not allowed ($target). Create a feature branch first." >&2
    # 検査はコマンドの実行前のブランチで行うため、同じコマンド内でブランチを作っても通らない
    if grep -qE 'git(\s+\S+)*\s+(switch\s+(-c|-C|--create)|checkout\s+(-b|-B))(\s|$)' <<<"$COMMAND"; then
      echo "このフックはコマンドの実行前のブランチで判定します。'git switch -c <branch>' を別の Bash 呼び出しで実行してから、コミットしてください。" >&2
    fi
    exit 2
  fi
done

exit 0
