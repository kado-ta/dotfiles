#!/bin/bash

COMMAND=$(jq -r '.tool_input.command' < /dev/stdin)

# rm -rf をブロック
if echo "$COMMAND" | grep -q 'rm -rf'; then
  echo "Blocked: rm -rf commands are not allowed" >&2
  exit 2  # exit 2 でツール実行をブロック
fi

# 本番環境への接続をブロック
if echo "$COMMAND" | grep -qE 'prod|prd'; then
  echo "Blocked: production access is not allowed" >&2
  exit 2
fi

exit 0
