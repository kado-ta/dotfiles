#!/bin/bash
# Claude が Edit・Write した Obsidian Vault のノートを、Vault の点検スクリプト（_System/Scripts/check_note.py）で
# 点検する（PostToolUse）。誤りがあれば、点検の結果を stderr に出して exit 2 で Claude に伝える。
# 点検スクリプトは Vault の中（sandbox から書ける場所）にあり、このフックは sandbox の外で動く。書き換えられた
# スクリプトを動かすと sandbox を迂回できるので、同じフォルダの check-vault-note.sha256（承認済みの SHA-256）と
# 一致するときだけ実行する。照合と実行のあいだに差し替えられないよう、一度だけ読んだバイト列を照合し、
# 同じバイト列を実行する（docs/work/20261124_check-vault-note-hook/plan.md）。
# PATH のコマンド（jq・shasum・python3）は使わない。macOS の /bin/bash 3.2 で動かす。
set -u

# 入力を最後まで読み捨てて終える。読まずに終わると、パイプの容量を超える入力（大きな Write）で
# Claude Code 側の書き込みが失敗する。
skip() {
  cat >/dev/null
  exit "${1:-0}"
}

project=${CLAUDE_PROJECT_DIR:-}
[ -n "$project" ] || skip
project=${project%/}
checker="$project/_System/Scripts/check_note.py"
# Vault 以外のプロジェクトでは Python を起動しない。
[ -f "$checker" ] || skip

# Command Line Tools がないと /usr/bin/python3 は動かず、呼ぶと導入を促すダイアログが出るので、先に確かめる。
# /usr/bin/python3 は、xcode-select -p（DEVELOPER_DIR が優先）の先の python3 を動かす。
dev=$(/usr/bin/xcode-select -p 2>/dev/null)
if [ -z "$dev" ] || [ ! -x "$dev/usr/bin/python3" ]; then
  echo "Vault のノートを点検できない: /usr/bin/python3 を使えない（Command Line Tools が入っていない見込み）。ユーザーに、xcode-select --install で導入するよう頼む。" >&2
  skip 2
fi

hash_file="$(dirname -- "$0")/check-vault-note.sha256"

# 引数は、プロジェクトのディレクトリ、点検スクリプト、承認済みのハッシュのファイル。stdin はフックの入力。
# here document にしない。bash 3.2 は here document を一時ファイルに書き、書けないと py が空のまま 1 で終わる。
# 単一引用符で囲むので、この Python のコードに単一引用符を書かない。
py='
import hashlib
import json
import sys
import types

project, checker, hash_file = sys.argv[1:4]

try:
    note = json.loads(sys.stdin.buffer.read())["tool_input"]["file_path"]
except Exception:
    sys.exit(0)
# 点検するのはプロジェクトの下の .md だけ。.. などは正規化しない（点検スクリプトが resolve() して、Vault の外なら点検しない）。
if not isinstance(note, str) or not note.startswith(project + "/") or not note.endswith(".md"):
    sys.exit(0)

try:
    with open(checker, "rb") as f:
        src = f.read()
except OSError:
    sys.exit(0)
try:
    with open(hash_file, "rb") as f:
        approved = f.read().decode("ascii").strip()
except (OSError, UnicodeError):
    approved = ""
if len(approved) != 64 or approved.strip("0123456789abcdef") or hashlib.sha256(src).hexdigest() != approved:
    print(
        "Vault の点検スクリプトが承認済みの版と違うため実行しない。"
        "ユーザーに、点検スクリプトのレビューと、dotfiles の claude/hooks/check-vault-note.sha256 の更新を頼む。",
        file=sys.stderr,
    )
    sys.exit(2)

# 照合したバイト列を、点検スクリプトを直接実行したときと同じく __main__ として実行する。
# 点検スクリプトは __file__ から Vault のルートを決める。
main = types.ModuleType("__main__")
main.__file__ = checker
sys.modules["__main__"] = main
sys.argv = [checker, note]
exec(compile(src, checker, "exec", dont_inherit=True), main.__dict__)
'

# -I: Vault のフォルダとカレントディレクトリを sys.path に入れず、PYTHON* の環境変数を読まない。
# -B: __pycache__ を書かない。点検スクリプトの stdout も Claude に届くよう stderr に出す。
/usr/bin/python3 -I -B -c "$py" "$project" "$checker" "$hash_file" 1>&2 || exit 2
exit 0
