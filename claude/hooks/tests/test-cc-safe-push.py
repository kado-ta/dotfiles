import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

FILE = Path(__file__).resolve().parents[2] / "bin" / "cc-safe-push"
loader = importlib.machinery.SourceFileLoader("cc_safe_push", str(FILE))
spec = importlib.util.spec_from_loader(loader.name, loader)
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
loader.exec_module(policy)


def local_git(cwd, *args):
    cp = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if cp.returncode:
        raise AssertionError(cp.stderr)
    return cp.stdout.strip()


def has_ref(bare, ref):
    return subprocess.run(["git", "-C", str(bare), "rev-parse", "-q", "--verify", ref], capture_output=True).returncode == 0


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="claude-push-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        local_git(self.repo, "init", "-b", "feature/demo")
        local_git(self.repo, "config", "user.name", "Test")
        local_git(self.repo, "config", "user.email", "test@example.com")
        (self.repo / "README.md").write_text("demo\n", encoding="utf-8")
        local_git(self.repo, "add", "README.md")
        local_git(self.repo, "commit", "-m", "init")
        local_git(self.repo, "remote", "add", "origin", "git@github.com:Example/Safe.git")
        self.config = self.root / "allowlist.jsonc"
        self.set_allowlist([{"gitCommonDir": str(self.repo / ".git"), "github": "Example/Safe"}])

    def set_allowlist(self, entries):
        self.config.write_text(json.dumps({"version": 1, "allowList": entries}), encoding="utf-8")
        os.chmod(self.config, 0o600)

    def evaluate(self, cwd=None):
        return policy.evaluate(cwd or self.repo, self.config)

    def link_into_git_dir(self, name):
        canary = self.root / "canary"
        canary.write_text("CANARY-LINE-1234\n", encoding="utf-8")
        target = self.repo / ".git" / name
        if target.exists():
            target.unlink()
        target.symlink_to(canary)


class PolicyTests(Base):
    def test_allowed_feature(self):
        d = self.evaluate()
        self.assertEqual((d.kind, d.slug, d.branch), ("allow", "Example/Safe", "feature/demo"))
        self.assertEqual(d.sha, local_git(self.repo, "rev-parse", "HEAD"))

    def test_unlisted_clone_denied(self):
        self.set_allowlist([])
        self.assertEqual(self.evaluate().kind, "deny")

    def test_unlisted_repository_is_denied_before_reading_it(self):
        self.set_allowlist([])
        with mock.patch.object(policy, "run", wraps=policy.run) as run:
            self.assertEqual(self.evaluate().kind, "deny")
        self.assertEqual(run.call_args.args[-1], "--git-common-dir")

    def test_allowed_repo_mismatched_remote_denied(self):
        local_git(self.repo, "remote", "set-url", "origin", "git@github.com:Other/Repo.git")
        self.assertEqual(self.evaluate().kind, "deny")

    def test_inspection_does_not_run_configured_programs(self):
        marker = self.root / "ran"
        program = self.root / "program"
        program.write_text(f'#!/bin/sh\ntouch "{marker}"\n', encoding="utf-8")
        program.chmod(0o755)
        for key in ("core.fsmonitor", "core.sshCommand", "core.pager", "core.askPass", "core.editor",
                    "credential.helper", "diff.external", "gpg.program"):
            local_git(self.repo, "config", key, str(program))
        for hook in ("post-checkout", "reference-transaction"):
            path = self.repo / ".git/hooks" / hook
            path.write_text(f'#!/bin/sh\ntouch "{marker}"\n', encoding="utf-8")
            path.chmod(0o755)
        self.assertEqual(self.evaluate().kind, "allow")
        self.assertFalse(marker.exists())

    def test_protected_branch_deny(self):
        for branch in ("main", "master", "staging"):
            local_git(self.repo, "switch", "-c", branch)
            self.assertEqual(self.evaluate().kind, "deny", branch)
            local_git(self.repo, "switch", "feature/demo")

    def test_protected_branch_is_denied_on_unlisted_repository(self):
        self.set_allowlist([])
        local_git(self.repo, "switch", "-c", "main")
        self.assertEqual(self.evaluate().kind, "deny")

    def test_protected_branch_case_variant_denied(self):
        local_git(self.repo, "switch", "-c", "Main")
        self.assertEqual(self.evaluate().kind, "deny")

    def test_protected_branch_with_same_named_tag_denied(self):
        local_git(self.repo, "switch", "-c", "main")
        local_git(self.repo, "tag", "main")
        d = self.evaluate()
        self.assertEqual((d.kind, d.branch), ("deny", "main"))

    def test_branch_with_same_named_tag_keeps_its_name(self):
        local_git(self.repo, "tag", "feature/demo")
        self.assertEqual(self.evaluate().branch, "feature/demo")

    def test_worktree_shares_common_git_dir(self):
        wt = self.root / "worktree"
        local_git(self.repo, "worktree", "add", "-b", "feature/worktree", str(wt))
        d = self.evaluate(wt)
        self.assertEqual((d.kind, d.branch), ("allow", "feature/worktree"))

    def test_git_dir_differing_by_trailing_character_is_not_the_listed_one(self):
        for suffix in (" ", "\r", "\n"):
            work = self.root / f"work{ord(suffix)}"
            work.mkdir()
            local_git(work, "init", "-b", "feature/other")
            local_git(work, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "--allow-empty", "-m", "init")
            local_git(work, "remote", "add", "origin", "git@github.com:Example/Safe.git")
            hidden = self.repo / f".git{suffix}"
            (work / ".git").rename(hidden)
            (work / ".git").symlink_to(hidden)
            self.assertEqual(self.evaluate(work).kind, "deny", repr(suffix))

    def test_subdirectory(self):
        sub = self.repo / "sub"
        sub.mkdir()
        self.assertEqual(self.evaluate(sub).kind, "allow")

    def test_detached_head_denied(self):
        local_git(self.repo, "checkout", "--detach", "HEAD")
        self.assertEqual(self.evaluate().kind, "deny")

    def test_unsafe_remotes_denied(self):
        for remote in ("https://github.com/Example/Safe.git", "git@evil.com:Example/Safe.git", "ext::evil", "git@github.com:Example/Safe.git;echo evil"):
            local_git(self.repo, "remote", "set-url", "origin", remote)
            self.assertEqual(self.evaluate().kind, "deny", remote)

    def test_multiple_remotes_denied(self):
        local_git(self.repo, "remote", "set-url", "--add", "origin", "git@github.com:Example/Another.git")
        self.assertEqual(self.evaluate().kind, "deny")

    def test_alternates_denied(self):
        (self.repo / ".git/objects/info/alternates").write_text("/nonexistent\n", encoding="utf-8")
        self.assertEqual(self.evaluate().kind, "deny")

    def test_missing_commit_is_not_fetched(self):
        source = self.root / "source.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(self.repo), str(source)], check=True)
        tree = local_git(source, "rev-parse", "HEAD^{tree}")
        sha = local_git(source, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit-tree", tree, "-m", "only in the source")
        local_git(source, "update-ref", "refs/heads/feature/demo", sha)
        local_git(self.repo, "config", "core.repositoryformatversion", "1")
        local_git(self.repo, "config", "extensions.partialClone", "promisor")
        local_git(self.repo, "config", "remote.promisor.url", str(source))
        local_git(self.repo, "config", "remote.promisor.promisor", "true")
        (self.repo / ".git/refs/heads/feature/demo").write_text(sha + "\n", encoding="utf-8")
        with mock.patch.object(policy, "TRANSPORT", "file"):
            self.assertEqual(self.evaluate().kind, "deny")

    def test_untrusted_config_permissions_denied(self):
        os.chmod(self.config, 0o666)
        self.assertEqual(self.evaluate().kind, "deny")

    def test_invalid_json_denied(self):
        self.config.write_text('{"repositories": []}', encoding="utf-8")
        self.assertEqual(self.evaluate().kind, "deny")

    def write_allowlist(self, lines):
        self.config.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(self.config, 0o600)

    def entry(self, trailing=""):
        return json.dumps({"gitCommonDir": str(self.repo / ".git"), "github": "Example/Safe"}) + trailing

    def test_whole_line_comments_are_allowed(self):
        self.write_allowlist(['// note', '{"version": 1, "allowList": [', '  // why this repository', "  " + self.entry(), "]}"])
        self.assertEqual(self.evaluate().kind, "allow")

    def test_commented_out_entry_is_not_active(self):
        self.write_allowlist(['{"version": 1, "allowList": [', "  // " + self.entry(), "]}"])
        self.assertEqual(self.evaluate().kind, "deny")

    def test_double_slash_inside_a_value_is_kept(self):
        path = f"{self.repo}//.git"
        self.write_allowlist(['{"version": 1, "allowList": [', json.dumps({"gitCommonDir": path, "github": "Example/Safe"}), "]}"])
        self.assertEqual(self.evaluate().kind, "allow")

    def test_other_comment_forms_are_denied(self):
        for lines in (
            ['{"version": 1, "allowList": [', self.entry(" // trailing"), "]}"],
            ['/* block */ {"version": 1, "allowList": [', self.entry(), "]}"],
            ['{"version": 1, "allowList": [', self.entry(","), "]}"],
        ):
            self.write_allowlist(lines)
            self.assertEqual(self.evaluate().kind, "deny", lines)

    def test_private_root_ignores_tmpdir(self):
        with mock.patch.dict(os.environ, {"TMPDIR": str(self.root)}):
            root = policy.private_root()
        self.assertTrue(root.is_dir())
        self.assertNotEqual(root, self.root)
        self.assertTrue(str(root).startswith("/var/folders/"))

    def test_sigterm_is_handled(self):
        with mock.patch.object(policy.signal, "signal") as handler:
            with mock.patch.object(sys, "argv", ["cc-safe-push", "--force"]):
                with contextlib.redirect_stderr(io.StringIO()):
                    policy.main()
        self.assertEqual(handler.call_args.args[0], policy.signal.SIGTERM)
        with self.assertRaises(SystemExit):
            handler.call_args.args[1](None, None)

    def test_missing_allowlist_denied(self):
        self.config.unlink()
        self.assertEqual(self.evaluate().kind, "deny")

    def test_removed_clone_does_not_deny_other_repositories(self):
        self.set_allowlist([
            {"gitCommonDir": str(self.repo / ".git"), "github": "Example/Safe"},
            {"gitCommonDir": str(self.root / "gone/.git"), "github": "Example/Gone"},
        ])
        self.assertEqual(self.evaluate().kind, "allow")

    def test_git_errors_do_not_quote_linked_files(self):
        for name in ("shallow", "packed-refs"):
            self.link_into_git_dir(name)
            self.assertNotIn("CANARY", self.evaluate().reason, name)
            (self.repo / ".git" / name).unlink()

    def test_reject_all_extra_arguments(self):
        for arg in ("--force", "--mirror", "origin", "HEAD:refs/heads/main", "--tags", "--hook"):
            with mock.patch.object(sys, "argv", ["cc-safe-push", arg]):
                with mock.patch.object(policy, "execute") as execute:
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(policy.main(), policy.EXIT_DENIED)
            execute.assert_not_called()

    def test_clean_env_ignores_git_command_injection(self):
        with mock.patch.dict(os.environ, {"GIT_SSH_COMMAND": "sh -c 'evil'", "GIT_CONFIG_COUNT": "1", "GIT_DIR": "/tmp/x", "PATH": "/tmp/hijack"}):
            env = policy.clean_env(policy.user_home())
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertNotIn("GIT_CONFIG_COUNT", env)
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("evil", env["GIT_SSH_COMMAND"])

    def test_ssh_command_is_accepted_by_ssh(self):
        home = Path("/Users/some one")
        cp = subprocess.run(["/bin/sh", "-c", policy.ssh_command(home) + " -G github.com"], capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        options = dict(line.split(" ", 1) for line in cp.stdout.splitlines() if " " in line)
        self.assertEqual(options["identityagent"], str(policy.agent_socket(home)))
        self.assertEqual(options["userknownhostsfile"], str(home / ".ssh/known_hosts"))
        self.assertEqual(options["identityfile"], "none")
        self.assertEqual(options["batchmode"], "yes")
        self.assertNotIn("proxycommand", options)


class ProductionAllowlistTests(Base):
    """root 所有の確認は本番のパスでしか動かないので、lstat の結果だけを差し替える。"""

    FILE = stat.S_IFREG | 0o644
    DIR = stat.S_IFDIR | 0o755
    USER = 501

    def evaluate_as_production(self, overrides=None):
        def fake_lstat(path):
            mode, uid = (overrides or {}).get(path, (self.FILE if path == self.config else self.DIR, 0))
            return SimpleNamespace(st_mode=mode, st_uid=uid)
        with mock.patch.object(policy, "CONFIG", self.config):
            with mock.patch.object(policy.Path, "lstat", autospec=True, side_effect=fake_lstat):
                return policy.evaluate(self.repo, self.config)

    def test_root_owned_allowlist_is_accepted(self):
        self.assertEqual(self.evaluate_as_production().kind, "allow")

    def test_allowlist_not_owned_by_root_denied(self):
        d = self.evaluate_as_production({self.config: (self.FILE, self.USER)})
        self.assertEqual(d.kind, "deny")
        self.assertIn("owned by root", d.reason)

    def test_unsafe_allowlist_file_denied(self):
        for mode in (stat.S_IFLNK | 0o755, stat.S_IFREG | 0o664, stat.S_IFREG | 0o666):
            self.assertEqual(self.evaluate_as_production({self.config: (mode, 0)}).kind, "deny", oct(mode))

    def test_unsafe_parent_directory_denied(self):
        unsafe = ((self.DIR, self.USER), (stat.S_IFDIR | 0o775, 0), (stat.S_IFDIR | 0o777, 0), (stat.S_IFLNK | 0o755, 0))
        for parent in (self.config.parent, Path("/")):
            for entry in unsafe:
                d = self.evaluate_as_production({parent: entry})
                self.assertEqual(d.kind, "deny", (parent, oct(entry[0]), entry[1]))
                self.assertIn("parent directory", d.reason)


class ExecuteTests(Base):
    decision = {"slug": "Example/Safe", "branch": "feature/demo", "sha": "a" * 40, "objects": "/x"}

    def execute(self, kind):
        d = policy.Decision(kind, "reason", **self.decision)
        with mock.patch.object(policy, "evaluate", return_value=d):
            with mock.patch.object(policy, "push", return_value=0) as pushed:
                with contextlib.redirect_stderr(io.StringIO()):
                    return policy.execute(), pushed.called

    def test_allow_pushes(self):
        self.assertEqual(self.execute("allow"), (0, True))

    def test_deny_never_pushes(self):
        self.assertEqual(self.execute("deny"), (policy.EXIT_DENIED, False))


class RealPushTests(Base):
    """SSH と GitHub だけをローカルの bare リポジトリへの file 転送に置き換える。"""

    def setUp(self):
        super().setUp()
        self.dest = self.root / "dest.git"
        self.other = self.root / "other.git"
        for bare in (self.dest, self.other):
            subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        self.caches = self.root / "caches"
        self.caches.mkdir()
        for name, value in (("TRANSPORT", "file"), ("private_root", lambda: self.caches), ("remote_url", lambda slug: str(self.dest))):
            patcher = mock.patch.object(policy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def push(self, cwd=None):
        d = self.evaluate(cwd)
        self.assertEqual(d.kind, "allow", d.reason)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = policy.push(d)
        return rc, out.getvalue() + err.getvalue()

    def test_pushes_only_the_current_branch(self):
        local_git(self.repo, "tag", "-a", "v1", "-m", "v1")
        local_git(self.repo, "branch", "feature/other")
        self.assertEqual(self.push()[0], 0)
        self.assertEqual(local_git(self.dest, "for-each-ref", "--format=%(refname)"), "refs/heads/feature/demo")
        self.assertEqual(local_git(self.dest, "rev-parse", "feature/demo"), local_git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(list(self.caches.iterdir()), [])

    def test_second_push_is_a_fast_forward(self):
        self.push()
        local_git(self.repo, "commit", "--allow-empty", "-m", "more")
        self.assertEqual(self.push()[0], 0)
        self.assertEqual(local_git(self.dest, "rev-parse", "feature/demo"), local_git(self.repo, "rev-parse", "HEAD"))

    def test_push_from_worktree(self):
        wt = self.root / "worktree"
        local_git(self.repo, "worktree", "add", "-b", "feature/worktree", str(wt))
        self.assertEqual(self.push(wt)[0], 0)
        self.assertTrue(has_ref(self.dest, "refs/heads/feature/worktree"))

    def test_repository_config_and_hooks_are_ignored(self):
        marker = self.root / "hook-ran"
        included = self.root / "included"
        included.write_text(f'[url "{self.other}"]\n\tpushInsteadOf = {self.dest}\n', encoding="utf-8")
        local_git(self.repo, "config", f"url.{self.other}.pushInsteadOf", str(self.dest))
        local_git(self.repo, "config", f"url.{self.other}.insteadOf", str(self.dest))
        local_git(self.repo, "config", f"remote.{self.dest}.pushurl", str(self.other))
        local_git(self.repo, "config", "include.path", str(included))
        for hook in ("pre-push", "reference-transaction"):
            path = self.repo / ".git/hooks" / hook
            path.write_text(f'#!/bin/sh\ntouch "{marker}"\n', encoding="utf-8")
            path.chmod(0o755)
        self.assertEqual(self.push()[0], 0)
        self.assertTrue(has_ref(self.dest, "refs/heads/feature/demo"))
        self.assertFalse(has_ref(self.other, "refs/heads/feature/demo"))
        self.assertFalse(marker.exists())

    def test_config_changed_after_the_decision_is_ignored(self):
        d = self.evaluate()
        local_git(self.repo, "config", f"url.{self.other}.pushInsteadOf", str(self.dest))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(policy.push(d), 0)
        self.assertFalse(has_ref(self.other, "refs/heads/feature/demo"))

    def test_commit_is_the_one_that_was_decided(self):
        d = self.evaluate()
        local_git(self.repo, "commit", "--allow-empty", "-m", "later")
        with contextlib.redirect_stdout(io.StringIO()):
            policy.push(d)
        self.assertEqual(local_git(self.dest, "rev-parse", "feature/demo"), d.sha)

    def test_working_repository_is_not_written(self):
        config = (self.repo / ".git/config").read_bytes()
        refs = local_git(self.repo, "for-each-ref")
        self.push()
        self.assertEqual((self.repo / ".git/config").read_bytes(), config)
        self.assertEqual(local_git(self.repo, "for-each-ref"), refs)

    def test_non_fast_forward_is_rejected(self):
        self.push()
        clone = self.root / "clone"
        subprocess.run(["git", "clone", "-q", "-b", "feature/demo", str(self.dest), str(clone)], check=True)
        local_git(clone, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "--allow-empty", "-m", "theirs")
        local_git(clone, "push", "-q", "origin", "feature/demo")
        remote = local_git(self.dest, "rev-parse", "feature/demo")
        local_git(self.repo, "commit", "--allow-empty", "-m", "ours")
        rc, output = self.push()
        self.assertEqual(rc, policy.EXIT_FAILED)
        self.assertIn("new commits", output)
        self.assertEqual(local_git(self.dest, "rev-parse", "feature/demo"), remote)

    def test_termination_removes_the_private_repository(self):
        d = self.evaluate()
        with mock.patch.object(policy, "run", side_effect=SystemExit(1)):
            with self.assertRaises(SystemExit):
                policy.push(d)
        self.assertEqual(list(self.caches.iterdir()), [])

    def test_failure_output_is_fixed_text(self):
        d = self.evaluate()
        result = subprocess.CompletedProcess([], 128, "", "fatal: CANARY-LINE-1234\n")
        with mock.patch.object(policy, "run", side_effect=[subprocess.CompletedProcess([], 0, "", ""), result]):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(policy.push(d), policy.EXIT_FAILED)
        self.assertNotIn("CANARY", err.getvalue())

    def test_unwritable_private_root_is_reported_without_a_traceback(self):
        d = self.evaluate()
        err = io.StringIO()
        with mock.patch.object(policy.tempfile, "mkdtemp", side_effect=PermissionError(1, "Operation not permitted")):
            with contextlib.redirect_stderr(err):
                self.assertEqual(policy.push(d), policy.EXIT_FAILED)
        self.assertIn("run cc-safe-push alone", err.getvalue())

    def test_refused_transport_does_not_push(self):
        with mock.patch.object(policy, "TRANSPORT", "ssh"):
            self.assertEqual(self.push()[0], policy.EXIT_FAILED)
        self.assertFalse(has_ref(self.dest, "refs/heads/feature/demo"))


if __name__ == "__main__":
    unittest.main()
