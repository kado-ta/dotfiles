#!/bin/bash
# ~/.gstack/projects（permissions.additionalDirectories）が symlink に差し替えられているあいだは、
# Edit・Write 系のツールをすべて止める。
# Claude Code は起動時に additionalDirectories の symlink を解決し、その先を作業ディレクトリとして扱う見込み
# （docs/work/20261116_sandbox-path-gaps/research-path-gaps.md の 2.5）。その先への直接の書き込みも作業ディレクトリの
# 中に見えるので、対象のパスでは絞らず、すべての呼び出しを止める。
# 呼ばれた時点の状態だけを見るので、symlink を実体に戻してから書く迂回は止めない（design.md の 7 章で受け入れた）。
# 入力（stdin）は読まず、jq も使わない。macOS の /bin/bash 3.2 で動かす。
set -u

block() {
  echo "Blocked: $1 Edit and Write tools are stopped because Claude Code may treat the resolved directory as a working directory. Ask the human to check ~/.gstack/projects and restart Claude Code." >&2
  exit 2
}

[ -n "${HOME:-}" ] || block "HOME is empty, so ~/.gstack/projects cannot be checked."
# HOME の途中の symlink（/var → /private/var など）で誤検知しないよう、比べる相手も実体のパスにする。
real_home=$(cd -P -- "$HOME" 2>/dev/null && pwd) || block "HOME ($HOME) cannot be resolved."
dir="$HOME/.gstack/projects"
# ないときは、gstack をまだ使っていないだけなので通す。先のない symlink は -e が偽になるので -L でも見る。
[ -e "$dir" ] || [ -L "$dir" ] || exit 0
[ -L "$dir" ] && block "$dir is a symlink to $(readlink "$dir")."
actual=$(cd -P -- "$dir" 2>/dev/null && pwd) || block "$dir is not a directory that can be entered."
[ "$actual" = "$real_home/.gstack/projects" ] || block "$dir resolves to $actual."
exit 0
