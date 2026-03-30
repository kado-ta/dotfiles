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

# hooks ディレクトリが存在しない場合は、ディレクトリを作成した上でシンボリックリンクを作成する。
[ -d "${CLAUDE_DIR}/hooks" ] || mkdir -p "${CLAUDE_DIR}/hooks"
ln -snfv "${SCRIPT_DIR}/hooks/validate-command.sh" "${CLAUDE_DIR}/hooks/validate-command.sh"
ln -snfv "${SCRIPT_DIR}/hooks/protect-main-branch.sh" "${CLAUDE_DIR}/hooks/protect-main-branch.sh"

[ -d "${CLAUDE_DIR}/scripts" ] || mkdir -p "${CLAUDE_DIR}/scripts"
ln -snfv "${SCRIPT_DIR}/scripts/statusline.sh" "${CLAUDE_DIR}/scripts/statusline.sh"

echo "Success!"
