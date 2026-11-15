"""settings-home-paths.py の単体テスト。

置き換えの関数を直接呼ぶテストと、偽の ~/.claude（HOME を一時ディレクトリに向ける）で
スクリプトをサブプロセスとして実行し、リンク先の書き換えを確かめるテストがある。

実行: python3 -B claude/scripts/test-settings-home-paths.py
"""
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "settings-home-paths.py"


def load_module():
    # ファイル名にハイフンがあるので import 文では読み込めない。
    spec = importlib.util.spec_from_file_location("settings_home_paths", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ToHomeRelativeTest(unittest.TestCase):
    def setUp(self):
        self.to_home_relative = load_module().to_home_relative

    def test_rewrites_home_command(self):
        text = '"command": "/Users/example/.claude/skills/gstack/hosts/claude/hooks/x",'
        self.assertEqual(
            self.to_home_relative(text, "/Users/example"),
            ('"command": "~/.claude/skills/gstack/hosts/claude/hooks/x",', 1),
        )

    def test_keeps_non_command_and_relative(self):
        text = (
            '"Read(/Users/example/a)",\n'
            '"command": "~/.claude/hooks/v.sh",\n'
            '"command": "bash \\"$HOME/.claude/hooks/h.sh\\" session",'
        )
        self.assertEqual(self.to_home_relative(text, "/Users/example"), (text, 0))

    def test_other_user_prefix_is_kept(self):
        text = '"command": "/Users/' + 'example2/x",'
        self.assertEqual(self.to_home_relative(text, "/Users/example"), (text, 0))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.target = self.home / "dotfiles" / "claude" / "settings.json"
        self.target.parent.mkdir(parents=True)
        self.link = self.home / ".claude" / "settings.json"
        self.link.parent.mkdir()
        os.symlink("../dotfiles/claude/settings.json", self.link)

    def write_settings(self, command):
        self.target.write_text(
            '{\n  "hooks": {\n    "Stop": [\n      {\n        "hooks": [\n'
            f'          {{\n            "type": "command",\n            "command": "{command}"\n          }}\n'
            '        ]\n      }\n    ]\n  }\n}\n',
            encoding="utf-8",
        )
        os.chmod(self.target, 0o644)

    def run_script(self):
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            env=env, capture_output=True, text=True,
        )

    def test_main_keeps_symlink_and_mode(self):
        self.write_settings(f"{self.home}/.claude/skills/gstack/bin/x")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.link.is_symlink())
        self.assertEqual(os.readlink(self.link), "../dotfiles/claude/settings.json")
        self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', self.target.read_text(encoding="utf-8"))
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o644)
        self.assertIn("1 件", result.stdout)

    def test_main_without_change_does_not_write(self):
        self.write_settings("~/.claude/skills/gstack/bin/x")
        before = self.target.stat()
        result = self.run_script()
        after = self.target.stat()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns))
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
