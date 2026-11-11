#!/bin/bash
# sandbox 内の gh に、作業中のリポジトリの owner 用の読み取り専用トークンを渡す。
# 書き込みできるトークンは Keychain にあり、sandbox からは denyRead で読めない。
# ここで渡すのは、人間が ~/.config/cc-gh-read/<owner>.token に置いた読み取り専用の PAT だけ。
#
# install: SessionStart フックから実行し、CLAUDE_ENV_FILE に GH_TOKEN を設定する 1 行を追記する。
# 引数なし: その 1 行から各 Bash コマンドの前に実行され、トークンを出力する。
#   どの失敗でも無出力で終わる。コマンドは止めず、gh は未認証になる（fail closed）。

# gh は GH_TOKEN が空だとこれらの変数を使うので、起動元から引き継いだ書き込み用のトークンを消す。
LINE='unset GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN; export GH_TOKEN="$(/bin/bash "$HOME/.claude/hooks/gh-read-token.sh" 2>/dev/null)"'

if [ "${1:-}" = install ]; then
  [ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
  grep -qxF "$LINE" "$CLAUDE_ENV_FILE" 2>/dev/null || printf '%s\n' "$LINE" >>"$CLAUDE_ENV_FILE"
  exit 0
fi

url=$(/usr/bin/git config --get remote.origin.url 2>/dev/null) || exit 0
case "$url" in
  git@github.com:*) path=${url#git@github.com:} ;;
  ssh://git@github.com/*) path=${url#ssh://git@github.com/} ;;
  https://github.com/*) path=${url#https://github.com/} ;;
  *) exit 0 ;;
esac
owner=${path%%/*}
[[ $owner =~ ^[A-Za-z0-9-]+$ ]] || exit 0
file="$HOME/.config/cc-gh-read/$(printf '%s' "$owner" | /usr/bin/tr '[:upper:]' '[:lower:]').token"
# リンクは読まない。トークン以外の文字（改行や空白）を含むファイルも使わない。
[ -f "$file" ] && [ ! -L "$file" ] || exit 0
token=$(<"$file")
[[ $token =~ ^[A-Za-z0-9_]+$ ]] || exit 0
printf '%s' "$token"
