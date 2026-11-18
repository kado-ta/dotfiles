"""register-mcp.sh の単体テスト。

偽のリポジトリ（スクリプトの写しと MCP の定義）、偽の HOME、claude・mise の偽物を置いた PATH で、
スクリプトを /bin/bash のサブプロセスとして実行し、呼ばれたコマンドの引数・順番・終了コードを確かめる。
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

DEFINITION = {
    "type": "stdio",
    "command": "${NODE_BIN}/npx",
    "args": ["-y", "pkg@1.2.3", "--output-dir", "${HOME}/Library/Caches/x"],
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
        write_executable(self.node / "bin" / "npx", "#!/bin/sh\n")
        write_executable(self.stub / "claude", CLAUDE_STUB)
        write_executable(self.stub / "mise", MISE_STUB)

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

    def test_removes_then_adds_to_user_scope(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.claude_calls()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], ["mcp", "remove", "playwright", "-s", "user"])
        self.assertEqual(calls[1][:4], ["mcp", "add-json", "-s", "user"])
        self.assertEqual(calls[1][4], "playwright")

    def test_replaces_home_and_node_bin_only(self):
        self.run_script()
        registered = json.loads(self.claude_calls()[1][5])
        node_bin = f"{self.node}/bin"
        self.assertEqual(registered["command"], f"{node_bin}/npx")
        self.assertEqual(registered["args"], ["-y", "pkg@1.2.3", "--output-dir", f"{self.home}/Library/Caches/x"])
        self.assertEqual(registered["env"]["PATH"], f"{node_bin}:/usr/bin:/bin")
        # Claude Code が起動時に展開するので、そのまま残す。
        self.assertEqual(registered["env"]["HEADLESS"], "${HEADLESS:-true}")

    def test_asks_mise_from_home(self):
        self.run_script()
        mise = [c for c in self.calls() if c[0] == "mise"]
        self.assertEqual(mise, [["mise", "where node", str(self.home)]])

    def test_rerun_registers_the_same_way(self):
        first = self.run_script()
        second = self.run_script()
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        calls = self.claude_calls()
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[:2], calls[2:])

    def test_missing_server_does_not_stop_add(self):
        result = self.run_script(remove=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c[1] for c in self.claude_calls()], ["remove", "add-json"])

    def test_add_failure_fails(self):
        result = self.run_script(add=1)
        self.assertNotEqual(result.returncode, 0)

    def test_mise_failure_registers_nothing(self):
        result = self.run_script(mise=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.claude_calls(), [])

    def test_missing_npx_registers_nothing(self):
        (self.node / "bin" / "npx").unlink()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("npx", result.stderr)
        self.assertEqual(self.claude_calls(), [])

    def test_invalid_definition_is_not_added(self):
        self.write_definition("playwright", "{")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("add-json", [c[1] for c in self.claude_calls()])

    def test_no_definitions_fails(self):
        (self.mcp / "playwright.json").unlink()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.claude_calls(), [])


class PlaywrightDefinitionTest(unittest.TestCase):
    """claude/mcp/playwright.json の判断（docs/work/20261118_playwright-mcp/plan.md）を固定する。"""

    def setUp(self):
        self.data = json.loads((MCP_DIR / "playwright.json").read_text(encoding="utf-8"))
        self.args = self.data["args"]

    def test_version_is_pinned(self):
        packages = [a for a in self.args if a.startswith("@playwright/mcp@")]
        self.assertEqual(len(packages), 1)
        self.assertRegex(packages[0], r"^@playwright/mcp@\d+\.\d+\.\d+$")

    def test_options(self):
        self.assertIn("--isolated", self.args)
        self.assertEqual(self.args[self.args.index("--browser") + 1], "chrome")
        self.assertEqual(self.args[self.args.index("--output-dir") + 1], "${HOME}/Library/Caches/playwright-mcp")

    def test_headless_is_switchable(self):
        # --headless を付けると、環境変数より優先されて切り替えられなくなる。
        self.assertNotIn("--headless", self.args)
        self.assertEqual(self.data["env"]["PLAYWRIGHT_MCP_HEADLESS"], "${PLAYWRIGHT_MCP_HEADLESS:-true}")

    def test_node_is_fixed(self):
        self.assertEqual(self.data["command"], "${NODE_BIN}/npx")
        self.assertTrue(self.data["env"]["PATH"].startswith("${NODE_BIN}:"))

    def test_no_unknown_placeholder(self):
        known = {"${HOME}", "${NODE_BIN}", "${PLAYWRIGHT_MCP_HEADLESS:-true}"}
        text = json.dumps(self.data)
        self.assertEqual(set(re.findall(r"\$\{[^}]*\}", text)) - known, set())


if __name__ == "__main__":
    unittest.main()
