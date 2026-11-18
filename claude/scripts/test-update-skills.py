"""update-skills.sh の単体テスト。

偽のリポジトリ（スクリプトの写しと crit の profile テストの偽物）、偽の HOME（gstack-upgrade の偽物と
settings.json）、claude・brew の偽物を置いた PATH で、スクリプトを /bin/bash のサブプロセスとして実行し、
呼ばれたコマンドの順番・出力・終了コードを確かめる。
crit の profile テストの偽物がまねている契約（CC_CRIT_PROFILE_REQUIRED=1 で、スキップを失敗に変える）は、
本物の profile テストを読み込んで確かめる。

実行: python3 -B claude/scripts/test-update-skills.py
"""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
PROFILE_TEST = SCRIPTS.parent / "hooks" / "tests" / "test-cc-crit-profile.py"

PLUGINS = ('[{"id":"a@m","scope":"user"},{"id":"s@m","scope":"local"},'
           '{"id":"b@m","scope":"user"},{"id":"s@m","scope":"local"}]')

CLOSING = ("次に、再起動する前に dotfiles の Claude Code で /sync-skill-docs を実行し、hooks の変化を確かめる。"
           "更新したプラグインは、Claude Code を再起動すると読み込まれる。")


def claude_stub(on_list):
    return ('#!/bin/sh\n'
            'echo "claude $*" >> "$STUB_LOG"\n'
            f'if [ "$1 $2" = "plugin list" ]; then {on_list}; fi\n')


BREW_STUB = '#!/bin/sh\necho "brew $*" >> "$STUB_LOG"\n'

# ホームから実行されたかを確かめるため、実行時のディレクトリも書く。
GSTACK_STUB = ('#!/bin/sh\necho "gstack-upgrade $(pwd -P)" >> "$STUB_LOG"\n'
               'exit "${STUB_GSTACK_RC:-0}"\n')

# 本物の profile テストの契約をまねる。STUB_PROFILE_SKIP=1 は、profile を確かめられない状況（sandbox の中、
# crit がないなど）を表す。そのとき、CC_CRIT_PROFILE_REQUIRED=1 がなければ unittest のスキップと同じく
# 終了コード 0 で、あれば 1 で終わる。
PROFILE_STUB = ('import os, sys\n'
                'with open(os.environ["STUB_LOG"], "a") as f:\n'
                '    f.write("crit-profile-test\\n")\n'
                'if os.environ.get("STUB_PROFILE_SKIP") == "1":\n'
                '    if os.environ.get("CC_CRIT_PROFILE_REQUIRED") == "1":\n'
                '        sys.exit("ERROR: setUpClass (required, but sandbox-exec cannot apply a profile here)")\n'
                '    print("OK (skipped=1)", file=sys.stderr)\n')


def write_executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


class UpdateSkillsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.stub = self.root / "stub"
        self.work = self.root / "work"
        self.log = self.root / "log"
        for name in ("update-skills.sh", "settings-home-paths.py"):
            target = self.repo / "claude" / "scripts" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SCRIPTS / name, target)
        write_executable(self.repo / "claude" / "hooks" / "tests" / "test-cc-crit-profile.py", PROFILE_STUB)
        self.settings = self.home / ".claude" / "settings.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(
            f'{{"hooks": {{"Stop": [{{"hooks": [{{"type": "command", '
            f'"command": "{self.home}/.claude/skills/gstack/bin/x"}}]}}]}}}}\n',
            encoding="utf-8",
        )
        write_executable(self.home / ".claude" / "skills" / "gstack" / "bin" / "gstack-upgrade", GSTACK_STUB)
        write_executable(self.stub / "claude", claude_stub(f"printf '%s\\n' '{PLUGINS}'"))
        write_executable(self.stub / "brew", BREW_STUB)
        self.work.mkdir()

    def run_script(self, gstack_rc=0, profile_skip=False):
        env = {
            "HOME": str(self.home),
            "PATH": f"{self.stub}:/usr/bin:/bin",
            "STUB_LOG": str(self.log),
            "STUB_GSTACK_RC": str(gstack_rc),
            "STUB_PROFILE_SKIP": "1" if profile_skip else "0",
        }
        result = subprocess.run(
            ["/bin/bash", str(self.repo / "claude" / "scripts" / "update-skills.sh")],
            cwd=self.work, env=env, capture_output=True, text=True,
        )
        log = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return result, log

    def test_runs_steps_in_order(self):
        result, log = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(log, [
            f"gstack-upgrade {self.home}",
            "claude plugin marketplace update",
            "claude plugin list --json",
            "claude plugin update a@m --scope user",
            "claude plugin update b@m --scope user",
            "brew upgrade crit",
            "crit-profile-test",
        ])
        self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', self.settings.read_text(encoding="utf-8"))

    def test_updates_only_user_scope_plugins(self):
        _, log = self.run_script()
        self.assertIn("claude plugin update a@m --scope user", log)
        self.assertFalse(any("s@m" in line for line in log))

    def test_failure_continues_and_reports(self):
        result, log = self.run_script(gstack_rc=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('"command": "~/.claude/skills/gstack/bin/x"', self.settings.read_text(encoding="utf-8"))
        self.assertEqual(log[-1], "crit-profile-test")
        self.assertIn("失敗した手順: gstack", result.stdout)

    def test_gstack_upgrade_runs_from_home(self):
        # gstack-upgrade は呼び出し元の git リポジトリも検査するので、どこから実行してもホームから呼ぶ。
        _, log = self.run_script()
        self.assertEqual(log[0], f"gstack-upgrade {self.home}")

    def test_inline_python_ignores_cwd_modules(self):
        # 実行したディレクトリ（sandbox から書けるリポジトリのルートなど）に置かれたモジュールを読み込まない。
        marker = self.root / "marker"
        (self.work / "json.py").write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")
        self.run_script()
        self.assertFalse(marker.exists())

    def test_plugin_list_failure_skips_updates_and_reports(self):
        # 一覧が取れないか空のときは、どれも更新されないので失敗に数え、残りの手順は続ける。
        for on_list in ("exit 1", "printf 'not json\\n'", "printf '[]\\n'"):
            with self.subTest(on_list=on_list):
                self.log.unlink(missing_ok=True)
                write_executable(self.stub / "claude", claude_stub(on_list))
                result, log = self.run_script()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(any(line.startswith("claude plugin update") for line in log))
                self.assertEqual(log[-2:], ["brew upgrade crit", "crit-profile-test"])
                self.assertIn("失敗した手順: plugin-list", result.stdout)

    def test_profile_skip_counts_as_failure(self):
        # sandbox の中や crit がないとき、profile テストはスキップされて終了コード 0 で終わる。
        # profile を確かめていないので、成功に数えない。
        result, log = self.run_script(profile_skip=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(log[-1], "crit-profile-test")
        self.assertIn("失敗した手順: crit-profile-test", result.stdout)

    def test_closing_message_asks_review_before_restart(self):
        result, _ = self.run_script()
        self.assertEqual(result.stdout.rstrip().splitlines()[-1], CLOSING)


class ProfileRequiredContractTest(unittest.TestCase):
    # PROFILE_STUB がまねている、本物の profile テストの契約を確かめる。CI は本物を変数なしでしか実行しない。
    def setUp(self):
        spec = importlib.util.spec_from_file_location("cc_crit_profile", PROFILE_TEST)
        self.profile = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.profile)

    def assert_skips_or_fails(self, run):
        for required, expected in (("1", AssertionError), (None, unittest.SkipTest)):
            with self.subTest(required=required), mock.patch.dict(os.environ):
                os.environ.pop("CC_CRIT_PROFILE_REQUIRED", None)
                if required:
                    os.environ["CC_CRIT_PROFILE_REQUIRED"] = required
                # SkipTest がテストから抜けると unittest はスキップに数えるので、受け止めて種類を比べる。
                try:
                    run()
                except (AssertionError, unittest.SkipTest) as e:
                    raised = type(e)
                else:
                    raised = None
                self.assertIs(raised, expected)

    def test_missing_tool(self):
        with mock.patch.object(self.profile, "CRIT", "/nonexistent/crit"):
            self.assert_skips_or_fails(self.profile.ProfileTests.setUpClass)

    def test_nested_sandbox(self):
        # crit と git はあるが、sandbox-exec がプロファイルを適用できない（Claude Code の sandbox の中）。
        with mock.patch.multiple(self.profile, CRIT="/usr/bin/true",
                                 GIT="/usr/bin/true", SANDBOX_EXEC="/usr/bin/false"):
            self.assert_skips_or_fails(self.profile.ProfileTests.setUpClass)

    def test_no_free_port(self):
        self.assert_skips_or_fails(lambda: self.profile.free_port([]))


if __name__ == "__main__":
    unittest.main()
