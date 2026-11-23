"""入っている Claude Code のスキルを、スナップショットとスキルの文書に照合する。

使い方:
  python3 -B claude/scripts/skills-check.py check     # 終了コード 0: 違いなし、1: 違いあり、2: 照合できない
  python3 -B claude/scripts/skills-check.py snapshot  # 今の状態を claude/skills-snapshot.json に書く

~/.claude は HOME から探す。--repo で照合する文書のリポジトリを変えられる（既定はこのスクリプトのリポジトリ）。
読むだけで、書くのは snapshot のときのスナップショットだけ。ネットワークは使わない。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

CLAUDE = Path(os.path.expanduser("~")) / ".claude"
SNAPSHOT = Path("claude/skills-snapshot.json")
INVENTORY = Path("claude/SKILL_INVENTORY.md")
DOCS = [Path("claude/rules/SKILL_ROUTING.md"), Path("claude/SKILL_CHEATSHEET.md"), INVENTORY]

# 組み込みと claude.ai 提供のスキル・コマンド。ディスク上にないので固定で持つ。
BUILTINS = {
    "code-review", "simplify", "security-review", "init", "update-config", "fewer-permission-prompts",
    "loop", "schedule", "run", "claude-api", "workflow-authoring", "plugin-authoring", "keybindings-help",
    "claude-in-chrome", "dataviz", "artifact-design", "artifact-diagramming", "artifact-capabilities",
    "doctor", "skill-doctor", "plugin", "verify",
} | {f"anthropic-skills:{n}" for n in (
    "built-in-browser", "chrome-browser", "computer-use", "deep-research", "docs", "docx",
    "google-workspace", "import-memory", "morning", "pdf", "pptx", "skill-creator", "xlsx")}
# スキルではないと分かって文書に書く名前（廃止された gstack のスキル、パス、mise のタスク）。
NOT_SKILLS = {"plan-eng-review", "investigate", "tmp", "crit:profile-test"}
# gstack の状態ごとの節（棚卸しのアンカー → skillOverrides の値）。
GSTACK_SECTIONS = [("gstack-enabled", "enabled", "on"),
                   ("gstack-limited", "user-invocable-only", "user-invocable-only"),
                   ("gstack-off", "off", "off")]


class Unreadable(Exception):
    """照合できない（ファイルが読めない、文書の形が想定と違う）。"""


def digest(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Unreadable(f"{path}: {e}") from e


def frontmatter(path):
    """SKILL.md の frontmatter を、キーごとの生の文字列（続きの行を含む）で返す。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fields, key = {}, None
    for line in (m.group(1) if m else "").splitlines():
        km = re.match(r"^([A-Za-z_-]+):(.*)$", line)
        if km:
            key = km.group(1)
            fields[key] = km.group(2).strip()
        elif key:
            fields[key] += "\n" + line
    return fields


def skill_entry(path, provider, override):
    fm = frontmatter(path)
    description = " ".join(fm.get("description", "").split()).strip("'\"")
    return {
        "provider": provider,
        "dmi": fm.get("disable-model-invocation", "").strip().lower() == "true",
        "user_invocable": fm.get("user-invocable", "").strip().lower() != "false",
        "override": override,
        "description": digest(description),
        "hooks": digest(fm["hooks"]) if "hooks" in fm else None,
    }


def hook_lines(data):
    lines = []
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command") or hook.get("prompt") or hook.get("type", "")
                lines.append(f"{event} {group.get('matcher', '')} {digest(command)}")
    return sorted(lines)


def collect(repo):
    """入っているプラグイン・スキル・エージェント・hooks と、repo の project スキルを集める。パスは記録しない。"""
    settings = load_json(CLAUDE / "settings.json")
    enabled = settings.get("enabledPlugins", {})
    overrides = settings.get("skillOverrides", {})
    installed = load_json(CLAUDE / "plugins" / "installed_plugins.json").get("plugins", {})
    state = {"version": 1, "plugins": {}, "gstack": None, "skills": {}, "agents": [], "plugin_hooks": {}}
    agents = set()
    for name, entries in sorted(installed.items()):
        user = [e for e in entries if e.get("scope") == "user"]
        main = (user or entries)[0]
        is_enabled = bool(user) and bool(enabled.get(name))
        state["plugins"][name] = {"version": main.get("version"),
                                  "scopes": sorted({e.get("scope") for e in entries}),
                                  "enabled": is_enabled}
        if not is_enabled:
            continue  # 読み込まれないプラグインのスキルは数えない
        root, short = Path(main.get("installPath", "")), name.split("@")[0]
        for skill in sorted(root.glob("skills/*/SKILL.md")):
            # skillOverrides はプラグインのスキルに効かないので、override は持たない
            state["skills"][f"{short}:{skill.parent.name}"] = skill_entry(skill, short, None)
        agents.update(f"{short}:{agent.stem}" for agent in root.glob("agents/*.md"))
        if (root / "hooks" / "hooks.json").is_file():
            state["plugin_hooks"][name] = hook_lines(load_json(root / "hooks" / "hooks.json"))

    skills_dir = CLAUDE / "skills"
    skills_root = skills_dir.resolve()
    if (skills_dir / "gstack" / "VERSION").is_file():
        state["gstack"] = {"version": (skills_dir / "gstack" / "VERSION").read_text(encoding="utf-8").strip()}
    for entry in sorted(skills_dir.iterdir()) if skills_dir.is_dir() else []:
        if not (entry / "SKILL.md").is_file():
            continue
        # SKILL.md の実体の場所で見分ける。個人スキルは dotfiles の claude/skills へのリンクで、実体が ~/.claude/skills の外にある。
        # gstack のスキルは、gstack/<name>/SKILL.md へのリンクか、setup が直接置いた実ファイル（_gstack-command など）で、
        # どちらも実体が ~/.claude/skills の中にある。
        real = (entry / "SKILL.md").resolve()
        provider = "gstack" if skills_root in real.parents else "personal"
        state["skills"][entry.name] = skill_entry(entry / "SKILL.md", provider, overrides.get(entry.name, "on"))
    for skill in sorted((repo / ".claude" / "skills").glob("*/SKILL.md")):
        # 同じ名前の個人スキルがあれば、そちらが優先されるので数えない
        state["skills"].setdefault(skill.parent.name, skill_entry(skill, "project", overrides.get(skill.parent.name, "on")))
    state["agents"] = sorted(agents)
    return state


def fmt(value):
    return json.dumps(value) if isinstance(value, bool) or value is None else str(value)


def diff_snapshot(old, new):
    """前回のスナップショットから何が変わったか。"""
    out = []
    for name in sorted(set(old["plugins"]) | set(new["plugins"])):
        a, b = old["plugins"].get(name), new["plugins"].get(name)
        if a is None:
            out.append(f"plugin added: {name} {b['version']}")
        elif b is None:
            out.append(f"plugin removed: {name}")
        else:
            for field in ("version", "enabled", "scopes"):
                if a.get(field) != b.get(field):
                    out.append(f"plugin {field}: {name} {fmt(a.get(field))} -> {fmt(b.get(field))}")
    a, b = (old.get("gstack") or {}).get("version"), (new.get("gstack") or {}).get("version")
    if a != b:
        out.append(f"gstack version: {fmt(a)} -> {fmt(b)}")
    for name in sorted(set(old["skills"]) | set(new["skills"])):
        a, b = old["skills"].get(name), new["skills"].get(name)
        if a is None:
            out.append(f"skill added: {name} ({b['provider']})")
        elif b is None:
            out.append(f"skill removed: {name}")
        else:
            for field in ("provider", "dmi", "user_invocable", "override"):
                if a.get(field) != b.get(field):
                    out.append(f"skill changed: {name} {field} {fmt(a.get(field))} -> {fmt(b.get(field))}")
            for field in ("description", "hooks"):
                if a.get(field) != b.get(field):
                    out.append(f"skill changed: {name} {field}")
    for agent in sorted(set(new["agents"]) - set(old["agents"])):
        out.append(f"agent added: {agent}")
    for agent in sorted(set(old["agents"]) - set(new["agents"])):
        out.append(f"agent removed: {agent}")
    for name in sorted(set(old["plugin_hooks"]) | set(new["plugin_hooks"])):
        a, b = set(old["plugin_hooks"].get(name, [])), set(new["plugin_hooks"].get(name, []))
        if a != b:
            out.append(f"plugin hooks changed: {name} (+{len(b - a)} -{len(a - b)})")
    return out


def code_words(text):
    """インラインコードの先頭の語を返す（コードブロックの中は除く）。"""
    text = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    return [span.split()[0] for span in re.findall(r"`([^`\n]+)`", text) if span.split()]


def section(text, anchor):
    marker = f'<a name="{anchor}"></a>'
    if marker not in text:
        raise Unreadable(f"{INVENTORY}: anchor {anchor} not found")
    start = text.index(marker) + len(marker)
    end = text.find("<a name=", start)
    return text[start:] if end < 0 else text[start:end]


def check_docs(repo, state, old):
    out = []
    known = set(state["skills"]) | BUILTINS | NOT_SKILLS
    shorts = {name.split("@")[0] for name in state["plugins"]} | {"anthropic-skills"}
    removed = set(old["skills"]) - set(state["skills"]) if old else set()
    removed |= {name.split(":", 1)[1] for name in removed if ":" in name}

    for doc in DOCS:
        rel = doc.relative_to("claude")
        try:
            text = (repo / doc).read_text(encoding="utf-8")
        except OSError as e:
            raise Unreadable(f"{doc}: {e}") from e
        seen = set()
        for word in code_words(text):
            name = word[1:] if word.startswith("/") else word
            if not name or "<" in name or "*" in name or "/" in name or name.endswith(":") or (word, rel) in seen:
                continue  # `/pstack:<名前>`・`anthropic-skills:*` の形、パス、接頭辞だけのものは名前ではない
            seen.add((word, rel))
            if name in removed:
                out.append(f"no longer installed but in {rel}: {word}")
            elif word.startswith("/") and name not in known:
                out.append(f"unknown name in {rel}: {word}")
            elif ":" in name and name.split(":", 1)[0] in shorts and name not in known:
                out.append(f"unknown name in {rel}: {word}")

    inventory = (repo / INVENTORY).read_text(encoding="utf-8")
    words = {w.lstrip("/") for w in code_words(inventory)}
    for name in sorted(set(state["skills"]) | set(state["agents"])):
        if not ({name, name.split(":", 1)[-1]} & words):
            out.append(f"not in SKILL_INVENTORY.md: {name}")

    listed = set()
    for row in re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", section(inventory, "sources"), re.M):
        provider, version = row
        if version in ("版", "—", "-") or set(version) <= set("-: "):
            continue  # 見出し・区切り・版のない行
        listed.add(provider)
        if provider == "gstack":
            installed = (state.get("gstack") or {}).get("version")
        else:
            installed = next((p["version"] for n, p in state["plugins"].items() if n.split("@")[0] == provider), None)
        if installed is None:
            out.append(f"not installed but in SKILL_INVENTORY.md: {provider}")
        elif installed != version:
            out.append(f"version in SKILL_INVENTORY.md: {provider} {version}, installed {installed}")
    for provider in sorted({n.split("@")[0] for n in state["plugins"]} | ({"gstack"} if state.get("gstack") else set())):
        if provider not in listed:
            out.append(f"not in the providers table of SKILL_INVENTORY.md: {provider}")

    gstack = {n: e for n, e in state["skills"].items() if e["provider"] == "gstack"}
    names = set(gstack) | ({n for n, e in old["skills"].items() if e["provider"] == "gstack"} if old else set())
    for anchor, label, value in GSTACK_SECTIONS:
        documented = {w.lstrip("/") for w in code_words(section(inventory, anchor))} & names
        actual = {n for n, e in gstack.items() if e["override"] == value}
        if documented != actual:
            out.append(f"gstack {label} section: missing {sorted(actual - documented)}, extra {sorted(documented - actual)}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check", "snapshot"])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        state = collect(args.repo)
        if args.command == "snapshot":
            text = json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            home = os.path.expanduser("~")
            if home in text or "/Users/" in text:
                raise Unreadable("snapshot would contain a local path")
            (args.repo / SNAPSHOT).write_text(text, encoding="utf-8")
            print(f"wrote {SNAPSHOT}: {len(state['plugins'])} plugins, {len(state['skills'])} skills")
            return 0
        old = load_json(args.repo / SNAPSHOT) if (args.repo / SNAPSHOT).is_file() else None
        changes = diff_snapshot(old, state) if old else ["no snapshot: run `mise run claude:skills-snapshot` once the docs match"]
        docs = check_docs(args.repo, state, old)
    except Unreadable as e:
        print(f"ERROR: {e}")
        return 2
    for title, lines in (("installed vs snapshot", changes), ("docs vs installed", docs)):
        print(f"== {title} ==")
        print("\n".join(f"  {line}" for line in lines) or "  none")
    total = len(changes) + len(docs)
    print(f"RESULT: {total} differences" if total else "RESULT: no differences")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
