"""~/.claude/settings.json のコマンドの先頭にある絶対パスの $HOME を ~ に戻す。

gstack の setup は、フックを $HOME/.claude/skills/gstack/... の絶対パスで登録する。~/ に直しても、
次の setup（prune-stale --repoint）が絶対パスに書き戻すので、gstack を更新するたびに実行する。
dotfiles は公開リポジトリなので、ユーザー名を含むパスをコミットしない。

使い方:
  /usr/bin/python3 -B claude/scripts/settings-home-paths.py
"""
import os
import stat
import tempfile
from pathlib import Path


def to_home_relative(text, home):
    # JSON を読み込んで書き直すと書式が変わるおそれがあるので、文字列のまま置き換える。
    # 末尾の / まで含めて比べるので、名前の先頭が同じ別のユーザーのパスは置き換えない。
    needle = '"command": "' + home + "/"
    count = text.count(needle)
    return text.replace(needle, '"command": "~/'), count


def main():
    # ~/.claude/settings.json は dotfiles へのリンク。リンクを残してリンク先を書き換える（gstack もリンク先に書く）。
    real = (Path.home() / ".claude" / "settings.json").resolve()
    text, count = to_home_relative(real.read_text(encoding="utf-8"), str(Path.home()))
    if count == 0:
        return 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=real.parent, delete=False) as tmp:
        tmp.write(text)
    os.chmod(tmp.name, stat.S_IMODE(real.stat().st_mode))
    os.replace(tmp.name, real)
    print(f"settings-home-paths: {count} 件のコマンドを ~/ に戻した（{real}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
