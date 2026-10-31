#!/bin/bash -e

# biome.jsonc の $schema URL 内のバージョンを、PATH 上の biome のバージョンに書き換える。
# mise の postinstall から呼ばれる（mise/mise_config.toml 参照）。手動実行も可。
# symlink 先（~/Library/Application Support/biome/biome.jsonc）に sed -i を使うと
# symlink が通常ファイルに置き換わるため、必ずリポジトリ内の実ファイルを書き換える。
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
VERSION=$(biome --version | awk '{print $2}')

sed -i '' -E "s#(https://biomejs\.dev/schemas/)[^/]+(/schema\.json)#\1${VERSION}\2#" "${SCRIPT_DIR}/biome.jsonc"

echo "biome.jsonc \$schema is synced to ${VERSION}"
