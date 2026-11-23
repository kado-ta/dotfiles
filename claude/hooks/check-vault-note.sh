#!/bin/bash
# Claude が Edit・Write した Obsidian Vault のノートを、Vault の点検スクリプト（_System/Scripts/check_note.py）で
# 点検する（PostToolUse）。誤りがあれば、点検の結果を stderr に出して exit 2 で Claude に伝える。
# 実行するのは Vault の点検スクリプトではなく、dotfiles にあるレビュー済みの写し（vault/check_note.py）で、
# Seatbelt の中で動かす。比べることと実行は check-vault-note.py が行う（docs/work/20261124_check-vault-note-hook/plan.md）。
# ここでは、早く終わる判定と Command Line Tools の確認だけをする。
# PATH のコマンドは使わず、外部のコマンドは絶対パスで呼ぶ。here document を使わない（bash 3.2 は一時ファイルに書き、
# 書けないと 1 で終わって点検が黙って止まる）。macOS の /bin/bash 3.2 で動かす。
set -u

# 入力を最後まで読み捨てて終える。読まずに終わると、パイプの容量を超える入力（大きな Write）で
# Claude Code 側の書き込みが失敗する。
skip() {
  /bin/cat >/dev/null
  exit "${1:-0}"
}

project=${CLAUDE_PROJECT_DIR:-}
[ -n "$project" ] || skip
project=${project%/}
# Vault 以外のプロジェクトでは Python を起動しない。
[ -f "$project/_System/Scripts/check_note.py" ] || skip

# Command Line Tools がないと python3 は動かず、/usr/bin/python3 を呼ぶと導入を促すダイアログが出るので、先に確かめる。
# /usr/bin/python3（xcrun の shim）は /private/var/folders のキャッシュを使い、Seatbelt の中では読めないので、
# xcode-select -p（DEVELOPER_DIR が優先）の先の python3 を直接使う。
dev=$(/usr/bin/xcode-select -p 2>/dev/null)
python="$dev/usr/bin/python3"
if [ -z "$dev" ] || [ ! -x "$python" ]; then
  echo "Vault のノートを点検できない: python3 を使えない（Command Line Tools が入っていない見込み）。ユーザーに、xcode-select --install で導入するよう頼む。" >&2
  skip 2
fi

# -I: スクリプトのフォルダとカレントディレクトリを sys.path に入れず、PYTHON* の環境変数を読まない。
# -B: __pycache__ を書かない。-S: site を読み込まない。点検スクリプトの stdout も Claude に届くよう stderr に出す。
"$python" -I -B -S "$(/usr/bin/dirname -- "$0")/check-vault-note.py" "$project" "$python" 1>&2 || exit 2
exit 0
