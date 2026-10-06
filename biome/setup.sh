#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

# スクリプト内で実行した場合、$0 はスクリプトのパス（例: ./biome/setup.sh）になる。
# ターミナルで直接実行した場合、$0 はシェル自身の名前になため、$0 は -/bin/zsh のような先頭にハイフンが付いた値となる。
SCRIPT_DIR=$(cd $(dirname $0) && pwd)
BIOME_DIR="$HOME/Library/Application Support/biome"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "BIOME_DIR: $BIOME_DIR"

if [ ! -d "$BIOME_DIR" ]; then mkdir -p "$BIOME_DIR"; fi
ln -snfv "${SCRIPT_DIR}/biome.json" "${BIOME_DIR}/biome.json"
