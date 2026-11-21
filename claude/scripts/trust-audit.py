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

    # purge は元に戻せず、改名や外したボリュームでもフォルダがないように見えるので、項目を消すだけにする。
    missing = [key for category, _, key in rows if category == "missing"]
    outside = [key for category, trusted, key in rows if category == "not-repo" and trusted]
    removable = set(missing + outside)

    print("区分      信頼   対応  パス")
    for category, trusted, key in rows:
        action = "消す  " if key in removable else "-     "
        print(f"{category:<10}{'true' if trusted else 'false':<7}{action}{display(key, home)}")
    print()
    if not removable:
        print("結果: 消す候補はない。やることはない。")
        return 0

    kinds = [f"{label} {len(keys)} 件" for label, keys in
             (("フォルダがない", missing), ("リポジトリの外で信頼している", outside)) if keys]
    print(f"結果: 消す候補が {len(removable)} 件ある（{'、'.join(kinds)}）。ほかの {len(rows) - len(removable)} 件は対応不要。")
    if missing:
        print("残しておくと: フォルダがない項目は、同じパスにフォルダを作り直したとき、確認なしで信頼される。急ぎではない。")
    if outside:
        print("残しておくと: リポジトリの外の項目は、その下の、リポジトリでないフォルダも信頼されたままになる。")
    print()
    print("次の手順:")
    print("1. Claude Code をすべて閉じる（claude --bg のセッションとデーモン、IDE、デスクトップアプリも）。")
    print("2. 通常のターミナルで、下のコマンドを上から順に実行する。")
    print("3. もう一度 mise run claude:trust-audit を実行し、「消す候補はない」と出ることを確かめる。")
    print()
    print(f"cp -p ~/.claude.json ~/.claude.json.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    print(f"(umask 077; jq {shlex.quote(JQ_FILTER)} ~/.claude.json --args {' '.join(map(shlex.quote, missing + outside))} \\")
    print("  > ~/.claude.json.new) && cat ~/.claude.json.new > ~/.claude.json && rm ~/.claude.json.new")
    print()
    print("jq は項目ごと消す。会話の記録は残る。項目にある local の MCP サーバーの設定なども消えるので、戻すときは上のバックアップから。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
