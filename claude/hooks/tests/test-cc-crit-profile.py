"""cc-crit.sb（Crit 専用の Seatbelt profile）が、必要なものだけを許可していることを確かめる。

Claude Code の sandbox の中では sandbox-exec を入れ子にできないので、その場合はスキップする。
人間が `!` で実行するか、CI（macOS）で実行する。crit か Homebrew の git がない環境でもスキップする。
"""
import errno
import json
import os
import platform
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# 変更前の profile と比べるときだけ、CC_CRIT_PROFILE で差し替える（テストのための指定で、ラッパーは読まない）。
PROFILE = Path(os.environ.get("CC_CRIT_PROFILE", ROOT / "claude" / "bin" / "cc-crit.sb"))
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
CRIT = "/opt/homebrew/bin/crit"
GIT = "/opt/homebrew/bin/git"
PORTS = range(47800, 47820)
OUT_OF_RANGE = 47900

# 探査の結果は標準出力の 1 行で返す。拒否は EPERM / EACCES だけを数え、それ以外のエラーは区別する。
PROBE = textwrap.dedent("""\
    import errno, os, socket, sys
    def attempt(fn):
        try:
            fn()
        except OSError as e:
            if e.errno in (errno.EPERM, errno.EACCES):
                print("DENIED", e.errno)
                sys.exit(3)
            print("ERROR", e.errno, e)
            sys.exit(4)
        print("ALLOWED")
        sys.exit(0)
""")


def free_port(ports):
    for port in ports:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise unittest.SkipTest("no free port in the range")


def lan_address():
    # UDP の connect はパケットを送らずに、外向きのインターフェースのアドレスを決める。
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))
            addr = s.getsockname()[0]
        except OSError:
            return None
    return None if addr.startswith("127.") else addr


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in (CRIT, GIT, SANDBOX_EXEC):
            if not os.path.exists(path):
                raise unittest.SkipTest(f"{path} is not installed")
        nested = subprocess.run([SANDBOX_EXEC, "-p", "(version 1)(allow default)", "/usr/bin/true"],
                                capture_output=True)
        if nested.returncode:
            raise unittest.SkipTest("sandbox-exec cannot apply a profile here (inside another sandbox);"
                                    " run this test outside Claude's sandbox")
        cls.root = Path(tempfile.mkdtemp(prefix="cc-crit-profile.")).resolve()
        cls.home_real = Path(os.path.expanduser("~")).resolve()
        cls.crit_home = cls.root / "crit-home"
        (cls.crit_home / ".crit").mkdir(parents=True)
        cls.config = cls.crit_home / ".crit.config.json"
        cls.config.write_text(json.dumps({"no_update_check": True, "no_integration_check": True}))
        cls.private_tmp = cls.root / "tmp"
        cls.private_tmp.mkdir()
        cls.repo = cls.root / "repo"
        cls.repo.mkdir()
        subprocess.run([GIT, "-C", str(cls.repo), "init", "-q"], check=True, env=cls.env())
        (cls.repo / "plan.md").write_text("# Probe\n\n- step\n")
        (cls.repo / ".env").write_text("SECRET=1\n")
        (cls.repo / "secret.pem").write_text("-----BEGIN-----\n")
        exe = sys.executable
        cls.test_profile = cls.root / "test.sb"
        # 本番の profile に、探査用の python の実行だけを足す。本番の profile は python を許さない。
        cls.test_profile.write_text(PROFILE.read_text() + textwrap.dedent(f"""
            (allow process-exec
              (literal "{exe}")
              (literal "{os.path.realpath(exe)}")
              (subpath "{os.path.realpath(sys.base_prefix)}"))
        """))
        cls.crit_port = None
        crit_version = subprocess.run([CRIT, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        git_version = subprocess.run([GIT, "--version"], capture_output=True, text=True).stdout.strip()
        print(f"\n{crit_version} / {git_version} / macOS {platform.mac_ver()[0]}", file=sys.stderr)

    @classmethod
    def tearDownClass(cls):
        if cls.crit_port is not None:
            cls.run_in_profile([CRIT, "stop", "--all"])
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def env(cls):
        return {
            "HOME": str(cls.crit_home) if hasattr(cls, "crit_home") else "/nonexistent",
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
            "TMPDIR": f"{getattr(cls, 'private_tmp', '/nonexistent')}/",
            "LANG": "en_US.UTF-8",
            "CRIT_NO_UPDATE_CHECK": "1",
            "CRIT_NO_INTEGRATION_CHECK": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        }

    @classmethod
    def sandbox_argv(cls, argv):
        return [SANDBOX_EXEC, "-f", str(cls.test_profile),
                "-D", f"HOME_REAL={cls.home_real}",
                "-D", f"CRIT_HOME={cls.crit_home}",
                "-D", f"PRIVATE_TMP={cls.private_tmp}",
                *argv]

    @classmethod
    def run_in_profile(cls, argv, timeout=30):
        return subprocess.run(cls.sandbox_argv(argv), cwd=cls.repo, env=cls.env(),
                              capture_output=True, text=True, timeout=timeout)

    def probe(self, statement):
        cp = self.run_in_profile([sys.executable, "-I", "-S", "-c", PROBE + statement])
        return cp.stdout.strip() + cp.stderr.strip()

    def assertAllowed(self, statement):
        out = self.probe(statement)
        self.assertTrue(out.startswith("ALLOWED"), out)

    def assertDenied(self, statement):
        out = self.probe(statement)
        self.assertTrue(out.startswith("DENIED"), out)

    # --- 動くべきもの ---

    def test_git_runs(self):
        cp = self.run_in_profile([GIT, "status", "--short"])
        self.assertEqual(cp.returncode, 0, cp.stderr)

    def test_crit_review_answers_health(self):
        port = free_port(PORTS)
        proc = subprocess.Popen(
            self.sandbox_argv([CRIT, "--no-open", "-p", str(port), "-o", str(self.crit_home / ".crit"), "plan.md"]),
            cwd=self.repo, env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        type(self).crit_port = port
        try:
            lines, deadline = [], time.monotonic() + 20
            while time.monotonic() < deadline:
                ready, _, _ = select.select([proc.stdout], [], [], 0.5)
                if ready:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    lines.append(line)
                    if f"http://localhost:{port}" in line:
                        break
            self.assertTrue(any(f"http://localhost:{port}" in l for l in lines), "".join(lines))
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as resp:
                self.assertEqual(json.load(resp).get("status"), "ok")
            # crit は 127.0.0.1 だけで待ち受けるので、LAN のアドレスからは届かない。
            addr = lan_address()
            if addr is not None:
                with self.assertRaises(ConnectionRefusedError):
                    socket.create_connection((addr, port), timeout=3).close()
        finally:
            proc.terminate()
            proc.wait(timeout=10)
            proc.stdout.close()

    def test_write_crit_dir_allowed(self):
        p = self.crit_home / ".crit" / "probe"
        self.assertAllowed(f"attempt(lambda: open({str(p)!r}, 'w').close())")

    def test_write_private_tmp_allowed(self):
        p = self.private_tmp / "probe"
        self.assertAllowed(f"attempt(lambda: open({str(p)!r}, 'w').close())")

    def test_read_repo_file_allowed(self):
        self.assertAllowed(f"attempt(lambda: open({str(self.repo / 'plan.md')!r}).read())")

    def test_bind_loopback_in_range_allowed(self):
        port = free_port(PORTS)
        self.assertAllowed(f"attempt(lambda: socket.socket().bind(('127.0.0.1', {port})))")

    # --- 拒否すべきもの: 書き込み ---

    def test_write_real_crit_denied(self):
        if not (self.home_real / ".crit").is_dir():
            self.skipTest("~/.crit does not exist")
        p = self.home_real / ".crit" / "cc-crit-profile-probe"
        self.assertDenied(f"attempt(lambda: (open({str(p)!r}, 'w').close(), os.remove({str(p)!r})))")

    def test_write_home_denied(self):
        p = self.home_real / "cc-crit-profile-probe"
        self.assertDenied(f"attempt(lambda: (open({str(p)!r}, 'w').close(), os.remove({str(p)!r})))")

    def test_write_config_denied(self):
        self.assertDenied(f"attempt(lambda: open({str(self.config)!r}, 'a').close())")

    def test_write_repo_denied(self):
        p = self.repo / "probe"
        self.assertDenied(f"attempt(lambda: (open({str(p)!r}, 'w').close(), os.remove({str(p)!r})))")

    # --- 拒否すべきもの: 読み取り ---

    def test_read_env_file_denied(self):
        self.assertDenied(f"attempt(lambda: open({str(self.repo / '.env')!r}).read())")

    def test_read_pem_file_denied(self):
        self.assertDenied(f"attempt(lambda: open({str(self.repo / 'secret.pem')!r}).read())")

    def test_read_ssh_config_denied(self):
        p = self.home_real / ".ssh" / "config"
        if not p.exists():
            self.skipTest("~/.ssh/config does not exist")
        self.assertDenied(f"attempt(lambda: open({str(p)!r}).read())")

    def test_read_claude_home_denied(self):
        # crit は使わない。会話の記録や IDE 連携の情報など、Claude の sandbox が読ませないものがある。
        p = self.home_real / ".claude"
        if not p.is_dir():
            self.skipTest("~/.claude does not exist")
        self.assertDenied(f"attempt(lambda: os.listdir({str(p)!r}))")

    def test_read_claude_edit_diff_cache_denied(self):
        p = Path(f"/private/tmp/claude-{os.getuid()}/bash-edit-diff")
        if not p.is_dir():
            self.skipTest(f"{p} does not exist")
        self.assertDenied(f"attempt(lambda: os.listdir({str(p)!r}))")

    def test_read_keychains_denied(self):
        p = self.home_real / "Library" / "Keychains"
        self.assertDenied(f"attempt(lambda: os.listdir({str(p)!r}))")

    # --- 拒否すべきもの: ネットワーク ---

    def test_external_connect_denied(self):
        self.assertDenied("attempt(lambda: socket.create_connection(('1.1.1.1', 443), timeout=5))")

    # Seatbelt の (local ip "localhost:N") はアドレスを区別しないので、範囲内のポートなら
    # 0.0.0.0、::、LAN のアドレスでも待ち受けられる【実測】。接続相手を条件にすると listen 自体が拒否される。
    # profile で制限できるのはポートだけなので、待ち受けのアドレスは crit の設定（127.0.0.1）で決める。
    # crit が LAN のアドレスから届かないことは test_crit_review_answers_health で確かめる。

    def test_bind_loopback_out_of_range_denied(self):
        self.assertDenied(f"attempt(lambda: socket.socket().bind(('127.0.0.1', {OUT_OF_RANGE})))")

    def test_bind_ipv6_loopback_out_of_range_denied(self):
        self.assertDenied(f"attempt(lambda: socket.socket(socket.AF_INET6).bind(('::1', {OUT_OF_RANGE})))")

    def test_connect_loopback_out_of_range_denied(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertNotIn(port, PORTS)
            self.assertDenied(f"attempt(lambda: socket.create_connection(('127.0.0.1', {port}), timeout=5))")

    # --- 拒否すべきもの: 実行 ---
    # /usr/bin/open は、許可されていると実際にブラウザが開くので試さない。任意の実行の拒否で代える。

    def test_exec_shell_denied(self):
        cp = self.run_in_profile(["/bin/sh", "-c", "exit 0"])
        self.assertNotEqual(cp.returncode, 0)

    def test_exec_osascript_denied(self):
        cp = self.run_in_profile(["/usr/bin/osascript", "-e", "return 1"])
        self.assertNotEqual(cp.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
