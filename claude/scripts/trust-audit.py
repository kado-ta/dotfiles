"""Claude Code が信頼したフォルダ（~/.claude.json の projects）を点検する。

projects のキーと、各項目の hasTrustDialogAccepted だけを読み、区分に分けて表示する。
消す候補があれば、消すためのコマンドを出力する（実行はしない）。
~/.claude.json を書き換えず、git も実行しない（.git の有無で判定する）。
終了コード: 0: 候補なし、1: 候補あり、2: 点検できない
使い方: python3 -B claude/scripts/trust-audit.py
"""
import datetime
import json
import os
import shlex
import sys
from pathlib import Path

# 表示の順。フォルダがない項目を先に出す。判定の順は classify() にある。
ORDER = ("missing", "home", "not-repo", "repo")
JQ_FILTER = ".projects |= with_entries(select(.key | IN($ARGS.positional[]) | not))"


def fail(message):
    print(f"trust-audit: 点検できない: {message}", file=sys.stderr)
    sys.exit(2)


def exists(path):
    # 権限がなくて調べられないときは OSError のまま上げる。missing とみなして消す候補にしないため。
    try:
        os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def classify(key, home):
    path = Path(key)
    if path == home:
        return "home"
    if not exists(path):
        return "missing"
    if any(exists(p / ".git") for p in (path, *path.parents)):
        return "repo"
    return "not-repo"


def display(key, home):
    if Path(key) == home:
        return "~"
    prefix = str(home) + "/"
    return "~/" + key[len(prefix):] if key.startswith(prefix) else key


def load_projects(config):
    # 例外のメッセージに中身が混ざらないよう、種類だけを出す。
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except OSError as e:
        fail(f"~/.claude.json を読めない（{e.strerror or type(e).__name__}）")
    except ValueError as e:
        fail(f"~/.claude.json を JSON として読めない（{type(e).__name__}）")
    projects = data.get("projects") if isinstance(data, dict) else None
    if not isinstance(projects, dict):
        fail("~/.claude.json の projects が辞書でない（形式が変わった見込み）")
    return projects


def main():
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        fail("CLAUDE_CONFIG_DIR が設定されている（~/.claude.json の場所が変わるので対応しない）")
    home = Path.home()
    projects = load_projects(home / ".claude.json")
    rows = []
    for key, entry in projects.items():
        # 制御文字があると、表示される（＝コピーされる）コマンドを見せかけられる。相対パスは cwd で意味が変わる。
        if not key.isprintable() or not os.path.isabs(key):
            fail(f"表示できない文字を含むか、絶対パスでないキーがある: {key!r}")
        trusted = isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True
        try:
            category = classify(key, home)
        except OSError as e:
            fail(f"{display(key, home)}: {e.strerror or type(e).__name__}")
        rows.append((category, trusted, key))
    rows.sort(key=lambda r: (ORDER.index(r[0]), r[2]))

    print("区分      信頼   パス")
    for category, trusted, key in rows:
        print(f"{category:<10}{'true' if trusted else 'false':<7}{display(key, home)}")

    # purge は元に戻せず、改名や外したボリュームでもフォルダがないように見えるので、項目を消すだけにする。
    removable = [key for category, trusted, key in rows
                 if category == "missing" or (category == "not-repo" and trusted)]
    if not removable:
        return 0

    print()
    print("# Claude Code をすべて閉じてから（claude --bg のセッションとデーモン、IDE・デスクトップアプリも）、通常のターミナルで実行する")
    print(f"cp -p ~/.claude.json ~/.claude.json.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    print()
    print("# フォルダがない項目と、リポジトリの外で信頼している項目を、項目ごと消す")
    print("# 会話の記録は残る。項目にある local の MCP サーバーの設定なども消えるので、戻すときは上のバックアップから")
    print(f"(umask 077; jq {shlex.quote(JQ_FILTER)} ~/.claude.json --args {' '.join(map(shlex.quote, removable))} \\")
    print("  > ~/.claude.json.new) && cat ~/.claude.json.new > ~/.claude.json && rm ~/.claude.json.new")
    return 1


if __name__ == "__main__":
    sys.exit(main())
