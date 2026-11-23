"""check-vault-note.sh から呼ばれる、Vault のノートの点検の Python の部分。

2 つの段を持つ。
- 引数が「プロジェクト python3」の段（sandbox の外）: フックの入力を読み、Vault のノートなら、Vault の点検
  スクリプトが dotfiles の写し（vault/check_note.py）と同じかを比べる。同じなら、sandbox-exec で
  Seatbelt の中の段に置き換わる。
- 引数が「--run プロジェクト ノート」の段（Seatbelt の中）: 写しを、Vault の点検スクリプトとして実行する。

Vault の点検スクリプトは sandbox から書ける場所にあるので、実行しない。実行するのは、sandbox から書けない
dotfiles の写しだけ（承認は、写しの git の差分のレビュー）。点検スクリプトは、symlink を通して Vault の外の
ファイルも読みうるので、Seatbelt（check-vault-note.sb）で読み込みを Vault に閉じ込める。
設計: docs/work/20261124_check-vault-note-hook/plan.md。/usr/bin/python3 3.9 の標準ライブラリだけを使う。
"""
import json
import os
import pwd
import sys
import types

HERE = os.path.dirname(os.path.realpath(__file__))
COPY = os.path.join(HERE, "vault", "check_note.py")
PROFILE = os.path.join(HERE, "check-vault-note.sb")
COPY_NAME = "claude/hooks/vault/check_note.py"


def checker_path(project):
    return project + "/_System/Scripts/check_note.py"


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def outside(project, python):
    try:
        note = json.loads(sys.stdin.buffer.read())["tool_input"]["file_path"]
    except Exception:
        return 0
    # 点検するのはプロジェクトの下の .md だけ。.. などは正規化しない（点検スクリプトが resolve() して、
    # Vault の外なら点検しない。読み込みは Seatbelt が Vault に閉じ込める）。
    if not isinstance(note, str) or not note.startswith(project + "/") or not note.endswith(".md"):
        return 0
    try:
        with open(COPY, "rb") as f:
            copy = f.read()
    except OSError:
        fail(f"Vault のノートを点検できない: dotfiles の写し {COPY_NAME} を読めない。ユーザーに確認を頼む。")
    try:
        with open(checker_path(project), "rb") as f:
            # 写しより長ければ違うと分かるので、それ以上は読まない。中身は出さない。
            vault = f.read(len(copy) + 1)
    except OSError:
        vault = None
    if vault != copy:
        fail(
            f"Vault の点検スクリプトが dotfiles の写し（{COPY_NAME}）と違うため点検しない。"
            "ユーザーに、差分のレビューと写しの更新を頼む。"
        )
    # Seatbelt はパスを realpath で比べるので、値も realpath で渡す。HOME は環境変数に頼らない。
    home = os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir)
    self_path = os.path.realpath(__file__)
    os.execv("/usr/bin/sandbox-exec", [
        "sandbox-exec", "-f", PROFILE,
        "-D", "HOME_DIR=" + home,
        "-D", "VAULT=" + os.path.realpath(project),
        "-D", "SELF=" + self_path,
        "-D", "COPY=" + os.path.realpath(COPY),
        python, "-I", "-B", self_path, "--run", project, note,
    ])


def run(project, note):
    with open(COPY, "rb") as f:
        src = f.read()
    # 点検スクリプトを直接実行したときと同じく __main__ として実行する。点検スクリプトは __file__ から
    # Vault のルートを決めるので、__file__ は Vault のパスにする。traceback の行は写しから読まれる。
    main = types.ModuleType("__main__")
    main.__file__ = checker_path(project)
    sys.modules["__main__"] = main
    sys.argv = [main.__file__, note]
    exec(compile(src, COPY, "exec", dont_inherit=True), main.__dict__)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--run"]:
        run(sys.argv[2], sys.argv[3])
    else:
        sys.exit(outside(sys.argv[1], sys.argv[2]))
