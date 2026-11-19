"""bin/.zshrc の git 関数（cc-checkout-guard の呼び出し）の回帰テスト。

印（# >>> cc-checkout-guard / # <<< cc-checkout-guard）のあいだを取り出し、
guard= を偽の確認コマンドに置き換えて、/bin/zsh -f で実際に動かす。
"""

from __future__ import annotations

import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ZSHRC = Path(__file__).resolve().parents[3] / "bin" / ".zshrc"
BEGIN = "# >>> cc-checkout-guard"
END = "# <<< cc-checkout-guard"

# 偽の確認コマンド。呼ばれた引数を LOG に記録し、終了コードと出力は用意したファイルから返す。
FAKE_GUARD = """#!/bin/sh
{ printf 'guard'; for a in "$@"; do printf ' [%s]' "$a"; done; printf '\\n'; } >> "$FAKE_DIR/log"
case "$1" in
  check)
    [ -f "$FAKE_DIR/check1.out" ] && cat "$FAKE_DIR/check1.out"
    exit "$(cat "$FAKE_DIR/check1.rc")"
    ;;
  verify)
    exit "$(cat "$FAKE_DIR/verify.rc")"
    ;;
esac
exit 1
"""

# 偽の git。呼ばれた引数を LOG に記録し、FAKE_DIR/git.rc の値で終了する。
FAKE_GIT = """#!/bin/sh
{ printf 'git'; for a in "$@"; do printf ' [%s]' "$a"; done; printf '\\n'; } >> "$FAKE_DIR/log"
exit "$(cat "$FAKE_DIR/git.rc")"
"""


def extract_block() -> str:
    text = ZSHRC.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r"\n(.*?)" + re.escape(END), text, re.S)
    if not m:
        raise AssertionError("bin/.zshrc に cc-checkout-guard の印がありません")
    return m.group(1)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="checkout-fn-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name).resolve()
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.guard = self.dir / "guard"
        self.write_exec(self.guard, FAKE_GUARD)
        self.write_exec(self.bin / "git", FAKE_GIT)
        self.set("check1.rc", "0")
        self.set("verify.rc", "0")
        self.set("git.rc", "0")

    def write_exec(self, path: Path, body: str) -> None:
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def set(self, name: str, value, binary: bool = False) -> None:
        data = value if isinstance(value, bytes) else str(value).encode()
        (self.dir / name).write_bytes(data)

    def run_fn(self, *args: str, guard: Path | None = None, extra_env=None):
        block = extract_block()
        g = guard if guard is not None else self.guard
        # guard= の値だけを偽の確認コマンドに置き換える
        block, n = re.subn(r"local guard=\S+", f"local guard={g}", block)
        self.assertEqual(n, 1)
        script = block + "\ngit " + " ".join(args) + "\n"
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.dir),
            "FAKE_DIR": str(self.dir),
        }
        env.update(extra_env or {})
        cp = subprocess.run(["/bin/zsh", "-f", "-c", script], capture_output=True, env=env)
        log = (self.dir / "log")
        lines = log.read_text().splitlines() if log.exists() else []
        return cp, lines


class CheckoutFunctionTest(Base):
    def test_stops_when_check_fails(self):
        self.set("check1.rc", "1")
        cp, log = self.run_fn("switch", "x")
        self.assertEqual(cp.returncode, 1)
        self.assertFalse([l for l in log if l.startswith("git ")])

    def test_runs_git_and_verify(self):
        self.set("check1.out", "STATE")
        self.set("git.rc", "5")
        cp, log = self.run_fn("switch", "x")
        self.assertEqual(cp.returncode, 5)
        git_lines = [l for l in log if l.startswith("git ")]
        self.assertEqual(git_lines, ["git [switch] [x]"])
        self.assertEqual(log[-1], "guard [verify] [STATE]")
        self.assertLess(log.index("git [switch] [x]"), log.index("guard [verify] [STATE]"))

    def test_no_verify_without_state(self):
        cp, log = self.run_fn("switch", "x")
        self.assertEqual(cp.returncode, 0)
        self.assertIn("git [switch] [x]", log)
        self.assertFalse([l for l in log if l.startswith("guard [verify]")])

    def test_pull_stops_without_git(self):
        # 確認コマンドは pull を止める（D1）。関数は git（先の fetch も）を動かさずに、その終了コードを返す。
        self.set("check1.rc", "1")
        cp, log = self.run_fn("pull")
        self.assertEqual(cp.returncode, 1)
        self.assertEqual(log, ["guard [check] [--git-env] [] [--] [pull]"])

    def test_other_codes_are_returned(self):
        # 終了コード 3（前の pull の手順）も、ほかの 0 以外と同じく、git を動かさずにそのまま返す（D1）。
        self.set("check1.rc", "3")
        self.set("check1.out", b"fetch\0origin")
        cp, log = self.run_fn("pull")
        self.assertEqual(cp.returncode, 3)
        self.assertEqual(log, ["guard [check] [--git-env] [] [--] [pull]"])

    def test_verify_failure_returns_nonzero(self):
        self.set("check1.out", "STATE")
        self.set("verify.rc", "1")
        cp, _ = self.run_fn("switch", "x")
        self.assertEqual(cp.returncode, 1)

    def test_missing_guard(self):
        cp, log = self.run_fn("switch", "x", guard=self.dir / "none")
        self.assertEqual(cp.returncode, 1)
        self.assertIn("README.md", cp.stderr.decode())
        self.assertFalse([l for l in log if l.startswith("git ")])

    def test_git_env_names(self):
        cp, log = self.run_fn("switch", "x", extra_env={"GIT_FOO": "1"})
        check = [l for l in log if l.startswith("guard [check]")][0]
        self.assertIn("[--git-env] [GIT_FOO]", check)
        self.assertNotIn("GIT_BAR", check)

    def test_git_env_excludes_unexported(self):
        block = extract_block()
        block = re.sub(r"local guard=\S+", f"local guard={self.guard}", block)
        script = "GIT_BAR=1\nexport GIT_FOO=1\n" + block + "\ngit switch x\n"
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.dir), "FAKE_DIR": str(self.dir)}
        subprocess.run(["/bin/zsh", "-f", "-c", script], capture_output=True, env=env)
        check = [l for l in (self.dir / "log").read_text().splitlines() if l.startswith("guard [check]")][0]
        self.assertIn("[--git-env] [GIT_FOO]", check)
        self.assertNotIn("GIT_BAR", check)

    def test_sandbox_runtime_does_not_skip(self):
        self.set("check1.rc", "1")
        cp, log = self.run_fn("switch", "x", extra_env={"SANDBOX_RUNTIME": "1"})
        self.assertEqual(cp.returncode, 1)
        self.assertTrue([l for l in log if l.startswith("guard [check]")])
        self.assertFalse([l for l in log if l.startswith("git ")])

    def test_block_is_after_mise(self):
        text = ZSHRC.read_text(encoding="utf-8")
        self.assertIn(BEGIN, text)
        self.assertGreater(text.index(BEGIN), text.index('eval "$(mise activate zsh)"'))


if __name__ == "__main__":
    unittest.main()
