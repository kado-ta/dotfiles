"""skills-check.py の単体テスト。

偽の ~/.claude（HOME を一時ディレクトリに向ける）と偽のリポジトリを作り、
スクリプトをサブプロセスで実行して、出力と終了コードを確かめる。

実行: python3 -B claude/scripts/test-skills-check.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "skills-check.py"

INVENTORY = textwrap.dedent("""\
    # Inventory

    <a name="sources"></a>

    ## Sources

    | 提供元 | 版 | 入れ方 |
    | --- | --- | --- |
    | demo | 1.0.0 | plugin |
    | gstack | 1.0 | skills |
    | 個人スキル | — | personal |

    <a name="gstack-enabled"></a>

    ### Enabled

    | スキル | 機能 |
    | --- | --- |
    | `review` | review the diff |

    <a name="gstack-limited"></a>

    ### Limited

    | スキル | 機能 |
    | --- | --- |
    | `careful` | warn before `rm` |

    <a name="gstack-off"></a>

    ### Off

    `gone`（`git push` する）、`router`、`gstack`（ルート）。

    <a name="other"></a>

    ## Other

    `/demo:alpha`、`demo:beta`、`helper`、`/mine`、`/proj`。廃止された `/plan-eng-review` と、`/demo:<名前>`・`anthropic-skills:*` の形。
    """)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def skill_md(name, description, extra=""):
    return f"---\nname: {name}\ndescription: {description}\n{extra}---\n\n# {name}\n"


class SkillsCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="skills-check-test."))
        self.home = self.tmp / "home"
        self.repo = self.tmp / "repo"
        claude = self.home / ".claude"

        # プラグイン demo（user スコープ、有効）
        self.plugin = self.tmp / "cache" / "demo" / "1.0.0"
        write(self.plugin / "skills" / "alpha" / "SKILL.md", skill_md("alpha", "Alpha skill"))
        write(self.plugin / "skills" / "beta" / "SKILL.md",
              skill_md("beta", "Beta skill", "disable-model-invocation: true\n"))
        write(self.plugin / "agents" / "helper.md", "---\nname: helper\n---\n")
        self.write_hooks("echo start")
        self.installed = {"version": 2, "plugins": {"demo@market": [{
            "scope": "user", "installPath": str(self.plugin), "version": "1.0.0"}]}}
        self.write_installed()
        self.settings = {"enabledPlugins": {"demo@market": True},
                         "skillOverrides": {"gone": "off", "router": "off", "gstack": "off",
                                            "careful": "user-invocable-only"}}
        self.write_settings()

        # gstack（~/.claude/skills/gstack に clone する）。実物と同じく、各スキルは実ディレクトリで、
        # 中の SKILL.md だけが gstack/<name>/SKILL.md へのリンク。gone はディレクトリごとのリンクにして、両方の形を試す。
        gstack = claude / "skills" / "gstack"
        write(gstack / "VERSION", "1.0\n")
        write(gstack / "SKILL.md", skill_md("gstack", "Root"))
        for name in ("review", "careful", "gone"):
            write(gstack / name / "SKILL.md", skill_md(name, f"{name} skill"))
        for name in ("review", "careful"):
            (claude / "skills" / name).mkdir()
            os.symlink(gstack / name / "SKILL.md", claude / "skills" / name / "SKILL.md")
        os.symlink(gstack / "gone", claude / "skills" / "gone")
        # gstack の setup は、リンクではない実ファイルも ~/.claude/skills に直接置く（_gstack-command など）
        write(claude / "skills" / "router" / "SKILL.md", skill_md("router", "Router"))

        # 個人スキル（リポジトリの claude/skills へのリンク）
        write(self.repo / "claude" / "skills" / "mine" / "SKILL.md", skill_md("mine", "Mine"))
        os.symlink(self.repo / "claude" / "skills" / "mine", claude / "skills" / "mine")

        # このリポジトリの project スキル（.claude/skills）
        write(self.repo / ".claude" / "skills" / "proj" / "SKILL.md", skill_md("proj", "Project skill"))

        write(self.repo / "claude" / "SKILL_INVENTORY.md", INVENTORY)
        write(self.repo / "claude" / "SKILL_CHEATSHEET.md", "# Cheat sheet\n\n`/review` と `/demo:alpha`。\n")
        write(self.repo / "claude" / "rules" / "SKILL_ROUTING.md", "# Routing\n\n`/review` を使う。\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_hooks(self, command):
        write(self.plugin / "hooks" / "hooks.json", json.dumps({"hooks": {"SessionStart": [
            {"matcher": "startup", "hooks": [{"type": "command", "command": command}]}]}}))

    def write_installed(self):
        write(self.home / ".claude" / "plugins" / "installed_plugins.json", json.dumps(self.installed))

    def write_settings(self):
        write(self.home / ".claude" / "settings.json", json.dumps(self.settings))

    def run_script(self, command):
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), command, "--repo", str(self.repo)],
            env=env, capture_output=True, text=True, check=False)

    def snapshot(self):
        result = self.run_script("snapshot")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_check(self, code, *needles):
        result = self.run_script("check")
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        for needle in needles:
            self.assertIn(needle, result.stdout)
        return result.stdout

    def test_clean_state_has_no_differences(self):
        self.snapshot()
        self.assert_check(0, "RESULT: no differences")

    def test_missing_snapshot_is_a_difference(self):
        self.assert_check(1, "no snapshot")

    def test_added_skill_is_reported_and_missing_from_docs(self):
        self.snapshot()
        write(self.plugin / "skills" / "gamma" / "SKILL.md", skill_md("gamma", "Gamma"))
        self.assert_check(1, "skill added: demo:gamma", "not in SKILL_INVENTORY.md: demo:gamma")

    def test_removed_skill_still_referenced_in_docs(self):
        self.snapshot()
        shutil.rmtree(self.plugin / "skills" / "beta")
        self.assert_check(1, "skill removed: demo:beta", "demo:beta")
        out = self.run_script("check").stdout
        self.assertIn("no longer installed", out)

    def test_override_change_is_reported_with_gstack_sections(self):
        self.snapshot()
        self.settings["skillOverrides"]["review"] = "off"
        self.write_settings()
        self.assert_check(1, "skill changed: review override on -> off", "gstack off section")

    def test_description_change_is_reported(self):
        self.snapshot()
        write(self.plugin / "skills" / "alpha" / "SKILL.md", skill_md("alpha", "Alpha skill, now different"))
        self.assert_check(1, "skill changed: demo:alpha description")

    def test_hook_change_is_reported(self):
        self.snapshot()
        self.write_hooks("curl https://example.com")
        self.assert_check(1, "plugin hooks changed: demo@market")

    def test_skill_hooks_in_frontmatter_are_tracked(self):
        self.snapshot()
        write(self.plugin / "skills" / "alpha" / "SKILL.md", skill_md(
            "alpha", "Alpha skill", "hooks:\n  PreToolUse:\n    - matcher: Bash\n"))
        self.assert_check(1, "skill changed: demo:alpha hooks")

    def test_unknown_reference_in_docs(self):
        self.snapshot()
        write(self.repo / "claude" / "rules" / "SKILL_ROUTING.md", "# Routing\n\n`/demo:nope` と `/nope`。\n")
        self.assert_check(1, "unknown name in rules/SKILL_ROUTING.md: /demo:nope",
                          "unknown name in rules/SKILL_ROUTING.md: /nope")

    def test_plugin_version_change_is_reported_in_both_checks(self):
        self.snapshot()
        self.installed["plugins"]["demo@market"][0]["version"] = "1.1.0"
        self.write_installed()
        self.assert_check(1, "plugin version: demo@market 1.0.0 -> 1.1.0",
                          "version in SKILL_INVENTORY.md: demo 1.0.0, installed 1.1.0")

    def test_gstack_version_change_is_reported(self):
        self.snapshot()
        write(self.home / ".claude" / "skills" / "gstack" / "VERSION", "1.1\n")
        self.assert_check(1, "gstack version: 1.0 -> 1.1", "version in SKILL_INVENTORY.md: gstack 1.0, installed 1.1")

    def test_disabled_plugin_skills_are_not_collected(self):
        self.snapshot()
        self.settings["enabledPlugins"]["demo@market"] = False
        self.write_settings()
        self.assert_check(1, "plugin enabled: demo@market true -> false", "skill removed: demo:alpha")

    def test_snapshot_has_no_local_paths(self):
        self.snapshot()
        text = (self.repo / "claude" / "skills-snapshot.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.tmp), text)
        self.assertNotIn("/Users/", text)
        data = json.loads(text)
        self.assertEqual(data["plugins"]["demo@market"]["version"], "1.0.0")
        self.assertTrue(data["skills"]["demo:beta"]["dmi"])
        self.assertEqual(data["skills"]["mine"]["provider"], "personal")
        self.assertEqual(data["skills"]["review"]["provider"], "gstack")
        self.assertEqual(data["skills"]["gone"]["provider"], "gstack")
        self.assertEqual(data["skills"]["router"]["provider"], "gstack")
        self.assertEqual(data["skills"]["proj"]["provider"], "project")
        self.assertIn("demo:helper", data["agents"])

    def test_gstack_section_mismatch_without_snapshot(self):
        write(self.repo / "claude" / "SKILL_INVENTORY.md",
              INVENTORY.replace("| `review` | review the diff |", "| `other` | not a gstack skill |"))
        self.assert_check(1, "gstack enabled section: missing ['review']")

    def test_provider_change_is_reported(self):
        self.snapshot()
        snapshot = self.repo / "claude" / "skills-snapshot.json"
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        data["skills"]["review"]["provider"] = "personal"
        snapshot.write_text(json.dumps(data), encoding="utf-8")
        self.assert_check(1, "skill changed: review provider personal -> gstack")

    def test_missing_anchor_is_an_error(self):
        self.snapshot()
        write(self.repo / "claude" / "SKILL_INVENTORY.md", INVENTORY.replace('<a name="gstack-off"></a>', ""))
        self.assert_check(2, "gstack-off")


if __name__ == "__main__":
    unittest.main()
