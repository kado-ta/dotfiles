#!/bin/bash
# main / master / staging ブランチへの git commit を防ぐ。
# Claude Code の Bash ツール用の PreToolUse フックとして使う。
# 終了コード 2 を返すとツールの実行がブロックされ、stderr の内容が Claude に表示される。

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

# コマンドが grep のパターンに一致するか。grep の失敗（終了コード 2 以上）を一致なしと区別し、本体を失敗させる。
# パイプではなくヒアストリングを使う。`grep -q` は最初の一致で終了するため、書き込み側が SIGPIPE を受けて
# pipefail のもとでパイプラインが失敗し、検査が飛ばされてしまう。
matches() {
  local code=0
  grep -qE "$1" <<<"$COMMAND" || code=$?
  # 2 はブロックを意味するので、失敗の終了コードは 3 にそろえる
  [ "$code" -le 1 ] || exit 3
  return "$code"
}

# git の組み込みコマンドか。組み込みコマンドはエイリアスで上書きできない
BUILTINS=""
is_builtin() {
  [ -n "$BUILTINS" ] || BUILTINS=$'\n'"$(git --list-cmds=builtins 2>/dev/null || true)"$'\n'
  case "$BUILTINS" in *$'\n'"$1"$'\n'*) return 0 ;; esac
  return 1
}

# エイリアス（$1）の値を ALIAS_VALUE に入れる。`-c alias.<name>=...` を優先し、なければ対象のリポジトリ（$2）
# から見える設定を見る。エイリアス名は大文字と小文字を区別しない。
# 長いコマンドで遅くならないよう、設定は対象のリポジトリが変わったときだけ読む。
ALIASES=""
ALIASES_DIR=""
lookup_alias() {
  local kv line code=0
  ALIAS_VALUE=""
  [ -n "$1" ] || return 0
  if [ "$ALIASES_DIR" != "$2" ]; then
    # 終了コード 1 はエイリアスがないだけ。それ以外の失敗は、検査できないので本体を失敗させる
    ALIASES=$(git -C "$2" config --get-regexp '^alias\.' 2>/dev/null) || code=$?
    [ "$code" -le 1 ] || exit 3
    ALIASES_DIR="$2"
  fi
  shopt -s nocasematch
  for kv in ${C_CONFIGS[@]+"${C_CONFIGS[@]}"}; do
    case "$kv" in "alias.$1="*) ALIAS_VALUE="${kv#*=}" ;; esac
  done
  if [ -z "$ALIAS_VALUE" ]; then
    while IFS= read -r line; do
      case "$line" in "alias.$1 "*) ALIAS_VALUE="${line#* }" ;; esac
    done <<<"$ALIASES"
  fi
  shopt -u nocasematch
}

# エイリアスが git commit に展開されるか。多段のエイリアスもたどり、行き着いた組み込みコマンドを ALIAS_FINAL に入れる。
# シェルエイリアス（`!` で始まるもの）とオプションで始まるエイリアスは、中身を解析できないので commit とみなす。
# 循環していたり深すぎたりして、たどりきれない場合も commit とみなす（fail closed）。
is_commit_alias() {
  local name="$1"
  ALIAS_FINAL=""
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    lookup_alias "$name" "$2"
    [ -n "$ALIAS_VALUE" ] || return 1
    case "$ALIAS_VALUE" in '!'* | -*) return 0 ;; esac
    name="${ALIAS_VALUE%%[[:space:]]*}"
    [ "$name" != "commit" ] || return 0
    # 組み込みコマンドはエイリアスで上書きできないので、展開はそこで止まる
    if [ -z "$name" ] || is_builtin "$name"; then
      ALIAS_FINAL="$name"
      return 1
    fi
  done
  return 0
}

main() {
  set -euo pipefail
  # ヒアストリングの一時ファイルを作れない環境では、grep が実行されずに「一致なし」と同じ終了コード 1 になる。
  # 区別できないので、最初に試して止める
  : <<<""

  INPUT=$(cat)
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

  # git commit コマンドだけを検査する（`git -C <path> commit` の形も含む）
  # commit の文字列がなくても、エイリアス経由のコミットがありうるので、git を含むコマンドは下で解析する。
  COMMIT_TEXT=1
  # shellcheck disable=SC2016 # コマンドの文字列中のバッククォートを文字どおりに照合する
  if ! matches '(^|\s|&&|\||\;|\(|`)git(\s+\S+)*\s+commit(\s|$|[;&|)`])'; then
    COMMIT_TEXT=0
    if ! matches '(^|\s|&&|\||\;|\(|`)git\s'; then
      exit 0
    fi
  fi

  # git が動かないと、ブランチやエイリアスを判定できずに通してしまうので、先に確かめる
  git --version >/dev/null

  # 作業ディレクトリをフックの入力から決める。なければ CLAUDE_PROJECT_DIR を使う
  CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
  CWD="${CWD:-${CLAUDE_PROJECT_DIR:-}}"

  if [ -z "$CWD" ]; then
    exit 0
  fi

  # すべての git commit の呼び出しについて、それより前の `cd <dir>` コマンドと、その呼び出しの
  # `-C <dir>` オプションからリポジトリを解決する。トークンは空白で区切るだけなので、ヒューリスティックである。
  # 行末を `;` の区切りにする。bash 3.2 の `${COMMAND//$'\n'/ ; }` は行数の二乗で遅いので sed を使う
  # 区切りの前後に空白を入れて、`a&&b` も別のトークンにする
  set -f
  # shellcheck disable=SC2207,SC2001 # 単語分割が目的。SC2001 が勧める置換は上記のとおり遅い
  TOKENS=($(sed -E 's/(&&|\|\||[;|&])/ \1 /g; s/$/ ;/' <<<"$COMMAND"))
  set +f
  CD_PATHS=()
  C_PATHS=()
  TARGETS=()
  BRANCH_CHANGE=0
  SWITCH_BEFORE_COMMIT=0
  COMMAND_START=1
  i=0
  while [ "$i" -lt "${#TOKENS[@]}" ]; do
    token="${TOKENS[$i]#(}"
    token="${token#\`}"
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
      CD_PATHS+=("$path")
      i=$((i + 2))
      continue
    fi
    COMMAND_START=0
    i=$((i + 1))
    [ "$token" = "git" ] || continue

    C_PATHS=()
    C_CONFIGS=()
    while [ "$i" -lt "${#TOKENS[@]}" ]; do
      case "${TOKENS[$i]}" in
        -C)
          C_PATHS+=("${TOKENS[$((i + 1))]:-}")
          i=$((i + 2))
          ;;
        -c)
          kv="${TOKENS[$((i + 1))]:-}"
          i=$((i + 2))
          # クォートした値に空白があると複数のトークンに分かれるので、閉じるクォートまでつなぐ
          case "$kv" in
            \"* | \'*)
              quote="${kv:0:1}"
              while [ "$i" -lt "${#TOKENS[@]}" ] && { [ "${#kv}" -lt 2 ] || [ "${kv: -1}" != "$quote" ]; }; do
                kv+=" ${TOKENS[$i]}"
                i=$((i + 1))
              done
              ;;
          esac
          kv="${kv#[\'\"]}"
          C_CONFIGS+=("${kv%[\'\"]}")
          ;;
        -*) i=$((i + 1)) ;;
        *) break ;;
      esac
    done
    subcommand="${TOKENS[$i]:-}"
    subcommand="${subcommand%)}"
    subcommand="${subcommand%\`}"
    case "$subcommand" in checkout | switch | branch | symbolic-ref | rebase) BRANCH_CHANGE=1 ;; esac
    # commit 以外の組み込みコマンドは、エイリアスでもないので検査しない
    if [ "$subcommand" != "commit" ] && is_builtin "$subcommand"; then
      continue
    fi

    # エイリアスは移動先のリポジトリの設定で決まるので、移動先を先に解決する。解決できなければブロックする
    target="$CWD"
    for path in ${CD_PATHS[@]+"${CD_PATHS[@]}"}; do
      target=$(resolve_path "$target" "$path") || block_unresolved "cd $path"
    done
    for path in ${C_PATHS[@]+"${C_PATHS[@]}"}; do
      target=$(resolve_path "$target" "$path") || block_unresolved "-C $path"
    done
    if [ "$subcommand" != "commit" ] && ! is_commit_alias "$subcommand" "$target"; then
      case "$ALIAS_FINAL" in checkout | switch | branch | symbolic-ref | rebase) BRANCH_CHANGE=1 ;; esac
      continue
    fi
    [ "$BRANCH_CHANGE" -eq 0 ] || SWITCH_BEFORE_COMMIT=1
    TARGETS+=("$target")
  done

  # 検査はコマンドの実行前のブランチで行うので、同じ呼び出しの中でブランチを切り替えてからのコミットは判定できない
  if [ "$SWITCH_BEFORE_COMMIT" -eq 1 ]; then
    echo "BLOCKED: このフックはコマンドの実行前のブランチで判定するため、同じ呼び出しの中でブランチを切り替えてからコミットできません。'git switch' などを別の Bash 呼び出しで実行してから、コミットしてください。" >&2
    exit 2
  fi

  # commit の文字列もエイリアス経由のコミットもなければ、検査しない
  if [ "$COMMIT_TEXT" -eq 0 ] && [ ${#TARGETS[@]} -eq 0 ]; then
    exit 0
  fi

  # 解決した対象に加えて、フックの cwd も常に検査する。これにより、コマンドを誤って解析しても
  # ブロックが増えるだけで、解析なしで適用される検査が飛ばされることはない。
  for target in "$CWD" ${TARGETS[@]+"${TARGETS[@]}"}; do
    code=0
    # --short は同名のタグがあると heads/main を返すので使わない。
    # 大文字・小文字を区別しないファイルシステムでは refs/heads/MAIN も main と同じファイルを更新するので、小文字で比較する。
    BRANCH=$(git -C "$target" symbolic-ref -q HEAD 2>/dev/null) || code=$?
    # 1 は detached HEAD、128 はリポジトリの外。どちらもブランチへのコミットではない。それ以外の失敗は止める
    case "$code" in 0 | 1 | 128) ;; *) exit 3 ;; esac
    BRANCH=$(printf %s "${BRANCH#refs/heads/}" | tr '[:upper:]' '[:lower:]')
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
}

# 想定外の失敗（jq が壊れている、未定義の変数など）で終了コードが 0 と 2 以外になると、フックの失敗として
# 扱われ、コマンドがそのまま通ってしまう。そこで本体をサブシェルで実行し、その終了コードを 2 に変えてブロックする
# （fail closed）。
(main)
code=$?
if [ "$code" -eq 0 ] || [ "$code" -eq 2 ]; then
  exit "$code"
fi
echo "BLOCKED: This hook failed (exit $code), so the command cannot be checked. If jq is failing, restart Claude Code, or run mise trust if this directory has an untrusted mise.toml." >&2
exit 2
