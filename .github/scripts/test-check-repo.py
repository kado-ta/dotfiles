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
MISE_DENY_WRITE = ["~/.config/mise", "~/dotfiles/mise", "~/.local/state/mise"]
MISE_EDIT_DENY = ["Edit(~/.local/state/mise/**)"]
MISE_EDIT_ASK = ["Edit(~/dotfiles/mise/**)"]
GUARD_TOOLS = ["Edit", "Write", "MultiEdit", "NotebookEdit"]
GUARD_ERROR = "hooks.PreToolUse lacks hooks/guard-additional-dirs.sh"
PLAYWRIGHT_DENY = [
    "mcp__playwright__browser_run_code_unsafe",
    "mcp__playwright__browser_file_upload",
    "Read(~/.crit/**)",
    "Edit(~/.local/share/claude-mcp/**)",
    "Edit(~/Library/Caches/playwright-mcp/**)",
]
PLAYWRIGHT_DENY_READ = ["~/.crit"]
PLAYWRIGHT_DENY_WRITE = ["~/.local/share/claude-mcp", "~/Library/Caches/playwright-mcp"]
PLAYWRIGHT_OUTPUT_DIR = "${HOME}/Library/Caches/playwright-mcp"
PLAYWRIGHT_HOOK_ERROR = "hooks.PreToolUse lacks hooks/guard-playwright-mcp.sh"
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
MWG_SKILL = "claude/skills/modern-web-guidance/SKILL.md"
MWG_DENY = [
    "Bash(npx *modern-web-guidance*)",
    "Bash(pnpx *modern-web-guidance*)",
    "Bash(pnpm *modern-web-guidance*)",
    "Bash(bunx *modern-web-guidance*)",
    "Bash(bun *modern-web-guidance*)",
    "Bash(yarn *modern-web-guidance*)",
    "Bash(npm *modern-web-guidance*)",
    "Bash(deno *modern-web-guidance*)",
]
README = "## Foo Bar\n\n[x](#foo-bar)\n\n"
PARANOID_CONFIG = '[settings]\nparanoid = ["config", "env_files"]\n'


def settings():
    return {
        "permissions": {
            "allow": [f"Bash({c})" for c in WRAPPER_COMMANDS],
            "deny": list(DENY_PUSH) + CRIT_DENY + LIMA_DENY + EDIT_DENY + MISE_EDIT_DENY + PLAYWRIGHT_DENY,
            "ask": list(MISE_ASK) + EDIT_ASK + MISE_EDIT_ASK,
            "blockWritesOutsideWorkingDirectories": True,
            "additionalDirectories": ["~/.gstack/projects"],
        },
        "sandbox": {
            "excludedCommands": list(WRAPPER_COMMANDS),
            "filesystem": {
                "allowWrite": ["~/.gstack/projects"],
                "denyRead": CRIT_DENY_READ + LIMA_DENY_READ + PLAYWRIGHT_DENY_READ,
                "denyWrite": list(MISE_DENY_WRITE) + PLAYWRIGHT_DENY_WRITE,
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
                # guard-additional-dirs.sh の組は、テストが [-1] で触るので最後に置く。
                {
                    "matcher": "mcp__playwright__.*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/bin/bash ~/.claude/hooks/guard-playwright-mcp.sh",
                            "timeout": 10,
                            "onFailure": "block",
                        },
                    ],
                },
                {
                    "matcher": "|".join(GUARD_TOOLS),
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/bin/bash ~/.claude/hooks/guard-additional-dirs.sh",
                            "timeout": 10,
                            "onFailure": "block",
                        },
                    ],
                },
            ],
        },
        "statusLine": {"type": "command", "command": "~/.claude/scripts/status.sh"},
        "disabledMcpjsonServers": ["playwright"],
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
        self.write("claude/hooks/guard-additional-dirs.sh", "#!/bin/bash\n")
        self.write("claude/hooks/guard-playwright-mcp.sh", "#!/bin/bash\n")
        self.write_playwright_args(["cli.js", "--output-dir", PLAYWRIGHT_OUTPUT_DIR])
        self.write("claude/scripts/status.sh", "#!/bin/bash\n", 0o755)
        self.write("README.md", README)
        self.write("mise/mise_config.toml", PARANOID_CONFIG)

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

    def write_playwright_args(self, args):
        self.write("claude/mcp/playwright.json", json.dumps({"args": args}, indent=2))

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
        # 接頭辞のない形の起点は、文書ではカレントディレクトリ。/cd などで起点が変わったときの備え。
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
        for path in MISE_DENY_WRITE:
            with self.subTest(path=path):
                data = settings()
                data["sandbox"]["filesystem"]["denyWrite"].remove(path)
                self.write_settings(data)
                self.assert_fails("FAIL edit-permissions", f"denyWrite lacks {path}")

    def test_unprefixed_mise_deny_write_fails(self):
        # sandbox のパスは、接頭辞がないとユーザー設定では ~/.claude が基準になり、作業ディレクトリに当たらない。
        data = settings()
        data["sandbox"]["filesystem"]["denyWrite"] = [p.removeprefix("~/") for p in MISE_DENY_WRITE]
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "denyWrite lacks ~/.config/mise")

    def test_missing_guard_hook_fails(self):
        data = settings()
        data["hooks"]["PreToolUse"].pop()
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", GUARD_ERROR)

    def test_guard_hook_matcher_missing_tool_fails(self):
        # MultiEdit・NotebookEdit が Edit を含むので、部分一致では Edit の抜けを見落とす。
        for tool in GUARD_TOOLS:
            with self.subTest(tool=tool):
                data = settings()
                data["hooks"]["PreToolUse"][-1]["matcher"] = "|".join(t for t in GUARD_TOOLS if t != tool)
                self.write_settings(data)
                self.assert_fails("FAIL edit-permissions", GUARD_ERROR)

    def test_guard_hook_other_command_fails(self):
        # matcher と onFailure を残したまま、コマンドだけをほかのフックに差し替えると、守りが消える。
        data = settings()
        data["hooks"]["PreToolUse"][-1]["hooks"][0]["command"] = "/bin/bash ~/.claude/hooks/viabash.sh"
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", GUARD_ERROR)

    def test_missing_mise_trust_store_deny_fails(self):
        # ~ で起動したセッションでは、Write ツールで信頼の記録に書ける。sandbox の denyWrite は Bash しか止めない。
        data = settings()
        data["permissions"]["deny"].remove("Edit(~/.local/state/mise/**)")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "permissions.deny lacks Edit(~/.local/state/mise/**)")

    def test_missing_global_mise_edit_ask_fails(self):
        data = settings()
        data["permissions"]["ask"].remove("Edit(~/dotfiles/mise/**)")
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", "permissions.ask lacks Edit(~/dotfiles/mise/**)")

    def test_guard_hook_without_block_fails(self):
        # 既定ではフックの失敗（タイムアウトなど）でツールが通る。
        data = settings()
        del data["hooks"]["PreToolUse"][-1]["hooks"][0]["onFailure"]
        self.write_settings(data)
        self.assert_fails("FAIL edit-permissions", GUARD_ERROR)

    def playwright_group(self, data):
        return next(g for g in data["hooks"]["PreToolUse"] if g["matcher"] == "mcp__playwright__.*")

    def test_missing_playwright_deny_fails(self):
        # Playwright MCP は sandbox の外で動く。run_code_unsafe は任意のコード、file_upload はプロジェクトのファイルを渡せる。
        for rule in PLAYWRIGHT_DENY:
            with self.subTest(rule=rule):
                data = settings()
                data["permissions"]["deny"].remove(rule)
                self.write_settings(data)
                self.assert_fails("FAIL playwright-mcp", f"permissions.deny lacks {rule}")

    def test_missing_playwright_deny_write_fails(self):
        # ~ で起動したセッションでは、入れる場所と出力先が allowWrite の "." に入る。cli.js は次の MCP の起動時に
        # sandbox の外で動き、出力先は symlink で向け替えられる。
        for path in PLAYWRIGHT_DENY_WRITE:
            with self.subTest(path=path):
                data = settings()
                data["sandbox"]["filesystem"]["denyWrite"].remove(path)
                self.write_settings(data)
                self.assert_fails("FAIL playwright-mcp", f"sandbox.filesystem.denyWrite lacks {path}")

    def test_playwright_output_dir_not_protected_fails(self):
        # denyWrite は、実際の出力先と同じパスのときだけ意味がある。指定がなければ、出力先はプロジェクトの中になる。
        for name, args in (
            ("elsewhere", ["cli.js", "--output-dir", "${HOME}/Library/Caches/other"]),
            ("missing", ["cli.js"]),
            ("equals-form", ["cli.js", f"--output-dir={PLAYWRIGHT_OUTPUT_DIR}"]),
            ("overridden", ["cli.js", "--output-dir", PLAYWRIGHT_OUTPUT_DIR, "--output-dir", "/tmp/x"]),
            ("no-value", ["cli.js", "--output-dir"]),
        ):
            with self.subTest(name=name):
                self.write_playwright_args(args)
                self.assert_fails("FAIL playwright-mcp", "claude/mcp/playwright.json: --output-dir")

    def test_missing_crit_deny_read_fails(self):
        # ほかの crit（プラグインの自動プランレビュー、ターミナルの crit）は、ランダムなポートを ~/.crit/sessions に書く。
        # 読めると、モデルがポートを知って Playwright で開き、承認を偽造できる。
        data = settings()
        data["sandbox"]["filesystem"]["denyRead"].remove("~/.crit")
        self.write_settings(data)
        self.assert_fails("FAIL playwright-mcp", "sandbox.filesystem.denyRead lacks ~/.crit")

    def test_missing_disabled_mcpjson_server_fails(self):
        # プロジェクトの .mcp.json の playwright は、強化した user スコープの定義を上書きする。
        for value in ([], ["other"]):
            with self.subTest(value=value):
                data = settings()
                data["disabledMcpjsonServers"] = value
                self.write_settings(data)
                self.assert_fails("FAIL playwright-mcp", "disabledMcpjsonServers lacks playwright")

    def test_missing_playwright_hook_fails(self):
        data = settings()
        data["hooks"]["PreToolUse"].remove(self.playwright_group(data))
        self.write_settings(data)
        self.assert_fails("FAIL playwright-mcp", PLAYWRIGHT_HOOK_ERROR)

    def test_playwright_hook_narrower_matcher_fails(self):
        # 一部のツールにしか当たらない matcher では、ほかのツールの filename・paths が通る。
        data = settings()
        self.playwright_group(data)["matcher"] = "mcp__playwright__browser_take_screenshot"
        self.write_settings(data)
        self.assert_fails("FAIL playwright-mcp", PLAYWRIGHT_HOOK_ERROR)

    def test_playwright_hook_other_command_fails(self):
        data = settings()
        self.playwright_group(data)["hooks"][0]["command"] = "/bin/bash ~/.claude/hooks/viabash.sh"
        self.write_settings(data)
        self.assert_fails("FAIL playwright-mcp", PLAYWRIGHT_HOOK_ERROR)

    def test_playwright_hook_without_block_fails(self):
        data = settings()
        del self.playwright_group(data)["hooks"][0]["onFailure"]
        self.write_settings(data)
        self.assert_fails("FAIL playwright-mcp", PLAYWRIGHT_HOOK_ERROR)

    def test_playwright_under_another_name_fails(self):
        # deny・フック・この検査は、サーバー名 playwright（ツール名 mcp__playwright__*）に結び付いている。
        self.write("claude/mcp/pw.json", json.dumps({"npmPackage": "@playwright/mcp@0.0.85"}))
        self.assert_fails("FAIL playwright-mcp", "claude/mcp/pw.json")

    def test_playwright_mcp_subcommand_under_another_name_fails(self):
        # playwright・playwright-core の CLI にも mcp サブコマンドがある。JSON の \/ や大文字でも素通りさせない。
        for name, text in (
            ("pw-cli", json.dumps({"npmPackage": "playwright@1.66.0", "args": ["cli.js", "mcp"]})),
            ("pw-escaped", '{"npmPackage": "@playwright\\/mcp@0.0.85"}'),
            ("pw-upper", json.dumps({"command": "/opt/Playwright/bin/node"})),
        ):
            with self.subTest(name=name):
                self.write(f"claude/mcp/{name}.json", text)
                self.assert_fails("FAIL playwright-mcp", f"claude/mcp/{name}.json")
                self.git("rm", "-q", "-f", f"claude/mcp/{name}.json")

    def test_unparsable_mcp_definition_fails(self):
        self.write("claude/mcp/broken.json", "{")
        self.assert_fails("FAIL playwright-mcp", "claude/mcp/broken.json")

    def test_other_mcp_definition_passes(self):
        self.write("claude/mcp/other.json", json.dumps({"npmPackage": "other-mcp@1.0.0"}))
        self.assert_passes()

    def test_without_playwright_definition_passes(self):
        # 定義を消して登録をやめたら、deny・denyWrite とフックは求めない。
        self.git("rm", "-q", "--cached", "claude/mcp/playwright.json")
        (self.root / "claude/mcp/playwright.json").unlink()
        data = settings()
        data["permissions"]["deny"] = [r for r in data["permissions"]["deny"] if r not in PLAYWRIGHT_DENY]
        data["sandbox"]["filesystem"]["denyWrite"] = list(MISE_DENY_WRITE)
        data["hooks"]["PreToolUse"].remove(self.playwright_group(data))
        self.write_settings(data)
        self.assert_passes()

    def test_missing_mise_global_config_fails(self):
        self.git("rm", "-q", "--cached", "mise/mise_config.toml")
        (self.root / "mise/mise_config.toml").unlink()
        self.assert_fails("FAIL mise-paranoid", "mise/mise_config.toml")

    def test_missing_paranoid_fails(self):
        self.write("mise/mise_config.toml", '[tools]\njq = "latest"\n')
        self.assert_fails("FAIL mise-paranoid", "settings.paranoid")

    def test_partial_paranoid_fails(self):
        # 文字列は部分一致で通さない。config だけでは、_.source などが読むファイルを中身で信頼しない。
        for value in ('["config"]', '["env_files"]', "false", '"config,env_files"'):
            with self.subTest(value=value):
                self.write("mise/mise_config.toml", f"[settings]\nparanoid = {value}\n")
                self.assert_fails("FAIL mise-paranoid", "settings.paranoid")

    def test_paranoid_true_passes(self):
        self.write("mise/mise_config.toml", "[settings]\nparanoid = true\n")
        self.assert_passes()

    def test_paranoid_superset_passes(self):
        self.write("mise/mise_config.toml", '[settings]\nparanoid = ["config", "env_files", "plugins"]\n')
        self.assert_passes()

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

    def test_vendored_skill_markdown_name_passes(self):
        # 上流から取り込んだスキルは、SKILL.md が参照ファイルを名前で指すので、上流の名前のまま置く。
        self.write("claude/skills/chrome-extensions/references/extensions/api-calling.md", "# API\n")
        self.assert_passes()

    def test_other_skill_lowercase_markdown_name_fails(self):
        # 例外は取り込んだスキルだけ。自分で書くスキルの参照ファイルは規約に従う。
        self.write("claude/skills/mine/references/notes.md", "# Notes\n")
        self.assert_fails("FAIL markdown-names", "claude/skills/mine/references/notes.md")

    def test_modern_web_guidance_without_npx_deny_fails(self):
        # ガイドと上流の SKILL.md は npx 系で最新版を動かすよう指示するので、スキルがあるあいだは deny にする。
        self.write(MWG_SKILL, "---\nname: modern-web-guidance\n---\n")
        for rule in MWG_DENY:
            with self.subTest(rule=rule):
                data = settings()
                data["permissions"]["deny"] += [r for r in MWG_DENY if r != rule]
                self.write_settings(data)
                self.assert_fails("FAIL modern-web-guidance", f"permissions.deny lacks {rule}")

    def test_modern_web_guidance_with_npx_deny_passes(self):
        self.write(MWG_SKILL, "---\nname: modern-web-guidance\n---\n")
        data = settings()
        data["permissions"]["deny"] += MWG_DENY
        self.write_settings(data)
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
