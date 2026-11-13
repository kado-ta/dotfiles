"""公開リポジトリとして守る不変条件、設定ファイルの構文、Markdown の規約を検査する。

使い方: python3 -B .github/scripts/check-repo.py [ROOT]
検査ごとに PASS / FAIL を出し、1 件でも失敗すれば終了コード 1 を返す。
対象は git が追跡しているファイルと、無視されていない未追跡のファイル。
CI は push の後に動くので、公開前に防ぐには push する前に手元で実行する。そのとき git add 前のファイルも見る。
"""

import json
import posixpath
import re
import shlex
import subprocess
import sys
import tomllib
import urllib.parse
from pathlib import Path, PurePosixPath

# 既存のプレースホルダー（codex/README.md の /Users/example と、cc-safe-push のテストの "/Users/some one"）。
PLACEHOLDER_USERS = {"example", "some"}
FORBIDDEN_FILES = ("aws/config", "aws/credentials")
INTERPRETERS = {"bash", "/bin/bash", "sh", "/bin/sh"}
CLAUDE_HOME = ("~/.claude/", "$HOME/.claude/", "${HOME}/.claude/")
# sandbox と権限の境界なので、完全一致で検査する。広げるときはここも一緒に変える。
WRAPPER_COMMANDS = (
    "/usr/local/libexec/claude-push/cc-safe-push",
    "/usr/local/libexec/claude-push/cc-safe-pr create",
    "/usr/local/libexec/claude-push/cc-safe-pr edit",
    "/usr/local/libexec/claude-crit/cc-crit review",
    "/usr/local/libexec/claude-crit/cc-crit reply",
)
# ラッパーを置くディレクトリ。permissions.allow のうち、ここを指す規則はすべて WRAPPER_COMMANDS と一致させる。
WRAPPER_RULE_PREFIX = "Bash(/usr/local/libexec/claude-"
# cc-crit の crit は、レビュー中のファイルの全文を ~/.cc-crit に書き出す。Claude の sandbox から読ませない。
# sandbox の外で動く crit は ~/.crit の hooks・prompts・レビューを信頼する。sandbox を通らない Edit・Write ツールでも書かせない。
CRIT_DENY = (
    "Read(~/.cc-crit/**)",
    "Edit(~/.crit/**)",
    "Edit(~/.crit.config.json)",
    "Edit(~/.cc-crit/**)",
)
CRIT_DENY_READ = ("~/.cc-crit",)
# Colima（Lima）の VM に SSH で入る鍵。Colima は $HOME を書き込み可能でマウントするので、VM に入れると sandbox を抜けられる。
LIMA_DENY = ("Read(~/.colima/_lima/_config/**)", "Read(~/.lima/_config/**)")
LIMA_DENY_READ = ("~/.colima/_lima/_config", "~/.lima/_config")
# Docker（Colima）のソケットや localhost の全ポートに、sandbox の中のすべてのコマンドから届くようにする設定。
FORBIDDEN_NETWORK = ("allowUnixSockets", "allowAllUnixSockets", "allowLocalBinding")
DENY_PUSH = ("Bash(git push)", "Bash(git push *)", "Bash(git -C * push *)", "Bash(git -c * push *)")
JSONC_FILES = {"vscode/settings.json", "vscode/keybindings.json"}
SETTINGS = "claude/settings.json"
PROJECT_SETTINGS = ".claude/settings.json"
# プロジェクト側には制限を足す設定だけを置く。権限を広げるキーは、未知のものも含めて失敗にする。
PROJECT_ALLOWED_KEYS = {
    "claudeMdExcludes",
    "permissions.ask",
    "permissions.deny",
    "sandbox.filesystem.denyWrite",
    "sandbox.filesystem.denyRead",
}
# 消すと dotfiles で起動したときの権限が広がる。外すときはここも一緒に変える。
PROJECT_ASK = (
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
)
PROJECT_DENY_WRITE = (
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
)

HOOK_SCRIPT = re.compile(r"\.claude/(?:hooks|scripts)/")
LOCAL_PATH = re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
INLINE_CODE = re.compile(r"(`+).+?(?<!`)\1(?!`)")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
EXPLICIT_ANCHOR = re.compile(r'<a\s+(?:name|id)="([^"]+)"')
LINK = re.compile(r'\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def repo_files(root):
    return [f for f in git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0") if f]


def tracked_modes(root):
    modes = {}
    for entry in git(root, "ls-files", "-s", "-z").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            modes[path] = meta.split()[0]
    return modes


def load_settings(root):
    return json.loads((root / SETTINGS).read_text(encoding="utf-8"))


def check_local_paths(root):
    errors = []
    for rel in repo_files(root):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(m.group(1) not in PLACEHOLDER_USERS for m in LOCAL_PATH.finditer(line)):
                # 公開される CI のログにユーザー名を出さないよう、パスそのものは表示しない。
                errors.append(f"{rel}:{lineno}: absolute path under /Users or /home with a real user name")
    return errors


def check_secret_files(root):
    tracked = set(repo_files(root))
    return [f"{rel}: must not be tracked" for rel in FORBIDDEN_FILES if rel in tracked]


def hook_commands(settings):
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                yield hook.get("command", "")
    status = settings.get("statusLine", {}).get("command")
    if status:
        yield status


def check_hook_scripts(root):
    settings = load_settings(root)
    modes = tracked_modes(root)
    errors = []
    for command in hook_commands(settings):
        if not HOOK_SCRIPT.search(command):
            continue
        tokens = shlex.split(command)
        direct = tokens[0] not in INTERPRETERS
        script = tokens[0] if direct else (tokens[1] if len(tokens) > 1 else "")
        rest = next((script[len(p):] for p in CLAUDE_HOME if script.startswith(p)), None)
        if rest is None or not rest.startswith(("hooks/", "scripts/")):
            # 飛ばすと、フックがなくても実行権限がなくても通ってしまう。
            errors.append(f"{SETTINGS}: cannot resolve the script path of a hook command: {command}")
            continue
        path = f"claude/{rest}"
        if path not in modes:
            errors.append(f"{SETTINGS}: {path} is not tracked (command: {command})")
        elif direct and modes[path] != "100755":
            errors.append(f"{path}: mode {modes[path]}, but {SETTINGS} runs it directly (needs 100755)")
    return errors


def check_push_permissions(root):
    settings = load_settings(root)
    permissions = settings.get("permissions", {})
    errors = []
    expected_allow = sorted(f"Bash({c})" for c in WRAPPER_COMMANDS)
    allow = sorted(rule for rule in permissions.get("allow", []) if rule.startswith(WRAPPER_RULE_PREFIX))
    if allow != expected_allow:
        errors.append(f"{SETTINGS}: permissions.allow has wrapper rules {allow}, expected {expected_allow}")
    excluded = sorted(settings.get("sandbox", {}).get("excludedCommands", []))
    if excluded != sorted(WRAPPER_COMMANDS):
        errors.append(f"{SETTINGS}: sandbox.excludedCommands is {excluded}, expected {sorted(WRAPPER_COMMANDS)}")
    deny = set(permissions.get("deny", []))
    errors += [f"{SETTINGS}: permissions.deny lacks {rule}" for rule in DENY_PUSH + CRIT_DENY + LIMA_DENY
               if rule not in deny]
    deny_read = settings.get("sandbox", {}).get("filesystem", {}).get("denyRead", [])
    errors += [f"{SETTINGS}: sandbox.filesystem.denyRead lacks {path}" for path in CRIT_DENY_READ + LIMA_DENY_READ
               if path not in deny_read]
    network = settings.get("sandbox", {}).get("network", {})
    errors += [f"{SETTINGS}: sandbox.network.{key} must not be set" for key in FORBIDDEN_NETWORK if network.get(key)]
    return errors


def key_paths(value, prefix=""):
    """dict を末端のキーのパス（a.b.c）に展開する。空の dict も末端として返す。"""
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from key_paths(child, f"{prefix}.{key}" if prefix else key)
    elif prefix:
        yield prefix


def check_project_permissions(root):
    settings = json.loads((root / PROJECT_SETTINGS).read_text(encoding="utf-8"))
    errors = [
        f"{PROJECT_SETTINGS}: {path} is not allowed (only settings that add restrictions belong here)"
        for path in key_paths(settings)
        if path not in PROJECT_ALLOWED_KEYS
    ]
    ask = set(settings.get("permissions", {}).get("ask", []))
    errors += [f"{PROJECT_SETTINGS}: permissions.ask lacks {rule}" for rule in PROJECT_ASK if rule not in ask]
    deny_write = set(settings.get("sandbox", {}).get("filesystem", {}).get("denyWrite", []))
    errors += [
        f"{PROJECT_SETTINGS}: sandbox.filesystem.denyWrite lacks {path}" for path in PROJECT_DENY_WRITE if path not in deny_write
    ]
    return errors


def check_syntax(root):
    errors = []
    for rel in repo_files(root):
        if rel.endswith(".json") and rel not in JSONC_FILES:
            try:
                json.loads((root / rel).read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"{rel}:{e.lineno}: {e.msg}")
        elif rel.endswith(".toml"):
            try:
                tomllib.loads((root / rel).read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                errors.append(f"{rel}: {e}")
    return errors


def check_markdown_names(root):
    return [
        f"{rel}: Markdown file names outside docs/ use only A-Z and _"
        for rel in repo_files(root)
        if rel.endswith(".md") and not rel.startswith("docs/") and not re.fullmatch(r"[A-Z_]+", PurePosixPath(rel).stem)
    ]


def prose_lines(text):
    """フェンスの中を空行にした行のリストを返す（行番号は保つ）。

    CommonMark と同じく、開いたフェンスと同じ文字で、同じか長いフェンスだけが閉じる。
    リストの中のフェンスも扱うため、インデントの深さは問わない。
    """
    lines, fence = [], None
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence = m.group(1)
            lines.append("" if fence else line)
        else:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                fence = None
            lines.append("")
    return lines


def slug(heading):
    """GitHub が見出しに付けるアンカー（重複の連番は付けない）。"""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def explicit_anchors(lines):
    return [name for line in lines for name in EXPLICIT_ANCHOR.findall(INLINE_CODE.sub("", line))]


def anchors(lines):
    found, seen = set(explicit_anchors(lines)), {}
    for line in lines:
        m = HEADING.match(line)
        if m:
            s = slug(m.group(1))
            n = seen.get(s, 0)
            seen[s] = n + 1
            found.add(s if n == 0 else f"{s}-{n}")
    return found


def check_markdown_links(root):
    files = repo_files(root)
    tracked = set(files)
    dirs = {str(p) for f in files for p in PurePosixPath(f).parents} - {"."}
    lines_cache, anchors_cache = {}, {}

    def lines_of(rel):
        if rel not in lines_cache:
            lines_cache[rel] = prose_lines((root / rel).read_text(encoding="utf-8"))
        return lines_cache[rel]

    def anchors_of(rel):
        if rel not in anchors_cache:
            anchors_cache[rel] = anchors(lines_of(rel))
        return anchors_cache[rel]

    errors = []
    for rel in files:
        if not rel.endswith(".md"):
            continue
        names = explicit_anchors(lines_of(rel))
        errors += [f"{rel}: duplicate anchor {name}" for name in sorted({n for n in names if names.count(n) > 1})]
        for lineno, line in enumerate(lines_of(rel), 1):
            for target in LINK.findall(INLINE_CODE.sub("", line)):
                if SCHEME.match(target):
                    continue
                path, _, fragment = target.partition("#")
                dest = rel
                if path:
                    dest = posixpath.normpath(posixpath.join(posixpath.dirname(rel), urllib.parse.unquote(path)))
                if dest not in tracked and dest not in dirs:
                    errors.append(f"{rel}:{lineno}: missing link target {target}")
                elif fragment and dest.endswith(".md") and urllib.parse.unquote(fragment) not in anchors_of(dest):
                    errors.append(f"{rel}:{lineno}: missing anchor {target}")
    return errors


CHECKS = (
    ("local-paths", check_local_paths),
    ("secret-files", check_secret_files),
    ("hook-scripts", check_hook_scripts),
    ("push-permissions", check_push_permissions),
    ("project-permissions", check_project_permissions),
    ("syntax", check_syntax),
    ("markdown-names", check_markdown_names),
    ("markdown-links", check_markdown_links),
)


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    failed = False
    for name, check in CHECKS:
        try:
            errors = check(root)
        except Exception as e:
            # 検査できないときは成功扱いにしない（fail closed）。
            errors = [f"error: {type(e).__name__}: {e}"]
        print(f"{'FAIL' if errors else 'PASS'} {name}")
        for error in errors:
            print(f"  {error}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
