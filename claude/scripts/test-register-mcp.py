"""register-mcp.sh の単体テスト。

偽のリポジトリ（スクリプトの写しと MCP の定義）、偽の HOME、偽の Node.js（npm の偽物）、claude・mise の偽物を
置いた PATH で、スクリプトを /bin/bash のサブプロセスとして実行し、呼ばれたコマンドの引数・順番・終了コードを確かめる。
claude/mcp/ の実際の定義が、版を固定していることなども確かめる。

実行: /usr/bin/python3 -B claude/scripts/test-register-mcp.py
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
MCP_DIR = SCRIPTS.parent / "mcp"

# 引数を 1 行の JSON 配列で記録する。STUB_REMOVE_RC・STUB_ADD_RC で終了コードを変える。
CLAUDE_STUB = '''#!/usr/bin/python3 -I
import json, os, sys
args = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps(["claude"] + args) + "\\n")
if args[:2] == ["mcp", "remove"]:
    sys.exit(int(os.environ.get("STUB_REMOVE_RC", "0")))
if args[:2] == ["mcp", "add-json"]:
    sys.exit(int(os.environ.get("STUB_ADD_RC", "0")))
'''

# ホームから実行されたかを確かめるため、実行時のディレクトリも書く。
MISE_STUB = '''#!/bin/sh
printf '["mise", "%s", "%s"]\\n' "$*" "$(pwd -P)" >> "$STUB_LOG"
[ "${STUB_MISE_RC:-0}" = 0 ] || exit "$STUB_MISE_RC"
printf '%s\\n' "$STUB_NODE_DIR"
'''

# 実行時のディレクトリと PATH と引数を記録する。STUB_NPM_RC で終了コードを変える。
NPM_STUB = '''#!/usr/bin/python3 -I
import json, os, sys
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps(["npm", os.getcwd(), os.environ.get("PATH", "")] + sys.argv[1:]) + "\\n")
sys.exit(int(os.environ.get("STUB_NPM_RC", "0")))
'''

DEFINITION = {
    "npmPackage": "pkg@1.2.3",
    "type": "stdio",
    "command": "${NODE_BIN}/node",
    "args": ["${PACKAGE_DIR}/node_modules/pkg/cli.js", "--output-dir", "${HOME}/Library/Caches/x"],
    "env": {
        "PATH": "${NODE_BIN}:/usr/bin:/bin",
        "HEADLESS": "${HEADLESS:-true}",
    },
}


def write_executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


class RegisterMcpTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.stub = self.root / "stub"
        self.node = self.root / "node"
        self.log = self.root / "log"
        script = self.repo / "claude" / "scripts" / "register-mcp.sh"
        script.parent.mkdir(parents=True)
        shutil.copy(SCRIPTS / "register-mcp.sh", script)
        self.mcp = self.repo / "claude" / "mcp"
        self.mcp.mkdir()
        self.write_definition("playwright", DEFINITION)
        self.home.mkdir()
        self.node_bin = self.node / "bin"
        write_executable(self.node_bin / "node", "#!/bin/sh\n")
        write_executable(self.node_bin / "npm", NPM_STUB)
        write_executable(self.stub / "claude", CLAUDE_STUB)
        write_executable(self.stub / "mise", MISE_STUB)
        self.package_dir = self.home / ".local" / "share" / "claude-mcp" / "playwright"

    def write_definition(self, name, data):
        text = data if isinstance(data, str) else json.dumps(data)
        (self.mcp / f"{name}.json").write_text(text, encoding="utf-8")

    def run_script(self, **rc):
        env = {
            "HOME": str(self.home),
            "PATH": f"{self.stub}:/usr/bin:/bin",
            "STUB_LOG": str(self.log),
            "STUB_NODE_DIR": str(self.node),
            "STUB_MISE_RC": str(rc.get("mise", 0)),
            "STUB_NPM_RC": str(rc.get("npm", 0)),
            "STUB_REMOVE_RC": str(rc.get("remove", 0)),
            "STUB_ADD_RC": str(rc.get("add", 0)),
        }
        return subprocess.run(
            ["/bin/bash", str(self.repo / "claude" / "scripts" / "register-mcp.sh")],
            cwd=self.root, env=env, capture_output=True, text=True,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def claude_calls(self):
        return [c[1:] for c in self.calls() if c[0] == "claude"]

    def npm_calls(self):
        return [c[1:] for c in self.calls() if c[0] == "npm"]

    def test_installs_then_removes_then_adds_to_user_scope(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[0] for c in self.calls()], ["mise", "npm", "claude", "claude"])
        calls = self.claude_calls()
        self.assertEqual(calls[0], ["mcp", "remove", "playwright", "-s", "user"])
        self.assertEqual(calls[1][:5], ["mcp", "add-json", "-s", "user", "playwright"])

    def test_installs_the_package_outside_the_project(self):
        # 実行時に npx を使うと、作業ディレクトリ（sandbox から書けるプロジェクト）の node_modules や .npmrc が使われる。
        self.run_script()
        [[cwd, path, *args]] = self.npm_calls()
        self.assertEqual(cwd, str(self.home))
        self.assertTrue(path.startswith(f"{self.node_bin}:"), path)
        self.assertEqual(args[0], "install")
        self.assertEqual(args[args.index("--prefix") + 1], str(self.package_dir))
        self.assertIn("--ignore-scripts", args)
        self.assertEqual(args[-1], "pkg@1.2.3")

    def test_replaces_placeholders_and_drops_the_package_key(self):
        self.run_script()
        registered = json.loads(self.claude_calls()[1][5])
        self.assertNotIn("npmPackage", registered)
        self.assertEqual(registered["command"], f"{self.node_bin}/node")
        self.assertEqual(registered["args"], [
            f"{self.package_dir}/node_modules/pkg/cli.js", "--output-dir", f"{self.home}/Library/Caches/x",
        ])
        self.assertEqual(registered["env"]["PATH"], f"{self.node_bin}:/usr/bin:/bin")
        # Claude Code が起動時に展開するので、そのまま残す。
        self.assertEqual(registered["env"]["HEADLESS"], "${HEADLESS:-true}")

    def test_definition_without_package_skips_install(self):
        data = dict(DEFINITION)
        del data["npmPackage"]
        self.write_definition("playwright", data)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.npm_calls(), [])
        self.assertEqual([c[1] for c in self.claude_calls()], ["remove", "add-json"])

    def test_asks_mise_from_home(self):
        self.run_script()
        mise = [c for c in self.calls() if c[0] == "mise"]
        self.assertEqual(mise, [["mise", "where node", str(self.home)]])

    def test_rerun_registers_the_same_way(self):
        first = self.run_script()
        second = self.run_script()
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        calls = self.calls()
        self.assertEqual(len(calls), 8)
        self.assertEqual(calls[:4], calls[4:])

    def test_missing_server_does_not_stop_add(self):
        result = self.run_script(remove=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[1] for c in self.claude_calls()], ["remove", "add-json"])

    def test_add_failure_fails(self):
        result = self.run_script(add=1)
        self.assertNotEqual(result.returncode, 0)

    def test_install_failure_registers_nothing(self):
        result = self.run_script(npm=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.claude_calls(), [])

    def test_mise_failure_registers_nothing(self):
        result = self.run_script(mise=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.claude_calls(), [])

    def test_missing_node_or_npm_registers_nothing(self):
        for tool in ("node", "npm"):
            with self.subTest(tool=tool):
                self.setUp()
                (self.node_bin / tool).unlink()
                result = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(tool, result.stderr)
                self.assertEqual(self.claude_calls(), [])

    def test_invalid_definition_is_not_added(self):
        self.write_definition("playwright", "{")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("add-json", [c[1] for c in self.claude_calls()])

    def test_no_definitions_succeeds(self):
        # README の削除の手順で定義を消しても、setup.sh が最後で止まらないようにする。
        (self.mcp / "playwright.json").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.claude_calls(), [])
        self.assertIn("No MCP definitions", result.stdout)

    def test_missing_mcp_directory_succeeds(self):
        # 最後の定義を消すと、Git は空のディレクトリを残さない。
        shutil.rmtree(self.mcp)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.claude_calls(), [])


class PlaywrightDefinitionTest(unittest.TestCase):
    """claude/mcp/playwright.json の判断（docs/work/20261118_playwright-mcp/plan.md）を固定する。"""

    def setUp(self):
        self.data = json.loads((MCP_DIR / "playwright.json").read_text(encoding="utf-8"))
        self.args = self.data["args"]

    def option(self, name):
        return self.args[self.args.index(name) + 1]

    def test_version_is_pinned(self):
        self.assertRegex(self.data["npmPackage"], r"^@playwright/mcp@\d+\.\d+\.\d+$")

    def test_runs_the_installed_package_with_node(self):
        # npx はプロジェクトの node_modules・.npmrc・node_modules/.bin を使うので、実行時には使わない。
        self.assertEqual(self.data["command"], "${NODE_BIN}/node")
        self.assertEqual(self.args[0], "${PACKAGE_DIR}/node_modules/@playwright/mcp/cli.js")
        self.assertNotIn("npx", json.dumps(self.data))

    def test_options(self):
        self.assertIn("--isolated", self.args)
        self.assertIn("--no-webmcp", self.args)
        self.assertEqual(self.option("--browser"), "chrome")
        self.assertEqual(self.option("--output-dir"), "${HOME}/Library/Caches/playwright-mcp")

    def test_blocks_crit_ports(self):
        # cc-crit の Crit は 47810〜47829 で待ち受ける（claude/bin/cc-crit の PORTS）。移す前の範囲の 47800〜47809 も止め、
        # 更新の順番によらず古い cc-crit の Crit を開かせない（docs/work/20261124_cc-crit-port-range/plan.md）。
        self.assertEqual(self.option("--blocked-origins").split(";"), [f"*:{p}" for p in range(47800, 47830)])

    def test_headless_is_switchable(self):
        # --headless を付けると、環境変数より優先されて切り替えられなくなる。
        self.assertNotIn("--headless", self.args)
        self.assertEqual(self.data["env"]["PLAYWRIGHT_MCP_HEADLESS"], "${PLAYWRIGHT_MCP_HEADLESS:-true}")

    def test_node_is_fixed(self):
        self.assertTrue(self.data["env"]["PATH"].startswith("${NODE_BIN}:"))

    def test_no_unknown_placeholder(self):
        known = {"${HOME}", "${NODE_BIN}", "${PACKAGE_DIR}", "${PLAYWRIGHT_MCP_HEADLESS:-true}"}
        text = json.dumps(self.data)
        self.assertEqual(set(re.findall(r"\$\{[^}]*\}", text)) - known, set())


if __name__ == "__main__":
    unittest.main()
