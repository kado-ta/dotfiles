"""modern-web-guidance（npm）の新しい版に気づき、明示したときだけ取り込む。

npm の配布物から、スキル modern-web-guidance・chrome-extensions を取り込み、mise で固定している CLI の版を上げる。
SKILL.md と CLI の版をそろえるため、同じ tarball から取る。計画: docs/work/20261123_modern-web-guidance/plan.md

modern-web-guidance の SKILL.md は、npx で最新版を取得して動かす指示を、mise で固定した CLI を直接動かす指示に
変換し、テレメトリを止める DISABLE_TELEMETRY=1 を付ける。chrome-extensions は手を加えずに置く。
上流の構成が変わって変換できないときや、取り込む前に人が確かめるべき変化（frontmatter のキー、依存、
インストール時のスクリプトなど）があるときは、何も書かずに失敗する。

npm と mise の設定を読むので、通常のターミナルでホームから実行する:
  /usr/bin/python3 -I -B ~/dotfiles/claude/scripts/update-modern-web-guidance.py
      新しい版があるかを確かめるだけ。何も書かない（update-skills.sh から呼ぶ）。
  /usr/bin/python3 -I -B ~/dotfiles/claude/scripts/update-modern-web-guidance.py --out DIR [--latest]
      固定している版（--latest なら npm の latest）のスキルを、DIR の下にだけ書く。取り込む前に中身を確かめる。
      sandbox の中では claude/ と mise/ に書けないので、Claude のセッションからはこれを使う。
  /usr/bin/python3 -I -B ~/dotfiles/claude/scripts/update-modern-web-guidance.py --apply
      作業ブランチで実行する。npm の latest のスキルと mise の版を書く（両方そろって書けたときだけ残す）。
      ~/.claude/skills と mise のグローバルの設定はこのリポジトリへのリンクなので、書いた時点で有効になる。
      check-repo.py は、.github/scripts が sandbox から書けるので、ここでは実行せず、Claude のセッションで実行する。

終了コード: 0 は最新、--out・--apply で書いた。1 は失敗（--apply の書き込みの途中の失敗を除き、何も書いていない）。
3 は新しい版がある（引数なしのときだけ）。
"""
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import zlib
from pathlib import Path, PurePosixPath

PACKAGE = "modern-web-guidance"
REGISTRY = "https://registry.npmjs.org/"
REPO = Path(__file__).resolve().parents[2]
MISE_CONFIG = REPO / "mise" / "mise_config.toml"
SKILLS_DIR = REPO / "claude" / "skills"
MWG = "modern-web-guidance"
CHROME = "chrome-extensions"
TARGET_PATHS = ("mise/mise_config.toml", f"claude/skills/{MWG}", f"claude/skills/{CHROME}")
CHECK_REPO_COMMAND = "python3 -B .github/scripts/check-repo.py"

PIN_RE = re.compile(r'^"npm:modern-web-guidance" = "(\d+\.\d+\.\d+)"$', re.M)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# npx 系で modern-web-guidance を動かす指示。同じ行の中で、間にバッククォートを挟まないものを数える
# （行末の \ で続けた行は、つなげてから調べる）。pnpm・bun・yarn・npm・deno は、オプションの後のサブコマンドで見る。
RUNNABLE_RE = re.compile(r"\b(?:npx|pnpx|bunx)\b[^\n`]*?modern-web-guidance"
                         r"|\b(?:pnpm|bun|yarn|npm|deno)\b[^\n`]*?\s(?:dlx|exec|x|run|install|i|add)\b[^\n`]*?modern-web-guidance"
                         r"|\b(?:pnpm|bun|yarn|npm|deno)\b[^\n`]*?modern-web-guidance[^\n`]*?\s(?:dlx|exec|x|run|install|i|add)\b")
# YAML は LF のほかに CR（と YAML 1.1 の NEL・LS・PS）も改行として扱う。LF で分けた行の検査を通さないよう拒否する。
OTHER_LINE_BREAKS = ("\r", "\x85", " ", " ")
NPX_SECTION_RE = re.compile(r"^## .*\b(?:npx|pnpx)\b")
SKILL_VERSION_RE = re.compile(r"--skill-version (\S+)")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):")
# hooks（sandbox の外で動く）や allowed-tools（確認なしでツールを使える）などは、取り込む前に人が判断する。
FRONTMATTER_KEYS = {"name", "description", "license", "metadata"}
# スキルを読み込むときに、Claude Code がコマンドを実行する書き方（インラインの !`…` と、フェンスの ```!）。
DYNAMIC_CONTEXT_RE = re.compile(r"!`|^[ \t]*(?:`{3,}|~{3,})[ \t]*!", re.M)
# mise install は sandbox の外で npm のパッケージを入れる（mise 2026.11 は aube を使う）。依存とインストール時の
# スクリプトが増えたら、取り込む前に人が判断する。bin は node_modules/.bin として PATH の先頭に入るので、
# modern-web-guidance 以外の名前（git など）があれば止める。
DEPENDENCY_KEYS = ("dependencies", "optionalDependencies", "peerDependencies", "bundleDependencies",
                   "bundledDependencies")
INSTALL_SCRIPTS = ("preinstall", "install", "postinstall", "prepare", "preprepare", "postprepare")
# chrome-extensions のうち、置いてよいファイル（SKILL.md・skill-version.txt と references の下の .md）。
# CLAUDE.md などが、作業ディレクトリの指示として読まれないようにする。
CHROME_FILES = ("SKILL.md", "skill-version.txt")
MAX_TOTAL_BYTES = 2 * 1024 * 1024

LOCAL_SECTION = """## Running the CLI (local install)

- The `modern-web-guidance` CLI is installed by mise at a pinned version. Run it directly as `DISABLE_TELEMETRY=1 modern-web-guidance <command> …`. It works offline and needs no network access.
- Guides link to other guides with a command that ends in `retrieve "<id>"`. Run `DISABLE_TELEMETRY=1 modern-web-guidance retrieve "<id>"` instead of that command.
- Never run it through `npx`, `pnpx`, `pnpm dlx`, `bunx` or `npm exec`. They fetch the latest package from npm, and the permission rules deny them.
- Always keep the `DISABLE_TELEMETRY=1` prefix. Without it, the CLI sends usage telemetry to Google.
"""


class Failure(Exception):
    pass


def parse_version(text):
    return tuple(int(part) for part in text.split("."))


def read_pin():
    matches = PIN_RE.findall(MISE_CONFIG.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise Failure(f'{MISE_CONFIG} に "npm:{PACKAGE}" = "X.Y.Z" の行がちょうど 1 つない（{len(matches)} 行）')
    return matches[0]


def npm(args, tmp):
    # npm は作業ディレクトリの .npmrc と、共有のキャッシュ（~/.npm。sandbox の中から書ける）を読む。
    # どちらも一時ディレクトリにし、レジストリも明示する。
    # --prefix で、プロジェクトの設定を探す場所も一時ディレクトリに固定する（祖先の node_modules に頼らない）。
    command = ["npm", *args, "--cache", str(tmp / "npm-cache"), "--prefix", str(tmp), f"--registry={REGISTRY}"]
    try:
        result = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
    except FileNotFoundError:
        raise Failure("npm がない（mise の node が PATH にあるターミナルで実行する）")
    if result.returncode != 0:
        raise Failure(f"npm {args[0]} が失敗した: {result.stderr.strip()}")
    return result.stdout


def latest_version(tmp):
    version = npm(["view", PACKAGE, "version"], tmp).strip()
    if not VERSION_RE.match(version):
        raise Failure(f"npm view が X.Y.Z でない版を返した: {version!r}")
    return version


def wanted(rel):
    return (rel in ("LICENSE", "package.json", f"skills/{MWG}/SKILL.md", f"skills/{MWG}/skill-version.txt")
            or rel.startswith(f"skills/{CHROME}/"))


def check_canonical_path(rel, name):
    """tarball の中の相対パスを、正規の形（//・.・.. や末尾の / がない）だけに限る。

    取り込まないエントリーにも当てる。展開するときは正規のパスと同じ場所を指すので、検証したファイルを
    上書きしたり、禁止したファイルを置いたりできてしまうため。
    """
    parts = PurePosixPath(rel).parts
    if (not rel or rel.startswith("/") or "\\" in rel or str(PurePosixPath(rel)) != rel
            or any(part in ("", ".", "..") for part in parts)):
        raise Failure(f"tarball に安全でないパスがある: {name!r}")


def read_package(tgz):
    """tarball から要るファイルだけをメモリに読む。展開せず、パスは正規の相対パスだけを許す。

    要るファイルの中身と、すべての通常のファイルの名前（package/ から下）を返す。
    """
    files = {}
    seen = {}
    total = 0
    try:
        with tarfile.open(tgz, "r:gz") as tar:
            for member in tar:
                if member.isdir():
                    continue
                # インストーラーは先頭の階層を名前によらず取り除くので、package/ の外があると、検査していない
                # package.json などがインストールで使われうる。
                if not member.name.startswith("package/"):
                    raise Failure(f"tarball に package/ の外のエントリーがある: {member.name!r}")
                rel = member.name[len("package/"):]
                # ここからの検査は、取り込まないエントリーにも当てる。
                check_canonical_path(rel, member.name)
                if not member.isfile():
                    raise Failure(f"tarball に通常のファイルでないものがある: {member.name!r}")
                # 重複と、大文字小文字・Unicode の正規化だけが違う名前を止める
                # （大文字小文字を区別しない APFS などで、検証した内容が別の名前のファイルに上書きされないように）。
                key = unicodedata.normalize("NFC", rel).casefold()
                if key in seen:
                    raise Failure(f"tarball の名前が衝突する（重複・大文字小文字・Unicode の正規化）: {seen[key]!r} と {rel!r}")
                seen[key] = rel
                if rel == "binding.gyp":
                    raise Failure("tarball に binding.gyp がある（インストールで node-gyp rebuild が動く）")
                if not wanted(rel):
                    continue
                if any(part.startswith(".") for part in PurePosixPath(rel).parts):
                    raise Failure(f"tarball にドットで始まる名前がある: {member.name!r}")
                total += member.size
                if total > MAX_TOTAL_BYTES:
                    raise Failure(f"取り込むファイルの合計が {MAX_TOTAL_BYTES} バイトを超えた")
                files[rel] = tar.extractfile(member).read()
    except (tarfile.TarError, EOFError, OSError, zlib.error) as e:
        raise Failure(f"tarball を読めない: {e}")
    for rel in ("LICENSE", "package.json", f"skills/{MWG}/SKILL.md", f"skills/{MWG}/skill-version.txt",
                f"skills/{CHROME}/SKILL.md"):
        if rel not in files:
            raise Failure(f"tarball に {rel} がない")
    return files, set(seen.values())


def fetch_package(version, tmp):
    stdout = npm(["pack", f"{PACKAGE}@{version}", "--pack-destination", str(tmp), "--json"], tmp)
    # npm 11.20.0 は配列を、npm 12.2.3 はパッケージ名をキーにしたオブジェクトを返す。
    try:
        data = json.loads(stdout)
        filename = (data[0] if isinstance(data, list) else data[PACKAGE])["filename"]
    except (ValueError, LookupError, TypeError):
        raise Failure(f"npm pack の出力を読めない: {stdout[:200]!r}")
    tgz = tmp / PurePosixPath(filename).name
    if not tgz.is_file():
        raise Failure(f"npm pack の結果がない: {tgz}")
    return read_package(tgz)


def check_package_json(data, names):
    """names: tarball の中のすべての通常のファイルの名前（package/ から下）。bin の参照先を確かめる。"""
    try:
        pkg = json.loads(data)
    except ValueError as e:
        raise Failure(f"package.json を読めない: {e}")
    for key in DEPENDENCY_KEYS:
        if pkg.get(key):
            raise Failure(f"package.json に {key} がある。中身を確かめてから手で取り込む")
    scripts = pkg.get("scripts") or {}
    for key in INSTALL_SCRIPTS:
        if key in scripts:
            raise Failure(f"package.json にインストール時のスクリプト {key} がある。中身を確かめてから手で取り込む")
    if pkg.get("name") != PACKAGE:
        raise Failure(f"package.json の name が {PACKAGE} でない: {pkg.get('name')!r}")
    bin_field = pkg.get("bin")
    # 文字列の bin は、パッケージの名前のコマンドになる。
    commands = {PACKAGE} if isinstance(bin_field, str) else set(bin_field) if isinstance(bin_field, dict) else set()
    if commands != {PACKAGE} or (pkg.get("directories") or {}).get("bin"):
        raise Failure(f"package.json の bin が {PACKAGE} だけでない（PATH に入るコマンドが変わる）: {bin_field!r}")
    # bin の参照先は、tarball の中の通常のファイルでなければならない（ないと CLI が成り立たない）。
    for target in ([bin_field] if isinstance(bin_field, str) else list(bin_field.values())):
        rel = target[2:] if isinstance(target, str) and target.startswith("./") else target
        if not isinstance(rel, str) or rel.startswith("/") or str(PurePosixPath(rel)) != rel or rel not in names:
            raise Failure(f"package.json の bin の参照先が、tarball の中の通常のファイルでない: {target!r}")


def split_frontmatter(text, name):
    """frontmatter のトップレベルのキーを確かめ、閉じる行までと、その後ろに分けて返す。"""
    if any(line_break in text for line_break in OTHER_LINE_BREAKS):
        raise Failure(f"{name} の SKILL.md に、LF 以外の改行（CR・NEL・LS・PS）がある")
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        raise Failure(f"{name} の SKILL.md の frontmatter が閉じていない")
    end = lines.index("---", 1)
    keys = {}
    for line in lines[1:end]:
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            keys[match.group(1)] = line[match.end():].strip()
        elif line and not line[0].isspace():
            raise Failure(f"{name} の SKILL.md の frontmatter を読めない行がある: {line!r}")
    extra = sorted(set(keys) - FRONTMATTER_KEYS)
    if extra:
        raise Failure(f"{name} の SKILL.md の frontmatter に、許していないキーがある: {extra}。中身を確かめてから手で取り込む")
    if keys.get("name") != name:
        raise Failure(f"{name} の SKILL.md の frontmatter に name: {name} がない")
    return "\n".join(lines[:end + 1]) + "\n", "\n".join(lines[end + 1:])


def find_runnable(text):
    return RUNNABLE_RE.search(text.replace("\\\n", " "))


def check_skill_md(text, name):
    if DYNAMIC_CONTEXT_RE.search(text):
        raise Failure(f"{name} の SKILL.md に、読み込み時にコマンドを実行する書き方（!`…` か ```!）がある")
    runnable = find_runnable(text)
    if runnable:
        raise Failure(f"{name} の SKILL.md に、npx 系の実行の指示が残った: {runnable.group(0)!r}")


def remove_npx_sections(text):
    # 見出しに npx・pnpx を含む H2 の節を、次の H2 の手前まで消す。
    kept = []
    skipping = False
    for line in text.splitlines(keepends=True):
        if line.startswith("## "):
            skipping = bool(NPX_SECTION_RE.match(line))
        if not skipping:
            kept.append(line)
    return "".join(kept)


def transform_mwg(text, skill_version, version):
    head, body = split_frontmatter(text, MWG)
    body = body.replace(f"npx -y {PACKAGE}@latest", f"DISABLE_TELEMETRY=1 {PACKAGE}")
    body = remove_npx_sections(body)
    # v1.0.1 の Step 1 の言い回し。なくても失敗にしない（実行の指示は下で調べる）。
    body = body.replace("directly with `npx` using", "using")
    if f"DISABLE_TELEMETRY=1 {PACKAGE} search" not in body:
        raise Failure(f"{MWG} の SKILL.md に search のコマンドがない")
    found = set(SKILL_VERSION_RE.findall(body))
    if found != {skill_version}:
        raise Failure(f"SKILL.md の --skill-version {sorted(found)} が、skill-version.txt の {skill_version} と一致しない")
    notice = (f"<!-- claude/scripts/update-modern-web-guidance.py が、npm の {PACKAGE}@{version} の "
              f"skills/{MWG}/SKILL.md から生成した、変更済みの写し（Apache-2.0、LICENSE.md）。"
              "mise で固定した CLI を、npx を使わず、テレメトリを止めて実行するように変えた。手で編集しない。 -->\n")
    text = head + notice + body.rstrip("\n") + "\n\n" + LOCAL_SECTION
    # 足した表示とローカルの節も含めて調べる。
    check_skill_md(text, MWG)
    return text


def decode(data, rel):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise Failure(f"{rel} が UTF-8 でない")


def build_skills(package, version):
    """package: read_package の結果。書き込むファイルを {スキル名: {スキルの中のパス: 中身}} で返す。

    検証に失敗したら Failure。
    """
    files, names = package
    check_package_json(files["package.json"], names)
    license_text = files["LICENSE"]
    skill_version = decode(files[f"skills/{MWG}/skill-version.txt"], "skill-version.txt").strip()
    mwg = transform_mwg(decode(files[f"skills/{MWG}/SKILL.md"], f"skills/{MWG}/SKILL.md"), skill_version, version)
    chrome = {}
    prefix = f"skills/{CHROME}/"
    for rel, data in files.items():
        if rel.startswith(prefix):
            name = rel[len(prefix):]
            if not (name in CHROME_FILES or (name.startswith("references/") and name.endswith(".md"))):
                raise Failure(f"{CHROME} に許していないファイルがある: {name!r}")
            runnable = find_runnable(data.decode("utf-8", errors="replace"))
            if runnable:
                raise Failure(f"{CHROME} の {name} に npx 系の実行の指示がある: {runnable.group(0)!r}")
            chrome[name] = data
    for name in chrome:
        for parent in PurePosixPath(name).parents:
            if str(parent) in chrome:
                raise Failure(f"{CHROME} の名前が衝突する（ファイルとディレクトリ）: {str(parent)!r} と {name!r}")
    chrome_skill = decode(chrome["SKILL.md"], f"{prefix}SKILL.md")
    split_frontmatter(chrome_skill, CHROME)
    check_skill_md(chrome_skill, CHROME)
    chrome["LICENSE.md"] = license_text
    return {
        MWG: {"SKILL.md": mwg.encode("utf-8"), "LICENSE.md": license_text},
        CHROME: chrome,
    }


def write_skills(skills, dest, then=None, undo=None):
    """一時ディレクトリに組み立ててから入れ替える。上流でなくなったファイルは残らない。

    入れ替えの後に then を呼ぶ（mise の版の書き込み）。入れ替えか then が失敗したら（Ctrl-C を含む）、undo を呼んで
    then の結果を戻し（then が済んでいてもいなくても呼ぶ）、スキルも元に戻す。
    戻すかどうかは、記録ではなくディスクの状態で決める（新しい版を置いた直後に止まっても戻せるように）。
    前になかったスキルは消す。戻すのにも失敗したら、旧版の写しを一時ディレクトリに残して、その場所を表示する。
    """
    dest.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".update-mwg-", dir=dest))
    root = os.path.realpath(staging) + os.sep
    keep_staging = False
    try:
        for name, tree in skills.items():
            for rel, data in tree.items():
                path = staging / "new" / name / rel
                if not os.path.realpath(path).startswith(root):
                    raise Failure(f"書き込み先が一時ディレクトリの外になる: {name}/{rel}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        (staging / "old").mkdir()
        try:
            for name in skills:
                if (dest / name).exists():
                    os.replace(dest / name, staging / "old" / name)
                os.replace(staging / "new" / name, dest / name)
            if then is not None:
                then()
        except BaseException:
            try:
                if undo is not None:
                    undo()
                for name in skills:
                    new, old = staging / "new" / name, staging / "old" / name
                    # 新しい版が一時ディレクトリにないなら、置いた後なので、置いた場所から戻す。
                    if not new.exists() and (dest / name).exists():
                        os.replace(dest / name, new)
                    if old.exists():
                        os.replace(old, dest / name)
            except BaseException:
                keep_staging = True
                print(f"{PACKAGE}: 元に戻せなかった。旧版の写しは {staging / 'old'} にある", file=sys.stderr)
            raise
    finally:
        if not keep_staging:
            shutil.rmtree(staging)


def bumped_pin(version):
    text, count = PIN_RE.subn(f'"npm:{PACKAGE}" = "{version}"', MISE_CONFIG.read_text(encoding="utf-8"))
    if count != 1:
        raise Failure("mise の設定の版の行を書き換えられない")
    return text


def write_pin(text):
    # ~/.config/mise/config.toml はこのファイルへのリンクなので、リンクを残してこのファイルを置き換える。
    # 失敗したら、一時ファイルを残さない。
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=MISE_CONFIG.parent, delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(text)
        os.chmod(tmp_name, stat.S_IMODE(MISE_CONFIG.stat().st_mode))
        os.replace(tmp_name, MISE_CONFIG)
    except BaseException:
        if tmp_name is not None and os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def scan(dest, tmp):
    if shutil.which("skillspector") is None:
        print("skillspector がないので、検査しなかった（mise install で入る）")
        return
    for name in (MWG, CHROME):
        report = tmp / f"skillspector-{name}.json"
        subprocess.run(["skillspector", "scan", str(dest / name), "--no-llm", "--format", "json",
                        "--output", str(report)], capture_output=True, text=True)
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            risk = data["risk_assessment"]
            print(f"skillspector: {name} score={risk['score']} severity={risk['severity']} "
                  f"recommendation={risk['recommendation']} issues={len(data['issues'])}")
        except (OSError, ValueError, LookupError, TypeError):
            print(f"skillspector: {name} の結果を読めなかった。skillspector scan {dest / name} --no-llm で確かめる")


def apply_skills_and_pin(skills, pin_text):
    """スキルを入れ替え、mise の版を書く。両方そろって書けたときだけ残す。

    途中で止まったら（版の置き換えの直後の Ctrl-C を含む）、スキルと一緒に版も元の中身に戻す。
    版だけ新しいまま残ると、次の --apply が「最新」で終わり、スキルが直らないため。
    戻すのは、今の中身がここで書いた版のときだけ（書く前に止まったときは、ほかからの書き込みを消さない）。
    """
    old_pin = MISE_CONFIG.read_text(encoding="utf-8")

    def undo():
        if MISE_CONFIG.read_text(encoding="utf-8") == pin_text:
            write_pin(old_pin)

    write_skills(skills, SKILLS_DIR, then=lambda: write_pin(pin_text), undo=undo)


def print_restore():
    print("取り込まないときは、次の 2 つで戻す（作業ツリーは共有なので、パスを付けて実行する）:")
    print(f"  git -C {REPO} restore --source=HEAD --staged --worktree -- {' '.join(TARGET_PATHS)}")
    print(f"  git -C {REPO} clean -fdx -- {' '.join(TARGET_PATHS[1:])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="modern-web-guidance の新しい版に気づき、明示したときだけ取り込む")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--out", type=Path, help="スキルを、このディレクトリの下にだけ書く")
    mode.add_argument("--apply", action="store_true", help="npm の latest のスキルと mise の版を、このリポジトリに書く")
    parser.add_argument("--latest", action="store_true", help="--out で、固定している版の代わりに npm の latest を書く")
    args = parser.parse_args(argv)
    if args.latest and args.out is None:
        parser.error("--latest は --out と一緒に使う")
    try:
        pinned = read_pin()
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            version = pinned
            if args.out is None or args.latest:
                latest = latest_version(tmp)
                if parse_version(latest) < parse_version(pinned):
                    raise Failure(f"npm の latest {latest} が、固定している版 {pinned} より古い。"
                                  "取り下げや非推奨になっていないかを確かめる")
                if args.out is None and latest == pinned:
                    print(f"{PACKAGE}: 最新（固定している版 {pinned}）")
                    return 0
                if args.out is None and not args.apply:
                    print(f"{PACKAGE}: 新しい版 {latest} がある（固定している版 {pinned}）。取り込むときは作業ブランチで"
                          f" --apply を実行する（先に --out <dir> --latest で中身を確かめられる）")
                    return 3
                version = latest
            skills = build_skills(fetch_package(version, tmp), version)
            if args.out is not None:
                dest = args.out.resolve()
                write_skills(skills, dest)
                print(f"{PACKAGE}: {version} のスキルを {dest} に書いた")
                scan(dest, tmp)
                return 0
            # 書き始める前に、検証と組み立てをすべて終える。スキルと mise の版は、両方そろって書けたときだけ残す。
            pin_text = bumped_pin(version)
            try:
                apply_skills_and_pin(skills, pin_text)
            except (OSError, Failure, KeyboardInterrupt) as e:
                reason = "止めた" if isinstance(e, KeyboardInterrupt) else f"書き込みに失敗した（{e}）"
                # 戻せなかったときは、版もスキルも新しいまま残る。旧版のスキルだけを手で戻すと、組み合わせが崩れる。
                print(f"{PACKAGE}: {reason}ので、スキルと mise の版を元に戻した。戻せなかったときは、その旨を上に表示した。"
                      "そのときは旧版の写しを手で戻さず、次の git のコマンドで、スキルと版を一緒に戻す", file=sys.stderr)
                print_restore()
                return 130 if isinstance(e, KeyboardInterrupt) else 1
            print(f"{PACKAGE}: {pinned} → {version} を取り込んだ（{CHROME} を含む）。"
                  "差分を確かめて PR にし、マージしてから通常のターミナルで mise install を実行する")
            scan(SKILLS_DIR, tmp)
            # .github/scripts は sandbox から書けるので、sandbox の外で動くこのスクリプトからは実行しない。
            print(f"次に、Claude のセッション（sandbox の中）で {CHECK_REPO_COMMAND} を実行して、取り込んだファイルを検査する")
            print_restore()
            return 0
    except Failure as e:
        print(f"{PACKAGE}: 失敗（何も書いていない）: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
