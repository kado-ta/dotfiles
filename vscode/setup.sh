#!/bin/bash -e

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
echo "SCRIPT_DIR: $SCRIPT_DIR"

VSCODE_DIR="${HOME}/Library/Application Support/Code/User"
echo "VSCODE_DIR: $VSCODE_DIR"

# Create symbolic link of settings.json
if [ -L "${VSCODE_DIR}/settings.json" ]; then
  ln -snfv "${SCRIPT_DIR}/settings.json" "${VSCODE_DIR}/settings.json"
fi

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
