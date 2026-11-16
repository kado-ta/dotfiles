"""check-repo.py の回帰テスト。

一時ディレクトリに git リポジトリを作り、すべての検査を通る最小構成に違反を 1 つずつ入れて確かめる。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-repo.py"

WRAPPER_COMMANDS = [
    "/usr/local/libexec/claude-push/cc-safe-push",
    "/usr/local/libexec/claude-push/cc-safe-pr create",
    "/usr/local/libexec/claude-push/cc-safe-pr edit",
    "/usr/local/libexec/claude-crit/cc-crit review",
    "/usr/local/libexec/claude-crit/cc-crit reply",
]
DENY_PUSH = ["Bash(git push)", "Bash(git push *)", "Bash(git -C * push *)", "Bash(git -c * push *)"]
CRIT_DENY = ["Read(~/.cc-crit/**)", "Edit(~/.crit/**)", "Edit(~/.crit.config.json)", "Edit(~/.cc-crit/**)"]
CRIT_DENY_READ = ["~/.cc-crit"]
LIMA_DENY = ["Read(~/.colima/_lima/_config/**)", "Read(~/.lima/_config/**)"]
LIMA_DENY_READ = ["~/.colima/_lima/_config", "~/.lima/_config"]
EDIT_DENY = ["Edit(**/.git/**/hooks/**)"]
EDIT_ASK = ["Edit(//**/.git/**/hooks/**)", "Edit(//**/.git/config)"]
MISE_CONFIG = [
    "**/mise.toml",
    "**/.mise.toml",
    "**/mise.*.toml",
    "**/.mise.*.toml",
    "**/mise/config.toml",
    "**/mise/config.*.toml",
    "**/mise/conf.d/**",
    "**/.mise/**",
    "**/.config/mise/**",
    "**/.tool-versions",
]
MISE_ASK = [f"Edit({p})" for p in MISE_CONFIG] + [f"Edit(//{p})" for p in MISE_CONFIG]
MISE_DENY_WRITE = ["~/" + p.removesuffix("/**") for p in MISE_CONFIG]
PROJECT_ASK = [
    "Edit(/claude/**)",
    "Edit(/zsh/**)",
    "Edit(/config/**)",
    "Edit(/mise/**)",
    "Edit(/mise.toml)",
    "Edit(/ghostty/**)",
    "Edit(/vscode/**)",
    "Edit(/bin/**)",
    "Edit(/codex/**)",
    "Edit(/biome/**)",
    "Edit(/obsidian/**)",
    "Edit(/aws/**)",
    "Edit(/init.command)",
    "Edit(/setup.command)",
    "Edit(/CLAUDE.md)",
    "Edit(/.claude/rules/**)",
]
PROJECT_DENY_WRITE = [
    "./claude",
    "./zsh",
    "./config",
    "./mise",
    "./mise.toml",
    "./ghostty",
    "./vscode",
    "./bin",
    "./codex",
    "./biome",
    "./obsidian",
    "./aws",
    "./init.command",
    "./setup.command",
    "./CLAUDE.md",
    "./.claude/rules",
]
README = "## Foo Bar\n\n[x](#foo-bar)\n\n"


def settings():
    return {
        "permissions": {
            "allow": [f"Bash({c})" for c in WRAPPER_COMMANDS],
            "deny": list(DENY_PUSH) + CRIT_DENY + LIMA_DENY + EDIT_DENY,
            "ask": list(MISE_ASK) + EDIT_ASK,
            "blockWritesOutsideWorkingDirectories": True,
            "additionalDirectories": ["~/.gstack/projects"],
        },
        "sandbox": {
            "excludedCommands": list(WRAPPER_COMMANDS),
            "filesystem": {
                "allowWrite": ["~/.gstack/projects"],
                "denyRead": CRIT_DENY_READ + LIMA_DENY_READ,
                "denyWrite": list(MISE_DENY_WRITE),
            },
        },
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "~/.claude/hooks/direct.sh"},
                        {"type": "command", "command": "/bin/bash ~/.claude/hooks/viabash.sh"},
                    ],
                },
            ],
        },
        "statusLine": {"type": "command", "command": "~/.claude/scripts/status.sh"},
    }


def project_settings():
    return {
        "claudeMdExcludes": ["**/dotfiles/claude/CLAUDE.md"],
        "permissions": {"ask": list(PROJECT_ASK)},
        "sandbox": {"filesystem": {"denyWrite": list(PROJECT_DENY_WRITE)}},
    }


class CheckRepoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="check-repo-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.write_settings(settings())
        self.write_project_settings(project_settings())
        self.write("claude/hooks/direct.sh", "#!/bin/bash\n", 0o755)
        self.write("claude/hooks/viabash.sh", "#!/bin/bash\n")
        self.write("claude/scripts/status.sh", "#!/bin/bash\n", 0o755)
        self.write("README.md", README)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def write(self, rel, text, mode=0o644, add=True):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)
        if add:
            self.git("add", "--", rel)

    def write_settings(self, data):
        self.write("claude/settings.json", json.dumps(data, indent=2))

    def write_project_settings(self, data):
        self.write(".claude/settings.json", json.dumps(data, indent=2))

    def check(self):
        cp = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)], capture_output=True, text=True)
        return cp.returncode, cp.stdout + cp.stderr

    def assert_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def assert_fails(self, *fragments):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        for fragment in fragments:
            self.assertIn(fragment, out)

    def test_clean_fixture_passes(self):
        self.assert_passes()

    def test_real_user_path_fails(self):
        # 検査対象のこのファイル自体が一致しないよう、連結で組み立てる。
        self.write("notes.txt", "/Users/" + "alice/x\n")
        self.assert_fails("FAIL local-paths", "notes.txt:1:")

    def test_untracked_file_with_user_path_fails(self):
        # push する前に手元で実行したとき、まだ git add していないファイルも検査する。
        self.write("notes.txt", "/Users/" + "alice/x\n", add=False)
        self.assert_fails("FAIL local-paths", "notes.txt:1:")

    def test_ignored_file_with_user_path_passes(self):
        self.write(".gitignore", "local.txt\n")
        self.write("local.txt", "/Users/" + "alice/x\n", add=False)
        self.assert_passes()

    def test_placeholder_user_path_passes(self):
        self.write("notes.txt", "/Users/example/x\n/Users/some one/x\n")
        self.assert_passes()

    def test_tracked_aws_credentials_fails(self):
        self.write("aws/config", "[default]\n")
        self.assert_fails("FAIL secret-files", "aws/config")

    def test_direct_hook_without_exec_bit_fails(self):
        self.write("claude/hooks/direct.sh", "#!/bin/bash\n", 0o644)
        self.assert_fails("FAIL hook-scripts", "claude/hooks/direct.sh")

    def test_missing_hook_fails(self):
        self.git("rm", "-q", "--cached", "claude/hooks/viabash.sh")
        self.assert_fails("FAIL hook-scripts", "claude/hooks/viabash.sh")

    def test_unresolvable_hook_command_fails(self):
        # パスを特定できない書き方は、黙って飛ばさず失敗にする。
        data = settings()
        data["hooks"]["PreToolUse"][0]["hooks"].append(
            {"type": "command", "command": "/usr/bin/env bash ~/.claude/hooks/viabash.sh"}
        )
        self.write_settings(data)
        self.assert_fails("FAIL hook-scripts", "cannot resolve")

    def test_braced_home_hook_is_checked(self):
        # ${HOME} の形もパスを特定し、直接実行するなら実行権限まで検査する。
        data = settings()
        data["hooks"]["PreToolUse"][0]["hooks"].append({"type": "command", "command": "${HOME}/.claude/hooks/viabash.sh"})
        self.write_settings(data)
        self.assert_fails("FAIL hook-scripts", "claude/hooks/viabash.sh: mode 100644")

    def test_missing_settings_fails(self):
        self.git("rm", "-q", "--cached", "claude/settings.json")
        (self.root / "claude/settings.json").unlink()
        self.assert_fails("FAIL hook-scripts", "FAIL push-permissions")

    def test_extra_excluded_command_fails(self):
        data = settings()
        data["sandbox"]["excludedCommands"].append("git")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions")

    def test_broader_wrapper_allow_fails(self):
        data = settings()
        data["permissions"]["allow"].append("Bash(/usr/local/libexec/claude-push/cc-safe-pr *)")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions")

    def test_broader_cc_crit_allow_fails(self):
        data = settings()
        data["permissions"]["allow"].append("Bash(/usr/local/libexec/claude-crit/cc-crit *)")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions")

    def test_unknown_wrapper_allow_fails(self):
        data = settings()
        data["permissions"]["allow"].append("Bash(/usr/local/libexec/claude-other/tool)")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions")

    def test_missing_cc_crit_excluded_command_fails(self):
        data = settings()
        data["sandbox"]["excludedCommands"].remove("/usr/local/libexec/claude-crit/cc-crit reply")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions")

    def test_missing_cc_crit_deny_read_fails(self):
        # crit がレビュー中のファイルを書き出す ~/.cc-crit を、Claude の sandbox から読ませない。
        data = settings()
        data["sandbox"]["filesystem"]["denyRead"].remove("~/.cc-crit")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions", "~/.cc-crit")

    def test_missing_cc_crit_read_deny_fails(self):
        data = settings()
        data["permissions"]["deny"].remove("Read(~/.cc-crit/**)")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions", "Read(~/.cc-crit/**)")

    def test_missing_lima_key_deny_read_fails(self):
        # Colima は $HOME を書き込み可能でマウントするので、VM に入る鍵を sandbox から読ませない。
        data = settings()
        data["sandbox"]["filesystem"]["denyRead"].remove("~/.colima/_lima/_config")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions", "~/.colima/_lima/_config")

    def test_missing_lima_key_read_deny_fails(self):
        data = settings()
        data["permissions"]["deny"].remove("Read(~/.lima/_config/**)")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions", "Read(~/.lima/_config/**)")

    def test_rejects_unix_socket_and_local_binding(self):
        # Docker（Colima）のソケットや localhost の全ポートに、sandbox の中のすべてのコマンドから届くようになる。
        for key, value in (("allowUnixSockets", ["~/.colima/default/docker.sock"]),
                           ("allowAllUnixSockets", True),
                           ("allowLocalBinding", True)):
            with self.subTest(key=key):
                data = settings()
                data["sandbox"]["network"] = {key: value}
                self.write_settings(data)
                self.assert_fails("FAIL push-permissions", key)

    def test_disabled_local_binding_passes(self):
        data = settings()
        data["sandbox"]["network"] = {"allowLocalBinding": False, "allowUnixSockets": []}
        self.write_settings(data)
        self.assert_passes()

    def test_missing_write_block_fails(self):
        # 作業ディレクトリの外への Edit・Write を、ほかに止める規則はない。
        data = settings()
        del data["permissions"]["blockWritesOutsideWorkingDirectories"]
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "blockWritesOutsideWorkingDirectories")

    def test_write_block_not_true_fails(self):
        for value in (False, "true"):
            with self.subTest(value=value):
                data = settings()
                data["permissions"]["blockWritesOutsideWorkingDirectories"] = value
                self.write_settings(data)
                self.assert_fails("FAIL edit-permissions", "blockWritesOutsideWorkingDirectories")

    def test_missing_git_hooks_deny_fails(self):
        # hooks は、人間が git を使ったときに sandbox の外で動く。
        data = settings()
        data["permissions"]["deny"].remove("Edit(**/.git/**/hooks/**)")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "Edit(**/.git/**/hooks/**)")

    def test_missing_mise_ask_fails(self):
        # 信頼済みのパスの mise の設定は、人間が cd したときに sandbox の外で動く。
        data = settings()
        data["permissions"]["ask"].remove("Edit(**/mise.toml)")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "Edit(**/mise.toml)")

    def test_missing_root_anchored_git_ask_fails(self):
        # 接頭辞のない形は起動したディレクトリが起点で、/add-dir で足したディレクトリに当たらない見込み。
        for rule in EDIT_ASK:
            with self.subTest(rule=rule):
                data = settings()
                data["permissions"]["ask"].remove(rule)
                self.write_settings(data)
                self.assert_fails("FAIL edit-permissions", f"permissions.ask lacks {rule}")

    def test_root_anchored_git_deny_fails(self):
        # deny は sandbox の denyWrite にもなり、// の形ではどこでも git init・git clone が hooks を写せなくなる。
        for rule in EDIT_ASK:
            with self.subTest(rule=rule):
                data = settings()
                data["permissions"]["deny"].append(rule)
                self.write_settings(data)
                self.assert_fails("FAIL edit-permissions", f"{rule} must not be a deny rule")

    def test_missing_root_anchored_mise_ask_fails(self):
        data = settings()
        data["permissions"]["ask"].remove("Edit(//**/mise.toml)")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "Edit(//**/mise.toml)")

    def test_missing_mise_deny_write_fails(self):
        data = settings()
        data["sandbox"]["filesystem"]["denyWrite"].remove("~/**/mise.toml")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "~/**/mise.toml")

    def test_unprefixed_mise_deny_write_fails(self):
        # sandbox のパスは、接頭辞がないとユーザー設定では ~/.claude が基準になり、作業ディレクトリに当たらない。
        data = settings()
        data["sandbox"]["filesystem"]["denyWrite"] = [p.removeprefix("~/") for p in MISE_DENY_WRITE]
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "~/**/mise.toml")

    def test_unexpected_additional_directory_fails(self):
        # 作業ディレクトリとして数えられ、blockWritesOutsideWorkingDirectories がそこでは効かなくなる。
        data = settings()
        data["permissions"]["additionalDirectories"].append("~/Dev")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "permissions.additionalDirectories must not list ~/Dev")

    def test_additional_directory_without_allow_write_fails(self):
        # additionalDirectories は、Bash がもともと書ける（sandbox の allowWrite にある）場所だけを許す。
        data = settings()
        data["sandbox"]["filesystem"]["allowWrite"] = []
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "sandbox.filesystem.allowWrite lacks ~/.gstack/projects")

    def test_additional_directory_variants_fail(self):
        # 前方一致にすると、隣の ~/.gstack/security（gstack の送信の記録）まで書けるようになる。
        for path in ("~/.gstack/projects/../security", "~/.gstack", "~/.gstack/projects/"):
            with self.subTest(path=path):
                data = settings()
                data["permissions"]["additionalDirectories"] = [path]
                self.write_settings(data)
                self.assert_fails("FAIL edit-permissions", f"must not list {path}")

    def test_sandbox_path_prefix_boundaries(self):
        data = settings()
        data["sandbox"]["filesystem"]["denyRead"].append("/Library/Keychains")
        self.write_settings(data)
        self.assert_passes()
        data = settings()
        data["sandbox"]["filesystem"]["denyRead"].append("~.ssh")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "unprefixed path ~.ssh")

    def test_unprefixed_sandbox_path_fails(self):
        # ユーザー設定では、~/ でも / でも始まらない sandbox のパスは ~/.claude が起点になり、黙って効かない。
        for key in ("denyRead", "denyWrite", "allowWrite", "allowRead"):
            for path in ("**/.ssh", "./secrets"):
                with self.subTest(key=key, path=path):
                    data = settings()
                    data["sandbox"]["filesystem"].setdefault(key, []).append(path)
                    self.write_settings(data)
                    self.assert_fails("FAIL edit-permissions", f"sandbox.filesystem.{key} has an unprefixed path {path}")

    def test_missing_push_deny_fails(self):
        data = settings()
        data["permissions"]["deny"].remove("Bash(git -C * push *)")
        self.write_settings(data)
        self.assert_fails("FAIL push-permissions", "Bash(git -C * push *)")

    def test_project_allow_rule_fails(self):
        data = project_settings()
        data["permissions"]["allow"] = ["Bash(*)"]
        self.write_project_settings(data)
        self.assert_fails("FAIL project-permissions", "permissions.allow")

    def test_project_excluded_commands_fails(self):
        data = project_settings()
        data["sandbox"]["excludedCommands"] = ["git"]
        self.write_project_settings(data)
        self.assert_fails("FAIL project-permissions", "sandbox.excludedCommands")

    def test_project_unknown_key_fails(self):
        # 中身が空でも、許可していないキーは失敗にする。
        data = project_settings()
        data["hooks"] = {}
        self.write_project_settings(data)
        self.assert_fails("FAIL project-permissions", "hooks")

    def test_project_removed_deny_write_fails(self):
        data = project_settings()
        data["sandbox"]["filesystem"]["denyWrite"].remove("./claude")
        self.write_project_settings(data)
        self.assert_fails("FAIL project-permissions", "./claude")

    def test_project_removed_ask_fails(self):
        data = project_settings()
        data["permissions"]["ask"].remove("Edit(/mise.toml)")
        self.write_project_settings(data)
        self.assert_fails("FAIL project-permissions", "Edit(/mise.toml)")

    def test_project_removed_claude_ask_fails(self):
        # worktree では、ユーザー設定の Edit(~/dotfiles/claude/**) が当たらない。
        data = project_settings()
        data["permissions"]["ask"].remove("Edit(/claude/**)")
        self.write_project_settings(data)
        self.assert_fails("FAIL project-permissions", "Edit(/claude/**)")

    def test_project_added_restrictions_pass(self):
        # 制限を強める方向の追加は通す。
        data = project_settings()
        data["permissions"]["ask"].append("Edit(/bin/**)")
        data["permissions"]["deny"] = ["Bash(rm *)"]
        data["sandbox"]["filesystem"]["denyWrite"].append("./bin")
        data["sandbox"]["filesystem"]["denyRead"] = ["./secrets"]
        self.write_project_settings(data)
        self.assert_passes()

    def test_missing_project_settings_fails(self):
        self.git("rm", "-q", "--cached", ".claude/settings.json")
        (self.root / ".claude/settings.json").unlink()
        self.assert_fails("FAIL project-permissions")

    def test_invalid_json_fails(self):
        self.write("x.json", "{,}")
        self.assert_fails("FAIL syntax", "x.json")

    def test_invalid_toml_fails(self):
        self.write("x.toml", "a =\n")
        self.assert_fails("FAIL syntax", "x.toml")

    def test_jsonc_file_skipped(self):
        self.write("vscode/settings.json", '{\n  // comment\n  "a": 1\n}\n')
        self.assert_passes()

    def test_lowercase_markdown_name_fails(self):
        self.write("notes.md", "# Notes\n")
        self.assert_fails("FAIL markdown-names", "notes.md")

    def test_docs_markdown_name_passes(self):
        self.write("docs/work/x/plan.md", "# Plan\n")
        self.assert_passes()

    def test_missing_link_target_fails(self):
        self.write("README.md", README + "[x](NOPE.md)\n")
        self.assert_fails("FAIL markdown-links", "README.md:5:")

    def test_missing_anchor_fails(self):
        self.write("README.md", README + "[x](#nope)\n")
        self.assert_fails("FAIL markdown-links", "#nope")

    def test_link_in_code_ignored(self):
        self.write("README.md", README + "```\n[x](NOPE.md)\n```\n\n`[x](NOPE.md)`\n")
        self.assert_passes()

    def test_nested_fence_keeps_checking(self):
        # 短いフェンスや別の文字のフェンスは、外側のフェンスを閉じない。
        inner = "````md\n```bash\n[y](NOPE2.md)\n```\n~~~\n````\n\n"
        self.write("README.md", README + inner + "[x](NOPE.md)\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("NOPE.md", out)
        self.assertNotIn("NOPE2.md", out)

    def test_explicit_anchor_passes(self):
        self.write("README.md", README + '<a name="setup"></a>\n\n## セットアップ\n\n[x](#setup)\n')
        self.assert_passes()

    def test_duplicate_explicit_anchor_fails(self):
        self.write("README.md", README + '<a name="setup"></a>\n\n<a name="setup"></a>\n')
        self.assert_fails("FAIL markdown-links", "setup")

    def test_slug_matches_github(self):
        extra = "## Claude Code 設定（`claude/`）\n\n[x](#claude-code-設定claude)\n\n## Foo Bar\n\n[y](#foo-bar-1)\n"
        self.write("README.md", README + extra)
        self.assert_passes()

    def test_percent_encoded_link(self):
        self.write("docs/a b.md", "# A\n")
        self.write("README.md", README + "[x](docs/a%20b.md)\n")
        self.assert_passes()


if __name__ == "__main__":
    unittest.main()
