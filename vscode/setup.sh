#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
VSCODE_DIR="$HOME/Library/Application Support/Code/User"
PJMANAGER_EXT_DIR="$HOME/Library/Application Support/Code/User/globalStorage/alefragnani.project-manager"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "VSCODE_DIR: $VSCODE_DIR"
echo "PJMANAGER_EXT_DIR: $PJMANAGER_EXT_DIR"

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

  # VSCode PROJECT MANAGER 拡張の設定ファイルのシンボリックリンクを作成する。
  ln -snfv "${SCRIPT_DIR}/projects.json" "${PJMANAGER_EXT_DIR}/projects.json"
else
  echo "Install 'code' command from VSCode command palette to install your extensions."
fi

# NOTE: Cursor はしばらく使用しない予定なので、コマンドを無効化しておく。

# Cursor
# CURSOR_DIR="$HOME/Library/Application Support/Cursor/User"
# echo "CURSOR_DIR: $CURSOR_DIR"

# Create symbolic link of settings.json
# ln -snfv "${SCRIPT_DIR}/settings.json" "${CURSOR_DIR}/settings.json"

# Install VSCode Extensions using the code command
# if [ "$(which code)" != "" ]; then
#   if [ "$(cursor --list-extensions)" != "$(cat "${SCRIPT_DIR}/extensions")" ]; then
#     cat < "${SCRIPT_DIR}/extensions" | while read -r line
#     do
#       code --install-extension "$line"
#     done
#   fi
# else
#   echo "Install 'cursor' command from Cursor command palette to install your extensions."
# fi
