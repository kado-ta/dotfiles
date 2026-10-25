#!/bin/bash
# コンテキスト圧縮が走る直前に、現在の作業状態を Claude に渡すスクリプト。
# 現在のブランチ名・未コミット変更 (git status --short)・直近5件のコミットを additionalContext として Claude へ渡す。
# CLAUDE.md の Compaction policy セクションを自動的にサポートする仕組み。

set -euo pipefail

CWD="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Gather state
BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null || echo "unknown")
GIT_STATUS=$(git -C "$CWD" status --short 2>/dev/null | head -20)
GIT_LOG=$(git -C "$CWD" log --oneline -5 2>/dev/null)

CONTEXT="Current work state (preserve in compaction summary):
Branch: $BRANCH"

if [ -n "$GIT_STATUS" ]; then
  CONTEXT="$CONTEXT
Uncommitted changes:
$GIT_STATUS"
fi

if [ -n "$GIT_LOG" ]; then
  CONTEXT="$CONTEXT
Recent commits:
$GIT_LOG"
fi

jq -Rn --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "PreCompact",
    additionalContext: $ctx
  }
}'
