#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
CLAUDE_DIR="$HOME/.claude"
echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CLAUDE_DIR: $CLAUDE_DIR"

ln -snfv "${SCRIPT_DIR}/settings.json" "${CLAUDE_DIR}/settings.json"
ln -snfv "${SCRIPT_DIR}/CLAUDE_.md" "${CLAUDE_DIR}/CLAUDE_.md"

ln -snfv "${SCRIPT_DIR}/hooks" "${CLAUDE_DIR}/hooks"
ln -snfv "${SCRIPT_DIR}/skills" "${CLAUDE_DIR}/skills"

[ -d "${CLAUDE_DIR}/scripts" ] || mkdir -p "${CLAUDE_DIR}/scripts"
ln -snfv "${SCRIPT_DIR}/scripts/statusline.sh" "${CLAUDE_DIR}/scripts/statusline.sh"

# Install plugins
if claude plugins list 2>/dev/null | grep -q "superpowers@claude-plugins-official"; then
	echo "superpowers plugin already installed, skipping"
else
	claude plugins install superpowers@claude-plugins-official
fi

# Install gstack
GSTACK_DIR="${CLAUDE_DIR}/skills/gstack"
if [ -d "${GSTACK_DIR}" ]; then
	echo "gstack already installed, skipping"
else
	git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git "${GSTACK_DIR}"
	"${GSTACK_DIR}/setup"
fi

echo "Success!"
