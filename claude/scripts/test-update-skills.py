"""update-skills.sh の単体テスト。

偽の HOME（gstack-upgrade の偽物と settings.json を置く）と、claude・brew・mise の偽物を置いた PATH で
スクリプトを /bin/bash のサブプロセスとして実行し、呼ばれたコマンドの順番・出力・終了コードを確かめる。

実行: python3 -B claude/scripts/test-update-skills.py
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "update-skills.sh"

PLUGINS = ('[{"id":"a@m","scope":"user"},{"id":"s@m","scope":"local"},'
           '{"id":"b@m","scope":"user"},{"id":"s@m","scope":"local"}]')

LOGGING_STUB = '#!/bin/sh\necho "{name} $*" >> "$STUB_LOG"\n'

CLAUDE_STUB = (
    '#!/bin/sh\n'
    'echo "claude $*" >> "$STUB_LOG"\n'
    'if [ "$1 $2" = "plugin list" ]; then\n'
    f"  printf '%s\\n' '{PLUGINS}'\n"
    'fi\n'
)

GSTACK_STUB = '#!/bin/sh\necho gstack-upgrade >> "$STUB_LOG"\nexit "${STUB_GSTACK_RC:-0}"\n'


def write_executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


class UpdateSkillsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.home = self.root / "home"
        self.stub = self.root / "stub"
        self.log = self.root / "log"
        self.settings = self.home / ".claude" / "settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(
            f'{{"hooks": {{"Stop": [{{"hooks": [{{"type": "command", '
            f'"command": "{self.home}/.claude/skills/gstack/bin/x"}}]}}]}}}}\n',
            encoding="utf-8",
        )
        write_executable(self.home / ".claude" / "skills" / "gstack" / "bin" / "gstack-upgrade", GSTACK_STUB)
        write_executable(self.stub / "claude", CLAUDE_STUB)
        write_executable(self.stub / "brew", LOGGING_STUB.format(name="brew"))
        write_executable(self.stub / "mise", LOGGING_STUB.format(name="mise"))

    def run_script(self, gstack_rc=0):
        env = {
            "HOME": str(self.home),
            "PATH": f"{self.stub}:/usr/bin:/bin",
            "STUB_LOG": str(self.log),
            "STUB_GSTACK_RC": str(gstack_rc),
        }
        result = subprocess.run(["/bin/bash", str(SCRIPT)], env=env, capture_output=True, text=True)
        log = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return result, log

    def test_runs_steps_in_order(self):
        result, log = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(log, [
            "gstack-upgrade",
            "claude plugin marketplace update",
            "claude plugin list --json",
            "claude plugin update a@m --scope user",
            "claude plugin update b@m --scope user",
            "brew upgrade crit",
            "mise run crit:profile-test",
        ])
        self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', self.settings.read_text(encoding="utf-8"))
        self.assertTrue(result.stdout.rstrip().endswith("Claude Code を再起動すると読み込まれる。"))

    def test_updates_only_user_scope_plugins(self):
        _, log = self.run_script()
        self.assertIn("claude plugin update a@m --scope user", log)
        self.assertFalse(any("s@m" in line for line in log))

    def test_failure_continues_and_reports(self):
        result, log = self.run_script(gstack_rc=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', self.settings.read_text(encoding="utf-8"))
        self.assertEqual(log[-1], "mise run crit:profile-test")
        self.assertIn("失敗した手順: gstack", result.stdout)


if __name__ == "__main__":
    unittest.main()
