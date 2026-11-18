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

    def check(self, *argv, start=None, git_env=(), tty=False, answer="", after_fetch=False):
        err = io.StringIO()
        result = guard.check(
            list(argv), start=start or self.repo, git_env=git_env, after_fetch=after_fetch,
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
        # 先頭以外の -h はヘルプではない（stash push -m -h はメッセージ -h で stash する）。
        # ヘルプとして素通りする (0, "") にならず、確認（状態つき）か停止になる。
        for argv in (("stash", "push", "-m", "-h"), ("checkout", "feature", "--", ".claude", "-h")):
            with self.subTest(argv=argv):
                self.assertNotEqual(self.check(*argv)[0], (0, ""))

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

    def commit_settings(self, text):
        self.settings.write_text(text, encoding="utf-8")
        local_git(self.repo, "commit", "-q", "-am", "settings")

    def approve_and_run(self, *argv, codes=(0,)):
        """確認で y と答え、本物の git を同じ引数で動かし、verify の結果を返す。"""
        (code, state), err = self.check(*argv, tty=True, answer="y\n")
        self.assertEqual(code, 0, err)
        cp = subprocess.run(["git", "-C", str(self.repo), *argv], capture_output=True, text=True)
        self.assertIn(cp.returncode, codes, cp.stderr)
        out = io.StringIO()
        return guard.verify(state, out), out.getvalue()

    def evil_branch_and_tag(self):
        """ブランチ evil に悪い中身、同じ名前の tag に今の中身を置き、@{-1} を evil にする。"""
        self.branch("evil", "main", {".claude/settings.json": '{"evil": 1}\n'})
        local_git(self.repo, "switch", "-q", "evil")
        local_git(self.repo, "switch", "-q", "main")
        local_git(self.repo, "tag", "evil", "main")


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
        for argv in (("switch", "feature"), ("restore", ".claude/settings.json"), ("reset", "--hard"),
                     ("merge", "feature"), ("cherry-pick", "feature"), ("stash",)):
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

    def test_previous_checkout_named_head_stops(self):
        # 前のチェックアウトの名前が HEAD だと、git は refs/heads/HEAD を使うが、check-ref-format --branch は失敗し、
        # rev-parse @{-1} は今の HEAD を返す。どちらにも合わせられないので止める。
        self.branch("evil", "main", {".claude/settings.json": '{"evil": 1}\n'})
        main = local_git(self.repo, "rev-parse", "main")
        heads = self.repo / ".git" / "refs" / "heads"
        (heads / "HEAD").write_text(local_git(self.repo, "rev-parse", "evil") + "\n", encoding="utf-8")
        with open(self.repo / ".git" / "logs" / "HEAD", "a", encoding="utf-8") as f:
            f.write(f"{main} {main} Test <test@example.com> 1900000000 +0000\tcheckout: moving from HEAD to main\n")
        for argv in (("switch", "-"), ("checkout", "-"), ("switch", "@{-1}"),
                     ("checkout", "-", "--", ".claude/settings.json")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="y\n")
                self.assertEqual(result, (1, ""))
                self.assertIn("@{-1} がどのブランチかを確かめられません", err)
                self.assertNotIn(guard.MSG_ASK, err)

    def test_previous_detached_checkout_still_resolves(self):
        # 前が detached のときは、check-ref-format --branch が oid を出し、これまでどおり計算する。
        local_git(self.repo, "switch", "-q", "--detach", "feature")
        local_git(self.repo, "switch", "-q", "main")
        result, err = self.check("switch", "-", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn('+{"v": 2}', err)

    def test_broken_branch_stops(self):
        # ない object を指すブランチは、同じ名前の tag に落とさずに止める。
        oid = local_git(self.repo, "rev-parse", "main")
        local_git(self.repo, "tag", "ghost", "main")
        (self.repo / ".git" / "refs" / "heads" / "ghost").write_text("1" * len(oid) + "\n", encoding="utf-8")
        for argv in (("switch", "ghost"), ("checkout", "ghost"), ("checkout", "ghost", "--", ".claude")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("ブランチ ghost を読めません", err)

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


class MergeTests(TreeBase):
    def test_merge(self):
        (code, out), err = self.check("merge", "docs")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["root"], str(self.repo))
        result, err = self.check("merge", "feature")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)

    def test_conflicting_merge_still_checked(self):
        self.commit_settings('{"v": 3}\n')
        result, err = self.check("merge", "feature", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("+<<<<<<< HEAD", err)
        self.assertIn("+>>>>>>> feature", err)

    def test_merge_abort(self):
        self.settings.write_text('{"v": 5}\n', encoding="utf-8")
        result, err = self.check("merge", "--abort")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        self.assertEqual(self.check("merge", "--quit")[0], (0, ""))
        self.assertEqual(self.check("merge", "--continue")[0], (0, ""))
        self.assertEqual(self.check("merge", "--abort", "-q")[0], (1, ""))

    def test_pull_fetch_protocol(self):
        origin = self.root / "origin.git"
        local_git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        local_git(self.repo, "remote", "add", "origin", str(origin))
        local_git(self.repo, "push", "-q", "-u", "origin", "main")
        other = self.root / "other"
        local_git(self.root, "clone", "-q", str(origin), str(other))
        local_git(other, "config", "user.name", "Test")
        local_git(other, "config", "user.email", "test@example.com")
        (other / "README.md").write_text("r\n", encoding="utf-8")
        local_git(other, "commit", "-q", "-am", "readme")
        local_git(other, "push", "-q", "origin", "main")
        self.assertEqual(self.check("pull")[0], (3, "fetch\0origin"))
        local_git(self.repo, "fetch", "-q", "origin")
        (code, out), err = self.check("pull", after_fetch=True)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["root"], str(self.repo))
        (other / ".claude" / "settings.json").write_text('{"v": 7}\n', encoding="utf-8")
        local_git(other, "commit", "-q", "-am", "settings")
        local_git(other, "push", "-q", "origin", "main")
        self.assertEqual(self.check("-C", "sub", "pull", "--ff-only")[0], (3, "-C\0sub\0fetch\0origin"))
        local_git(self.repo, "fetch", "-q", "origin")
        result, err = self.check("pull", "--ff-only", after_fetch=True)
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)

    def test_pull_unsupported_forms(self):
        result, err = self.check("pull", "origin", "main")
        self.assertEqual(result, (1, ""))
        self.assertIn("pull の引数", err)
        local_git(self.repo, "config", "pull.rebase", "true")
        result, err = self.check("pull")
        self.assertEqual(result, (1, ""))
        self.assertIn("rebase", err)

    def test_merge_settings_that_change_the_result_stop(self):
        for key, value in (("merge.renormalize", "true"), ("merge.autoStash", "true"), ("pull.twohead", "resolve"),
                           ("branch.main.mergeOptions", "-X theirs")):
            with self.subTest(key=key):
                local_git(self.repo, "config", key, value)
                result, err = self.check("merge", "docs")
                self.assertEqual(result, (1, ""))
                self.assertIn(key, err)
                local_git(self.repo, "config", "--unset", key)
        self.assertEqual(self.check("merge", "docs")[0][0], 0)
        # pull は pull.autoStash で git merge --autostash を動かす（レビューで実測）。
        local_git(self.repo, "config", "pull.autoStash", "true")
        for argv in (("pull",), ("-c", "pull.autoStash=false", "-c", "pull.autoStash=true", "pull")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("pull.autoStash", err)
        local_git(self.repo, "config", "--unset", "pull.autoStash")
        result, err = self.check("-c", "pull.autoStash=true", "pull")
        self.assertEqual(result, (1, ""))
        self.assertIn("pull.autoStash", err)

    def test_merge_fetch_head_reads_merge_lines(self):
        # git merge FETCH_HEAD は、not-for-merge でない行をすべて取り込む（2 行以上なら octopus）。
        # rev-parse FETCH_HEAD は 1 行目だけを読む（レビューで実測）。
        docs, feature = (local_git(self.repo, "rev-parse", name) for name in ("docs", "feature"))
        fetch_head = self.repo / ".git" / "FETCH_HEAD"
        fetch_head.write_text(f"{docs}\t\tbranch 'docs' of x\n{feature}\t\tbranch 'feature' of x\n", encoding="utf-8")
        result, err = self.check("merge", "FETCH_HEAD")
        self.assertEqual(result, (1, ""))
        self.assertIn("FETCH_HEAD", err)
        fetch_head.write_text(f"{docs}\tnot-for-merge\tbranch 'docs' of x\n{feature}\t\tbranch 'feature' of x\n",
                              encoding="utf-8")
        result, err = self.check("merge", "FETCH_HEAD")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        fetch_head.write_text(f"{feature}\tnot-for-merge\tbranch 'feature' of x\n{docs}\t\tbranch 'docs' of x\n",
                              encoding="utf-8")
        self.assertEqual(self.check("merge", "FETCH_HEAD")[0][0], 0)
        # 衝突の印のラベルは、取り込むコミットの oid になる（実測）。
        self.commit_settings('{"v": 3}\n')
        fetch_head.write_text(f"{feature}\t\tbranch 'feature' of x\n", encoding="utf-8")
        self.assertEqual(self.approve_and_run("merge", "--no-edit", "-q", "FETCH_HEAD", codes=(1,)), (0, ""))
        self.assertIn(f">>>>>>> {feature}", self.settings.read_text(encoding="utf-8"))

    def test_merge_driver_is_not_run(self):
        # merge-tree は、作業ツリーの .gitattributes と .git/info/attributes の merge 属性で、設定のドライバーを動かす（実測）。
        canary = self.root / "canary"
        script = self.root / "merge-canary"
        script.write_text(f"#!/bin/sh\ntouch '{canary}'\n", encoding="utf-8")
        script.chmod(0o755)
        (self.repo / "README.md").write_text("s\n", encoding="utf-8")
        local_git(self.repo, "stash", "-q")
        (self.repo / "README.md").write_text("m\n", encoding="utf-8")
        local_git(self.repo, "commit", "-q", "-am", "readme")
        local_git(self.repo, "config", "merge.x.driver", f"{script} %O %A %B")
        info = self.repo / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("* merge=x\n", encoding="utf-8")
        # 仕掛けが効くことを、テストの git で確かめる（README は両側で変わっている）。
        subprocess.run(["git", "-C", str(self.repo), "merge-tree", "--write-tree", "HEAD", "feature"],
                       capture_output=True)
        self.assertTrue(canary.exists())
        canary.unlink()
        for argv in (("merge", "feature"), ("cherry-pick", "feature"), ("stash", "pop")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="y\n")
                self.assertEqual(result, (1, ""))
                self.assertIn("merge.x.driver", err)
                self.assertFalse(canary.exists())

    def test_planted_autostash_stops(self):
        # MERGE_AUTOSTASH は sandbox から置け、git は merge・--continue・--abort の後にその中身を書く（実測）。
        self.settings.write_text('{"evil": 1}\n', encoding="utf-8")
        stash = local_git(self.repo, "stash", "create")
        local_git(self.repo, "checkout", "--", ".claude/settings.json")
        (self.repo / ".git" / "MERGE_AUTOSTASH").write_text(stash + "\n", encoding="utf-8")
        for argv in (("merge", "docs"), ("merge", "--abort"), ("merge", "--continue")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("MERGE_AUTOSTASH", err)
        # --quit は作業ツリーを書かず、自動の stash を stash の一覧に入れる。
        self.assertEqual(self.check("merge", "--quit")[0], (0, ""))

    def test_commit_with_planted_autostash_stops(self):
        # git commit（--amend も、MERGE_HEAD がなくても）と、git commit を動かす cherry-pick -e・revert -e は、
        # コミットの後に MERGE_AUTOSTASH の中身を書く（実測）。
        self.settings.write_text('{"evil": 1}\n', encoding="utf-8")
        stash = local_git(self.repo, "stash", "create")
        local_git(self.repo, "checkout", "--", ".claude/settings.json")
        (self.repo / ".git" / "MERGE_HEAD").write_text(local_git(self.repo, "rev-parse", "docs") + "\n",
                                                       encoding="utf-8")
        autostash = self.repo / ".git" / "MERGE_AUTOSTASH"
        autostash.write_text(stash + "\n", encoding="utf-8")
        local_git(self.repo, "config", "alias.ci", "commit")
        for argv in (("commit", "-q", "--no-edit"), ("ci", "-m", "x"), ("commit", "--amend", "--no-edit"),
                     ("cherry-pick", "-e", "feature"), ("revert", "-e", "HEAD")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("MERGE_AUTOSTASH", err)
                self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 1}\n')
        autostash.unlink()
        for argv in (("commit", "-q", "--no-edit"), ("ci", "-m", "x"), ("commit", "--amend", "--no-edit")):
            with self.subTest(argv=argv, autostash=False):
                self.assertEqual(self.check(*argv), ((0, ""), ""))

    def test_rerere_stops_protected_conflict(self):
        # rr-cache があると、git は記録した解決を衝突したファイルに書く（rerere.enabled がなくても。実測）。
        self.commit_settings('{"v": 3}\n')
        (self.repo / ".git" / "rr-cache").mkdir()
        result, err = self.check("merge", "feature", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("rerere", err)
        self.assertNotIn(guard.MSG_ASK, err)
        local_git(self.repo, "config", "rerere.enabled", "false")
        result, err = self.check("merge", "feature", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn(guard.MSG_ASK, err)

    def test_real_git_merge_matches_state(self):
        self.assertEqual(self.approve_and_run("merge", "--no-edit", "-q", "feature"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 2}\n')
        local_git(self.repo, "reset", "-q", "--hard", "HEAD~1")
        self.commit_settings('{"v": 3}\n')
        # 衝突の印のラベルも、merge-tree と git merge で同じになる（実測）。
        self.assertEqual(self.approve_and_run("merge", "--no-edit", "-q", "feature", codes=(1,)), (0, ""))
        self.assertIn(">>>>>>> feature", self.settings.read_text(encoding="utf-8"))


class StashAndPickTests(TreeBase):
    def test_stash(self):
        self.settings.write_text('{"v": 5}\n', encoding="utf-8")
        result, err = self.check("stash")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        local_git(self.repo, "stash", "-q")
        result, err = self.check("stash", "pop")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        local_git(self.repo, "stash", "drop", "-q")
        (self.repo / ".env.local").write_text("A=1\n", encoding="utf-8")
        result, err = self.check("stash", "-u")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 .env.local", err)
        local_git(self.repo, "stash", "-q", "-u")
        result, err = self.check("stash", "pop")
        self.assertEqual(result, (1, ""))
        self.assertIn("追加 .env.local", err)
        for argv in (("stash", "list"), ("stash", "show", "-p"), ("stash", "drop")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (0, ""))
        self.assertEqual(self.check("stash", "branch", "x")[0], (1, ""))

    def test_stash_keep_index_with_staged_protected_file_stops(self):
        # -k は、HEAD に戻した後に index の中身を書く（実測）。
        self.stage('{"evil": 1}\n')
        result, err = self.check("stash", "-k")
        self.assertEqual(result, (1, ""))
        self.assertIn("stash -k", err)

    def test_cherry_pick_and_revert(self):
        result, err = self.check("cherry-pick", "feature")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        self.assertEqual(self.check("cherry-pick", "docs")[0][0], 0)
        result, err = self.check("revert", "HEAD")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 .claude/settings.json", err)
        for argv in (("cherry-pick", "main..feature"), ("cherry-pick", "feature^!"), ("cherry-pick", "^main"),
                     ("cherry-pick", "--continue")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (1, ""))

    def test_merge_commit_pick_stops(self):
        local_git(self.repo, "merge", "-q", "--no-ff", "--no-edit", "docs")
        result, err = self.check("cherry-pick", "HEAD")
        self.assertEqual(result, (1, ""))
        self.assertIn("マージコミット", err)

    def test_protected_conflict_stops_pick_and_stash(self):
        # cherry-pick・revert・stash の衝突の印は、merge-tree とラベルが違う（実測）。
        self.settings.write_text('{"v": 4}\n', encoding="utf-8")
        local_git(self.repo, "stash", "-q")
        self.commit_settings('{"v": 3}\n')
        for argv in (("cherry-pick", "feature"), ("stash", "pop")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="y\n")
                self.assertEqual(result, (1, ""))
                self.assertIn(".claude/settings.json が衝突します", err)
                self.assertNotIn(guard.MSG_ASK, err)

    def test_staged_changes_stop_stash_apply_and_pick(self):
        # stash apply と cherry-pick -n は、HEAD ではなく index を tree にして merge する（実測）。
        self.settings.write_text('{"v": 4}\n', encoding="utf-8")
        local_git(self.repo, "stash", "-q")
        notes = self.blob("staged\n")
        local_git(self.repo, "update-index", "--add", "--cacheinfo", f"100644,{notes},notes.txt")
        for argv in (("stash", "apply"), ("cherry-pick", "-n", "feature"), ("revert", "-n", "HEAD")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("index に HEAD と違う変更があります", err)

    def test_real_git_pick_and_stash_match_state(self):
        self.assertEqual(self.approve_and_run("cherry-pick", "feature"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 2}\n')
        self.settings.write_text('{"v": 5}\n', encoding="utf-8")
        self.assertEqual(self.approve_and_run("stash", "-q"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 2}\n')
        self.assertEqual(self.approve_and_run("stash", "pop", "-q"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 5}\n')


class RevisionTests(TreeBase):
    def branch_and_tag(self):
        """ブランチ evil に {"evil": 1}、同じ名前の tag に {"tag": 1} を置き、@{-1} を evil にする。"""
        self.branch("evil", "main", {".claude/settings.json": '{"evil": 1}\n'})
        self.branch("tagged", "main", {".claude/settings.json": '{"tag": 1}\n'})
        local_git(self.repo, "tag", "evil", "tagged")
        local_git(self.repo, "branch", "-q", "-D", "tagged")
        local_git(self.repo, "switch", "-q", "evil")
        local_git(self.repo, "switch", "-q", "main")

    def test_revs_resolve_like_git(self):
        # merge・cherry-pick・worktree add --detach は rev-parse と同じく tag を先に使い、
        # worktree add（-b・--detach なし）はブランチを先に使う（実測）。
        self.branch_and_tag()
        cases = [(("merge", "evil"), "tag"), (("merge", "-"), "tag"), (("merge", "@{-1}"), "tag"),
                 (("cherry-pick", "evil"), "tag"), (("cherry-pick", "-"), "tag"),
                 (("worktree", "add", "../wt", "evil"), "evil"), (("worktree", "add", "../wt", "-"), "evil"),
                 (("worktree", "add", "--detach", "../wt", "evil"), "tag")]
        if (self.repo / ".git" / "refs" / "heads" / "EVIL").exists():
            cases += [(("merge", "EVIL"), "tag"), (("cherry-pick", "EVIL"), "tag"),
                      (("worktree", "add", "../wt", "EVIL"), "evil")]
        for argv, shown in cases:
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn(f'+{{"{shown}": 1}}', err)

    def test_real_git_resolves_tag_and_branch_like_state(self):
        self.branch_and_tag()
        self.assertEqual(self.approve_and_run("merge", "--no-edit", "-q", "evil"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"tag": 1}\n')
        self.assertEqual(self.approve_and_run("worktree", "add", "-q", "../wt", "evil"), (0, ""))
        wt = self.root / "wt" / ".claude" / "settings.json"
        self.assertEqual(wt.read_text(encoding="utf-8"), '{"evil": 1}\n')
        # 元のチェックアウトと同じ中身なら確認なしで通り、状態は新しい作業ツリーの中身を確かめる。
        self.assertEqual(self.approve_and_run("worktree", "add", "-q", "--detach", "../wt2", "evil"), (0, ""))
        wt2 = self.root / "wt2" / ".claude" / "settings.json"
        self.assertEqual(wt2.read_text(encoding="utf-8"), '{"tag": 1}\n')


class OtherWriteTests(TreeBase):
    def test_rm_clean_mv(self):
        result, err = self.check("rm", ".claude/settings.json")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 .claude/settings.json", err)
        self.assertEqual(self.check("rm", "--cached", ".claude/settings.json")[0], (0, ""))
        (self.repo / ".env.local").write_text("A=1\n", encoding="utf-8")
        result, err = self.check("clean", "-fdx")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 .env.local", err)
        self.assertEqual(self.check("clean", "-n")[0], (0, ""))
        self.assertEqual(self.check("mv", "README.md", ".claude/x.md")[0], (1, ""))
        self.assertEqual(self.check("mv", "README.md", "R.md")[0], (0, ""))

    def test_clean_counts_quiet_quoted_and_directory_removals(self):
        (self.repo / "sub" / "deep").mkdir()
        (self.repo / "sub" / "deep" / ".env").write_text("A=1\n", encoding="utf-8")
        (self.repo / '.env"q').write_text("A=1\n", encoding="utf-8")
        # -q は --dry-run の一覧も消すので、打ち消して数える（実測）。
        result, err = self.check("clean", "-fdq")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 sub/deep/.env", err)
        self.assertIn('削除 .env"q', err)
        result, err = self.check("clean", "-f", "-d", start=self.repo / "sub")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 sub/deep/.env", err)
        self.assertNotIn('.env"q', err)
        for argv in (("clean", "-i"), ("clean", "-fdi"), ("clean", "--dry")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (1, ""))
        self.assertEqual(self.check("clean", "-fe", "x", "-n")[0], (0, ""))

    def test_mv_into_directory_and_of_directory(self):
        self.assertEqual(self.check("mv", "README.md", ".claude")[0], (1, ""))
        self.assertEqual(self.check("mv", "README.md", "sub")[0], (0, ""))
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / ".env.example").write_text("A=1\n", encoding="utf-8")
        local_git(self.repo, "add", "pkg")
        result, err = self.check("mv", "pkg", "lib")
        self.assertEqual(result, (1, ""))
        self.assertIn("pkg/.env.example", err)

    def test_worktree_add_compares_with_main_checkout(self):
        result, err = self.check("worktree", "add", "../wt", "feature")
        self.assertEqual(result, (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        (code, out), err = self.check("worktree", "add", "../wt2", "docs")
        self.assertEqual(code, 0, err)
        state = json.loads(out)
        self.assertEqual(state["root"], str(self.root / "wt2"))
        self.assertIsNone(state["expect"][".claude/settings.json"][0])
        self.assertEqual(self.check("worktree", "list")[0], (0, ""))
        self.assertEqual(self.check("worktree", "add", "--orphan", "../wt3")[0], (1, ""))
        self.assertEqual(self.check("worktree", "add", "--no-checkout", "../wt3", "feature")[0], (0, ""))
        # 行き先の途中が symlink なら、git は別の場所に書くので止める。
        (self.root / "elsewhere").mkdir()
        (self.root / "link").symlink_to(self.root / "elsewhere")
        for path in ("../link", "../link/wt"):
            with self.subTest(path=path):
                result, err = self.check("worktree", "add", path, "docs")
                self.assertEqual(result, (1, ""))
                self.assertIn("symlink", err)

    def test_worktree_add_symlink_parent_stops(self):
        self.branch("nest", "main", {"x/.claude/settings.json": '{"n": 1}\n'})
        self.branch("nestlink", "nest", {"x/.claude/settings.json": None, "x": ("120000", "/tmp")})
        local_git(self.repo, "switch", "-q", "nest")
        result, err = self.check("worktree", "add", "../wt", "nestlink", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("x がsymlink", err)
        self.assertNotIn(guard.MSG_ASK, err)

    def test_worktree_add_checks_attributes_of_unchanged_files(self):
        # 新しい作業ツリーには、元のチェックアウトと同じ中身の対象も書かれ、属性はそれにも効く（レビューで実測）。
        info = self.repo / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text(".claude/settings.json working-tree-encoding=UTF-16\n", encoding="utf-8")
        result, err = self.check("worktree", "add", "../wt", "docs", tty=True, answer="y\n")
        self.assertEqual(result, (1, ""))
        self.assertIn("working-tree-encoding", err)
        self.assertNotIn(guard.MSG_ASK, err)

    def test_worktree_into_protected_place_stops(self):
        # 新しい作業ツリーの中のファイルは、今と元のチェックアウトから見ると対象のパスになりうる（レビューで実測）。
        self.branch("skill", "main", {"SKILL.md": "# evil\n"})
        result, err = self.check("worktree", "add", ".claude/skills/x", "skill")
        self.assertEqual(result, (1, ""))
        self.assertIn(".claude/skills/x", err)
        wt = self.root / "wt"
        local_git(self.repo, "worktree", "add", "-q", str(wt), "docs")
        # 元のチェックアウトの対象の中も止める（今のチェックアウトは wt）。
        result, err = self.check("worktree", "add", "../repo/.claude/skills/z", "skill", start=wt)
        self.assertEqual(result, (1, ""))
        self.assertIn(".claude/skills/z", err)
        # move の行き先も同じ（R18）。行き先がディレクトリなら、git はその中に同じ名前で動かす。
        for dest in (".claude/skills/y", ".claude"):
            with self.subTest(dest=dest):
                result, err = self.check("worktree", "move", "../wt", dest)
                self.assertEqual(result, (1, ""))
                self.assertIn(".claude", err)
        self.assertEqual(self.check("worktree", "move", "../wt", "../wt-moved")[0], (0, ""))
        self.assertEqual(self.check("worktree", "move", "../wt", "sub")[0], (0, ""))

    def test_worktree_destinations_resolve_like_git(self):
        # 行き先は、git と同じく物理的に決まる（再レビューで実測）。決めきれない形は止める。
        self.branch("skill", "main", {"SKILL.md": "# evil\n"})
        protected_place = "は自動で読み込まれるパスの中です"
        # (a) symlink の後の ..: git は symlink の先の親に書く。
        (self.repo / ".claude" / "skills" / "sub").mkdir(parents=True)
        os.symlink(self.repo / ".claude" / "skills" / "sub", self.repo / "link")
        for path in ("link/../x", "link/x"):
            with self.subTest(path=path):
                result, err = self.check("worktree", "add", path, "skill")
                self.assertEqual(result, (1, ""))
                self.assertIn("symlink", err)
        wt = self.root / "wt"
        local_git(self.repo, "worktree", "add", "-q", "--detach", str(wt), "docs")
        # (b) 祖先の名前の大文字と小文字だけが違う（大文字と小文字を区別しないファイルシステム）。
        if (self.root / "REPO").exists():
            for argv in (("worktree", "add", "../REPO/.claude/skills/x", "skill"),
                         ("worktree", "move", "../wt", "../REPO/.claude/skills/y")):
                with self.subTest(argv=argv):
                    result, err = self.check(*argv)
                    self.assertEqual(result, (1, ""))
                    self.assertIn(protected_place, err)
        # (c) 行き先がディレクトリなら、git は登録された worktree のパスの最後の名前で、その中に動かす。
        side = self.root / "side"
        side.mkdir()
        local_git(self.repo, "worktree", "add", "-q", str(side / ".claude"), "skill")
        os.symlink(side / ".claude", self.root / "wtlink")
        (self.repo / "pkg").mkdir()
        for name in ("../wtlink", "../side/.claude/.", "../side/.claude"):
            with self.subTest(name=name):
                result, err = self.check("worktree", "move", name, "pkg")
                self.assertEqual(result, (1, ""))
                self.assertIn("pkg/.claude " + protected_place, err)
        self.assertEqual(self.check("worktree", "move", "../side/.claude", "../moved")[0], (0, ""))
        result, err = self.check("worktree", "move", "../none", "pkg")
        self.assertEqual(result, (1, ""))
        self.assertIn("どの worktree かを確かめられません", err)

    def test_worktree_main_checkout_must_be_known(self):
        # --separate-git-dir の共通の gitdir は .git という名前ではなく、元のチェックアウトの場所が決まらない（R19）。
        sep = self.root / "sep"
        local_git(self.root, "init", "-q", "-b", "main", "--separate-git-dir", str(self.root / "sep.gitdir"), str(sep))
        (sep / "a.txt").write_text("a\n", encoding="utf-8")
        local_git(sep, "add", "a.txt")
        local_git(sep, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "a")
        local_git(sep, "worktree", "add", "-q", "-b", "w", str(self.root / "sepwt"))
        for argv in (("worktree", "move", "../sepwt", "../sepwt2"), ("worktree", "add", "--no-checkout", "../sepwt3")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, start=sep)
                self.assertEqual(result, (1, ""))
                self.assertIn("元のチェックアウトを確かめられません", err)
        # bare のリポジトリには元のチェックアウトがないので、今のチェックアウトだけを確かめる。
        bare = self.root / "bare.git"
        local_git(self.root, "clone", "-q", "--bare", str(self.repo), str(bare))
        local_git(bare, "worktree", "add", "-q", str(self.root / "bw1"), "main")
        local_git(bare, "worktree", "add", "-q", str(self.root / "bw2"), "docs")
        self.assertEqual(self.check("worktree", "move", "../bw2", "../bw3", start=self.root / "bw1")[0], (0, ""))


class WorktreeCreateTests(TreeBase):
    """元のチェックアウト main は、一時ディレクトリの bare（origin）を clone したもの。origin/HEAD は main。"""

    def setUp(self):
        super().setUp()
        self.origin = self.root / "origin.git"
        local_git(self.root, "clone", "-q", "--bare", str(self.repo), str(self.origin))
        self.main = self.root / "main"
        local_git(self.root, "clone", "-q", str(self.origin), str(self.main))
        self.place = self.main / ".claude" / "worktrees" / "x"

    def create(self, name="x", cwd=None, payload=None):
        """フックを呼ぶ。self.adds に、worktree add を呼んだ回数を残す（作る前に止めたかを確かめる）。"""
        out, err = io.StringIO(), io.StringIO()
        if payload is None:
            payload = {"name": name, "cwd": str(cwd or self.main)}
        real = guard._git_process
        self.adds = 0

        def spy(cwd, *args, **kwargs):
            self.adds += args[:2] == ("worktree", "add")
            return real(cwd, *args, **kwargs)

        with mock.patch.object(guard, "_git_process", side_effect=spy):
            code = guard.worktree_create(payload, stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def has_branch(self, repo, name):
        cp = subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/heads/{name}"])
        return cp.returncode == 0

    def assert_nothing_left(self, repo=None, name="x"):
        repo = repo or self.main
        place = repo / ".claude" / "worktrees" / name
        self.assertFalse(os.path.lexists(place))
        self.assertFalse(os.path.lexists(repo / ".git" / "worktrees" / name))
        self.assertFalse(self.has_branch(repo, f"worktree-{name}"))
        self.assertNotIn(f"worktree {place}", local_git(repo, "worktree", "list", "--porcelain").split("\n"))

    def blob_in(self, repo, text):
        cp = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                            input=text.encode("utf-8"), capture_output=True, check=True)
        return cp.stdout.decode().strip()

    def replace_after_compare(self, repo, original, replacement):
        """作る前の比較が終わった後に、original を replacement に差し替える（確かめた後の差し替え）。"""
        real = guard.compare_with_main

        def compare_then_replace(*args):
            found = real(*args)
            local_git(repo, "-c", "core.hooksPath=/dev/null", "replace", original, replacement)
            return found

        return mock.patch.object(guard, "compare_with_main", side_effect=compare_then_replace)

    def test_create_matches_main_checkout(self):
        code, out, err = self.create()
        self.assertEqual((code, err), (0, ""), err)
        # 標準出力は、置き場所の 1 行だけ（R21）。
        self.assertEqual(out, f"{self.place}\n")
        self.assertTrue(self.has_branch(self.main, "worktree-x"))
        self.assertEqual(local_git(self.place, "rev-parse", "HEAD"), local_git(self.main, "rev-parse", "origin/main"))
        settings = ".claude/settings.json"
        self.assertEqual((self.place / settings).read_bytes(), (self.main / settings).read_bytes())

    def test_tampered_origin_head_is_rejected(self):
        local_git(self.main, "update-ref", "refs/remotes/origin/evil", "refs/remotes/origin/feature")
        local_git(self.main, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/evil")
        code, out, err = self.create()
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn("変更 .claude/settings.json", err)
        self.assert_nothing_left()

    def test_replaced_blob_is_caught_after_checkout(self):
        original = local_git(self.main, "rev-parse", "HEAD:.claude/settings.json")
        evil = self.blob_in(self.main, '{"evil": 1}\n')
        # 作る前の比較の後に差し替えると、作った後の比較で見つかり、片付けられる。
        with self.replace_after_compare(self.main, original, evil):
            code, out, err = self.create()
        self.assertEqual((code, out, self.adds), (1, "", 1))
        self.assertIn("変更 .claude/settings.json", err)
        self.assertIn(guard.MSG_WT_REPLACED, err)
        self.assert_nothing_left()
        # 確かめる前から差し替えてあれば、作る前の比較で止まる。
        code, out, err = self.create()
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn("変更 .claude/settings.json", err)
        self.assert_nothing_left()

    def test_bad_names_are_rejected(self):
        for name in ("", "../x", ".x", "a/b", "a" * 65, "-x", "x\n"):
            with self.subTest(name=name):
                code, out, err = self.create(name)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("使えません", err)
        for payload in ({}, {"name": "x"}, {"name": 1, "cwd": str(self.main)}, {"name": "x", "cwd": 1},
                        {"name": "x", "cwd": "main"}, ["x"]):
            with self.subTest(payload=payload):
                code, out, err = self.create(payload=payload)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("止めました", err)
        self.assertFalse(os.path.lexists(self.main / ".claude" / "worktrees"))
        self.assertEqual(local_git(self.main, "for-each-ref", "refs/heads/worktree-*"), "")
        self.assertEqual(self.create("a" * 64)[0], 0)

    def test_existing_worktree_returns_path(self):
        first = self.create()
        self.assertEqual(first, (0, f"{self.place}\n", ""))
        self.assertEqual(self.create(), first)
        # 登録だけが残り、ディレクトリがないときは止め、ブランチにも触らない（R20）。
        oid = local_git(self.main, "rev-parse", "worktree-x")
        os.rename(self.place, self.root / "moved")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(local_git(self.main, "rev-parse", "worktree-x"), oid)
        self.assertIn(str(self.place), local_git(self.main, "worktree", "list", "--porcelain"))

    def test_existing_branch_or_directory_is_not_touched(self):
        # 前からあるブランチとディレクトリは、このフックが作ったものではないので消さない（R20）。
        local_git(self.main, "branch", "worktree-x", "origin/feature")
        oid = local_git(self.main, "rev-parse", "worktree-x")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("worktree-x", err)
        self.assertEqual(local_git(self.main, "rev-parse", "worktree-x"), oid)
        self.assertFalse(os.path.lexists(self.place))
        local_git(self.main, "branch", "-D", "worktree-x")
        self.place.mkdir(parents=True)
        (self.place / "keep").write_text("k\n", encoding="utf-8")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertTrue((self.place / "keep").exists())
        self.assertFalse(self.has_branch(self.main, "worktree-x"))

    def test_guidance_for_other_branch(self):
        local_git(self.main, "switch", "-q", "feature")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("変更 .claude/settings.json", err)
        self.assertIn(guard.MSG_WT_BRANCH, err)
        self.assert_nothing_left()

    def test_guidance_for_uncommitted_and_behind(self):
        (self.main / ".claude" / "settings.json").write_text('{"v": 9}\n', encoding="utf-8")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn(guard.MSG_WT_UNCOMMITTED, err)
        local_git(self.main, "checkout", "--", ".claude/settings.json")
        local_git(self.main, "reset", "-q", "--hard", "HEAD~1")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("追加 .claude/settings.json", err)
        self.assertIn(guard.MSG_WT_BEHIND, err)
        self.assert_nothing_left()

    def test_no_origin_uses_head(self):
        place = self.repo / ".claude" / "worktrees" / "x"
        code, out, err = self.create(cwd=self.repo)
        self.assertEqual((code, out, err), (0, f"{place}\n", ""))
        self.assertEqual(local_git(place, "rev-parse", "HEAD"), local_git(self.repo, "rev-parse", "HEAD"))
        settings = ".claude/settings.json"
        self.assertEqual((place / settings).read_bytes(), (self.repo / settings).read_bytes())

    def test_hooks_do_not_run(self):
        # worktree add と片付けの git は、フックを動かさない（R20）。
        hooks = self.root / "hooks"
        hooks.mkdir()
        canary = self.root / "canary"
        for name in ("post-checkout", "reference-transaction"):
            (hooks / name).write_text(f"#!/bin/sh\ntouch '{canary}'\n", encoding="utf-8")
            (hooks / name).chmod(0o755)
        local_git(self.main, "config", "core.hooksPath", str(hooks))
        # 仕掛けが効くことを、テストの git で確かめる。
        local_git(self.main, "branch", "probe")
        self.assertTrue(canary.exists())
        canary.unlink()
        self.assertEqual(self.create()[0], 0)
        self.assertFalse(canary.exists())
        # 作った後に片付けるときも動かさない。
        original = local_git(self.main, "rev-parse", "HEAD:.claude/settings.json")
        evil = self.blob_in(self.main, '{"evil": 1}\n')
        with self.replace_after_compare(self.main, original, evil):
            self.assertEqual(self.create("y")[0], 1)
        self.assertFalse(canary.exists())
        self.assert_nothing_left(name="y")

    def test_failed_add_leaves_nothing(self):
        # git は checkout に失敗すると、ディレクトリと登録は消すが、-b で作ったブランチは残す（実測）。
        local_git(self.main, "config", "filter.boom.smudge", "false")
        local_git(self.main, "config", "filter.boom.required", "true")
        info = self.main / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("README.md filter=boom\n", encoding="utf-8")
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("worktree add が失敗しました", err)
        self.assertNotIn(guard.MSG_WT_LEFT, err)
        self.assert_nothing_left()
        # 失敗した後に置き場所にあるものは、このフックが作ったものではない（同時に動いた別の作成など）ので触らない（R20）。
        (info / "attributes").unlink()
        real = guard._git_process

        def other_appears(cwd, *args, **kwargs):
            if args[:2] == ("worktree", "add"):
                local_git(self.main, "worktree", "add", "-q", "--detach", str(self.place), "HEAD")
                (self.place / "keep").write_text("k\n", encoding="utf-8")
                return subprocess.CompletedProcess(args, 128, b"", b"")
            return real(cwd, *args, **kwargs)

        with mock.patch.object(guard, "_git_process", side_effect=other_appears):
            code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertTrue((self.place / "keep").exists())
        self.assertIn(f"worktree {self.place}", local_git(self.main, "worktree", "list", "--porcelain").split("\n"))

    def test_interrupted_add_is_cleaned_up(self):
        # 止められた worktree add は lock（initializing）を残す。フックの timeout（60 秒）より前に止め、片付ける。
        real = guard._git_process
        timeouts = []

        def add_then_timeout(cwd, *args, **kwargs):
            cp = real(cwd, *args, **kwargs)
            if args[:2] == ("worktree", "add"):
                timeouts.append(kwargs.get("timeout"))
                (self.main / ".git" / "worktrees" / "x" / "locked").write_text("initializing", encoding="utf-8")
                raise subprocess.TimeoutExpired(args, kwargs.get("timeout"))
            return cp

        with mock.patch.object(guard, "_git_process", side_effect=add_then_timeout):
            code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("TimeoutExpired", err)
        self.assertEqual(timeouts, [guard.WORKTREE_ADD_TIMEOUT])
        self.assertLess(guard.WORKTREE_ADD_TIMEOUT, 60)
        self.assert_nothing_left()

    def test_lfs_path_only_for_worktree_add(self):
        # PATH に /opt/homebrew/bin を足すのは worktree add だけ（R3）。ほかの git は確認コマンドの環境で動く。
        calls = []
        real = guard._git_process

        def spy(cwd, *args, **kwargs):
            calls.append((args[:2], kwargs.get("env")))
            return real(cwd, *args, **kwargs)

        with mock.patch.object(guard, "_git_process", side_effect=spy):
            self.assertEqual(self.create()[0], 0)
        adds = [env for args, env in calls if args == ("worktree", "add")]
        self.assertEqual([env["PATH"] for env in adds], [guard.WORKTREE_ADD_PATH])
        self.assertEqual({k: v for k, v in adds[0].items() if k != "PATH"},
                         {k: v for k, v in guard.git_env(guard.user_home()).items() if k != "PATH"})
        self.assertEqual([args for args, env in calls if env is not None], [("worktree", "add")])

    def test_symlinked_place_stops(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.main / ".claude" / "worktrees")
        plain = self.root / "plain"
        local_git(self.root, "clone", "-q", str(self.origin), str(plain))
        local_git(plain, "rm", "-q", "-r", ".claude")
        local_git(plain, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "rm")
        os.symlink(elsewhere, plain / ".claude")
        for repo in (self.main, plain):
            with self.subTest(repo=repo.name):
                code, out, err = self.create(cwd=repo)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("symlink", err)
                self.assertEqual(os.listdir(elsewhere), [])
                self.assertFalse(self.has_branch(repo, "worktree-x"))

    def test_bare_and_separate_gitdir_stop(self):
        code, out, err = self.create(cwd=self.origin)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("bare", err)
        sep = self.root / "sep"
        local_git(self.root, "init", "-q", "-b", "main", "--separate-git-dir", str(self.root / "sep.gitdir"), str(sep))
        (sep / "a.txt").write_text("a\n", encoding="utf-8")
        local_git(sep, "add", "a.txt")
        local_git(sep, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "a")
        code, out, err = self.create(cwd=sep)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("元のチェックアウトを確かめられません", err)
        self.assertFalse(os.path.lexists(sep / ".claude"))

    def test_cwd_outside_main_checkout_stops(self):
        # 元のチェックアウトの .git/commondir を書くと、共通の gitdir を別のリポジトリに向けられる（実測）。
        fake = self.root / "fake"
        local_git(self.root, "clone", "-q", str(self.origin), str(fake))
        commondir = self.main / ".git" / "commondir"
        commondir.write_text(f"{fake / '.git'}\n", encoding="utf-8")
        code, out, err = self.create()
        commondir.unlink()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("元のチェックアウトの中にありません", err)
        self.assert_nothing_left(fake)
        self.assert_nothing_left()

    def test_dangerous_attributes_stop_before_creating(self):
        # 新しい worktree には、元のチェックアウトと同じ中身の対象もすべて書かれ、属性はそれにも効く（Task 3 の教訓）。
        info = self.main / ".git" / "info"
        info.mkdir(exist_ok=True)
        for attr in ("working-tree-encoding=UTF-16", "filter=probe", "ident"):
            with self.subTest(attr=attr):
                (info / "attributes").write_text(f".claude/settings.json {attr}\n", encoding="utf-8")
                code, out, err = self.create()
                self.assertEqual((code, out, self.adds), (1, "", 0))
                self.assertIn(attr.split("=")[0], err)
                self.assert_nothing_left()

    def test_protected_symlink_stops_even_when_same_as_main(self):
        # 作る前に止める。作った後の比較も symlink で止めるが、それだけに頼らない（Task 3 の教訓）。
        os.symlink("settings.json", self.repo / ".claude" / "link.json")
        local_git(self.repo, "add", ".claude/link.json")
        local_git(self.repo, "commit", "-q", "-m", "link")
        code, out, err = self.create(cwd=self.repo)
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn(".claude/link.json がsymlink", err)
        self.assert_nothing_left(self.repo)

    def test_symlink_parent_is_caught_after_checkout(self):
        # 作った後の比較は、親が symlink のパスを、たどった先の中身で同じとみなさない。
        nested = self.repo / "x" / ".claude"
        nested.mkdir(parents=True)
        (nested / "settings.json").write_text('{"n": 1}\n', encoding="utf-8")
        local_git(self.repo, "add", "x")
        local_git(self.repo, "commit", "-q", "-m", "nested")
        head = local_git(self.repo, "rev-parse", "HEAD")
        self.branch("xlink", "HEAD", {"x/.claude/settings.json": None, "x": ("120000", str(self.repo / "x"))})
        evil = local_git(self.repo, "commit-tree", "xlink^{tree}", "-m", "evil")
        with self.replace_after_compare(self.repo, head, evil):
            code, out, err = self.create(cwd=self.repo)
        self.assertEqual((code, out, self.adds), (1, "", 1))
        self.assertIn("x がsymlink", err)
        self.assert_nothing_left(self.repo)
        # 片付けは symlink の先を消さない。
        self.assertTrue((nested / "settings.json").exists())

    def test_main_reads_payload_from_stdin(self):
        def run(data):
            stdin = io.TextIOWrapper(io.BytesIO(data))
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(sys, "stdin", stdin), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                code = guard.main(["worktree-create"])
            return code, out.getvalue(), err.getvalue()

        payload = {"session_id": "s", "transcript_path": "/dev/null", "cwd": str(self.main),
                   "hook_event_name": "WorktreeCreate", "name": "x"}
        self.assertEqual(run(json.dumps(payload).encode("utf-8")), (0, f"{self.place}\n", ""))
        for data in (b"", b"{", b"[]", b'"x"'):
            with self.subTest(data=data):
                code, out, err = run(data)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("止めました", err)
        self.assertEqual(guard.main(["worktree-create", "x"]), 1)


if __name__ == "__main__":
    unittest.main()
