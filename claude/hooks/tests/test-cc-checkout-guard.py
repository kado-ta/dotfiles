import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import select
import signal
import subprocess
import sys
import tempfile
import threading
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
            list(argv), start=start or self.repo, git_env=git_env,
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

    def test_read_only_commands_that_write_files_stop(self):
        # 作業ツリーに書かないサブコマンドも、--output などでファイルに書く（最終レビューで実測）。
        # 中身は sandbox が書けるコミットから来るので、確かめずに止める（C1）。
        local_git(self.repo, "config", "alias.l", "log")
        local_git(self.repo, "config", "alias.archive", "status")  # git は builtin の alias を使わない
        for argv in (("show", "-s", "--format=%B", "--output=.claude/settings.local.json"),
                     ("log", "-1", "--format=%B", "--output", ".env.local"), ("l", "--output=.env"),
                     ("diff-tree", "-p", "HEAD", "--output=x"), ("range-diff", "--output=x", "a...b"),
                     ("blame", "--output=x", "README.md"), ("whatchanged", "--output=x"), ("log", "--outp=x"),
                     ("format-patch", "-1", "-o", ".claude/rules"), ("format-patch", "-1", "--output=x"),
                     ("archive", "-o", "x.tar", "HEAD"), ("bundle", "create", "x.bundle", "HEAD"),
                     ("config", "-f", ".claude/settings.json", "a.b", "c"), ("config", "--file=x", "a.b", "c"),
                     ("config", "--fil=x", "a.b", "c"), ("config", "-fx", "a.b", "c"), ("config", "-lfx"),
                     ("config", "set", "--file", "x", "a.b", "c"), ("-C", "sub", "show", "--output=x"),
                     # 作り直しの init は、--separate-git-dir で .git（sandbox が書ける）を丸ごと動かし、
                     # テンプレート（--template・-c init.templateDir）から .git/hooks に書く（再レビューで実測。R24）。
                     ("init", "--separate-git-dir=.claude/skills/evil"), ("init", "--separate-git-dir", "x"),
                     ("init", "--sep=x"), ("init", "--separate", "x"), ("init", "--template=x"),
                     ("init", "--templ=x"), ("init", "--template", "x"), ("-c", "init.templateDir=x", "init"),
                     ("-c", "INIT.TEMPLATEDIR=x", "init", "-q")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("ファイルに書きます", err)
                self.assertIn("command git", err)
        # リポジトリの外でも、書き先は絶対パスで対象を指せる。
        outside = self.root / "outside"
        outside.mkdir()
        for argv in (("diff", "--no-index", "a", "b", f"--output={self.repo}/.env"),
                     ("archive", f"--remote={self.repo}", "-o", f"{self.repo}/.env", "HEAD")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv, start=outside)[0], (1, ""))
        self.assertEqual(self.check("init", "newproj", start=outside)[0], (0, ""))
        # 書かない形は今までどおり通す。
        for argv in (("show", "--output-indicator-new=>", "HEAD"), ("config", "--get", "user.name"),
                     ("config", "--fixed-value", "--get", "a.b", "c"), ("log", "--oneline"), ("ls-files", "-o"),
                     ("init",), ("init", "newdir"), ("init", "-q"), ("init", "-b", "main"),
                     ("init", "--initial-branch=main"), ("init", "--bare", "x.git"), ("init", "--object-format=sha1"),
                     ("init", "--ref-format=files"), ("init", "--shared"), ("init", "--shared=group"),
                     ("-c", "init.defaultBranch=main", "init")):
            with self.subTest(argv=argv):
                self.assertEqual(self.check(*argv)[0], (0, ""))


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

    def test_ref_swap_while_asking_stops(self):
        # 人間が差分を読んでいる間（readline の中）に ref を差し替えると、見せていない中身が書かれる（最終レビューで実測）。
        # y の後に同じ計算をもう一度して、違えば git を動かさずに止める（I1）。
        self.branch("evil", "feature", {".claude/settings.json": '{"evil": 1}\n'})
        self.branch("readme", "feature", {"README.md": "r\n"})
        original = local_git(self.repo, "rev-parse", "feature")
        repo = self.repo

        class Swap(io.StringIO):
            def __init__(self, target):
                super().__init__()
                self.target = target

            def readline(self, *args):
                local_git(repo, "update-ref", "refs/heads/feature", self.target)
                return "y\n"

        def ask(target):
            local_git(repo, "update-ref", "refs/heads/feature", original)
            err = io.StringIO()
            result = guard.check(["switch", "feature"], start=repo, git_env=(), home=self.home,
                                 stdin=Swap(target), stderr=err, tty=True)
            return result, err.getvalue()

        result, err = ask("evil")
        self.assertEqual(result, (1, ""))
        self.assertIn('+{"v": 2}', err)
        self.assertNotIn('"evil"', err)
        self.assertIn(guard.MSG_CHANGED_WHILE_ASKING, err)
        # 対象のファイルが確認のときと同じなら（README だけが変わる）、許可する。
        (code, state), err = ask("readme")
        self.assertEqual(code, 0, err)
        self.assertNotIn(guard.MSG_CHANGED_WHILE_ASKING, err)
        self.assertEqual(json.loads(state)["expect"][".claude/settings.json"][1],
                         ["100644", local_git(repo, "rev-parse", "readme:.claude/settings.json")])

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

    def test_config_of_the_command_is_used_to_show_content(self):
        # 人間の -c（core.useReplaceRefs=false など）は、見せる中身にも効かせる。git はその設定で書く（M6）。
        original = local_git(self.repo, "rev-parse", "feature:.claude/settings.json")
        local_git(self.repo, "replace", original, self.blob('{"evil": 1}\n'))
        result, err = self.check("-c", "core.useReplaceRefs=false", "switch", "feature", tty=True, answer="n\n")
        self.assertEqual(result, (1, ""))
        self.assertIn('+{"v": 2}', err)
        self.assertNotIn('"evil"', err)

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

    def test_missing_index_writes_the_whole_tree(self):
        # index がないと、git switch・checkout は initial checkout として、書く元の tree 全体（HEAD と同じパスも）を書き出す。
        # info/exclude に * があると、追跡していないファイルを上書きしないための確かめも効かない（レビューで実測。両方の git）。
        # sandbox は、作業ツリーに触れずに HEAD のブランチを進め、index を消せる（D3）。
        local_git(self.repo, "update-ref", "refs/heads/main", "feature")
        (self.repo / ".git" / "index").unlink()
        (self.repo / ".git" / "info").mkdir(exist_ok=True)
        with open(self.repo / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write("*\n")
        for argv in (("switch", "main"), ("checkout",), ("checkout", "main")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("変更 .claude/settings.json", err)
        self.assertEqual(self.approve_and_run("switch", "-q", "main"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 2}\n')

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

    def test_verify_stops_when_the_root_is_replaced(self):
        # 確かめた後に、作業ツリーの場所を symlink に替えられると、git は別の場所に書き、verify はその先を読んで一致と
        # みなしうる。状態の root が、実パスと同じ実体のディレクトリでなくなっていれば止める（D3）。
        (code, state), _ = self.check("switch", "feature", tty=True, answer="y\n")
        self.assertEqual(code, 0)
        self.settings.write_text('{"v": 2}\n', encoding="utf-8")
        err = io.StringIO()
        self.assertEqual(guard.verify(state, err), 0)
        moved = self.root / "moved"
        os.rename(self.repo, moved)
        os.symlink(moved, self.repo)
        err = io.StringIO()
        self.assertEqual(guard.verify(state, err), 1)
        self.assertIn(f"{self.repo} が、実体のディレクトリでなくなりました", err.getvalue())

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

    def test_no_tty_command_is_escaped(self):
        # 端末でないときに見せる、普段の端末で打つコマンドも、制御文字を <U+XXXX> にする（D3）。
        self.stage('{"v": 9}\n')
        result, err = self.check("restore", "--", ".claude/settings.json", "x\x1b[2Ky")
        self.assertEqual(result, (1, ""))
        self.assertNotIn("\x1b", err)
        self.assertIn("x<U+001B>[2Ky", err)

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

    def test_disk_content_is_read_as_a_bounded_regular_file(self):
        # 差分に見せるディスクの中身は、symlink をたどらず、FIFO で固まらず、上限（16 MiB）まで読む（D3）。
        entry = guard.Entry("100644", "0" * 40)
        limit = 16 << 20
        big = self.repo / "big"
        big.write_bytes(b"x" * limit)
        self.assertEqual(len(guard._disk_bytes(self.repo, "big", entry)), limit)
        big.write_bytes(b"x" * (limit + 1))
        with self.assertRaises(guard.GuardError):
            guard._disk_bytes(self.repo, "big", entry)
        fifo = self.repo / "fifo"
        os.mkfifo(fifo)
        result = []

        def read():
            try:
                result.append(guard._disk_bytes(self.repo, "fifo", entry))
            except Exception as e:  # noqa: BLE001 - 種類を下で確かめる
                result.append(e)

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        thread.join(10)
        if thread.is_alive():
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))  # 固まった open を解く
            thread.join(10)
            self.fail("FIFO を開いて固まりました")
        self.assertIsInstance(result[0], guard.GuardError)

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
            # Claude Code の sandbox の中では疑似端末を開けない。CI（macOS）では実際に動くこと（R7）を前提にしているので、
            # CI では飛ばさずに失敗にする（D3）。
            if os.environ.get("CI"):
                self.fail(f"CI で疑似端末を開けません: {e}")
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


class GitdirTests(TreeBase):
    """git は gitdir の COMMIT_EDITMSG・FETCH_HEAD・logs/HEAD などを開いて書くので、symlink の先（作業ツリーの外も）に書く
    （レビューで実測。CLT の git 2.54 と Homebrew の git 2.56）。sandbox の外では、gitdir と共通の gitdir に symlink か
    特殊なファイルがあれば、何も許可しない（D2）。早道は決めずに全体の処理に任せる。
    """

    def setUp(self):
        super().setUp()
        self.gitdir = self.repo / ".git"
        self.victim = self.root / "victim.json"
        self.victim.write_text('{"keep": 1}\n', encoding="utf-8")

    def fast(self, argv, start=None):
        return guard.fast_allow(["check", "--git-env", "", "--", *argv], cwd=str(start or self.repo))

    def assert_stopped(self, argv, path, start=None):
        result, err = self.check(*argv, start=start, tty=True, answer="y\n")
        self.assertEqual(result, (1, ""), err)
        self.assertIn(f"{path} が、symlink か", err)
        self.assertNotIn("command git", err)
        self.assertNotIn(guard.MSG_ASK, err)
        self.assertFalse(self.fast(argv, start))

    def test_commit_editmsg_symlink_to_config_stops_commit(self):
        # COMMIT_EDITMSG を .git/config への symlink にし、SQUASH_MSG に中身を置くと、人間の git commit は、
        # エディタが失敗しても .git/config を書き換えた（レビューで実測）。
        config = self.gitdir / "config"
        link = self.gitdir / "COMMIT_EDITMSG"
        link.unlink()
        os.symlink("config", link)
        (self.gitdir / "SQUASH_MSG").write_text(config.read_text(encoding="utf-8") + "[probe]\n\tmarker = 1\n",
                                               encoding="utf-8")
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        local_git(self.repo, "add", "README.md")
        for argv in (("-c", "core.editor=false", "commit"), ("commit", "-m", "x"), ("status",)):
            with self.subTest(argv=argv):
                self.assert_stopped(argv, link)
        # 仕掛けが効くことを、テストの git で確かめる。
        subprocess.run(["git", "-C", str(self.repo), "-c", "core.editor=false", "commit"], capture_output=True)
        self.assertEqual(local_git(self.repo, "config", "--get", "probe.marker"), "1")

    def test_fetch_head_symlink_stops_fetch(self):
        # FETCH_HEAD の symlink を通して、git fetch は作業ツリーの外のファイルを書き換えた（レビューで実測）。
        link = self.gitdir / "FETCH_HEAD"
        os.symlink(self.victim, link)
        for argv in (("fetch", str(self.repo)), ("fetch",), ("log", "--oneline"), ("--version",), ("switch", "-h")):
            with self.subTest(argv=argv):
                self.assert_stopped(argv, link)
        local_git(self.repo, "fetch", "-q", str(self.repo))
        self.assertNotEqual(self.victim.read_text(encoding="utf-8"), '{"keep": 1}\n')

    def test_reflog_symlink_stops_switch(self):
        # logs/HEAD の symlink を通して、git switch は作業ツリーの外のファイルに追記した（レビューで実測）。
        link = self.gitdir / "logs" / "HEAD"
        link.unlink()
        os.symlink(self.victim, link)
        self.assert_stopped(("switch", "docs"), link)
        local_git(self.repo, "switch", "-q", "docs")
        self.assertIn("checkout: moving from main to docs", self.victim.read_text(encoding="utf-8"))

    def test_entries_git_writes_through(self):
        # 最上位のすべて、logs・refs・sequencer・rebase-merge・rebase-apply の下のすべて、objects とその直下を見る。
        # symlink のディレクトリ（refs/heads・objects など）の中にも、git は新しいファイルを書く（実測）。
        outside = self.root / "outside"
        outside.mkdir()
        oid = local_git(self.repo, "rev-parse", "HEAD")
        cases = (
            ("refs/heads/sub", lambda p: os.symlink(outside, p)),
            ("refs/tags/v", lambda p: os.symlink(self.victim, p)),
            ("logs/refs/heads/main", lambda p: (p.unlink(), os.symlink(self.victim, p))),
            ("objects/" + oid[:2], lambda p: (os.rename(p, outside / "o"), os.symlink(outside / "o", p))),
            ("sequencer/todo", lambda p: (p.parent.mkdir(), os.symlink(self.victim, p))),
            ("rebase-merge/done", lambda p: (p.parent.mkdir(), os.symlink(self.victim, p))),
            ("rebase-apply/x/y", lambda p: (p.parent.mkdir(parents=True), os.symlink(self.victim, p))),
            ("hooks", lambda p: (p.mkdir(exist_ok=True), os.rename(p, outside / "h"), os.symlink(outside / "h", p))),
            ("MERGE_MSG", lambda p: os.mkfifo(p)),
            ("description", lambda p: (p.unlink(missing_ok=True), os.symlink(self.victim, p))),
        )
        for rel, make in cases:
            with self.subTest(rel=rel):
                path = self.gitdir / rel
                make(path)
                self.assert_stopped(("status",), path)
                # 戻す。
                if rel.startswith("objects/") or rel == "hooks":
                    path.unlink()
                    os.rename(outside / ("o" if rel.startswith("objects/") else "h"), path)
                else:
                    path.unlink()
                self.assertTrue(self.fast(("status",)))
                self.assertEqual(self.check("status")[0], (0, ""))
        # 大文字と小文字だけが違う名前のディレクトリにも、git は書く（大文字と小文字を区別しないファイルシステム）。
        logs = self.gitdir / "logs"
        os.rename(logs, self.gitdir / "LOGS")
        if (self.gitdir / "logs").exists():
            link = self.gitdir / "LOGS" / "HEAD"
            link.unlink()
            os.symlink(self.victim, link)
            self.assert_stopped(("status",), link)
        else:
            with self.subTest(case="LOGS"):
                self.skipTest("大文字と小文字を区別するファイルシステムでは、git は LOGS を読まない")

    def test_linked_worktree_gitdir_and_common_dir(self):
        # linked worktree では、その gitdir（.git/worktrees/<id>）と共通の gitdir（.git）の両方を見る。
        wt = self.root / "wt"
        local_git(self.repo, "worktree", "add", "-q", "--detach", str(wt), "docs")
        self.assertTrue(self.fast(("status",), wt))
        self.assertEqual(self.check("status", start=wt)[0], (0, ""))
        for link in (self.gitdir / "worktrees" / "wt" / "FETCH_HEAD", self.gitdir / "FETCH_HEAD"):
            with self.subTest(link=link):
                os.symlink(self.victim, link)
                self.assert_stopped(("status",), link, start=wt)
                self.assert_stopped(("-C", str(wt), "status"), link, start=self.root)
                link.unlink()

    def test_fast_path_finds_the_gitdir_like_git(self):
        # 早道は git を動かさずに gitdir を探す。git と同じと言い切れない形は、決めずに任せる。
        os.symlink(self.victim, self.gitdir / "FETCH_HEAD")
        sub = self.repo / "sub"
        # 中のディレクトリからも、symlink を通ったカレントディレクトリからも、同じ gitdir を見つける。
        os.symlink(sub, self.root / "sublink")
        for start in (sub, self.root / "sublink"):
            with self.subTest(start=start):
                self.assertFalse(self.fast(("status",), start))
        self.assertFalse(self.fast(("-C", "sub", "status")))
        # git が使わない .git ディレクトリ（HEAD・objects・refs がない）を作業ツリーに置いても、その上を見落とさない。
        (sub / ".git").mkdir()
        self.assertFalse(self.fast(("status",), sub))
        self.assertEqual(self.check("status", start=sub)[0], (1, ""))
        (sub / ".git").rmdir()
        (self.gitdir / "FETCH_HEAD").unlink()
        # bare のリポジトリの形（HEAD がある）と、.git が symlink の形は任せる。リポジトリの外は許可する。
        (sub / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        self.assertFalse(self.fast(("status",), sub))
        (sub / "HEAD").unlink()
        self.assertTrue(self.fast(("status",), sub))
        os.symlink(self.gitdir, self.root / "linked-dotgit")
        other = self.root / "other"
        other.mkdir()
        os.symlink(self.root / "linked-dotgit", other / ".git")
        self.assertFalse(self.fast(("status",), other))
        outside = self.root / "outside"
        outside.mkdir()
        self.assertTrue(self.fast(("status",), outside))
        self.assertEqual(self.check("status", start=outside)[0], (0, ""))


class FastPathTests(TreeBase):
    """引数だけで許可する早道（I2）は、全体の処理が許可する形しか許可しない。"""

    def fast(self, argv, git_env=""):
        return guard.fast_allow(["check", "--git-env", git_env, "--", *argv], cwd=str(self.repo))

    def test_fast_path_agrees_with_full_path(self):
        allowed = [("status",), ("log", "--oneline"), ("diff", "--stat"), ("-C", "sub", "status"),
                   ("-c", "color.ui=never", "log"), ("--no-pager", "log"), ("-p", "show"), ("--version",),
                   ("--help",), ("-h",), ("-C", "sub", "--help"), (), ("-C", "sub"), ("switch", "-h"),
                   ("checkout", "--help"), ("worktree", "-h"), ("show", "--output-indicator-new=>"),
                   ("config", "--get", "user.name"), ("branch", "-a"), ("rm", "-h"), ("init",), ("init", "-q", "x"),
                   ("init", "--bare", "--shared", "x.git")]
        for argv in allowed:
            with self.subTest(allowed=argv):
                self.assertTrue(self.fast(argv))
                self.assertEqual(self.check(*argv)[0], (0, ""))
        stopped = [("show", "--output=x"), ("log", "--outp=x"), ("config", "-f", "x", "a.b", "c"),
                   ("config", "--fil=x", "a.b", "c"), ("archive", "-o", "x", "HEAD"), ("archive", "-h"),
                   ("format-patch", "-1"), ("bundle", "create", "x", "HEAD"), ("-c", "alias.st=status", "status"),
                   ("-c", "ALIAS.st=status", "status"), ("--git-dir=x", "status"), ("--bare", "status"),
                   ("-C",), ("-c",), ("rebase", "main"), ("switch", "feature"), ("rm", ".claude/settings.json"),
                   ("show", "-h", "--output=x"), ("init", "--separate-git-dir=.claude/skills/evil"),
                   ("init", "--templ=x"), ("-c", "init.templateDir=x", "init"), ("-c", "Init.TemplateDir=x", "init")]
        for argv in stopped:
            with self.subTest(stopped=argv):
                self.assertFalse(self.fast(argv))
                self.assertEqual(self.check(*argv)[0], (1, ""))
        # 早道が決めない形は、全体の処理が決める（許可することもある）。
        local_git(self.repo, "config", "alias.st", "status")
        for argv in (("switch", "docs"), ("-c", "user.name=Jürgen", "status"), ("st",), ("st", "-h"),
                     ("rm", "--cached", "README.md"), ("-c", "init.templateDir=x", "status")):
            with self.subTest(handed_over=argv):
                self.assertFalse(self.fast(argv))
                self.assertEqual(self.check(*argv)[0][0], 0)
        # 受け入れた違い（ledger の判断。R24）: CLT の git が読めないリポジトリでは、早道は READ_ONLY とヘルプを
        # 引数だけで許可し、全体の処理は rev-parse の失敗で止める（リポジトリを読めません）。どちらも作業ツリーに書かない。
        # どちらかを変えたときに気づけるよう、今の違いをそのまま確かめる。
        for argv in (("-C", "nonexistent", "status"), ("-c", "foo", "status"), ("-C", "nonexistent", "--help")):
            with self.subTest(accepted_divergence=argv):
                self.assertTrue(self.fast(argv))
                self.assertEqual(self.check(*argv)[0], (1, ""))
        # GIT_ の名前と check のオプションも、main と parse と同じく読む。
        self.assertTrue(self.fast(("status",), "GIT_EDITOR,GIT_PAGER"))
        self.assertEqual(self.check("status", git_env=("GIT_EDITOR", "GIT_PAGER"))[0], (0, ""))
        self.assertFalse(self.fast(("status",), "GIT_EDITOR,GIT_DIR"))
        self.assertEqual(self.check("status", git_env=("GIT_EDITOR", "GIT_DIR"))[0], (1, ""))
        # --after-fetch（pull の手順。D1 で消した）は、ほかの知らないオプションと同じく main が止める。
        for argv in (["check", "--bogus", "--", "status"], ["check", "--git-env"], ["check", "status"],
                     ["check", "--after-fetch", "--git-env", "", "--", "status"], ["verify", "{}"], ["status"], []):
            with self.subTest(main=argv):
                self.assertFalse(guard.fast_allow(argv))
        self.assertEqual(guard.main(["check", "--bogus", "--", "status"]), 1)
        self.assertEqual(guard.main(["check", "--after-fetch", "--git-env", "", "--", "status"]), 1)
        # -h を許すサブコマンドの一覧は、HANDLERS と同じ。
        self.assertEqual(set(guard.HANDLERS), guard.HANDLED)
        # gitdir に symlink か特殊なファイルがあれば、早道は決めずに任せ、全体の処理は止める（D2）。
        victim = self.root / "victim"
        victim.write_text("v\n", encoding="utf-8")
        gitdir = self.repo / ".git"
        for rel, make in (("COMMIT_EDITMSG", lambda p: os.symlink("config", p)),
                          ("FETCH_HEAD", lambda p: os.symlink(victim, p)),
                          ("logs/HEAD", lambda p: os.symlink(victim, p)), ("MERGE_MSG", os.mkfifo)):
            path = gitdir / rel
            path.unlink(missing_ok=True)
            make(path)
            for argv in (("status",), ("--version",), ("switch", "-h"), ("-C", "sub", "log"), ("init",)):
                with self.subTest(gitdir=rel, argv=argv):
                    self.assertFalse(self.fast(argv))
                    self.assertEqual(self.check(*argv)[0], (1, ""))
            path.unlink()

    def test_fast_path_runs_before_heavy_imports(self):
        # インストールと同じく、スクリプトとして起動する。
        def imported(*argv):
            cmd = [sys.executable, "-I", "-X", "importtime", str(FILE), "check", "--git-env", "", "--", *argv]
            cp = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo)
            return cp, {line.rsplit("|", 1)[-1].strip() for line in cp.stderr.splitlines() if "|" in line}

        cp, names = imported("status")
        self.assertEqual((cp.returncode, cp.stdout), (0, ""))
        for name in ("subprocess", "difflib", "dataclasses", "tempfile", "ctypes"):
            with self.subTest(name=name):
                self.assertNotIn(name, names)
        # 早道で決まらない形は、全体の処理に進む。
        _, names = imported("switch", "docs")
        self.assertIn("subprocess", names)


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

    def test_pull_stops(self):
        # pull は、確かめた後にもう一度 fetch して、その FETCH_HEAD を取り込む。確かめた中身（@{u}。sandbox が書ける ref）と、
        # git が取り込む中身が一致しない（レビューで実測）。fetch と merge @{u} に分けるよう案内して、どの形も止める（D1）。
        origin = self.root / "origin.git"
        local_git(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        local_git(self.repo, "remote", "add", "origin", str(origin))
        local_git(self.repo, "push", "-q", "-u", "origin", "main")
        other = self.root / "other"
        local_git(self.root, "clone", "-q", str(origin), str(other))
        local_git(other, "config", "user.name", "Test")
        local_git(other, "config", "user.email", "test@example.com")
        (other / ".claude" / "settings.json").write_text('{"v": 7}\n', encoding="utf-8")
        local_git(other, "commit", "-q", "-am", "settings")
        local_git(other, "push", "-q", "origin", "main")
        before = local_git(self.repo, "rev-parse", "origin/main")
        local_git(self.repo, "config", "alias.pl", "pull")
        for argv in (("pull",), ("pull", "--ff-only"), ("-C", "sub", "pull"), ("pull", "origin", "main"),
                     ("pull", "--rebase"), ("pl",), ("pull", "-q", "-h")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="y\n")
                self.assertEqual(result, (1, ""))
                self.assertIn("git pull は、確かめた後にもう一度 fetch して取り込むので止めました", err)
                self.assertIn("git merge @{u}", err)
                self.assertIn("git merge --ff-only @{u}", err)
                self.assertNotIn("command git", err)
                self.assertNotIn(guard.MSG_ASK, err)
        # 確かめるための fetch もしない。
        self.assertEqual(local_git(self.repo, "rev-parse", "origin/main"), before)
        for argv in (("pull", "-h"), ("pull", "--help")):
            with self.subTest(help=argv):
                self.assertEqual(self.check(*argv)[0], (0, ""))
        # 案内する fetch と merge @{u} は、ほかの merge と同じく確かめる（印のラベルも @{u} で、git と同じ。実測）。
        local_git(self.repo, "fetch", "-q", "origin")
        for argv in (("merge", "@{u}"), ("merge", "--ff-only", "@{u}")):
            with self.subTest(merge=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("変更 .claude/settings.json", err)
        self.assertEqual(self.approve_and_run("merge", "--ff-only", "-q", "@{u}"), (0, ""))
        self.assertEqual(self.settings.read_text(encoding="utf-8"), '{"v": 7}\n')
        (other / ".claude" / "settings.json").write_text('{"v": 8}\n', encoding="utf-8")
        local_git(other, "commit", "-q", "-am", "settings 8")
        local_git(other, "push", "-q", "origin", "main")
        local_git(self.repo, "fetch", "-q", "origin")
        self.commit_settings('{"v": 9}\n')
        self.assertEqual(self.approve_and_run("merge", "--no-edit", "-q", "@{u}", codes=(1,)), (0, ""))
        self.assertIn(">>>>>>> @{u}", self.settings.read_text(encoding="utf-8"))

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

    def test_fetch_head_is_read_as_a_bounded_regular_file(self):
        # FETCH_HEAD（sandbox が書ける）は、symlink をたどらずに、通常のファイルとして上限まで読む（M5）。
        # symlink と FIFO は、先に gitdir の確かめ（D2）が止める。M5 の読み方は、それを外して確かめる。
        line = f"{local_git(self.repo, 'rev-parse', 'feature')}\t\tbranch 'feature' of x\n"
        fetch_head = self.repo / ".git" / "FETCH_HEAD"
        real = self.root / "fetch-head"
        real.write_text(line, encoding="utf-8")

        def stopped(reason):
            result, err = self.check("merge", "FETCH_HEAD")
            self.assertEqual(result, (1, ""))
            self.assertIn(f"{fetch_head} が、symlink か", err)
            with mock.patch.object(guard, "_check_gitdirs"):
                result, err = self.check("merge", "FETCH_HEAD")
            self.assertEqual(result, (1, ""))
            self.assertIn(reason, err)

        fetch_head.symlink_to(real)
        stopped("FETCH_HEAD を読めません")
        fetch_head.unlink()
        fetch_head.write_text(line + "#" * (1 << 20), encoding="utf-8")
        result, err = self.check("merge", "FETCH_HEAD")
        self.assertEqual(result, (1, ""))
        self.assertIn("FETCH_HEAD が大きすぎます", err)
        fetch_head.unlink()
        os.mkfifo(fetch_head)  # 書く側がいなくても、固まらずに止まる
        stopped("FETCH_HEAD は通常のファイルではありません")

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
        else:
            with self.subTest(case="EVIL"):
                self.skipTest("大文字と小文字を区別するファイルシステムでは、git は EVIL を evil として読まない")
        for argv, shown in cases:
            with self.subTest(argv=argv):
                result, err = self.check(*argv, tty=True, answer="n\n")
                self.assertEqual(result, (1, ""))
                self.assertIn(f'+{{"{shown}": 1}}', err)

    def test_output_of_failed_rev_parse_is_not_used(self):
        # rev-parse --verify --quiet は、HEAD^@ などで oid を出しながら終了コード 1 で終わる。git の reset --hard HEAD^@ は
        # 失敗する（レビューで実測）。0 以外の終了コードの出力は使わない（D3）。
        inv = self.parse("reset", "--hard", "HEAD^@")
        self.assertIsNone(guard._rev(inv, "HEAD^@", "commit"))
        result, err = self.check("reset", "--hard", "HEAD^@")
        self.assertEqual(result, (1, ""))
        self.assertIn("HEAD^@ を解決できません", err)

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

    def test_rm_combined_short_options(self):
        # rm の短いオプション（r・f・q・n）のまとめ書きを、clean と同じく読む（M4）。
        result, err = self.check("rm", "-" + "rf", ".claude")
        self.assertEqual(result, (1, ""))
        self.assertIn("削除 .claude/settings.json", err)
        self.assertNotIn("確かめられない", err)
        self.assertEqual(self.check("rm", "-" + "fq", "README.md")[0][0], 0)
        self.assertEqual(self.check("rm", "-" + "rn", ".claude")[0], (0, ""))  # -n は消さない
        result, err = self.check("rm", "-rx", ".claude")
        self.assertEqual(result, (1, ""))
        self.assertIn("確かめられない", err)

    def test_rm_and_mv_through_symlinked_parent_stop(self):
        # 途中に追跡していない symlink（sandbox が作れる）を含むパスで、git rm -f は symlink の先のファイル（作業ツリーの外も）を
        # 消し、git mv は先のファイルを動かす。行き先の途中の symlink には、CLT の git 2.54 は書き、2.56 は拒否した
        # （レビューで実測）。rm と mv は、すべてのパスの途中（ルートの下）を lstat で確かめ、symlink があれば止める（D3）。
        oid = local_git(self.repo, "rev-parse", "HEAD:.claude/settings.json")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("k\n", encoding="utf-8")
        keep = local_git(self.repo, "hash-object", "-w", str(outside / "keep.txt"))
        (self.repo / "notes.md").write_text('{"hooks": "evil"}\n', encoding="utf-8")
        local_git(self.repo, "add", "notes.md")
        for path, blob in (("link/settings.json", oid), ("out/keep.txt", keep)):
            local_git(self.repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
        local_git(self.repo, "commit", "-q", "-m", "entries")
        os.symlink(".claude", self.repo / "link")
        os.symlink(outside, self.repo / "out")
        for argv in (("rm", "-f", "link/settings.json"), ("rm", "-q", "link/settings.json"), ("rm", "-" + "rf", "link"),
                     ("rm", "-f", "out/keep.txt"), ("-C", "sub", "rm", "-f", "../link/settings.json"),
                     ("mv", "notes.md", "link/settings.local.json"), ("mv", "notes.md", "link"),
                     ("mv", "-f", "link/settings.json", "moved.json"), ("mv", "notes.md", "out/n.md"),
                     ("mv", "notes.md", "README.md", "link")):
            with self.subTest(argv=argv):
                result, err = self.check(*argv)
                self.assertEqual(result, (1, ""))
                self.assertIn("symlink", err)
        # 途中に symlink のないパスは、今までどおり。
        self.assertEqual(self.check("rm", "-f", "notes.md")[0][0], 0)
        self.assertEqual(self.check("mv", "notes.md", "sub/n.md")[0], (0, ""))
        # 仕掛けが効くことを、テストの git で確かめる（rm -f は symlink の先の作業ツリーの外のファイルを消す）。
        subprocess.run(["git", "-C", str(self.repo), "rm", "-q", "-f", "out/keep.txt"], capture_output=True)
        self.assertFalse((outside / "keep.txt").exists())

    def test_submodule_recurse_and_sparse_checkout_stop(self):
        # submodule.recurse では、switch などが submodule の作業ツリーにも（.git/modules から）書く。sparse checkout では、
        # sandbox が .git/info/sparse-checkout を広げると、確認に出ないパスも書く（どちらも両方の git で実測）。
        # 作業ツリーに書く形は止める。設定は人間の -c も読む（D3）。
        writes = (("switch", "docs"), ("checkout", "docs"), ("restore", "README.md"), ("checkout-index", "-a"),
                  ("reset", "--hard"), ("merge", "docs"), ("merge", "--abort"), ("stash",), ("cherry-pick", "docs"),
                  ("revert", "HEAD"), ("rm", "README.md"), ("clean", "-f"), ("mv", "README.md", "R.md"),
                  ("worktree", "add", "../wt", "docs"))
        others = (("commit", "-m", "x"), ("restore", "--staged", "README.md"), ("reset", "--soft", "HEAD"),
                  ("rm", "--cached", "README.md"), ("status",), ("worktree", "add", "--no-checkout", "../wt", "docs"))
        for key in ("submodule.recurse", "core.sparseCheckout", "core.sparseCheckoutCone", "index.sparse"):
            for how in ("config", "-c"):
                pre = ("-c", f"{key}=true") if how == "-c" else ()
                if how == "config":
                    local_git(self.repo, "config", key, "true")
                for argv in writes:
                    with self.subTest(key=key, how=how, argv=argv):
                        result, err = self.check(*pre, *argv)
                        self.assertEqual(result, (1, ""))
                        self.assertIn(f"{key.lower()} が設定されています", err)
                for argv in others:
                    with self.subTest(key=key, how=how, allowed=argv):
                        self.assertEqual(self.check(*pre, *argv)[0][0], 0)
                if how == "config":
                    local_git(self.repo, "config", "--unset", key)
        # 人間の -c で false にすれば、今までどおり確かめる。
        local_git(self.repo, "config", "submodule.recurse", "true")
        self.assertEqual(self.check("-c", "submodule.recurse=false", "switch", "docs")[0][0], 0)

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
        else:
            with self.subTest(case="REPO"):
                self.skipTest("大文字と小文字を区別するファイルシステムでは、REPO は別のディレクトリ")
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

    def test_worktree_remove_checks_the_registered_path(self):
        # git worktree remove は、登録（.git/worktrees/<id>/gitdir。sandbox が書けうる）の指す場所を消す。
        # 登録のパスに // や symlink があると、名前の上では一致しても別の場所を消す（最終レビューで実測）。
        # 登録のパスが実パスの実体のディレクトリで、その .git がこの登録を指すときだけ許可する（I3）。
        wt = self.root / "wt"
        local_git(self.repo, "worktree", "add", "-q", "--detach", str(wt), "docs")
        admin = self.repo / ".git" / "worktrees" / "wt"
        registered = (admin / "gitdir").read_text(encoding="utf-8")
        for argv in (("../wt",), ("wt",), (str(wt),), ("--force", "--force", "../wt")):
            with self.subTest(allowed=argv):
                self.assertEqual(self.check("worktree", "remove", *argv)[0], (0, ""))
        # 戻りの .git を置いた別の場所 T と、そこへの symlink。
        target = self.root / "valuable"
        (target / "sub").mkdir(parents=True)
        (target / "sub" / "keep.txt").write_text("k\n", encoding="utf-8")
        (target / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
        q = self.root / "q"
        link = Path(str(q) + str(wt))
        link.parent.mkdir(parents=True)
        os.symlink(target, link)
        inner = self.repo / ".git" / "inner"
        inner.mkdir()
        (inner / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
        cases = (
            # 形 B: 後ろの一致で wt に当たり、symlink の先の T を消す。
            ("double slash", f"{q}/{wt}/.git\n", str(wt), "実パスではありません"),
            ("symlink", f"{link}/.git\n", "wt", "実パスではありません"),
            ("inside the git directory", f"{inner}/.git\n", "inner", "git のディレクトリの中です"),
        )
        for name, gitdir, arg, reason in cases:
            with self.subTest(case=name):
                (admin / "gitdir").write_text(gitdir, encoding="utf-8")
                result, err = self.check("worktree", "remove", "--force", arg)
                self.assertEqual(result, (1, ""))
                self.assertIn(reason, err)
        (admin / "gitdir").write_text(registered, encoding="utf-8")
        # .git がほかを指す、.git が symlink、ディレクトリがない。
        (wt / ".git").rename(self.root / "wt.git")
        (wt / ".git").write_text("gitdir: /nowhere\n", encoding="utf-8")
        result, err = self.check("worktree", "remove", "../wt")
        self.assertEqual(result, (1, ""))
        self.assertIn("登録を指していません", err)
        (wt / ".git").unlink()
        os.symlink(self.root / "wt.git", wt / ".git")
        self.assertEqual(self.check("worktree", "remove", "../wt")[0], (1, ""))
        (wt / ".git").unlink()
        (self.root / "wt.git").rename(wt / ".git")
        self.assertEqual(self.check("worktree", "remove", "../wt")[0], (0, ""))
        wt.rename(self.root / "wt-moved")
        result, err = self.check("worktree", "remove", str(wt))
        self.assertEqual(result, (1, ""))
        self.assertIn("ディレクトリがありません", err)
        # どの worktree にも当たらない名前と、元のチェックアウト。
        self.assertEqual(self.check("worktree", "remove", "none")[0], (1, ""))
        self.assertEqual(self.check("worktree", "remove", ".")[0], (1, ""))

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
        self.place = self.place_of(self.main)

    def key_of(self, root):
        """置き場所のキー（R22）。物理パスの最後の名前を英数字と ._- にし、物理パスの sha256 の先頭 12 桁を付ける。"""
        real = os.path.realpath(root)
        name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(real))
        if name.startswith("."):
            name = "_" + name[1:]
        return f"{name}-{hashlib.sha256(os.fsencode(real)).hexdigest()[:12]}"

    def place_of(self, repo, name="x"):
        return self.home / ".cc-worktrees" / self.key_of(repo) / name

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
            code = guard.worktree_create(payload, stdout=out, stderr=err, home=self.home)
        return code, out.getvalue(), err.getvalue()

    def has_branch(self, repo, name):
        cp = subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/heads/{name}"])
        return cp.returncode == 0

    def assert_nothing_left(self, repo=None, name="x"):
        repo = repo or self.main
        place = self.place_of(repo, name)
        self.assertFalse(os.path.lexists(place))
        self.assertFalse(os.path.lexists(place.parent / ".verified" / name))
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
        # 置き場所はリポジトリの外（R22）。基のディレクトリは 0o700 で作り、確かめ終わった印を置く。
        key = self.place.parent
        self.assertEqual(key.parent, self.home / ".cc-worktrees")
        for d in (key.parent, key, key / ".verified"):
            with self.subTest(d=d.name):
                self.assertEqual(os.lstat(d).st_mode & 0o777, 0o700)
        st = os.lstat(self.place)
        self.assertEqual((key / ".verified" / "x").read_text(encoding="utf-8"), f"{st.st_dev} {st.st_ino}\n")
        self.assertFalse(os.path.lexists(self.main / ".claude" / "worktrees"))
        # 案内する消し方（README・MSG_WT_UNVERIFIED）は、worktree remove の確認を通る（I3）。
        self.assertEqual(self.check("worktree", "remove", "--force", str(self.place), start=self.main)[0], (0, ""))

    def test_key_of_odd_repository_name(self):
        # 名前の英数字と ._- 以外は _ にし、先頭の . も _ にする。続けて、物理パスの sha256 の先頭 12 桁（R22）。
        odd = self.root / ".my repo+x"
        local_git(self.root, "clone", "-q", str(self.origin), str(odd))
        code, out, err = self.create(cwd=odd)
        self.assertEqual(code, 0, err)
        digest = hashlib.sha256(os.fsencode(str(odd))).hexdigest()[:12]
        self.assertEqual(out, f"{self.home}/.cc-worktrees/_my_repo_x-{digest}/x\n")

    def test_tampered_origin_head_is_rejected(self):
        local_git(self.main, "update-ref", "refs/remotes/origin/evil", "refs/remotes/origin/feature")
        local_git(self.main, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/evil")
        code, out, err = self.create()
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn("変更 .claude/settings.json", err)
        self.assert_nothing_left()
        # 案内は 2 つのブランチの名前を出し、差し替えた先へ切り替えさせない（I4）。
        self.assertIn("元のチェックアウトのブランチは main、origin/HEAD の指す先は origin/evil", err)
        self.assertIn("git ls-remote --symref origin HEAD", err)
        self.assertIn("git remote set-head origin --auto", err)
        self.assertNotIn("既定ブランチに戻す", err)

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
        self.assertFalse(os.path.lexists(self.home / ".cc-worktrees"))
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
        # Claude Code の Remove worktree はブランチを残すので、消し方を案内する（M2）。
        self.assertIn(f"git -C {self.main} branch -D worktree-x", err)
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
        self.assertIn(guard.MSG_WT_BRANCH.format(current="feature", origin="origin/main"), err)
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
        place = self.place_of(self.repo)
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
        groups = []

        def add_then_timeout(cwd, *args, **kwargs):
            cp = real(cwd, *args, **kwargs)
            if args[:2] == ("worktree", "add"):
                groups.append(kwargs.get("group"))
                (self.main / ".git" / "worktrees" / "x" / "locked").write_text("initializing", encoding="utf-8")
                raise subprocess.TimeoutExpired(args, 1)
            return cp

        with mock.patch.object(guard, "_git_process", side_effect=add_then_timeout):
            code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("TimeoutExpired", err)
        self.assertEqual(groups, [True])
        self.assertLess(guard.WORKTREE_BUDGET + guard.WORKTREE_DISCARD_TIME, 60)
        self.assert_nothing_left()

    def test_add_timeout_kills_grandchildren(self):
        # worktree add は自分の session で動かし、期限を過ぎたら、git が動かした子（フィルタなど）もまとめて止める（Minor 2）。
        pidfile = self.root / "filter.pid"
        local_git(self.main, "config", "filter.slow.smudge", f"echo $$ > '{pidfile}'; exec sleep 30")
        info = self.main / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("README.md filter=slow\n", encoding="utf-8")
        start = time.monotonic()
        with mock.patch.object(guard, "WORKTREE_BUDGET", 4), mock.patch.object(guard, "WORKTREE_ADD_MIN", 1):
            code, out, err = self.create()
        self.assertLess(time.monotonic() - start, 20)
        self.assertEqual((code, out, self.adds), (1, "", 1))
        self.assertIn("TimeoutExpired", err)
        self.assert_nothing_left()
        pid = int(pidfile.read_text(encoding="utf-8"))
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail(f"filter process {pid} is still running")

    def test_deadline_bounds_every_git_call(self):
        # フックの開始からの期限（50 秒）の残りを、このモードの git のすべての timeout にする（Minor 3）。
        timeouts = []
        real_run = guard.subprocess.run

        def spy_run(*args, **kwargs):
            timeouts.append(kwargs.get("timeout"))
            return real_run(*args, **kwargs)

        with mock.patch.object(guard.subprocess, "run", side_effect=spy_run):
            self.assertEqual(self.create()[0], 0)
        self.assertTrue(timeouts)
        self.assertTrue(all(0 < t <= guard.WORKTREE_BUDGET for t in timeouts), timeouts)
        # 残りが worktree add に足りなければ、作らずに止める。
        with mock.patch.object(guard, "WORKTREE_ADD_MIN", guard.WORKTREE_BUDGET + 1):
            code, out, err = self.create("y")
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn("時間", err)
        self.assert_nothing_left(name="y")
        # 期限を過ぎたら、次の git を動かさずに止める。
        with mock.patch.object(guard, "WORKTREE_BUDGET", 0):
            code, out, err = self.create("z")
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn("時間", err)
        self.assert_nothing_left(name="z")

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

    def test_old_location_symlink_has_no_effect(self):
        # 置き場所はリポジトリの外なので、sandbox が書ける .claude/worktrees を、確かめる途中で symlink にしても
        # 書く先は変わらない（レビューの probe の形 A）。
        outside = self.root / "outside"
        outside.mkdir()
        real = guard.compare_with_main

        def swap_then_compare(*args):
            os.symlink(outside, self.main / ".claude" / "worktrees")
            return real(*args)

        with mock.patch.object(guard, "compare_with_main", side_effect=swap_then_compare):
            code, out, err = self.create()
        self.assertEqual((code, out, err), (0, f"{self.place}\n", ""))
        self.assertEqual(os.listdir(outside), [])
        self.assertIn(f"worktree {self.place}", local_git(self.main, "worktree", "list", "--porcelain").split("\n"))

    def test_unsafe_base_stops(self):
        # 置き場所の基（.cc-worktrees・キー・.verified）は、自分だけが書ける実体のディレクトリでなければ止める（R22）。
        base = self.home / ".cc-worktrees"
        key = self.place.parent
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()

        def check(label):
            with self.subTest(label=label):
                code, out, err = self.create()
                self.assertEqual((code, out, self.adds), (1, "", 0))
                self.assertIn("自分だけが書ける", err)
                self.assertEqual(os.listdir(elsewhere), [])
                self.assert_nothing_left()

        os.symlink(elsewhere, base)
        check("base symlink")
        base.unlink()
        base.mkdir(mode=0o700)
        os.symlink(elsewhere, key)
        check("key symlink")
        key.unlink()
        key.mkdir(mode=0o700)
        os.chmod(key, 0o770)
        check("key group-writable")
        os.chmod(key, 0o700)
        os.symlink(elsewhere, key / ".verified")
        check("verified symlink")
        (key / ".verified").unlink()
        # ほかの人のディレクトリは作れないので、uid を差し替えて確かめる。
        home = guard.user_home()
        with mock.patch.object(guard.os, "getuid", return_value=os.getuid() + 1), \
                mock.patch.object(guard, "user_home", return_value=home):
            check("owned by someone else")
        self.assertEqual(self.create()[0], 0)

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

    def test_gitdir_symlink_stops_before_creating(self):
        # worktree add は、元のチェックアウトの共通の gitdir に書く（logs/refs/heads/worktree-<name> など）。
        # その途中が symlink なら、git はその先に書くので、作る前に止める（D2）。
        logs = self.main / ".git" / "logs" / "refs"
        outside = self.root / "outside-logs"
        os.rename(logs, outside)
        os.symlink(outside, logs)
        before = sorted(p.name for p in outside.rglob("*"))
        code, out, err = self.create()
        self.assertEqual((code, out, self.adds), (1, "", 0))
        self.assertIn(f"{logs} が、symlink か", err)
        self.assertEqual(sorted(p.name for p in outside.rglob("*")), before)
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
        # main はホームの下に作る。sandbox はホームに書けないので、テストではホームを一時ディレクトリに差し替える。
        with mock.patch.object(guard, "user_home", return_value=self.home):
            self.assertEqual(run(json.dumps(payload).encode("utf-8")), (0, f"{self.place}\n", ""))
        for data in (b"", b"{", b"[]", b'"x"'):
            with self.subTest(data=data):
                code, out, err = run(data)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("止めました", err)
        self.assertEqual(guard.main(["worktree-create", "x"]), 1)

    def test_unverified_worktree_is_left_alone(self):
        # 確かめ終わった印のない登録（作る途中で止められたものなど）は返さず、消すコマンドを案内して触らない（R22・R20）。
        self.assertEqual(self.create()[0], 0)
        marker = self.place.parent / ".verified" / "x"
        oid = local_git(self.main, "rev-parse", "worktree-x")

        def check(label, name="x"):
            place = self.place_of(self.main, name)
            with self.subTest(label=label):
                code, out, err = self.create(name)
                self.assertEqual((code, out, self.adds), (1, "", 0))
                self.assertIn(f"git -C {self.main} worktree remove --force {place}", err)
                self.assertIn(f"git -C {self.main} branch -D worktree-{name}", err)
                self.assertTrue((place / ".claude" / "settings.json").exists())
                self.assertIn(f"worktree {place}", local_git(self.main, "worktree", "list", "--porcelain").split("\n"))

        marker.unlink()
        check("no marker")
        st = os.lstat(self.place)
        marker.write_text(f"{st.st_dev} {st.st_ino + 1}\n", encoding="utf-8")
        check("other inode")
        self.assertEqual(local_git(self.main, "rev-parse", "worktree-x"), oid)
        # フックを通さずに作った worktree も、同じく返さない。
        local_git(self.main, "worktree", "add", "-q", "-b", "worktree-plain", str(self.place_of(self.main, "plain")))
        check("made without the hook", "plain")

    def test_failed_add_leaves_others_branch(self):
        # 確認の後に別のものが作ったブランチは、作成元を指していなければ消さない（Minor 1）。
        feature = local_git(self.main, "rev-parse", "origin/feature")
        real = guard._git_process

        def branch_appears(cwd, *args, **kwargs):
            if args[:2] == ("worktree", "add"):
                local_git(self.main, "branch", "worktree-x", feature)
                return subprocess.CompletedProcess(args, 128, b"", b"")
            return real(cwd, *args, **kwargs)

        with mock.patch.object(guard, "_git_process", side_effect=branch_appears):
            code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("worktree add が失敗しました", err)
        self.assertEqual(local_git(self.main, "rev-parse", "worktree-x"), feature)


if __name__ == "__main__":
    unittest.main()
