#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname)" != "Darwin" ] ; then
  echo "This is not macOS!"
  exit 1
fi

# セッション中に ~/.claude のリンクを張り直すと、Claude Code のサンドボックスがリンクを削除し、
# deny ルール・フック・サンドボックスが無効になる。
# CLAUDECODE は IDE の統合ターミナルにも設定されるが、IDE にセッションが残っている可能性が高いので拒否する。
if [ -n "${CLAUDECODE:-}" ]; then
  echo "Run this from a plain terminal (not an IDE-integrated one) with all Claude Code sessions closed."
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# worktree の中から実行すると、リンクが worktree を指し、worktree を消すと警告なしに切れる。
# worktree では .git がファイルになるので、git を使わずに判定する。
if [ -f "${SCRIPT_DIR}/../.git" ]; then
  echo "${SCRIPT_DIR} is in a git worktree. Run this script from the main checkout (~/dotfiles) instead." >&2
  exit 1
fi

CLAUDE_DIR="$HOME/.claude"
echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CLAUDE_DIR: $CLAUDE_DIR"

# リンク先が実体（シンボリックリンク以外）のときは止める。
# ln -snf は、実ディレクトリならその中にリンクを作り、実ファイルなら黙って上書きするため。
link() {
  local src="$1" dest="$2"
  if [ -e "${dest}" ] && [ ! -L "${dest}" ]; then
    echo "Not a symlink: ${dest}. Move or remove it, then rerun." >&2
    exit 1
  fi
  ln -snfv "${src}" "${dest}"
}

[ -d "${CLAUDE_DIR}" ] || mkdir -p "${CLAUDE_DIR}"
link "${SCRIPT_DIR}/settings.json" "${CLAUDE_DIR}/settings.json"
link "${SCRIPT_DIR}/CLAUDE.md" "${CLAUDE_DIR}/CLAUDE.md"
link "${SCRIPT_DIR}/rules" "${CLAUDE_DIR}/rules"
link "${SCRIPT_DIR}/themes" "${CLAUDE_DIR}/themes"

if [ -d "${CLAUDE_DIR}/hooks" ] && [ ! -L "${CLAUDE_DIR}/hooks" ]; then
  echo "Removing existing Claude Code hooks directory: ${CLAUDE_DIR}/hooks"
  rm -rf "${CLAUDE_DIR}/hooks"
fi
link "${SCRIPT_DIR}/hooks" "${CLAUDE_DIR}/hooks"

[ -d "${CLAUDE_DIR}/scripts" ] || mkdir -p "${CLAUDE_DIR}/scripts"
link "${SCRIPT_DIR}/scripts/statusline.sh" "${CLAUDE_DIR}/scripts/statusline.sh"

# プラグインが user スコープに入っているかを返す。
# claude plugins list は、全プロジェクトの project・local スコープのものも、無効なものも返す。
# ID だけで判定すると、別のプロジェクトにだけ入っているときに user スコープへのインストールを飛ばしてしまう。
plugin_installed_for_user() {
  claude plugins list --json 2>/dev/null | /usr/bin/python3 -c '
import json, sys
plugins = json.load(sys.stdin)
sys.exit(not any(p.get("id") == sys.argv[1] and p.get("scope") == "user" for p in plugins))
' "$1"
}

# マーケットプレイスが追加済みかを返す。
# grep -q は一致した時点で読むのをやめるので、pipefail の下では claude が SIGPIPE で失敗し、
# 追加済みでも未追加と判定して marketplace add を実行しうる。JSON を最後まで読んで判定する。
marketplace_added() {
  claude plugins marketplace list --json 2>/dev/null | /usr/bin/python3 -c '
import json, sys
marketplaces = json.load(sys.stdin)
sys.exit(not any(m.get("name") == sys.argv[1] for m in marketplaces))
' "$1"
}

# Install Superpowers
if plugin_installed_for_user superpowers@claude-plugins-official; then
  echo "superpowers plugin already installed, skipping"
else
  claude plugins install superpowers@claude-plugins-official
fi

# Install claude-code-setup
if plugin_installed_for_user claude-code-setup@claude-plugins-official; then
  echo "claude-code-setup plugin already installed, skipping"
else
  claude plugins install claude-code-setup@claude-plugins-official
fi

# Install ruby-lsp
# LSP サーバーの ruby-lsp コマンドは含まれないので、別途 gem で入れて PATH に通す。
if plugin_installed_for_user ruby-lsp@claude-plugins-official; then
  echo "ruby-lsp plugin already installed, skipping"
else
  claude plugins install ruby-lsp@claude-plugins-official
fi

# Install crit
# settings.json の extraKnownMarketplaces だけではマーケットプレイスが取得されず、install が失敗する。
if plugin_installed_for_user crit@crit; then
  echo "crit plugin already installed, skipping"
else
  marketplace_added crit || claude plugins marketplace add tomasz-tomczyk/crit
  claude plugins install crit@crit
fi

# Install understand-anything
# crit と同じく、マーケットプレイスを先に追加しないと install が失敗する。
if plugin_installed_for_user understand-anything@understand-anything; then
  echo "understand-anything plugin already installed, skipping"
else
  marketplace_added understand-anything || claude plugins marketplace add Egonex-AI/Understand-Anything
  claude plugins install understand-anything@understand-anything
fi

# Install pstack
# crit と同じく、マーケットプレイスを先に追加しないと install が失敗する。
if plugin_installed_for_user pstack@cursor-plugins; then
  echo "pstack plugin already installed, skipping"
else
  marketplace_added cursor-plugins || claude plugins marketplace add cursor/plugins
  claude plugins install pstack@cursor-plugins
fi

# Install gstack
GSTACK_DIR="${CLAUDE_DIR}/skills/gstack"
[ -d "${CLAUDE_DIR}/skills" ] || mkdir -p "${CLAUDE_DIR}/skills"
if [ -d "${GSTACK_DIR}" ]; then
  echo "gstack already cloned, skipping clone"
else
  git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git "${GSTACK_DIR}"
fi
# ~/.gstack/config.yaml は dotfiles にリンクせず、新しいマシンでも残したいキーだけをここで設定する。
# gstack-config は一時ファイルを mv して書き換えるので、リンクは実ファイルに置き換わる。
# リンク先を dotfiles に置くと、dotfiles で起動したセッションの sandbox からも書けるようになる。
# setup が redact_prepush_hook の確認で止まらないように、setup の前に設定する。
# - telemetry: 既定も off だが、外部への送信に関わるので明示する。
# - update_channel: 既定の auto は team_mode でなければ main を追い、main へのマージごとに更新される。
# - routing_declined: CLAUDE.md にスキルのルーティングを書き足すかの確認を出さない。
# - redact_prepush_hook: /ship が各リポジトリに認証情報の pre-push フックを入れることへの同意。/ship は無効にしている。
# - codex_reviews: /review・/plan-ceo-review などの外部レビューの段で、リポジトリの内容を Codex に送らない。Codex はユーザーが通常のターミナルで実行する。
# - plan_tune_hooks: plan-tune のフックを導入しない。--no-plan-tune-hooks は config.yaml に保存されないので、/gstack-upgrade が実行する setup のために設定する。
GSTACK_CONFIG="${GSTACK_DIR}/bin/gstack-config"
"${GSTACK_CONFIG}" set telemetry off
"${GSTACK_CONFIG}" set update_channel stable
"${GSTACK_CONFIG}" set routing_declined true
"${GSTACK_CONFIG}" set redact_prepush_hook true
"${GSTACK_CONFIG}" set codex_reviews disabled
"${GSTACK_CONFIG}" set plan_tune_hooks no
# clone 後の setup が途中で失敗しても、再実行で回復できるように毎回実行する。
# "${GSTACK_DIR}/setup" は GSTACK_DIR 内で実行しないと正常終了しない。
# サブシェル (...) 内での cd はスクリプト本体のカレントディレクトリに影響しない。
# plan-tune のフックは導入しない。確認で止まらず、claude/settings.json も書き換えないようにする。
# timeline の Stop フックも導入しない。Stop はターンごとに発火するので、実行中の skill を完了扱いにしてしまう。
# /plan-ceo-review のゲート（Stop・SubagentStop）も導入しない。使わないスキルのために、終了のたびに sandbox の外で bun が動く。
# スキルのルーティング（UserPromptSubmit）、出力の契約のゲート（Stop）、破壊的なコマンドの検査（PreToolUse の Bash）も導入しない。
# 1.102.0.0 から既定で on。どれも、そのたびに sandbox の外で bun が動く。破壊的なコマンドは validate-command.sh と deny で止めている。
# timeline・ゲート・ルーティングなどのフラグは ~/.gstack/config.yaml に保存されるので、/gstack-upgrade が実行する setup でも登録しない。
# --no-plan-tune-hooks だけは保存されない（~/.gstack/.plan-tune-hooks-prompted を書くだけ）ので、上で plan_tune_hooks を設定している。
# 保存されるのはこの setup を実行したときだけ。フラグを足したときは、setup.sh を実行し直すか、gstack-config set <キー> off を実行する。
(cd "${GSTACK_DIR}" && ./setup --no-plan-tune-hooks --no-timeline-stop-hook --no-ceo-review-gate --no-skill-routing --no-skill-contracts --no-destructive-guard)
# setup はフックを $HOME の絶対パスで settings.json に登録する。公開リポジトリにユーザー名を入れないよう ~/ に戻す。
/usr/bin/python3 -B "${SCRIPT_DIR}/scripts/settings-home-paths.py"

# Link personal skills (global, available in all projects)
for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "${skill_dir}")
  link "${skill_dir}" "${CLAUDE_DIR}/skills/${skill_name}"
done

# MCP サーバー（mcp/*.json）を user スコープに登録する。登録済みなら置き換える。
# ネットワークや npm が使えずに失敗しても、登録されないだけなので、setup.command の後の手順を止めない。
if ! /bin/bash "${SCRIPT_DIR}/scripts/register-mcp.sh"; then
  echo "Warning: MCP servers were not registered. Rerun: /bin/bash ${SCRIPT_DIR}/scripts/register-mcp.sh" >&2
fi

echo "Success!"
