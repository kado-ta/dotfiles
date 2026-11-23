"""期間内の Claude Code のトランスクリプトから、スキルの使われ方を集計する（日付は UTC、YYYY-MM-DD）。

件数とセッション ID だけを出し、会話の中身は出さない。
使い方: python3 -B claude/scripts/skill-usage.py <since> <until>（until は含まない）
"""
import collections
import glob
import json
import os
import re
import sys

# 日付は文字列のまま比べるので、桁数の違う形式は間違った件数になる。ASCII の数字だけを許す。
if len(sys.argv) != 3 or not all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", a) for a in sys.argv[1:]):
    sys.exit("使い方: skill-usage.py <since> <until>（YYYY-MM-DD、UTC、until は含まない。例: 2026-11-16 2026-12-07）")
since, until = sys.argv[1], sys.argv[2]
REVIEW = {"review", "code-review", "superpowers:requesting-code-review"}
PLANNING = {"superpowers:brainstorming", "superpowers:writing-plans"}

skill_calls = collections.Counter()
skill_sessions = collections.defaultdict(set)
slash = collections.Counter()
pstack_suggestions = 0
sessions = set()
reviews_by_session = collections.defaultdict(set)
planning_sessions = set()

for path in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    try:
        lines = open(path, encoding="utf-8")
    except OSError:
        continue
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ts = (d.get("timestamp") or "")[:10]
        if not (since <= ts < until):
            continue
        sid = d.get("sessionId")
        sessions.add(sid)
        content = (d.get("message") or {}).get("content")
        if d.get("type") == "assistant" and isinstance(content, list):
            for c in content:
                if c.get("type") == "tool_use" and c.get("name") == "Skill":
                    name = str((c.get("input") or {}).get("skill"))
                    skill_calls[name] += 1
                    skill_sessions[name].add(sid)
                    if name in REVIEW:
                        reviews_by_session[sid].add(name)
                    if name in PLANNING:
                        planning_sessions.add(sid)
                elif c.get("type") == "text" and "/pstack:" in c.get("text", ""):
                    pstack_suggestions += 1
        elif d.get("type") == "user":
            if isinstance(content, list):
                text = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            else:
                text = content or ""
            for name in re.findall(r"<command-name>/?([^<]+)</command-name>", text):
                slash[name] += 1
                if name in REVIEW:
                    reviews_by_session[sid].add(name)

print(f"period: {since} .. {until} (until is exclusive)")
print(f"sessions: {len(sessions)}")
print("skill tool calls (calls / sessions):")
for name, n in skill_calls.most_common():
    print(f"  {name}: {n} / {len(skill_sessions[name])}")
print("slash commands typed by the user:")
for name, n in slash.most_common():
    print(f"  {name}: {n}")
review_dup_sessions = sorted(sid for sid, s in reviews_by_session.items() if len(s) >= 2)
print(f"sessions with 2+ review skills: {len(review_dup_sessions)}")
for sid in review_dup_sessions:
    print(f"  {sid}")
print(f"assistant messages suggesting /pstack: {pstack_suggestions}")
print("sessions that started brainstorming or writing-plans (check these by hand):")
for sid in sorted(planning_sessions):
    print(f"  {sid}")
