"""公開リポジトリとして守る不変条件、設定ファイルの構文、Markdown の規約を検査する。

使い方: python3 -B .github/scripts/check-repo.py [ROOT]
検査ごとに PASS / FAIL を出し、1 件でも失敗すれば終了コード 1 を返す。
対象は git が追跡しているファイルと、無視されていない未追跡のファイル。
CI は push の後に動くので、公開前に防ぐには push する前に手元で実行する。そのとき git add 前のファイルも見る。
"""

import importlib.machinery
import importlib.util
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

# checkout guard（root 所有でインストールして使う）の元のファイルと、WorktreeCreate フックのコマンド。
CHECKOUT_GUARD = "claude/bin/cc-checkout-guard"
CHECKOUT_GUARD_COMMAND = "/usr/local/libexec/claude-guard/cc-checkout-guard worktree-create"
# ガードの関数が zsh に入っていること。mise の初期化より後でなければ、git が mise の shim に上書きされうる。
ZSHRC = "bin/.zshrc"
ZSHRC_BLOCK = (
    "# >>> cc-checkout-guard",
    "git() {",
    "local guard=/usr/local/libexec/claude-guard/cc-checkout-guard",
    "# <<< cc-checkout-guard",
)
ZSHRC_AFTER = 'eval "$(mise activate zsh)"'
# ガードの対象に必ず含める一般パターン（ガード側の定数の部分集合であること）。
GUARD_REQUIRED_DIRS = (".claude", ".vscode", ".idea")
GUARD_REQUIRED_NAMES = (".mcp.json", "mise.lock")
GUARD_REQUIRED_PREFIXES = (".env",)
# mise.lock は mise が sandbox の外で読むので、Edit も止める。
MISE_LOCK_DENY = ("Edit(**/mise.lock)",)
# 環境変数で paranoid や信頼済みパスを上書きさせない。
MISE_ENV_FORBIDDEN = ("MISE_TRUSTED_CONFIG_PATHS", "MISE_PARANOID")
MISE_ENV_FILES = ("bin/.zshrc", "bin/.zprofile", "mise/mise_config.toml")  # ほかに zsh/*.zsh

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


def guard_hook_registered(settings):
    for group in settings.get("hooks", {}).get("PreToolUse", []):
        # MultiEdit・NotebookEdit が Edit を含むので、部分一致ではなく | で分けて比べる。
        if not set(GUARD_TOOLS) <= set(group.get("matcher", "").split("|")):
            continue
        if any(hook.get("command", "").endswith(GUARD_HOOK) and hook.get("onFailure") == "block"
               for hook in group.get("hooks", [])):
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
    errors += [f"{SETTINGS}: permissions.deny lacks {rule}" for rule in EDIT_DENY + MISE_EDIT_DENY + MISE_LOCK_DENY
               if rule not in deny]
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
    config = tomllib.loads(path.read_text(encoding="utf-8")).get("settings", {})
    paranoid = config.get("paranoid")
    errors = []
    # 文字列は部分一致で通ってしまうので、リストのときだけ中身を見る。
    if not (paranoid is True or (isinstance(paranoid, list) and all(c in paranoid for c in PARANOID_REQUIRED))):
        errors.append(f"{MISE_GLOBAL_CONFIG}: settings.paranoid must be true or a list with {', '.join(PARANOID_REQUIRED)}")
    # 空のリストでも、パスによる信頼の経路を開く。
    if "trusted_config_paths" in config:
        errors.append(f"{MISE_GLOBAL_CONFIG}: settings.trusted_config_paths must not be set")
    for rel in MISE_ENV_FILES + tuple(sorted(p.relative_to(root).as_posix() for p in (root / "zsh").glob("*.zsh"))):
        file = root / rel
        if file.is_file():
            text = file.read_text(encoding="utf-8")
            errors += [f"{rel}: must not mention {name}" for name in MISE_ENV_FORBIDDEN if name in text]
    return errors


def check_checkout_guard(root):
    errors = []
    try:
        loader = importlib.machinery.SourceFileLoader("cc_checkout_guard", str(root / CHECKOUT_GUARD))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        guard = importlib.util.module_from_spec(spec)
        loader.exec_module(guard)
        pairs = (
            (PROJECT_DENY_WRITE, "DOTFILES_PROTECTED"),
            (GUARD_REQUIRED_DIRS, "PROTECTED_DIRS"),
            (GUARD_REQUIRED_NAMES, "PROTECTED_NAMES"),
            (GUARD_REQUIRED_PREFIXES, "PROTECTED_PREFIXES"),
        )
        for required, name in pairs:
            errors += [f"{CHECKOUT_GUARD}: {name} lacks {item}" for item in required if item not in getattr(guard, name)]
    except Exception as e:
        errors.append(f"{CHECKOUT_GUARD}: cannot load: {type(e).__name__}: {e}")
    commands = [hook.get("command") for group in load_settings(root).get("hooks", {}).get("WorktreeCreate", [])
                for hook in group.get("hooks", [])]
    if commands != [CHECKOUT_GUARD_COMMAND]:
        errors.append(f"{SETTINGS}: hooks.WorktreeCreate must be exactly [{CHECKOUT_GUARD_COMMAND}], got {commands}")
    lines = [line.strip() for line in (root / ZSHRC).read_text(encoding="utf-8").splitlines()]
    after = next((i for i, line in enumerate(lines) if line == ZSHRC_AFTER), None)
    position = -1
    for expected in ZSHRC_BLOCK:
        position = next((i for i in range(position + 1, len(lines)) if lines[i] == expected), None)
        if position is None:
            errors.append(f"{ZSHRC}: lacks '{expected}' in the checkout guard block (in order)")
            break
        if expected == ZSHRC_BLOCK[0] and (after is None or position < after):
            errors.append(f"{ZSHRC}: the checkout guard block must come after {ZSHRC_AFTER}")
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
    ("edit-permissions", check_edit_permissions),
    ("project-permissions", check_project_permissions),
    ("mise-paranoid", check_mise_paranoid),
    ("checkout-guard", check_checkout_guard),
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
