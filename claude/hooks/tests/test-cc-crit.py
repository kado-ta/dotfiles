import contextlib
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

BIN = Path(__file__).resolve().parents[2] / "bin"
loader = importlib.machinery.SourceFileLoader("cc_crit", str(BIN / "cc-crit"))
spec = importlib.util.spec_from_loader(loader.name, loader)
wrapper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wrapper
loader.exec_module(wrapper)

REQUEST = ".cc-crit-request.json"
SESSION = "d58eb1c63694"


def reply_request(**changes):
    data = {"session": SESSION, "replies": [{"reply_to": "c_73f150", "body": "3.3 を更新しました。\n\t詳細は下記"}]}
    data.update(changes)
    return data


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cc-crit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        # find_toplevel は .git の有無だけを見て、git は実行しない。
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "plan.md").write_text("# plan\n", encoding="utf-8")
        (self.root / "outside.md").write_text("outside\n", encoding="utf-8")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)

    def write_request(self, data=None, raw=None):
        Path(REQUEST).write_bytes(raw if raw is not None else json.dumps(data).encode("utf-8"))

    def assertDenied(self, fn, *args):
        with self.assertRaises(wrapper.Denied):
            fn(*args)


class ClaimTests(Base):
    def test_claims_and_removes_the_request(self):
        self.write_request({"files": ["docs/plan.md"]})
        raw = wrapper.claim_request()
        self.assertEqual(json.loads(raw), {"files": ["docs/plan.md"]})
        self.assertFalse(os.path.lexists(REQUEST))

    def test_missing_request_is_denied(self):
        self.assertDenied(wrapper.claim_request)

    def test_invalid_content_is_claimed_and_removed_before_parsing(self):
        self.write_request(raw=b"not json")
        raw = wrapper.claim_request()
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertDenied(wrapper.parse_request, raw, "review")

    def test_symlink_is_denied_and_removed(self):
        target = self.root / "target.json"
        target.write_text('{"files": []}', encoding="utf-8")
        os.symlink(target, REQUEST)
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertTrue(target.exists())

    def test_hard_link_is_denied_and_removed(self):
        other = self.root / "other.json"
        other.write_text('{"files": []}', encoding="utf-8")
        os.link(other, REQUEST)
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertTrue(other.exists())

    def test_fifo_is_denied_without_blocking(self):
        os.mkfifo(REQUEST)
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))

    def test_oversized_request_is_denied_and_removed(self):
        self.write_request(raw=b"{" + b" " * wrapper.MAX_REQUEST + b"}")
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))


class ParseReviewTests(Base):
    def parse(self, data):
        return wrapper.parse_request(json.dumps(data).encode("utf-8"), "review")

    def test_files_are_returned(self):
        self.assertEqual(self.parse({"files": ["docs/plan.md"]}), {"files": ["docs/plan.md"]})

    def test_omitted_files_mean_the_branch_diff(self):
        self.assertEqual(self.parse({}), {"files": []})

    def test_too_many_files_are_denied(self):
        self.assertDenied(self.parse, {"files": [f"f{i}.md" for i in range(wrapper.MAX_FILES + 1)]})

    def test_non_string_file_is_denied(self):
        self.assertDenied(self.parse, {"files": [1]})

    def test_empty_file_name_is_denied(self):
        self.assertDenied(self.parse, {"files": [""]})

    def test_files_must_be_a_list(self):
        self.assertDenied(self.parse, {"files": "docs/plan.md"})

    def test_unknown_key_is_denied(self):
        self.assertDenied(self.parse, {"files": [], "host": "0.0.0.0"})

    def test_reply_fields_are_denied_for_review(self):
        self.assertDenied(self.parse, reply_request())


class ParseReplyTests(Base):
    def parse(self, data):
        return wrapper.parse_request(json.dumps(data).encode("utf-8"), "reply")

    def test_valid_reply_is_returned(self):
        self.assertEqual(self.parse(reply_request()), reply_request())

    def test_missing_session_is_denied(self):
        data = reply_request()
        del data["session"]
        self.assertDenied(self.parse, data)

    def test_malformed_session_is_denied(self):
        for session in ("D58EB1C63694", "d58eb1c6369", "d58eb1c63694x", "../../etc", 123):
            with self.subTest(session=session):
                self.assertDenied(self.parse, reply_request(session=session))

    def test_missing_or_empty_replies_are_denied(self):
        data = reply_request()
        del data["replies"]
        self.assertDenied(self.parse, data)
        self.assertDenied(self.parse, reply_request(replies=[]))

    def test_too_many_replies_are_denied(self):
        replies = [{"reply_to": "c_73f150", "body": "ok"}] * (wrapper.MAX_REPLIES + 1)
        self.assertDenied(self.parse, reply_request(replies=replies))

    def test_reply_to_a_review_level_comment_is_accepted(self):
        data = reply_request(replies=[{"reply_to": "r_b4c9e1", "body": "全体のコメントへの返信"}])
        self.assertEqual(self.parse(data), data)

    def test_malformed_reply_to_is_denied(self):
        for reply_to in ("rp_bc1969", "c_XYZXYZ", "c_123", "c_73f150 --resolve", 7):
            with self.subTest(reply_to=reply_to):
                self.assertDenied(self.parse, reply_request(replies=[{"reply_to": reply_to, "body": "ok"}]))

    def test_extra_reply_fields_are_denied(self):
        # 解決済みへの変更、author の指定、新しいコメントの追加はできない。
        for extra in ({"resolve": True}, {"author": "kado-ta"}, {"file": "docs/plan.md", "line": 1}):
            with self.subTest(extra=extra):
                reply = {"reply_to": "c_73f150", "body": "ok", **extra}
                self.assertDenied(self.parse, reply_request(replies=[reply]))

    def test_body_with_control_characters_is_denied(self):
        for body in ("\x1b[31mred", "carriage\rreturn", "nul\0byte"):
            with self.subTest(body=body):
                self.assertDenied(self.parse, reply_request(replies=[{"reply_to": "c_73f150", "body": body}]))

    def test_empty_or_oversized_body_is_denied(self):
        for body in ("", "x" * (wrapper.MAX_BODY + 1), None):
            with self.subTest(length=None if body is None else len(body)):
                self.assertDenied(self.parse, reply_request(replies=[{"reply_to": "c_73f150", "body": body}]))

    def test_review_fields_are_denied_for_reply(self):
        self.assertDenied(self.parse, {"files": []})


class ParseEncodingTests(Base):
    def test_duplicate_keys_are_denied(self):
        self.assertDenied(wrapper.parse_request, b'{"files": [], "files": ["docs/plan.md"]}', "review")

    def test_byte_order_mark_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'\xef\xbb\xbf{"files": []}', "review")

    def test_invalid_utf8_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'{"files": ["\xff.md"]}', "review")

    def test_non_object_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'["docs/plan.md"]', "review")

    def test_non_finite_number_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'{"files": NaN}', "review")


class ToplevelTests(Base):
    def test_repository_root(self):
        self.assertEqual(wrapper.find_toplevel(self.repo), self.repo)

    def test_from_a_subdirectory(self):
        self.assertEqual(wrapper.find_toplevel(self.repo / "docs"), self.repo)

    def test_worktree_with_a_git_file(self):
        worktree = self.root / "worktree"
        (worktree / "sub").mkdir(parents=True)
        (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8")
        self.assertEqual(wrapper.find_toplevel(worktree / "sub"), worktree)

    def test_outside_a_repository_is_denied(self):
        self.assertDenied(wrapper.find_toplevel, self.root)


class ResolveFilesTests(Base):
    def resolve(self, files, cwd=None):
        return wrapper.resolve_files(files, cwd or self.repo, self.repo)

    def test_relative_path_becomes_absolute(self):
        self.assertEqual(self.resolve(["docs/plan.md"]), [str(self.repo / "docs" / "plan.md")])

    def test_relative_to_a_subdirectory(self):
        self.assertEqual(self.resolve(["plan.md"], cwd=self.repo / "docs"), [str(self.repo / "docs" / "plan.md")])

    def test_symlink_inside_the_repository_resolves_to_the_target(self):
        os.symlink(self.repo / "docs" / "plan.md", self.repo / "link.md")
        self.assertEqual(self.resolve(["link.md"]), [str(self.repo / "docs" / "plan.md")])

    def test_option_like_name_is_denied(self):
        for name in ("-o", "--pr", "-"):
            with self.subTest(name=name):
                self.assertDenied(self.resolve, [name])

    def test_path_outside_the_repository_is_denied(self):
        for name in ("../outside.md", str(self.root / "outside.md")):
            with self.subTest(name=name):
                self.assertDenied(self.resolve, [name])

    def test_symlink_pointing_outside_is_denied(self):
        os.symlink(self.root / "outside.md", self.repo / "escape.md")
        self.assertDenied(self.resolve, ["escape.md"])

    def test_directory_is_denied(self):
        self.assertDenied(self.resolve, ["docs"])

    def test_missing_file_is_denied(self):
        self.assertDenied(self.resolve, ["missing.md"])

    def test_file_inside_dot_git_is_denied(self):
        (self.repo / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        self.assertDenied(self.resolve, [".git/config"])

    def test_fifo_is_denied(self):
        os.mkfifo(self.repo / "pipe")
        self.assertDenied(self.resolve, ["pipe"])


COVERED = ["~/.ssh/id_*", "~/.ssh/config", "~/.aws/credentials", "~/dotfiles/aws/credentials", "~/Library/Keychains",
           "~/.colima/_lima/_config", "~/.lima/_config"]

# 偽物は python の実体で動かす。/usr/bin/python3 は xcrun の中継役で、SDKROOT などを環境変数に足すため。
PYTHON = os.path.realpath(sys.executable)

# sandbox-exec の偽物。受け取った引数と環境変数を記録し、-f / -D を飛ばして残りを実行する（sandbox はかけない）。
FAKE_SANDBOX = """\
#!{python} -I
import json, os, sys
args = sys.argv[1:]
with open({calls!r}, "a") as f:
    f.write(json.dumps({{"tool": "sandbox-exec", "argv": args, "env": dict(os.environ), "cwd": os.getcwd()}}) + "\\n")
i = 0
while i < len(args) and args[i] in ("-f", "-D"):
    i += 2
os.execv(args[i], args[i:])
"""

# crit の偽物。mode ファイルの内容で振る舞いを変える。
FAKE_CRIT = """\
#!{python} -I
import fcntl, json, os, signal, sys, time
from pathlib import Path
root = Path({root!r})
args = sys.argv[1:]
record = {{"tool": "crit", "argv": args, "env": dict(os.environ), "cwd": os.getcwd(), "pid": os.getpid()}}
if args[:1] == ["comment"]:
    record["stdin"] = sys.stdin.read()
with open(root / "calls.jsonl", "a") as f:
    f.write(json.dumps(record) + "\\n")

def lockcheck(name):
    # cc-crit の起動のロック（専用 HOME の 1 つ上の lock）を、3 秒まで取れるか試す。
    fd = os.open(str(Path(os.environ["HOME"]).parent / "lock"), os.O_RDWR | os.O_CREAT, 0o600)
    result = "held"
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            result = "acquired"
            break
        except BlockingIOError:
            time.sleep(0.05)
    os.close(fd)
    (root / name).write_text(result)

if args[:1] == ["comment"]:
    lockcheck("lockcheck-comment")
    print("Replied to the comments", flush=True)
    sys.exit(0)
mode = (root / "mode").read_text().strip()
if mode == "fail":
    print("Error: listen tcp 127.0.0.1: bind: address already in use", flush=True)
    sys.exit(1)
if mode == "hang":
    def on_term(signum, frame):
        (root / "terminated").write_text("1")
        sys.exit(0)
    signal.signal(signal.SIGTERM, on_term)
    print("waiting", flush=True)
    time.sleep(30)
    sys.exit(0)
port = int(args[args.index("-p") + 1])
sessions = Path(os.environ["HOME"]) / ".crit" / "sessions"
sessions.mkdir(parents=True, exist_ok=True)
(sessions / "abcdefabcdef.json").write_text(json.dumps({{"pid": os.getpid(), "port": port, "host": "127.0.0.1"}}))
if mode in ("started", "lockcheck"):
    print(f"Started crit daemon at http://localhost:{{port}} (session abcdefabcdef, PID {{os.getpid()}})", flush=True)
    if mode == "lockcheck":
        lockcheck("lockcheck")
else:
    print(f"Connected to crit daemon at http://localhost:{{port}} (session abcdefabcdef)", flush=True)
print("approved: true", flush=True)
"""

FAKE_OPEN = """\
#!{python} -I
import json, sys
with open({calls!r}, "a") as f:
    f.write(json.dumps({{"tool": "open", "argv": sys.argv[1:]}}) + "\\n")
"""


def can_listen():
    try:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
        return True
    except PermissionError:
        return False


# Claude Code の sandbox の中では localhost でも待ち受けられない。
CAN_LISTEN = can_listen()


def free_ports(count):
    if not CAN_LISTEN:
        # 待ち受けできない環境では、どこにもつながらない固定の番号を使う。
        return list(range(47950, 47950 + count))
    sockets = [socket.socket() for _ in range(count)]
    try:
        for s in sockets:
            s.bind(("127.0.0.1", 0))
        return [s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets:
            s.close()


class RunBase(Base):
    def setUp(self):
        super().setUp()
        self.home = self.root / "home"
        self.home.mkdir()
        self.crit_home = self.home / ".cc-crit" / "crit-home"
        self.calls = self.root / "calls.jsonl"
        fake = self.root / "fake"
        fake.mkdir()
        self.fake_sandbox = self.write_script(fake / "sandbox-exec",
                                              FAKE_SANDBOX.format(python=PYTHON, calls=str(self.calls)))
        self.fake_crit = self.write_script(fake / "crit", FAKE_CRIT.format(python=PYTHON, root=str(self.root)))
        self.fake_open = self.write_script(fake / "open", FAKE_OPEN.format(python=PYTHON, calls=str(self.calls)))
        self.profile = fake / "cc-crit.sb"
        self.profile.write_text("(version 1)\n", encoding="utf-8")
        self.set_mode("started")
        self.ports = free_ports(3)
        self.browser_clients = False
        self.healthy = True
        self.alive = None  # None なら、どの PID も生きているとみなす
        for name, value in (
            ("SANDBOX_EXEC", str(self.fake_sandbox)),
            ("CRIT", str(self.fake_crit)),
            ("OPEN", str(self.fake_open)),
            ("PROFILE", self.profile),
            ("PORTS", self.ports),
            ("real_home", lambda: self.home),
            ("crit_health", self.health),
            ("pid_alive", lambda pid: self.alive is None or pid in self.alive),
        ):
            patcher = mock.patch.object(wrapper, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_script(self, path, text):
        path.write_text(text, encoding="utf-8")
        os.chmod(path, 0o755)
        return path

    def set_mode(self, mode):
        (self.root / "mode").write_text(mode, encoding="utf-8")

    def health(self, port):
        return {"status": "ok", "browser_clients": self.browser_clients} if self.healthy else None

    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["cc-crit", *args]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = wrapper.main()
        self.stdout, self.stderr = out.getvalue(), err.getvalue()
        return code

    def recorded(self, tool):
        if not self.calls.exists():
            return []
        lines = self.calls.read_text(encoding="utf-8").splitlines()
        return [c for c in map(json.loads, lines) if c["tool"] == tool]

    def review(self, files=("docs/plan.md",)):
        self.write_request({"files": list(files)})
        return self.main("review")


class ReviewTests(RunBase):
    def test_crit_runs_in_the_profile_with_fixed_arguments(self):
        self.assertEqual(self.review(), 0, self.stderr)
        [call] = self.recorded("sandbox-exec")
        crit_dir = self.crit_home / ".crit"
        port = self.ports[0]
        self.assertEqual(call["argv"], [
            "-f", str(self.profile),
            "-D", f"HOME_REAL={self.home}",
            "-D", f"CRIT_HOME={self.crit_home}",
            "-D", f"PRIVATE_TMP={self.home / '.cc-crit' / 'tmp'}",
            str(self.fake_crit), "--no-open", "-p", str(port), "-o", str(crit_dir),
            str(self.repo / "docs" / "plan.md"),
        ])
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertIn("approved: true", self.stdout)

    def test_runs_from_the_toplevel_when_called_in_a_subdirectory(self):
        os.chdir(self.repo / "docs")
        self.assertEqual(self.review(["plan.md"]), 0, self.stderr)
        [call] = self.recorded("sandbox-exec")
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertEqual(call["argv"][-1], str(self.repo / "docs" / "plan.md"))

    def test_no_files_means_the_branch_diff(self):
        self.assertEqual(self.review([]), 0, self.stderr)
        [call] = self.recorded("crit")
        self.assertEqual(call["argv"][-2:], ["-o", str(self.crit_home / ".crit")])

    def test_environment_is_an_allowlist(self):
        leaked = {"GH_TOKEN": "x", "GITHUB_TOKEN": "x", "CRIT_HOST": "0.0.0.0", "CRIT_PUBLIC_URL": "http://x",
                  "GIT_DIR": "/tmp/x", "SSH_AUTH_SOCK": "/tmp/agent", "OPENAI_API_KEY": "x"}
        with mock.patch.dict(os.environ, leaked):
            self.assertEqual(self.review(), 0, self.stderr)
        [call] = self.recorded("sandbox-exec")
        env = call["env"]
        for name in leaked:
            self.assertNotIn(name, env)
        self.assertEqual(env["HOME"], str(self.crit_home))
        self.assertEqual(env["TMPDIR"], f"{self.home / '.cc-crit' / 'tmp'}/")
        self.assertEqual(env["PATH"], "/opt/homebrew/bin:/usr/bin:/bin")
        for name, value in (("GIT_CONFIG_GLOBAL", "/dev/null"), ("GIT_CONFIG_NOSYSTEM", "1"),
                            ("GIT_CONFIG_COUNT", "2"),
                            ("GIT_CONFIG_KEY_0", "core.fsmonitor"), ("GIT_CONFIG_VALUE_0", "false"),
                            ("GIT_CONFIG_KEY_1", "core.hooksPath"), ("GIT_CONFIG_VALUE_1", "/dev/null"),
                            ("CRIT_NO_UPDATE_CHECK", "1"), ("CRIT_NO_INTEGRATION_CHECK", "1")):
            self.assertEqual(env.get(name), value, name)
        allowed = {"HOME", "USER", "LOGNAME", "PATH", "LANG", "TMPDIR", "CRIT_NO_UPDATE_CHECK",
                   "CRIT_NO_INTEGRATION_CHECK", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_COUNT",
                   "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "GIT_CONFIG_KEY_1", "GIT_CONFIG_VALUE_1",
                   "__CF_USER_TEXT_ENCODING"}
        self.assertEqual(set(env) - allowed, set())

    def test_config_pins_the_host_and_ignores_project_hooks(self):
        self.assertEqual(self.review(), 0, self.stderr)
        config = json.loads((self.crit_home / ".crit.config.json").read_text(encoding="utf-8"))
        key = "sha256:" + hashlib.sha256(str(self.repo).encode("utf-8")).hexdigest()
        self.assertEqual(wrapper.repo_root_hash(self.repo), key)
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertTrue(config["no_update_check"])
        self.assertTrue(config["no_integration_check"])
        self.assertEqual(config["trusted_project_prompts"], {key: {"mode": "defaults"}})

    def config(self):
        return json.loads((self.crit_home / ".crit.config.json").read_text(encoding="utf-8"))

    def make_home(self):
        (self.crit_home / ".crit").mkdir(parents=True)
        (self.home / ".cc-crit" / "tmp").mkdir()

    def test_trust_of_other_repositories_is_kept(self):
        other = self.root / "other"
        (other / ".git").mkdir(parents=True)
        (other / "notes.md").write_text("notes\n", encoding="utf-8")
        self.assertEqual(self.review(), 0, self.stderr)
        os.chdir(other)
        self.assertEqual(self.review(["notes.md"]), 0, self.stderr)
        self.assertEqual(self.config()["trusted_project_prompts"], {
            wrapper.repo_root_hash(self.repo): {"mode": "defaults"},
            wrapper.repo_root_hash(other): {"mode": "defaults"},
        })

    def test_only_fixed_keys_and_defaults_trust_survive(self):
        self.make_home()
        (self.crit_home / ".crit.config.json").write_text(json.dumps({
            "agent_cmd": "touch /tmp/pwned",
            "open_cmd": "/tmp/evil",
            "trusted_project_prompts": {"sha256:always": {"mode": "always"},
                                        "sha256:kept": {"mode": "defaults"}},
        }), encoding="utf-8")
        self.assertEqual(self.review(), 0, self.stderr)
        config = self.config()
        self.assertNotIn("agent_cmd", config)
        self.assertNotIn("open_cmd", config)
        self.assertEqual(config["trusted_project_prompts"], {
            "sha256:kept": {"mode": "defaults"},
            wrapper.repo_root_hash(self.repo): {"mode": "defaults"},
        })

    def test_hard_linked_config_is_denied(self):
        self.make_home()
        victim = self.root / "victim"
        victim.write_text("keep", encoding="utf-8")
        os.link(victim, self.crit_home / ".crit.config.json")
        self.assertEqual(self.review(), 2)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")
        self.assertEqual(self.recorded("crit"), [])

    def test_config_is_replaced_not_rewritten_in_place(self):
        # 書き換えの途中を crit に読ませないように、一時ファイルを rename で置き換える。
        self.make_home()
        path = self.crit_home / ".crit.config.json"
        path.write_text("{}", encoding="utf-8")
        before = os.stat(path).st_ino
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertNotEqual(os.stat(path).st_ino, before)
        self.assertEqual([p.name for p in self.crit_home.iterdir() if p.name.startswith(".crit.config.json.")], [])

    def test_broken_config_is_rewritten(self):
        self.make_home()
        (self.crit_home / ".crit.config.json").write_text("{", encoding="utf-8")
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual(self.config()["host"], "127.0.0.1")

    def test_config_symlink_is_denied(self):
        victim = self.root / "victim"
        victim.write_text("keep", encoding="utf-8")
        (self.crit_home / ".crit").mkdir(parents=True)
        (self.home / ".cc-crit" / "tmp").mkdir()
        os.symlink(victim, self.crit_home / ".crit.config.json")
        self.assertEqual(self.review(), 2)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")
        self.assertEqual(self.recorded("crit"), [])

    def test_symlinked_private_home_is_denied(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.home / ".cc-crit")
        self.assertEqual(self.review(), 2)
        self.assertEqual(self.recorded("crit"), [])
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_unwritable_home_fails_with_a_hint(self):
        os.chmod(self.home, 0o500)
        self.addCleanup(os.chmod, self.home, 0o700)
        self.assertEqual(self.review(), 1)
        self.assertIn("run cc-crit alone", self.stderr)
        self.assertEqual(self.recorded("crit"), [])


class BrowserTests(RunBase):
    def opened(self):
        return [c["argv"] for c in self.recorded("open")]

    def test_opens_the_browser_after_a_new_daemon_starts(self):
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual(self.opened(), [[f"http://127.0.0.1:{self.ports[0]}/"]])

    def test_does_not_open_when_the_endpoint_does_not_answer(self):
        self.healthy = False
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual(self.opened(), [])

    def test_does_not_open_when_the_daemon_pid_is_not_alive(self):
        self.alive = set()
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual(self.opened(), [])

    def test_reconnect_with_a_browser_already_open_does_not_open_again(self):
        self.set_mode("connected")
        self.browser_clients = True
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual(self.opened(), [])

    def test_reconnect_without_a_browser_opens_it(self):
        self.set_mode("connected")
        self.browser_clients = False
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual(self.opened(), [[f"http://127.0.0.1:{self.ports[0]}/"]])


class PortTests(RunBase):
    def setUp(self):
        super().setUp()
        # sandbox の中でも動くように、待ち受けているポートは差し替えで指定する。
        self.listening = set()
        patcher = mock.patch.object(wrapper, "port_listening", lambda port: port in self.listening)
        patcher.start()
        self.addCleanup(patcher.stop)

    def listen(self, port):
        self.listening.add(port)

    def register(self, port, pid, name=None):
        sessions = self.crit_home / ".crit" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / f"{name or f'k{port}'}.json").write_text(json.dumps({"pid": pid, "port": port, "host": "127.0.0.1"}))

    def test_stale_entry_for_the_same_port_does_not_hide_the_live_daemon(self):
        # 異常終了した daemon の session が残り、同じポートを新しい daemon が使っている。
        # 古い方のファイル名が後に並んでも、生きている daemon を crit とみなす。
        self.listen(self.ports[0])
        self.register(self.ports[0], os.getpid(), name="aa-live")
        self.register(self.ports[0], 999999, name="zz-stale")
        self.alive = {os.getpid()}
        self.assertEqual(self.review(), 0, self.stderr)
        [call] = self.recorded("crit")
        self.assertEqual(call["argv"][call["argv"].index("-p") + 1], str(self.ports[1]))

    def test_foreign_listener_in_the_range_is_denied(self):
        self.listen(self.ports[0])
        self.assertEqual(self.review(), 2)
        self.assertIn(str(self.ports[0]), self.stderr)
        self.assertEqual(self.recorded("crit"), [])

    def test_known_daemon_is_skipped_and_the_next_free_port_is_used(self):
        self.listen(self.ports[0])
        self.register(self.ports[0], os.getpid())
        self.assertEqual(self.review(), 0, self.stderr)
        [call] = self.recorded("crit")
        self.assertEqual(call["argv"][call["argv"].index("-p") + 1], str(self.ports[1]))

    def test_stale_session_with_a_dead_pid_does_not_cover_a_foreign_listener(self):
        self.listen(self.ports[0])
        self.register(self.ports[0], 999999)
        self.alive = {os.getpid()}
        self.assertEqual(self.review(), 2)
        self.assertEqual(self.recorded("crit"), [])

    def take_every_port(self):
        for port in self.ports:
            self.listen(port)
            self.register(port, os.getpid())

    def test_no_free_port_still_reconnects(self):
        # 同じ session の daemon が生きていれば、crit は -p を使わずにつなぐ。
        self.take_every_port()
        self.set_mode("connected")
        self.assertEqual(self.review(), 0, self.stderr)
        [call] = self.recorded("crit")
        self.assertEqual(call["argv"][call["argv"].index("-p") + 1], str(self.ports[0]))

    def test_no_free_port_without_a_session_explains(self):
        self.take_every_port()
        self.set_mode("fail")
        self.assertEqual(self.review(), 1)
        self.assertIn("no free port is left", self.stderr)
        # 利用者の HOME の crit stop は、専用 HOME の daemon に届かない。
        self.assertNotIn("crit stop", self.stderr)


class LockTests(RunBase):
    """同時に動く cc-crit が、信頼の設定とポートを取り合わないこと（PR #15 の Codex の指摘 1・2）。"""

    def lock_path(self):
        base = self.home / ".cc-crit"
        base.mkdir(parents=True, exist_ok=True)
        return base / "lock"

    def hold_lock(self):
        fd = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def assert_lock_free(self):
        fd = os.open(self.lock_path(), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)

    def test_config_write_waits_for_the_lock(self):
        self.hold_lock()
        with mock.patch.object(wrapper, "LOCK_TIMEOUT", 0.3, create=True):
            self.assertEqual(self.review(), 1)
        self.assertIn("another cc-crit is starting", self.stderr)
        self.assertEqual(self.recorded("crit"), [])
        self.assertFalse((self.crit_home / ".crit.config.json").exists())

    def test_lock_is_released_after_the_daemon_starts(self):
        # daemon が動いている間は持ち続けない。crit にロックの fd を引き継がないことも、これで確かめる。
        self.set_mode("lockcheck")
        self.assertEqual(self.review(), 0, self.stderr)
        self.assertEqual((self.root / "lockcheck").read_text(), "acquired")

    def test_lock_is_released_when_crit_exits_without_starting(self):
        self.set_mode("fail")
        self.assertEqual(self.review(), 1)
        self.assert_lock_free()

    def test_reply_releases_the_lock_before_running_crit(self):
        self.write_request(reply_request())
        self.assertEqual(self.main("reply"), 0, self.stderr)
        self.assertEqual((self.root / "lockcheck-comment").read_text(), "acquired")


class ReplyTests(RunBase):
    def test_sends_only_reply_to_and_body_with_a_fixed_author(self):
        self.write_request(reply_request())
        self.assertEqual(self.main("reply"), 0, self.stderr)
        [call] = self.recorded("crit")
        self.assertEqual(call["argv"], ["comment", "--session", SESSION, "--json", "--author", "Claude Code"])
        self.assertEqual(json.loads(call["stdin"]), reply_request()["replies"])
        self.assertEqual(call["cwd"], str(self.repo))
        self.assertEqual(self.recorded("open"), [])

    def test_reply_runs_in_the_profile(self):
        self.write_request(reply_request())
        self.assertEqual(self.main("reply"), 0, self.stderr)
        [call] = self.recorded("sandbox-exec")
        self.assertEqual(call["argv"][:2], ["-f", str(self.profile)])


class DenyReadTests(RunBase):
    def settings(self, path, deny_read):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sandbox": {"filesystem": {"denyRead": deny_read}}}), encoding="utf-8")

    def test_covered_entries_pass(self):
        self.settings(self.home / ".claude" / "settings.json", COVERED)
        self.assertEqual(self.review(), 0, self.stderr)

    def test_own_private_home_entry_passes(self):
        # ~/.cc-crit は Claude の sandbox から読ませないための項目で、crit 自身は読む。
        self.settings(self.home / ".claude" / "settings.json", COVERED + ["~/.cc-crit"])
        self.assertEqual(self.review(), 0, self.stderr)

    def test_uncovered_project_entry_is_denied(self):
        self.settings(self.repo / ".claude" / "settings.json", ["~/.netrc"])
        self.assertEqual(self.review(), 2)
        self.assertIn("~/.netrc", self.stderr)
        self.assertEqual(self.recorded("crit"), [])

    def test_uncovered_local_entry_is_denied(self):
        self.settings(self.repo / ".claude" / "settings.local.json", ["~/.config/gh"])
        self.assertEqual(self.review(), 2)

    def test_fifo_settings_are_denied(self):
        # 入れ子のリポジトリなどに FIFO を置かれても、読み込みで止まらないこと。
        path = self.repo / ".claude" / "settings.local.json"
        path.parent.mkdir()
        os.mkfifo(path)
        result = {}

        def check():
            try:
                wrapper.check_deny_read(self.home, self.repo)
            except wrapper.Denied as e:
                result["reason"] = e.reason

        thread = threading.Thread(target=check, daemon=True)
        thread.start()
        thread.join(5)
        if thread.is_alive():
            # 止まっているスレッドを、書き込み側を開いて解放する。
            os.close(os.open(path, os.O_WRONLY | os.O_NONBLOCK))
            thread.join(5)
            self.fail("check_deny_read blocked on a FIFO")
        self.assertIn("cannot read the sandbox settings", result.get("reason", ""))

    def test_broken_settings_are_denied(self):
        path = self.repo / ".claude" / "settings.local.json"
        path.parent.mkdir()
        path.write_text("{", encoding="utf-8")
        self.assertEqual(self.review(), 2)
        self.assertEqual(self.recorded("crit"), [])

    def test_covered_list_matches_the_profile(self):
        profile = (BIN / "cc-crit.sb").read_text(encoding="utf-8")
        marked = {line.split("; denyRead: ", 1)[1].strip()
                  for line in profile.splitlines() if line.startswith("; denyRead: ")}
        self.assertEqual(marked, set(wrapper.COVERED_DENY_READ))
        self.assertEqual(marked, set(COVERED))

    def test_repository_settings_are_covered(self):
        # claude/settings.json の denyRead を足したら、cc-crit.sb と COVERED_DENY_READ も一緒に変える。
        # 変えないと、インストール済みの cc-crit が拒否する。
        settings = json.loads((BIN.parent / "settings.json").read_text(encoding="utf-8"))
        deny_read = set(settings["sandbox"]["filesystem"]["denyRead"])
        self.assertEqual(deny_read - wrapper.COVERED_DENY_READ - wrapper.OWN_DENY_READ, set())


class MainTests(RunBase):
    def test_wrong_arguments_are_denied(self):
        for args in ((), ("review", "x"), ("create",), ("--help",)):
            with self.subTest(args=args):
                self.assertEqual(self.main(*args), 2)
        self.assertEqual(self.recorded("crit"), [])

    def test_missing_request_is_denied(self):
        self.assertEqual(self.main("review"), 2)
        self.assertEqual(self.recorded("crit"), [])

    def test_missing_tools_fail_closed(self):
        for name in ("SANDBOX_EXEC", "CRIT", "PROFILE"):
            with self.subTest(name=name), mock.patch.object(wrapper, name, str(self.root / "missing")):
                self.write_request({"files": []})
                self.assertEqual(self.main("review"), 2)
                with contextlib.suppress(FileNotFoundError):
                    Path(REQUEST).unlink()
        self.assertEqual(self.recorded("crit"), [])
        self.assertEqual(self.recorded("sandbox-exec"), [])


class SigtermTests(RunBase):
    def test_sigterm_stops_crit_and_does_not_open_the_browser(self):
        self.set_mode("hang")
        self.write_request({"files": ["docs/plan.md"]})
        launcher = textwrap.dedent(f"""\
            import importlib.machinery, importlib.util, sys
            from pathlib import Path
            loader = importlib.machinery.SourceFileLoader("cc_crit", {str(BIN / "cc-crit")!r})
            spec = importlib.util.spec_from_loader(loader.name, loader)
            m = importlib.util.module_from_spec(spec)
            loader.exec_module(m)
            m.SANDBOX_EXEC = {str(self.fake_sandbox)!r}
            m.CRIT = {str(self.fake_crit)!r}
            m.OPEN = {str(self.fake_open)!r}
            m.PROFILE = Path({str(self.profile)!r})
            m.PORTS = {self.ports!r}
            m.real_home = lambda: Path({str(self.home)!r})
            m.crit_health = lambda port: {{"status": "ok", "browser_clients": False}}
            sys.argv = ["cc-crit", "review"]
            sys.exit(m.main())
        """)
        proc = subprocess.Popen([sys.executable, "-I", "-c", launcher], cwd=self.repo,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "waiting")
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close()
        self.assertNotEqual(proc.returncode, 0)
        deadline = time.monotonic() + 5
        while not (self.root / "terminated").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue((self.root / "terminated").exists())
        self.assertEqual(self.recorded("open"), [])


CLT = "/Library/Developer/CommandLineTools/usr/bin"


class InterpreterTests(unittest.TestCase):
    """xcrun の shim と呼び出し元の環境変数に、実行されるプログラムを左右させない。"""

    def test_shebang_clears_env_and_skips_xcrun(self):
        first = (BIN / "cc-crit").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, f"#!/usr/bin/env -i {CLT}/python3 -I")

    def test_ignores_caller_developer_dir(self):
        with tempfile.TemporaryDirectory(prefix="claude-crit-") as tmp:
            copy = Path(tmp) / "cc-crit"
            copy.write_bytes((BIN / "cc-crit").read_bytes())
            copy.chmod(0o755)
            cp = subprocess.run([str(copy), "bogus"], capture_output=True, text=True, cwd=tmp,
                                env={"DEVELOPER_DIR": "/nonexistent", "PATH": "/usr/bin:/bin"})
        self.assertNotIn("xcrun", cp.stderr)
        self.assertEqual(cp.returncode, wrapper.EXIT_DENIED)
        self.assertIn("DENIED: exactly one argument is allowed: review or reply", cp.stderr)

    def test_empty_environment_prints_utf8(self):
        # env -i で起動するとロケールの環境変数がない。crit の出力（日本語のコメント）をそのまま中継できること。
        cp = subprocess.run(["/usr/bin/env", "-i", f"{CLT}/python3", "-I", "-c", "print('日本語')"],
                            capture_output=True)
        self.assertEqual(cp.stdout, "日本語\n".encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
