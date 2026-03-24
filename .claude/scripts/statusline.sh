#!/bin/bash
input=$(cat)
CONTEXT_SIZE=$(echo "$input" | jq -r '.context_window.context_window_size')
USAGE=$(echo "$input" | jq '.context_window.current_usage')

if [ "$USAGE" != "null" ] && [ "$CONTEXT_SIZE" != "null" ] && [ "$CONTEXT_SIZE" != "0" ]; then
    CURRENT=$(echo "$USAGE" | jq '.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens')
    PERCENT=$((CURRENT * 100 / CONTEXT_SIZE))
    echo "Context: ${PERCENT}%"
else
    echo "Context: -"
fi

# NOTE: コンテキスト使用率が70-80%になったら `/compact` コマンドで圧縮を検討すべき。
# `/compact 認証機能の実装状況は保持して` のように、保持すべき情報を指定することも可能。
# 新しいタスクに着手する際は `/clear` コマンドでコンテキストを完全にリセットする。
