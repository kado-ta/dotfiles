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
link "${SCRIPT_DIR}/mcp.json" "${CLAUDE_DIR}/mcp.json"

if [ -d "${CLAUDE_DIR}/hooks" ] && [ ! -L "${CLAUDE_DIR}/hooks" ]; then
  echo "Removing existing Claude Code hooks directory: ${CLAUDE_DIR}/hooks"
  rm -rf "${CLAUDE_DIR}/hooks"
fi
link "${SCRIPT_DIR}/hooks" "${CLAUDE_DIR}/hooks"

[ -d "${CLAUDE_DIR}/scripts" ] || mkdir -p "${CLAUDE_DIR}/scripts"
link "${SCRIPT_DIR}/scripts/statusline.sh" "${CLAUDE_DIR}/scripts/statusline.sh"

# Install Superpowers
if claude plugins list 2>/dev/null | grep -q " superpowers@claude-plugins-official$"; then
  echo "superpowers plugin already installed, skipping"
else
  claude plugins install superpowers@claude-plugins-official
fi

# Install claude-code-setup
if claude plugins list 2>/dev/null | grep -q " claude-code-setup@claude-plugins-official$"; then
  echo "claude-code-setup plugin already installed, skipping"
else
  claude plugins install claude-code-setup@claude-plugins-official
fi

# Install crit
# settings.json の extraKnownMarketplaces だけではマーケットプレイスが取得されず、install が失敗する。
if claude plugins list 2>/dev/null | grep -q " crit@crit$"; then
  echo "crit plugin already installed, skipping"
else
  claude plugins marketplace list 2>/dev/null | grep -q " crit$" || claude plugins marketplace add tomasz-tomczyk/crit
  claude plugins install crit@crit
fi

# Install gstack
GSTACK_DIR="${CLAUDE_DIR}/skills/gstack"
[ -d "${CLAUDE_DIR}/skills" ] || mkdir -p "${CLAUDE_DIR}/skills"
if [ -d "${GSTACK_DIR}" ]; then
  echo "gstack already cloned, skipping clone"
else
  git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git "${GSTACK_DIR}"
fi
# clone 後の setup が途中で失敗しても、再実行で回復できるように毎回実行する。
# "${GSTACK_DIR}/setup" は GSTACK_DIR 内で実行しないと正常終了しない。
# サブシェル (...) 内での cd はスクリプト本体のカレントディレクトリに影響しない。
# plan-tune のフックは導入しない。確認で止まらず、claude/settings.json も書き換えないようにする。
# timeline の Stop フックも導入しない。Stop はターンごとに発火するので、実行中の skill を完了扱いにしてしまう。
# このフラグは ~/.gstack/config.yaml に保存されるので、/gstack-upgrade が実行する setup でも登録しない。
(cd "${GSTACK_DIR}" && ./setup --no-plan-tune-hooks --no-timeline-stop-hook)

# Link personal skills (global, available in all projects)
for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "${skill_dir}")
  link "${skill_dir}" "${CLAUDE_DIR}/skills/${skill_name}"
done

echo "Success!"
