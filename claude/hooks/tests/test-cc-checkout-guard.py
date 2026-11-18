import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from pathlib import Path
from unittest import mock

FILE = Path(__file__).resolve().parents[2] / "bin" / "cc-checkout-guard"
loader = importlib.machinery.SourceFileLoader("cc_checkout_guard", str(FILE))
spec = importlib.util.spec_from_loader(loader.name, loader)
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
loader.exec_module(guard)


def local_git(cwd, *args, env=None, input=None):
    cp = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env, input=input)
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

    def check(self, *argv, start=None, git_env=(), tty=False, answer=""):
        err = io.StringIO()
        result = guard.check(
            list(argv), start=start or self.repo, git_env=git_env, after_fetch=False,
            home=self.home, stdin=io.StringIO(answer), stderr=err, tty=tty,
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
        result, err = self.check("switch", "x")
        self.assertEqual(result, (1, ""))
        self.assertIn("リポジトリを読めません", err)

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


class TreeBase(Base):
    """main: settings={"v": 1}・README=a。feature は両方を変え、docs は README だけを変える。"""

    def setUp(self):
        super().setUp()
        (self.repo / ".claude").mkdir()
        self.settings = self.repo / ".claude" / "settings.json"
        self.settings.write_text('{"v": 1}\n', encoding="utf-8")
        (self.repo / "README.md").write_text("a\n", encoding="utf-8")
        local_git(self.repo, "add", ".claude/settings.json", "README.md")
        local_git(self.repo, "commit", "-q", "-m", "main")
        self.branch("feature", "main", {".claude/settings.json": '{"v": 2}\n', "README.md": "b\n"})
        self.branch("docs", "main", {"README.md": "c\n"})

    def blob(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        cp = subprocess.run(["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"],
                            input=data, capture_output=True, check=True)
        return cp.stdout.decode().strip()

    def branch(self, name, base, files):
        """作業ツリーを変えずに、base に files を当てたブランチを作る。None は削除、(mode, 値) はその mode で入れる。"""
        env = {**os.environ, "GIT_INDEX_FILE": str(self.root / f"index-{name}")}
        local_git(self.repo, "read-tree", base, env=env)
        for path, value in files.items():
            if value is None:
                local_git(self.repo, "update-index", "--force-remove", "--", path, env=env)
                continue
            mode, data = value if isinstance(value, tuple) else ("100644", value)
            oid = data if mode == "160000" else self.blob(data)
            local_git(self.repo, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}", env=env)
        tree = local_git(self.repo, "write-tree", env=env)
        commit = local_git(self.repo, "commit-tree", tree, "-p", base, "-m", name, env=env)
        local_git(self.repo, "update-ref", f"refs/heads/{name}", commit)

    def stage(self, text):
        """作業ツリーを変えずに、index の settings だけを変える。"""
        local_git(self.repo, "update-index", "--cacheinfo", f"100644,{self.blob(text)},.claude/settings.json")


class SwitchTests(TreeBase):
    def test_switch_without_protected_change_allows(self):
        (code, out), err = self.check("switch", "docs")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        state = json.loads(out)
        self.assertEqual(state["root"], str(self.repo))
        old, new = state["expect"][".claude/settings.json"]
        self.assertEqual(old, new)

    def test_switch_stops_without_tty(self):
        result, err = self.check("switch", "feature")
        self.assertEqual(result, (1, ""))
        self.assertIn(".claude/settings.json", err)
        self.assertIn("git -C", err)
        self.assertNotIn(guard.MSG_ASK, err)

    def test_switch_asks_on_tty(self):
        blob = local_git(self.repo, "rev-parse", "feature:.claude/settings.json")
        for answer in ("y\n", "Y\n", "yes\n"):
            with self.subTest(answer=answer):
                (code, out), err = self.check("switch", "feature", tty=True, answer=answer)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out)["expect"][".claude/settings.json"][1], ["100644", blob])
                self.assertIn(guard.MSG_ASK, err)
                self.assertIn('-{"v": 1}', err)
                self.assertIn('+{"v": 2}', err)
        for answer in ("\n", "n\n", ""):
            with self.subTest(answer=answer):
                result, err = self.check("switch", "feature", tty=True, answer=answer)
                self.assertEqual(result, (1, ""))
                self.assertIn(guard.MSG_DECLINED, err)

    def test_checkout_forms(self):
        local_git(self.repo, "config", "alias.co", "checkout")
        self.assertEqual(self.check("co", "feature")[0], (1, ""))
        self.assertEqual(self.check("checkout", "feature", "--", "README.md")[0][0], 0)
        self.assertEqual(self.check("checkout", "feature", "--", ".claude")[0], (1, ""))

    def test_branch_wins_over_tag(self):
        # git の switch・checkout は、同じ名前の tag よりブランチを使う。tag で計算すると、確認を素通りする。
        local_git(self.repo, "tag", "feature", "docs")
        for argv in (("switch", "feature"), ("checkout", "feature"), ("checkout", "feature", "--", ".claude")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (1, ""))

    def test_unsupported_options_stop(self):
        for argv in (("switch", "-qf", "feature"), ("switch", "--merge", "feature"),
                     ("checkout", "--ours", "--", "README.md"), ("restore", "--source=feature", "-p", "x"),
                     ("checkout-index", "--prefix=x/", "-a"), ("reset", "--har"),
                     ("reset", "--hard", "--recurse-submodules")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("command git", err)

    def test_index_only_change_is_caught(self):
        self.stage('{"v": 9}\n')
        for argv in (("restore", ".claude/settings.json"), ("checkout", "--", ".claude/settings.json"),
                     ("checkout-index", "-f", "-a")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn('{"v": 9}', err)
        self.assertEqual(self.check("restore", "--staged", ".claude/settings.json")[0], (0, ""))

    def test_assume_unchanged_index_is_caught(self):
        # git diff は assume-unchanged の entry を変わっていないとみなすが、checkout はその中身を書く。
        self.stage('{"v": 9}\n')
        local_git(self.repo, "update-index", "--assume-unchanged", ".claude/settings.json")
        for argv in (("restore", ".claude/settings.json"), ("checkout", "--", ".claude"),
                     ("checkout-index", "-f", ".claude/settings.json")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn('{"v": 9}', err)

    def test_reset_hard_to_moved_branch(self):
        local_git(self.repo, "update-ref", "refs/heads/main", "feature")
        result, err = self.check("reset", "--hard")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)

    def test_reset_forms(self):
        self.assertEqual(self.check("reset", "--soft", "feature")[0], (0, ""))
        self.assertEqual(self.check("reset", "feature")[0], (0, ""))
        self.assertEqual(self.check("reset", "--hard", "docs")[0][0], 0)
        self.assertEqual(self.check("reset", "--keep", "feature")[0], (1, ""))

    def test_replace_ref_content_is_shown(self):
        original = local_git(self.repo, "rev-parse", "feature:.claude/settings.json")
        evil = self.blob('{"evil": 1}\n')
        local_git(self.repo, "replace", original, evil)
        result, err = self.check("switch", "feature", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn('"evil"', err)
        # 書く git も replace を効かせるので、状態の新は差し替えた後の中身になる。
        (code, out), _ = self.check("switch", "feature", tty=True, answer="y\n")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["expect"][".claude/settings.json"][1], ["100644", evil])

    def test_symlink_and_gitlink_stop_without_asking(self):
        head = local_git(self.repo, "rev-parse", "HEAD")
        self.branch("link", "main", {".claude/settings.json": ("120000", "../README.md")})
        self.branch("glink", "main", {".claude/hooks": ("160000", head)})
        for name, word in (("link", "symlink"), ("glink", "gitlink")):
            with self.subTest(name=name):
                result, err = self.check("switch", name, tty=True, answer="y\n")
                self.assertEqual(result, (1, ""))
                self.assertIn(word, err)
                self.assertNotIn(guard.MSG_ASK, err)

    def test_parent_becoming_symlink_stops(self):
        self.branch("nest", "main", {"x/.claude/settings.json": '{"n": 1}\n'})
        self.branch("nestlink", "nest", {"x/.claude/settings.json": None, "x": ("120000", "/tmp")})
        local_git(self.repo, "switch", "-q", "nest")
        result, err = self.check("switch", "nestlink", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("symlink", err)
        self.assertNotIn(guard.MSG_ASK, err)

    def test_dangerous_attributes_stop(self):
        info = self.repo / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text(".claude/** filter=lfs\n", encoding="utf-8")
        result, err = self.check("switch", "feature", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("filter", err)
        self.assertNotIn(guard.MSG_ASK, err)
        (info / "attributes").unlink()
        self.branch("enc", "feature", {".gitattributes": ".claude/settings.json working-tree-encoding=UTF-16\n"})
        result, err = self.check("switch", "enc", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("working-tree-encoding", err)
        self.assertNotIn(guard.MSG_ASK, err)
        # index だけにある .gitattributes も、checkout が書くときに読む。
        # lfs だと、テストの git が index を書くときに git-lfs を呼ぶので、設定のない名前にする。
        attrs = self.blob(".claude/** filter=probe\n")
        local_git(self.repo, "update-index", "--add", "--cacheinfo", f"100644,{attrs},.gitattributes")
        result, err = self.check("checkout", "feature", "--", ".claude/settings.json", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("filter", err)

    def test_deletion_is_shown(self):
        self.branch("gone", "main", {".claude/settings.json": None})
        result, err = self.check("switch", "gone", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除", err)
        # tree にないパスを消すのは、restore と --no-overlay の checkout だけ。
        for argv in (("checkout", "--no-overlay", "gone", "--", ".claude"), ("restore", "--source", "gone", ".claude")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn("削除", err)
        self.assertEqual(self.check("checkout", "gone", "--", ".claude")[0][0], 0)

    def test_pathspec_relative_to_subdirectory(self):
        self.stage('{"v": 9}\n')
        sub = self.repo / "sub"
        self.assertEqual(self.check("restore", "../.claude/settings.json", start=sub)[0], (1, ""))
        self.assertEqual(self.check("-C", "sub", "restore", "../.claude/settings.json")[0], (1, ""))
        # sub から見た .claude/settings.json は sub/.claude/settings.json で、ない。
        self.assertEqual(self.check("restore", ".claude/settings.json", start=sub)[0][0], 0)

    def test_unborn_and_detached_head(self):
        empty = self.root / "empty"
        empty.mkdir()
        local_git(empty, "init", "-q", "-b", "main")
        local_git(empty, "fetch", "-q", str(self.repo), "feature:feature")
        result, err = self.check("checkout", "feature", start=empty)
        self.assertEqual(result, (1, ""))
        self.assertIn("追加 .claude/settings.json", err)
        local_git(self.repo, "switch", "-q", "--detach", "main")
        result, err = self.check("switch", "feature")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)

    def test_verify(self):
        tasks = self.repo / ".vscode" / "tasks.json"
        tasks.parent.mkdir()
        tasks.write_text("{}\n", encoding="utf-8")
        local_git(self.repo, "add", ".vscode/tasks.json")
        (code, state), _ = self.check("switch", "feature", tty=True, answer="y\n")
        self.assertEqual(code, 0)

        def verify():
            err = io.StringIO()
            return guard.verify(state, err), err.getvalue()

        self.settings.write_text('{"v": 2}\n', encoding="utf-8")
        self.assertEqual(verify(), (0, ""))
        self.settings.write_text('{"v": 1}\n', encoding="utf-8")
        self.assertEqual(verify(), (0, ""))
        self.settings.write_text('{"v": 3}\n', encoding="utf-8")
        code, err = verify()
        self.assertEqual(code, 1)
        self.assertIn(guard.MSG_VERIFY, err)
        self.assertIn(".claude/settings.json", err)
        self.settings.write_text('{"v": 2}\n', encoding="utf-8")
        tasks.write_text('{"x": 1}\n', encoding="utf-8")
        code, err = verify()
        self.assertEqual(code, 1)
        self.assertIn(".vscode/tasks.json", err)
        self.assertNotIn(".claude/settings.json", err)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(guard.main(["verify", state]), 1)
            self.assertEqual(guard.main(["verify", "{"]), 1)

    def test_does_not_run_configured_programs(self):
        canary = self.root / "canary"
        script = self.root / "touch-canary"
        script.write_text(f"#!/bin/sh\ntouch '{canary}'\ncat\n", encoding="utf-8")
        script.chmod(0o755)
        (self.repo / ".gitattributes").write_text("* diff=x\nREADME.md filter=x\n", encoding="utf-8")
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        self.settings.write_text('{"v": 5}\n', encoding="utf-8")
        for key in ("core.fsmonitor", "core.pager", "diff.external", "diff.x.textconv",
                    "filter.x.clean", "filter.x.smudge"):
            local_git(self.repo, "config", key, str(script))
        # 仕掛けが効くことを、テストの git で確かめる。
        subprocess.run(["git", "-C", str(self.repo), "status"], capture_output=True)
        self.assertTrue(canary.exists())
        canary.unlink()
        for argv in (("switch", "feature"), ("restore", ".claude/settings.json"), ("reset", "--hard")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn(guard.MSG_ASK, err)
                self.assertFalse(canary.exists())

    def test_bang_message_quotes_arguments(self):
        spaced = self.root / "with space"
        local_git(self.root, "clone", "-q", str(self.repo), str(spaced))
        (spaced / ".claude" / "settings.json").write_text('{"v": 5}\n', encoding="utf-8")
        result, err = self.check("restore", "--", ".claude/settings.json", start=spaced)
        self.assertEqual(result, (1, ""))
        self.assertIn(f"git -C '{spaced}' restore -- .claude/settings.json", err)

    def test_control_characters_are_escaped(self):
        self.branch("esc", "main", {".claude/settings.json": '{"v": 1}\x1b[2K\r{"v": 2}\n'})
        result, err = self.check("switch", "esc", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertNotIn("\x1b", err)
        self.assertNotIn("\r", err)
        self.assertIn("<U+001B>", err)

    def evil_branch_and_tag(self):
        """ブランチ evil に悪い中身、同じ名前の tag に今の中身を置き、@{-1} を evil にする。"""
        self.branch("evil", "main", {".claude/settings.json": '{"evil": 1}\n'})
        local_git(self.repo, "switch", "-q", "evil")
        local_git(self.repo, "switch", "-q", "main")
        local_git(self.repo, "tag", "evil", "main")

    def test_previous_branch_wins_over_tag(self):
        # git は - と @{-N} をブランチの名前に戻して refs/heads を読む。rev-parse は同じ名前の tag を先に使う。
        self.evil_branch_and_tag()
        for argv in (("switch", "-"), ("checkout", "-"), ("checkout", "-", "--", ".claude/settings.json"),
                     ("switch", "@{-1}")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn('+{"evil": 1}', err)

    def test_case_changed_branch_name(self):
        # 大文字と小文字を区別しないファイルシステムでは、git は loose の refs/heads/evil を EVIL として読む。
        self.evil_branch_and_tag()
        if not (self.repo / ".git" / "refs" / "heads" / "EVIL").exists():
            self.skipTest("大文字と小文字を区別するファイルシステムでは、git も tag を使う")
        for argv in (("switch", "EVIL"), ("checkout", "EVIL"), ("checkout", "EVIL", "--", ".claude")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn('+{"evil": 1}', err)

    def approve_and_run(self, *argv):
        """確認で y と答え、本物の git を同じ引数で動かし、verify の結果を返す。"""
        (code, state), err = self.check(*argv, tty=True, answer="y\n")
        self.assertEqual(code, 0, err)
        local_git(self.repo, *argv)
        out = io.StringIO()
        return guard.verify(state, out), out.getvalue()

    def test_real_git_matches_state(self):
        self.assertEqual(self.approve_and_run("switch", "-q", "feature"), (0, ""))
        self.assertEqual(self.approve_and_run("switch", "-q", "main"), (0, ""))
        self.stage('{"v": 9}\n')
        self.assertEqual(self.approve_and_run("restore", ".claude/settings.json"), (0, ""))
        local_git(self.repo, "update-ref", "refs/heads/main", "feature")
        self.assertEqual(self.approve_and_run("reset", "-q", "--hard"), (0, ""))
        self.evil_branch_and_tag()
        self.assertEqual(self.approve_and_run("switch", "-q", "-"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"evil": 1}\n')

    def test_verify_catches_content_git_wrote_differently(self):
        (code, state), _ = self.check("switch", "feature", tty=True, answer="y\n")
        self.assertEqual(code, 0)
        # 確認と実行のあいだに、ブランチを差し替えられる。
        self.branch("swapped", "main", {".claude/settings.json": '{"evil": 1}\n'})
        local_git(self.repo, "update-ref", "refs/heads/feature", "swapped")
        local_git(self.repo, "switch", "-q", "feature")
        err = io.StringIO()
        self.assertEqual(guard.verify(state, err), 1)
        self.assertIn(guard.MSG_VERIFY, err.getvalue())
        self.assertIn(".claude/settings.json", err.getvalue())

    def test_verify_catches_new_protected_file(self):
        (code, state), _ = self.check("switch", "feature", tty=True, answer="y\n")
        self.assertEqual(code, 0)
        # 差し替えたブランチが、確認になかった対象のファイルを持ち込む。
        self.branch("extra", "feature", {".mcp.json": '{"servers": {}}\n'})
        local_git(self.repo, "update-ref", "refs/heads/feature", "extra")
        local_git(self.repo, "switch", "-q", "feature")
        err = io.StringIO()
        self.assertEqual(guard.verify(state, err), 1)
        self.assertIn(guard.MSG_VERIFY, err.getvalue())
        self.assertIn(".mcp.json", err.getvalue())
        self.assertNotIn(".claude/settings.json", err.getvalue())

    def test_invalid_utf8_is_shown_as_text(self):
        self.branch("latin", "main", {".claude/settings.json": b'{"v": "caf\xe9"}\n'})
        result, err = self.check("switch", "latin", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn(guard.MSG_ASK, err)
        self.assertIn('+{"v": "caf\\xe9"}', err)
        # 読めないバイトと「\xe9」という文字列は、表示は同じでも差分の行として出る。
        self.branch("literal", "main", {".claude/settings.json": '{"v": "caf\\xe9"}\n'})
        local_git(self.repo, "switch", "-q", "literal")
        result, err = self.check("switch", "latin", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn('-{"v": "caf\\xe9"}', err)
        self.assertIn('+{"v": "caf\\xe9"}', err)

    def test_nul_content_stops_without_asking(self):
        self.branch("nul", "main", {".claude/settings.json": b'{"v": 1}\x00\n'})
        result, err = self.check("switch", "nul", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("バイナリの中身", err)
        self.assertNotIn(guard.MSG_ASK, err)

    def test_literal_escape_text_and_real_escape_differ(self):
        self.branch("literal", "main", {".claude/settings.json": '{"v": "<U+001B>"}\n'})
        self.branch("real", "main", {".claude/settings.json": '{"v": "\x1b"}\n'})
        local_git(self.repo, "switch", "-q", "literal")
        result, err = self.check("switch", "real", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn('-{"v": "<U+001B>"}', err)
        self.assertIn('+{"v": "<U+001B>"}', err)
        self.assertNotIn("\x1b", err)

    def test_prompt_through_pty(self):
        for answer, expected in ((b"y\n", 0), (b"n\n", 1), (None, 1)):
            with self.subTest(answer=answer):
                code, out = self.run_in_pty(answer)
                self.assertEqual(code, expected, out)
                if answer is None:
                    # 標準入力が端末でなければ、聞かずに止める。
                    self.assertNotIn(guard.MSG_ASK, out)
                    self.assertIn("git -C", out)
                else:
                    self.assertIn(guard.MSG_ASK, out)

    def run_in_pty(self, answer):
        import pty

        sys.stdout.flush()
        sys.stderr.flush()
        try:
            pid, fd = pty.fork()
        except OSError as e:
            # Claude Code の sandbox の中では疑似端末を開けない。CI（macOS）では実際に動く。
            self.skipTest(f"疑似端末を開けません: {e}")
        if pid == 0:
            code = 99
            try:
                os.chdir(self.repo)
                if answer is None:
                    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
                # 起動したばかりのプロセスと同じく、0〜2 番から標準入出力を作り直す（テストの実行環境によらないため）。
                sys.stdin = open(0, encoding="utf-8", closefd=False)
                sys.stdout = open(1, "w", encoding="utf-8", closefd=False)
                sys.stderr = open(2, "w", encoding="utf-8", closefd=False)
                code = guard.main(["check", "--", "switch", "feature"])
            except BaseException:
                traceback.print_exc()
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(code)
        out = b""
        sent = answer is None
        prompt = guard.MSG_ASK.strip().encode()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 1)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
            if not sent and prompt in out:
                os.write(fd, answer)
                sent = True
        else:
            os.kill(pid, signal.SIGKILL)
        os.close(fd)
        _, status = os.waitpid(pid, 0)
        return os.waitstatus_to_exitcode(status), out.decode("utf-8", "replace")


if __name__ == "__main__":
    unittest.main()
