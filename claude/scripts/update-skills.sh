#!/bin/bash
# gstack・Claude Code のプラグイン・crit の CLI をまとめて更新する。
# ~/.claude/skills・~/.claude/plugins・Homebrew に書くので、sandbox の外で実行する。
#   Claude Code から: ! /bin/bash ~/dotfiles/claude/scripts/update-skills.sh
#   端末から: 上と同じか、dotfiles で mise run claude:update
# Claude Code から mise run を使わないのは、mise が dotfiles のルートの設定ファイル（mise.local.toml など）を
# 自動で信頼して読み込み、ルートには sandbox から書けるため。同じ理由で、ホームに移ってから各コマンドを実行し、
# Python には -I を付けて、カレントディレクトリなどからの import を防ぐ。
# 手順が失敗しても残りを続け、最後に失敗した手順を表示して終了コード 1 で終わる。
# macOS の /bin/bash 3.2 で動かすので、空の配列と set -u は使わない。

set -o pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "${script_dir}/../.." && pwd)
failed=""
# gstack-upgrade も、呼び出し元の git リポジトリを検査する（zsh の gstack-upgrade 関数と同じく、ホームから実行する）。
cd "$HOME" || exit 1

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
step settings-home-paths /usr/bin/python3 -I -B "${script_dir}/settings-home-paths.py"

step marketplaces claude plugin marketplace update
# local スコープは別のリポジトリのものなので、user スコープだけを更新する。
# -y は付けない。マーケットプレイスが宣言したインストールコマンドが変わったときに、人が見ないまま受け入れないため。
# 確認が要るプラグインは、TTY がないとき（! や mise run）に拒否されて失敗に数えられる。
# そのときは端末で claude plugin update <id> --scope user を直接実行する。
echo "==> plugin-list"
if plugins=$(claude plugin list --json | /usr/bin/python3 -I -B -c '
import json, sys
ids = []
for plugin in json.load(sys.stdin):
    if plugin.get("scope") == "user" and plugin["id"] not in ids:
        ids.append(plugin["id"])
print("\n".join(ids))
') && [ -n "${plugins}" ]; then
  for id in ${plugins}; do
    step "${id}" claude plugin update "${id}" --scope user
  done
else
  # 一覧が取れないか空のとき（CLI の出力の形が変わったときなど）は、どれも更新されないので失敗に数える。
  failed="${failed} plugin-list"
fi

# crit はプラグインと CLI の版の組み合わせで動くので、CLI も一緒に更新し、cc-crit の profile を確かめる。
step crit-cli brew upgrade crit
step crit-profile-test /usr/bin/python3 -I -B "${repo}/claude/hooks/tests/test-cc-crit-profile.py"

if [ -n "${failed}" ]; then
  echo "失敗した手順:${failed}"
fi
# 更新した hooks は、再起動した後のセッションで動き始めるので、その前に見直す。
echo "次に、再起動する前に dotfiles の Claude Code で /sync-skill-docs を実行し、hooks の変化を確かめる。更新したプラグインは、Claude Code を再起動すると読み込まれる。"
[ -z "${failed}" ]
