#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
VSCODE_DIR="$HOME/Library/Application Support/Code/User"
CURSOR_DIR="$HOME/Library/Application Support/Cursor/User"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "VSCODE_DIR: $VSCODE_DIR"
echo "CURSOR_DIR: $CURSOR_DIR"

# VSCode
# Create symbolic link of settings.json
ln -snfv "${SCRIPT_DIR}/settings.json" "${VSCODE_DIR}/settings.json"

# Install VSCode Extensions using the code command
if [ "$(which code)" != "" ]; then
  if [ "$(code --list-extensions)" != "$(cat "${SCRIPT_DIR}/extensions")" ]; then
    cat < "${SCRIPT_DIR}/extensions" | while read -r line
    do
      code --install-extension "$line"
    done
  fi
else
  echo "Install 'code' command from VSCode command palette to install your extensions."
fi

# Cursor
# Create symbolic link of settings.json
ln -snfv "${SCRIPT_DIR}/settings.json" "${CURSOR_DIR}/settings.json"

# Install VSCode Extensions using the code command
if [ "$(which code)" != "" ]; then
  if [ "$(cursor --list-extensions)" != "$(cat "${SCRIPT_DIR}/extensions")" ]; then
    cat < "${SCRIPT_DIR}/extensions" | while read -r line
    do
      code --install-extension "$line"
    done
  fi
else
  echo "Install 'cursor' command from Cursor command palette to install your extensions."
fi
