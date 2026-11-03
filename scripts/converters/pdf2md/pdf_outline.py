import re
from collections import Counter

from pdf_lines import EDGE, MAX_TITLE_LEN, page_lines

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

def at_edge(line, page):
    height = page.rect.height
    return line["y0"] / height < EDGE or line["y1"] / height > 1 - EDGE


def repeated_texts(doc):
    counts, pages = {}, 0
    for page in doc:
        lines = page_lines(page)
        if not lines:
            continue
        pages += 1
        seen = set()
        for line in lines:
            text = line["text"]
            if len(text) < MAX_TITLE_LEN and at_edge(line, page) and text not in seen:
                seen.add(text)
                counts[text] = counts.get(text, 0) + 1
    if pages < 3:
        return frozenset()
    threshold = max(3, pages * 0.6)
    return frozenset(text for text, count in counts.items() if count >= threshold)
