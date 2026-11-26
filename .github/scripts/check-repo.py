"""公開リポジトリとして守る不変条件、設定ファイルの構文、Markdown の規約、手元と CI の検査ツールの版を検査する。

使い方: python3 -B .github/scripts/check-repo.py [ROOT]
検査ごとに PASS / FAIL を出し、1 件でも失敗すれば終了コード 1 を返す。
対象は git が追跡しているファイルと、無視されていない未追跡のファイル。作業ツリーで消したが index に残るファイルは、
中身を読めないので local-paths が FAIL にし、中身を読むほかの検査は飛ばす（名前を見る検査は調べる）。
CI は push の後に動くので、公開前に防ぐには push する前に手元で実行する。そのとき git add 前のファイルも見る。
"""

import getpass
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.parse
from pathlib import Path, PurePosixPath

# 既存のプレースホルダー（codex/README.md の /Users/example と、cc-safe-push のテストの "/Users/some one"）。
PLACEHOLDER_USERS = {"example", "some"}
FORBIDDEN_FILES = ("aws/config", "aws/credentials")
GITLEAKS_TIMEOUT = 120
# 見つかったときの終了コード。1 はエラー、2 は Go の panic と重なるので避ける。
GITLEAKS_LEAKS_EXIT = 42
CI_WORKFLOW = ".github/workflows/ci.yaml"
# CI が版を固定して入れるツール（名前、ci.yaml の env のキーの接頭辞、版を出す引数）。
CI_TOOLS = (
    ("shellcheck", "SHELLCHECK", "--version"),
    ("actionlint", "ACTIONLINT", "--version"),
    ("zizmor", "ZIZMOR", "--version"),
    ("gitleaks", "GITLEAKS", "version"),
)
TOOL_VERSION_TIMEOUT = 10
TOOL_VERSION = re.compile(r"\d+\.\d+\.\d+")
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
# 環境変数で paranoid や信頼するパスを上書きさせない。zsh の起動で読まれる設定とグローバルの設定に書かせない。
# bin/link.sh は bin/.??* をすべて ~ にリンクするので、bin/.z* は zsh が読む。sheldon の inline も zsh の起動で動く。
MISE_ENV_FORBIDDEN = ("MISE_TRUSTED_CONFIG_PATHS", "MISE_PARANOID")
MISE_ENV_FILES = (MISE_GLOBAL_CONFIG, "config/sheldon/plugins.toml")
MISE_ENV_GLOBS = ("bin/.z*", "zsh/*.zsh")
# グローバルの git の設定（~/.gitconfig の実体）。rerere が動くと、sandbox の外の git が、.git/rr-cache と MERGE_RR（どちらも
# sandbox が書ける）の解決を任意のパス（作業ツリーの外も）に書く。rerere.enabled がなくても、rr-cache があれば動くので false にする。
GITCONFIG = "bin/.gitconfig"
# リンク用のスクリプトの worktree の判定（PR #124）。worktree の中から実行すると、リンクが worktree を指し、worktree を
# 消すと警告なしに切れる。CI はスクリプトを動かさないので、書き方で確かめる。誤操作を防ぐためのもので、わざと崩した書き方は通る。
# 対象は ln を呼ぶ *.sh。hook のテストは一時ディレクトリの中にリンクを作るので除く。\ln・`ln …`・LN="ln"・"/bin/ln"・
# ln>/dev/null の形も対象にする（文字列の中の ln も当たるが、漏れて黙って通るより、誤って失敗して除外に足すほうを選ぶ）。
LINK_GUARD_EXEMPT = ("claude/hooks/tests/",)
LN_COMMAND = re.compile(r"(?:^|[\s;&|(`\"'=\\])(?:\S*/)?ln(?:[\s;&|()<>`\"']|$)")
SHELL_BLANK_OR_COMMENT = re.compile(r"\s*(?:#.*)?")
# 判定は $SCRIPT_DIR/../.git を見るので、スクリプトはルートの 1 つ下に置く。インデントした判定と、前置きの if の中の判定は、
# 実行されないことがあるので数えない。
LINK_GUARD = re.compile(r'if \[ -f "\$(?:SCRIPT_DIR|\{SCRIPT_DIR\})/\.\./\.git" \]; then\s*')
LINK_GUARD_SCRIPT_DIR = re.compile(r'\s*SCRIPT_DIR=\$\(cd "\$\(dirname "\$0"\)" && pwd\)\s*')
# 引用符の中の \" は文字列を閉じない。行末の \" で次の行へ続く文字列（その中の exit 1）を echo として数えない。
LINK_GUARD_ECHO = re.compile(r'\s*echo "(?:[^"\\]|\\.)*"(?: >&2)?\s*')
# パイプやリダイレクトの付かない fi（後ろのコメントは可）。
SHELL_FI_LINE = re.compile(r"\s*fi\s*(?:#.*)?")
# 判定より前に置いてよい行（set と、macOS や CLAUDECODE の確認の部品）。書き込むコマンドはツールの呼び出しも含めて
# 並べきれないので、許す行を決める。判定の本体も同じく、echo とコメントの後の exit 1 だけを数える（抜け道の || {、
# 継続行、case、入れ子の if・else の中の exit 1 は、条件しだいで実行されない）。
LINK_GUARD_PRELUDE = (
    SHELL_BLANK_OR_COMMENT,
    LINK_GUARD_SCRIPT_DIR,
    LINK_GUARD_ECHO,
    re.compile(r"\s*set(?:\s+[-+][A-Za-z]+|\s+[a-z]+)+\s*"),
    re.compile(r"\s*if \[ [^;&|<>`]* \] ?; then\s*"),
    re.compile(r"\s*exit [0-9]+\s*"),
    SHELL_FI_LINE,
)
# 前置きの if の深さを数えるための fi と、1 行で閉じる if（…; fi）。
SHELL_FI = re.compile(r"\s*fi\b")
SHELL_ONE_LINE_FI = re.compile(r";\s*fi\b")
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
# Obsidian の Vault。.obsidian/plugins のコードは、次に Obsidian が起動したとき sandbox の外で動き、その設定（data.json など）
# には認証情報がある。.obsidian の中の symlink はリンク自体を差し替えられるので、.obsidian ごと書かせない。Vault を
# 動かしても外れないよう、場所を問わず名前で判定する。Vault の .gitignore で .obsidian を外すと、sandbox の外の
# obsidian-git がプラグインの設定をコミットし、git のオブジェクトから読めるので、.gitignore も Bash から書かせず、
# Edit は ask にする。Vault は ~/Obsidian の直下に置く決まりなので、.gitignore はそこに絞る。denyWrite・denyRead は
# Bash しか止めないので、Edit・Read ツールは規則で止める。
OBSIDIAN_DENY_WRITE = ("/**/.obsidian", "~/Obsidian/*/.gitignore")
OBSIDIAN_DENY_READ = ("/**/.obsidian/plugins",)
OBSIDIAN_DENY = ("Edit(//**/.obsidian/**)", "Read(//**/.obsidian/plugins/**)")
OBSIDIAN_ASK = ("Edit(~/Obsidian/*/.gitignore)",)
# 上流から取り込んだスキル。claude/scripts/update-modern-web-guidance.py が npm の配布物から書く。
# SKILL.md が参照ファイルを名前で指すので、上流の名前のまま置き、markdown-names の対象から外す。
VENDORED_SKILLS = ("claude/skills/modern-web-guidance/", "claude/skills/chrome-extensions/")
# modern-web-guidance のガイドと上流の SKILL.md は、npx 系で最新版を取得して動かすよう指示する。スキルがあるあいだは
# deny にして、mise で固定した CLI を迂回させない。npm は exec の別名（x）や npm i もあるので、サブコマンドを問わない。
# Bash の規則は、絶対パスや sh -c で包んだ形には当たらない（境界ではなく、ふだんの形を止める）。
MWG_SKILL = "claude/skills/modern-web-guidance/SKILL.md"
MWG_DENY = (
    "Bash(npx *modern-web-guidance*)",
    "Bash(pnpx *modern-web-guidance*)",
    "Bash(pnpm *modern-web-guidance*)",
    "Bash(bunx *modern-web-guidance*)",
    "Bash(bun *modern-web-guidance*)",
    "Bash(yarn *modern-web-guidance*)",
    "Bash(npm *modern-web-guidance*)",
    "Bash(deno *modern-web-guidance*)",
)
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
# パスの先頭がシェルの変数（$T・${T}）なら、その変数の下の階層なので外す。パスの途中の /Users/ でも、
# /Volumes/Backup/Users/<名前> のように実在するユーザー名でありうるので、外すのは変数の直後だけにする。
# 直前が / や名前の文字の $ は、変数ではなくディレクトリ名の一部（/Volumes/$Archive/Users/<名前>）なので外さない。
# 変数が実在のマウント先を表すこともあるので、実行しているユーザーのログイン名は、変数の直後でも止める。
# 名前は先読みにして読み進めない（$X/home/Users/<名前> の /Users/<名前> も調べる）。
LOCAL_PATH = re.compile(r"((?<![\w/.-])\$(?:\w+|\{\w+\}))?/(Users|home)(?=/([A-Za-z0-9._-]+))")
LOGIN = getpass.getuser()
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
INLINE_CODE = re.compile(r"(`+).+?(?<!`)\1(?!`)")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
EXPLICIT_ANCHOR = re.compile(r'<a\s+(?:name|id)="([^"]+)"')
LINK = re.compile(r'\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def in_worktree(path):
    # 消えたとみなすのはファイルがないときだけ。権限で調べられないものは残し、読む検査で失敗させる（壊れた symlink も残る）。
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        pass
    return True


def repo_files(root, include_deleted=False):
    files = [f for f in git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0") if f]
    # 作業ツリーで消したが index に反映していないファイルは、読めないので既定では除く。
    return files if include_deleted else [f for f in files if in_worktree(root / f)]


def tracked_modes(root):
    modes = {}
    for entry in git(root, "ls-files", "-s", "-z").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            modes[path] = meta.split()[0]
    return modes


def load_settings(root):
    return json.loads((root / SETTINGS).read_text(encoding="utf-8"))


def has_real_user_path(text):
    for m in LOCAL_PATH.finditer(text):
        variable, base, name = m.groups()
        # /Users/Shared は macOS の全ユーザーの共有フォルダ。/home の下の Shared はアカウントでありうるので外さない。
        if name in PLACEHOLDER_USERS or (base, name) == ("Users", "Shared"):
            continue
        if variable is None or name == LOGIN:
            return True
    return False


def check_local_paths(root):
    errors = []
    real_root = root.resolve()
    for rel in repo_files(root, include_deleted=True):
        path = root / rel
        # 作業ツリーで消しても、index に残っていればコミットに入る。中身を読めないので、黙って通さない。
        if not in_worktree(path):
            errors.append(f"{rel}: deleted from the working tree but still in the index (git rm it or restore it)")
            continue
        # 公開されるのはリンクの文字列なので、リンク先ではなくそれを調べる。
        # 公開される CI のログにユーザー名を出さないよう、パスそのものは表示しない。
        if path.is_symlink():
            if has_real_user_path(os.readlink(path)):
                errors.append(f"{rel}: symlink target is an absolute path under /Users or /home with a real user name")
            continue
        # 途中のディレクトリが symlink のファイルは、実体がリポジトリの外にあるので読まない。
        if not path.resolve().is_relative_to(real_root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if has_real_user_path(line):
                errors.append(f"{rel}:{lineno}: absolute path under /Users or /home with a real user name")
    return errors


def check_secret_files(root):
    # 作業ツリーで消しただけのファイルも、index に残っていればコミットに入る。
    tracked = set(repo_files(root, include_deleted=True))
    return [f"{rel}: must not be tracked" for rel in FORBIDDEN_FILES if rel in tracked]


# gitleaks dir は .gitignore を見ず、読めないファイルは警告だけ出して飛ばす。
# 対象のファイルだけを一時ディレクトリに写してから調べ、読めなければ写す時点で失敗させる。
# 写した先を cwd にして . を調べ、allowlist の paths がリポジトリからの相対パスに当たるようにする
# （絶対パスだと、一時ディレクトリの名前に当たる除外で全ファイルが外れる）。
def check_secret_content(root):
    exe = shutil.which("gitleaks")
    if exe is None:
        return ["gitleaks not found (install it with brew install gitleaks)"]
    with tempfile.TemporaryDirectory(prefix="check-repo-gitleaks-") as tmp:
        base = Path(tmp).resolve()
        src = base / "src"
        src.mkdir()
        report = base / "report.json"
        real_root = root.resolve()
        for rel in repo_files(root):
            path = root / rel
            # 公開されるのはリンクの文字列なので、symlink とその先（途中のディレクトリが symlink の場合も）は読まない。
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(real_root):
                continue
            # gitleaks は対象のルートの .gitleaksignore も読む。一時ディレクトリが大文字小文字を区別しないと
            # .GITLEAKSIGNORE なども読むので、大文字小文字を区別せずに写さない。
            if rel.casefold() == ".gitleaksignore":
                continue
            dest = src / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
        cmd = [exe, "dir", ".", "--no-banner", "--redact", "--report-format", "json",
               "--report-path", str(report), "--exit-code", str(GITLEAKS_LEAKS_EXIT)]
        # 名前（.gitleaks）で探させると .gitleaks.json などが先に読まれるので、.gitleaks.toml に固定する。
        config = src / ".gitleaks.toml"
        if config.is_file():
            # 設定を渡すと既定のルールは使われないので、継承していない設定では全件を見逃す。
            # 読めない設定は gitleaks に渡し、gitleaks のエラーで FAIL にする。
            try:
                extend = tomllib.loads(config.read_text(encoding="utf-8")).get("extend", {})
            except tomllib.TOMLDecodeError:
                extend = {"useDefault": True}
            if extend.get("useDefault") is not True:
                return [".gitleaks.toml: [extend] useDefault = true is required"]
            cmd += ["--config", str(config)]
        # 手元の環境変数で設定が差し替わらないようにする。ログの色は --no-color では消えないので NO_COLOR で消す。
        env = {k: v for k, v in os.environ.items() if k not in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")}
        env["NO_COLOR"] = "1"
        # CI のログは公開されるので、パスは出さない（TimeoutExpired・OSError のメッセージにはパスが入る）。
        try:
            cp = subprocess.run(cmd, cwd=src, env=env, capture_output=True, text=True, timeout=GITLEAKS_TIMEOUT)
        except (subprocess.TimeoutExpired, OSError) as e:
            return [f"error: cannot run gitleaks ({type(e).__name__})"]
        if cp.returncode not in (0, GITLEAKS_LEAKS_EXIT):
            return [f"error: gitleaks exited with {cp.returncode}", *cp.stderr.splitlines()]
        # CI のログは公開されるので、Secret と Match は出さない。
        errors = sorted(
            f"{(src / f['File']).resolve().relative_to(src)}:{f['StartLine']}: {f['RuleID']}"
            for f in json.loads(report.read_text(encoding="utf-8"))
        )
    if cp.returncode == GITLEAKS_LEAKS_EXIT and not errors:
        return ["error: gitleaks reported leaks but the report is empty"]
    return errors


def version_key(version):
    return tuple(int(n) for n in version.split("."))


# 手元（Homebrew）は版を固定しないので、brew upgrade で CI と黙ってずれないよう、PATH のツールの版を ci.yaml と比べる。
def check_tool_versions(root):
    path = root / CI_WORKFLOW
    if not path.is_file():
        return [f"{CI_WORKFLOW}: missing"]
    text = path.read_text(encoding="utf-8")
    errors = []
    for name, prefix, arg in CI_TOOLS:
        # 標準ライブラリに YAML の parser がないので、env の行を正規表現で読む。引用符と行末のコメントは外す。
        pinned = re.findall(rf"^[ \t]*{prefix}_VERSION:[ \t]*(\S+?)(?:[ \t]+#.*)?[ \t]*$", text, re.MULTILINE)
        if len(pinned) != 1:
            errors.append(f"{CI_WORKFLOW}: {prefix}_VERSION must be set exactly once")
            continue
        expected = pinned[0].strip("\"'").removeprefix("v")
        if not TOOL_VERSION.fullmatch(expected):
            errors.append(f"{CI_WORKFLOW}: cannot read {prefix}_VERSION as a version")
            continue
        exe = shutil.which(name)
        if exe is None:
            errors.append(f"{name} not found (install it with brew install {name})")
            continue
        # CI のログは公開されるので、ツールのパスは出さない（TimeoutExpired・OSError のメッセージにはパスが入る）。
        try:
            cp = subprocess.run([exe, arg], capture_output=True, text=True, timeout=TOOL_VERSION_TIMEOUT)
        except (subprocess.TimeoutExpired, OSError):
            errors.append(f"cannot read the version of {name}")
            continue
        found = TOOL_VERSION.search(cp.stdout)
        if cp.returncode != 0 or found is None:
            errors.append(f"cannot read the version of {name}")
        elif found.group() != expected:
            # 手元が古いときに CI を上げる案内をすると、CI の版を下げてしまう（ほかの Mac で先に上げたときなど）。
            local_newer = version_key(found.group()) > version_key(expected)
            hint = (f"update {prefix}_VERSION and {prefix}_SHA256 together in a separate PR" if local_newer
                    else f"run brew upgrade {name}")
            errors.append(f"{name} {found.group()} on PATH, but {CI_WORKFLOW} pins {expected} ({hint})")
    return errors


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


def check_obsidian_vault(root):
    settings = load_settings(root)
    permissions = settings.get("permissions", {})
    filesystem = settings.get("sandbox", {}).get("filesystem", {})
    deny, ask = set(permissions.get("deny", [])), set(permissions.get("ask", []))
    errors = [f"{SETTINGS}: sandbox.filesystem.denyWrite lacks {path}"
              for path in OBSIDIAN_DENY_WRITE if path not in filesystem.get("denyWrite", [])]
    errors += [f"{SETTINGS}: sandbox.filesystem.denyRead lacks {path}"
               for path in OBSIDIAN_DENY_READ if path not in filesystem.get("denyRead", [])]
    errors += [f"{SETTINGS}: permissions.deny lacks {rule}" for rule in OBSIDIAN_DENY if rule not in deny]
    errors += [f"{SETTINGS}: permissions.ask lacks {rule}" for rule in OBSIDIAN_ASK if rule not in ask]
    return errors


def check_modern_web_guidance(root):
    if not (root / MWG_SKILL).exists():
        return []
    deny = set(load_settings(root).get("permissions", {}).get("deny", []))
    return [f"{SETTINGS}: permissions.deny lacks {rule} (required while {MWG_SKILL} exists)"
            for rule in MWG_DENY if rule not in deny]


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
    # パスを入れると paranoid でも中身を確かめずに信頼される。空のリストは既定値と同じだが、キーごと置かせない。
    if "trusted_config_paths" in config:
        errors.append(f"{MISE_GLOBAL_CONFIG}: settings.trusted_config_paths must not be set")
    for rel in MISE_ENV_FILES + tuple(sorted(p.relative_to(root).as_posix() for g in MISE_ENV_GLOBS for p in root.glob(g))):
        file = root / rel
        if file.is_file():
            text = file.read_text(encoding="utf-8")
            errors += [f"{rel}: must not mention {name}" for name in MISE_ENV_FORBIDDEN if name in text]
    return errors


def check_rerere(root):
    # git と同じく読む（最後の値が勝つ。no・0 も false）。ファイルやキーがなければ終了コード 1、bool でなければ 128。
    cp = subprocess.run(["git", "config", "--file", str(root / GITCONFIG), "--type=bool", "--get", "rerere.enabled"],
                        capture_output=True, text=True)
    if cp.returncode != 0 or cp.stdout.strip() != "false":
        return [f"{GITCONFIG}: rerere.enabled must be false"]
    # include は書いた位置で読み込まれ、後の値が勝つ。--file は include をたどらないので、include が後ろにあれば失敗にする。
    keys = git(root, "config", "--file", GITCONFIG, "--null", "--name-only", "--list").split("\0")
    last = max(i for i, key in enumerate(keys) if key == "rerere.enabled")
    if any(key == "include.path" or (key.startswith("includeif.") and key.endswith(".path")) for key in keys[last + 1:]):
        return [f"{GITCONFIG}: rerere.enabled must come after every include.path and includeif.*.path"]
    return []


def guard_exits(lines):
    """判定の if の次の行から、空行・コメント・echo "…" だけを挟んで exit 1 があり、次の行がただの fi か。

    fi にパイプなどが付くと、if 全体が子シェルで動き、exit 1 は子シェルだけを終える。
    """
    exited = False
    for line in lines:
        if SHELL_BLANK_OR_COMMENT.fullmatch(line):
            continue
        if exited:
            return bool(SHELL_FI_LINE.fullmatch(line))
        if line.strip() == "exit 1":
            exited = True
        elif not LINK_GUARD_ECHO.fullmatch(line):
            return False
    return False


def check_link_guard(root):
    errors = []
    for rel in repo_files(root):
        if not rel.endswith(".sh") or rel.startswith(LINK_GUARD_EXEMPT):
            continue
        try:
            lines = (root / rel).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            # 1 本読めないだけで、ほかのスクリプトの結果を隠さない。CI のログは公開されるので、例外の本文（絶対パス）は出さない。
            errors.append(f"{rel}: cannot read ({type(e).__name__}), so the worktree guard is not checked")
            continue
        if not any(LN_COMMAND.search(line) for line in lines if not SHELL_BLANK_OR_COMMENT.fullmatch(line)):
            continue
        if len(PurePosixPath(rel).parts) != 2:
            errors.append(f"{rel}: runs ln but is not directly under a top-level directory "
                          "(the worktree guard checks $SCRIPT_DIR/../.git)")
        start = next((i for i, line in enumerate(lines) if LINK_GUARD.fullmatch(line)), None)
        if start is None or not guard_exits(lines[start + 1:]):
            errors.append(f'{rel}: runs ln without the worktree guard (if [ -f "$SCRIPT_DIR/../.git" ]; then '
                          'followed by only echo "..." lines and exit 1)')
            continue
        depth, script_dir = 0, False
        for n, line in enumerate(lines[:start], 1):
            if not any(p.fullmatch(line) for p in LINK_GUARD_PRELUDE):
                errors.append(f"{rel}:{n}: only blank lines, comments, set, SCRIPT_DIR=... and if/echo/exit/fi checks "
                              "may come before the worktree guard")
            # 前置きの if の中の SCRIPT_DIR= は、条件しだいで実行されない。
            elif depth == 0 and LINK_GUARD_SCRIPT_DIR.fullmatch(line):
                script_dir = True
            # 許さない行の if も数え、対応する fi で深さがずれないようにする。
            if line.split()[:1] == ["if"] and not SHELL_ONE_LINE_FI.search(line):
                depth += 1
            elif SHELL_FI.match(line):
                depth -= 1
        if depth != 0:
            errors.append(f"{rel}: the worktree guard must not be inside another if block")
        if not script_dir:
            errors.append(f'{rel}: SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd) must come before the worktree guard, '
                          "outside any if block")
    return errors


def strip_jsonc(text):
    """JSONC のコメントと、閉じ括弧の直前の末尾のカンマを空白に替える。改行は残すので、行番号はずれない。

    閉じていないブロックコメントと、要素の後でないカンマ（{,} など）は VSCode でも誤りなので、そのまま残して
    json.loads に誤りとして報告させる。
    """
    out = list(text)
    i, n = 0, len(text)
    last = None  # 文字列とコメントの外の、直前の空白でない文字（文字列は '"'）。
    comma = None  # 要素の後の最後のカンマ。後に空白とコメントしか続かないあいだだけ保つ。
    while i < n:
        if text[i] == '"':
            comma, last = None, '"'
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
            i += 1
        elif text.startswith(("//", "/*"), i):
            line_comment = text[i + 1] == "/"
            end = text.find("\n" if line_comment else "*/", i + 2)
            if end == -1:
                if not line_comment:
                    break
                end = n
            elif not line_comment:
                end += 2
            for j in range(i, end):
                if out[j] != "\n":
                    out[j] = " "
            i = end
        else:
            ch = text[i]
            if ch == ",":
                comma = None if last in (None, "{", "[", ",") else i
            elif ch in "}]" and comma is not None:
                out[comma] = " "
                comma = None
            elif not ch.isspace():
                comma = None
            if not ch.isspace():
                last = ch
            i += 1
    return "".join(out)


def check_syntax(root):
    errors = []
    for rel in repo_files(root):
        if rel.endswith(".json"):
            try:
                text = (root / rel).read_text(encoding="utf-8")
                json.loads(strip_jsonc(text) if rel in JSONC_FILES else text)
            except json.JSONDecodeError as e:
                errors.append(f"{rel}:{e.lineno}: {e.msg}")
        elif rel.endswith(".toml"):
            try:
                tomllib.loads((root / rel).read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                errors.append(f"{rel}: {e}")
    return errors


def check_markdown_names(root):
    # 名前だけを見るので、作業ツリーで消しても index に残る（コミットに入る）ファイルも調べる。
    return [
        f"{rel}: Markdown file names outside docs/ use only A-Z and _"
        for rel in repo_files(root, include_deleted=True)
        if rel.endswith(".md") and not rel.startswith(("docs/",) + VENDORED_SKILLS)
        and not re.fullmatch(r"[A-Z_]+", PurePosixPath(rel).stem)
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
    ("secret-content", check_secret_content),
    ("tool-versions", check_tool_versions),
    ("hook-scripts", check_hook_scripts),
    ("push-permissions", check_push_permissions),
    ("edit-permissions", check_edit_permissions),
    ("playwright-mcp", check_playwright_mcp),
    ("obsidian-vault", check_obsidian_vault),
    ("modern-web-guidance", check_modern_web_guidance),
    ("project-permissions", check_project_permissions),
    ("mise-paranoid", check_mise_paranoid),
    ("rerere", check_rerere),
    ("link-guard", check_link_guard),
    ("syntax", check_syntax),
    ("markdown-names", check_markdown_names),
    ("markdown-links", check_markdown_links),
)


def exception_detail(e, root):
    """例外の型の後ろに付ける文字列（": <メッセージ>"、出さないときは " (…)"）を返す。CI のログは公開されるので、
    ユーザー名を含むパスは出さない。

    OSError などのメッセージには絶対パスが入る。リポジトリのルートは "." にして原因を追えるようにし、
    それでもユーザー名を含むパス（ルートの外のもの）が残れば、メッセージごと出さない。
    """
    message = str(e).replace(str(root.absolute()), ".")
    if has_real_user_path(message):
        return " (the message is not shown because it contains a path with a user name)"
    return f": {message}"


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    failed = False
    for name, check in CHECKS:
        try:
            errors = check(root)
        except Exception as e:
            # 検査できないときは成功扱いにしない（fail closed）。
            errors = [f"error: {type(e).__name__}{exception_detail(e, root)}"]
        print(f"{'FAIL' if errors else 'PASS'} {name}")
        for error in errors:
            print(f"  {error}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
