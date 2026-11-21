"""trust-audit.py の単体テスト。

偽の HOME（一時ディレクトリ）に ~/.claude.json とフォルダを作り、
区分・提案するコマンド・終了コードと、ほかの値を出力しないことを確かめる。

実行: python3 -B claude/scripts/test-trust-audit.py
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "trust-audit.py"
SECRET = "do-not-print-this-value"


class TrustAuditTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="trust-audit-test."))

    def tearDown(self):
        # 権限を外したフォルダには降りられないので、降りる前に戻す。
        for d, dirs, _ in os.walk(self.home):
            for name in dirs:
                os.chmod(os.path.join(d, name), 0o700)
        shutil.rmtree(self.home)

    def folder(self, rel, git=None):
        path = self.home / rel
        path.mkdir(parents=True, exist_ok=True)
        if git == "dir":
            (path / ".git").mkdir()
        elif git == "file":
            (path / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8")
        return str(path)

    def write_config(self, projects):
        data = {"oauthAccount": {"emailAddress": SECRET}, "userID": SECRET, "projects": projects}
        (self.home / ".claude.json").write_text(json.dumps(data), encoding="utf-8")

    @staticmethod
    def entry(trusted):
        # 項目のほかのキーにも目印を入れ、出力に出ないことを確かめる。
        return {"hasTrustDialogAccepted": trusted, "lastSessionId": SECRET, "allowedTools": [SECRET]}

    def run_script(self, **extra_env):
        env = dict(os.environ, HOME=str(self.home))
        env.pop("CLAUDE_CONFIG_DIR", None)
        env.update(extra_env)
        return subprocess.run([sys.executable, "-B", str(SCRIPT)],
                              env=env, capture_output=True, text=True, check=False)

    @staticmethod
    def rows(out):
        lines = out.splitlines()
        assert lines[0].startswith("区分"), out
        rows = []
        for line in lines[1:]:
            if not line:
                break
            category, trust, path = line.split(None, 2)
            rows.append((category, trust, path))
        return rows

    @staticmethod
    def jq_words(out):
        """jq の行（--args を含む行）を、行末の \\ を除いて単語に分ける。"""
        lines = [line for line in out.splitlines() if " --args " in line]
        if not lines:
            return []
        assert len(lines) == 1, out
        return shlex.split(lines[0].removesuffix(" \\"))

    def jq_args(self, out):
        words = self.jq_words(out)
        return words[words.index("--args") + 1:] if words else []

    def write_typical_config(self):
        self.paths = {
            "home": str(self.home),
            "gone": str(self.home / "gone"),
            "gone-untrusted": str(self.home / "gone-untrusted"),
            "plain-trusted": self.folder("plain-trusted"),
            "plain-untrusted": self.folder("plain-untrusted"),
            "repo": self.folder("repo", git="dir"),
            "worktree": self.folder("worktree", git="file"),
            "mono/sub": self.folder("mono/sub"),
        }
        self.folder("mono", git="dir")
        trusted = {"home": True, "gone": True, "gone-untrusted": False, "plain-trusted": True,
                   "plain-untrusted": False, "repo": True, "worktree": True, "mono/sub": True}
        self.write_config({self.paths[k]: self.entry(trusted[k]) for k in self.paths})

    def test_classifies_each_entry(self):
        self.write_typical_config()
        rows = self.run_script().stdout
        self.assertEqual(sorted(self.rows(rows)), sorted([
            ("home", "true", "~"),
            ("missing", "true", "~/gone"),
            ("missing", "false", "~/gone-untrusted"),
            ("not-repo", "true", "~/plain-trusted"),
            ("not-repo", "false", "~/plain-untrusted"),
            ("repo", "true", "~/repo"),
            ("repo", "true", "~/worktree"),
            ("repo", "true", "~/mono/sub"),
        ]))

    def test_lists_rows_in_display_order(self):
        self.write_typical_config()
        categories = [row[0] for row in self.rows(self.run_script().stdout)]
        order = ["missing", "home", "not-repo", "repo"]
        self.assertEqual(categories, sorted(categories, key=order.index))

    def test_suggests_jq_for_missing_folders_and_trusted_folders_outside_repositories(self):
        self.write_typical_config()
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        expected = [self.paths["gone"], self.paths["gone-untrusted"], self.paths["plain-trusted"]]
        self.assertEqual(sorted(self.jq_args(result.stdout)), sorted(expected))
        self.assertIn("~/.claude.json --args ", result.stdout)

    def test_does_not_suggest_purge(self):
        # purge は元に戻せない。改名や外したボリュームでも「フォルダがない」に見えるので、提案しない。
        self.write_typical_config()
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(" --args ", result.stdout)
        self.assertNotIn("claude purge", result.stdout)

    def test_suggests_a_backup_before_the_commands(self):
        self.write_typical_config()
        lines = self.run_script().stdout.splitlines()
        backups = [i for i, line in enumerate(lines)
                   if line.startswith("cp -p ~/.claude.json ~/.claude.json.bak-")]
        self.assertEqual(len(backups), 1, lines)
        # 同じ日に 2 回実行しても上書きしないよう、時刻まで付ける。
        self.assertRegex(lines[backups[0]], r"\.bak-[0-9]{8}-[0-9]{6}$")
        jq = [i for i, line in enumerate(lines) if " --args " in line]
        self.assertLess(backups[0], jq[0])

    def test_writes_the_new_file_with_umask_077(self):
        # ~/.claude.json.new は ~/.claude.json の写しなので、ほかのアカウントから読めないようにする。
        self.write_typical_config()
        self.assertEqual(self.jq_words(self.run_script().stdout)[:3], ["(umask", "077;", "jq"])

    @unittest.skipUnless(shutil.which("jq"), "jq がない")
    def test_suggested_jq_removes_only_the_listed_entries(self):
        self.write_typical_config()
        out = self.run_script().stdout
        words, args = self.jq_words(out), self.jq_args(out)
        self.assertEqual(len(args), 3, out)
        config = self.home / ".claude.json"
        expected = json.loads(config.read_text(encoding="utf-8"))
        for key in args:
            del expected["projects"][key]
        result = subprocess.run(["jq", words[words.index("jq") + 1], str(config), "--args", *args],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), expected)

    def test_no_commands_when_nothing_to_remove(self):
        self.write_config({
            str(self.home): self.entry(False),
            self.folder("repo", git="dir"): self.entry(True),
            self.folder("plain-untrusted"): self.entry(False),
        })
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.rows(result.stdout)), 3)
        for word in ("claude purge", "jq ", "cp -p"):
            self.assertNotIn(word, result.stdout)

    def test_does_not_print_other_values(self):
        self.write_typical_config()
        result = self.run_script()
        # スクリプトが動かなくても目印は出ないので、動いて表を出したことを先に確かめる。
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(result.stdout.startswith("区分"), result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_does_not_write_files(self):
        self.write_typical_config()
        config = self.home / ".claude.json"
        before = (config.read_bytes(), config.stat().st_mtime_ns, sorted(self.home.rglob("*")))
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual((config.read_bytes(), config.stat().st_mtime_ns, sorted(self.home.rglob("*"))), before)

    def test_quotes_paths_for_the_shell(self):
        names = ["with space", "it's", "$(touch pwned)", "`id`;x"]
        missing = [str(self.home / "gone" / n) for n in names]
        trusted = [self.folder(n) for n in names]
        self.write_config({p: self.entry(True) for p in missing + trusted})
        self.assertEqual(sorted(self.jq_args(self.run_script().stdout)), sorted(missing + trusted))

    def assert_cannot_audit(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        # python3 もスクリプトを開けないと 2 で終わるので、スクリプトのメッセージで見分ける。
        self.assertIn("点検できない", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertNotIn("--args", result.stdout)

    def test_exits_2_without_the_file(self):
        self.assert_cannot_audit(self.run_script())

    def test_exits_2_on_invalid_json(self):
        (self.home / ".claude.json").write_text(f'{{"userID": "{SECRET}", ', encoding="utf-8")
        self.assert_cannot_audit(self.run_script())

    def test_exits_2_when_projects_is_not_a_dict(self):
        for data in ({"userID": SECRET}, {"userID": SECRET, "projects": [SECRET]}, [SECRET]):
            with self.subTest(data=data):
                (self.home / ".claude.json").write_text(json.dumps(data), encoding="utf-8")
                self.assert_cannot_audit(self.run_script())

    def test_exits_2_on_unprintable_or_relative_keys(self):
        # 制御文字があると、表示される（＝コピーされる）コマンドを見せかけられる。相対パスは cwd で意味が変わる。
        for key in ("relative/path", "/x/\x1b[2Kfake", "/x/a\rb", "/x/a\nb", "/x/a\x00b"):
            with self.subTest(key=key):
                self.write_config({key: self.entry(True)})
                result = self.run_script()
                self.assert_cannot_audit(result)
                for char in ("\x1b", "\r", "\x00"):
                    self.assertNotIn(char, result.stdout + result.stderr)

    def test_exits_2_when_claude_config_dir_is_set(self):
        # ~/.claude.json の場所が変わるので、古いファイルを点検して「候補なし」と返さない。
        self.write_typical_config()
        self.assert_cannot_audit(self.run_script(CLAUDE_CONFIG_DIR=str(self.home / "other")))

    @unittest.skipIf(os.geteuid() == 0, "root は権限に関係なく読める")
    def test_exits_2_when_a_folder_cannot_be_checked(self):
        # 調べられないフォルダを missing として、消す候補にしない。
        locked = Path(self.folder("locked"))
        self.write_config({str(locked / "child"): self.entry(True)})
        locked.chmod(0)
        self.assert_cannot_audit(self.run_script())


if __name__ == "__main__":
    unittest.main()
