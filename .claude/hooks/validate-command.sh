#!/bin/bash

COMMAND=$(jq -r '.tool_input.command' < /dev/stdin)

# rm -rf をブロック
if echo "$COMMAND" | grep -q 'rm -rf'; then
  echo "Blocked: rm -rf commands are not allowed" >&2
  exit 2  # exit 2 でツール実行をブロック
fi

# 本番環境への接続をブロック
# 'prod' が含まれているもの、または、'prd' が単語として含まれている ('-prd-', '_prd_' など) をブロック対象とする。
if echo "$COMMAND" | grep -qE 'prod|(^|[^[:alnum:]_])prd([^[:alnum:]_]|$)'; then
  echo "Blocked: production access is not allowed" >&2
  exit 2
fi

exit 0
