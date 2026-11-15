#!/bin/bash
# gstack・Claude Code のプラグイン・crit の CLI をまとめて更新する（mise run claude:update）。
# ~/.claude/skills・~/.claude/plugins・Homebrew に書くので、sandbox の外（端末か Claude Code の !）で実行する。
# 手順が失敗しても残りを続け、最後に失敗した手順を表示して終了コード 1 で終わる。
# macOS の /bin/bash 3.2 で動かすので、空の配列と set -u は使わない。

set -o pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
failed=""

# step <手順名> <コマンド...>: 失敗したら手順名を記録して先に進む。
step() {
  local name=$1
  shift
  echo "==> ${name}"
  "$@" || failed="${failed} ${name}"
}

step gstack "$HOME/.claude/skills/gstack/bin/gstack-upgrade"
# setup はフックを $HOME の絶対パスで登録し、~/ に直した項目も絶対パスに書き戻す。
# 途中で失敗しても書き込んでいることがあるので、gstack の結果によらず実行する。
step settings-home-paths /usr/bin/python3 -B "${script_dir}/settings-home-paths.py"

step marketplaces claude plugin marketplace update
# local スコープは別のリポジトリのものなので、user スコープだけを更新する。
# -y は付けない。マーケットプレイスが宣言したインストールコマンドが変わったときに、人が見ないまま受け入れないため。
# 確認が要るときは、TTY のない ! の中では拒否されて失敗に数えられるので、端末で更新し直す。
echo "==> plugin-list"
if plugins=$(claude plugin list --json | /usr/bin/python3 -c '
import json, sys
ids = []
for plugin in json.load(sys.stdin):
    if plugin.get("scope") == "user" and plugin["id"] not in ids:
        ids.append(plugin["id"])
print("\n".join(ids))
'); then
  for id in ${plugins}; do
    step "${id}" claude plugin update "${id}" --scope user
  done
else
  failed="${failed} plugin-list"
fi

# crit はプラグインと CLI の版の組み合わせで動くので、CLI も一緒に更新し、cc-crit の profile を確かめる。
step crit-cli brew upgrade crit
step crit-profile-test mise run crit:profile-test

if [ -n "${failed}" ]; then
  echo "失敗した手順:${failed}"
fi
echo "次に、dotfiles の Claude Code で /sync-skill-docs を実行する。更新したプラグインは、Claude Code を再起動すると読み込まれる。"
[ -z "${failed}" ]
