#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname)" != "Darwin" ] ; then
  echo "This is not macOS!"
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# ここでは、Obsidian の main vault を対象とする。
# 他の Vault への設定反映は、その Vault の .obsidian/ ディレクトリへこのディレクトリのファイルをコピーして反映する。
OBSIDIAN_DIR="$HOME/Obsidian/main/.obsidian"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "OBSIDIAN_DIR: $OBSIDIAN_DIR"

ln -snfv "${SCRIPT_DIR}/app.json" "${OBSIDIAN_DIR}/app.json"
ln -snfv "${SCRIPT_DIR}/appearance.json" "${OBSIDIAN_DIR}/appearance.json"
ln -snfv "${SCRIPT_DIR}/community-plugins.json" "${OBSIDIAN_DIR}/community-plugins.json"
ln -snfv "${SCRIPT_DIR}/core-plugins.json" "${OBSIDIAN_DIR}/core-plugins.json"
ln -snfv "${SCRIPT_DIR}/graph.json" "${OBSIDIAN_DIR}/graph.json"
ln -snfv "${SCRIPT_DIR}/hotkeys.json" "${OBSIDIAN_DIR}/hotkeys.json"

if [ -d "${OBSIDIAN_DIR}/snippets" ] && [ ! -L "${OBSIDIAN_DIR}/snippets" ]; then
  echo "Removing existing Obsidian snippets directory: ${OBSIDIAN_DIR}/snippets"
  rm -rf "${OBSIDIAN_DIR}/snippets"
fi
ln -snfv "${SCRIPT_DIR}/snippets" "${OBSIDIAN_DIR}/snippets"

echo "Success!"
