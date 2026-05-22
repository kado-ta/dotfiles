#!/bin/bash
# Status line displaying: cwd | ctx% | 5h% | 7d% | effort
# All segments are color-coded with thresholded percentages.

input=$(cat)

CYAN=$'\033[36m'
DIM=$'\033[90m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
MAGENTA=$'\033[35m'
BLUE=$'\033[34m'
RESET=$'\033[0m'

IFS=$'\x1f' read -r DIR CTX FIVE_H WEEK MODEL EFFORT < <(
    printf '%s' "$input" | jq -r '[
        (.workspace.current_dir // ""),
        (.context_window.used_percentage // "" | tostring | split(".")[0]),
        (.rate_limits.five_hour.used_percentage // "" | tostring | split(".")[0]),
        (.rate_limits.seven_day.used_percentage // "" | tostring | split(".")[0]),
        (.model.display_name // ""),
        (.effort.level // "")
    ] | join("")'
)

SHORT_DIR="${DIR/#$HOME/~}"
[ -z "$SHORT_DIR" ] && SHORT_DIR="-"

pick_color() {
    local pct="$1"
    if [[ ! "$pct" =~ ^[0-9]+$ ]]; then printf '%s' "$DIM"
    elif [ "$pct" -ge 90 ]; then printf '%s' "$RED"
    elif [ "$pct" -ge 70 ]; then printf '%s' "$YELLOW"
    else printf '%s' "$GREEN"; fi
}

SEP=" │ "
parts=("${CYAN}${SHORT_DIR}${RESET}")

if [ -n "$CTX" ]; then
    parts+=("ctx $(pick_color "$CTX")${CTX}%${RESET}")
else
    parts+=("${DIM}ctx -${RESET}")
fi

if [ -n "$FIVE_H" ]; then
    parts+=("5h $(pick_color "$FIVE_H")${FIVE_H}%${RESET}")
fi

if [ -n "$WEEK" ]; then
    parts+=("7d $(pick_color "$WEEK")${WEEK}%${RESET}")
fi

if [ -n "$MODEL" ]; then
    parts+=("${BLUE}${MODEL}${RESET}")
fi

if [ -n "$EFFORT" ]; then
    parts+=("${MAGENTA}${EFFORT}${RESET}")
fi

output=""
for i in "${!parts[@]}"; do
    [ "$i" -gt 0 ] && output+="$SEP"
    output+="${parts[$i]}"
done

printf '%s\n' "$output"
