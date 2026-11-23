#!/usr/bin/env python3
"""Vault のノートの Properties と Markdown の記法を点検する。

規約の正本は README.md の §6（Properties）・§7.1（タグ）と、AGENTS.md の「Markdown 記法」。
タグの辞書は _System/Tags.md の「使うタグ」の表。

使い方:    python3 _System/Scripts/check_note.py <ノート>...
終了コード: 0 = 誤りなし（警告は出ることがある）、1 = 誤りあり、2 = 使い方の誤り

厳しさ（README §6.5）:
- 01_Inbox の外のノートと、source: claude-code の下書きは、規約違反をすべて誤りにする。
- そのほかの 01_Inbox の下書きは、Properties が読めない・必須項目がないなどの誤り以外を警告にする。
  古い下書きは一括で直さず、昇格時に直すため（README §6.1）。
- 日本語の見出しの前のアンカーは、source: claude-code のノートだけ誤りにし、ほかは警告にする。
"""
from __future__ import annotations

import datetime
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
TAGS_FILE = VAULT / "_System" / "Tags.md"
ROOT_DOCS = {"README.md", "AGENTS.md", "CLAUDE.md"}

ENUMS = {
    "status": ("draft", "reviewed", "deprecated"),
    "type": ("project", "area", "knowledge", "source", "decision", "journal", "moc"),
    "verification": ("unverified", "partial", "confirmed"),
    "decision_status": ("proposed", "accepted", "superseded", "rejected"),
}
DATE_KEYS = {"created", "updated", "reviewed_at", "decided_at", "accessed_at", "published_at"}
LIST_KEYS = {"aliases", "tags", "cssclasses", "decision-makers", "consulted", "informed"}
TEXT_KEYS = set(ENUMS) | {"title", "source", "project", "url", "publisher"}
KNOWN_KEYS = DATE_KEYS | LIST_KEYS | TEXT_KEYS
ABOLISHED_KEYS = {
    "review_status": "status を使う",
    "projects": "1 つの project を使う",
    "sources": "本文の「根拠・関連ノート」に書く",
}
DEPRECATED_KEYS = {"tag": "tags", "alias": "aliases", "cssclass": "cssclasses"}
FOLDER_TYPES = (  # 先に一致したものを使う
    ("30_Knowledge/_MOCs/", ("moc",)),
    ("10_Projects/", ("project", "decision")),
    ("20_Areas/", ("area",)),
    ("30_Knowledge/", ("knowledge",)),
    ("40_Sources/", ("source",)),
    ("50_Journal/", ("journal",)),
    ("60_ADR/", ("decision",)),
)
ALERT_TYPES = {"NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"}

KEY_RE = re.compile(r"^([^\s#-][^:]*?):(?:[ \t]+(.*?))?[ \t]*$")
ITEM_RE = re.compile(r"^\s*-(?:[ \t]+(.*?))?[ \t]*$")
TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ANCHOR_RE = re.compile(r'<a\s+name="([^"]*)"\s*>\s*</a>')
ANCHOR_LINE_RE = re.compile(r'^\s*<a\s+name="[^"]*"\s*>\s*</a>\s*$')
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
QUOTE_MARK_RE = re.compile(r"^ {0,3}> ?")
LIST_MARK_RE = re.compile(r"^ {0,3}(?:[-+*]|\d{1,9}[.)])(?= |$)")
THEMATIC_BREAK_RE = re.compile(r"^ {0,3}([-*_])(?: *\1){2,} *$")
COMMENT_START_RE = re.compile(r"^ {0,3}<!--")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
INLINE_RE = re.compile(r"(<!--.*?-->)|(`+)(.+?)\2")  # 1 行の中の HTML コメントかインラインコード。左から先に始まるほう
# リンク先の中の丸括弧は、対応の取れた 1 段まで読む（CommonMark は深い入れ子も許すが、そのリンクは点検しない）
LINK_RE = re.compile(r"\]\((<[^>\n]*>|(?:[^()\s]|\([^()\s]*\))*)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
CALLOUT_RE = re.compile(r"^\s*(?:>\s*)+\[!([^\]]*)\]([-+]?)(.*)$")
HIGHLIGHT_RE = re.compile(r"(?<!=)==(?=[^\s=]).*?(?<=[^\s=])==(?!=)")
BLOCK_ID_RE = re.compile(r"(?:^|\s)\^[A-Za-z0-9-]+\s*$")
DELIMITER_ROW_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")


class Report:
    def __init__(self) -> None:
        self.strict = True  # 規約違反を誤りにするか
        self.claude = False  # source: claude-code のノートか
        self.items: list[tuple[int, bool, str]] = []

    def error(self, line: int, msg: str) -> None:
        self.items.append((line, True, msg))

    def warn(self, line: int, msg: str) -> None:
        self.items.append((line, False, msg))

    def rule(self, line: int, msg: str) -> None:
        """規約違反。厳しく点検するノートでは誤り、そのほかの下書きでは警告にする。"""
        self.items.append((line, self.strict, msg))

    @property
    def errors(self) -> int:
        return sum(1 for _, is_error, _ in self.items if is_error)


class Prop:
    def __init__(self, line: int, kind: str, value: str | list[str] | None = None) -> None:
        self.line = line
        self.kind = kind  # scalar / list / empty / nested
        self.value = [] if value is None else value


def scalar(props: dict[str, Prop], key: str) -> str:
    p = props.get(key)
    return p.value if p is not None and p.kind == "scalar" else ""


def unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return re.sub(r"\s+#.*$", "", raw)


def frontmatter_end(lines: list[str]) -> int | None:
    """frontmatter の終わりの行の添字。frontmatter がなければ None、閉じていなければ -1。"""
    if not lines or lines[0].strip() != "---":
        return None
    return next((i for i in range(1, len(lines)) if lines[i].rstrip() in ("---", "...")), -1)


def parse_frontmatter(lines: list[str], end: int, report: Report) -> dict[str, Prop]:
    """Obsidian が使う範囲の YAML（キーと値、リスト）だけを読む。"""
    props: dict[str, Prop] = {}
    current = None
    block = False
    for i in range(1, end):
        line, n = lines[i], i + 1
        if block:
            if not line.strip() or line[0] == " ":
                continue
            block = False
        if "\t" in line[: len(line) - len(line.lstrip())]:
            report.error(n, "Properties の字下げにタブを使っている")
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = ITEM_RE.match(line)
        if item:
            p = props.get(current) if current else None
            if p is None or p.kind not in ("empty", "list"):
                report.error(n, "Properties を読めない（キーに属さないリスト項目）")
                continue
            p.kind = "list"
            p.value.append(unquote(item.group(1) or ""))
            continue
        if line[0] == " ":
            if current:
                props[current].kind = "nested"
            continue
        m = KEY_RE.match(line)
        if not m:
            report.error(n, f"Properties を読めない行: {line.strip()[:40]}")
            current = None
            continue
        key, raw = m.group(1).strip(), (m.group(2) or "").strip()
        if key in props:
            report.error(n, f"キー {key} が {props[key].line} 行目と重複している")
        current = key
        if not raw or raw in ("~", "null"):
            props[key] = Prop(n, "empty")
        elif raw[0] in "|>":
            props[key] = Prop(n, "nested")
            block = True
        elif raw.startswith("["):
            if not raw.endswith("]"):
                report.error(n, f"{key} のリストが ] で閉じていない")
            props[key] = Prop(n, "list", [unquote(x) for x in raw.strip("[]").split(",") if x.strip()])
        elif raw.startswith("{"):
            props[key] = Prop(n, "nested")
        else:
            props[key] = Prop(n, "scalar", unquote(raw))
    return props


def load_tag_dict() -> set[str] | None:
    if not TAGS_FILE.is_file():
        return None
    tags: set[str] = set()
    in_section = False
    for line in TAGS_FILE.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^##\s+(.*?)\s*$", line)
        if heading:
            in_section = heading.group(1) == "使うタグ"
            continue
        m = re.match(r"^\|\s*`([^`]+)`\s*\|", line) if in_section else None
        if m:
            tags.add(m.group(1))
    return tags


def check_properties(rel: str, props: dict[str, Prop] | None, report: Report, tag_dict: set[str] | None) -> None:
    journal = rel.startswith("50_Journal/") or (props is not None and scalar(props, "type") == "journal")
    if props is None:
        report.error(1, "Properties がない（" + ("created" if journal else "status と created") + " は必須）")
        return
    for key, new in DEPRECATED_KEYS.items():
        if key in props:
            report.error(props[key].line, f"{key} は Obsidian 1.9 で既定のプロパティでなくなった。{new} を使う")
    if not scalar(props, "created"):
        report.error(1, "created がない")
    if not journal and not scalar(props, "status"):
        report.error(1, "status がない")

    for key, p in props.items():
        if key in ABOLISHED_KEYS:
            report.rule(p.line, f"{key} は廃止した。{ABOLISHED_KEYS[key]}")
        elif key not in KNOWN_KEYS and key not in DEPRECATED_KEYS:
            report.warn(p.line, f"規約にないキー {key}（README §6）")
        if p.kind == "nested":
            report.rule(p.line, f"{key} が入れ子か複数行の値になっている（Obsidian が扱えない）")
        elif key in LIST_KEYS and p.kind == "scalar":
            report.rule(p.line, f"{key} はリストで書く")
        elif key in TEXT_KEYS | DATE_KEYS and p.kind == "list":
            report.rule(p.line, f"{key} は 1 つの値で書く")
        values = p.value if p.kind == "list" else [p.value] if p.kind == "scalar" else []
        for v in values:
            if "[[" in v:
                report.rule(p.line, f"{key} に Wikilink がある。関連ノートは本文の「根拠・関連ノート」に書く")
            elif "](" in v or "**" in v:
                report.warn(p.line, f"{key} の Markdown は Obsidian で表示されない")

    for key, allowed in ENUMS.items():
        v = scalar(props, key)
        if v and v not in allowed:
            report.rule(props[key].line, f"{key} の値 {v} は規約にない（{' / '.join(allowed)}）")

    today = datetime.date.today()
    dates: dict[str, datetime.date] = {}
    for key in sorted(DATE_KEYS):
        v = scalar(props, key)
        if not v:
            continue
        try:
            if not DATE_RE.match(v):
                raise ValueError
            dates[key] = datetime.date.fromisoformat(v)
        except ValueError:
            report.rule(props[key].line, f"{key} は YYYY-MM-DD の実在する日付で書く（{v}）")
    created = dates.get("created")
    for key in ("updated", "reviewed_at"):
        if created and key in dates and dates[key] < created:
            report.rule(props[key].line, f"{key} が created より前になっている")
    for key in ("created", "updated", "reviewed_at", "decided_at", "accessed_at"):
        if key in dates and dates[key] > today:
            report.rule(props[key].line, f"{key} が未来の日付になっている")

    ntype = scalar(props, "type")
    if not rel.startswith("01_Inbox/"):
        if not ntype:
            report.rule(1, "01_Inbox の外のノートには type が必要")
        if not journal and not scalar(props, "verification"):
            report.rule(1, "01_Inbox の外のノートには verification が必要")
    if scalar(props, "status") == "reviewed" and not scalar(props, "reviewed_at"):
        report.rule(props["status"].line, "status: reviewed には reviewed_at が必要")
    if ntype == "source":
        for key in ("url", "accessed_at"):
            if not scalar(props, key):
                report.rule(1, f"type: source には {key} が必要")
    if ntype == "decision":
        ds = scalar(props, "decision_status")
        if not ds:
            report.rule(1, "type: decision には decision_status が必要")
        elif ds != "proposed" and not scalar(props, "decided_at"):
            report.rule(props["decision_status"].line, f"decision_status: {ds} には decided_at が必要")
    project = scalar(props, "project")
    if project and not any((VAULT / d / project).is_dir() for d in ("10_Projects", "90_Archived/Projects")):
        report.rule(props["project"].line, f"project の {project} が 10_Projects/ にない")
    if ntype:
        for prefix, allowed in FOLDER_TYPES:
            if rel.startswith(prefix):
                if ntype not in allowed:
                    report.warn(props["type"].line, f"{prefix} のノートの type は {' / '.join(allowed)}（{ntype} になっている）")
                break

    p = props.get("tags")
    seen: set[str] = set()
    for t in p.value if p is not None and p.kind == "list" else []:
        if t in seen:
            report.warn(p.line, f"タグ {t} が重複している")
        seen.add(t)
        if not TAG_RE.match(t) or not re.search(r"[a-z]", t):
            report.rule(p.line, f"タグ {t} は英小文字・数字・ハイフンで書き、階層は / で区切る（README §7.1）")
        elif tag_dict is not None and not any(d == t or d.startswith(t + "/") for d in tag_dict):
            report.warn(p.line, f"タグ {t} が _System/Tags.md の辞書にない")


def match_containers(stack: list[int | None], text: str) -> tuple[int, str]:
    """開いている入れ子のうち、この行が続けるものの数と、その記号と字下げを除いた残り。

    stack の None は引用、数はリスト項目の内容が始まる桁（外側の入れ子の内容から数える）。text はタブを展開した行。
    """
    for k, width in enumerate(stack):
        if width is None:
            m = QUOTE_MARK_RE.match(text)
            if not m:
                return k, text
            text = text[m.end():]
        elif not text.strip(" "):
            text = ""  # 空行はリスト項目を続ける
        elif len(text) - len(text.lstrip(" ")) >= width:
            text = text[width:]
        else:
            return k, text
    return len(stack), text


def open_containers(stack: list[int | None], text: str) -> str:
    """行の先頭で始まる引用とリスト項目を stack に積み、残りを返す。"""
    while True:
        m = QUOTE_MARK_RE.match(text)
        if m:
            stack.append(None)
            text = text[m.end():]
            continue
        m = LIST_MARK_RE.match(text)
        if not m or THEMATIC_BREAK_RE.match(text):
            return text
        rest = text[m.end():]
        spaces = len(rest) - len(rest.lstrip(" "))
        if not rest.strip(" ") or spaces > 4:  # 空の項目と、字下げしたコードで始まる項目は、記号の 1 文字後から内容とする
            spaces = 1
        stack.append(m.end() + spaces)
        text = rest[spaces:]


def find_comment_end(lines: list[str], i: int, stack: list[int | None], block: bool) -> int | None:
    """i 行目で閉じずに始まる HTML コメントを閉じる行の添字。閉じなければ None。

    行頭の <!-- は HTML ブロックなので、空行をまたぐ。行の途中の <!-- は段落の中なので、空行で途切れる。
    どちらも入れ子が続かない行で途切れる（段落の遅延継続は扱わず、伏せない側に倒す）。
    """
    for j in range(i + 1, len(lines)):
        k, rest = match_containers(stack, lines[j].expandtabs(4))
        if k < len(stack) or (not block and not rest.strip(" ")):
            return None
        if "-->" in lines[j]:
            return j
    return None


def mask_inline(m: re.Match) -> str:
    if m.group(1):
        return " " * len(m.group(1))
    return m.group(2) + "x" * len(m.group(3)) + m.group(2)


def mask_code(lines: list[str], start: int) -> list[str | None]:
    """点検しない行を None にし、ほかの行は HTML コメントを空白で、インラインコードの中身を x で伏せて返す。

    点検しない行は、フェンスのコードブロックの行と、複数行の HTML コメントの間の行。
    フェンスは引用とリスト項目の中でも認識し、その入れ子が続かない行で閉じる（CommonMark）。
    閉じない <!-- は伏せない。伏せると、後ろの誤りをすべて隠すため。
    インラインコードの両端の ` は残す。** の前後の判定で記号として扱うため。
    """
    masked: list[str | None] = [None] * len(lines)
    stack: list[int | None] = []  # 開いている入れ子（match_containers を参照）
    fence = None  # 開いているフェンスの記号
    comment_end = None  # 複数行の HTML コメントを閉じる行の添字
    for i in range(start, len(lines)):
        if comment_end is not None and i < comment_end:
            continue
        k, rest = match_containers(stack, lines[i].expandtabs(4))
        head = 0  # この行でコメントの外が始まる位置
        if i == comment_end:
            comment_end = None
            head = lines[i].index("-->") + 3
        elif fence and k == len(stack):
            m = FENCE_RE.match(rest)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not rest.strip()[len(m.group(1)):].strip():
                fence = None
            continue
        else:
            fence = None  # 入れ子が続かなければ、その中のコードブロックも閉じる
            del stack[k:]
            rest = open_containers(stack, rest)
            m = FENCE_RE.match(rest)
            if m:
                fence = m.group(1)
                continue
        line = " " * head + INLINE_RE.sub(mask_inline, lines[i][head:])
        p = line.find("<!--")
        if p >= 0:
            block = head == 0 and bool(COMMENT_START_RE.match(rest)) and lines[i].find("<!--") == p
            # ATX 見出しの中身は 1 行なので、見出しの中の <!-- は次の行に続かない
            end = None if not block and HEADING_RE.match(rest) else find_comment_end(lines, i, stack, block)
            if end is not None:
                line = line[:p] + " " * (len(line) - p)
                comment_end = end
        masked[i] = line
    return masked


def github_slug(text: str) -> str:
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    out = []
    for c in text.strip().lower():
        if c == " ":
            out.append("-")
        elif c in "-_" or unicodedata.category(c)[0] in "LNM":
            out.append(c)
    return "".join(out)


def structure(lines: list[str], masked: list[str | None]):
    """アンカー（行, ID）と見出し（行, 見出しの文字列）の一覧。"""
    anchors, headings = [], []
    for i, m in enumerate(masked):
        if m is None:
            continue
        anchors += [(i + 1, a.group(1)) for a in ANCHOR_RE.finditer(m)]
        # 見出しかどうかは元の行で決める。#<!-- --> x はコメントを伏せると見出しに見えるが、# の直後が空白でないので見出しでない
        heading = HEADING_RE.match(lines[i])
        if heading:
            headings.append((i + 1, heading.group(2)))
    return anchors, headings


def link_ids(anchors, headings) -> set[str]:
    """リンクの #... で指せる ID。明示したアンカーと、GitHub が見出しから作る ID。

    GitHub は、重なる見出しの ID に、生成済みの ID と重ならない番号を付ける（Topic・Topic-1・Topic の 3 つ目は topic-2）。
    """
    ids = {name for _, name in anchors}
    used: set[str] = set()
    counts: dict[str, int] = {}
    for _, text in headings:
        slug = result = github_slug(text)
        while result in used:
            counts[slug] = counts.get(slug, 0) + 1
            result = f"{slug}-{counts[slug]}"
        used.add(result)
        ids.add(result)
    return ids


_ids_cache: dict[Path, set[str]] = {}


def ids_of_file(path: Path) -> set[str]:
    if path not in _ids_cache:
        lines = path.read_text(encoding="utf-8").lstrip("﻿").splitlines()
        end = frontmatter_end(lines)
        masked = mask_code(lines, end + 1 if end is not None and end >= 0 else 0)
        _ids_cache[path] = link_ids(*structure(lines, masked))
    return _ids_cache[path]


def is_space(c: str | None) -> bool:
    return c is None or c.isspace()


def is_punct(c: str | None) -> bool:
    return c is not None and unicodedata.category(c)[0] in "PS"


def check_strong(n: int, m: str, report: Report) -> None:
    """閉じない・開かない ** を見つける（CommonMark の left/right-flanking の規則）。"""
    if re.search(r"(?<!\\)\*{3,}", m):
        return
    runs = [r for r in re.finditer(r"(?<![\\*])\*\*(?!\*)", m)]
    if len(runs) % 2:
        return
    for k, r in enumerate(runs):
        prev = m[r.start() - 1] if r.start() > 0 else None
        nxt = m[r.end()] if r.end() < len(m) else None
        if k % 2 == 0:
            ok = not is_space(nxt) and (not is_punct(nxt) or is_space(prev) or is_punct(prev))
        else:
            ok = not is_space(prev) and (not is_punct(prev) or is_space(nxt) or is_punct(nxt))
        if not ok:
            report.rule(n, "** が強調にならない（記号の外側が文字に接している）。記号を ** の外に出すか、** の外側に空白を入れる")
            return


def split_cells(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return re.split(r"(?<!\\)\|", row)


def check_tables(masked: list[str | None], report: Report) -> None:
    i = 0
    while i < len(masked) - 1:
        head, delim = masked[i], masked[i + 1]
        if head is None or delim is None or "|" not in head or "|" not in delim or not DELIMITER_ROW_RE.match(delim):
            i += 1
            continue
        h, d = len(split_cells(head)), len(split_cells(delim))
        if d != h:
            report.rule(i + 2, f"表の区切り行が {d} 列で、見出し行の {h} 列と違う（表として表示されない）")
        j = i + 2
        while j < len(masked) and masked[j] is not None and masked[j].strip() and "|" in masked[j]:
            c = len(split_cells(masked[j]))
            if c != h:
                report.rule(j + 1, f"表の行が {c} 列で、見出し行の {h} 列と違う")
            j += 1
        i = j


def check_links(n: int, m: str, path: Path, ids: set[str], report: Report) -> None:
    for lk in LINK_RE.finditer(m):
        target = lk.group(1)
        if target.startswith("<"):
            target = target[1:-1]
        if not target or SCHEME_RE.match(target):
            continue
        file_part, _, frag = target.partition("#")
        file_part, frag = urllib.parse.unquote(file_part), urllib.parse.unquote(frag)
        if not file_part:
            if frag not in ids:
                report.rule(n, f"リンク先のアンカー #{frag} がない")
            continue
        dest = VAULT / file_part.lstrip("/") if file_part.startswith("/") else path.parent / file_part
        if not dest.exists():
            report.rule(n, f"リンク先 {file_part} がない")
        elif frag and dest.suffix == ".md" and frag not in ids_of_file(dest.resolve()):
            report.rule(n, f"リンク先 {file_part} にアンカー #{frag} がない")


def check_markdown(path: Path, lines: list[str], start: int, report: Report) -> None:
    masked = mask_code(lines, start)
    anchors, headings = structure(lines, masked)

    first_line: dict[str, int] = {}
    for n, name in anchors:
        if not re.fullmatch(r"[a-z0-9-]+", name):
            report.rule(n, f"アンカー ID「{name}」は英小文字・数字・ハイフンだけで書く")
        if name in first_line:
            report.rule(n, f"アンカー ID {name} が {first_line[name]} 行目と重複している")
        first_line.setdefault(name, n)

    first_heading: dict[str, int] = {}
    for n, text in headings:
        if re.search(r"[^A-Za-z0-9 -]", text):
            prev = next((lines[j] for j in range(n - 2, start - 1, -1) if lines[j].strip()), "")
            if not ANCHOR_LINE_RE.match(prev):
                # 承認済みのノートの多くは、この規則より前に書かれた。誤りにすると、
                # 1 行の編集で全見出しの変換を促してしまうので、Claude Code のノートだけ誤りにする。
                msg = f"見出し「{text}」の直前に <a name=\"...\"></a> を置く"
                if report.claude:
                    report.rule(n, msg)
                else:
                    report.warn(n, msg)
        if text in first_heading:
            report.warn(n, f"見出し「{text}」が {first_heading[text]} 行目と重複している")
        first_heading.setdefault(text, n)

    ids = link_ids(anchors, headings)
    for i, m in enumerate(masked):
        if m is None:
            continue
        n = i + 1
        if "[[" in m:
            report.rule(n, "Wikilink（[[...]]）は使わない。[表示名](<相対パス.md>) で書く")
        callout = CALLOUT_RE.match(m)
        if callout and (callout.group(1) not in ALERT_TYPES or callout.group(2) or callout.group(3).strip()):
            report.rule(n, "コールアウトは GitHub Alerts（> [!NOTE] など。大文字で 1 行に単独で書く）だけを使う")
        if HIGHLIGHT_RE.search(m):
            report.rule(n, "ハイライト（==...==）は Obsidian 独自の記法")
        if "%%" in m:
            report.rule(n, "コメント（%%...%%）は Obsidian 独自の記法")
        if BLOCK_ID_RE.search(m):
            report.rule(n, "ブロック ID（^id）は Obsidian 独自の記法")
        check_links(n, m, path, ids, report)
        check_strong(n, m, report)
    check_tables(masked, report)


def excluded(rel: str) -> bool:
    parts = rel.split("/")
    return (len(parts) == 1 and parts[0] in ROOT_DOCS) or parts[0] == "_System" or any(p.startswith(".") for p in parts)


def check_file(path: Path, rel: str, tag_dict: set[str] | None) -> Report:
    report = Report()
    lines = path.read_text(encoding="utf-8").lstrip("﻿").splitlines()
    end = frontmatter_end(lines)
    if end == -1:
        report.error(1, "Properties の終わりの --- がない")
        return report
    props = parse_frontmatter(lines, end, report) if end is not None else None
    report.claude = props is not None and scalar(props, "source") == "claude-code"
    report.strict = not rel.startswith("01_Inbox/") or report.claude
    check_properties(rel, props, report, tag_dict)
    check_markdown(path, lines, end + 1 if end is not None else 0, report)
    return report


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    tag_dict = load_tag_dict()
    status = 0
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            print(f"{arg}: ファイルがない", file=sys.stderr)
            status = 2
            continue
        try:
            rel = path.resolve().relative_to(VAULT).as_posix()
        except ValueError:
            print(f"{arg}: Vault の外なので点検しない")
            continue
        if path.suffix != ".md" or excluded(rel):
            continue
        report = check_file(path, rel, tag_dict)
        for line, is_error, msg in sorted(report.items):
            print(f"{rel}:{line}: {'誤り' if is_error else '警告'}: {msg}")
        if report.items and not report.strict:
            print(f"{rel}: 01_Inbox の下書きなので、記法と値の問題は警告にした（昇格時に直す）")
        if report.errors and status == 0:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
