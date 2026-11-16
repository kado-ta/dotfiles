"""skill-usage.py の単体テスト。

偽のトランスクリプトを HOME（一時ディレクトリ）の ~/.claude/projects に作り、
件数が正しいことと、会話の中身を出力しないことを確かめる。

実行: python3 -B claude/scripts/test-skill-usage.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "skill-usage.py"
SECRET = "do-not-print-this-message-body"


def assistant(session, ts, content):
    return {"type": "assistant", "sessionId": session, "timestamp": ts, "message": {"content": content}}


def user(session, ts, text):
    return {"type": "user", "sessionId": session, "timestamp": ts, "message": {"content": text}}


def skill(name):
    return {"type": "tool_use", "name": "Skill", "input": {"skill": name}}


class SkillUsageTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="skill-usage-test."))
        events = [
            assistant("s1", "2026-11-20T01:00:00Z", [skill("superpowers:brainstorming")]),
            assistant("s1", "2026-11-20T01:01:00Z", [{"type": "text", "text": f"{SECRET} /pstack:how を試して"}]),
            user("s1", "2026-11-20T01:02:00Z", f"<command-name>/pstack:why</command-name> {SECRET}"),
            assistant("s2", "2026-11-21T01:00:00Z", [skill("review")]),
            user("s2", "2026-11-21T01:01:00Z", [{"type": "text", "text": "<command-name>/code-review</command-name>"}]),
            # 期間の外（until は含まない）
            assistant("s3", "2026-12-07T01:00:00Z", [skill("superpowers:writing-plans")]),
        ]
        path = self.home / ".claude" / "projects" / "-repo" / "s.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.home)

    def run_script(self, *args):
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                              env=env, capture_output=True, text=True, check=False)

    def test_counts_within_the_period(self):
        result = self.run_script("2026-11-16", "2026-12-07")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("sessions: 2", out)
        self.assertIn("  superpowers:brainstorming: 1 / 1", out)
        self.assertIn("  review: 1 / 1", out)
        self.assertNotIn("superpowers:writing-plans", out)  # 期間の外
        self.assertIn("  pstack:why: 1", out)
        self.assertIn("  code-review: 1", out)
        self.assertIn("sessions with 2+ review skills: 1", out)
        self.assertIn("assistant messages suggesting /pstack: 1", out)
        self.assertIn("  s1", out)

    def test_does_not_print_message_content(self):
        result = self.run_script("2026-11-16", "2026-12-07")
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_requires_two_dates(self):
        result = self.run_script("2026-11-16")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("使い方", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_rejects_dates_not_in_yyyy_mm_dd(self):
        for args in [("2026-11-1", "2026-12-07"), ("2026-11-16", "2026/12/07"), ("２０２６-11-16", "2026-12-07")]:
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("使い方", result.stderr)


if __name__ == "__main__":
    unittest.main()
