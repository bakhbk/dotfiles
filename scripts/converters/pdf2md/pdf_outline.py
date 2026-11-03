import re
from collections import Counter

from pdf_lines import page_lines

HEAD_MARK = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 6}
NUMBERED = re.compile(r"^\d+(?:\.\d+)*\.?\s")
DOT_LEADER_RE = re.compile(r"\.{4,}")
BULLET_RE = re.compile(r"^[\u00b7\u00d8\u00a7\u00b0\u00b1\uf000-\uf0ff]\s*")


def normalize(text):
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def strip_marks(text):
    return re.sub(r"\s+", " ", re.sub(r"[*_]+", " ", text)).strip()


def is_heading(title):
    title = title.strip()
    if not title or len(title) > 160 or BULLET_RE.match(title):
        return False
    return bool(NUMBERED.match(title))


def outline(doc):
    return [(level, title, page) for level, title, page in doc.get_toc() if is_heading(title)]


def heading_levels(doc):
    counts = Counter()
    for page in doc:
        for line in page_lines(page):
            counts[line["size"]] += len(line["text"])
    if not counts:
        return {}
    body = counts.most_common(1)[0][0]
    big = sorted({size for size in counts if size > body + 1}, reverse=True)
    return {size: min(rank + 2, 6) for rank, size in enumerate(big)}


def size_heading(line, levels):
    level = levels.get(line["size"])
    text = strip_marks(line["text"])
    if not level or len(text) > 160 or BULLET_RE.match(line["text"]):
        return None
    if DOT_LEADER_RE.search(text):
        return None
    return level, text


def heads_by_page(entries):
    grouped = {}
    for entry in entries:
        grouped.setdefault(entry[2], []).append(entry)
    return grouped


def match_heading(line, page_heads, used):
    text = normalize(line["text"])
    if not text:
        return None
    for index, (level, title, page) in enumerate(page_heads):
        if index in used:
            continue
        target = normalize(title)
        if not target or len(target) < 2:
            continue
        if text == target or text.startswith(target[:18]) or target.startswith(text[:18]):
            used.add(index)
            body = strip_marks(line["text"])
            name = title if len(target) >= len(text) else body
            return HEAD_MARK.get(level, 6), name
    return None
