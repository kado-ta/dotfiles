#!/bin/bash

# jq が動かないとコマンドを検査できないので、素通りさせずにブロックする。
COMMAND=$(jq -r '.tool_input.command' < /dev/stdin) || {
  echo "Blocked: jq failed, so this command cannot be checked. Restart Claude Code, or run mise trust if this directory has an untrusted mise.toml." >&2
  exit 2
}

# rm -rf をブロック
if echo "$COMMAND" | grep -q 'rm -rf'; then
  echo "Blocked: rm -rf commands are not allowed" >&2
  exit 2  # exit 2 でツール実行をブロック
fi

# Allow read-only SF Lifecycle Center queries and pull request creation (the Hub org is production) as a single simple command.
# Reject shell metacharacters so that no other command can be chained after the allowed one.
is_allowed_devops_command() {
  [[ "$COMMAND" == *$'\n'* ]] && return 1
  echo "$COMMAND" | grep -q '[;&|<>`$()]' && return 1
  echo "$COMMAND" | grep -qE '^(SF_[A-Z_]+=[^[:space:]]+ +)*sf +devops[ :](project[ :]list|pipeline[ :](list|get)|work-item[ :]list|request[ :]status|review[ :]create)( |$)'
}

# 本番環境への接続をブロック
# 'prod' が含まれているもの、または、'prd' が単語として含まれている ('-prd-', '_prd_' など) をブロック対象とする。
if ! is_allowed_devops_command && echo "$COMMAND" | grep -qE 'prod|(^|[^[:alnum:]])prd([^[:alnum:]]|$)'; then
  echo "Blocked: production access is not allowed" >&2
  exit 2
fi

exit 0
