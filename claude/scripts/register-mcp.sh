#!/bin/bash
# claude/mcp/<name>.json の MCP サーバーを、Claude Code の user スコープに <name> で登録する。
# 同じ名前の user スコープの登録は消してから足すので、何度実行しても登録は 1 つで、定義を変えれば置き換わる。
# ~/.claude.json と ~/.local/share/claude-mcp に書くので、sandbox の外（通常の端末）で実行する。
# ~/.claude.json は claude の CLI だけが書く。Claude Code の ! は、セッションによっては sandbox の中で動き、失敗する。
#   端末から: /bin/bash ~/dotfiles/claude/scripts/register-mcp.sh（claude/setup.sh からも呼ばれる）
# 定義の npmPackage は、~/.local/share/claude-mcp/<name> に npm install し、登録する定義からは外す。
# 実行時に npx を使わないのは、npx が作業ディレクトリ（sandbox から書けるプロジェクト）の node_modules・
# node_modules/.bin・.npmrc を使い、そこに置かれたコードが sandbox の外で動くため。入れる場所は sandbox から書けない。
# 定義の ${HOME}・${NODE_BIN}・${PACKAGE_DIR} は、登録するときに実際のパスに置き換える（公開リポジトリにユーザー名を
# 入れないため）。ほかの ${...} は置き換えずに残し、Claude Code がサーバーの起動時に展開する。
# NODE_BIN は mise のグローバル設定の Node.js の bin。Claude Code の起動元（端末以外の PATH）と、プロジェクトの
# mise の設定（版の違いと、信頼していない設定での shim の失敗）に左右されないよう、絶対パスで登録する。
# Node.js を更新したら、このスクリプトを再実行する。
# update-skills.sh と同じく、ホームに移ってから実行し、Python には -I を付ける。macOS の /bin/bash 3.2 で動かす。
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
mcp_dir="${script_dir}/../mcp"
packages_dir="$HOME/.local/share/claude-mcp"
cd "$HOME"

# 最後の定義を消すと、Git は空の mcp/ を残さない。削除の手順の後も setup.sh が止まらないよう、成功で終える。
definitions=()
if [ -d "${mcp_dir}" ]; then
  for definition in "${mcp_dir}"/*.json; do
    [ -f "${definition}" ] && definitions+=("${definition}")
  done
fi
if [ "${#definitions[@]}" -eq 0 ]; then
  echo "No MCP definitions in ${mcp_dir}; nothing to register."
  exit 0
fi

node_bin="$(mise where node)/bin"
for tool in node npm; do
  if [ ! -x "${node_bin}/${tool}" ]; then
    echo "${tool} is not found in the Node.js that mise uses globally: ${node_bin}" >&2
    exit 1
  fi
done

# spec <定義>: npmPackage を出力する（なければ空）。
# render <定義> <HOME> <NODE_BIN> <PACKAGE_DIR>: npmPackage を外し、プレースホルダーを置き換えた JSON を出力する。
definition_tool='
import json, sys

mode, path = sys.argv[1:3]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
if mode == "spec":
    print(data.get("npmPackage", ""))
    sys.exit(0)
home, node_bin, package_dir = sys.argv[3:]
data.pop("npmPackage", None)

def render(value):
    if isinstance(value, str):
        return value.replace("${HOME}", home).replace("${NODE_BIN}", node_bin).replace("${PACKAGE_DIR}", package_dir)
    if isinstance(value, list):
        return [render(v) for v in value]
    if isinstance(value, dict):
        return {k: render(v) for k, v in value.items()}
    return value

print(json.dumps(render(data), ensure_ascii=False))
'

for definition in "${definitions[@]}"; do
  name=$(basename "${definition}" .json)
  package_dir="${packages_dir}/${name}"
  echo "==> ${name}"
  spec=$(/usr/bin/python3 -I -B -c "${definition_tool}" spec "${definition}")
  if [ -n "${spec}" ]; then
    mkdir -p "${package_dir}"
    # npm の bin は #!/usr/bin/env node で始まるので、同じ Node.js を PATH の先頭に置く。
    PATH="${node_bin}:/usr/bin:/bin" "${node_bin}/npm" install --prefix "${package_dir}" --ignore-scripts --no-audit --no-fund "${spec}"
  fi
  json=$(/usr/bin/python3 -I -B -c "${definition_tool}" render "${definition}" "$HOME" "${node_bin}" "${package_dir}")
  # まだ登録されていなければ失敗するので、結果は見ない。ほかの理由で失敗したときは、次の add-json が失敗する。
  claude mcp remove "${name}" -s user >/dev/null 2>&1 || true
  claude mcp add-json -s user "${name}" "${json}"
done
