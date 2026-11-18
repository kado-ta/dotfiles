import contextlib
import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FILE = Path(__file__).resolve().parents[2] / "bin" / "cc-checkout-guard"
loader = importlib.machinery.SourceFileLoader("cc_checkout_guard", str(FILE))
spec = importlib.util.spec_from_loader(loader.name, loader)
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
loader.exec_module(guard)


def local_git(cwd, *args):
    cp = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if cp.returncode:
        raise AssertionError(cp.stderr)
    return cp.stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="claude-guard-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "sub").mkdir()
        local_git(self.repo, "init", "-b", "main")
        local_git(self.repo, "config", "user.name", "Test")
        local_git(self.repo, "config", "user.email", "test@example.com")
        (self.repo / "README.md").write_text("demo\n", encoding="utf-8")
        local_git(self.repo, "add", "README.md")
        local_git(self.repo, "commit", "-m", "init")
        # テスト自体が Claude Code の sandbox の中で動くので、実際の判定は使わない。
        self.real_in_sandbox = guard.in_sandbox
        patcher = mock.patch.object(guard, "in_sandbox", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, *argv, start=None, git_env=()):
        err = io.StringIO()
        result = guard.check(
            list(argv), start=start or self.repo, git_env=git_env, after_fetch=False,
            home=self.home, stdin=io.StringIO(), stderr=err, tty=False,
        )
        return result, err.getvalue()

    def parse(self, *argv, git_env=()):
        return guard.parse(self.repo, list(argv), git_env, self.home)


class ProtectedPathTests(Base):
    def test_protected_paths(self):
        for rel in (".claude/settings.json", "a/.Claude/Settings.json", ".claude", ".env",
                    "sub/.ENV.local", ".mcp.json", ".vscode/tasks.json", ".idea/workspace.xml",
                    "x/mise.lock"):
            with self.subTest(rel=rel):
                self.assertTrue(guard.is_protected(self.repo, rel, self.home))
        for rel in ("src/main.py", "docs/claude/x.md", "environment.txt", "mise.lock.bak"):
            with self.subTest(rel=rel):
                self.assertFalse(guard.is_protected(self.repo, rel, self.home))

    def test_dotfiles_paths_only_in_main_checkout(self):
        main = self.home / "dotfiles"
        for rel in ("claude/settings.json", "bin/.zshrc", "mise.toml", ".claude/rules/a.md", "CLAUDE.md"):
            with self.subTest(rel=rel):
                self.assertTrue(guard.is_protected(main, rel, self.home))
        self.assertFalse(guard.is_protected(main, "docs/x.md", self.home))
        for other in (main / ".claude/worktrees/x", self.home / "other"):
            with self.subTest(root=str(other)):
                self.assertFalse(guard.is_protected(other, "claude/settings.json", self.home))


class ParseTests(Base):
    def test_parse_global_options(self):
        self.assertEqual(self.parse("-C", "sub", "status").cwd, self.repo / "sub")
        inv = self.parse("-c", "merge.conflictStyle=diff3", "status")
        self.assertEqual(inv.config, ("merge.conflictStyle=diff3",))
        self.assertEqual(inv.sub, "status")
        with self.assertRaises(guard.GuardError):
            self.parse("--git-dir=x", "status")
        with self.assertRaises(guard.GuardError):
            self.parse("-c", "alias.s=switch s", "status")

    def test_alias_expansion(self):
        local_git(self.repo, "config", "alias.sw", "switch")
        inv = self.parse("sw", "x")
        self.assertEqual((inv.sub, inv.args), ("switch", ("x",)))
        local_git(self.repo, "config", "alias.sw2", "sw")
        self.assertEqual(self.parse("sw2", "x").sub, "switch")
        local_git(self.repo, "config", "alias.x", "!sh -c true")
        with self.assertRaises(guard.GuardError):
            self.parse("x")
        local_git(self.repo, "config", "alias.loop", "loop")
        with self.assertRaises(guard.GuardError):
            self.parse("loop")

    def test_git_env(self):
        self.assertEqual(self.parse("status", git_env=("GIT_EDITOR",)).sub, "status")
        for name in ("GIT_DIR", "GIT_CONFIG_COUNT"):
            with self.subTest(name=name):
                self.assertEqual(self.check("status", git_env=(name,))[0][0], 1)
                self.assertEqual(self.check("status", git_env=(name,))[0], (1, ""))


class CheckTests(Base):
    def test_read_only_and_help_allow(self):
        for argv in (("status",), ("log",), ("diff",), ("fetch",), ("switch", "-h"),
                     ("switch", "--help"), ("--version",)):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (0, ""))

    def test_outside_repository_allows(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.assertEqual(self.check("clone", "a", "b", start=outside)[0], (0, ""))
        self.assertEqual(self.check("switch", "x", start=outside)[0], (0, ""))

    def test_help_only_as_first_argument(self):
        for argv in (("stash", "push", "-m", "-h"), ("checkout", "feature", "--", ".claude", "-h")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (1, ""))

    def test_unreadable_repository_stops(self):
        local_git(self.repo, "config", "extensions.cc-probe", "1")
        local_git(self.repo, "config", "core.repositoryformatversion", "1")
        self.assertEqual(self.check("switch", "x")[0], (1, ""))

    def test_unknown_subcommand_stops(self):
        result, err = self.check("rebase", "main")
        self.assertEqual(result, (1, ""))
        self.assertIn("確かめられない", err)
        self.assertIn("command git", err)

    def test_in_sandbox_allows_everything(self):
        with mock.patch.object(guard, "in_sandbox", return_value=True):
            self.assertEqual(self.check("rebase", "main")[0], (0, ""))

    def test_sandbox_env_is_ignored(self):
        without = {k: v for k, v in os.environ.items() if k != "SANDBOX_RUNTIME"}
        # Base が差し替えた関数ではなく、本物を比べる。
        with mock.patch.dict(os.environ, without, clear=True):
            expected = self.real_in_sandbox()
        with mock.patch.dict(os.environ, {**without, "SANDBOX_RUNTIME": "1"}, clear=True):
            self.assertEqual(self.real_in_sandbox(), expected)

    def test_status_mode(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(guard.main(["status"]), 0)
        self.assertEqual(out.getvalue().strip(), "sandbox: no")

    def test_errors_fail_closed(self):
        with mock.patch.object(guard, "run_git", side_effect=OSError("boom")):
            result, err = self.check("status")
        self.assertEqual(result, (1, ""))
        self.assertIn("止めました", err)


if __name__ == "__main__":
    unittest.main()
