"""check-repo.py の回帰テスト。

一時ディレクトリに git リポジトリを作り、すべての検査を通る最小構成に違反を 1 つずつ入れて確かめる。
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

SCRIPT = Path(__file__).resolve().parent / "check-repo.py"
# 検査対象のこのファイル自体が一致しないよう、連結で組み立てる（後半は 36 文字）。
FAKE_PAT = "ghp_" + "Zq8rT2vX9wL4mN7pK3sB6dF1gH5jC0yE8uA2"

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
GITCONFIG = "[merge]\n\tff = false\n[rerere]\n\tenabled = false\n"
# リンク用のスクリプト（aws/link.sh の形）の部品。判定は SCRIPT_DIR= の後に置き、その前には空行・コメント・set・
# SCRIPT_DIR=・if/echo/exit/fi の確認だけを置く。
SCRIPT_DIR_LINE = 'SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)\n'
GUARD = 'if [ -f "$SCRIPT_DIR/../.git" ]; then\n  echo "$SCRIPT_DIR is in a git worktree." >&2\n  exit 1\nfi\n'
LINK_BODY = 'mkdir -p "$HOME/.aws"\nln -snfv "$SCRIPT_DIR/config" "$HOME/.aws/config"\n'
CI_WORKFLOW = ".github/workflows/ci.yaml"
CI_VERSIONS = (
    "    env:\n"
    "      SHELLCHECK_VERSION: v0.11.0\n"
    "      ACTIONLINT_VERSION: 1.7.12\n"
    "      ZIZMOR_VERSION: 1.33.1\n"
    "      GITLEAKS_VERSION: 8.30.1\n"
)
# 手元（Homebrew）の版のコマンドの出力（2026-11-25 に確かめた）。偽のツールが出す。
FAKE_VERSION_OUTPUT = {
    "shellcheck": "ShellCheck - shell script analysis tool\nversion: 0.11.0\n"
                  "license: GNU General Public License, version 3\nwebsite: https://www.shellcheck.net\n",
    "actionlint": "1.7.12\ninstalled from Homebrew\nbuilt with go1.26.3 compiler for darwin/arm64\n",
    "zizmor": "zizmor 1.33.1\n",
    "gitleaks": "8.30.1\n",
}
REAL_GITLEAKS = shutil.which("gitleaks")


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


def link_script(before="", guard=GUARD):
    return "#!/bin/bash -e\n\n" + before + SCRIPT_DIR_LINE + "\n" + guard + "\n" + LINK_BODY


def project_settings():
    return {
        "claudeMdExcludes": ["**/dotfiles/claude/CLAUDE.md"],
        "permissions": {"ask": list(PROJECT_ASK)},
        "sandbox": {"filesystem": {"denyWrite": list(PROJECT_DENY_WRITE)}},
    }


def write_fake_tool(directory, name, body):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


class CheckRepoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 手元に入っている版に結果が左右されないよう、check() は版を出す偽のツールを PATH の先頭に置く。
        # 新しく作ったスクリプトは初回の起動に 0.1〜0.3 秒かかるので、クラスで 1 回だけ作る。
        cls.fake_bin = Path(tempfile.mkdtemp(prefix="check-repo-fake-tools-"))
        cls.addClassCleanup(shutil.rmtree, cls.fake_bin)
        for name, output in FAKE_VERSION_OUTPUT.items():
            body = f"printf '%s' '{output}'\n"
            if name == "gitleaks":
                # 入っていなければ、secret-content と tool-versions がどちらも not found で失敗する。
                if REAL_GITLEAKS is None:
                    continue
                # secret-content は本物の gitleaks で動かす。
                body = f'if [ "$1" = version ]; then {body}exit 0; fi\nexec {shlex.quote(REAL_GITLEAKS)} "$@"\n'
            write_fake_tool(cls.fake_bin, name, body)

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
        self.write("bin/.gitconfig", GITCONFIG)
        self.write("aws/link.sh", link_script(), 0o755)
        self.write(CI_WORKFLOW, CI_VERSIONS)
        self.path_dirs = [self.fake_bin]

    def override_tool(self, name, body):
        """このテストだけ、偽のツールを差し替える（クラスで共有する偽のツールは書き換えない）。"""
        directory = Path(tempfile.mkdtemp(prefix="check-repo-override-"))
        self.addCleanup(shutil.rmtree, directory)
        write_fake_tool(directory, name, body)
        self.path_dirs.insert(0, directory)

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

    def check(self, env=None):
        if env is None:
            env = {**os.environ, "PATH": os.pathsep.join([*map(str, self.path_dirs), os.environ["PATH"]])}
        cp = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.root)], capture_output=True, text=True, env=env)
        return cp.returncode, cp.stdout + cp.stderr

    def assert_passes(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def assert_fails(self, *fragments, env=None):
        code, out = self.check(env)
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

    def test_symlinked_dir_is_not_read_by_local_paths(self):
        # 追跡しているディレクトリを外への symlink に差し替えても、リンク先は読まない。
        self.write("sub/f.txt", "ok\n")
        outside = tempfile.TemporaryDirectory(prefix="check-repo-outside-")
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / "f.txt").write_text("/Users/" + "alice/x\n", encoding="utf-8")
        shutil.rmtree(self.root / "sub")
        (self.root / "sub").symlink_to(outside.name)
        self.assert_passes()

    def test_symlink_target_with_user_path_fails(self):
        # 公開されるのはリンクの文字列なので、リンク先のパスにあるユーザー名を調べる。
        (self.root / "link").symlink_to("/Users/" + "alice/x")
        self.assert_fails("FAIL local-paths", "link: symlink target is an absolute path under /Users or /home with a real user name")

    def test_placeholder_user_path_passes(self):
        self.write("notes.txt", "/Users/example/x\n/Users/some one/x\n")
        self.assert_passes()

    def test_tracked_aws_credentials_fails(self):
        self.write("aws/config", "[default]\n")
        self.assert_fails("FAIL secret-files", "aws/config")

    def test_secret_in_tracked_file_fails(self):
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")
        # CI のログは公開されるので、見つかった値は出さない。
        _, out = self.check()
        self.assertNotIn(FAKE_PAT[4:], out)

    def test_secret_in_untracked_file_fails(self):
        self.write("notes/token.txt", FAKE_PAT + "\n", add=False)
        self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")

    def test_secret_in_ignored_file_passes(self):
        self.write(".gitignore", "ignored.txt\n")
        self.write("ignored.txt", FAKE_PAT + "\n", add=False)
        self.assert_passes()

    def test_gitleaks_allow_comment_passes(self):
        self.write("notes/token.txt", FAKE_PAT + "  # gitleaks:allow\n")
        self.assert_passes()

    def test_symlink_is_not_followed(self):
        # 公開されるのはリンクの文字列で、リンク先の中身ではない。
        outside = tempfile.TemporaryDirectory(prefix="check-repo-outside-")
        self.addCleanup(outside.cleanup)
        target = Path(outside.name) / "token.txt"
        target.write_text(FAKE_PAT + "\n", encoding="utf-8")
        (self.root / "link.txt").symlink_to(target)
        self.assert_passes()

    def test_file_under_symlinked_dir_is_not_copied(self):
        # 追跡しているディレクトリを外への symlink に差し替えても、リンク先は読まない。
        self.write("sub/f.txt", "ok\n")
        outside = tempfile.TemporaryDirectory(prefix="check-repo-outside-")
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / "f.txt").write_text(FAKE_PAT + "\n", encoding="utf-8")
        shutil.rmtree(self.root / "sub")
        (self.root / "sub").symlink_to(outside.name)
        _, out = self.check()
        self.assertIn("PASS secret-content", out)

    def test_gitleaks_toml_without_default_rules_fails(self):
        # [extend] useDefault = true がないと、gitleaks は既定のルールを使わない。
        self.write(".gitleaks.toml", 'title = "dotfiles"\n')
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("FAIL secret-content", ".gitleaks.toml: [extend] useDefault = true is required")

    def test_uppercase_gitleaksignore_does_not_suppress(self):
        # 大文字小文字を区別しない一時ディレクトリでは、gitleaks が .GITLEAKSIGNORE を .gitleaksignore として読む。
        self.write(".GITLEAKSIGNORE", "notes/token.txt:github-pat:1\n")
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")

    def test_path_with_space_and_japanese_is_reported(self):
        self.write("docs/日本語 メモ.txt", FAKE_PAT + "\n")
        self.assert_fails("FAIL secret-content", "docs/日本語 メモ.txt:1: github-pat")

    def test_gitleaks_config_env_is_ignored(self):
        # 手元の環境変数で github-pat を外されても、検査は既定の設定で動く。
        conf = self.root.parent / f"{self.root.name}-env.toml"
        conf.write_text('[extend]\nuseDefault = true\ndisabledRules = ["github-pat"]\n', encoding="utf-8")
        self.addCleanup(conf.unlink)
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("notes/token.txt:1: github-pat", env={**os.environ, "GITLEAKS_CONFIG": str(conf)})

    def test_gitleaks_config_toml_env_is_ignored(self):
        toml = '[extend]\nuseDefault = true\ndisabledRules = ["github-pat"]\n'
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("notes/token.txt:1: github-pat", env={**os.environ, "GITLEAKS_CONFIG_TOML": toml})

    def test_repo_gitleaks_config_allowlist_passes(self):
        # allowlist の paths は、リポジトリからの相対パスに当たる。
        self.write(".gitleaks.toml", "[extend]\nuseDefault = true\n\n[[allowlists]]\npaths = ['''^fixtures/''']\n")
        self.write("fixtures/token.txt", FAKE_PAT + "\n")
        self.assert_passes()

    def test_allowlist_does_not_match_temp_dir(self):
        # 写した先のディレクトリ名に当たる除外で、全ファイルが外れない。
        self.write(".gitleaks.toml", "[extend]\nuseDefault = true\n\n[[allowlists]]\npaths = ['''(?:^|/)src/''']\n")
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")

    def test_gitleaks_json_does_not_shadow_config(self):
        # gitleaks は名前（.gitleaks）で設定を探すと .gitleaks.json を先に読むので、.gitleaks.toml に固定する。
        self.write(".gitleaks.toml", "[extend]\nuseDefault = true\n")
        self.write(".gitleaks.json", '[extend]\nuseDefault = true\ndisabledRules = ["github-pat"]\n')
        self.write("notes/token.txt", FAKE_PAT + "\n")
        self.assert_fails("FAIL secret-content", "notes/token.txt:1: github-pat")

    def test_broken_gitleaks_config_fails(self):
        self.write(".gitleaks.toml", "[extend\n")
        self.assert_fails("FAIL secret-content", "error: gitleaks exited with 1")
        _, out = self.check()
        self.assertNotIn("\x1b[", out)

    def test_leaks_exit_with_empty_report_fails(self):
        fake = Path(tempfile.mkdtemp(prefix="check-repo-fake-gitleaks-"))
        self.addCleanup(shutil.rmtree, fake)
        script = fake / "gitleaks"
        script.write_text(
            '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
            '  if [ "$1" = --report-path ]; then printf "[]" > "$2"; fi\n'
            "  shift\ndone\nexit 42\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
        env = {**os.environ, "PATH": f"{fake}:/usr/bin:/bin"}
        self.assert_fails("FAIL secret-content", "gitleaks reported leaks but the report is empty", env=env)

    def test_missing_gitleaks_fails(self):
        path = "/usr/bin:/bin"
        self.assertIsNone(shutil.which("gitleaks", path=path))
        self.assert_fails("FAIL secret-content", "gitleaks not found", env={**os.environ, "PATH": path})

    def test_newer_local_tool_asks_to_bump_ci(self):
        # 1.7.12 は 1.7.9 より新しい（文字列ではなく数で比べる）。
        self.write(CI_WORKFLOW, CI_VERSIONS.replace("ACTIONLINT_VERSION: 1.7.12", "ACTIONLINT_VERSION: 1.7.9"))
        self.assert_fails(
            "FAIL tool-versions",
            "actionlint 1.7.12 on PATH, but .github/workflows/ci.yaml pins 1.7.9 "
            "(update ACTIONLINT_VERSION and ACTIONLINT_SHA256 together in a separate PR)",
        )

    def test_older_local_tool_asks_to_brew_upgrade(self):
        # ほかの Mac で先に CI を上げたときなど。CI の版を下げる案内をしない。
        self.write(CI_WORKFLOW, CI_VERSIONS.replace("ZIZMOR_VERSION: 1.33.1", "ZIZMOR_VERSION: 1.34.0"))
        self.assert_fails(
            "FAIL tool-versions",
            "zizmor 1.33.1 on PATH, but .github/workflows/ci.yaml pins 1.34.0 (run brew upgrade zizmor)",
        )

    def test_missing_ci_workflow_fails(self):
        self.git("rm", "-q", "-f", CI_WORKFLOW)
        self.assert_fails("FAIL tool-versions", ".github/workflows/ci.yaml: missing")

    def test_missing_version_key_fails(self):
        self.write(CI_WORKFLOW, CI_VERSIONS.replace("      GITLEAKS_VERSION: 8.30.1\n", ""))
        self.assert_fails("FAIL tool-versions", ".github/workflows/ci.yaml: GITLEAKS_VERSION must be set exactly once")

    def test_duplicate_version_key_fails(self):
        self.write(CI_WORKFLOW, CI_VERSIONS + "      GITLEAKS_VERSION: 8.31.0\n")
        self.assert_fails("FAIL tool-versions", ".github/workflows/ci.yaml: GITLEAKS_VERSION must be set exactly once")

    def test_quoted_version_values_pass(self):
        # 引用符で囲んでも、GitHub Actions に渡る値は変わらない。
        text = CI_VERSIONS.replace("SHELLCHECK_VERSION: v0.11.0", 'SHELLCHECK_VERSION: "v0.11.0"')
        self.write(CI_WORKFLOW, text.replace("GITLEAKS_VERSION: 8.30.1", "GITLEAKS_VERSION: '8.30.1'"))
        self.assert_passes()

    def test_version_value_with_comment_passes(self):
        self.write(CI_WORKFLOW, CI_VERSIONS.replace("ZIZMOR_VERSION: 1.33.1", "ZIZMOR_VERSION: 1.33.1  # pinned"))
        self.assert_passes()

    def test_unreadable_pinned_version_fails_and_checks_the_rest(self):
        text = CI_VERSIONS.replace("SHELLCHECK_VERSION: v0.11.0", "SHELLCHECK_VERSION: latest")
        self.write(CI_WORKFLOW, text.replace("GITLEAKS_VERSION: 8.30.1", "GITLEAKS_VERSION: 8.31.0"))
        self.assert_fails(
            "FAIL tool-versions",
            ".github/workflows/ci.yaml: cannot read SHELLCHECK_VERSION as a version",
            "gitleaks 8.30.1 on PATH",
        )

    def test_missing_tool_fails(self):
        path = "/usr/bin:/bin"
        self.assertIsNone(shutil.which("actionlint", path=path))
        self.assert_fails(
            "FAIL tool-versions",
            "actionlint not found (install it with brew install actionlint)",
            env={**os.environ, "PATH": path},
        )

    def test_unreadable_tool_version_fails(self):
        self.override_tool("shellcheck", "echo 'ShellCheck - shell script analysis tool'\n")
        self.assert_fails("FAIL tool-versions", "cannot read the version of shellcheck")

    def test_tool_version_with_nonzero_exit_fails(self):
        self.override_tool("zizmor", "echo 'zizmor 1.33.1'\nexit 1\n")
        self.assert_fails("FAIL tool-versions", "cannot read the version of zizmor")

    def test_hanging_tool_fails_without_path_and_checks_the_rest(self):
        # 版のコマンドがタイムアウト（10 秒）したとき。例外のメッセージにはツールのパスが入る。
        self.override_tool("zizmor", "exec sleep 30\n")
        self.write(CI_WORKFLOW, CI_VERSIONS.replace("GITLEAKS_VERSION: 8.30.1", "GITLEAKS_VERSION: 8.31.0"))
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("cannot read the version of zizmor", out)
        self.assertIn("gitleaks 8.30.1 on PATH", out)
        self.assertNotIn(str(self.path_dirs[0]), out)

    def test_tool_that_cannot_start_fails_without_path(self):
        self.override_tool("shellcheck", "")
        # シバンがないので、起動の時点で OSError（Exec format error）になる。
        (self.path_dirs[0] / "shellcheck").write_text("echo 'version: 0.11.0'\n", encoding="utf-8")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("cannot read the version of shellcheck", out)
        self.assertNotIn(str(self.path_dirs[0]), out)

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

    def test_trusted_config_paths_fails(self):
        # 空のリストは既定値と同じで何も信頼しないが、キーごと置かせない（パスを足す変更を止める）。
        for value in ("[]", '["~/Dev"]'):
            with self.subTest(value=value):
                self.write("mise/mise_config.toml", PARANOID_CONFIG + f"trusted_config_paths = {value}\n")
                self.assert_fails("FAIL mise-paranoid", "settings.trusted_config_paths")

    def test_mise_env_override_fails(self):
        # 環境変数で、paranoid や信頼するパスを上書きさせない。
        # bin/link.sh は bin/.??* をすべて ~ にリンクするので、bin/.zshenv なども zsh が読む。sheldon の inline も zsh の起動で動く。
        for rel, text in (("bin/.zshrc", "export MISE_PARANOID=0\n"),
                          ("bin/.zprofile", "export MISE_TRUSTED_CONFIG_PATHS=~/Dev\n"),
                          ("bin/.zshenv", "export MISE_PARANOID=0\n"),
                          ("zsh/x.zsh", "export MISE_TRUSTED_CONFIG_PATHS=~/Dev\n"),
                          ("config/sheldon/plugins.toml", '[plugins.x]\ninline = "export MISE_PARANOID=0"\n'),
                          ("mise/mise_config.toml", PARANOID_CONFIG + '[env]\nMISE_PARANOID = "0"\n')):
            with self.subTest(rel=rel):
                self.write(rel, text)
                self.assert_fails("FAIL mise-paranoid", rel)
                self.write(rel, PARANOID_CONFIG if rel == "mise/mise_config.toml" else "")

    def test_gitconfig_rerere_not_false_fails(self):
        # rerere が動くと、sandbox の外の git が .git/rr-cache と MERGE_RR（sandbox が書ける）の解決を任意のパスに書く。
        for name, text in (("missing section", "[merge]\n\tff = false\n"), ("true", "[rerere]\n\tenabled = true\n"),
                           ("bare key", "[rerere]\n\tenabled\n"), ("invalid", "[rerere]\n\tenabled = maybe\n"),
                           ("last wins", GITCONFIG + "[rerere]\n\tenabled = true\n")):
            with self.subTest(case=name):
                self.write("bin/.gitconfig", text)
                self.assert_fails("FAIL rerere", "bin/.gitconfig: rerere.enabled must be false")
        self.git("rm", "-q", "-f", "bin/.gitconfig")
        self.assert_fails("FAIL rerere", "bin/.gitconfig: rerere.enabled must be false")

    def test_gitconfig_include_after_rerere_fails(self):
        # include は書いた位置で読み込まれ、後の値が勝つ。--file は include をたどらないので、順序で確かめる。
        for name, text in (("include", GITCONFIG + "[include]\n\tpath = ~/.gitconfig_x\n"),
                           ("includeIf", GITCONFIG + '[includeIf "gitdir:~/x/"]\n\tpath = ~/.gitconfig_x\n')):
            with self.subTest(case=name):
                self.write("bin/.gitconfig", text)
                self.assert_fails("FAIL rerere", "bin/.gitconfig: rerere.enabled must come after every include")

    def test_gitconfig_include_before_rerere_passes(self):
        self.write("bin/.gitconfig", '[includeIf "gitdir:~/x/"]\n\tpath = ~/.gitconfig_x\n' + GITCONFIG)
        self.assert_passes()

    def test_gitconfig_rerere_false_forms_pass(self):
        for text in ("[ReReRe]\n\tEnabled = no\n", "[rerere]\n\tenabled = 0\n",
                     "[rerere]\n\tenabled = true\n[rerere]\n\tenabled = false\n"):
            with self.subTest(text=text):
                self.write("bin/.gitconfig", text)
                self.assert_passes()

    def test_link_guard_forms_pass(self):
        # 今の 10 本の判定は、$SCRIPT_DIR と ${SCRIPT_DIR}、空白とタブのインデントで書き方が分かれている。
        # 判定より前に、set・macOS の確認・CLAUDECODE の確認・コメントを置くものもある。
        prelude = ('# curl | bash で、curl の失敗を検出するため。\nset -o pipefail\nset -euo pipefail\n\n'
                   'if [ "$(uname)" != "Darwin" ] ; then\n\techo "This is not macOS! x setup is failed ;("\n\texit 1\nfi # macOS\n\n'
                   'if [ -n "${CLAUDECODE:-}" ]; then\n  echo "Run this from a plain terminal."\n  exit 1\nfi\n\n')
        tabs = 'if [ -f "${SCRIPT_DIR}/../.git" ]; then\n\techo "${SCRIPT_DIR} is in a git worktree." >&2\n\texit 1\nfi\n'
        for name, text in (("braced", link_script(guard=GUARD.replace("$SCRIPT_DIR", "${SCRIPT_DIR}"))),
                           ("tabs", link_script(guard=tabs)), ("prelude", link_script(before=prelude)),
                           ("fi with comment", link_script(guard=GUARD.replace("fi\n", "fi # worktree guard\n"))),
                           ("escaped quotes", link_script(guard=GUARD.replace(
                               'worktree."', 'worktree. Run it from \\"~/dotfiles\\"."')))):
            with self.subTest(case=name):
                self.write("aws/link.sh", text)
                self.assert_passes()

    def test_scripts_without_link_guard_target_pass(self):
        # hook のテストは一時ディレクトリの中にリンクを作るので、判定は要らない。
        # SCRIPT_DIR= があってもリンクを作らないもの（biome/sync_schema.sh）、コメントや語の中の ln も対象にしない。
        for rel, text in (("claude/hooks/tests/test-x.sh", SCRIPT_DIR_LINE + 'ln -s "$SCRIPT_DIR/x" "$TMP/x"\n'),
                          ("biome/sync_schema.sh", SCRIPT_DIR_LINE + 'cp "$SCRIPT_DIR/a" "$SCRIPT_DIR/b"\n'),
                          ("config/x.sh", '# ln -snfv "$SCRIPT_DIR/x" "$HOME/"\n  # ln コマンドを追加する\n'),
                          ("claude/hooks/ask-x.sh", 'RE="-[abd-ln-sv-z]"\n')):
            with self.subTest(rel=rel):
                self.write(rel, text)
                self.assert_passes()

    def test_link_script_without_guard_fails(self):
        # リンク用のスクリプトを足して判定を書き忘れると、worktree の中から実行したときにリンクが worktree を指す。
        for line in ('ln -snfv "$SCRIPT_DIR/x" "$HOME/x"', '/bin/ln -s "$SCRIPT_DIR/x" "$HOME/x"',
                     'command ln -s "$SCRIPT_DIR/x" "$HOME/x"', 'true;ln -s "$SCRIPT_DIR/x" "$HOME/x"',
                     'ln "$SCRIPT_DIR/x" "$HOME/x"', '\\ln -s "$SCRIPT_DIR/x" "$HOME/x"',
                     'out=`ln -s "$SCRIPT_DIR/x" "$HOME/x"`', 'LN="ln -snfv"\n$LN "$SCRIPT_DIR/x" "$HOME/x"',
                     "LN='ln -snfv'\n$LN \"$SCRIPT_DIR/x\" \"$HOME/x\"", 'LN=ln\n$LN -s "$SCRIPT_DIR/x" "$HOME/x"',
                     'LN="ln"\n"$LN" -s "$SCRIPT_DIR/x" "$HOME/x"', 'ln>/dev/null -s "$SCRIPT_DIR/x" "$HOME/x"',
                     '"/bin/ln" -snfv "$SCRIPT_DIR/x" "$HOME/x"'):
            with self.subTest(line=line):
                self.write("aws/link.sh", "#!/bin/bash -e\n" + SCRIPT_DIR_LINE + line + "\n")
                self.assert_fails("FAIL link-guard", "aws/link.sh: runs ln without the worktree guard")

    def test_untracked_link_script_without_guard_fails(self):
        # push する前に手元で実行したとき、git add 前の新しいスクリプトも見る。
        self.write("ghostty/link.sh", "#!/bin/bash -e\n" + SCRIPT_DIR_LINE + LINK_BODY, add=False)
        self.assert_fails("FAIL link-guard", "ghostty/link.sh: runs ln without the worktree guard")

    def test_link_guard_after_other_line_fails(self):
        # 判定より前の行は、worktree の中でも判定で止まる前に動く。ツールの呼び出しも書き込むので、許した行のほかはすべて失敗にする。
        for line in ('mkdir -p "$HOME/x"', 'touch "$SCRIPT_DIR/credentials"', "cat <<'EOF' >\"$SCRIPT_DIR/config\"",
                     "mise install", 'echo "x" > "$HOME/x"'):
            with self.subTest(line=line):
                self.write("aws/link.sh", "#!/bin/bash -e\n" + SCRIPT_DIR_LINE + line + "\n" + GUARD + LINK_BODY)
                self.assert_fails("FAIL link-guard", "aws/link.sh:3: only blank lines, comments")

    def test_link_guard_without_script_dir_before_fails(self):
        # $SCRIPT_DIR が空だと、判定は /../.git を見て偽になり、set -u のないスクリプトは先へ進む。
        for name, text in (("after", "#!/bin/bash -e\n" + GUARD + SCRIPT_DIR_LINE + LINK_BODY),
                           ("missing", "#!/bin/bash -e\n" + GUARD + LINK_BODY),
                           ("other form", '#!/bin/bash -e\nSCRIPT_DIR=$(dirname "$0")\n' + GUARD + LINK_BODY)):
            with self.subTest(case=name):
                self.write("aws/link.sh", text)
                self.assert_fails("FAIL link-guard", 'aws/link.sh: SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd) must come before')

    def test_link_guard_lookalikes_fail(self):
        # 判定に見えても、worktree の中で止まらない形は数えない。インデントした判定は、ほかのブロックの中で実行されないことがある。
        for name, guard in (("root .git", GUARD.replace("/../.git", "/.git")),
                            ("two levels up", GUARD.replace("/../.git", "/../../.git")),
                            ("directory test", GUARD.replace("-f", "-d")),
                            ("exit 0", GUARD.replace("exit 1", "exit 0")),
                            ("no exit", GUARD.replace("  exit 1\n", "")),
                            ("indented", "".join("  " + line for line in GUARD.splitlines(True))),
                            # 分岐や入れ子の if の中の exit 1 は、worktree の中で止まらないことがある。
                            ("nested if", GUARD.replace("  exit 1\n", '  if [ -n "${X:-}" ]; then\n    exit 1\n  fi\n')),
                            ("else", GUARD.replace("  exit 1\n", "else\n  exit 1\n")),
                            ("elif", GUARD.replace("  exit 1\n", 'elif [ -n "${X:-}" ]; then\n  exit 1\n')),
                            # fi の後ろに文字があっても判定の終わりとみなし、後ろの関数の exit 1 を拾わない。
                            ("fi with comment", GUARD.replace("  exit 1\nfi\n", "fi # worktree guard\nlink() {\n  exit 1\n}\n")),
                            ("fi;", GUARD.replace("  exit 1\nfi\n", "fi;\nlink() {\n  exit 1\n}\n")),
                            # 抜け道や継続行、case の中の exit 1 も、条件しだいで実行されない。
                            ("or brace", GUARD.replace("  exit 1\n", '  [ -n "${ALLOW_WORKTREE:-}" ] || {\n    exit 1\n  }\n')),
                            ("or continuation", GUARD.replace("  exit 1\n", '  [ -n "${X:-}" ] ||\n  exit 1\n')),
                            ("case", GUARD.replace("  exit 1\n", '  case "${X:-}" in\n    "")\n      exit 1\n      ;;\n  esac\n')),
                            # 行末の \" では文字列が閉じず、次の行の exit 1 は文字列の一部になる。
                            ("escaped quote at end", GUARD.replace('worktree." >&2\n  exit 1\nfi\n',
                                                                    'worktree.\\"\n  exit 1\n"\nfi\n')),
                            # fi にパイプが付くと if 全体が子シェルで動き、exit 1 は子シェルだけを終える。
                            ("pipe on fi", GUARD.replace("fi\n", "fi 2>&1 | sed 's/^/[aws] /' >&2\n"))):
            with self.subTest(case=name):
                self.write("aws/link.sh", link_script(guard=guard))
                self.assert_fails("FAIL link-guard", "aws/link.sh: runs ln without the worktree guard")

    def test_link_guard_inside_prelude_block_fails(self):
        # macOS の確認の中の SCRIPT_DIR= や判定は、macOS では実行されない。判定を確認の fi の上に差し込む誤りもある。
        darwin = 'if [ "$(uname)" != "Darwin" ] ; then\n  echo "This is not macOS!"\n  exit 1\n'
        for name, text, fragment in (
                ("script dir in block", darwin + "  " + SCRIPT_DIR_LINE + "fi\n" + GUARD,
                 'aws/link.sh: SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd) must come before'),
                ("guard above fi", darwin + SCRIPT_DIR_LINE + GUARD + "fi\n",
                 "aws/link.sh: the worktree guard must not be inside another if block")):
            with self.subTest(case=name):
                self.write("aws/link.sh", "#!/bin/bash -e\n" + text + LINK_BODY)
                self.assert_fails("FAIL link-guard", fragment)

    def test_rejected_prelude_block_reports_only_its_line(self):
        # 許さない複数行の if は、その行の失敗だけを出す。対応する fi で深さがずれ、ブロックの中だという誤った失敗を出さない。
        block = 'if ! command -v ghostty >/dev/null 2>&1; then\n  echo "Install ghostty."\n  exit 1\nfi\n'
        self.write("aws/link.sh", link_script(before=block))
        code, out = self.check()
        self.assertEqual(code, 1, out)
        section = out.split("FAIL link-guard\n", 1)[-1].split("\nPASS ", 1)[0]
        self.assertEqual(section.strip().splitlines(), [
            "aws/link.sh:3: only blank lines, comments, set, SCRIPT_DIR=... and if/echo/exit/fi checks may come before "
            "the worktree guard"], out)

    def test_unreadable_script_fails_per_file(self):
        # 1 本読めないだけで検査全体を 1 件の例外にせず、ほかのスクリプトも調べる。絶対パスは出さない。
        # 消したファイルは local-paths も読めずに例外になる（変更前からの動き）ので、link-guard の節だけを見る。
        self.write("ghostty/link.sh", "#!/bin/bash -e\n" + SCRIPT_DIR_LINE + LINK_BODY, add=False)
        for name, rel in (("not utf-8", "x/latin1.sh"), ("deleted before git add", "x/gone.sh")):
            with self.subTest(case=name):
                path = self.root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"# \xe9\nln -s a b\n")
                self.git("add", "--", rel)
                if name == "deleted before git add":
                    path.unlink()
                code, out = self.check()
                self.assertEqual(code, 1, out)
                section = out.split("FAIL link-guard\n", 1)[-1].split("\nPASS ", 1)[0].split("\nFAIL ", 1)[0]
                self.assertIn(f"{rel}: cannot read", section, out)
                self.assertIn("ghostty/link.sh: runs ln without the worktree guard", section, out)
                self.assertNotIn(str(self.root), section, out)
                self.git("rm", "-q", "-f", "--cached", "--", rel)
                path.unlink(missing_ok=True)

    def test_link_script_not_directly_under_top_level_fails(self):
        # 判定は $SCRIPT_DIR/../.git を見るので、ルートの 1 つ下にないと worktree の中でも偽になる。
        for rel in ("config/sf/link.sh", "link.sh", "claude/hooks/x.sh"):
            with self.subTest(rel=rel):
                self.write(rel, link_script())
                self.assert_fails("FAIL link-guard", f"{rel}: runs ln but is not directly under a top-level directory")
                self.git("rm", "-q", "-f", "--", rel)

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
