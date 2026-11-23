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
# Edit・Write ツールは sandbox の外で動く。消すと、作業ディレクトリの外（ほかのリポジトリの .git/hooks、
# ~/Library/LaunchAgents など）にも、auto mode の判定だけで書ける。
WRITE_BLOCK = "blockWritesOutsideWorkingDirectories"
# 作業ディレクトリの中で、人間が操作しなくても sandbox の外で動くもの。外は WRITE_BLOCK が止める。
# hooks は、人間が git を使ったときに動く。
EDIT_DENY = ("Edit(**/.git/**/hooks/**)",)
# 接頭辞のない形は /add-dir で足したディレクトリにも当たる（2026-11-16 に実測）。文書は起点をカレントディレクトリと
# しているので、/cd などで起点が変わったときの備えに // の形も置く。deny にしない。Edit の deny は sandbox の denyWrite にもなり、// の形ではどこでも git init・git clone が
# hooks のサンプルを写せなくなる。ask は sandbox に変換されない。
EDIT_ASK = ("Edit(//**/.git/**/hooks/**)", "Edit(//**/.git/config)")
# mise が読む設定。信頼済みのパスの hooks・_.source・exec() は、人間が cd したときに動く。
MISE_CONFIG = (
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
)
MISE_ASK = tuple(f"Edit({p})" for p in MISE_CONFIG) + tuple(f"Edit(//{p})" for p in MISE_CONFIG)
# paranoid の土台は、どこで起動したセッションでも Bash（sandbox の中）から書かせない。グローバルの設定（paranoid でも
# パスで信頼される）、その実体、信頼の記録。ほかの mise の設定は paranoid が中身で守るので入れない（入れると、
# ほかのリポジトリの git の操作が途中で止まる）。sandbox のパスは、接頭辞がないとユーザー設定では ~/.claude が基準になるので、~/ を付ける。
MISE_DENY_WRITE = ("~/.config/mise", "~/dotfiles/mise", "~/.local/state/mise")
# 上の denyWrite は Bash しか止めない。Edit・Write ツールは、~ で起動したセッションでは作業ディレクトリの外を止める設定も
# 効かないので、規則でも止める。信頼の記録は Claude が書く理由がないので deny（sandbox の denyWrite にもなる）、
# グローバルの設定の実体は ask にする。~/.config/mise は MISE_ASK の **/.config/mise/** が当たる。
MISE_EDIT_DENY = ("Edit(~/.local/state/mise/**)",)
MISE_EDIT_ASK = ("Edit(~/dotfiles/mise/**)",)
# グローバルの mise 設定（~/.config/mise/config.toml の実体）。paranoid は、グローバルの設定でだけ効く。
MISE_GLOBAL_CONFIG = "mise/mise_config.toml"
# config は設定を、env_files は _.source などが読むファイルを、パスではなく中身で信頼させる。true（すべて）でもよい。
PARANOID_REQUIRED = ("config", "env_files")
# ユーザー設定のこれらのリストは、~/ でも / でも始まらないパスが ~/.claude を起点にし、黙って効かない。
SANDBOX_PATH_LISTS = ("denyRead", "denyWrite", "allowWrite", "allowRead")
# additionalDirectories は作業ディレクトリとして数えられ、そこでは WRITE_BLOCK が効かない。
# gstack の置き場所は sandbox の allowWrite にも入っていて、Bash はもともと書けるので、これだけを許す。
ADDITIONAL_DIRECTORIES = ("~/.gstack/projects",)
# その根が symlink に差し替えられているあいだ、Edit・Write 系のツールをすべて止めるフック。
# 既定ではフックの失敗（タイムアウトなど）でツールが通るので、onFailure を block にする。
GUARD_HOOK = "hooks/guard-additional-dirs.sh"
GUARD_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Playwright MCP は sandbox の外でユーザーの権限で動く。定義があるあいだは、任意のコードを動かすツールと
# プロジェクトのファイルをページに渡すツールを deny にし、ローカルのファイルを指す filename・paths 引数をフックで止める。
# matcher は完全一致で比べる（一部のツールにしか当たらないと、ほかのツールの filename・paths が通る）。
# ブラウザは localhost に届くので、cc-crit 以外の crit（プラグインの自動プランレビュー、ターミナルの crit）がランダムなポートを
# 書く ~/.crit も読ませない（ポートを知って開けば、承認を偽造できる）。プロジェクトの .mcp.json の playwright は、
# 強化した user スコープの定義を上書きするので拒否する。
PLAYWRIGHT_DEFINITION = "claude/mcp/playwright.json"
# 入れる場所（register-mcp.sh の packages_dir）と出力先（定義の --output-dir）。cli.js は次の MCP の起動時に sandbox の外で
# 動き、出力先は symlink で向け替えられる。リポジトリのルートで起動したセッションからは書けないが、~ で起動すると
# allowWrite の "." に入り、作業ディレクトリの外を止める設定も効かないので、mise と同じく denyWrite と Edit の deny で止める。
# Edit の deny も sandbox の denyWrite になるが、Edit を ask に緩めても Bash の守りが残るよう、denyWrite にも置く。
PLAYWRIGHT_OUTPUT_DIR = "~/Library/Caches/playwright-mcp"
PLAYWRIGHT_DENY_WRITE = ("~/.local/share/claude-mcp", PLAYWRIGHT_OUTPUT_DIR)
PLAYWRIGHT_DENY = (
    "mcp__playwright__browser_run_code_unsafe",
    "mcp__playwright__browser_file_upload",
    "Read(~/.crit/**)",
) + tuple(f"Edit({path}/**)" for path in PLAYWRIGHT_DENY_WRITE)
PLAYWRIGHT_DENY_READ = ("~/.crit",)
PLAYWRIGHT_SERVER = "playwright"
PLAYWRIGHT_HOOK = "hooks/guard-playwright-mcp.sh"
PLAYWRIGHT_MATCHER = "mcp__playwright__.*"
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


def blocking_hook(group, script):
    return any(hook.get("command", "").endswith(script) and hook.get("onFailure") == "block"
               for hook in group.get("hooks", []))


def guard_hook_registered(settings):
    for group in settings.get("hooks", {}).get("PreToolUse", []):
        # MultiEdit・NotebookEdit が Edit を含むので、部分一致ではなく | で分けて比べる。
        if not set(GUARD_TOOLS) <= set(group.get("matcher", "").split("|")):
            continue
        if blocking_hook(group, GUARD_HOOK):
            return True
    return False


def check_edit_permissions(root):
    settings = load_settings(root)
    permissions = settings.get("permissions", {})
    errors = []
    if permissions.get(WRITE_BLOCK) is not True:
        errors.append(f"{SETTINGS}: permissions.{WRITE_BLOCK} must be true")
    errors += [f"{SETTINGS}: permissions.additionalDirectories must not list {path}"
               for path in permissions.get("additionalDirectories", []) if path not in ADDITIONAL_DIRECTORIES]
    deny, ask = set(permissions.get("deny", [])), set(permissions.get("ask", []))
    errors += [f"{SETTINGS}: permissions.deny lacks {rule}" for rule in EDIT_DENY + MISE_EDIT_DENY if rule not in deny]
    errors += [f"{SETTINGS}: permissions.ask lacks {rule}" for rule in MISE_ASK + EDIT_ASK + MISE_EDIT_ASK
               if rule not in ask]
    errors += [f"{SETTINGS}: permissions.deny: {rule} must not be a deny rule" for rule in EDIT_ASK if rule in deny]
    filesystem = settings.get("sandbox", {}).get("filesystem", {})
    errors += [f"{SETTINGS}: sandbox.filesystem.allowWrite lacks {path} (listed in permissions.additionalDirectories)"
               for path in permissions.get("additionalDirectories", [])
               if path in ADDITIONAL_DIRECTORIES and path not in filesystem.get("allowWrite", [])]
    deny_write = filesystem.get("denyWrite", [])
    errors += [f"{SETTINGS}: sandbox.filesystem.denyWrite lacks {path}" for path in MISE_DENY_WRITE
               if path not in deny_write]
    if not guard_hook_registered(settings):
        errors.append(f"{SETTINGS}: hooks.PreToolUse lacks {GUARD_HOOK} for {'|'.join(GUARD_TOOLS)} with onFailure block")
    errors += [f"{SETTINGS}: sandbox.filesystem.{key} has an unprefixed path {path}"
               for key in SANDBOX_PATH_LISTS for path in filesystem.get(key, [])
               if not path.startswith(("~/", "/"))]
    return errors


def playwright_aliases(root):
    """claude/mcp/ の playwright.json 以外で、Playwright を起動しうる定義を返す。

    deny・フック・この検査はサーバー名 playwright に結び付いている。@playwright/mcp だけでなく、playwright・
    playwright-core の CLI の mcp サブコマンドでも同じサーバーが動くので、JSON を読み、大文字・小文字を区別せずに
    playwright を含む定義をすべて止める（JSON の \\/ のようなエスケープでも抜けないように、読んでから比べる）。
    """
    errors = []
    for path in sorted((root / PLAYWRIGHT_DEFINITION).parent.glob("*.json")):
        rel = path.relative_to(root).as_posix()
        if rel == PLAYWRIGHT_DEFINITION:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"{rel}: cannot be parsed as JSON")
            continue
        if "playwright" in json.dumps(data).lower():
            errors.append(f"{rel}: mentions Playwright under another server name; define it only in {PLAYWRIGHT_DEFINITION}")
    return errors


def check_playwright_mcp(root):
    errors = playwright_aliases(root)
    if not (root / PLAYWRIGHT_DEFINITION).exists():
        return errors
    settings = load_settings(root)
    deny = set(settings.get("permissions", {}).get("deny", []))
    errors += [f"{SETTINGS}: permissions.deny lacks {rule} (required while {PLAYWRIGHT_DEFINITION} exists)"
               for rule in PLAYWRIGHT_DENY if rule not in deny]
    deny_read = settings.get("sandbox", {}).get("filesystem", {}).get("denyRead", [])
    errors += [f"{SETTINGS}: sandbox.filesystem.denyRead lacks {path} (required while {PLAYWRIGHT_DEFINITION} exists)"
               for path in PLAYWRIGHT_DENY_READ if path not in deny_read]
    deny_write = settings.get("sandbox", {}).get("filesystem", {}).get("denyWrite", [])
    errors += [f"{SETTINGS}: sandbox.filesystem.denyWrite lacks {path} (required while {PLAYWRIGHT_DEFINITION} exists)"
               for path in PLAYWRIGHT_DENY_WRITE if path not in deny_write]
    # denyWrite は、実際の出力先と同じパスのときだけ効く。--output-dir=… の形や 2 回目の指定は、照合しにくいので失敗にする。
    args = json.loads((root / PLAYWRIGHT_DEFINITION).read_text(encoding="utf-8")).get("args", [])
    output_dir = PLAYWRIGHT_OUTPUT_DIR.replace("~", "${HOME}", 1)
    given = [arg for arg in args if arg.startswith("--output-dir")]
    i = args.index("--output-dir") if given == ["--output-dir"] else -1
    if i < 0 or args[i + 1:i + 2] != [output_dir]:
        errors.append(f"{PLAYWRIGHT_DEFINITION}: --output-dir must be given once as {output_dir} "
                      f"(the path in sandbox.filesystem.denyWrite)")
    if PLAYWRIGHT_SERVER not in settings.get("disabledMcpjsonServers", []):
        errors.append(f"{SETTINGS}: disabledMcpjsonServers lacks {PLAYWRIGHT_SERVER} "
                      f"(required while {PLAYWRIGHT_DEFINITION} exists)")
    if not any(group.get("matcher") == PLAYWRIGHT_MATCHER and blocking_hook(group, PLAYWRIGHT_HOOK)
               for group in settings.get("hooks", {}).get("PreToolUse", [])):
        errors.append(f"{SETTINGS}: hooks.PreToolUse lacks {PLAYWRIGHT_HOOK} for {PLAYWRIGHT_MATCHER} "
                      f"with onFailure block (required while {PLAYWRIGHT_DEFINITION} exists)")
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


def check_mise_paranoid(root):
    path = root / MISE_GLOBAL_CONFIG
    if not path.exists():
        return [f"{MISE_GLOBAL_CONFIG}: missing"]
    paranoid = tomllib.loads(path.read_text(encoding="utf-8")).get("settings", {}).get("paranoid")
    # 文字列は部分一致で通ってしまうので、リストのときだけ中身を見る。
    if paranoid is True or (isinstance(paranoid, list) and all(c in paranoid for c in PARANOID_REQUIRED)):
        return []
    return [f"{MISE_GLOBAL_CONFIG}: settings.paranoid must be true or a list with {', '.join(PARANOID_REQUIRED)}"]


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
    ("edit-permissions", check_edit_permissions),
    ("playwright-mcp", check_playwright_mcp),
    ("project-permissions", check_project_permissions),
    ("mise-paranoid", check_mise_paranoid),
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
