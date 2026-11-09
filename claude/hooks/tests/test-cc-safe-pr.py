import contextlib
import errno
import http.client
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

BIN = Path(__file__).resolve().parents[2] / "bin"
loader = importlib.machinery.SourceFileLoader("cc_safe_pr", str(BIN / "cc-safe-pr"))
spec = importlib.util.spec_from_loader(loader.name, loader)
wrapper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wrapper
loader.exec_module(wrapper)
policy = wrapper.load_push_policy()

REQUEST = ".cc-pr-request.json"
REPO = "/repos/Example/Safe"
PR_URL = "https://github.com/Example/Safe/pull/7"
TOKEN = "gho_" + "a" * 36


def local_git(cwd, *args):
    cp = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if cp.returncode:
        raise AssertionError(cp.stderr)
    return cp.stdout.strip()


def without(data, *keys):
    return {k: v for k, v in data.items() if k not in keys}


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def read(self, amt=None):
        return self.body

    def getheader(self, name, default=None):
        return "GH-REQ-1" if name.lower() == "x-github-request-id" else default


class FakeConnection:
    def __init__(self, github):
        self.github = github
        self.route = None

    def request(self, method, path, body=None, headers=None):
        self.github.requests.append(SimpleNamespace(
            method=method, path=path, body=json.loads(body) if body else None, headers=headers or {}))
        if (method, path) not in self.github.routes:
            raise AssertionError(f"unexpected request: {method} {path}")
        self.route = self.github.routes[(method, path)]
        if self.route.get("before"):
            self.route["before"]()

    def getresponse(self):
        if self.route.get("error"):
            raise self.route["error"]
        raw = self.route.get("raw")
        return FakeResponse(self.route["status"], raw if raw is not None else json.dumps(self.route["data"]).encode())

    def close(self):
        pass


class FakeGitHub:
    """api.github.com の代わり。HTTPS 接続の層だけを差し替え、wrapper.api() は本物を動かす。"""

    def __init__(self):
        self.routes = {}
        self.requests = []
        self.connections = []

    def set(self, method, path, status=200, data=None, raw=None, error=None, before=None):
        self.routes[(method, path)] = {"status": status, "data": data, "raw": raw, "error": error, "before": before}

    def connection(self, host, port=None, context=None, timeout=None):
        self.connections.append(SimpleNamespace(host=host, port=port, context=context, timeout=timeout))
        return FakeConnection(self)

    def writes(self):
        return [r for r in self.requests if r.method in ("POST", "PATCH", "PUT", "DELETE")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="claude-pr-")
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
        self.sha = local_git(self.repo, "rev-parse", "HEAD")
        self.config = self.root / "allowlist.jsonc"
        self.set_allowlist([{"gitCommonDir": str(self.repo / ".git"), "github": "Example/Safe"}])
        self.log = self.root / "logs" / "audit.jsonl"
        self.log.parent.mkdir()
        self.github = FakeGitHub()
        real_evaluate = policy.evaluate
        for target, name, value in (
            (policy, "evaluate", lambda cwd: real_evaluate(cwd, self.config)),
            (wrapper, "log_path", lambda home: self.log),
            (wrapper, "github_token", lambda: TOKEN),
            (http.client, "HTTPSConnection", self.github.connection),
        ):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)

    def set_allowlist(self, entries):
        self.config.write_text(json.dumps({"version": 1, "allowList": entries}), encoding="utf-8")
        os.chmod(self.config, 0o600)

    def create_request(self, **changes):
        return {"version": 1, "op": "create", "head": "feature/demo", "title": "feat: demo",
                "body": "body text", "base": "main", "draft": False, **changes}

    def edit_request(self, **changes):
        return {"version": 1, "op": "edit", "head": "feature/demo", "number": 7,
                "title": "new title", "body": "new body", **changes}

    def pull(self, **changes):
        return {
            "number": 7, "html_url": PR_URL, "state": "open", "merged": False, "draft": False,
            "title": "feat: demo", "body": "body text", "user": {"login": "me"},
            "head": {"ref": "feature/demo", "sha": self.sha, "repo": {"full_name": "Example/Safe"}},
            "base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "Example/Safe"}},
            **changes,
        }

    def stock_create(self, base="main", branch="feature/demo"):
        self.github.set("GET", REPO, data={"full_name": "Example/Safe", "archived": False, "default_branch": "main"})
        self.github.set("GET", f"{REPO}/git/ref/heads/{branch}",
                        data={"ref": f"refs/heads/{branch}", "object": {"sha": self.sha, "type": "commit"}})
        head = "Example%3A" + branch.replace("/", "%2F")
        self.github.set("GET", f"{REPO}/pulls?head={head}&base={base}&state=open", data=[])
        self.github.set("POST", f"{REPO}/pulls", status=201, data=self.pull(
            head={"ref": branch, "sha": self.sha, "repo": {"full_name": "Example/Safe"}},
            base={"ref": base, "sha": "b" * 40, "repo": {"full_name": "Example/Safe"}}))

    def stock_edit(self):
        self.github.set("GET", "/user", data={"login": "me"})
        self.github.set("GET", f"{REPO}/pulls/7", data=self.pull())
        self.github.set("PATCH", f"{REPO}/pulls/7", data=self.pull())

    def write_request(self, data=None, raw=None):
        Path(REQUEST).write_bytes(raw if raw is not None else json.dumps(data).encode("utf-8"))

    def run_op(self, op, request=None, raw=None):
        if request is not None or raw is not None:
            self.write_request(request, raw)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = wrapper.execute(op, policy)
        self.out, self.err = out.getvalue(), err.getvalue()
        return code

    def log_records(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def assert_no_claim_left(self):
        self.assertEqual(list(Path(".").glob(REQUEST + ".*")), [])


class CreateTests(Base):
    def test_sends_only_the_fixed_fields(self):
        self.stock_create()
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertEqual([(r.method, r.path) for r in self.github.writes()], [("POST", f"{REPO}/pulls")])
        self.assertEqual(self.github.writes()[0].body, {
            "title": "feat: demo", "head": "feature/demo", "base": "main", "body": "body text", "draft": False})
        self.assertEqual(self.out, f"CREATED: {PR_URL}\n")

    def test_draft_is_forwarded(self):
        self.stock_create()
        self.assertEqual(self.run_op("create", self.create_request(draft=True)), 0, self.err)
        self.assertIs(self.github.writes()[0].body["draft"], True)

    def test_draft_defaults_to_false(self):
        self.stock_create()
        self.assertEqual(self.run_op("create", without(self.create_request(), "draft")), 0, self.err)
        self.assertIs(self.github.writes()[0].body["draft"], False)

    def test_base_defaults_to_the_repository_default_branch(self):
        self.stock_create(base="develop")
        self.github.set("GET", REPO, data={"full_name": "Example/Safe", "archived": False, "default_branch": "develop"})
        self.assertEqual(self.run_op("create", without(self.create_request(), "base")), 0, self.err)
        self.assertEqual(self.github.writes()[0].body["base"], "develop")

    def test_from_subdirectory(self):
        sub = self.repo / "sub"
        sub.mkdir()
        os.chdir(sub)
        self.stock_create()
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)

    def test_from_worktree(self):
        wt = self.root / "worktree"
        local_git(self.repo, "worktree", "add", "-b", "feature/wt", str(wt))
        os.chdir(wt)
        self.stock_create(branch="feature/wt")
        self.assertEqual(self.run_op("create", self.create_request(head="feature/wt")), 0, self.err)
        self.assertEqual(self.github.writes()[0].body["head"], "feature/wt")

    def test_git_file_cannot_change_the_destination(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / ".git").write_text(f"gitdir: {self.repo / '.git'}\n", encoding="utf-8")
        os.chdir(elsewhere)
        self.stock_create()
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertEqual(self.github.writes()[0].path, f"{REPO}/pulls")

    def test_preflight_denials_send_nothing(self):
        cases = {
            "not pushed": lambda: self.github.set("GET", f"{REPO}/git/ref/heads/feature/demo", status=404, data={"message": "Not Found"}),
            "other sha": lambda: self.github.set("GET", f"{REPO}/git/ref/heads/feature/demo", data={"ref": "refs/heads/feature/demo", "object": {"sha": "c" * 40}}),
            "archived": lambda: self.github.set("GET", REPO, data={"full_name": "Example/Safe", "archived": True, "default_branch": "main"}),
            "renamed case": lambda: self.github.set("GET", REPO, data={"full_name": "example/safe", "archived": False, "default_branch": "main"}),
            "existing": lambda: self.github.set("GET", f"{REPO}/pulls?head=Example%3Afeature%2Fdemo&base=main&state=open", data=[self.pull()]),
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.github.requests.clear()
                self.stock_create()
                change()
                self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_DENIED, name)
                self.assertEqual(self.github.writes(), [], name)

    def test_existing_pull_request_is_named(self):
        self.stock_create()
        self.github.set("GET", f"{REPO}/pulls?head=Example%3Afeature%2Fdemo&base=main&state=open", data=[self.pull()])
        self.run_op("create", self.create_request())
        self.assertIn(PR_URL, self.err)

    def test_base_equal_to_head_is_denied(self):
        self.stock_create(base="feature/demo")
        self.assertEqual(self.run_op("create", self.create_request(base="feature/demo")), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])

    def test_response_mismatch_needs_confirmation_and_names_the_url(self):
        cases = {
            "head sha": {"head": {"ref": "feature/demo", "sha": "d" * 40, "repo": {"full_name": "Example/Safe"}}},
            "head ref": {"head": {"ref": "feature/other", "sha": self.sha, "repo": {"full_name": "Example/Safe"}}},
            "base ref": {"base": {"ref": "other", "sha": "b" * 40, "repo": {"full_name": "Example/Safe"}}},
            "base repo": {"base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "Other/Repo"}}},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                self.stock_create()
                self.github.set("POST", f"{REPO}/pulls", status=201, data=self.pull(**changes))
                self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_UNKNOWN, name)
                self.assertIn(PR_URL, self.err)
                self.assertNotIn(PR_URL, self.out)


class EditTests(Base):
    def test_sends_only_title_and_body(self):
        self.stock_edit()
        self.assertEqual(self.run_op("edit", self.edit_request()), 0, self.err)
        self.assertEqual([(r.method, r.path) for r in self.github.writes()], [("PATCH", f"{REPO}/pulls/7")])
        self.assertEqual(self.github.writes()[0].body, {"title": "new title", "body": "new body"})
        self.assertEqual(self.out, f"EDITED: {PR_URL}\n")

    def test_omitted_field_is_not_sent(self):
        self.stock_edit()
        self.assertEqual(self.run_op("edit", without(self.edit_request(), "body")), 0, self.err)
        self.assertEqual(self.github.writes()[0].body, {"title": "new title"})

    def test_needs_title_or_body(self):
        self.stock_edit()
        self.assertEqual(self.run_op("edit", without(self.edit_request(), "title", "body")), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.requests, [])

    def test_preflight_denials_send_nothing(self):
        cases = {
            "fork": {"head": {"ref": "feature/demo", "sha": "a" * 40, "repo": {"full_name": "Other/Fork"}}},
            "deleted fork": {"head": {"ref": "feature/demo", "sha": "a" * 40, "repo": None}},
            "other branch": {"head": {"ref": "feature/other", "sha": "a" * 40, "repo": {"full_name": "Example/Safe"}}},
            "other base repo": {"base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "Other/Repo"}}},
            "closed": {"state": "closed"},
            "merged": {"state": "closed", "merged": True},
            "merged but open": {"merged": True},
            "other author": {"user": {"login": "someone"}},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                self.github.requests.clear()
                self.stock_edit()
                self.github.set("GET", f"{REPO}/pulls/7", data=self.pull(**changes))
                self.assertEqual(self.run_op("edit", self.edit_request()), wrapper.EXIT_DENIED, name)
                self.assertEqual(self.github.writes(), [], name)

    def test_missing_pull_request_is_denied(self):
        self.stock_edit()
        self.github.set("GET", f"{REPO}/pulls/7", status=404, data={"message": "Not Found"})
        self.assertEqual(self.run_op("edit", self.edit_request()), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])

    def test_response_mismatch_needs_confirmation(self):
        cases = {
            "closed": {"state": "closed"},
            "merged": {"merged": True},
            "other repo": {"base": {"ref": "main", "sha": "b" * 40, "repo": {"full_name": "Other/Repo"}}},
            "other head": {"head": {"ref": "feature/other", "sha": "a" * 40, "repo": {"full_name": "Example/Safe"}}},
            "other number": {"number": 8},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                self.stock_edit()
                self.github.set("PATCH", f"{REPO}/pulls/7", data=self.pull(**changes))
                self.assertEqual(self.run_op("edit", self.edit_request()), wrapper.EXIT_UNKNOWN, name)


class RepositoryPolicyTests(Base):
    def assert_denied_without_requests(self, request):
        self.assertEqual(self.run_op("create", request), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.requests, [])

    def test_unlisted_repository_keeps_the_request_untouched(self):
        self.set_allowlist([])
        self.assert_denied_without_requests(self.create_request())
        self.assertTrue(Path(REQUEST).exists())

    def test_other_clone_of_the_same_repository_is_denied(self):
        clone = self.root / "clone"
        subprocess.run(["git", "clone", "-q", str(self.repo), str(clone)], check=True)
        local_git(clone, "remote", "set-url", "origin", "git@github.com:Example/Safe.git")
        os.chdir(clone)
        self.assert_denied_without_requests(self.create_request())

    def test_detached_head_is_denied(self):
        local_git(self.repo, "checkout", "--detach", "HEAD")
        self.assert_denied_without_requests(self.create_request())

    def test_protected_branch_is_denied(self):
        local_git(self.repo, "switch", "-c", "main")
        self.assert_denied_without_requests(self.create_request(head="main", base="develop"))

    def test_changed_origin_is_denied(self):
        local_git(self.repo, "remote", "set-url", "origin", "git@github.com:Other/Repo.git")
        self.assert_denied_without_requests(self.create_request())

    def test_multiple_origin_urls_are_denied(self):
        local_git(self.repo, "remote", "set-url", "--add", "origin", "git@github.com:Other/Repo.git")
        self.assert_denied_without_requests(self.create_request())

    def test_deleted_working_directory_is_denied(self):
        gone = self.root / "gone"
        gone.mkdir()
        os.chdir(gone)
        gone.rmdir()
        self.assertEqual(self.run_op("create"), wrapper.EXIT_DENIED)

    def test_configured_programs_are_never_run(self):
        marker = self.root / "ran"
        program = self.root / "program"
        program.write_text(f'#!/bin/sh\ntouch "{marker}"\n', encoding="utf-8")
        program.chmod(0o755)
        for key in ("core.fsmonitor", "core.sshCommand", "core.pager", "core.askPass", "credential.helper"):
            local_git(self.repo, "config", key, str(program))
        self.stock_create()
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertFalse(marker.exists())


class ArgumentTests(Base):
    def test_only_create_or_edit_alone_is_accepted(self):
        self.write_request(self.create_request())
        for argv in ([], ["--repo", "x/y"], ["create", "extra"], ["merge"], ["close"], ["ready"], ["CREATE"]):
            with self.subTest(argv):
                with mock.patch.object(sys, "argv", ["cc-safe-pr", *argv]):
                    with mock.patch.object(wrapper, "execute") as execute:
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(wrapper.main(), wrapper.EXIT_DENIED)
                execute.assert_not_called()
        self.assertTrue(Path(REQUEST).exists())

    def test_environment_cannot_redirect_the_request(self):
        self.stock_create()
        hostile = {"GH_REPO": "Other/Repo", "GH_HOST": "evil.example", "GH_TOKEN": "x", "GITHUB_TOKEN": "x",
                   "GIT_DIR": "/nonexistent", "HTTPS_PROXY": "http://evil.example:1", "https_proxy": "http://evil.example:1",
                   "PATH": "/nonexistent"}
        with mock.patch.dict(os.environ, hostile):
            self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertEqual(self.github.writes()[0].path, f"{REPO}/pulls")
        self.assertEqual({c.host for c in self.github.connections}, {"api.github.com"})
        self.assertEqual(self.github.requests[0].headers["Authorization"], f"Bearer {TOKEN}")


class RequestFileTests(Base):
    def setUp(self):
        super().setUp()
        self.stock_create()
        self.secret = self.root / "secret"
        self.secret.write_text("CANARY-SECRET\n", encoding="utf-8")

    def assert_denied(self, op="create"):
        self.assertEqual(self.run_op(op), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])
        self.assertNotIn("CANARY-SECRET", self.err)
        self.assert_no_claim_left()

    def test_missing_file_is_denied(self):
        self.assert_denied()

    def test_symlink_is_removed_without_touching_its_target(self):
        Path(REQUEST).symlink_to(self.secret)
        self.assert_denied()
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertEqual(self.secret.read_text(encoding="utf-8"), "CANARY-SECRET\n")

    def test_symlink_to_a_valid_request_is_not_followed(self):
        target = self.root / "valid.json"
        target.write_text(json.dumps(self.create_request()), encoding="utf-8")
        Path(REQUEST).symlink_to(target)
        self.assert_denied()

    def test_hard_link_is_denied(self):
        target = self.root / "valid.json"
        target.write_text(json.dumps(self.create_request()), encoding="utf-8")
        os.link(target, REQUEST)
        self.assert_denied()
        self.assertTrue(target.exists())

    def test_fifo_is_denied_without_blocking(self):
        os.mkfifo(REQUEST)
        self.assert_denied()

    def test_directory_is_denied(self):
        os.mkdir(REQUEST)
        self.assertEqual(self.run_op("create"), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])

    def test_file_owned_by_someone_else_is_denied(self):
        self.write_request(self.create_request())
        real = os.fstat

        def other_owner(fd):
            st = real(fd)
            return SimpleNamespace(st_mode=st.st_mode, st_uid=st.st_uid + 1, st_nlink=st.st_nlink, st_size=st.st_size)
        with mock.patch.object(wrapper.os, "fstat", other_owner):
            self.assert_denied()

    def test_non_regular_file_is_denied_even_if_readable(self):
        self.write_request(self.create_request())
        real = os.fstat

        def fifo(fd):
            st = real(fd)
            return SimpleNamespace(st_mode=stat.S_IFIFO | 0o600, st_uid=st.st_uid, st_nlink=st.st_nlink, st_size=st.st_size)
        with mock.patch.object(wrapper.os, "fstat", fifo):
            self.assert_denied()

    def test_oversized_file_is_denied(self):
        # 先頭だけで有効な JSON になるようにして、切り詰めて読んでも受理されないことを確かめる。
        self.write_request(raw=json.dumps(self.create_request()).encode() + b" " * (1024 * 1024))
        self.assert_denied()

    def test_invalid_requests_are_denied_without_echoing_them(self):
        good = self.create_request()
        cases = {
            "not json": b'{"title": "CANARY-SECRET", oops',
            "not utf-8": b'\xff\xfe"CANARY-SECRET"',
            "not an object": b'["CANARY-SECRET"]',
            "duplicate key": b'{"version": 1, "op": "create", "head": "feature/demo", "title": "x", "title": "y", "body": "b"}',
            "nan": json.dumps({**good, "draft": float("nan")}).encode(),
            "infinity": json.dumps({**good, "draft": float("inf")}).encode(),
            "unknown key": json.dumps({**good, "repo": "Other/Repo"}).encode(),
            "url key": json.dumps({**good, "url": "https://github.com/Other/Repo/pull/1"}).encode(),
            "version 2": json.dumps({**good, "version": 2}).encode(),
            "version true": json.dumps({**good, "version": True}).encode(),
            "missing version": json.dumps(without(good, "version")).encode(),
            "op mismatch": json.dumps({**good, "op": "edit"}).encode(),
            "missing head": json.dumps(without(good, "head")).encode(),
            "other head": json.dumps({**good, "head": "feature/other"}).encode(),
            "missing title": json.dumps(without(good, "title")).encode(),
            "missing body": json.dumps(without(good, "body")).encode(),
            "empty title": json.dumps({**good, "title": ""}).encode(),
            "newline in title": json.dumps({**good, "title": "a\nb"}).encode(),
            "control in title": json.dumps({**good, "title": "a\x07b"}).encode(),
            "long title": json.dumps({**good, "title": "x" * 300}).encode(),
            "title not string": json.dumps({**good, "title": 1}).encode(),
            "nul in body": json.dumps({**good, "body": "a\x00b"}).encode(),
            "long body": json.dumps({**good, "body": "x" * 70000}).encode(),
            "body not string": json.dumps({**good, "body": ["x"]}).encode(),
            "draft string": json.dumps({**good, "draft": "true"}).encode(),
            "draft number": json.dumps({**good, "draft": 1}).encode(),
            "base option": json.dumps({**good, "base": "-x"}).encode(),
            "base not string": json.dumps({**good, "base": 1}).encode(),
        }
        for name, raw in cases.items():
            with self.subTest(name):
                self.github.requests.clear()
                self.write_request(raw=raw)
                self.assert_denied()

    def test_invalid_edit_numbers_are_denied(self):
        self.stock_edit()
        for number in (True, 0, -1, "7", 7.0, None):
            with self.subTest(number):
                self.write_request(self.edit_request(number=number))
                self.assert_denied("edit")

    def test_request_is_consumed_even_when_denied_after_reading(self):
        self.run_op("create", self.create_request(head="feature/other"))
        self.assertFalse(os.path.lexists(REQUEST))

    def test_second_run_finds_no_request(self):
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertEqual(self.run_op("create"), wrapper.EXIT_DENIED)
        self.assertEqual(len(self.github.writes()), 1)

    def test_request_written_after_the_claim_survives(self):
        later = json.dumps(self.create_request(title="later")).encode("utf-8")
        self.github.set("POST", f"{REPO}/pulls", status=201, data=self.pull(), before=lambda: Path(REQUEST).write_bytes(later))
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertEqual(Path(REQUEST).read_bytes(), later)
        self.assertEqual(self.github.writes()[0].body["title"], "feat: demo")
        self.assert_no_claim_left()

    def test_no_claim_is_left_after_success(self):
        self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertFalse(os.path.lexists(REQUEST))
        self.assert_no_claim_left()


class GitHubFailureTests(Base):
    def test_preflight_failures_send_nothing(self):
        cases = {
            "forbidden": {"status": 403, "data": {"message": "Forbidden"}},
            "not found": {"status": 404, "data": {"message": "Not Found"}},
            "redirect": {"status": 301, "data": {"url": "https://api.github.com/repositories/1"}},
            "server error": {"status": 500, "data": {}},
            "invalid json": {"status": 200, "raw": b"<html>"},
            "timeout": {"error": socket.timeout("timed out")},
            "tls": {"error": ssl.SSLCertVerificationError("bad certificate")},
            "protocol": {"error": http.client.RemoteDisconnected("closed")},
        }
        for name, route in cases.items():
            with self.subTest(name):
                self.github.requests.clear()
                self.stock_create()
                self.github.set("GET", REPO, **route)
                self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_FAILED, name)
                self.assertEqual(self.github.writes(), [], name)

    def test_refused_writes_are_failures(self):
        for status in (401, 403, 404, 422, 301):
            with self.subTest(status):
                self.stock_create()
                self.github.set("POST", f"{REPO}/pulls", status=status, data={"message": "no"})
                self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_FAILED, status)

    def test_uncertain_create_results_need_confirmation(self):
        cases = {
            "timeout": {"error": socket.timeout("timed out")},
            "disconnect": {"error": http.client.RemoteDisconnected("closed")},
            "server error": {"status": 502, "data": {"message": "Bad Gateway"}},
            "invalid json": {"status": 201, "raw": b"<html>"},
            "not an object": {"status": 201, "data": []},
            "no url": {"status": 201, "data": {"number": 7}},
            "foreign url": {"status": 201, "data": self.pull(html_url="https://evil.example/pull/7")},
        }
        for name, route in cases.items():
            with self.subTest(name):
                self.stock_create()
                self.github.set("POST", f"{REPO}/pulls", **route)
                self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_UNKNOWN, name)

    def test_uncertain_edit_results_need_confirmation(self):
        cases = {
            "timeout": {"error": socket.timeout("timed out")},
            "server error": {"status": 503, "data": {}},
            "invalid json": {"status": 200, "raw": b"<html>"},
        }
        for name, route in cases.items():
            with self.subTest(name):
                self.stock_edit()
                self.github.set("PATCH", f"{REPO}/pulls/7", **route)
                self.assertEqual(self.run_op("edit", self.edit_request()), wrapper.EXIT_UNKNOWN, name)

    def test_unexpected_success_on_create_needs_confirmation(self):
        for status in (200, 202, 204):
            with self.subTest(status):
                self.stock_create()
                self.github.set("POST", f"{REPO}/pulls", status=status, data=self.pull())
                self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_UNKNOWN, status)

    def test_unexpected_success_on_edit_needs_confirmation(self):
        for status in (201, 202, 204):
            with self.subTest(status):
                self.stock_edit()
                self.github.set("PATCH", f"{REPO}/pulls/7", status=status, data=self.pull())
                self.assertEqual(self.run_op("edit", self.edit_request()), wrapper.EXIT_UNKNOWN, status)

    def test_termination_before_sending_is_a_failure(self):
        self.stock_create()
        self.github.set("GET", REPO, before=lambda: wrapper.on_sigterm(signal.SIGTERM, None),
                        data={"full_name": "Example/Safe", "archived": False, "default_branch": "main"})
        self.write_request(self.create_request())
        with self.assertRaises(SystemExit) as raised:
            self.run_op("create")
        self.assertEqual(raised.exception.code, wrapper.EXIT_FAILED)

    def test_termination_while_sending_needs_confirmation(self):
        self.stock_create()
        self.github.set("POST", f"{REPO}/pulls", status=201, data=self.pull(),
                        before=lambda: wrapper.on_sigterm(signal.SIGTERM, None))
        self.write_request(self.create_request())
        with self.assertRaises(SystemExit) as raised:
            self.run_op("create")
        self.assertEqual(raised.exception.code, wrapper.EXIT_UNKNOWN)

    def test_tls_context_verifies_with_the_system_bundle_only(self):
        self.stock_create()
        with mock.patch.dict(os.environ, {"SSL_CERT_FILE": "/dev/null", "SSL_CERT_DIR": "/nonexistent"}):
            self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        context = self.github.connections[0].context
        self.assertEqual(self.github.connections[0].port, 443)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)

    def test_only_the_system_certificate_bundle_is_trusted(self):
        self.stock_create()
        with mock.patch.object(wrapper.ssl, "create_default_context", wraps=ssl.create_default_context) as create:
            self.assertEqual(self.run_op("create", self.create_request()), 0, self.err)
        self.assertEqual({call.kwargs.get("cafile") for call in create.call_args_list}, {"/etc/ssl/cert.pem"})

    def test_request_headers_satisfy_github(self):
        self.stock_create()
        self.run_op("create", self.create_request())
        headers = self.github.requests[0].headers
        self.assertTrue(headers["User-Agent"])
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertTrue(headers["X-GitHub-Api-Version"])


class TokenTests(Base):
    def setUp(self):
        super().setUp()
        self.env_dump = self.root / "env"
        self.cwd_dump = self.root / "cwd"
        self.gh = self.root / "fake-gh"

    def token(self):
        # setUp で差し替えた wrapper.github_token ではなく、本物を実行する。
        return REAL_GITHUB_TOKEN()

    def write_gh(self, body):
        self.gh.write_text(f'#!/bin/sh\nenv > "{self.env_dump}"\npwd > "{self.cwd_dump}"\necho "$*" >> "{self.env_dump}"\n{body}\n', encoding="utf-8")
        self.gh.chmod(0o755)

    def with_gh(self):
        return mock.patch.object(wrapper, "GH", str(self.gh))

    def test_gh_path_is_absolute(self):
        self.assertTrue(os.path.isabs(wrapper.GH))

    def test_returns_the_token_from_a_minimal_environment(self):
        self.write_gh(f'printf "%s\\n" "{TOKEN}"')
        hostile = {"GH_TOKEN": "x", "GH_REPO": "Other/Repo", "GH_CONFIG_DIR": "/nonexistent", "GH_HOST": "evil.example"}
        with self.with_gh(), mock.patch.dict(os.environ, hostile):
            self.assertEqual(self.token(), TOKEN)
        env = self.env_dump.read_text(encoding="utf-8")
        for name in hostile:
            self.assertNotIn(name + "=", env)
        self.assertIn("auth token --hostname github.com", env)
        self.assertEqual(self.cwd_dump.read_text(encoding="utf-8").strip(), "/")

    def test_failures_are_reported_without_the_output(self):
        for name, body in {
            "fails": 'echo CANARY-SECRET >&2\nexit 1',
            "fails after printing a token": f'printf "%s\\n" "{TOKEN}"\nexit 1',
            "empty": "true",
            "bad format": 'echo "CANARY-SECRET: not a token"',
            "header injection": f'printf "%s\\r\\nX-Evil: 1\\n" "{TOKEN}"',
        }.items():
            with self.subTest(name):
                self.write_gh(body)
                with self.with_gh(), self.assertRaises(wrapper.Failed) as raised:
                    self.token()
                self.assertNotIn("CANARY-SECRET", str(raised.exception))

    def test_missing_gh_is_a_failure(self):
        with self.with_gh(), self.assertRaises(wrapper.Failed):
            self.token()

    def test_timeout_is_a_failure(self):
        self.write_gh(f'printf "%s\\n" "{TOKEN}"')
        with self.with_gh(), mock.patch.object(wrapper.subprocess, "run", side_effect=subprocess.TimeoutExpired("gh", 1)):
            with self.assertRaises(wrapper.Failed):
                self.token()

    def test_token_failure_sends_nothing(self):
        self.stock_create()
        with mock.patch.object(wrapper, "github_token", side_effect=wrapper.Failed("no token")):
            self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_FAILED)
        self.assertEqual(self.github.requests, [])


class AuditLogTests(Base):
    def test_unwritable_log_denies_before_reading_the_request(self):
        self.stock_create()
        blocker = self.root / "blocker"
        blocker.write_text("x", encoding="utf-8")
        with mock.patch.object(wrapper, "log_path", lambda home: blocker / "audit.jsonl"):
            self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.requests, [])
        self.assertTrue(Path(REQUEST).exists())

    def test_symlinked_log_is_denied_without_writing_through_it(self):
        self.stock_create()
        target = self.root / "target"
        target.write_text("original", encoding="utf-8")
        self.log.symlink_to(target)
        self.assertEqual(self.run_op("create", self.create_request()), wrapper.EXIT_DENIED)
        self.assertEqual(target.read_text(encoding="utf-8"), "original")
        self.assertEqual(self.github.requests, [])

    def run_with_log_write(self, write):
        self.stock_create()
        with mock.patch.object(wrapper.os, "write", write):
            return self.run_op("create", self.create_request())

    def test_short_writes_still_record_whole_entries(self):
        real = os.write
        code = self.run_with_log_write(lambda fd, data: real(fd, bytes(data)[:10]))
        self.assertEqual(code, 0, self.err)
        self.assertEqual([(r["phase"], r["outcome"]) for r in self.log_records()], [("decision", "allow"), ("result", "success")])

    def test_failed_write_denies_before_sending(self):
        def no_space(fd, data):
            raise OSError(errno.ENOSPC, "No space left on device")
        self.assertEqual(self.run_with_log_write(no_space), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])

    def test_failure_after_a_partial_write_denies_before_sending(self):
        real = os.write
        calls = []

        def partial_then_no_space(fd, data):
            if calls:
                raise OSError(errno.ENOSPC, "No space left on device")
            calls.append(1)
            return real(fd, bytes(data)[:10])
        self.assertEqual(self.run_with_log_write(partial_then_no_space), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])

    def test_write_without_progress_denies_before_sending(self):
        self.assertEqual(self.run_with_log_write(lambda fd, data: 0), wrapper.EXIT_DENIED)
        self.assertEqual(self.github.writes(), [])

    def test_result_that_cannot_be_recorded_only_warns(self):
        real = os.write
        calls = []

        def allow_then_no_space(fd, data):
            if calls:
                raise OSError(errno.ENOSPC, "No space left on device")
            calls.append(1)
            return real(fd, data)
        self.assertEqual(self.run_with_log_write(allow_then_no_space), 0, self.err)
        self.assertEqual(len(self.github.writes()), 1)
        self.assertIn("WARNING", self.err)

    def test_success_is_recorded_for_correlation(self):
        self.stock_create()
        self.run_op("create", self.create_request())
        records = self.log_records()
        self.assertEqual([(r["phase"], r["outcome"]) for r in records], [("decision", "allow"), ("result", "success")])
        self.assertEqual(records[0]["request_id"], records[1]["request_id"])
        result = records[1]
        self.assertEqual((result["op"], result["repo"], result["branch"]), ("create", "Example/Safe", "feature/demo"))
        self.assertEqual((result["local_sha"], result["remote_sha"]), (self.sha, self.sha))
        self.assertEqual((result["pr_number"], result["pr_url"]), (7, PR_URL))
        self.assertEqual((result["http_status"], result["github_request_id"]), (201, "GH-REQ-1"))
        self.assertEqual((result["title_len"], result["body_len"]), (10, 9))

    def test_denial_is_recorded(self):
        self.set_allowlist([])
        self.run_op("create", self.create_request())
        self.assertEqual([(r["phase"], r["outcome"]) for r in self.log_records()], [("decision", "deny")])

    def test_uncertain_result_is_recorded(self):
        self.stock_create()
        self.github.set("POST", f"{REPO}/pulls", error=socket.timeout("timed out"))
        self.run_op("create", self.create_request())
        self.assertEqual(self.log_records()[-1]["outcome"], "unknown")

    def test_secrets_and_text_are_not_recorded(self):
        self.stock_create()
        self.run_op("create", self.create_request(title="CANARY-TITLE", body="CANARY-BODY"))
        text = self.log.read_text(encoding="utf-8")
        for needle in ("CANARY-TITLE", "CANARY-BODY", TOKEN):
            self.assertNotIn(needle, text)

    def test_log_file_is_private(self):
        self.stock_create()
        self.run_op("create", self.create_request())
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)

    def test_large_log_is_rotated_once(self):
        self.stock_create()
        self.log.write_bytes(b"x" * (6 * 1024 * 1024))
        self.run_op("create", self.create_request())
        self.assertEqual((self.log.parent / "audit.jsonl.1").stat().st_size, 6 * 1024 * 1024)
        self.assertLess(self.log.stat().st_size, 1024 * 1024)


class InstallationTests(unittest.TestCase):
    def test_missing_push_policy_denies(self):
        with tempfile.TemporaryDirectory(prefix="claude-pr-") as tmp:
            copy = Path(tmp) / "cc-safe-pr"
            shutil.copy(BIN / "cc-safe-pr", copy)
            cp = subprocess.run(["/usr/bin/python3", "-I", "-B", str(copy), "create"], capture_output=True, text=True, cwd=tmp)
        self.assertEqual(cp.returncode, wrapper.EXIT_DENIED)
        self.assertIn("DENIED", cp.stderr)


REAL_GITHUB_TOKEN = wrapper.github_token

if __name__ == "__main__":
    unittest.main()
