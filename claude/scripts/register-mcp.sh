#!/bin/bash
# claude/mcp/<name>.json の MCP サーバーを、Claude Code の user スコープに <name> で登録する。
# 同じ名前の user スコープの登録は消してから足すので、何度実行しても登録は 1 つで、定義を変えれば置き換わる。
# ~/.claude.json に書くので、sandbox の外で実行する。~/.claude.json は claude の CLI だけが書く。
#   Claude Code から: ! /bin/bash ~/dotfiles/claude/scripts/register-mcp.sh
#   端末から: 上と同じ（claude/setup.sh からも呼ばれる）
# 定義の ${HOME} と ${NODE_BIN} は、登録するときに実際のパスに置き換える（公開リポジトリにユーザー名を入れないため）。
# ほかの ${...} は置き換えずに残し、Claude Code がサーバーの起動時に展開する。
# NODE_BIN は mise のグローバル設定の Node.js の bin。Claude Code の起動元（端末以外の PATH）と、プロジェクトの
# mise の設定（版の違いと、信頼していない設定での shim の失敗）に左右されないよう、絶対パスで登録する。
# Node.js を更新したら、このスクリプトを再実行する。
# update-skills.sh と同じく、ホームに移ってから実行し、Python には -I を付ける。macOS の /bin/bash 3.2 で動かす。
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
mcp_dir=$(cd "${script_dir}/../mcp" && pwd)
cd "$HOME"

node_bin="$(mise where node)/bin"
if [ ! -x "${node_bin}/npx" ]; then
  echo "npx is not found in the Node.js that mise uses globally: ${node_bin}" >&2
  exit 1
fi

found=""
for definition in "${mcp_dir}"/*.json; do
  [ -f "${definition}" ] || continue
  found=1
  name=$(basename "${definition}" .json)
  echo "==> ${name}"
  json=$(/usr/bin/python3 -I -B -c '
import json, sys

path, home, node_bin = sys.argv[1:]

def render(value):
    if isinstance(value, str):
        return value.replace("${HOME}", home).replace("${NODE_BIN}", node_bin)
    if isinstance(value, list):
        return [render(v) for v in value]
    if isinstance(value, dict):
        return {k: render(v) for k, v in value.items()}
    return value

with open(path, encoding="utf-8") as f:
    print(json.dumps(render(json.load(f)), ensure_ascii=False))
' "${definition}" "$HOME" "${node_bin}")
  # まだ登録されていなければ失敗するので、結果は見ない。ほかの理由で失敗したときは、次の add-json が失敗する。
  claude mcp remove "${name}" -s user >/dev/null 2>&1 || true
  claude mcp add-json -s user "${name}" "${json}"
done

if [ -z "${found}" ]; then
  echo "No MCP definitions in ${mcp_dir}" >&2
  exit 1
fi
